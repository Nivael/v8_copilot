from __future__ import annotations

from api_contract import ResearchRequest
from announcement_body import AnnouncementBody
from api import orchestrate
from llm.providers import FakeLLMProvider
from llm.schemas import NarrativeDraft, ParsedQuestion
from llm_adapter import orchestrate_with_provider_result
from orchestrator_v1 import enrich_response_v1
from orchestrator_v2 import enrich_response_v2


def _fake_body(record, **_kwargs) -> AnnouncementBody:
    return AnnouncementBody(
        announcement_id=record.announcement_id,
        announcement_date=record.announcement_date,
        source_url=record.url or "https://static.cninfo.com.cn/finalpage/2026-07-08/1225415810.PDF",
        page_count=3,
        text=(
            "债权人浙江某公司以南都电源不能清偿到期债务为由，向法院申请对公司进行预重整及重整。"
            "截至公告披露日，法院尚未裁定受理申请。公司能否进入预重整或重整程序存在不确定性。"
        ),
    )


def test_latest_announcement_uses_body_evidence(monkeypatch) -> None:
    calls = []

    def offline_body(record, **kwargs):
        calls.append(kwargs)
        return _fake_body(record, **kwargs)

    monkeypatch.setattr("answer_engine.load_announcement_body", offline_body)
    response = orchestrate(ResearchRequest(
        question="南都最新的公告具体说了什么",
        llm_mode="off",
    ))

    assert response.answer_card is not None
    rows = response.answer_card["body_rows"]
    body = next(row for row in rows if row.get("记录类型") == "公告正文证据")
    assert body["公告编号"] == "1225415810"
    assert any("法院尚未裁定受理" in item for item in body["正文证据片段"])
    assert response.narrative is not None
    assert "债权人" in response.narrative.direct_answer.text
    assert calls and calls[0]["allow_network"] is False


def test_mubang_progress_separates_case_stage_from_history(monkeypatch) -> None:
    monkeypatch.setattr("answer_engine.load_announcement_body", _fake_body)
    response = orchestrate(ResearchRequest(
        question="沐邦的公开招募推进到哪一步了？下一个节点最可能是什么？",
        llm_mode="off",
    ))

    assert response.route.matched_rules[0] == "stock_restructuring_progress_query"
    assert response.answer_card is not None
    rows = response.answer_card["body_rows"]
    current = next(row for row in rows if row.get("记录类型") == "当前公开里程碑")
    assert current["主体范围"] == "上市公司本体"
    assert "预重整" in current["阶段判断"]
    assert "未找到公开招募记录" in current["公开招募记录"]
    historical = [row for row in rows if row.get("记录类型") == "同阶段历史后续"]
    assert historical
    stage_rows = [row for row in historical if row["后续口径"] == "下一个不同重整阶段"]
    assert stage_rows
    assert all(
        row["可观察后续总数"] + row["未观察到后续"] == row["起点事件总数"]
        for row in stage_rows
    )
    assert response.narrative is not None
    assert "右删失" in response.narrative.direct_answer.text
    assert str(stage_rows[0]["可观察后续总数"]) in response.narrative.direct_answer.text
    assert any(
        "下一个不同重整阶段" in step.title
        for step in response.narrative.reasoning_steps
    )


def test_two_stock_comparison_executes_instead_of_falling_back() -> None:
    response = orchestrate(ResearchRequest(
        question="沐邦和南都怎么比较",
        llm_mode="off",
    ))

    assert response.route.matched_rules == ["stock_comparison_query"]
    assert response.answer_card is not None
    assert response.answer_card["object_ref"] == "cohort:comparison:603398,300068"
    rows = response.answer_card["body_rows"]
    assert {row["股票"] for row in rows} == {"603398", "300068"}
    mubang = next(row for row in rows if row["股票"] == "603398")
    assert "2026-02-26" in mubang["最近上市公司本体重整里程碑"]
    assert "2026-06-17" not in mubang["最近上市公司本体重整里程碑"]
    assert "2026-06-17" not in mubang["各自最新上市公司本体重整里程碑"]
    assert "2026-06-17" in mubang["各自最新关联主体重整事项"]
    assert "孙公司" in mubang["各自最新关联主体重整事项"]
    assert response.narrative is not None
    assert len(response.narrative.reasoning_steps) >= 4
    assert any(
        step.title == "关联主体重整事项"
        for step in response.narrative.reasoning_steps
    )
    assert response.answer_card["as_of"] == "2026-07-08"


