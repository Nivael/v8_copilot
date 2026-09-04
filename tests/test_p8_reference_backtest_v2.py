from p8_reference_backtest_v2 import _interval_score, build_reference_observations, scorecard


def _reference(symbol: str, day: str, value: float, stage: str = "plan_approved") -> dict:
    return {
        "reference_id": f"P8REF-{'A' * 14}{symbol}",
        "family": "public_node_reference", "symbol": symbol,
        "available_as_of": day, "stage": stage, "stage_source": "body_verified",
        "delisting_risk_type": "financial", "board": "主板",
        "regime_version": "2020_exit_reform", "total_market_value": value,
        "old_equity_value": None, "value_status": "total_mv_fact_only",
        "contamination_flags": [], "source_ids": [symbol],
        "evidence_status": "body_verified", "not_a_fair_value_claim": True,
    }


def test_interval_score_penalizes_misses() -> None:
    assert _interval_score(5, 4, 6) == 2
    assert _interval_score(2, 4, 6) == 10


def test_reference_walk_forward_never_uses_test_year_as_training() -> None:
    records = [
        _reference(f"{index:06d}", "2022-06-01", float(index + 10))
        for index in range(1, 10)
    ]
    records.append(_reference("000101", "2023-06-01", 15.0))
    records.append(_reference("000102", "2023-07-01", 10_000.0))
    observations = build_reference_observations(records)
    assert len(observations) == 2
    assert all(item["reference_n"] == 9 for item in observations)


def test_reference_scorecard_fails_closed_below_global_gate() -> None:
    card = scorecard([{
        "symbol": "000001", "test_year": 2023,
        "interval_score_difference": -1.0,
        "normalized_interval_score_difference": -0.1,
        "median_absolute_percentage_error": .1, "stratified_covered": True,
    }], family="public_node_reference")
    assert card["status"] == "unavailable"
