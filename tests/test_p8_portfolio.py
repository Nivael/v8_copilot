import pytest

from p8_portfolio import _compound, _compound_benchmark_intervals


def test_compound_uses_concurrent_daily_returns_not_arithmetic_sum() -> None:
    assert _compound([]) is None
    assert _compound([0.10, -0.10]) == pytest.approx(-0.01)


def test_benchmark_uses_exact_portfolio_intervals() -> None:
    series = {"2026-01-01": 100.0, "2026-01-02": 110.0, "2026-01-05": 99.0}
    assert _compound_benchmark_intervals(
        series,
        [("2026-01-01", "2026-01-02"), ("2026-01-02", "2026-01-05")],
    ) == pytest.approx(-0.01)
    assert _compound_benchmark_intervals(
        series,
        [("2026-01-01", "2026-01-03")],
    ) is None
