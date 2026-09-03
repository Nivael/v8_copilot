"""One-page machine-readable P7 implementation and release-gate status."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from settings import (
    MARKET_ACTIVITY_DB, MARKET_ACTIVITY_MANIFEST_PATH, MARKET_CONTEXT_DB,
    P7_FORWARD_SHADOW_START, P7_INTELLIGENCE_DB,
)


FORWARD_GATE = {
    "minimum_trading_days": 60,
    "minimum_balanced_episodes": 20,
    "minimum_companies": 15,
    "minimum_control_match_ratio": 0.80,
    "minimum_daily_turnover_coverage": 0.95,
    "minimum_good_day_ratio": 0.90,
    "ratchet": "thresholds_may_only_tighten_before_forward_outcomes_are_read",
}


def _latest(connection: sqlite3.Connection, table: str, column: str) -> dict[str, Any]:
    row = connection.execute(
        f"select {column} from {table} order by created_at desc limit 1"
    ).fetchone()
    return json.loads(row[0]) if row else {}


def build_status(
    *, activity_manifest: Path, intelligence_database: Path,
    provider_probe: Path | None = None,
    market_context_database: Path = MARKET_CONTEXT_DB,
    activity_database: Path = MARKET_ACTIVITY_DB,
) -> dict[str, Any]:
    activity = json.loads(activity_manifest.read_text(encoding="utf-8")) if activity_manifest.is_file() else {}
    announcement: dict[str, Any] = {}
    anomaly: dict[str, Any] = {}
    linkage: dict[str, Any] = {}
    historical_linkage: dict[str, Any] = {}
    prospective_linkage: dict[str, Any] = {}
    if intelligence_database.is_file():
        with sqlite3.connect(f"file:{intelligence_database}?mode=ro", uri=True) as connection:
            tables = {str(row[0]) for row in connection.execute("select name from sqlite_master where type='table'")}
            if "announcement_runs" in tables:
                announcement = _latest(connection, "announcement_runs", "summary_json")
            if "p7_runs" in tables:
                anomaly = _latest(connection, "p7_runs", "payload_json")
            if "linkage_runs" in tables:
                linkage = _latest(connection, "linkage_runs", "summary_json")
                row = connection.execute(
                    "select summary_json from linkage_runs "
                    "where json_extract(summary_json,'$.shadow_summary.mode')='historical_replay' "
                    "order by created_at desc limit 1"
                ).fetchone()
                historical_linkage = json.loads(row[0]) if row else {}
                row = connection.execute(
                    "select summary_json from linkage_runs "
                    "where json_extract(summary_json,'$.shadow_summary.mode')='prospective' "
                    "order by created_at desc limit 1"
                ).fetchone()
                prospective_linkage = json.loads(row[0]) if row else {}
    probe = json.loads(provider_probe.read_text(encoding="utf-8")) if provider_probe and provider_probe.is_file() else {}
    exchange_status = "available" if all(
        probe.get("provider_permission_matrix", {}).get(name, {}).get("status") in {"success", "empty_valid"}
        for name in ("stk_shock", "stk_high_shock", "stk_alert")
    ) else "unavailable"
    shadow = historical_linkage.get("shadow_summary", linkage.get("shadow_summary", {}))
    prospective_days = 0
    good_coverage_days = 0
    good_day_ratio = 0.0
    checked_through = str(activity.get("checked_through") or "")
    if checked_through >= P7_FORWARD_SHADOW_START and market_context_database.is_file():
        with sqlite3.connect(f"file:{market_context_database}?mode=ro", uri=True) as connection:
            prospective_days = int(connection.execute(
                "select count(*) from benchmark_daily where benchmark_id='csi_all_share' "
                "and trade_date between ? and ?",
                (P7_FORWARD_SHADOW_START, checked_through),
            ).fetchone()[0])
    if prospective_days and activity_database.is_file():
        with sqlite3.connect(f"file:{activity_database}?mode=ro", uri=True) as connection:
            good_coverage_days = int(connection.execute(
                "with ranked as (select trade_date,coverage_ratio,daily_row_count,daily_basic_row_count,"
                "limit_row_count,row_number() over (partition by trade_date order by fetched_at desc,snapshot_id desc) rn "
                "from activity_snapshots where trade_date between ? and ?) "
                "select count(*) from ranked where rn=1 and daily_row_count>0 and daily_basic_row_count>0 "
                "and limit_row_count>0 and coverage_ratio>=?",
                (P7_FORWARD_SHADOW_START, checked_through, FORWARD_GATE["minimum_daily_turnover_coverage"]),
            ).fetchone()[0])
        good_day_ratio = good_coverage_days / prospective_days
    prospective_summary = prospective_linkage.get("shadow_summary", {})
    gate_checks = {
        "trading_days": prospective_days >= FORWARD_GATE["minimum_trading_days"],
        "balanced_episodes": int(prospective_summary.get("episode_count") or 0) >= FORWARD_GATE["minimum_balanced_episodes"],
        "companies": int(prospective_summary.get("company_count") or 0) >= FORWARD_GATE["minimum_companies"],
        "control_match_ratio": float(prospective_summary.get("matched_control_episode_ratio") or 0) >= FORWARD_GATE["minimum_control_match_ratio"],
        "coverage_stability": good_day_ratio >= FORWARD_GATE["minimum_good_day_ratio"],
    }
    forward_gate = {
        "contract": FORWARD_GATE,
        "observed": {
            "trading_days": prospective_days,
            "balanced_episodes": int(prospective_summary.get("episode_count") or 0),
            "companies": int(prospective_summary.get("company_count") or 0),
            "control_match_ratio": prospective_summary.get("matched_control_episode_ratio"),
            "good_coverage_days": good_coverage_days,
            "good_day_ratio": round(good_day_ratio, 8),
        },
        "checks": gate_checks,
        "eligible_for_owner_release_review": all(gate_checks.values()),
        "inference_status": "descriptive_only_until_separately_validated",
    }
    return {
        "contract_version": "p7_status_v1",
        "announcement": announcement,
        "activity": {
            **activity,
            "coverage_pct": round(float(activity.get("latest_turnover_rate_f_coverage") or 0) * 100, 2),
        },
        "anomaly": anomaly,
        "linkage": linkage,
        "shadow": {**shadow, "prospective_days": prospective_days, "prospective_minimum_days": 60, "prospective_start_date": P7_FORWARD_SHADOW_START},
        "forward_gate": forward_gate,
        "provider": {
            "probe_id": probe.get("probe_id", ""),
            "required_matrix": {
                name: probe.get("provider_permission_matrix", {}).get(name, {}).get("status", "not_probed")
                for name in ("daily", "daily_basic", "suspend_d", "stk_limit")
            },
            "daily_basic_limit_status": (
                "missing_despite_explicit_request"
                if "limit_status" in probe.get("provider_permission_matrix", {}).get("daily_basic", {}).get("missing_required_fields", [])
                else "available"
            ),
            "exchange_reference_status": exchange_status,
        },
        "release_gates": {
            "p7a": "ready_for_owner_descriptive_release_decision" if announcement else "unavailable",
            "p7b": (
                "ready_for_owner_descriptive_release_decision"
                if forward_gate["eligible_for_owner_release_review"]
                else "keep_shadow_until_forward_gate_is_met"
            ),
            "p7c": "keep_shadow_until_forward_gate_and_research_value_validation_are_met",
        },
        "human_review_cards": 2,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build P7 release status")
    parser.add_argument("--activity-manifest", type=Path, default=MARKET_ACTIVITY_MANIFEST_PATH)
    parser.add_argument("--intelligence-database", type=Path, default=P7_INTELLIGENCE_DB)
    parser.add_argument("--provider-probe", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    status = build_status(
        activity_manifest=args.activity_manifest,
        intelligence_database=args.intelligence_database,
        provider_probe=args.provider_probe,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "release_gates": status["release_gates"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
