from __future__ import annotations

import json

import pytest

from market_context import HistoricalMembershipRow, MarketContextRepository
from market_factors import (
    MARKET_CAP_SOURCE,
    MarketFactorRepository,
    MarketFactorService,
    advance_market_factor_current,
    build_market_factor_manifest,
    write_market_factor_dated_manifest,
    write_market_factor_manifest,
    write_market_factor_manifest_set,
)


class FakeDailyBasicProvider:
    def __init__(self, rows):
        self.rows = rows
        self.calls: list[str] = []

    def fetch_daily_basic(self, *, trade_date: str):
        self.calls.append(trade_date)
        return self.rows


def _membership(database, symbols: list[str], day: str = "2026-07-06") -> None:
    MarketContextRepository(database).upsert_membership_rows([
        HistoricalMembershipRow(
            trade_date=day,
            symbol=symbol,
            ts_code=f"{symbol}.SZ",
            name=f"ST {symbol}",
        )
        for symbol in symbols
    ])


def _row(symbol: str, *, total_mv=100.0, circ_mv=80.0) -> dict:
    return {
        "ts_code": f"{symbol}.SZ",
        "trade_date": "20260706",
        "total_share": 10.0,
        "float_share": 8.0,
        "free_share": 6.0,
        "total_mv": total_mv,
        "circ_mv": circ_mv,
        "turnover_rate": 2.5,
    }


def test_daily_basic_materialization_uses_historical_membership_and_rmb_units(
    tmp_path,
) -> None:
    context = tmp_path / "context.sqlite3"
    factors = tmp_path / "factors.sqlite3"
    _membership(context, ["000001", "000002"])
    provider = FakeDailyBasicProvider([
        _row("000001"),
        _row("000002", total_mv=200.0, circ_mv=150.0),
        _row("000003", total_mv=1.0, circ_mv=1.0),
    ])

    snapshot = MarketFactorService(
        provider=provider,
        repository=MarketFactorRepository(factors),
        market_context_database=context,
    ).refresh(as_of="2026-07-06")
    points = MarketFactorRepository(factors).points(snapshot.snapshot_id)

    assert provider.calls == ["2026-07-06"]
    assert [point.symbol for point in points] == ["000001", "000002"]
    assert points[0].total_shares == 100_000
    assert points[0].total_market_value == 1_000_000
    assert points[0].circulating_market_value == 800_000
    assert points[0].source == MARKET_CAP_SOURCE
    assert snapshot.membership_count == 2
    assert snapshot.valid_total_market_value_count == 2
    assert snapshot.coverage_ratio == 1.0


def test_snapshot_id_is_content_addressed_and_rerun_is_idempotent(tmp_path) -> None:
    context = tmp_path / "context.sqlite3"
    factors = tmp_path / "factors.sqlite3"
    _membership(context, ["000001"])
    provider = FakeDailyBasicProvider([_row("000001")])
    service = MarketFactorService(
        provider=provider,
        repository=MarketFactorRepository(factors),
        market_context_database=context,
    )

    first = service.refresh(as_of="2026-07-06")
    second = service.refresh(as_of="2026-07-06")

    assert first.snapshot_id == second.snapshot_id
    assert MarketFactorRepository(factors).snapshot_count() == 1


def test_manifest_fails_closed_below_market_cap_coverage_threshold(tmp_path) -> None:
    context = tmp_path / "context.sqlite3"
    factors = tmp_path / "factors.sqlite3"
    manifest = tmp_path / "manifest.json"
    _membership(context, ["000001", "000002"])
    snapshot = MarketFactorService(
        provider=FakeDailyBasicProvider([_row("000001")]),
        repository=MarketFactorRepository(factors),
        market_context_database=context,
    ).refresh(as_of="2026-07-06")

    payload = build_market_factor_manifest(
        repository=MarketFactorRepository(factors),
        snapshot_id=snapshot.snapshot_id,
        coverage_threshold=0.95,
    )
    write_market_factor_manifest(payload, manifest)

    assert payload["status"] == "gaps"
    assert payload["coverage"]["ratio"] == 0.5
    assert "低于门槛" in payload["blocking_gaps"][0]
    assert json.loads(manifest.read_text())["factor_snapshot_id"] == snapshot.snapshot_id


def test_refresh_rejects_missing_historical_membership_without_current_backfill(
    tmp_path,
) -> None:
    provider = FakeDailyBasicProvider([_row("000001")])
    service = MarketFactorService(
        provider=provider,
        repository=MarketFactorRepository(tmp_path / "factors.sqlite3"),
        market_context_database=tmp_path / "missing-context.sqlite3",
    )

    with pytest.raises(ValueError, match="拒绝使用当前名单回填"):
        service.refresh(as_of="2026-07-06")

    assert provider.calls == []


def test_manifest_set_keeps_dated_artifact_when_current_pointer_advances(tmp_path) -> None:
    context = tmp_path / "context.sqlite3"
    factors = tmp_path / "factors.sqlite3"
    _membership(context, ["000001"])
    repository = MarketFactorRepository(factors)
    first = MarketFactorService(
        provider=FakeDailyBasicProvider([_row("000001")]),
        repository=repository,
        market_context_database=context,
    ).refresh(as_of="2026-07-06")
    first_manifest = build_market_factor_manifest(
        repository=repository, snapshot_id=first.snapshot_id,
    )
    current = tmp_path / "current.json"
    directory = tmp_path / "manifests"

    dated = write_market_factor_manifest_set(
        first_manifest, current_path=current, manifest_directory=directory,
    )
    first_payload = json.loads(dated.read_text(encoding="utf-8"))
    second_manifest = {
        **first_manifest,
        "factor_date": "2026-07-20",
        "factor_snapshot_id": "MFS-FFFFFFFFFFFFFFFFFFFF",
        "manifest_id": "MF-FFFFFFFFFFFFFFFFFFFF",
    }
    write_market_factor_manifest_set(
        second_manifest,
        current_path=current,
        manifest_directory=directory,
    )

    assert json.loads(dated.read_text(encoding="utf-8")) == first_payload
    assert json.loads(current.read_text(encoding="utf-8")) == second_manifest
    assert (directory / "2026-07-20.json").is_file()


def test_historical_dated_manifest_does_not_regress_current_pointer(
    tmp_path,
) -> None:
    current = tmp_path / "current.json"
    directory = tmp_path / "manifests"
    latest = {
        "factor_date": "2026-07-20",
        "factor_snapshot_id": "MFS-AAAAAAAAAAAAAAAAAAAA",
    }
    historical = {
        "factor_date": "2021-03-17",
        "factor_snapshot_id": "MFS-BBBBBBBBBBBBBBBBBBBB",
    }
    advance_market_factor_current(latest, current_path=current)

    dated = write_market_factor_dated_manifest(
        historical, manifest_directory=directory
    )
    advanced = advance_market_factor_current(
        historical, current_path=current
    )

    assert dated.name == "2021-03-17.json"
    assert advanced is False
    assert json.loads(current.read_text()) == latest


def test_current_pointer_same_snapshot_is_idempotent(tmp_path) -> None:
    current = tmp_path / "current.json"
    payload = {
        "factor_date": "2026-07-20",
        "factor_snapshot_id": "MFS-AAAAAAAAAAAAAAAAAAAA",
    }

    assert advance_market_factor_current(payload, current_path=current) is True
    assert advance_market_factor_current(payload, current_path=current) is False
