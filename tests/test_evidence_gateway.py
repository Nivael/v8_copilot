from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from api_contract import ResearchRequest
from api_contract_v2 import NarrativeStatement, ResearchNarrative
from evidence_gateway import (
    DecisionAudit,
    DecisionFactor,
    EvidencePack,
    ResearchDraft,
    build_evidence_pack,
    validate_research_draft,
)


def test_evidence_pack_adapts_deterministic_answer_without_changing_contracts() -> None:
    pack = build_evidence_pack(ResearchRequest(
        question="沐邦和南都怎么比较？",
        llm_mode="off",
    ))

    assert pack.pack_id.startswith("EP-")
    assert pack.question_scope["route"] == "answer_query"
    assert pack.rows
    assert pack.deterministic_response["contract_version"] == "v8_copilot_api_contract_v2"
    assert pack.validation_catalog
    assert pack.not_evidence is False


def test_evidence_pack_detects_tampering() -> None:
    pack = build_evidence_pack(ResearchRequest(
        question="ST面板自身两周涨跌分布如何？",
        llm_mode="off",
    ))
    payload = pack.model_dump(mode="json")
    payload["rows"][0]["样本数"] = 999999

    with pytest.raises(ValidationError, match="digest"):
        EvidencePack.model_validate(payload)


def test_validator_requires_real_backing_and_rejects_action_wording() -> None:
    pack = build_evidence_pack(ResearchRequest(
        question="沐邦和南都怎么比较？",
        llm_mode="off",
    ))
    first_ref = next(iter(pack.validation_catalog)).split(":", 1)
    backing = {"kind": first_ref[0], "ref": first_ref[1]}
    draft = ResearchDraft(narrative=ResearchNarrative(
        direct_answer=NarrativeStatement(
            text="可以买入其中一只。",
            backing=[backing],
        ),
        reasoning_steps=[],
        uncertainties=[],
        watch_items=[],
        basis_note="只读 EvidencePack。",
    ))

    report = validate_research_draft(pack, draft)

    assert report.valid is False
    assert "forbidden_wording" in {issue.code for issue in report.issues}


def test_validator_rejects_backing_not_in_pack() -> None:
    pack = build_evidence_pack(ResearchRequest(
        question="ST面板自身两周涨跌分布如何？",
        llm_mode="off",
    ))
    draft = ResearchDraft(narrative=ResearchNarrative(
        direct_answer=NarrativeStatement(
            text="现有证据支持描述性比较。",
            backing=[{"kind": "query_row", "ref": "missing-row"}],
        ),
        basis_note="只读 EvidencePack。",
    ))

    report = validate_research_draft(pack, draft)

    assert report.valid is False
    assert report.issues[0].code == "missing_backing"


def test_validator_audits_ordinal_decision_factors_against_pack() -> None:
    pack = build_evidence_pack(ResearchRequest(
        question="沐邦和南都怎么比较？",
        llm_mode="off",
    ))
    kind, ref = next(iter(pack.validation_catalog)).split(":", 1)
    backing = {"kind": kind, "ref": ref}
    draft = ResearchDraft(narrative=ResearchNarrative(
        direct_answer=NarrativeStatement(text="现有证据支持有限比较。", backing=[backing]),
        basis_note="只读 EvidencePack。",
    ), decision_audit=DecisionAudit(
        judgment="现有证据支持有限比较。",
        judgment_backing=[backing],
        confidence="medium",
        factors=[DecisionFactor(
            factor_id="entity_scope", label="主体口径", direction="limits",
            importance="decisive", rationale="主体口径限制比较范围。", backing=[backing],
        )],
    ))

    report = validate_research_draft(pack, draft)

    assert report.valid is True
    assert report.decision_audit_status == "complete"
    assert report.checked_backings >= 3
