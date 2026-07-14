"""Read-only adapter from the deterministic v8 engine to Codex EvidencePacks."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api_contract import ClaimBacking, ResearchRequest
from api_contract_v2 import ResearchNarrative
from llm_adapter import orchestrate_optional_llm
from orchestrator_v1 import enrich_response_v1
from orchestrator_v2 import enrich_response_v2


EVIDENCE_PACK_VERSION = "v8_evidence_pack_v0"
VALIDATION_REPORT_VERSION = "v8_research_validation_report_v0"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ApplicableExperience(StrictModel):
    experience_id: str
    title: str
    experience_type: str
    value_summary: str
    trigger_conditions: list[str]
    answer_rubric: list[str]
    coverage_boundaries: list[str]
    version: int = Field(ge=1)
    not_evidence: Literal[True] = True


class EvidencePack(StrictModel):
    contract_version: Literal[EVIDENCE_PACK_VERSION] = EVIDENCE_PACK_VERSION
    pack_id: str = Field(pattern=r"^EP-[A-F0-9]{20}$")
    pack_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    question_scope: dict[str, Any]
    query_plan_id: str
    rows: list[dict[str, Any]]
    source_freshness: dict[str, str]
    provenance: list[str]
    coverage_gaps: list[dict[str, Any]]
    definitions: list[str]
    allowed_claims: list[dict[str, Any]]
    forbidden_inferences: list[str]
    validation_catalog: dict[str, str]
    applicable_experiences: list[ApplicableExperience] = Field(default_factory=list)
    deterministic_response: dict[str, Any]
    not_evidence: Literal[False] = False

    @model_validator(mode="after")
    def digest_matches_content(self) -> "EvidencePack":
        payload = self.model_dump(mode="json", exclude={"pack_id", "pack_digest"})
        digest = _digest(payload)
        if digest != self.pack_digest:
            raise ValueError("EvidencePack digest 不匹配")
        if self.pack_id != f"EP-{digest[:20].upper()}":
            raise ValueError("EvidencePack id 不匹配")
        return self


class ResearchDraft(StrictModel):
    narrative: ResearchNarrative


class ValidationIssue(StrictModel):
    code: str
    message: str
    statement: str = ""


class ValidationReport(StrictModel):
    contract_version: Literal[VALIDATION_REPORT_VERSION] = VALIDATION_REPORT_VERSION
    valid: bool
    pack_id: str
    issues: list[ValidationIssue] = Field(default_factory=list)
    checked_statements: int = Field(ge=0)
    checked_backings: int = Field(ge=0)


class DraftValidationRequest(StrictModel):
    evidence_pack: EvidencePack
    draft: ResearchDraft


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _deterministic_response(request: ResearchRequest):
    local_request = request.model_copy(update={"llm_mode": "off"})
    base = orchestrate_optional_llm(local_request)
    response_v1 = enrich_response_v1(local_request, base)
    return enrich_response_v2(local_request, response_v1)


def _catalog(answer_card: dict[str, Any]) -> dict[str, str]:
    catalog: dict[str, str] = {}
    for row in answer_card.get("body_rows", []):
        row_id = row.get("row_id")
        if row_id:
            catalog[f"query_row:{row_id}"] = _canonical_json(
                {key: value for key, value in row.items() if key != "row_id"}
            )
    for row in answer_card.get("lens_invocations", []):
        release_id = row.get("release_id")
        if release_id:
            catalog[f"lens_invocation:{release_id}"] = _canonical_json(row)
    for ref in answer_card.get("provenance", []):
        catalog[f"provenance_ref:{ref}"] = _canonical_json({"source": ref})
    for row in answer_card.get("data_debt", []):
        ref = row.get("debt_ref")
        if ref:
            catalog[f"data_debt:{ref}"] = _canonical_json(row)
    for row in answer_card.get("lens_gap", []):
        ref = row.get("gap_id")
        if ref:
            catalog[f"lens_gap:{ref}"] = _canonical_json(row)
    return catalog


def _applicable_experiences(question: str, *, repository=None) -> list[ApplicableExperience]:
    if repository is None:
        return []
    return [
        ApplicableExperience.model_validate(row)
        for row in repository.retrieve_accepted(question, limit=8)
    ]


def build_evidence_pack(
    request: ResearchRequest,
    *,
    experience_repository=None,
) -> EvidencePack:
    """Execute only local deterministic readers and package their evidence for Codex."""
    response = _deterministic_response(request)
    card = response.answer_card or {}
    route_rules = list(response.route.matched_rules)
    query_plan_id = response.query_template_id or (
        route_rules[0] if route_rules else response.route.route
    )
    gaps = [gap.model_dump(mode="json") for gap in response.gaps]
    gaps.extend(card.get("lens_gap", []))
    gaps.extend(card.get("data_debt", []))
    object_ref = response.interpretation.object.model_dump(mode="json")
    payload: dict[str, Any] = {
        "contract_version": EVIDENCE_PACK_VERSION,
        "question_scope": {
            "question": request.question,
            "object": object_ref,
            "intent": response.interpretation.intent,
            "route": response.route.route,
            "matched_rules": route_rules,
            "as_of": card.get("as_of", ""),
        },
        "query_plan_id": query_plan_id,
        "rows": list(card.get("body_rows", [])),
        "source_freshness": dict(card.get("source_freshness", {})),
        "provenance": list(card.get("provenance", [])),
        "coverage_gaps": gaps,
        "definitions": [
            value for value in (
                card.get("sample_scope"),
                card.get("evidence_grade"),
                *card.get("caveats", []),
            ) if value
        ],
        "allowed_claims": [claim.model_dump(mode="json") for claim in response.claims],
        "forbidden_inferences": [
            "不得把描述性历史样本升级为当前个案预测。",
            "不得混淆上市公司本体与子公司、孙公司或控股股东。",
            "不得把单一来源未找到扩大成现实中没有发生。",
            "不得输出买卖、持有、仓位、目标价或排序建议。",
        ],
        "validation_catalog": _catalog(card),
        "applicable_experiences": [
            row.model_dump(mode="json")
            for row in _applicable_experiences(
                request.question,
                repository=experience_repository,
            )
        ],
        "deterministic_response": response.model_dump(mode="json"),
        "not_evidence": False,
    }
    digest = _digest(payload)
    return EvidencePack.model_validate({
        **payload,
        "pack_id": f"EP-{digest[:20].upper()}",
        "pack_digest": digest,
    })


def _numeric_tokens(text: str) -> set[str]:
    import re

    dates = re.findall(r"20\d{2}(?:[-年/]\d{1,2})?(?:[-月/]\d{1,2})?日?", text)
    numbers = re.findall(r"(?<![A-Za-z0-9])[-+]?\d[\d,]*(?:\.\d+)?%?", text)
    return {token.replace(",", "") for token in [*dates, *numbers]}


def validate_research_draft(pack: EvidencePack, draft: ResearchDraft) -> ValidationReport:
    """Validate Codex-authored statements against the immutable EvidencePack catalog."""
    from llm.boundaries import LLM_FORBIDDEN_WORDING

    issues: list[ValidationIssue] = []
    statements = [
        draft.narrative.direct_answer,
        *draft.narrative.reasoning_steps,
        *draft.narrative.uncertainties,
        *draft.narrative.watch_items,
    ]
    checked_backings = 0
    for statement in statements:
        summaries: list[str] = []
        for backing in statement.backing:
            checked_backings += 1
            key = f"{backing.kind}:{backing.ref}"
            summary = pack.validation_catalog.get(key)
            if summary is None:
                issues.append(ValidationIssue(
                    code="missing_backing",
                    message=f"backing 不在 EvidencePack: {key}",
                    statement=statement.text,
                ))
            else:
                summaries.append(summary)
        forbidden = [term for term in LLM_FORBIDDEN_WORDING if term in statement.text]
        if forbidden:
            issues.append(ValidationIssue(
                code="forbidden_wording",
                message=f"命中禁用交易措辞: {forbidden}",
                statement=statement.text,
            ))
        if summaries:
            supported = _numeric_tokens(" ".join(summaries))
            unsupported = sorted(_numeric_tokens(statement.text) - supported)
            if unsupported:
                issues.append(ValidationIssue(
                    code="unsupported_number_or_date",
                    message=f"数字或日期没有被引用 backing 支持: {unsupported}",
                    statement=statement.text,
                ))
    direct = draft.narrative.direct_answer.text.strip()
    if direct.startswith(("本分析", "本题", "查询结果", "描述性查询")):
        issues.append(ValidationIssue(
            code="indirect_opening",
            message="主回答应先回答用户问题，不应以系统口径开头。",
            statement=direct,
        ))
    return ValidationReport(
        valid=not issues,
        pack_id=pack.pack_id,
        issues=issues,
        checked_statements=len(statements),
        checked_backings=checked_backings,
    )
