from __future__ import annotations

import json
import sqlite3

from market_comparison import load_market_comparison


DATES = [f"2026-07-{day:02d}" for day in range(1, 12)]


def _market_database(path, *, low_coverage_date: str = "") -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("""
            create table benchmark_daily (
                benchmark_id text, trade_date text, close real,
                coverage_ratio real
            )
        """)
        for index, day in enumerate(DATES):
            connection.executemany(
                "insert into benchmark_daily values (?,?,?,?)",
                [
                    (
                        "st_equal_weight_v1", day, 1000 + index * 10,
                        0.90 if day == low_coverage_date else 0.98,
                    ),
                    ("csi_2000", day, 2000 + index * 10, None),
                    ("csi_all_share", day, 5000 + index * 10, None),
                ],
            )


def _price_database(path, *, missing_date: str = "") -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("""
            create table daily_prices (
                symbol text, trade_date text, adjust text, close real
            )
        """)
        connection.executemany(
            "insert into daily_prices values ('000001',?,'qfq',?)",
            [
                (day, 10 + index)
                for index, day in enumerate(DATES)
                if day != missing_date
            ],
        )


def _manifest(
    path, *, required=None, status: str = "ready", end: str = DATES[-1]
) -> None:
    path.write_text(json.dumps({
        "manifest_id": "MC-" + "A" * 20,
        "generated_at": "2026-07-12T00:00:00+00:00",
        "current_status": status,
        "current_required_benchmarks": required or [
            "st_equal_weight_v1", "csi_2000", "csi_all_share",
        ],
        "pool_common_window": {"start": DATES[0], "end": end},
    }), encoding="utf-8")


def _universe_pointer(path, *, as_of: str = DATES[-1]) -> None:
    path.write_text(json.dumps({
        "snapshot_id": "SU-" + "B" * 20,
        "as_of": as_of,
    }), encoding="utf-8")


def test_stock_and_three_benchmarks_share_exact_trading_day_window(tmp_path) -> None:
    market = tmp_path / "market.sqlite3"
    prices = tmp_path / "prices.sqlite3"
    manifest = tmp_path / "manifest.json"
    universe = tmp_path / "current.json"
    _market_database(market)
    _price_database(prices)
    _manifest(manifest)
    _universe_pointer(universe)
    before = (market.stat().st_mtime_ns, prices.stat().st_mtime_ns)

    result = load_market_comparison(
        price_database=prices,
        market_database=market,
        manifest_path=manifest,
        universe_current_path=universe,
        symbol="000001",
        sessions=10,
    )

    assert result.ready
    assert (result.start_date, result.end_date) == (DATES[0], DATES[-1])
    assert result.returns_pct == {
        "st_equal_weight_v1": 10.0,
        "csi_2000": 5.0,
        "csi_all_share": 2.0,
        "stock": 100.0,
    }
    assert result.relative_pp["stock_minus_st"] == 90.0
    assert result.relative_pp["st_minus_csi2000"] == 5.0
    assert len(result.series_rows()) == 11
    assert result.series_rows()[0]["stock_normalized"] == 100.0
    assert result.series_rows()[-1]["stock_normalized"] == 200.0
    assert result.summary_row()["个股相对中证2000"] == "+95.00个百分点"
    assert (market.stat().st_mtime_ns, prices.stat().st_mtime_ns) == before


def test_missing_stock_trading_date_is_a_gap_not_interpolation(tmp_path) -> None:
    market = tmp_path / "market.sqlite3"
    prices = tmp_path / "prices.sqlite3"
    manifest = tmp_path / "manifest.json"
    universe = tmp_path / "current.json"
    _market_database(market)
    _price_database(prices, missing_date=DATES[5])
    _manifest(manifest)
    _universe_pointer(universe)

    result = load_market_comparison(
        price_database=prices,
        market_database=market,
        manifest_path=manifest,
        universe_current_path=universe,
        symbol="000001",
    )

    assert result.status == "gaps"
    assert DATES[5] in result.gaps[0]
    assert result.series_rows() == []


def test_low_st_coverage_blocks_the_comparison(tmp_path) -> None:
    market = tmp_path / "market.sqlite3"
    prices = tmp_path / "prices.sqlite3"
    manifest = tmp_path / "manifest.json"
    universe = tmp_path / "current.json"
    _market_database(market, low_coverage_date=DATES[3])
    _price_database(prices)
    _manifest(manifest)
    _universe_pointer(universe)

    result = load_market_comparison(
        price_database=prices,
        market_database=market,
        manifest_path=manifest,
        universe_current_path=universe,
        symbol="000001",
    )

    assert result.status == "gaps"
    assert "覆盖率低于门槛" in result.gaps[0]


def test_manifest_must_require_the_complete_pool(tmp_path) -> None:
    market = tmp_path / "market.sqlite3"
    prices = tmp_path / "prices.sqlite3"
    manifest = tmp_path / "manifest.json"
    universe = tmp_path / "current.json"
    _market_database(market)
    _price_database(prices)
    _manifest(manifest, required=["st_equal_weight_v1", "csi_all_share"])
    _universe_pointer(universe)

    result = load_market_comparison(
        price_database=prices,
        market_database=market,
        manifest_path=manifest,
        universe_current_path=universe,
        symbol="000001",
    )

    assert result.status == "gaps"
    assert result.gaps == ["manifest 缺 required benchmark: csi_2000"]


def test_manifest_end_is_the_exact_read_boundary(tmp_path) -> None:
    market = tmp_path / "market.sqlite3"
    prices = tmp_path / "prices.sqlite3"
    manifest = tmp_path / "manifest.json"
    universe = tmp_path / "current.json"
    _market_database(market)
    _price_database(prices)
    _manifest(manifest, end=DATES[-2])
    _universe_pointer(universe, as_of=DATES[-2])

    result = load_market_comparison(
        price_database=prices,
        market_database=market,
        manifest_path=manifest,
        universe_current_path=universe,
        symbol="000001",
        sessions=9,
    )

    assert result.ready
    assert result.end_date == DATES[-2]
    assert result.returns_pct["stock"] == 90.0


def test_universe_pointer_must_match_the_manifest_end(tmp_path) -> None:
    market = tmp_path / "market.sqlite3"
    prices = tmp_path / "prices.sqlite3"
    manifest = tmp_path / "manifest.json"
    universe = tmp_path / "current.json"
    _market_database(market)
    _price_database(prices)
    _manifest(manifest)
    _universe_pointer(universe, as_of=DATES[-2])

    result = load_market_comparison(
        price_database=prices,
        market_database=market,
        manifest_path=manifest,
        universe_current_path=universe,
        symbol="000001",
    )

    assert result.status == "gaps"
    assert "as-of 与市场窗口终点不一致" in result.gaps[0]
