import json
import sqlite3

import pytest

from p8_backfill_market_activity import _load_plan
from p8_backtest_v2_dry_plan import _date_coverage, _p8_source_digest, render_markdown
from p8_research import build_run


def test_date_capacity_is_outcome_blind_and_keeps_regime_sub_boundary() -> None:
    calendar = ["2024-04-30", "2024-10-30"]
    memberships = {day: {"000001", "000002"} for day in calendar}
    benchmarks = {
        "st_equal_weight_v1": set(calendar),
        "csi_2000": set(calendar),
    }
    qfq = {(symbol, day) for day in calendar for symbol in memberships[day]}
    activity = {
        day: {
            "snapshot_id": f"MAS-{index}",
            "membership_count": 2,
            "valid_turnover_rate_f_count": 2,
            "daily_row_count": 2,
            "daily_basic_row_count": 2,
            "limit_row_count": 2,
        }
        for index, day in enumerate(calendar)
    }
    rows, summary = _date_coverage(
        calendar=calendar, memberships=memberships, benchmarks=benchmarks,
        qfq=qfq, activity=activity,
    )
    assert summary["complete_input_date_count"] == 2
    assert rows[0]["regime_version"] == "2024_exit_reform"
    assert rows[0]["market_cap_rule_effective"] is False
    assert rows[1]["market_cap_rule_effective"] is True
    assert not any("return" in key or "outcome" in key for key in rows[0])


def test_markdown_states_that_results_were_not_read() -> None:
    plan = {
        "plan_id": "P8BT2DP-TEST",
        "git_provenance": {"commit": "abc123"},
        "date_coverage": {
            "complete_input_date_count": 1,
            "calendar_date_count": 10,
            "missing_activity_date_count": 9,
        },
        "request_budget": {
            "endpoint_requests": 36,
            "incomplete_or_missing_trade_dates": 9,
        },
        "historical_funnel_capacity": {"test_year_date_count": 0},
        "event_truth_inventory": {"verified_hard_event_count": 2},
        "human_decisions_required": [],
        "feature_capacity": {
            "family_capacity": {
                "p8c_accumulation": {
                    "observation_count": 10,
                    "company_count": 4,
                    "status": "capacity_gate_failed",
                }
            }
        },
        "hard_blockers": ["missing"],
        "recommended_next_step": "backfill",
    }
    text = render_markdown(plan)
    assert "没有读取收益、命中率或股票贡献" in text
    assert "capacity_gate_failed" in text


def test_repository_run_contract_accepts_all_v2_run_kinds() -> None:
    for run_kind in (
        "p8_backtest_v2_dry_plan", "p8_signal_rank_v2",
        "p8_historical_funnel_v2", "p8_walk_forward_basket_v2",
        "p8_backtest_v2_report",
    ):
        run = build_run(
            run_kind=run_kind, contract_version="test",
            start_date="2023-01-01", through="2023-12-31",
            source_run_ids=[], source_digests={},
            record_payloads={"test": []},
        )
        assert run.run_kind == run_kind


def test_p8_source_digest_ignores_dry_plan_self_writes(tmp_path) -> None:
    database = tmp_path / "p8.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "create table p8_runs (run_id text,run_kind text,content_digest text,created_at text)"
        )
        connection.execute(
            "insert into p8_runs values ('source','event_graph',?,'2026-01-01')", ("a" * 64,)
        )
    before = _p8_source_digest(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "insert into p8_runs values ('dry','p8_backtest_v2_dry_plan',?,'2026-01-02')", ("b" * 64,)
        )
    assert _p8_source_digest(database) == before


def test_backfill_rejects_non_outcome_blind_or_divergent_endpoint_plan(tmp_path) -> None:
    plan = {
        "contract_version": "v8_p8_backtest_dry_plan_v1",
        "outcomes_read": False,
        "returns_computed": False,
        "request_budget": {"incomplete_or_missing_trade_dates": 1},
        "endpoint_request_plan": {
            endpoint: {"dates": ["2023-01-03"]}
            for endpoint in ("daily", "daily_basic", "stk_limit", "suspend_d")
        },
    }
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    _payload, dates = _load_plan(path)
    assert dates == ["2023-01-03"]
    plan["outcomes_read"] = True
    path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(ValueError, match="读取过 outcome"):
        _load_plan(path)
