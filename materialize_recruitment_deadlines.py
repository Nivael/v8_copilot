"""Materialize verified recruitment deadlines from official CNINFO PDFs.

This is intentionally separate from the Answer path. It may use the network and
writes only a local JSON artifact; the research answer only reads that artifact.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
import re
from datetime import datetime, timezone
from pathlib import Path

from announcement_body import AnnouncementBodyError, load_announcement_body
from announcement_inventory import OfficialAnnouncement
from recruitment_precedent import (
    MATERIALIZATION_SCHEMA_VERSION,
    extract_recruitment_deadline,
)
from settings import DATA_ROOT, RECRUITMENT_DEADLINE_MATERIALIZATION


DEFAULT_DATABASE = DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"


def _subject_scope(title: str) -> str:
    if any(term in title for term in ("控股股东", "子公司", "孙公司")):
        return "related_entity"
    return "listed_company"


def _stock_name(text: str) -> str:
    match = re.search(r"证券简称\s*[：:]\s*(.+?)\s+公告编号", text[:3000])
    return re.sub(r"\s+", "", match.group(1)) if match else ""


def _records(database: Path) -> list[OfficialAnnouncement]:
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "select announcement_id,announcement_date,title,url from company_announcements "
            "where announcement_id not glob '*[^0-9]*' "
            "and (title like '%公开招募%投资人%' or title like '%招募%重整投资人%') "
            "and title not like '%进展%' and title not like '%延期%' "
            "and title not like '%延长%' and title not like '%结果%' "
            "order by announcement_date,announcement_id"
        ).fetchall()
    return [OfficialAnnouncement(
        announcement_id=str(announcement_id),
        announcement_date=str(announcement_date)[:10],
        title=str(title),
        url=str(url or "") or None,
        source="frozen_v5_sqlite",
        body_available=False,
    ) for announcement_id, announcement_date, title, url in rows]


def materialize(database: Path, output: Path, *, limit: int | None = None) -> dict:
    records = _records(database)
    if limit is not None:
        records = records[:limit]
    cases: list[dict] = []
    failures: list[dict] = []
    for record in records:
        try:
            body = load_announcement_body(
                record,
                source_db=database,
                allow_network=True,
                timeout_seconds=20.0,
            )
            deadline = extract_recruitment_deadline(body.text, record.announcement_date)
            if not deadline:
                raise ValueError("公告正文未提取到报名截止日")
            cases.append({
                "announcement_id": record.announcement_id,
                "symbol": "",
                "announcement_date": record.announcement_date,
                "title": record.title,
                "recruitment_deadline": deadline,
                "source_url": body.source_url,
                "subject_scope": _subject_scope(record.title),
                "stock_name": _stock_name(body.text),
                "body_source": body.source,
            })
        except (AnnouncementBodyError, ValueError) as exc:
            failures.append({
                "announcement_id": record.announcement_id,
                "announcement_date": record.announcement_date,
                "title": record.title,
                "error": str(exc),
            })

    symbols_by_id: dict[str, str] = {}
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        for announcement_id, symbol in connection.execute(
            "select announcement_id,symbol from company_announcements"
        ):
            symbols_by_id[str(announcement_id)] = str(symbol)
    for case in cases:
        case["symbol"] = symbols_by_id.get(case["announcement_id"], "")

    payload = {
        "schema_version": MATERIALIZATION_SCHEMA_VERSION,
        "materialized_at": datetime.now(timezone.utc).isoformat(),
        "source_database": "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3",
        "record_count": len(records),
        "case_count": len(cases),
        "failure_count": len(failures),
        "cases": cases,
        "failures": failures,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=output.name, suffix=".tmp", dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            json.dump(payload, target, ensure_ascii=False, indent=2)
        os.replace(temp_name, output)
    except OSError:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--output", type=Path, default=RECRUITMENT_DEADLINE_MATERIALIZATION)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    payload = materialize(args.database.resolve(), args.output.resolve(), limit=args.limit)
    print(json.dumps({
        "output": str(args.output),
        "record_count": payload["record_count"],
        "case_count": payload["case_count"],
        "failure_count": payload["failure_count"],
    }, ensure_ascii=False))
    return 0 if payload["case_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
