import json
import sqlite3
from pathlib import Path

import pytest

from snapshot_metadata import (
    SnapshotContractError,
    limiting_as_of,
    load_episode_snapshot,
    load_price_snapshot,
    load_table_snapshot,
)


def test_price_snapshot_can_be_scoped_to_one_symbol(tmp_path: Path) -> None:
    database = tmp_path / "prices.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "create table daily_prices (symbol text, trade_date text, close real, adjust text)"
        )
        for day in range(1, 13):
            connection.execute(
                "insert into daily_prices values (?,?,?,?)",
                ("000001", f"2026-07-{day:02d}", float(day), "qfq"),
            )
        for day in range(1, 16):
            connection.execute(
                "insert into daily_prices values (?,?,?,?)",
                ("000002", f"2026-07-{day:02d}", float(day), "qfq"),
            )

    snapshot = load_price_snapshot(database, symbol="000001")

    assert snapshot.as_of == "2026-07-12"
    assert snapshot.symbol_count == 1
    assert snapshot.row_count == 12


def test_table_snapshot_rejects_malformed_dates(tmp_path: Path) -> None:
    database = tmp_path / "bad.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("create table events (event_date text)")
        connection.execute("insert into events values ('2026-99-99')")

    with pytest.raises(SnapshotContractError, match="日期非法"):
        load_table_snapshot(database, table="events", date_column="event_date")


def test_episode_snapshot_rejects_malformed_as_of(tmp_path: Path) -> None:
    index = tmp_path / "episode.jsonl"
    index.write_text('{"symbol":"000001"}\n', encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "builder_version": "fixture", "as_of": "unknown"
    }), encoding="utf-8")

    with pytest.raises(SnapshotContractError, match="日期非法"):
        load_episode_snapshot(index, manifest)


def test_limiting_as_of_rejects_malformed_freshness() -> None:
    with pytest.raises(SnapshotContractError, match="日期非法"):
        limiting_as_of("2026-07-10", "x")
