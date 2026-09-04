from p8_backtest import _next_outcome_counts


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
    }
