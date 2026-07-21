from __future__ import annotations

import json
import sqlite3

from maintenance_plan import build_maintenance_plan
from data_maintenance import _validate_bootstrap_scope


def _database(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            create table daily_prices (
                symbol text, trade_date text, adjust text
            );
            create table company_announcements (
                symbol text, announcement_date text
            );
            insert into daily_prices values
                ('000001','2026-07-20','qfq'),
                ('000002','2026-07-18','qfq');
            insert into company_announcements values
                ('000001','2026-07-10'),
                ('000002','2026-07-10');
        """)


def test_plan_is_read_only_and_separates_stale_from_bootstrap(tmp_path) -> None:
    database = tmp_path / "base.sqlite3"
    _database(database)
    overlays = tmp_path / "announcements"
    overlays.mkdir()
    (overlays / "000001.json").write_text(json.dumps({
        "source": "cninfo",
        "symbol": "000001",
        "checked_through": "2026-07-21",
        "records": [],
    }), encoding="utf-8")

    plan = build_maintenance_plan(
        database=database,
        announcement_refresh_dir=overlays,
        state_database=tmp_path / "missing-state.sqlite3",
        symbols=["000001", "000002", "000003"],
        price_through="2026-07-20",
        announcement_through="2026-07-21",
        universe_snapshot_id="SU-EXAMPLE",
        universe_as_of="2026-07-20",
    )

    price, announcements = plan.sources
    assert price.current_symbols == ["000001"]
    assert price.stale_symbols == ["000002"]
    assert price.missing_baseline_symbols == ["000003"]
    assert price.estimated_minimum_requests == 4
    assert announcements.current_symbols == ["000001"]
    assert announcements.stale_symbols == ["000002"]
    assert announcements.missing_baseline_symbols == ["000003"]
    assert len(plan.warnings) == 2
    assert not (tmp_path / "missing-state.sqlite3").exists()


def test_multi_symbol_batch_rejects_one_global_bootstrap_date() -> None:
    try:
        _validate_bootstrap_scope(
            symbols=["000001", "000002"],
            price_start="2016-01-01",
            announcement_start="",
        )
    except ValueError as exc:
        assert "逐股 bootstrap" in str(exc)
    else:
        raise AssertionError("global bootstrap date must be rejected for a batch")
