import pytest

from p8_portfolio import _compound


def test_compound_uses_concurrent_daily_returns_not_arithmetic_sum() -> None:
    assert _compound([]) is None
    assert _compound([0.10, -0.10]) == pytest.approx(-0.01)
