"""Validated read-only inventory of official announcements plus local CNINFO refreshes."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from snapshot_metadata import load_table_snapshot


@dataclass(frozen=True)
class OfficialAnnouncement:
    announcement_id: str
    announcement_date: str
    title: str
    url: str | None
    source: str
    body_available: bool


@dataclass(frozen=True)
class AnnouncementInventory:
    records: tuple[OfficialAnnouncement, ...]
    base_as_of: str
    announcement_as_of: str
    refresh_checked_at: str | None
    refresh_count: int


def _normalize_url(value: object) -> str | None:
    url = str(value or "").strip() or None
    if url and url.startswith("http://static.cninfo.com.cn/"):
        return "https://" + url.removeprefix("http://")
    return url


def _refresh_records(
    symbol: str,
    refresh_dir: Path,
) -> tuple[list[OfficialAnnouncement], str | None]:
    path = refresh_dir / f"{symbol}.json"
    if not path.exists():
        return [], None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"公告增量快照 JSON 非法: {path}: {exc}") from exc
    if payload.get("source") != "cninfo" or str(payload.get("symbol")) != symbol:
        raise ValueError(f"公告增量快照来源或股票代码不合法: {path}")
    rows = payload.get("records")
    if not isinstance(rows, list):
        raise ValueError(f"公告增量快照缺 records list: {path}")

    records: list[OfficialAnnouncement] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"公告增量快照 records 必须全部为 object: {path}")
        announcement_id = str(row.get("announcement_id") or "").strip()
        announcement_date = str(row.get("announcement_date") or "")[:10]
        title = str(row.get("title") or "").strip()
        if not announcement_id or not announcement_date or not title:
            raise ValueError(f"公告增量快照存在缺字段记录: {symbol}")
        try:
            datetime.fromisoformat(announcement_date)
        except ValueError as exc:
            raise ValueError(f"公告增量快照日期非法: {symbol}:{announcement_date}") from exc
        body = row.get("body_text")
        url = _normalize_url(row.get("url") or row.get("pdf_url"))
        records.append(OfficialAnnouncement(
            announcement_id=announcement_id,
            announcement_date=announcement_date,
            title=title,
            url=url,
            source="cninfo_local_refresh",
            body_available=isinstance(body, str) and bool(body.strip()),
        ))
    checked_at = datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
    return records, checked_at


def load_announcement_inventory(
    *,
    symbol: str,
    base_db: Path,
    refresh_dir: Path,
) -> AnnouncementInventory:
    """Merge frozen SQLite metadata and a validated local overlay without writing either."""
    base_snapshot = load_table_snapshot(
        base_db,
        table="company_announcements",
        date_column="announcement_date",
    )
    with sqlite3.connect(f"file:{base_db}?mode=ro", uri=True) as connection:
        columns = {
            str(row[1])
            for row in connection.execute("pragma table_info(company_announcements)")
        }
        url_expression = "url" if "url" in columns else "null"
        base_rows = connection.execute(
            "select announcement_id,announcement_date,title,"
            f"{url_expression} from company_announcements where symbol=?",
            (symbol,),
        ).fetchall()

    merged = {
        str(announcement_id): OfficialAnnouncement(
            announcement_id=str(announcement_id),
            announcement_date=str(announcement_date)[:10],
            title=str(title),
            url=_normalize_url(url),
            source="frozen_v5_sqlite",
            body_available=False,
        )
        for announcement_id, announcement_date, title, url in base_rows
        if announcement_id and announcement_date and title
    }
    refresh_records, refresh_checked_at = _refresh_records(symbol, refresh_dir)
    for record in refresh_records:
        merged[record.announcement_id] = record
    records = tuple(sorted(
        merged.values(),
        key=lambda item: (item.announcement_date, item.announcement_id),
        reverse=True,
    ))
    announcement_as_of = records[0].announcement_date if records else base_snapshot.as_of
    return AnnouncementInventory(
        records=records,
        base_as_of=base_snapshot.as_of,
        announcement_as_of=announcement_as_of,
        refresh_checked_at=refresh_checked_at,
        refresh_count=len(refresh_records),
    )
