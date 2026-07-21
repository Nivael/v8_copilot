from __future__ import annotations

import pytest

from evals.deterministic_router_v0 import route_question
from evals.run_route_eval import evaluate_routes
from evals.validate_w2_evals import QUESTION_SET, load_jsonl


def test_deterministic_router_matches_question_routing_set() -> None:
    result = evaluate_routes(load_jsonl(QUESTION_SET))

    assert result.failures == []
    assert result.passed == 30
    assert result.route_counts == {
        "answer_checklist": 3,
        "answer_evidence": 2,
        "answer_methodology": 1,
        "answer_query": 9,
        "clarify": 2,
        "data_debt": 5,
        "lens_gap": 2,
        "needs_review": 2,
        "refuse_or_rewrite": 4,
    }


def test_trading_advice_routes_to_boundary() -> None:
    prediction = route_question({
        "user_question": "这票目标价看到多少？",
        "object": {"kind": "stock", "ref": "603398"},
    })

    assert prediction.predicted_route == "refuse_or_rewrite"
    assert prediction.expected_view == "boundary"
    assert prediction.required_lens_behavior == "not_applicable"


def test_trading_boundary_precedes_missing_context() -> None:
    prediction = route_question({
        "user_question": "这票能买吗？",
        "object": {"kind": "unknown", "ref": "unknown"},
    })

    assert prediction.predicted_route == "refuse_or_rewrite"
    assert prediction.matched_rules == ["trading_advice_boundary"]


@pytest.mark.parametrize("question", [
    "现在能买沐邦吗？",
    "亚光现在可以买了吗？",
    "南都适合继续持有吗？",
    "603398 是否可以买？",
    "重整公告出来后要不要买？",
    "这只票卖掉合适吗？",
])
def test_trading_boundary_handles_split_natural_language(question: str) -> None:
    prediction = route_question({
        "user_question": question,
        "object": {"kind": "stock", "ref": "603398"},
    })

    assert prediction.predicted_route == "refuse_or_rewrite"


@pytest.mark.parametrize("question", [
    "沐邦接下来有哪些公开公告窗口？",
    "历史案例中投资人购买资产的公告怎么分类？",
])
def test_research_descriptions_are_not_action_requests(question: str) -> None:
    prediction = route_question({
        "user_question": question,
        "object": {"kind": "stock", "ref": "603398"},
    })

    assert prediction.predicted_route != "refuse_or_rewrite"


def test_compound_data_gaps_preserve_all_known_refs() -> None:
    prediction = route_question({
        "user_question": "股东人数按省份分层有什么变化？",
        "object": {"kind": "cohort", "ref": "st_universe"},
    })

    assert prediction.predicted_route == "data_debt"
    assert prediction.required_data_debt_refs == ["D-051A"]
    assert prediction.required_question_card_refs == [
        "QC-20260710-011",
        "QC-20260710-006",
    ]
    assert prediction.matched_rules == [
        "missing_province_mapping",
        "missing_shareholder_count_full_coverage",
    ]


def test_partial_event_query_preserves_shareholder_count_gap() -> None:
    prediction = route_question({
        "user_question": "某个节点前后公告、价格和股东人数发生了什么？",
        "object": {"kind": "stock_event", "ref": "603398:2024-11-18"},
    })

    assert prediction.predicted_route == "answer_query"
    assert "QC-20260710-006" in prediction.required_question_card_refs
    assert "missing_shareholder_count_full_coverage" in prediction.matched_rules


def test_known_context_predictive_question_routes_to_checklist_not_boundary() -> None:
    prediction = route_question({
        "user_question": "沐邦接下来可能的爆发点在哪里？",
        "object": {"kind": "stock", "ref": "603398"},
    })

    assert prediction.predicted_route == "answer_checklist"
    assert prediction.expected_view == "checklist"
    assert "QC-20260710-015" in prediction.required_question_card_refs


def test_missing_context_routes_to_clarify() -> None:
    prediction = route_question({
        "user_question": "那它呢？",
        "object": {"kind": "unknown", "ref": "pronoun"},
    })

    assert prediction.predicted_route == "clarify"
    assert prediction.required_lens_behavior == "not_applicable"
