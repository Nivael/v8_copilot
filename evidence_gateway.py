"""Read-only adapter from the deterministic v8 engine to Codex EvidencePacks."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api_contract import ClaimBacking, ResearchRequest
from api_contract_v2 import ResearchNarrative
from llm_adapter import orchestrate_optional_llm
from orchestrator_v1 import enrich_response_v1
from orchestrator_v2 import enrich_response_v2
from freshness_manifest import load_freshness_manifest
from settings import FRESHNESS_MANIFEST_PATH


EVIDENCE_PACK_VERSION = "v8_evidence_pack_v2"
VALIDATION_REPORT_VERSION = "v8_research_validation_report_v1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ApplicableExperience(StrictModel):
    experience_id: str
    title: str
    experience_type: str
    value_summary: str
    trigger_conditions: list[str]
    topic_tags: list[str] = Field(default_factory=list)
    answer_rubric: list[str]
    coverage_boundaries: list[str]
    version: int = Field(ge=1)
    not_evidence: Literal[True] = True


class ExternalEvidenceFactInput(StrictModel):
    fact_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$")
    text: str = Field(min_length=1, max_length=2000)


class ExternalEvidenceInput(StrictModel):
    source_kind: Literal[
        "official_announcement", "official_exchange_or_regulator",
        "official_court_or_administrator", "official_company_profile",
        "official_financial_report", "market_data_provider",
    ]
    source_mode: Literal["verified_materialization", "live_web_observation"]
    subject_ref: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=500)
    source_url: str = Field(pattern=r"^https?://", max_length=2000)
    published_at: str = ""
    fetched_at: str
    coverage_note: str = Field(min_length=1, max_length=1200)
    facts: list[ExternalEvidenceFactInput] = Field(min_length=1, max_length=30)


class ExternalEvidenceItem(ExternalEvidenceInput):
    evidence_id: str = Field(pattern=r"^EXT-[A-F0-9]{20}$")
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    not_mechanism_evidence: Literal[True] = True


class EvidenceAcquisitionPlan(StrictModel):
    online_fact_lookup: bool
    online_purposes: list[str]
    offline_mechanisms: list[str]
    reasons: list[str]
    synthesis_rule: Literal[
        "external_facts_and_local_mechanisms_must_share_one_validated_evidence_pack"
    ] = "external_facts_and_local_mechanisms_must_share_one_validated_evidence_pack"


class EvidencePack(StrictModel):
    contract_version: Literal[EVIDENCE_PACK_VERSION] = EVIDENCE_PACK_VERSION
    pack_id: str = Field(pattern=r"^EP-[A-F0-9]{20}$")
    pack_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    question_scope: dict[str, Any]
    query_plan_id: str
    rows: list[dict[str, Any]]
    lens_invocations: list[dict[str, Any]]
    external_evidence: list[ExternalEvidenceItem] = Field(default_factory=list)
    freshness_manifest: dict[str, Any]
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
    decision_audit: "DecisionAudit | None" = None


class DecisionFactor(StrictModel):
    factor_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$")
    label: str = Field(min_length=1, max_length=120)
    direction: Literal["supports", "weakens", "limits", "context"]
    importance: Literal["decisive", "high", "medium", "low"]
    rationale: str = Field(min_length=1, max_length=1200)
    backing: list[ClaimBacking] = Field(min_length=1, max_length=20)


class DecisionAlternative(StrictModel):
    label: str = Field(min_length=1, max_length=160)
    disposition: Literal["selected", "rejected", "unresolved"]
    reason: str = Field(min_length=1, max_length=1200)
    backing: list[ClaimBacking] = Field(min_length=1, max_length=20)


class DecisionAudit(StrictModel):
    weighting_method: Literal["ordinal_evidence_weighting_v0"] = "ordinal_evidence_weighting_v0"
    judgment: str = Field(min_length=1, max_length=1200)
    judgment_backing: list[ClaimBacking] = Field(min_length=1, max_length=20)
    confidence: Literal["high", "medium", "low", "insufficient"]
    factors: list[DecisionFactor] = Field(min_length=1, max_length=20)
    alternatives: list[DecisionAlternative] = Field(default_factory=list, max_length=12)
    not_hidden_chain_of_thought: Literal[True] = True


class ValidationIssue(StrictModel):
    code: str
    message: str
    statement: str = ""


class ValidationReport(StrictModel):
    contract_version: Literal[VALIDATION_REPORT_VERSION] = VALIDATION_REPORT_VERSION
    valid: bool
    pack_id: str
    pack_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    draft_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    issues: list[ValidationIssue] = Field(default_factory=list)
    checked_statements: int = Field(ge=0)
    checked_backings: int = Field(ge=0)
    decision_audit_status: Literal["complete", "not_provided"] = "not_provided"


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


def _current_freshness_manifest() -> dict[str, Any]:
    if not FRESHNESS_MANIFEST_PATH.is_file():
        return {"status": "not_published", "manifest_id": "", "coverage_gaps": [
            "数据维护窗口尚未发布统一 freshness manifest。"
        ]}
    try:
        manifest = load_freshness_manifest(FRESHNESS_MANIFEST_PATH)
        return manifest.model_dump(mode="json")
    except (OSError, ValueError) as exc:
        return {
            "status": "invalid", "manifest_id": "",
            "coverage_gaps": [f"统一 freshness manifest 无法校验: {exc}"],
        }


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
        "lens_invocations": list(card.get("lens_invocations", [])),
        "external_evidence": [],
        "freshness_manifest": _current_freshness_manifest(),
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


def plan_evidence_acquisition(pack: EvidencePack) -> EvidenceAcquisitionPlan:
    """Decide whether current factual acquisition may use the network.

    Online lookup supplements current facts only.  Cohorts, episodes, Lens results,
    path calculations and other mechanism outputs always remain local/reproducible.
    """
    question = str(pack.question_scope.get("question") or "")
    gaps_text = _canonical_json({
        "coverage_gaps": pack.coverage_gaps,
        "freshness_manifest": pack.freshness_manifest,
    })
    purposes: list[str] = []
    if any(term in question for term in ("最新公告", "公告说了什么", "最新披露")):
        purposes.append("latest_official_announcement")
    if any(term in question for term in ("基本面", "财务", "主营", "公司资料", "股东户数")):
        purposes.append("current_company_fundamentals")
    if any(term in question for term in ("公开招募", "管理人", "破产重整", "法院", "截止日")):
        purposes.append("official_proceeding_channel")
    if any(term in question for term in ("今天", "当前价格", "跌停", "涨停")):
        purposes.append("current_market_fact")
    if any(term in gaps_text for term in ("未覆盖", "其他渠道", "尚未材料化", "stale", "freshness")):
        purposes.append("declared_coverage_gap")
    purposes = list(dict.fromkeys(purposes))
    reasons = []
    if purposes:
        reasons.append("问题包含当前事实或本地 EvidencePack 已声明来源覆盖缺口。")
    else:
        reasons.append("本题没有识别到必须补充的当前外部事实，优先保持完全可复现。")
    return EvidenceAcquisitionPlan(
        online_fact_lookup=bool(purposes),
        online_purposes=purposes,
        offline_mechanisms=[
            "database_rows", "episode_and_case_deduplication", "lens_invocations",
            "historical_distributions", "event_window_and_price_path_calculations",
        ],
        reasons=reasons,
    )


def augment_evidence_pack(
    pack: EvidencePack,
    external_inputs: list[ExternalEvidenceInput],
) -> EvidencePack:
    """Bind separately acquired online facts into a new immutable EvidencePack."""
    if not external_inputs:
        return pack
    items = list(pack.external_evidence)
    catalog = dict(pack.validation_catalog)
    provenance = list(pack.provenance)
    source_freshness = dict(pack.source_freshness)
    existing_ids = {item.evidence_id for item in items}
    for value in external_inputs:
        try:
            fetched_at = datetime.fromisoformat(value.fetched_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"external fetched_at 非法: {value.fetched_at!r}") from exc
        if fetched_at.tzinfo is None:
            raise ValueError("external fetched_at 必须带时区")
        if fetched_at > datetime.now(timezone.utc):
            raise ValueError("external fetched_at 不能晚于当前时间")
        if value.published_at:
            try:
                datetime.fromisoformat(value.published_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(
                    f"external published_at 非法: {value.published_at!r}"
                ) from exc
        content = value.model_dump(mode="json")
        digest = _digest(content)
        evidence_id = f"EXT-{digest[:20].upper()}"
        item = ExternalEvidenceItem(
            **content, evidence_id=evidence_id, content_digest=digest,
        )
        if evidence_id not in existing_ids:
            items.append(item)
            existing_ids.add(evidence_id)
        if value.source_url not in provenance:
            provenance.append(value.source_url)
        source_freshness[f"external:{evidence_id}"] = value.fetched_at
        for fact in value.facts:
            catalog[f"provenance_ref:{evidence_id}:{fact.fact_id}"] = _canonical_json({
                "fact": fact.text,
                "title": value.title,
                "subject_ref": value.subject_ref,
                "source_kind": value.source_kind,
                "source_mode": value.source_mode,
                "source_url": value.source_url,
                "published_at": value.published_at,
                "fetched_at": value.fetched_at,
                "coverage_note": value.coverage_note,
            })
    payload = pack.model_dump(mode="json", exclude={"pack_id", "pack_digest"})
    payload.update({
        "external_evidence": [item.model_dump(mode="json") for item in items],
        "validation_catalog": catalog,
        "provenance": provenance,
        "source_freshness": source_freshness,
    })
    digest = _digest(payload)
    return EvidencePack.model_validate({
        **payload, "pack_id": f"EP-{digest[:20].upper()}", "pack_digest": digest,
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

    def check_statement(text: str, backings: list[ClaimBacking]) -> None:
        nonlocal checked_backings
        summaries: list[str] = []
        for backing in backings:
            checked_backings += 1
            key = f"{backing.kind}:{backing.ref}"
            summary = pack.validation_catalog.get(key)
            if summary is None:
                issues.append(ValidationIssue(
                    code="missing_backing",
                    message=f"backing 不在 EvidencePack: {key}",
                    statement=text,
                ))
            else:
                summaries.append(summary)
        forbidden = [term for term in LLM_FORBIDDEN_WORDING if term in text]
        if forbidden:
            issues.append(ValidationIssue(
                code="forbidden_wording",
                message=f"命中禁用交易措辞: {forbidden}",
                statement=text,
            ))
        if summaries:
            supported = _numeric_tokens(" ".join(summaries))
            unsupported = sorted(_numeric_tokens(text) - supported)
            if unsupported:
                issues.append(ValidationIssue(
                    code="unsupported_number_or_date",
                    message=f"数字或日期没有被引用 backing 支持: {unsupported}",
                    statement=text,
                ))

    for statement in statements:
        check_statement(statement.text, statement.backing)
    audit = draft.decision_audit
    if audit is not None:
        check_statement(audit.judgment, audit.judgment_backing)
        for factor in audit.factors:
            check_statement(f"{factor.label}：{factor.rationale}", factor.backing)
        for alternative in audit.alternatives:
            check_statement(f"{alternative.label}：{alternative.reason}", alternative.backing)
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
        pack_digest=pack.pack_digest,
        draft_digest=_digest(draft.model_dump(mode="json")),
        issues=issues,
        checked_statements=(
            len(statements)
            + (1 + len(audit.factors) + len(audit.alternatives) if audit else 0)
        ),
        checked_backings=checked_backings,
        decision_audit_status="complete" if audit else "not_provided",
    )
