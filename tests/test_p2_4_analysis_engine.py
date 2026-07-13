from __future__ import annotations

from api_contract import ResearchRequest
from announcement_body import AnnouncementBody
from api import orchestrate
from llm.composer import _strip_reasoning_ordinal
from llm.providers import FakeLLMProvider
from llm.schemas import NarrativeDraft, ParsedQuestion
from llm_adapter import orchestrate_with_provider_result
from narrative_builder import _comparison_narrative
from orchestrator_v1 import enrich_response_v1
from orchestrator_v2 import enrich_response_v2


def _fake_body(record, **_kwargs) -> AnnouncementBody:
    return AnnouncementBody(
        announcement_id=record.announcement_id,
        announcement_date=record.announcement_date,
        source_url=record.url or "https://static.cninfo.com.cn/finalpage/2026-07-08/1225415810.PDF",
        page_count=3,
        text=(
            "证券代码：300068 证券简称：ST 南都 公告编号：2026-068。"
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
    assert body["巨潮公告ID"] == "1225415810"
    assert body["公告编号"] == "2026-068"
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
    assert current["公开招募证据口径"] == "仅核查公司正式公告清单"
    assert "破产重整信息平台" in current["未覆盖渠道"]
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
    assert "不能据此判断实际公开招募是否已经开始" in response.narrative.direct_answer.text
    assert any(
        gap["gap_id"] == "restructuring_recruitment_channel_coverage"
        for gap in response.answer_card["lens_gap"]
    )
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
    assert len(response.narrative.reasoning_steps) == 3
    assert "公开程序维度" in response.narrative.direct_answer.text
    assert "公开节点" in response.narrative.direct_answer.text
    assert "更深入" in response.narrative.direct_answer.text
    assert "不能据此推断重整成功率或投资价值" in response.narrative.direct_answer.text
    assert "最新收盘" not in response.narrative.direct_answer.text
    assert [step.title for step in response.narrative.reasoning_steps] == [
        "先看最实质的程序差异",
        "再分清时间与主体口径",
        "其他指标只作背景",
    ]
    assert response.answer_card["as_of"] == "2026-07-08"


def test_comparison_judgment_uses_row_values_instead_of_seed_symbols() -> None:
    rows = [
        {
            "row_id": "comparison_AAA111",
            "记录类型": "股票并列比较",
            "股票": "AAA111",
            "当前ST状态": "ST甲",
            "共同公告截止日": "2030-01-31",
            "各自最新上市公司本体重整里程碑": "2030-01-20《申请公告》；阶段标签：债权人已提出预重整或重整申请",
            "各自最新关联主体重整事项": "当前正式公告清单未找到关联主体重整事项",
            "近20日变化": "-2.0%",
        },
        {
            "row_id": "comparison_BBB222",
            "记录类型": "股票并列比较",
            "股票": "BBB222",
            "当前ST状态": "*ST乙",
            "共同公告截止日": "2030-01-31",
            "各自最新上市公司本体重整里程碑": "2030-01-25《预重整进展》；阶段标签：预重整工作推进中",
            "各自最新关联主体重整事项": "关联主体（子公司）：2030-01-30《子公司重整》",
            "近20日变化": "1.0%",
        },
    ]
    narrative = _comparison_narrative(
        {"body_rows": rows, "lens_invocations": []}, []
    )

    assert "乙的公开节点比甲更深入" in narrative.direct_answer.text
    assert "603398" not in narrative.direct_answer.text
    assert len(narrative.reasoning_steps) == 3


def test_comparison_narrative_follows_explicit_density_focus() -> None:
    response = orchestrate(ResearchRequest(
        question="比较ST亚光和ST南都最近一个月的公告密度。",
        llm_mode="off",
    ))

    assert response.narrative is not None
    assert "近30日公告密度" in response.narrative.direct_answer.text
    assert "300068在该窗口披露更频繁" in response.narrative.direct_answer.text
    assert "重整进度、风险高低或整体优劣" in response.narrative.direct_answer.text
    assert [step.title for step in response.narrative.reasoning_steps] == [
        "先统一比较窗口", "再解释数量差异",
    ]


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
                    "title": "1. 状态层",
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
    assert response_v2.narrative.reasoning_steps[0].title == "状态层"
    assert response_v2.llm_used is True


def _non_directional_comparison_factory(response_model: type, payload: dict) -> dict:
    if response_model is ParsedQuestion:
        return {
            "normalized_question": payload["question"],
            "object_kind": "cohort",
            "object_ref": "603398,300068",
            "intent": "research_question",
            "time_range": {"start": "", "end": ""},
            "dimensions": ["restructuring"],
            "ambiguities": [],
            "candidate_topics": ["restructuring"],
            "proposed_route": "answer_query",
            "compliant_rewrite": "",
        }
    if response_model is NarrativeDraft:
        rows = [
            item for item in payload["backing_catalog"]
            if item["kind"] == "query_row" and "股票并列比较" in item["summary"]
        ]
        return {
            "claims": [],
            "narrative": {
                "direct_answer": {
                    "text": "两家公司处于不同公开阶段，但不能据此判断整体优劣。",
                    "backing": [
                        {"kind": item["kind"], "ref": item["ref"]} for item in rows
                    ],
                },
                "reasoning_steps": [],
                "uncertainties": [],
                "watch_items": [],
            },
        }
    raise AssertionError(response_model)


def test_llm_comparison_cannot_replace_directional_judgment_with_difference() -> None:
    request = ResearchRequest(question="沐邦和南都怎么比较？", llm_mode="auto")
    result = orchestrate_with_provider_result(
        request, FakeLLMProvider(response_factory=_non_directional_comparison_factory)
    )

    assert result.narrative is not None
    assert result.response.llm_used is True
    assert result.narrative.direct_answer.text.startswith(
        "在上市公司本体的公开程序维度，沐邦的公开节点比南都更深入。"
    )
    assert "不能据此判断整体优劣" in result.narrative.direct_answer.text


def test_llm_comparison_retries_when_direction_is_reversed() -> None:
    narrative_calls = 0

    def factory(response_model: type, payload: dict) -> dict:
        nonlocal narrative_calls
        if response_model is ParsedQuestion:
            return _non_directional_comparison_factory(response_model, payload)
        if response_model is NarrativeDraft:
            narrative_calls += 1
            rows = [
                item for item in payload["backing_catalog"]
                if item["kind"] == "query_row" and "股票并列比较" in item["summary"]
            ]
            if narrative_calls == 1:
                text = "南都当前公开的上市公司本体节点更进一步。"
            else:
                assert "direction_correction" in payload
                text = "沐邦的公开节点比南都更深入，但不能据此判断整体优劣。"
            return {
                "claims": [],
                "narrative": {
                    "direct_answer": {
                        "text": text,
                        "backing": [
                            {"kind": item["kind"], "ref": item["ref"]}
                            for item in rows
                        ],
                    },
                    "reasoning_steps": [],
                    "uncertainties": [],
                    "watch_items": [],
                },
            }
        raise AssertionError(response_model)

    provider = FakeLLMProvider(response_factory=factory)
    result = orchestrate_with_provider_result(
        ResearchRequest(question="沐邦和南都怎么比较？", llm_mode="auto"),
        provider,
    )

    assert narrative_calls == 2
    assert result.narrative is not None
    assert result.response.llm_used is True
    assert "沐邦的公开节点比南都更深入" in result.narrative.direct_answer.text
    assert "南都当前公开的上市公司本体节点更进一步" not in (
        result.narrative.direct_answer.text
    )


def test_llm_comparison_falls_back_after_repeated_direction_reversal() -> None:
    def factory(response_model: type, payload: dict) -> dict:
        if response_model is ParsedQuestion:
            return _non_directional_comparison_factory(response_model, payload)
        if response_model is NarrativeDraft:
            rows = [
                item for item in payload["backing_catalog"]
                if item["kind"] == "query_row" and "股票并列比较" in item["summary"]
            ]
            return {
                "claims": [],
                "narrative": {
                    "direct_answer": {
                        "text": "南都当前公开的上市公司本体节点更进一步。",
                        "backing": [
                            {"kind": item["kind"], "ref": item["ref"]}
                            for item in rows
                        ],
                    },
                    "reasoning_steps": [],
                    "uncertainties": [],
                    "watch_items": [],
                },
            }
        raise AssertionError(response_model)

    result = orchestrate_with_provider_result(
        ResearchRequest(question="沐邦和南都怎么比较？", llm_mode="auto"),
        FakeLLMProvider(response_factory=factory),
    )

    assert result.narrative is None
    assert result.response.llm_used is False
    assert any(
        "LLM 分析叙述不可用" in reason
        for reason in result.response.degraded_reasons
    )


def _overbroad_absence_factory(response_model: type, payload: dict) -> dict:
    if response_model is ParsedQuestion:
        return {
            "normalized_question": payload["question"],
            "object_kind": "stock",
            "object_ref": "603398",
            "intent": "research_question",
            "time_range": {"start": "", "end": ""},
            "dimensions": ["restructuring"],
            "ambiguities": [],
            "candidate_topics": ["restructuring"],
            "proposed_route": "answer_query",
            "compliant_rewrite": "",
        }
    if response_model is NarrativeDraft:
        current = next(
            item for item in payload["backing_catalog"]
            if "公开招募证据口径" in item["summary"]
        )
        return {
            "claims": [],
            "narrative": {
                "direct_answer": {
                    "text": "公开招募尚未推进到已公开招募这一步。",
                    "backing": [{"kind": current["kind"], "ref": current["ref"]}],
                },
                "reasoning_steps": [],
                "uncertainties": [],
                "watch_items": [],
            },
        }
    raise AssertionError(response_model)


def _scoped_restructuring_factory(response_model: type, payload: dict) -> dict:
    if response_model is ParsedQuestion:
        return _overbroad_absence_factory(response_model, payload)
    if response_model is NarrativeDraft:
        current = next(
            item for item in payload["backing_catalog"]
            if "公开招募证据口径" in item["summary"]
        )
        stage = next(
            item for item in payload["backing_catalog"]
            if "可观察后续总数" in item["summary"]
            and "未观察到后续" in item["summary"]
        )
        return {
            "claims": [],
            "narrative": {
                "direct_answer": {
                    "text": "公司正式公告清单未找到公开招募记录，其他渠道未覆盖。",
                    "backing": [{"kind": current["kind"], "ref": current["ref"]}],
                },
                "reasoning_steps": [],
                "uncertainties": [{
                    "text": (
                        "历史阶段转换统计的起点总数为98，可观察后续为64，"
                        "未观察到后续为34，阶段类别比例以64个样本为分母。"
                    ),
                    "backing": [{"kind": stage["kind"], "ref": stage["ref"]}],
                }],
                "watch_items": [],
            },
        }
    raise AssertionError(response_model)


def test_llm_cannot_expand_announcement_absence_to_real_world_absence() -> None:
    request = ResearchRequest(
        question="沐邦的公开招募推进到哪一步了？下一个节点可能是什么？",
        llm_mode="auto",
    )
    result = orchestrate_with_provider_result(
        request, FakeLLMProvider(response_factory=_overbroad_absence_factory)
    )

    assert result.narrative is None
    assert result.response.llm_used is False
    assert any("LLM 分析叙述不可用" in reason for reason in result.response.degraded_reasons)


def test_llm_restructuring_narrative_always_exposes_censoring_denominator() -> None:
    request = ResearchRequest(
        question="沐邦的公开招募推进到哪一步了？下一个节点可能是什么？",
        llm_mode="auto",
    )
    result = orchestrate_with_provider_result(
        request, FakeLLMProvider(response_factory=_scoped_restructuring_factory)
    )

    assert result.narrative is not None
    censoring = next(
        item for item in result.narrative.uncertainties if "右删失" in item.text
    )
    assert "episode case 去重" in censoring.text
    assert "98 个起点" in censoring.text
    assert "64 个观察到" in censoring.text
    assert "34 个" in censoring.text
    assert "可观察到后续的 case 为分母" in censoring.text
    assert sum(
        all(value in item.text for value in ("98", "64", "34"))
        for item in result.narrative.uncertainties
    ) == 1


def test_reasoning_step_text_does_not_keep_llm_ordinal_prefix() -> None:
    assert _strip_reasoning_ordinal("第二，风险线索需要分层阅读。") == (
        "风险线索需要分层阅读。"
    )
