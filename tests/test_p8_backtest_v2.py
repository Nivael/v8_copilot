from datetime import date, timedelta

from p8_backtest_v2 import (
    attach_outcomes,
    build_accumulation_scores,
    build_holder_scores,
    build_historical_funnel,
    leadingness_diagnostic,
    rank_scorecard,
)


def _feature(symbol: str, day: str, value: float, label: str = "quiet") -> dict:
    return {
        "feature_id": f"F-{symbol}-{day}",
        "symbol": symbol,
        "trade_date": day,
        "calculable": True,
        "cum_turnover_log_excess_20": value,
        "elevated_day_ratio_20": value,
        "excess_return_st_20": 0.01 * value,
        "range_compression_20": 1.0 - value * 0.01,
        "shape_label": label,
    }


def test_accumulation_score_is_same_day_order_invariant_and_uses_prior_history() -> None:
    start = date(2022, 1, 3)
    features = []
    stages = {}
    for index in range(12):
        symbol = f"{index + 1:06d}"
        day = (start + timedelta(days=index)).isoformat()
        features.append(_feature(symbol, day, float(index)))
        stages[(symbol, day)] = "st_distress_only"
    target_day = (start + timedelta(days=20)).isoformat()
    first = _feature("000101", target_day, 3.0)
    second = _feature("000102", target_day, 9.0)
    stages[("000101", target_day)] = "st_distress_only"
    stages[("000102", target_day)] = "st_distress_only"
    left = build_accumulation_scores([*features, first, second], stage_map=stages)
    right = build_accumulation_scores([*features, second, first], stage_map=stages)
    left_scores = {item["symbol"]: item["score"] for item in left}
    right_scores = {item["symbol"]: item["score"] for item in right}
    assert left_scores == right_scores
    assert left_scores["000102"] > left_scores["000101"]
    assert next(item for item in left if item["symbol"] == "000101")["history_observation_count"] == 12


def test_holder_score_uses_disclosed_decrease_and_strict_prior_history() -> None:
    start = date(2022, 1, 3)
    records = []
    stages = {}
    for index in range(12):
        symbol = f"{index + 1:06d}"
        day = (start + timedelta(days=index)).isoformat()
        records.append({
            "record_id": f"H-{symbol}", "symbol": symbol, "trade_date": day,
            "available_as_of": day, "holder_change_pct": -index / 100,
        })
        stages[(symbol, day)] = "st_distress_only"
    target_day = (start + timedelta(days=20)).isoformat()
    records.extend([
        {"record_id": "H-101", "symbol": "000101", "trade_date": target_day,
         "available_as_of": target_day, "holder_change_pct": -0.03},
        {"record_id": "H-102", "symbol": "000102", "trade_date": target_day,
         "available_as_of": target_day, "holder_change_pct": -0.09},
    ])
    stages[("000101", target_day)] = "st_distress_only"
    stages[("000102", target_day)] = "st_distress_only"
    result = build_holder_scores(records, stage_map=stages)
    by_symbol = {item["symbol"]: item for item in result}
    assert by_symbol["000102"]["score"] > by_symbol["000101"]["score"]
    assert by_symbol["000101"]["history_observation_count"] == 12


def test_historical_funnel_separates_same_day_event_reaction_from_persistent_lane() -> None:
    calendar = ["2023-01-02", "2023-01-03", "2023-01-04", "2023-01-05", "2023-01-06"]
    memberships = {day: {"000001", "000002"} for day in calendar}
    events = [{
        "event_id": "E1", "symbol": "000001", "available_as_of": "2023-01-06",
        "evidence_status": "deterministic_verified", "possible_successors": ["next"],
        "failure_successors": [],
    }]
    features = [
        _feature("000001", "2023-01-06", 4.0, "persistent_activity_price_stable"),
        _feature("000002", "2023-01-06", 5.0, "persistent_activity_price_stable"),
    ]
    scores = [
        {"symbol": "000001", "trade_date": "2023-01-06", "score": .8},
        {"symbol": "000002", "trade_date": "2023-01-06", "score": .9},
    ]
    stage_map = {(symbol, "2023-01-06"): "st_distress_only" for symbol in ("000001", "000002")}
    result = build_historical_funnel(
        calendar=calendar, memberships=memberships, events=events,
        features=features, scores=scores, stage_map=stage_map,
    )
    by_symbol = {item["symbol"]: item for item in result}
    assert by_symbol["000001"]["primary_lane"] == "event_frontier"
    assert by_symbol["000001"]["matched_lanes"] == ["event_frontier"]
    assert by_symbol["000002"]["primary_lane"] == "persistent_activity"


