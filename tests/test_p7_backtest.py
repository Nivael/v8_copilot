from p7_anomalies import ActivityAnomaly
from p7_announcements import IssuerTransition
from p7_backtest import (
    _announcement_release_status,
    _calendar_index,
    _outcome,
    _threshold_episodes,
    derive_anchors,
    deviation_level,
)


def _anomaly(
    day: str, *, symbol: str = "000001", percentile: float = 99.0,
    robust_z: float = 5.0, calculable: bool = True,
) -> ActivityAnomaly:
    return ActivityAnomaly(
        anomaly_id=f"P7AD-{(symbol + day.replace('-', '') + '0' * 20)[:20]}",
        symbol=symbol,
        trade_date=day,
        history_count=120,
        turnover_rate_f=10.0,
        turnover_median_120=2.0,
        turnover_mad_120=1.0,
        turnover_percentile_120=percentile,
        turnover_robust_z_120=robust_z,
        calculable=calculable,
        narrative="test",
    )


def test_anchors_are_selected_mechanically_without_signal_counts() -> None:
    calendar = [f"2025-01-{day:02d}" for day in range(1, 32)] + [
        f"2026-01-{day:02d}" for day in range(1, 32)
    ]
    anchors = derive_anchors(calendar, "2026-01-31")
    assert anchors["past_week"] == "2026-01-26"
    assert anchors["past_month"] == "2026-01-10"
    assert anchors["past_year"] == "2025-01-31"


def test_deviation_level_preserves_nested_frozen_thresholds() -> None:
    assert deviation_level(_anomaly("2026-01-01", percentile=89.9, robust_z=9)) == 0
    assert deviation_level(_anomaly("2026-01-01", percentile=90, robust_z=2)) == 1
    assert deviation_level(_anomaly("2026-01-01", percentile=95, robust_z=3)) == 2
    assert deviation_level(_anomaly("2026-01-01", percentile=97.5, robust_z=4)) == 3
    assert deviation_level(_anomaly("2026-01-01", percentile=99, robust_z=5)) == 4
    assert deviation_level(_anomaly("2026-01-01", calculable=False)) is None


def test_threshold_episode_uses_first_hit_and_five_eligible_observation_gap() -> None:
    rows = [
        _anomaly(f"2026-01-{day:02d}", percentile=(99 if day in {1, 3, 9} else 50), robust_z=5)
        for day in range(1, 10)
    ]
    starts = _threshold_episodes(rows, minimum_level=3, merge_gap=5)
    assert [item.trade_date for item in starts] == ["2026-01-01", "2026-01-09"]


def test_future_transition_is_only_an_outcome_and_incomplete_horizon_is_censored() -> None:
    calendar = [f"2026-01-{day:02d}" for day in range(1, 11)]
    index = {day: number for number, day in enumerate(calendar)}
    transition = IssuerTransition(
        transition_id="P7TR-1234567890ABCDEFABCD",
        symbol="000001",
        dimension="restructuring",
        from_state="unknown",
        to_state="plan_approved",
        event_type="restructuring_plan_approved",
        announced_at="2026-01-04",
        effective_at="2026-01-04",
        available_as_of="2026-01-04",
        bundle_id="P7AB-1234567890ABCDEFABCD",
        source_refs=["official_announcement:A1"],
        evidence_status="verified",
    )
    observed = _outcome(
        symbol="000001", start_date="2026-01-01", horizon=5,
        transitions={"000001": [transition]}, index=index,
    )
    censored = _outcome(
        symbol="000001", start_date="2026-01-08", horizon=5,
        transitions={"000001": [transition]}, index=index,
    )
    assert observed[0] is True and observed[2] == 3
    assert censored == (None, None, None)


def test_non_trading_announcement_date_maps_to_next_trading_day() -> None:
    calendar = ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"]
    index = _calendar_index(calendar, event_dates=["2026-01-03"])
    assert index["2026-01-03"] == index["2026-01-05"] == 1


def test_tiny_priority_edge_is_not_promoted_when_intervals_overlap() -> None:
    priority = {
        "observed_by_horizon": {"20": 384},
        "hard_node_rate_by_horizon": {"20": 0.0599},
        "wilson_95_horizon_20": [0.0402, 0.0883],
    }
    routine = {
        "observed_by_horizon": {"20": 1234},
        "hard_node_rate_by_horizon": {"20": 0.0583},
        "wilson_95_horizon_20": [0.0466, 0.0728],
    }
    assert (
        _announcement_release_status(priority, routine)
        == "not_predictively_separated_out_of_sample"
    )


def test_announcement_candidate_requires_separated_intervals() -> None:
    priority = {
        "observed_by_horizon": {"20": 100},
        "hard_node_rate_by_horizon": {"20": 0.20},
        "wilson_95_horizon_20": [0.14, 0.29],
    }
    routine = {
        "observed_by_horizon": {"20": 500},
        "hard_node_rate_by_horizon": {"20": 0.05},
        "wilson_95_horizon_20": [0.03, 0.07],
    }
    assert (
        _announcement_release_status(priority, routine)
        == "retrospective_research_value_candidate_only"
    )
