from p8_backtest import _event_outcomes, _next_outcome_counts


def test_outcomes_remain_direction_separated() -> None:
    calendar = [f"2026-01-{day:02d}" for day in range(1, 11)]
    outcomes = {
        "000001": [
            {"calendar_index": 3, "process_direction": "advance", "old_equity_effect": "mixed"},
            {"calendar_index": 5, "process_direction": "rollback", "old_equity_effect": "adverse"},
        ]
    }
    result = _next_outcome_counts(
        symbol="000001", day="2026-01-01", horizon=6,
        calendar=calendar, outcomes=outcomes,
    )
    assert result == {
        "process_advance": 1,
        "old_equity_mixed_or_unknown": 1,
        "process_rollback": 1,
        "old_equity_adverse": 1,
        "verified_hard_outcome_any": 1,
    }


def test_no_verified_hard_outcome_is_explicit() -> None:
    calendar = [f"2026-01-{day:02d}" for day in range(1, 11)]
    result = _next_outcome_counts(
        symbol="000001", day="2026-01-01", horizon=6,
        calendar=calendar, outcomes={},
    )
    assert result == {"no_verified_hard_outcome": 1}


def test_only_verified_hard_events_enter_outcome_ledger() -> None:
    calendar = ["2026-01-01", "2026-01-02", "2026-01-05"]
    events = [
        {
            "event_id": "precursor", "symbol": "000001", "available_as_of": "2026-01-02",
            "evidence_status": "deterministic_verified", "not_hard_outcome": True,
        },
        {
            "event_id": "hard", "symbol": "000001", "available_as_of": "2026-01-05",
            "evidence_status": "deterministic_verified", "not_hard_outcome": False,
        },
        {
            "event_id": "title", "symbol": "000001", "available_as_of": "2026-01-05",
            "evidence_status": "title_derived", "not_hard_outcome": False,
        },
    ]
    assert [item["event_id"] for item in _event_outcomes(events, calendar)["000001"]] == ["hard"]