def test_historical_funnel_carries_latest_disclosed_holder_score() -> None:
    calendar = ["2023-01-02", "2023-01-03", "2023-01-04", "2023-01-05", "2023-01-06"]
    memberships = {day: {"000001"} for day in calendar}
    result = build_historical_funnel(
        calendar=calendar, memberships=memberships, events=[], features=[], scores=[],
        holder_scores=[{
            "record_id": "HS1", "source_holder_id": "H1", "symbol": "000001",
            "trade_date": "2023-01-03", "score": .9,
        }],
        stage_map={("000001", "2023-01-06"): "st_distress_only"},
    )
    assert result[0]["primary_lane"] == "chip_or_exploration"
    assert result[0]["holder_score"] == .9


def test_attach_outcomes_keeps_positive_and_negative_nodes_separate() -> None:
    start = date(2023, 1, 1)
    prices = {"000001": [((start + timedelta(days=i)).isoformat(), 10 + i) for i in range(130)]}
    benchmarks = {
        "st_equal_weight_v1": {day: 100 + index for index, (day, _value) in enumerate(prices["000001"])},
        "csi_2000": {},
    }
    score = {
        "symbol": "000001", "trade_date": prices["000001"][0][0],
        "test_year": 2023, "score": .9, "bucket": "high", "stratum_key": "s|H1",
    }
    events = [{
        "symbol": "000001", "available_as_of": prices["000001"][10][0],
        "evidence_status": "deterministic_verified", "not_hard_outcome": False,
        "process_direction": "advance", "old_equity_effect": "supportive",
    }]
    result = attach_outcomes([score], prices=prices, benchmarks=benchmarks, events=events)
    assert result[0]["h120_positive_hard_node"] is True
    assert result[0]["h120_negative_hard_node"] is False


def test_attach_outcomes_applies_delist_total_loss_on_market_horizon() -> None:
    start = date(2023, 1, 1)
    calendar = [(start + timedelta(days=i)).isoformat() for i in range(130)]
    prices = {"000001": [(day, 10.0) for day in calendar[:20]]}
    benchmarks = {
        "st_equal_weight_v1": {day: 100.0 for day in calendar},
        "csi_2000": {day: 100.0 for day in calendar},
    }
    result = attach_outcomes(
        [{
            "symbol": "000001", "trade_date": calendar[0], "test_year": 2023,
            "score": .9, "bucket": "high", "stratum_key": "s|H1",
        }],
        prices=prices, benchmarks=benchmarks, events=[], market_calendar=calendar,
        terminal_dates={"000001": calendar[30]},
    )
    assert result[0]["h120_observed"] is True
    assert result[0]["h120_delisted"] is True
    assert result[0]["h120_stock_qfq_return"] == -1.0
    assert result[0]["h120_last_observable_return"] == 0.0
    assert result[0]["h120_excess_return_st_last_observable"] == 0.0


def test_rank_scorecard_reports_frozen_secondary_and_risk_diagnostics() -> None:
    rows = []
    for index in range(120):
        bucket = "high" if index % 2 else "low"
        rows.append({
            "symbol": f"{index % 40 + 1:06d}", "trade_date": f"2023-{index % 12 + 1:02d}-15",
            "test_year": 2023, "score": float(index), "bucket": bucket,
            "stratum_key": "st_distress_only|H1", "h60_excess_return_st": .01,
            "h120_excess_return_st": .02, "h120_excess_return_csi2000": .03,
            "h120_positive_hard_node": False, "h120_negative_hard_node": False,
            "h120_delisted": bucket == "low" and index == 0,
        })
    card = rank_scorecard(rows)
    assert "cell_equal_high_minus_low_60d_excess_st" in card
    assert "cell_equal_high_minus_low_120d_excess_csi2000" in card
    assert card["delisted_120d"]["low_count"] == 1
    assert set(card["diagnostic_slices"]) == {
        "annual_report_season", "outside_annual_report_season",
        "2024_pre_rule_revision", "2024_post_revision_pre_mv_rule",
        "2024_market_cap_rule_effective",
    }


def test_leadingness_diagnostic_counts_recent_covered_announcements() -> None:
    calendar = [f"2023-01-{day:02d}" for day in range(1, 11)]
    scores = [
        {
            "symbol": "000001", "trade_date": "2023-01-08", "test_year": 2023,
            "bucket": "high", "shape_label": "persistent_activity_price_stable",
        },
        {
            "symbol": "000002", "trade_date": "2023-01-08", "test_year": 2023,
            "bucket": "high", "shape_label": "persistent_activity_price_down",
        },
    ]
    result = leadingness_diagnostic(
        scores,
        events=[{"symbol": "000001", "available_as_of": "2023-01-05"}],
        calendar=calendar,
    )
    assert result["overall"]["recent_covered_announcement_share"] == .5
    assert result["overall"]["no_covered_announcement_share"] == .5
