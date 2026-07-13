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
from api_contract import ClaimBacking as ApiClaimBacking
from api_contract_v2 import NarrativeStatement, NarrativeStep, ResearchNarrative
from llm.boundaries import LLM_FORBIDDEN_WORDING
from llm.config import LLMConfigurationError, resolve_model
from llm.providers import LLMProviderError, StructuredLLMProvider
from llm.schemas import (
    BackingEntry,
    FilteredAnswerCard,
    NarrativeClaim,
    NarrativeDraft,
)


COMPOSER_SYSTEM_PROMPT = """你是 ST Research Copilot 的证据分析师。
你只能根据 filtered_answer_card、backing_catalog 和 evidence_summary 生成 claim blocks 和面向研究者的完整 narrative。
先直接回答用户真正问的内容，再用 2-6 个有顺序的 reasoning_steps 解释证据如何支持答案；把不能确认的部分放入 uncertainties，把可核查的后续公开节点放入 watch_items。
每个 statement 和每条 claim 都必须引用 backing_catalog 中真实存在的 query_row、lens_invocation、provenance_ref、data_debt 或 lens_gap。
比较题必须逐维度比较，不得只说数据不足；阶段题必须把当前公开里程碑与历史后续分布分开。
公告题必须根据公告正文证据片段总结，不得只复述标题。
巨潮公告ID是披露平台文档标识，不是上市公司正文中的公告编号；只有“公告编号”字段才可称为公告编号。
不得补造数字、日期、事件、因果或证据等级，不得输出买卖、持有、仓位、目标价或排序建议。
数量和日期必须原样保留 backing 中的阿拉伯数字，不要改写成新的中文数量表达。
缺乏 backing 时不要生成该 statement 或 claim。输出只包含结构化字段，不输出 schema 外自由文本。
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
    research_narrative: ResearchNarrative | None = None
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


def _numeric_tokens(text: str) -> set[str]:
    tokens: set[str] = set()

    def normalized_number(value: str) -> str:
        return value.replace(",", "").removeprefix("+")

    def mask(pattern: str, formatter) -> None:
        nonlocal text

        def replace_match(match: re.Match[str]) -> str:
            tokens.add(formatter(match))
            return " " * len(match.group(0))

        text = re.sub(pattern, replace_match, text)

    mask(
        r"(?<!\d)(20\d{2})[-/](\d{1,2})[-/](\d{1,2})(?!\d)",
        lambda match: (
            f"date:{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
        ),
    )
    mask(
        r"(?<!\d)(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        lambda match: (
            f"date:{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
        ),
    )
    number = r"[-+]?\d[\d,]*(?:\.\d+)?%?"
    mask(
        rf"(?<![A-Za-z0-9])({number})\s*(?:至|到|~|—|–|-)\s*({number})",
        lambda match: (
            f"range:{normalized_number(match.group(1))}..{normalized_number(match.group(2))}"
        ),
    )
    tokens.update(
        normalized_number(token)
        for token in re.findall(r"(?<![A-Za-z0-9])[-+]?\d[\d,]*(?:\.\d+)?%?", text)
    )
    return tokens


def _unsupported_numbers(text: str, backing_summary: str) -> list[str]:
    unsupported = _numeric_tokens(text) - _numeric_tokens(backing_summary)
    quantity_pattern = (
        r"(?<![下第某每其])[两三四五六七八九十百千万亿]+"
        r"(?:天|周|个?月|年|倍|成)"
    )
    unsupported.update(
        set(re.findall(quantity_pattern, text))
        - set(re.findall(quantity_pattern, backing_summary))
    )
    chinese_percent = r"(?:百分之[一二两三四五六七八九十百千万亿]+|[一二两三四五六七八九十百千万亿]+%)"
    unsupported.update(
        set(re.findall(chinese_percent, text))
        - set(re.findall(chinese_percent, backing_summary))
    )
    return sorted(unsupported)


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
    entries.extend(
        BackingEntry(
            kind="data_debt",
            ref=row.debt_ref,
            summary=_compact_json({"gap": row.gap, "affects": row.affects}),
        )
        for row in card.data_debt
    )
    entries.extend(
        BackingEntry(
            kind="lens_gap",
            ref=gap.gap_id,
            summary=_compact_json({
                "missing_for": gap.missing_for,
                "sediment_as": gap.sediment_as,
                "note": gap.note,
            }),
        )
        for gap in card.lens_gap
    )
    entries.extend(
        BackingEntry(
            kind="provenance_ref",
            ref=ref,
            summary=_compact_json({"source": ref}),
        )
        for ref in card.provenance
    )
    return entries


def _validated_statement(
    statement: object,
    backing_summaries: dict[tuple[str, str], str],
    *,
    title: str | None = None,
) -> NarrativeStatement | NarrativeStep:
    text = str(getattr(statement, "text"))
    raw_backing = list(getattr(statement, "backing"))
    keys = [(item.kind, item.ref) for item in raw_backing]
    missing = [key for key in keys if key not in backing_summaries]
    if missing:
        raise ValidationError.from_exception_data(
            "StructuredNarrativeDraft",
            [{"type": "value_error", "loc": ("backing",), "input": keys,
              "ctx": {"error": ValueError(f"backing 不在可引用目录: {missing}")}}],
        )
    hit = [term for term in LLM_FORBIDDEN_WORDING if term in text]
    if hit:
        raise ValidationError.from_exception_data(
            "StructuredNarrativeDraft",
            [{"type": "value_error", "loc": ("text",), "input": text,
              "ctx": {"error": ValueError(f"命中禁用交易措辞: {hit}")}}],
        )
    combined = " ".join(backing_summaries[key] for key in keys)
    if title is not None:
        normalized_title = re.sub(
            r"^\s*[一二三四五六七八九十0-9]+[.、：:]\s*", "", title
        )
        title_hit = [term for term in LLM_FORBIDDEN_WORDING if term in title]
        if title_hit:
            raise ValidationError.from_exception_data(
                "StructuredNarrativeDraft",
                [{"type": "value_error", "loc": ("title",), "input": title,
                  "ctx": {"error": ValueError(f"标题命中禁用交易措辞: {title_hit}")}}],
            )
        title_unsupported = _unsupported_numbers(normalized_title, combined)
        if title_unsupported:
            raise ValidationError.from_exception_data(
                "StructuredNarrativeDraft",
                [{"type": "value_error", "loc": ("title",), "input": title,
                  "ctx": {"error": ValueError(
                      f"标题含 backing 未出现的数字: {title_unsupported}"
                  )}}],
            )
    unsupported = _unsupported_numbers(text, combined)
    if unsupported:
        raise ValidationError.from_exception_data(
            "StructuredNarrativeDraft",
            [{"type": "value_error", "loc": ("text",), "input": text,
              "ctx": {"error": ValueError(f"statement 含 backing 未出现的数字: {unsupported}")}}],
        )
    backing = [ApiClaimBacking(kind=item.kind, ref=item.ref) for item in raw_backing]
    if title is not None:
        return NarrativeStep(title=normalized_title, text=text, backing=backing)
    return NarrativeStatement(text=text, backing=backing)


def _validated_narrative(
    card: AnswerCard,
    draft: object | None,
    backing_summaries: dict[tuple[str, str], str],
) -> tuple[ResearchNarrative | None, int]:
    if draft is None:
        return None, 0
    try:
        direct = _validated_statement(draft.direct_answer, backing_summaries)
    except ValidationError:
        return None, 1
    rejected = 0

    def collect(items: list[object], *, with_title: bool = False) -> list:
        nonlocal rejected
        accepted = []
        for item in items:
            try:
                accepted.append(_validated_statement(
                    item,
                    backing_summaries,
                    title=getattr(item, "title") if with_title else None,
                ))
            except ValidationError:
                rejected += 1
        return accepted

    steps = collect(list(draft.reasoning_steps), with_title=True)
    uncertainties = collect(list(draft.uncertainties))
    watch_items = collect(list(draft.watch_items))
    return ResearchNarrative(
        direct_answer=direct,
        reasoning_steps=steps,
        uncertainties=uncertainties,
        watch_items=watch_items,
        basis_note=(
            f"本分析仅组织 {len(card.body_rows)} 行可回链查询证据和 "
            f"{len(card.lens_invocations)} 条冻结 Lens；审阅材料与正文链接单独保留。"
        ),
    ), rejected


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

        research_narrative, rejected_statements = _validated_narrative(
            card, draft.narrative, backing_summaries
        )
        composed = replace(card, analysis_claims=[*card.analysis_claims, *accepted])
        composed.validate()
        return CompositionResult(
            answer_card=composed,
            accepted_claims=accepted,
            rejected_claims=rejected,
            research_narrative=research_narrative,
            llm_used=True,
            degraded_reasons=(
                [f"LLM 主叙述有 {rejected_statements} 个 statement 未通过 backing 校验，已剔除。"]
                if rejected_statements else []
            ) + (["LLM 未返回可用的主叙述。"] if research_narrative is None else []),
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
                research_narrative=None,
                llm_used=False,
                degraded_reasons=[f"LLM 叙述生成降级: {type(exc).__name__}"],
            )
