from __future__ import annotations

import json
import sqlite3

from data_refresh import atomic_write_json
from market_factors import (
    MarketCapPoint,
    MarketFactorRepository,
    build_market_factor_manifest,
)
from microcap_comparison import load_microcap_comparison


SYMBOLS = [f"0000{index:02d}" for index in range(1, 11)]


def _factor_asset(tmp_path):
    database = tmp_path / "factors.sqlite3"
    repository = MarketFactorRepository(database)
    snapshot = repository.store_snapshot(
        trade_date="2026-07-06",
        membership_symbols=SYMBOLS,
        points=[
            MarketCapPoint(
                symbol=symbol,
                trade_date="2026-07-06",
                total_market_value=index * 100_000_000,
                circulating_market_value=index * 80_000_000,
            )
            for index, symbol in enumerate(SYMBOLS, 1)
        ],
    )
    manifest = build_market_factor_manifest(
        repository=repository,
        snapshot_id=snapshot.snapshot_id,
    )
    path = tmp_path / "manifest.json"
    atomic_write_json(path, manifest)
    return database, path, snapshot


def _prices(path, *, missing_symbol: str = "") -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "create table daily_prices "
            "(symbol text,trade_date text,adjust text,close real)"
        )
        for index, symbol in enumerate(SYMBOLS, 1):
            connection.execute(
                "insert into daily_prices values (?,?,?,?)",
                (symbol, "2026-07-06", "qfq", 10.0),
            )
            if symbol != missing_symbol:
                end = 10.0 * (1 + (30 - index) / 100)
                connection.execute(
                    "insert into daily_prices values (?,?,?,?)",
                    (symbol, "2026-07-20", "qfq", end),
                )


def test_bottom_30_percent_uses_window_start_market_cap_without_lookahead(
    tmp_path,
) -> None:
    factor_db, manifest, snapshot = _factor_asset(tmp_path)
    price_db = tmp_path / "prices.sqlite3"
    _prices(price_db)
    # A later snapshot reverses the order, but the comparison must stay bound to
    # the manifest's window-start snapshot.
    MarketFactorRepository(factor_db).store_snapshot(
        trade_date="2026-07-20",
        membership_symbols=SYMBOLS,
        points=[
            MarketCapPoint(
                symbol=symbol,
                trade_date="2026-07-20",
                total_market_value=(11 - index) * 100_000_000,
            )
            for index, symbol in enumerate(SYMBOLS, 1)
        ],
    )

    result = load_microcap_comparison(
        price_database=price_db,
        factor_database=factor_db,
        manifest_path=manifest,
        manifest_directory=tmp_path / "dated-manifests",
        start_date="2026-07-06",
        end_date="2026-07-20",
    )

    assert result.ready
    assert result.factor_snapshot_id == snapshot.snapshot_id
    assert result.microcap_symbols == SYMBOLS[:3]
    assert result.other_symbols == SYMBOLS[3:]
    assert result.cutoff_market_value == 300_000_000
    assert result.microcap_stats["median_return"] == 28.0
    assert result.other_stats["median_return"] == 23.0
    assert result.body_rows()[0]["定义ID"] == "st_total_mv_bottom_30pct_v1"
    assert result.body_rows()[-1]["微盘减普通ST中位收益"] == "+5.00个百分点"


def test_missing_endpoint_below_cohort_coverage_is_an_explicit_gap(tmp_path) -> None:
    factor_db, manifest, _ = _factor_asset(tmp_path)
    price_db = tmp_path / "prices.sqlite3"
    _prices(price_db, missing_symbol=SYMBOLS[0])

    result = load_microcap_comparison(
        price_database=price_db,
        factor_database=factor_db,
        manifest_path=manifest,
        manifest_directory=tmp_path / "dated-manifests",
        start_date="2026-07-06",
        end_date="2026-07-20",
    )

    assert result.status == "gaps"
    assert "微盘ST收益覆盖率" in result.gaps[0]
    assert result.body_rows()[0]["row_id"] == "microcap_comparison_gap"


def test_dated_manifest_wins_after_current_pointer_advances(tmp_path) -> None:
    factor_db, start_manifest, snapshot = _factor_asset(tmp_path)
    price_db = tmp_path / "prices.sqlite3"
    _prices(price_db)
    manifest_directory = tmp_path / "dated-manifests"
    manifest_directory.mkdir()
    atomic_write_json(
        manifest_directory / "2026-07-06.json",
        json.loads(start_manifest.read_text(encoding="utf-8")),
    )
    current = tmp_path / "current.json"
    atomic_write_json(current, {
        "status": "ready",
        "factor_date": "2026-07-20",
        "factor_snapshot_id": "MFS-FFFFFFFFFFFFFFFFFFFF",
        "factor_definition": {"definition_id": "st_total_mv_bottom_30pct_v1"},
    })

    result = load_microcap_comparison(
        price_database=price_db,
        factor_database=factor_db,
        manifest_path=current,
        manifest_directory=manifest_directory,
        start_date="2026-07-06",
        end_date="2026-07-20",
    )

    assert result.ready
    assert result.factor_snapshot_id == snapshot.snapshot_id
