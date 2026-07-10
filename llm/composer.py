from __future__ import annotations

from copy import deepcopy
from typing import Any

from answer_engine import (
    AnalysisClaim,
    AnswerCard,
    BackingRef,
    DataDebtRow,
)
from lens_binding import LensGap, LensInvocation

from .models import AnalysisClaimOutput, ClaimBatch
from .providers import StructuredLLMProvider


COMPOSER_INSTRUCTIONS = """你是 ST 历史研究叙述层，只能重组输入中的证据菜单。
每条 claim 必须引用 backing_catalog 中的一项；不得引入新数字、新日期、新事实、
新证据等级或买卖/持有/仓位/目标价建议。缺口应写成 caveat、question 或 data_gap。"""


def backing_catalog(card: dict[str, Any]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    refs.extend({"kind": "lens_invocation", "ref": row["release_id"]}
                for row in card.get("lens_invocations", []) if row.get("release_id"))
    refs.extend({"kind": "query_row", "ref": row["row_id"]}
                for row in card.get("body_rows", []) if row.get("row_id"))
    refs.extend({"kind": "provenance_ref", "ref": ref}
                for ref in card.get("provenance", []) if ref)
    refs.extend({"kind": "data_debt", "ref": ref}
                for ref in card.get("data_debt_refs", []) if ref)
    refs.extend({"kind": "lens_gap", "ref": row["gap_id"]}
                for row in card.get("lens_gap", []) if row.get("gap_id"))
    return refs


def minimal_composer_payload(card: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "question", "object_ref", "view", "as_of", "sample_scope", "evidence_grade",
        "lens_invocations", "lens_gap", "body_rows", "analysis_claims", "data_debt",
        "data_debt_refs", "caveats", "provenance",
    }
    payload = {key: deepcopy(value) for key, value in card.items() if key in allowed}
    payload["existing_claims"] = payload.pop("analysis_claims", [])
    payload["backing_catalog"] = backing_catalog(card)
    return payload


def _rehydrate(card: dict[str, Any], claims: list[AnalysisClaimOutput]) -> AnswerCard:
    values = deepcopy(card)
    values["lens_invocations"] = [LensInvocation(**row) for row in values.get("lens_invocations", [])]
    values["lens_gap"] = [LensGap(**row) for row in values.get("lens_gap", [])]
    values["data_debt"] = [DataDebtRow(**row) for row in values.get("data_debt", [])]
    values["analysis_claims"] = [
        AnalysisClaim(
            text=claim.text,
            claim_type=claim.claim_type,
            backing=BackingRef(kind=claim.backing.kind, ref=claim.backing.ref),
        )
        for claim in claims
    ]
    return AnswerCard(**values)


def validate_claims_against_card(
    card: dict[str, Any], claims: list[AnalysisClaimOutput]
) -> list[dict[str, Any]]:
    rehydrated = _rehydrate(card, claims)
    rehydrated.validate()
    return [claim.model_dump(mode="json") for claim in claims]


class NarrativeComposer:
    def __init__(self, provider: StructuredLLMProvider) -> None:
        self.provider = provider

    def compose(self, card: dict[str, Any]) -> list[dict[str, Any]]:
        batch = self.provider.parse(
            response_model=ClaimBatch,
            instructions=COMPOSER_INSTRUCTIONS,
            payload=minimal_composer_payload(card),
        )
        return validate_claims_against_card(card, batch.claims)
