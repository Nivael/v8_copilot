import json
import sqlite3
from pathlib import Path

from p8_dry_plan import build_body_missing_queue


def test_body_missing_queue_keeps_full_denominator_and_source_pointer(tmp_path: Path) -> None:
    database = tmp_path / "p7.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "create table announcement_runs (run_id text, created_at text)"
        )
        connection.execute(
            "create table announcement_facts (run_id text, available_as_of text, "
            "announcement_id text, payload_json text)"
        )
        connection.execute("insert into announcement_runs values ('run-1','2026-01-01')")
        rows = [
            {
                "announcement_id": "ann-missing", "symbol": "000001",
                "available_as_of": "2026-01-01", "title": "重整进展",
                "category": "restructuring_and_pre_restructuring",
                "source": "cninfo", "url": "https://example.test/ann.pdf",
                "llm_route": "shortlist_body_missing",
            },
            {
                "announcement_id": "ann-ready", "symbol": "000002",
                "available_as_of": "2026-01-01", "title": "已有正文",
                "category": "routine_or_other", "source": "cninfo", "url": "",
                "llm_route": "shortlist_body_available",
            },
        ]
        for item in rows:
            connection.execute(
                "insert into announcement_facts values (?,?,?,?)",
                ("run-1", item["available_as_of"], item["announcement_id"], json.dumps(item)),
            )
    queue = build_body_missing_queue(database)
    assert queue["record_count"] == 1
    assert queue["records"][0]["announcement_id"] == "ann-missing"
    assert queue["records"][0]["url"] == "https://example.test/ann.pdf"
    assert len(queue["content_digest"]) == 64
