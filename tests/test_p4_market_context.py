from __future__ import annotations

from datetime import date, timedelta
import json
import sqlite3

import pytest

from api_contract import ResearchRequest
from core_router import interpret_request
from market_comparison import load_market_comparison
from orchestrator import orchestrate


@pytest.fixture
def aligned_market_inputs(tmp_path, monkeypatch):
    """Exercise the real comparison loader with a small, explicitly synthetic aligned input.

    The live universe pointer can move beyond the market manifest. That is a genuine
    production gap, not a reason to expect this ready-branch integration test to pass.
    """
    market, prices = tmp_path / "market.sqlite3", tmp_path / "prices.sqlite3"
    manifest, universe = tmp_path / "manifest.json", tmp_path / "universe.json"
    days = [(date(2026, 7, 1) + timedelta(days=offset)).isoformat() for offset in range(15)
            if (date(2026, 7, 1) + timedelta(days=offset)).weekday() < 5]
    with sqlite3.connect(market) as connection:
        connection.execute("create table benchmark_daily (benchmark_id text,trade_date text,close real,coverage_ratio real)")
        connection.executemany("insert into benchmark_daily values (?,?,?,?)", [
            (code, day, base + index * 10, .98 if code == "st_equal_weight_v1" else None)
            for index, day in enumerate(days)
            for code, base in (("st_equal_weight_v1", 1000), ("csi_2000", 2000), ("csi_all_share", 5000))
        ])
    with sqlite3.connect(prices) as connection:
        connection.execute("create table daily_prices (symbol text,trade_date text,adjust text,close real)")
        connection.executemany("insert into daily_prices values ('603398',?,'qfq',?)", [
            (day, 10 + index) for index, day in enumerate(days)
        ])
    manifest.write_text(json.dumps({"manifest_id": "MC-synthetic-test", "generated_at": "2026-07-16T00:00:00+00:00",
        "current_status": "ready", "current_required_benchmarks": ["st_equal_weight_v1", "csi_2000", "csi_all_share"],
        "pool_common_window": {"start": days[0], "end": days[-1]}}))
    universe.write_text(json.dumps({"snapshot_id": "SU-synthetic-test", "as_of": days[-1]}))

    def load(*, price_database, symbol=None, sessions=10):
        return load_market_comparison(price_database=prices, market_database=market,
            manifest_path=manifest, universe_current_path=universe, symbol=symbol, sessions=sessions)
    monkeypatch.setattr("answer_engine.load_market_comparison", load)
    return universe, days


def _market_rows(response):
    return [
        row for row in response.answer_card["body_rows"]
        if str(row.get("row_id") or "").startswith("market_comparison")
    ]


def test_market_relative_question_is_answerable_and_closes_d051c(aligned_market_inputs) -> None:
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
    assert rows[0]["ST等权收益"] == "10.00%"
    assert rows[0]["中证2000收益"].endswith("%")
    assert rows[0]["中证全指收益"].endswith("%")
    assert len(rows) == 12


def test_stock_move_answer_has_four_aligned_series_and_relative_differences(aligned_market_inputs) -> None:
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


def test_unaligned_universe_does_not_become_a_ready_answer(aligned_market_inputs):
    universe, days = aligned_market_inputs
    universe.write_text(json.dumps({"snapshot_id": "SU-synthetic-test", "as_of": days[-2]}))
    response = orchestrate(ResearchRequest(question="ST沐邦最近两周为什么跌了？", llm_mode="off"))
    rows = _market_rows(response)
    assert len(rows) == 1
    assert rows[0]["row_id"] == "market_comparison_gap"
    assert "as-of 与市场窗口终点不一致" in rows[0]["缺口"]
    assert "个股相对ST" not in rows[0]


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