def test_generic_wentai_analysis_loads_multiple_dimensions() -> None:
    response = orchestrate(ResearchRequest(
        question="分析一下 ST 闻泰",
        llm_mode="off",
    ))

    assert response.interpretation.object.ref == "600745"
    assert response.answer_card is not None
    row_types = {row.get("记录类型") for row in response.answer_card["body_rows"]}
    assert {"状态区间", "近期官方公告", "近期分类节点", "近期价格窗口"} <= row_types
    assert response.narrative is not None
    assert len(response.narrative.reasoning_steps) >= 4
    assert any(
        "股东人数 pilot 没有该股票" in item.text
        for item in response.narrative.uncertainties
    )
    assert any(
        gap["gap_id"] == "shareholder_count_coverage"
        for gap in response.answer_card["lens_gap"]
    )
    boundary = next(
        row for row in response.answer_card["body_rows"]
        if row.get("记录类型") == "分析时间边界"
    )
    assert boundary["事件索引截至"] == "2026-05-25"
    assert boundary["事件覆盖ST后"] is False
    assert response.answer_card["as_of"] == "2026-06-28"


def test_stock_without_episode_does_not_inherit_global_episode_date() -> None:
    response = orchestrate(ResearchRequest(
        question="分析一下 000005",
        llm_mode="off",
    ))

    assert response.interpretation.object.ref == "000005"
    assert response.answer_card is not None
    rows = response.answer_card["body_rows"]
    assert not any(row.get("记录类型") == "近期分类节点" for row in rows)
    boundary = next(
        row for row in rows if row.get("记录类型") == "分析时间边界"
    )
    assert boundary["事件索引截至"] == ""
    assert boundary["事件覆盖ST后"] is False


def _llm_factory(response_model: type, payload: dict) -> dict:
    if response_model is ParsedQuestion:
        return {
            "normalized_question": payload["question"],
            "object_kind": "stock",
            "object_ref": "600745",
            "intent": "research_question",
            "time_range": {"start": "", "end": ""},
            "dimensions": ["announcement", "price"],
            "ambiguities": [],
            "candidate_topics": ["st_lifecycle"],
            "proposed_route": "answer_query",
            "compliant_rewrite": "",
        }
    if response_model is NarrativeDraft:
        first = payload["backing_catalog"][0]
        return {
            "claims": [],
            "narrative": {
                "direct_answer": {
                    "text": "当前材料应先按状态、公告、事件和价格四层阅读。",
                    "backing": [{"kind": first["kind"], "ref": first["ref"]}],
                },
                "reasoning_steps": [{
                    "title": "状态层",
                    "text": "先核对当前状态记录。",
                    "backing": [{"kind": first["kind"], "ref": first["ref"]}],
                }],
                "uncertainties": [],
                "watch_items": [],
            },
        }
    raise AssertionError(response_model)


def test_validated_llm_narrative_becomes_main_api_narrative() -> None:
    request = ResearchRequest(question="分析一下 ST 闻泰", llm_mode="auto")
    result = orchestrate_with_provider_result(
        request, FakeLLMProvider(response_factory=_llm_factory)
    )
    response_v1 = enrich_response_v1(request, result.response)
    response_v2 = enrich_response_v2(
        request, response_v1, narrative_override=result.narrative
    )

    assert result.narrative is not None
    assert response_v2.narrative is not None
    assert response_v2.narrative.direct_answer.text.startswith("当前材料应先")
    assert response_v2.llm_used is True
