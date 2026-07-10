from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace

from pydantic import ValidationError

from answer_engine import (
    AnalysisClaim,
    AnswerCard,
    BackingRef,
)
from llm.boundaries import LLM_FORBIDDEN_WORDING
from llm.config import LLMConfigurationError, resolve_model
from llm.providers import LLMProviderError, StructuredLLMProvider
from llm.schemas import (
    BackingEntry,
    FilteredAnswerCard,
    NarrativeClaim,
    NarrativeDraft,
)


COMPOSER_SYSTEM_PROMPT = """你是 ST Research Copilot 的证据叙述器。
你只能根据 filtered_answer_card、backing_catalog 和 evidence_summary 生成 claim blocks。
每条 claim 必须引用 backing_catalog 中真实存在的 query_row 或 lens_invocation。
不得补造数字、日期、事件、因果或证据等级，不得输出买卖、持有、仓位、目标价或排序建议。
缺乏 backing 时不要生成该 claim。输出只包含结构化 claims，不输出自由文本答案。
"""


@dataclass(frozen=True)
class RejectedClaim:
    claim: NarrativeClaim
    reason: str


@dataclass(frozen=True)
class CompositionResult:
    answer_card: AnswerCard
    accepted_claims: list[AnalysisClaim]
    rejected_claims: list[RejectedClaim]
    llm_used: bool = True
    degraded_reasons: list[str] | None = None

    def public_payload(self) -> dict:
        """Only validated AnswerCard content may cross the API/UI boundary."""
        return self.answer_card.to_dict()

    def verified_claims_payload(self) -> list[dict]:
        return [
            {
                "text": claim.text,
                "claim_type": claim.claim_type,
                "backing": {
                    "kind": claim.backing.kind,
                    "ref": claim.backing.ref,
                },
            }
            for claim in self.answer_card.analysis_claims
        ]


def _compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _unsupported_numbers(text: str, backing_summary: str) -> list[str]:
    numbers = set(re.findall(r"(?<![A-Za-z0-9-])\d+(?:\.\d+)?%?", text))
    return sorted(number for number in numbers if number not in backing_summary)


def _filtered_card(card: AnswerCard) -> FilteredAnswerCard:
    return FilteredAnswerCard(
        question=card.question,
        object_ref=card.object_ref,
        view=card.view,
        as_of=card.as_of,
        sample_scope=card.sample_scope,
        evidence_grade=card.evidence_grade,
        body_rows=card.body_rows,
        caveats=card.caveats,
        data_debt_summary=[
            f"{row.debt_ref}: {row.gap} -> {row.affects}" for row in card.data_debt
        ],
        lens_gap_summary=[
            f"{gap.gap_id}: {gap.missing_for} -> {gap.sediment_as}" for gap in card.lens_gap
        ],
    )


def _backing_catalog(card: AnswerCard) -> list[BackingEntry]:
    entries = [
        BackingEntry(
            kind="query_row",
            ref=str(row["row_id"]),
            summary=_compact_json({key: value for key, value in row.items() if key != "row_id"}),
        )
        for row in card.body_rows
    ]
    entries.extend(
        BackingEntry(
            kind="lens_invocation",
            ref=invocation.release_id,
            summary=_compact_json({
                "lens_kind": invocation.lens_kind,
                "contributed_section": invocation.contributed_section,
                "logic_chain_summary": invocation.logic_chain_summary,
                "evidence_grade": invocation.evidence_grade,
                "cohort_id": invocation.cohort_id,
                "allowed_wording": invocation.allowed_wording,
                "forbidden_wording": invocation.forbidden_wording,
            }),
        )
        for invocation in card.lens_invocations
    )
    return entries


class NarrativeComposer:
    def __init__(self, provider: StructuredLLMProvider, *, model: str | None = None) -> None:
        self._provider = provider
        self._model = model

    def compose(self, card: AnswerCard) -> CompositionResult:
        card.validate()
        filtered = _filtered_card(card)
        catalog = _backing_catalog(card)
        payload = {
            "filtered_answer_card": filtered.model_dump(mode="json"),
            "backing_catalog": [entry.model_dump(mode="json") for entry in catalog],
            "evidence_summary": [entry.summary for entry in catalog],
        }
        draft = self._provider.generate(
            response_model=NarrativeDraft,
            system_prompt=COMPOSER_SYSTEM_PROMPT,
            payload=payload,
            model=resolve_model(self._model),
        )

        backing_summaries = {(entry.kind, entry.ref): entry.summary for entry in catalog}
        valid_backings = set(backing_summaries)
        accepted: list[AnalysisClaim] = []
        rejected: list[RejectedClaim] = []
        seen: set[tuple[str, str, str]] = {
            (claim.text, claim.backing.kind, claim.backing.ref)
            for claim in card.analysis_claims
        }
        for claim in draft.claims:
            backing_key = (claim.backing.kind, claim.backing.ref)
            hit = [term for term in LLM_FORBIDDEN_WORDING if term in claim.text]
            dedupe_key = (claim.text, *backing_key)
            if backing_key not in valid_backings:
                rejected.append(RejectedClaim(claim, "backing 不在可引用目录"))
                continue
            if hit:
                rejected.append(RejectedClaim(claim, f"命中禁用交易措辞: {hit}"))
                continue
            unsupported_numbers = _unsupported_numbers(
                claim.text, backing_summaries[backing_key]
            )
            if unsupported_numbers:
                rejected.append(RejectedClaim(
                    claim,
                    f"claim 含 backing 未出现的数字: {unsupported_numbers}",
                ))
                continue
            if dedupe_key in seen:
                rejected.append(RejectedClaim(claim, "重复 claim"))
                continue
            seen.add(dedupe_key)
            accepted.append(AnalysisClaim(
                text=claim.text,
                claim_type=claim.claim_type,
                backing=BackingRef(kind=claim.backing.kind, ref=claim.backing.ref),
            ))

        composed = replace(card, analysis_claims=[*card.analysis_claims, *accepted])
        composed.validate()
        return CompositionResult(
            answer_card=composed,
            accepted_claims=accepted,
            rejected_claims=rejected,
            llm_used=True,
            degraded_reasons=[],
        )

    def compose_or_fallback(self, card: AnswerCard) -> CompositionResult:
        try:
            return self.compose(card)
        except (LLMProviderError, LLMConfigurationError, ValidationError) as exc:
            card.validate()
            return CompositionResult(
                answer_card=card,
                accepted_claims=[],
                rejected_claims=[],
                llm_used=False,
                degraded_reasons=[f"LLM 叙述生成降级: {type(exc).__name__}"],
            )
