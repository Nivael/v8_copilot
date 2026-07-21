from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from types import SimpleNamespace

import data_maintenance
import freshness_manifest as module
from freshness_manifest import build_freshness_manifest, load_freshness_manifest, write_freshness_manifest


def _sqlite(path, statements: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(statements)


def _fixtures(monkeypatch, tmp_path) -> None:
    database = tmp_path / "research.sqlite3"
    _sqlite(database, """
        create table daily_prices (
            symbol text, trade_date text, adjust text, close real
        );
        insert into daily_prices values
            ('603398','2024-01-01','qfq',10),
            ('603398','2024-01-02','qfq',10),
            ('603398','2024-01-03','qfq',10),
            ('603398','2024-01-04','qfq',10),
            ('603398','2024-01-05','qfq',10),
            ('603398','2024-01-06','qfq',10),
            ('603398','2024-01-07','qfq',10),
            ('603398','2024-01-08','qfq',10),
            ('603398','2024-01-09','qfq',10),
            ('603398','2024-01-10','qfq',10),
            ('603398','2024-01-11','qfq',10),
            ('603398','2024-01-12','qfq',10);
        create table company_announcements (
            announcement_id text, symbol text, announcement_date text, title text
        );
        insert into company_announcements values ('1','603398','2024-01-01','公告');
    """)
    episode_index = tmp_path / "episode.jsonl"
    episode_index.write_text('{"event_id":"E-1"}\n', encoding="utf-8")
    episode_manifest = tmp_path / "episode-manifest.json"
    episode_manifest.write_text(json.dumps({
        "builder_version": "test", "as_of": "2024-01-03",
    }), encoding="utf-8")
    lens = tmp_path / "release-library.json"
    lens.write_text(json.dumps({
        "library_version": "test", "frozen_at": "2024-01-03",
        "records": [{"release_id": "RL-1"}],
    }), encoding="utf-8")
    refresh = tmp_path / "announcement-refresh"
    refresh.mkdir()
    refresh_file = refresh / "603398.json"
    refresh_file.write_text(json.dumps({
        "symbol": "603398", "source": "cninfo", "records": [{
            "announcement_id": "123", "announcement_date": "2024-01-03", "title": "最新公告",
        }],
    }), encoding="utf-8")
    timestamp = datetime(2024, 1, 3, 12, 0).timestamp()
    os.utime(refresh_file, (timestamp, timestamp))
    bodies = tmp_path / "bodies" / "123"
    bodies.mkdir(parents=True)
    (bodies / "123.json").write_text(json.dumps({
        "announcement_id": "123", "announcement_date": "2024-01-03", "text": "正文",
    }), encoding="utf-8")
    shareholder = tmp_path / "shareholder.sqlite3"
    _sqlite(shareholder, """
        create table shareholder_count_snapshots (report_date text);
        insert into shareholder_count_snapshots values ('2024-01-02');
        create table equity_timeline_events (event_date text);
        insert into equity_timeline_events values ('2024-01-03');
    """)
    recruitment = tmp_path / "recruitment.json"
    recruitment.write_text(json.dumps({
        "materialized_at": "2024-01-03T12:00:00Z",
        "cases": [{"symbol": "603398", "announcement_date": "2024-01-03"}],
    }), encoding="utf-8")

    monkeypatch.setattr(module, "BASE_DB", database)
    monkeypatch.setattr(module, "EPISODE_INDEX", episode_index)
    monkeypatch.setattr(module, "EPISODE_MANIFEST", episode_manifest)
    monkeypatch.setattr(module, "RELEASE_LIBRARY", lens)
    monkeypatch.setattr(module, "ANNOUNCEMENT_REFRESH_DIR", refresh)
    monkeypatch.setattr(module, "ANNOUNCEMENT_BODY_CACHE_DIR", tmp_path / "bodies")
    monkeypatch.setattr(module, "SHAREHOLDER_DB", shareholder)
    monkeypatch.setattr(module, "RECRUITMENT_DEADLINE_MATERIALIZATION", recruitment)
    monkeypatch.setattr(module, "DATA_MAINTENANCE_DB", tmp_path / "maintenance.sqlite3")


def test_manifest_is_ready_only_for_declared_current_scope(monkeypatch, tmp_path) -> None:
    _fixtures(monkeypatch, tmp_path)

    manifest = build_freshness_manifest(
        expected_price_through="2024-01-03",
        expected_announcement_checked_through="2024-01-03",
        research_symbols=["603398"],
    )

    assert manifest.overall_status == "ready"
    sources = {source.source_id: source for source in manifest.sources}
    assert sources["daily_prices"].status == "current"
    assert sources["company_announcements"].status == "current"
    assert sources["company_announcements"].as_of == "2024-01-03"
    output = tmp_path / "freshness.json"
    write_freshness_manifest(manifest, output)
    assert load_freshness_manifest(output).manifest_id == manifest.manifest_id


def test_manifest_records_full_universe_provenance(monkeypatch, tmp_path) -> None:
    _fixtures(monkeypatch, tmp_path)
    snapshot = SimpleNamespace(
        snapshot_id="SU-" + "A" * 20,
        as_of="2024-01-03",
        content_digest="b" * 64,
        member_count=1,
        symbols=["603398"],
    )

    manifest = build_freshness_manifest(
        expected_price_through="2024-01-03",
        expected_announcement_checked_through="2024-01-03",
        research_symbols=["603398"],
        universe_snapshot=snapshot,
    )

    assert manifest.contract_version == "v8_freshness_manifest_v1"
    assert manifest.universe_snapshot_id == snapshot.snapshot_id
    assert manifest.universe_as_of == "2024-01-03"
    assert manifest.universe_content_digest == "b" * 64
    assert manifest.universe_member_count == 1


def test_manifest_reports_symbol_coverage_and_price_gaps(monkeypatch, tmp_path) -> None:
    _fixtures(monkeypatch, tmp_path)

    manifest = build_freshness_manifest(
        expected_price_through="2024-01-15",
        expected_announcement_checked_through="2024-01-03",
        research_symbols=["603398", "300068"],
    )

    assert manifest.overall_status == "gaps"
    sources = {source.source_id: source for source in manifest.sources}
    assert sources["daily_prices"].status == "stale"
    assert sources["company_announcements"].status == "stale"
    assert sources["company_announcements"].details["missing_refresh_symbols"] == ["300068"]


def test_price_checkpoint_marks_suspended_symbol_verified_without_fake_price(monkeypatch, tmp_path) -> None:
    _fixtures(monkeypatch, tmp_path)
    state = tmp_path / "maintenance.sqlite3"
    _sqlite(state, """
        create table refresh_checkpoints (
            source_id text, symbol text, checked_through text, observed_as_of text,
            status text, last_attempted_at text, last_success_at text,
            rows_seen integer, rows_written integer, metadata_json text, error text
        );
        insert into refresh_checkpoints values (
            'tushare_daily_qfq','300068','2024-01-15','2024-01-10',
            'success','2024-01-15T01:00:00Z','2024-01-15T01:00:00Z',
            0,0,'{}',''
        );
    """)

    manifest = build_freshness_manifest(
        expected_price_through="2024-01-15",
        expected_announcement_checked_through="2024-01-03",
        research_symbols=["300068"],
    )

    source = next(item for item in manifest.sources if item.source_id == "daily_prices")
    assert source.status == "current"
    assert source.details["missing_symbols"] == []
    assert source.details["per_symbol_as_of"] == {}
    assert source.details["per_symbol_verified_through"] == {"300068": "2024-01-15"}


def test_announcement_promotion_validates_then_atomically_writes(monkeypatch, tmp_path) -> None:
    refresh = tmp_path / "refresh"
    monkeypatch.setattr(data_maintenance, "ANNOUNCEMENT_REFRESH_DIR", refresh)
    source = tmp_path / "input.json"
    source.write_text(json.dumps({
        "symbol": "603398", "source": "cninfo", "records": [{
            "announcement_id": "123", "announcement_date": "2024-01-03", "title": "公告",
        }],
    }), encoding="utf-8")

    destination = data_maintenance._promote_announcement(source, "603398")

    assert destination == refresh / "603398.json"
    assert json.loads(destination.read_text(encoding="utf-8"))["source"] == "cninfo"
