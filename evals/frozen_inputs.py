"""Explicit evaluation-only metadata fixtures; never used by the live answer path."""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import re
from unittest.mock import patch

from announcement_inventory import AnnouncementInventory, OfficialAnnouncement


def frozen_inventory_loader(fixture_name: str):
    if not re.fullmatch(r"[a-z0-9_]+\.json", fixture_name):
        raise ValueError("invalid evaluation fixture name")
    payload = json.loads((Path(__file__).parent / "fixtures" / fixture_name).read_text())
    if payload["fixture_version"] != "research_announcement_fixture_v1":
        raise ValueError("unsupported evaluation fixture")
    inventories = {}
    for symbol, rows in payload["announcements"].items():
        records = tuple(sorted((OfficialAnnouncement(
            **row, source="frozen_evaluation_fixture", body_available=False,
        ) for row in rows), key=lambda row: (row.announcement_date, row.announcement_id), reverse=True))
        inventories[symbol] = AnnouncementInventory(
            records=records, base_as_of=payload["observed_through"],
            announcement_as_of=records[0].announcement_date,
            refresh_checked_at=payload["observed_through"], refresh_count=0,
        )
    def load(*, symbol: str, **_kwargs) -> AnnouncementInventory:
        if symbol not in inventories:
            raise ValueError(f"evaluation fixture does not cover {symbol}")
        return inventories[symbol]
    return load


@contextmanager
def frozen_announcement_inputs(fixture_name: str):
    with patch("answer_engine.load_announcement_inventory", frozen_inventory_loader(fixture_name)):
        yield
