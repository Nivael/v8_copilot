from datetime import date, timedelta

from p8_backtest_v2 import (
    attach_outcomes,
    build_accumulation_scores,
    build_historical_funnel,
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
