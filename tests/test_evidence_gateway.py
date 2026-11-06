from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from api_contract import ResearchObject, ResearchRequest
from api_contract_v2 import NarrativeStatement, ResearchNarrative
from evidence_gateway import (
    DecisionAudit,
    DecisionFactor,
    EvidencePack,
    ExternalEvidenceInput,
    ResearchDraft,
    build_evidence_pack,
    augment_evidence_pack,
    plan_evidence_acquisition,
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


@pytest.mark.parametrize('ref,code',[
    ('603398.SH','603398'),
    (' 603398.sh ','603398'),
    ('002207.SZ','002207'),
    ('002207.sz','002207'),
])
@pytest.mark.parametrize('question',[
    '预亏公告没给营收，能否从亏损倒推半年营收？',
    '今天跌停，预亏公告没给营收，能否从亏损倒推半年营收？',
])
def test_explicit_stock_suffix_uses_the_same_real_evidence_as_its_six_digit_code(ref,code,question) -> None:
    request=ResearchRequest(question=question,object=ResearchObject(kind='stock',ref=ref),llm_mode='off')
    pack=build_evidence_pack(request)
    plain=build_evidence_pack(ResearchRequest(question=question,object=ResearchObject(kind='stock',ref=code),llm_mode='off'))

    assert pack.question_scope['object']=={'kind':'stock','ref':code}
    assert pack.question_scope==plain.question_scope
    assert pack.rows and pack.rows==plain.rows
    assert pack.query_plan_id==plain.query_plan_id
    assert request.object.ref==ref


@pytest.mark.parametrize('ref',[
    '603398.SZ',
    '002207.SH',
    '603398.CSI',
    '603398.SH,002207.SZ',
    '看603398.SH',
    '1603398.SH',
    '603398.SH/备选',
])
def test_invalid_explicit_stock_identity_requests_clarification_without_guessing(ref) -> None:
    pack=build_evidence_pack(ResearchRequest(question='分析沐邦的营收与价格',object=ResearchObject(kind='stock',ref=ref),llm_mode='off'))

    assert pack.question_scope['object']=={'kind':'unknown','ref':ref}
    assert pack.question_scope['route']=='clarify'
    assert not pack.rows


def test_invalid_stock_identity_does_not_bypass_the_existing_action_boundary() -> None:
    pack=build_evidence_pack(ResearchRequest(question='可以买沐邦吗？',object=ResearchObject(kind='stock',ref='603398.SZ'),llm_mode='off'))

    assert pack.question_scope['route']=='refuse_or_rewrite'
    assert not pack.rows


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


def test_network_plan_keeps_mechanisms_local_and_augments_pack_with_auditable_fact() -> None:
    pack = build_evidence_pack(ResearchRequest(
        question="沐邦的公开招募最新推进到哪一步？",
        llm_mode="off",
    ))
    plan = plan_evidence_acquisition(pack)
    external = ExternalEvidenceInput(
        source_kind="official_court_or_administrator",
        source_mode="live_web_observation",
        subject_ref="603398",
        title="管理人公开招募说明",
        source_url="https://example.gov.cn/restructuring/603398",
        published_at="2026-07-14",
        fetched_at="2026-07-15T00:00:00+00:00",
        coverage_note="只补充管理人渠道当前事实，不替代本地历史样本计算。",
        facts=[{"fact_id": "deadline", "text": "公开招募截止日为2026-07-20。"}],
    )

    augmented = augment_evidence_pack(pack, [external])
    item = augmented.external_evidence[0]
    backing = {"kind": "provenance_ref", "ref": f"{item.evidence_id}:deadline"}
    draft = ResearchDraft(narrative=ResearchNarrative(
        direct_answer=NarrativeStatement(
            text="管理人渠道列明的公开招募截止日为2026-07-20。",
            backing=[backing],
        ),
        basis_note="联网事实与本地机制证据先合入同一 EvidencePack。",
    ))
    report = validate_research_draft(augmented, draft)

    assert plan.online_fact_lookup is True
    assert "episode_and_case_deduplication" in plan.offline_mechanisms
    assert augmented.pack_id != pack.pack_id
    assert augmented.external_evidence[0].not_mechanism_evidence is True
    assert report.valid is True


def test_external_evidence_rejects_unparseable_publication_time() -> None:
    pack = build_evidence_pack(ResearchRequest(
        question="沐邦的公开招募最新推进到哪一步？",
        llm_mode="off",
    ))
    external = ExternalEvidenceInput(
        source_kind="official_court_or_administrator",
        source_mode="live_web_observation",
        subject_ref="603398",
        title="管理人公开招募说明",
        source_url="https://example.gov.cn/restructuring/603398",
        published_at="不确定",
        fetched_at="2026-07-15T00:00:00+00:00",
        coverage_note="仅补当前事实。",
        facts=[{"fact_id": "status", "text": "已发布招募说明。"}],
    )

    with pytest.raises(ValueError, match="published_at 非法"):
        augment_evidence_pack(pack, [external])
