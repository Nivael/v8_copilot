import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api_contract import ResearchRequest
from api_contract_v2 import (
    API_CONTRACT_VERSION_V2,
    ResearchResponseV2,
    public_contract_schema_v2,
)
from api import orchestrate


ROOT = Path(__file__).resolve().parents[1]


def test_checklist_response_has_readable_backed_logic_chain() -> None:
    response = orchestrate(ResearchRequest(
        question="沐邦平台整理期接下来有哪些可验证窗口？",
        object={"kind": "stock", "ref": "603398"},
        llm_mode="off",
    ))

    assert response.contract_version == API_CONTRACT_VERSION_V2
    assert response.narrative is not None
    assert "不能确认" in response.narrative.direct_answer.text
    assert response.narrative.reasoning_steps[0].title == "先把预测问题改成验证问题"
    assert len(response.narrative.watch_items) == 5
    assert all(item.backing for item in response.narrative.watch_items)


def test_boundary_response_is_explicit_and_offers_safe_rewrite() -> None:
    response = orchestrate(ResearchRequest(
        question="现在能买沐邦吗？",
        object={"kind": "stock", "ref": "603398"},
        llm_mode="off",
    ))

    assert response.route.route == "refuse_or_rewrite"
    assert response.answer_card is None
    assert response.narrative is None
    assert response.boundary_rewrite is not None
    assert response.boundary_rewrite.rewritten_question == "603398 接下来该看哪些窗口？"
    assert "买卖" in response.boundary_rewrite.message


def test_narrative_rejects_missing_backing_reference() -> None:
    response = orchestrate(ResearchRequest(
        question="沐邦平台整理期接下来有哪些可验证窗口？",
        object={"kind": "stock", "ref": "603398"},
        llm_mode="off",
    )).model_dump(mode="json")
    response["narrative"]["direct_answer"]["backing"][0]["ref"] = "missing-row"

    with pytest.raises(ValidationError, match="narrative backing 无对应对象"):
        ResearchResponseV2.model_validate(response)


def test_timing_narrative_explains_all_three_definitions() -> None:
    response = orchestrate(ResearchRequest(
        question="公开招募后下一个公告节点通常多久？",
        object={"kind": "episode_type", "ref": "restructuring_investor_recruitment"},
        llm_mode="off",
    ))

    assert response.narrative is not None
    assert "4.0 天" in response.narrative.direct_answer.text
    assert "10 天" in response.narrative.direct_answer.text
    assert "14 天" in response.narrative.direct_answer.text
    assert [step.title for step in response.narrative.reasoning_steps] == [
        "下一个任意公告", "下一个已分类重整节点", "下一个不同阶段里程碑",
    ]


def test_evidence_narrative_keeps_sample_and_counterexample_chain() -> None:
    response = orchestrate(ResearchRequest(
        question="哪些月份有历史月份效应证据？",
        object={"kind": "lens_cluster", "ref": "calendar_regime"},
        llm_mode="off",
    ))

    assert response.narrative is not None
    assert [step.title for step in response.narrative.reasoning_steps] == [
        "样本范围", "历史结果摘要", "反例边界",
    ]
    assert "N=16215" in response.narrative.reasoning_steps[0].text
    assert "N=20462" in response.narrative.reasoning_steps[0].text


def test_committed_v2_schema_matches_models() -> None:
    path = ROOT / "contracts/v8_copilot_api_contract_v2/schema.json"
    assert json.loads(path.read_text(encoding="utf-8")) == public_contract_schema_v2()


def test_v2_contract_artifacts_have_no_machine_local_paths() -> None:
    contract_dir = ROOT / "contracts/v8_copilot_api_contract_v2"
    for path in contract_dir.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert "/Users/" not in text
            assert "/home/" not in text
