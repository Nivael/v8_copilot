from __future__ import annotations

import sqlite3

from market_factors import MarketCapPoint, MarketFactorRepository
from p6b_market_map import (
    fixed_twelve_month_size_change,
    last_valid_size_position,
    same_day_size_position,
)


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


def _market_context(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            create table benchmark_daily (
                benchmark_id text, trade_date text, close real
            );
            create table st_membership_daily (
                trade_date text, symbol text
            );
            insert into benchmark_daily values
                ('csi_all_share','2023-01-03',100),
                ('csi_all_share','2024-01-03',110),
                ('csi_all_share','2024-01-04',111);
            insert into st_membership_daily values
                ('2023-01-03','000001'),
                ('2023-01-03','000002'),
                ('2023-01-03','000003'),
                ('2023-01-03','000004'),
                ('2024-01-03','000001'),
                ('2024-01-03','000002'),
                ('2024-01-03','000003'),
                ('2024-01-03','000005');
        """)


def test_fixed_twelve_month_change_shows_turnover_and_composition_noise(
    tmp_path,
) -> None:
    factors = tmp_path / "factors.sqlite3"
    repository = MarketFactorRepository(factors)
    repository.store_snapshot(
        trade_date="2023-01-03",
        membership_symbols=["000001", "000002", "000003", "000004"],
        points=[
            MarketCapPoint(
                symbol=f"00000{index}", trade_date="2023-01-03",
                total_market_value=value,
            )
            for index, value in enumerate((10, 20, 30, 40), 1)
        ],
    )
    repository.store_snapshot(
        trade_date="2024-01-03",
        membership_symbols=["000001", "000002", "000003", "000005"],
        points=[
            MarketCapPoint(
                symbol=symbol, trade_date="2024-01-03",
                total_market_value=value,
            )
            for symbol, value in zip(
                ["000001", "000002", "000003", "000005"],
                [30, 20, 10, 40],
                strict=True,
            )
        ],
    )
    market = tmp_path / "market.sqlite3"
    _market_context(market)

    result = fixed_twelve_month_size_change(
        market_factor_database=factors,
        market_context_database=market,
        symbol="000001",
        end_date="2024-01-03",
        minimum_cohort_size=4,
    )

    assert result.status == "ready"
    assert result.comparison_date == "2023-01-03"
    assert result.percentile_change_points == 66.666667
    assert result.cohort_turnover == 0.4
    assert result.membership_composition_noise is True
    assert result.start_membership_count == result.end_membership_count == 4


def test_last_valid_position_reports_suspension_distance_without_stale_peers(
    tmp_path,
) -> None:
    factors = tmp_path / "factors.sqlite3"
    MarketFactorRepository(factors).store_snapshot(
        trade_date="2024-01-03",
        membership_symbols=["000001", "000002", "000003", "000004"],
        points=[
            MarketCapPoint(
                symbol=f"00000{index}", trade_date="2024-01-03",
                total_market_value=value,
            )
            for index, value in enumerate((10, 20, 30, 40), 1)
        ],
    )
    market = tmp_path / "market.sqlite3"
    _market_context(market)
    prices = tmp_path / "prices.sqlite3"
    with sqlite3.connect(prices) as connection:
        connection.executescript("""
            create table daily_prices (
                symbol text, trade_date text, adjust text, close real
            );
            insert into daily_prices values ('000001','2024-01-03','qfq',10);
        """)

    result = last_valid_size_position(
        market_factor_database=factors,
        market_context_database=market,
        price_database=prices,
        symbol="000001",
        valuation_date="2024-01-04",
        minimum_cohort_size=4,
    )

    assert result.status == "ready"
    assert result.target_traded_on_valuation_date is False
    assert result.last_valid_trade_date == "2024-01-03"
    assert result.trading_day_distance == 1
    assert result.position is not None
    assert result.position.status == "ready"
