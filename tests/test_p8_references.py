import json
import sqlite3

import pytest

from p8_references import (
    CurrentMarketInput,
    ScenarioReference,
    _scaled_number,
    build_distribution,
    current_market_input_digest,
    _market_values,
    scenario_weight,
    strategic_terms,
)


def _reference(symbol: str, board: str, value: float) -> ScenarioReference:
    return ScenarioReference(
        reference_id=f"P8REF-{'A' * 14}{symbol}",
        family="public_node_reference",
        symbol=symbol,
        available_as_of="2026-08-01",
        stage="plan_approved",
        stage_source="body_verified",
        delisting_risk_type="financial",
        board=board,
        regime_version="2024_exit_reform",
        old_equity_value=value,
        value_status="exact_old_equity",
        contamination_flags=[], source_ids=[f"source-{symbol}"],
        evidence_status="body_verified",
    )


def test_distribution_follows_frozen_drop_board_relaxation():
    refs = [
        _reference(f"00000{index}", "主板" if index < 4 else "创业板", float(index))
        for index in range(1, 10)
    ]
    result = build_distribution(
        refs, family="public_node_reference", as_of="2026-09-01",
        stage="plan_approved", risk_type="financial", board="主板",
        regime_version="2024_exit_reform",
    )
    assert result.status == "distribution"
    assert result.relaxation_path == ["exact", "drop_board"]
    assert result.n == 9
    assert result.company_n == 9

    leave_one_out = build_distribution(
        refs, family="public_node_reference", as_of="2026-09-01",
        stage="plan_approved", risk_type="financial", board="主板",
        regime_version="2024_exit_reform", exclude_symbol="000001",
    )
    assert leave_one_out.status == "distribution"
    assert leave_one_out.n == 8
    assert leave_one_out.company_n == 8


def test_scenario_weight_fails_closed_and_does_not_clamp():
    assert scenario_weight(current=None, failure=0, success=10) == (None, "input_unknown")
    assert scenario_weight(current=5, failure=10, success=5) == (None, "non_positive_scenario_spread")
    value, status = scenario_weight(current=15, failure=0, success=10)
    assert value == 1.5
    assert status == "outside_scenario_range"


def test_reference_module_does_not_import_activity_or_funnel():
    source = open("p8_references.py", encoding="utf-8").read()
    assert "import p8_activity" not in source
    assert "import p8_funnel" not in source


def test_current_market_input_excludes_activity_and_future_fields():
    assert set(CurrentMarketInput.model_fields) == {
        "symbol", "name", "trade_date", "close", "total_market_value",
        "source_snapshot_id", "source_digest",
    }
    forbidden = {
        "turnover_rate_f", "volume_ratio", "amount", "amplitude_pct",
        "shape_label", "future_return", "funnel_rank",
    }
    assert forbidden.isdisjoint(CurrentMarketInput.model_fields)


def test_p8a_economic_input_digest_ignores_mixed_snapshot_provenance():
    first = CurrentMarketInput(
        symbol="000001", name="ST测试", trade_date="2026-09-03",
        close=2.0, total_market_value=2_000_000_000.0,
        source_snapshot_id="snapshot-with-turnover-a", source_digest="a" * 64,
    )
    second = first.model_copy(update={
        "source_snapshot_id": "snapshot-with-turnover-b",
        "source_digest": "b" * 64,
    })
    assert current_market_input_digest([first]) == current_market_input_digest([second])


def test_market_value_fallback_reads_only_total_mv_and_keeps_c14_priority(tmp_path):
    factor = tmp_path / "factor.sqlite3"
    activity = tmp_path / "activity.sqlite3"
    with sqlite3.connect(factor) as connection:
        connection.executescript("""
            create table market_factor_snapshots(snapshot_id text,created_at text);
            create table market_cap_daily(snapshot_id text,symbol text,trade_date text,total_market_value real);
            insert into market_factor_snapshots values('M1','2023-01-01');
            insert into market_cap_daily values('M1','000001','2023-01-03',123.0);
        """)
    payloads = [
        {"symbol": "000001", "total_mv_10k_cny": 999.0, "turnover_rate_f": 88.0},
        {"symbol": "000002", "total_mv_10k_cny": 20.0, "turnover_rate_f": 77.0},
    ]
    with sqlite3.connect(activity) as connection:
        connection.executescript("""
            create table activity_snapshots(snapshot_id text,trade_date text,fetched_at text);
            create table market_activity_daily(snapshot_id text,payload_json text);
            insert into activity_snapshots values('A1','2023-01-03','2023-01-04');
        """)
        connection.executemany(
            "insert into market_activity_daily values('A1',?)",
            [(json.dumps(item),) for item in payloads],
        )
    values = _market_values(factor, market_activity_database=activity)
    assert values[("000001", "2023-01-03")] == 123.0
    assert values[("000002", "2023-01-03")] == 200_000.0


def test_transaction_fact_numbers_respect_chinese_share_units():
    assert _scaled_number("1.5", "亿股") == 150_000_000
    assert _scaled_number("2,500", "万股") == 25_000_000
    assert _scaled_number("1.20", "元/股") == 1.2


def test_strategic_terms_close_only_with_verified_same_document_inputs():
    extraction = {
        "evidence_status": "body_verified",
        "key_facts": [
            {"fact_type": "strategic_entry_price", "value": "1.20", "unit": "元/股", "evidence_quote": "每股1.20元"},
            {"fact_type": "transferred_share_count", "value": "2,000", "unit": "万股", "evidence_quote": "受让2000万股"},
            {"fact_type": "post_restructuring_total_share_count", "value": "1.5", "unit": "亿股", "evidence_quote": "总股本1.5亿股"},
            {"fact_type": "old_shareholder_retained_share_count", "value": "1.1", "unit": "亿股", "evidence_quote": "原股东保留1.1亿股"},
            {"fact_type": "share_transfer_ratio", "value": "20", "unit": "%", "evidence_quote": "让渡20%"},
            {"fact_type": "cash_investment", "value": "3", "unit": "亿元", "evidence_quote": "投入3亿元"},
        ],
    }
    terms = strategic_terms(extraction, event_evidence_status="body_verified")
    assert terms.arithmetic_closed is True
    assert terms.transaction_consideration == 24_000_000
    assert terms.headline_post_money == 180_000_000
    assert terms.old_shareholder_retained_ratio == pytest.approx(110_000_000 / 150_000_000)
    assert terms.contamination_flags == ["package_contaminated"]

    unverified = strategic_terms(extraction, event_evidence_status="title_derived")
    assert unverified.arithmetic_closed is False
    assert "old_shareholder_equity_not_exact" in unverified.contamination_flags


def test_strategic_terms_reject_conflicting_numeric_facts():
    extraction = {
        "evidence_status": "body_verified",
        "key_facts": [
            {"fact_type": "strategic_entry_price", "value": "1.20", "unit": "元/股", "evidence_quote": "价格一"},
            {"fact_type": "strategic_entry_price", "value": "1.30", "unit": "元/股", "evidence_quote": "价格二"},
            {"fact_type": "transferred_share_count", "value": "2000", "unit": "万股", "evidence_quote": "受让"},
            {"fact_type": "post_restructuring_total_share_count", "value": "1.5", "unit": "亿股", "evidence_quote": "总股本"},
            {"fact_type": "old_shareholder_retained_share_count", "value": "1.1", "unit": "亿股", "evidence_quote": "保留"},
            {"fact_type": "share_transfer_ratio", "value": "20", "unit": "%", "evidence_quote": "让渡"},
        ],
    }
    assert strategic_terms(extraction, event_evidence_status="body_verified").arithmetic_closed is False
