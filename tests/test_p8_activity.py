from datetime import date, timedelta

import pytest

from market_activity import MarketActivityFact, SOURCE
from p8_activity import (
    FROZEN_SHAPE_PROFILES,
    build_activity_features,
    choose_capacity_profile,
    classify_shape,
)


def _fact(day: str, turnover: float, close: float, *, amplitude: float = 2.0) -> MarketActivityFact:
    return MarketActivityFact(
        symbol="000001", ts_code="000001.SZ", trade_date=day,
        open=close, high=close * 1.01, low=close * .99, close=close,
        pre_close=close, amount=1000, amplitude_pct=amplitude,
        turnover_rate_f=turnover, suspension_status="trading",
        one_price_limit=False, terminal_phase_status="not_terminal",
        eligible_for_anomaly=True, source=SOURCE,
    )


def test_activity_features_use_lagged_history_and_are_reproducible():
    days = [(date(2025, 1, 1) + timedelta(days=index)).isoformat() for index in range(100)]
    facts = [_fact(day, 1.0 if index < 80 else 2.0, 10 + index * .01) for index, day in enumerate(days)]
    qfq = {("000001", day): 10 + index * .01 for index, day in enumerate(days)}
    benchmark = {
        (benchmark_id, day): 100 + index * .01
        for benchmark_id in ("st_equal_weight_v1", "csi_2000")
        for index, day in enumerate(days)
    }
    features = build_activity_features(
        facts, qfq_close_by_symbol_date=qfq,
        benchmark_close_by_id_date=benchmark,
    )
    assert len(features) == 100
    assert features[-1].calculable is True
    assert features[-1].cum_turnover_log_excess_20 is not None
    assert features[-1].cum_turnover_log_excess_20 > 0

    changed = list(facts)
    changed[-1] = _fact(days[-1], 100.0, 11)
    changed_features = build_activity_features(
        changed, qfq_close_by_symbol_date=qfq,
        benchmark_close_by_id_date=benchmark,
    )
    assert features[-2].model_dump() == changed_features[-2].model_dump()
    assert changed_features[-1].cum_turnover_log_excess_20 > features[-1].cum_turnover_log_excess_20


def test_shape_classification_is_descriptive_and_capacity_choice_uses_coverage():
    days = [(date(2025, 1, 1) + timedelta(days=index)).isoformat() for index in range(100)]
    facts = [_fact(day, 1.0 if index < 80 else 2.0, 10.0) for index, day in enumerate(days)]
    benchmark = {
        (benchmark_id, day): 100.0
        for benchmark_id in ("st_equal_weight_v1", "csi_2000")
        for day in days
    }
    features = build_activity_features(facts, benchmark_close_by_id_date=benchmark)
    label = classify_shape(features[-1], FROZEN_SHAPE_PROFILES[0])
    assert label.label == "persistent_activity_price_stable"
    assert "主力" not in "".join(label.reasons)

    capacity = {
        "broad": {"daily_median": 5, "daily_p90": 12, "company_count": 100, "candidate_count": 300},
        "base": {"daily_median": 3, "daily_p90": 8, "company_count": 80, "candidate_count": 200},
        "strict": {"daily_median": 1, "daily_p90": 5, "company_count": 50, "candidate_count": 100},
    }
    assert choose_capacity_profile(capacity) == "broad"


def test_single_day_jump_uses_single_day_relative_return_and_range_expansion():
    days = [(date(2025, 1, 1) + timedelta(days=index)).isoformat() for index in range(100)]
    facts = [_fact(day, 1.0, 10.0) for day in days[:-1]]
    facts.append(_fact(days[-1], 10.0, 11.0, amplitude=4.0))
    benchmark = {
        (benchmark_id, day): 100.0
        for benchmark_id in ("st_equal_weight_v1", "csi_2000")
        for day in days
    }
    feature = build_activity_features(facts, benchmark_close_by_id_date=benchmark)[-1]
    assert feature.single_day_excess_return_st == pytest.approx(0.1)
    assert feature.single_day_amplitude_ratio == pytest.approx(2.0)
    label = classify_shape(feature, FROZEN_SHAPE_PROFILES[0], single_day_strict=True)
    assert label.label == "single_day_activity_price_jump"

    persistent_and_jump = feature.model_copy(update={
        "cum_turnover_log_excess_20": 5.0,
        "elevated_day_ratio_20": 0.8,
        "excess_return_st_20": -0.2,
    })
    assert classify_shape(
        persistent_and_jump, FROZEN_SHAPE_PROFILES[0], single_day_strict=True,
    ).label == "single_day_activity_price_jump"
