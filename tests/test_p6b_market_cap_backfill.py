from __future__ import annotations

import json

import pytest

from market_context import HistoricalMembershipRow, MarketContextRepository
from p6b_market_cap_backfill import (
    SOURCE_DRY_PLAN_ID,
    build_backfill_plan,
    load_backfill_plan,
    run_backfill,
)


DATES = ("2024-04-29", "2025-04-30")


class FakeProvider:
    def __init__(self):
        self.calls: list[str] = []

    def fetch_daily_basic(self, *, trade_date: str):
        self.calls.append(trade_date)
        symbols = ("000001", "000002")
        if trade_date == DATES[1]:
            symbols = ("000001",)
        return [
            {
                "ts_code": f"{symbol}.SZ",
                "trade_date": trade_date.replace("-", ""),
                "total_share": 10,
                "float_share": 8,
                "free_share": 7,
                "total_mv": 100,
                "circ_mv": 80,
                "turnover_rate": 1,
            }
            for symbol in symbols
        ]


def _plan():
    return build_backfill_plan(
        {
            "plan_id": SOURCE_DRY_PLAN_ID,
            "as_of": "2026-07-20",
            "episodes": [
                {"start_date": DATES[1]},
                {"start_date": DATES[0]},
                {"start_date": DATES[0]},
            ],
        },
        trading_calendar=list(DATES),
    )


def _membership(path) -> None:
    repository = MarketContextRepository(path)
    repository.upsert_membership_rows([
        HistoricalMembershipRow(
            trade_date=day,
            symbol=symbol,
            ts_code=f"{symbol}.SZ",
            name=f"ST {symbol}",
        )
        for day in DATES
        for symbol in ("000001", "000002")
    ])


def test_plan_is_content_addressed_and_rejects_drift(tmp_path) -> None:
    plan = _plan()
    path = tmp_path / "plan.json"
    path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")

    loaded = load_backfill_plan(path)

    assert loaded.plan_id == plan.plan_id
    assert loaded.trade_dates == list(DATES)
    assert loaded.source_episode_start_count == 2
    payload = json.loads(path.read_text())
    payload["trade_dates"].append("2026-01-01")
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="content hash"):
        load_backfill_plan(path)


def test_plan_snaps_non_trading_episode_start_to_next_trade_date() -> None:
    plan = build_backfill_plan(
        {
            "plan_id": SOURCE_DRY_PLAN_ID,
            "as_of": "2026-07-20",
            "episodes": [
                {"start_date": "2026-07-12"},
                {"start_date": "2026-07-15"},
            ],
        },
        trading_calendar=["2026-07-10", "2026-07-13", "2026-07-15"],
    )

    assert plan.trade_dates == ["2026-07-13", "2026-07-15"]
    assert plan.anchor_date_adjustments[0].model_dump() == {
        "source_episode_start_date": "2026-07-12",
        "market_cap_anchor_trade_date": "2026-07-13",
        "reason": "next_csi_all_share_trade_date",
    }


def test_backfill_is_resumable_and_only_advances_current_when_complete(
    tmp_path,
) -> None:
    context = tmp_path / "context.sqlite3"
    factors = tmp_path / "factors.sqlite3"
    manifests = tmp_path / "manifests"
    current = tmp_path / "current.json"
    _membership(context)
    provider = FakeProvider()
    plan = _plan()

    first = run_backfill(
        plan=plan,
        provider=provider,
        market_context_database=context,
        market_factor_database=factors,
        manifest_directory=manifests,
        current_manifest_path=current,
        max_fetches=1,
        retry_backoff_seconds=0,
    )

    assert first.status == "partial"
    assert first.snapshot_date_count == 1
    assert first.missing_dates == [DATES[1]]
    assert not current.exists()
    assert (manifests / f"{DATES[0]}.json").is_file()

    second = run_backfill(
        plan=plan,
        provider=provider,
        market_context_database=context,
        market_factor_database=factors,
        manifest_directory=manifests,
        current_manifest_path=current,
        retry_backoff_seconds=0,
    )

    assert second.status == "complete"
    assert second.snapshot_date_count == 2
    assert second.ready_date_count == 1
    assert second.gap_date_count == 1
    assert second.current_pointer_advanced is True
    assert json.loads(current.read_text())["factor_date"] == DATES[1]
    assert provider.calls == list(DATES)

    third = run_backfill(
        plan=plan,
        provider=provider,
        market_context_database=context,
        market_factor_database=factors,
        manifest_directory=manifests,
        current_manifest_path=current,
        retry_backoff_seconds=0,
    )

    assert third.status == "complete"
    assert third.fetched_date_count == 0
    assert third.existing_date_count == 2
    assert provider.calls == list(DATES)
