from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta

from p7_anomalies import AnomalyRun
from p7_announcements import AnnouncementRun
from p7_daily import LinkageRun
from p7_manifest import build_p7_manifest, write_p7_manifest_set
from p7_status import build_status


def _runs(mode: str):
    anomaly = AnomalyRun(
        run_id="P7AR-11111111111111111111", generated_at="2026-09-04T00:00:00+00:00",
        start_date="2026-01-01", through="2026-09-03", fact_count=1,
        calculable_count=1, broad_hit_count=0, balanced_hit_count=0,
        strict_hit_count=0, zero_mad_breakout_count=0, episode_counts={},
        anomalies=[], episodes=[],
    )
    announcement = AnnouncementRun(
        run_id="P7AN-11111111111111111111", generated_at="2026-09-04T00:00:00+00:00",
        start_date="2026-01-01", through="2026-09-03", announcement_count=0,
        bundle_count=0, priority_bundle_count=0, hard_transition_count=0,
        category_counts={}, facts=[], bundles=[], transitions=[],
    )
    linkage = LinkageRun(
        run_id=("P7LR-11111111111111111111" if mode == "historical_replay" else "P7LR-22222222222222222222"),
        generated_at="2026-09-04T00:00:00+00:00", through="2026-09-03",
        anomaly_run_id=anomaly.run_id, announcement_run_id=announcement.run_id,
        queue_items=[], shadow_outcomes=[], relation_counts={},
        shadow_summary={"mode": mode},
    )
    return anomaly, announcement, linkage


def test_historical_and_prospective_manifests_coexist_and_current_prefers_prospective(tmp_path):
    current = tmp_path / "current.json"
    manifests = tmp_path / "manifests"
    historical = build_p7_manifest(
        anomaly_run=_runs("historical_replay")[0],
        announcement_run=_runs("historical_replay")[1],
        linkage_run=_runs("historical_replay")[2],
    )
    prospective_runs = _runs("prospective")
    prospective = build_p7_manifest(
        anomaly_run=prospective_runs[0], announcement_run=prospective_runs[1],
        linkage_run=prospective_runs[2],
    )
    historical_path = write_p7_manifest_set(historical, current_path=current, manifest_directory=manifests)
    prospective_path = write_p7_manifest_set(prospective, current_path=current, manifest_directory=manifests)
    assert historical_path.name.startswith("2026-09-03_historical_replay_P7M-")
    assert prospective_path.name.startswith("2026-09-03_prospective_P7M-")
    assert json.loads(current.read_text())["shadow_mode"] == "prospective"
    write_p7_manifest_set(historical, current_path=current, manifest_directory=manifests)
    assert json.loads(current.read_text())["shadow_mode"] == "prospective"


def test_forward_gate_is_mechanical_and_requires_all_frozen_checks(tmp_path):
    start = date(2026, 9, 4)
    days = [(start + timedelta(days=index)).isoformat() for index in range(60)]
    activity_manifest = tmp_path / "activity.json"
    activity_manifest.write_text(json.dumps({
        "checked_through": days[-1], "latest_turnover_rate_f_coverage": 0.99,
    }))
    context = tmp_path / "context.sqlite3"
    with sqlite3.connect(context) as connection:
        connection.execute("create table benchmark_daily (benchmark_id text,trade_date text)")
        connection.executemany(
            "insert into benchmark_daily values ('csi_all_share',?)", [(day,) for day in days]
        )
    activity = tmp_path / "activity.sqlite3"
    with sqlite3.connect(activity) as connection:
        connection.execute(
            "create table activity_snapshots (trade_date text,coverage_ratio real,daily_row_count integer,"
            "daily_basic_row_count integer,limit_row_count integer,fetched_at text,snapshot_id text)"
        )
        connection.executemany(
            "insert into activity_snapshots values (?,?,?,?,?,?,?)",
            [(day, .99, 1, 1, 1, day, f'S{index}') for index, day in enumerate(days)],
        )
    intelligence = tmp_path / "p7.sqlite3"
    summary = {
        "shadow_summary": {
            "mode": "prospective", "episode_count": 20, "company_count": 15,
            "matched_control_episode_ratio": .8,
        }
    }
    with sqlite3.connect(intelligence) as connection:
        connection.execute("create table linkage_runs (summary_json text,created_at text)")
        connection.execute("insert into linkage_runs values (?,?)", (json.dumps(summary), "2026-12-01"))
    status = build_status(
        activity_manifest=activity_manifest, intelligence_database=intelligence,
        market_context_database=context, activity_database=activity,
    )
    assert status["forward_gate"]["eligible_for_owner_release_review"] is True
    assert all(status["forward_gate"]["checks"].values())
