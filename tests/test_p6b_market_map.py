from __future__ import annotations

from market_factors import MarketCapPoint, MarketFactorRepository
from p6b_market_map import same_day_size_position


DAY = "2024-04-29"


def _point(symbol: str, market_cap: float | None) -> MarketCapPoint:
    return MarketCapPoint(
        symbol=symbol,
        trade_date=DAY,
        total_market_value=market_cap,
    )


def test_same_day_position_uses_average_rank_for_ties(tmp_path) -> None:
    database = tmp_path / "factors.sqlite3"
    MarketFactorRepository(database).store_snapshot(
        trade_date=DAY,
        membership_symbols=["000001", "000002", "000003", "000004"],
        points=[
            _point("000001", 10),
            _point("000002", 20),
            _point("000003", 20),
            _point("000004", 40),
        ],
    )

    result = same_day_size_position(
        database=database,
        symbol="000002",
        trade_date=DAY,
        minimum_cohort_size=4,
    )

    assert result.status == "ready"
    assert result.average_rank == 2.5
    assert result.percentile == 0.5
    assert result.total_market_value_rmb == 20
    assert "低尾不等于便宜" in result.warning


def test_same_day_position_fails_closed_below_coverage_gate(tmp_path) -> None:
    database = tmp_path / "factors.sqlite3"
    MarketFactorRepository(database).store_snapshot(
        trade_date=DAY,
        membership_symbols=["000001", "000002", "000003", "000004"],
        points=[
            _point("000001", 10),
            _point("000002", 20),
            _point("000003", 30),
        ],
    )

    result = same_day_size_position(
        database=database,
        symbol="000001",
        trade_date=DAY,
        minimum_cohort_size=3,
    )

    assert result.status == "unavailable"
    assert result.gap_code == "coverage_below_gate"
    assert result.percentile is None


def test_same_day_position_requires_target_market_cap(tmp_path) -> None:
    database = tmp_path / "factors.sqlite3"
    MarketFactorRepository(database).store_snapshot(
        trade_date=DAY,
        membership_symbols=["000001", "000002", "000003", "000004"],
        points=[
            _point("000001", 10),
            _point("000002", 20),
            _point("000003", 30),
            _point("000004", None),
        ],
    )

    result = same_day_size_position(
        database=database,
        symbol="000004",
        trade_date=DAY,
        coverage_threshold=0.75,
        minimum_cohort_size=3,
    )

    assert result.status == "unavailable"
    assert result.gap_code == "target_market_cap_unavailable"


def test_same_day_position_requires_exact_snapshot(tmp_path) -> None:
    result = same_day_size_position(
        database=tmp_path / "missing.sqlite3",
        symbol="000001",
        trade_date=DAY,
        minimum_cohort_size=1,
    )

    assert result.status == "unavailable"
    assert result.gap_code == "missing_snapshot"
    assert not (tmp_path / "missing.sqlite3").exists()
