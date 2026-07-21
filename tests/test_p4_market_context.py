from __future__ import annotations

from api_contract import ResearchRequest
from core_router import interpret_request
from orchestrator import orchestrate


def _market_rows(response):
    return [
        row for row in response.answer_card["body_rows"]
        if str(row.get("row_id") or "").startswith("market_comparison")
    ]


def test_market_relative_question_is_answerable_and_closes_d051c() -> None:
    response = orchestrate(ResearchRequest(
        question="ST 相对大盘两周异动的分布是什么？",
        llm_mode="off",
    ))

    assert response.route.route == "answer_query"
    assert response.route.status == "answerable"
    assert "D-051C" not in response.route.data_debt_refs
    assert response.answer_card is not None
    assert "D-051C" not in response.answer_card["data_debt_refs"]
    rows = _market_rows(response)
    assert rows[0]["row_id"] == "market_comparison_summary"
    assert rows[0]["ST等权收益"].endswith("%")
    assert rows[0]["中证2000收益"].endswith("%")
    assert rows[0]["中证全指收益"].endswith("%")
    assert len(rows) == 12


def test_stock_move_answer_has_four_aligned_series_and_relative_differences() -> None:
    response = orchestrate(ResearchRequest(
        question="ST沐邦最近两周为什么跌了？",
        llm_mode="off",
    ))

    assert response.answer_card is not None
    summary, *points = _market_rows(response)
    assert summary["股票代码"] == "603398"
    assert summary["窗口起点"] < summary["窗口终点"]
    assert summary["个股相对ST"].endswith("个百分点")
    assert summary["个股相对中证2000"].endswith("个百分点")
    assert summary["个股相对全市场"].endswith("个百分点")
    assert len(points) == 11
    assert all(point["stock_normalized"] is not None for point in points)
    assert response.answer_card["source_freshness"]["market_context_as_of"] == (
        summary["窗口终点"]
    )
    assert response.answer_card["source_freshness"]["st_universe_as_of"] == (
        summary["窗口终点"]
    )
    assert any("market_context_manifest_v1.json" in item for item in (
        response.answer_card["provenance"]
    ))
    assert any("st_universe/current.json#SU-" in item for item in (
        response.answer_card["provenance"]
    ))


def test_market_wording_loads_price_dimension_once() -> None:
    interpretation = interpret_request(ResearchRequest(
        question="ST沐邦最近两周相对大盘跌了多少？",
        llm_mode="off",
    ))

    assert interpretation.dimensions.count("price") == 1
    assert interpretation.dimensions.count("market_relative") == 1


def test_market_relative_synonyms_also_request_price_context() -> None:
    for question in ("沐邦相对市场如何？", "沐邦和ST板块共振吗？"):
        interpretation = interpret_request(ResearchRequest(
            question=question,
            llm_mode="off",
        ))

        assert "market_relative" in interpretation.dimensions
        assert "price" in interpretation.dimensions
