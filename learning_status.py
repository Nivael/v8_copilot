"""Read-only observations of the learning loop; no inferred quality score."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from experience_contract import ExperienceRecord
from experience_governance import PytestRegressionExecutor, RegressionReport, detect_experience_conflicts
from experience_verification import READONLY_AUDIT_PATH, inventory_digest, method_digest, software_digest
from canonical_json import digest
from freshness_manifest import FreshnessManifest
from market_risk import MARKET_RISK_DIR, market_update_status
from settings import (
    EXPERIENCE_GOVERNANCE_DB, EXPERIENCE_REPOSITORY_DB, FRESHNESS_MANIFEST_PATH,
    RESEARCH_RUN_LEDGER_DB,
)


def _read_rows(path: Path, query: str) -> list[dict[str, Any]]:
    # A missing source must stay missing. Never call the repositories' migrating readers.
    if not path.is_file():
        raise FileNotFoundError(path.name)
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(query)]


def _instant(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except ValueError:
        return None


def _regression_state(record: ExperienceRecord, row: dict[str, Any] | None, now: datetime,
                      binding: dict[str, Any] | None, code: str) -> str:
    if row is None:
        return "never_checked"
    checked = _instant(row["last_checked_at"])
    due = _instant(row["next_due_at"])
    if checked is None or due is None or checked > now or due < checked:
        return "unverified"
    if record.reviewed_at and record.reviewed_at.tzinfo is None:
        return "unverified"
    if record.reviewed_at and checked < record.reviewed_at:
        return "needs_recheck"
    if not binding or binding.get("last_run_id") != row["last_run_id"] or binding.get("method_digest") != method_digest(record) or binding.get("software_digest") != code:
        return "needs_recheck"
    if row["last_status"] == "failed":
        return "failed"
    if row["last_status"] != "passed":
        return "unverified"
    return "due" if due <= now else "current"


def _freshness(path: Path, today: date) -> dict[str, Any]:
    try:
        payload = FreshnessManifest.model_validate_json(path.read_text(encoding="utf-8")).model_dump()
        sources = []
        for row in payload["sources"]:
            as_of = row.get("as_of") or ""
            try:
                age = (today - date.fromisoformat(as_of)).days
            except (ValueError, TypeError):
                age = None
            sources.append({
                "source_id": row["source_id"], "label": row["label"],
                "as_of": as_of or None, "checked_at": row.get("checked_at") or None,
                "expected_through": row.get("expected_through") or None,
                "declared_status": row.get("status", "unknown"),
                "age_calendar_days": age,
                "row_count": row.get("row_count"), "coverage_count": row.get("coverage_count"),
                "source_ref": row.get("source_ref", ""),
            })
        return {
            "availability": "available", "manifest_id": payload.get("manifest_id"),
            "generated_at": payload.get("generated_at"),
            "declared_status": payload.get("overall_status", "unknown"),
            "universe_as_of": payload.get("universe_as_of") or None,
            "research_symbol_count": len(payload.get("research_symbols", [])),
            "sources": sources,
            "blocking_gaps": payload.get("blocking_gaps", []),
            "coverage_gaps": payload.get("coverage_gaps", []),
        }
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return {"availability": "missing" if not path.exists() else "invalid", "sources": []}


def _readonly_audit(path: Path, records: list[ExperienceRecord], code: str, now: datetime) -> tuple[dict, dict]:
    try:
        audit = json.loads(path.read_text())
        content_digest = audit.pop("content_digest")
        if audit.get("audit_version") != "readonly_experience_audit_v1" or digest(audit) != content_digest:
            raise ValueError("audit integrity mismatch")
        report = RegressionReport.model_validate(audit["report"])
        results = {row.experience_id: row for row in report.results}
        accepted = {row.experience_id: row for row in records if row.status.value == "accepted"}
        if len(results) != len(report.results) or set(results) != set(accepted):
            return {"availability": "stale"}, {}
        if (report.accepted_examined != len(results)
            or report.passed != sum(row.status == "passed" for row in results.values())
            or report.failed != sum(row.status == "failed" for row in results.values())
            or report.unverified != sum(row.status == "unverified" for row in results.values())):
            raise ValueError("audit totals mismatch")
        if any(row.status == "passed" and (not row.checks or any(check.status != "passed" for check in row.checks)) for row in results.values()):
            raise ValueError("audit pass without passing checks")
        if (audit.get("status") != "complete" or audit.get("source_unchanged") is not True
            or audit.get("scope") != "software_rule_checks_only"
            or audit.get("software_digest") != code
            or audit.get("source_inventory_digest") != inventory_digest(records)
            or any(audit["bindings"].get(eid) != method_digest(record) for eid, record in accepted.items())):
            return {"availability": "stale"}, {}
        checked = _instant(report.completed_at)
        if checked is None or checked > now:
            raise ValueError("invalid audit date")
        if checked + timedelta(days=report.cadence_days) <= now:
            return {"availability": "expired"}, {}
        return {"availability": "current", "completed_at": report.completed_at,
                "accepted_examined": report.accepted_examined, "passed": report.passed,
                "failed": report.failed, "unverified": report.unverified,
                "run_id": report.run_id, "content_digest": content_digest,
                "source_unchanged": True, "cadence_days": report.cadence_days}, results
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {"availability": "missing" if not path.exists() else "invalid"}, {}


def build_learning_status(
    *, experience_db: Path = EXPERIENCE_REPOSITORY_DB,
    ledger_db: Path = RESEARCH_RUN_LEDGER_DB,
    governance_db: Path = EXPERIENCE_GOVERNANCE_DB,
    freshness_path: Path = FRESHNESS_MANIFEST_PATH,
    audit_path: Path = READONLY_AUDIT_PATH,
    market_snapshot_dir: Path = MARKET_RISK_DIR,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    today = now.astimezone(ZoneInfo("Asia/Shanghai")).date()
    availability: dict[str, str] = {}
    gaps = []

    def read(key: str, path: Path, query: str) -> list[dict[str, Any]] | None:
        try:
            result = _read_rows(path, query)
            availability[key] = "available"
            return result
        except (OSError, sqlite3.Error):
            availability[key] = "missing" if not path.exists() else "invalid"
            gaps.append(f"{key}:{availability[key]}")
            return None

    raw = read("experiences", experience_db, "select * from experiences order by created_at desc")
    records: list[ExperienceRecord] = []
    if raw is not None:
        try:
            # Table columns own lifecycle state; payload_json owns method fields.
            records = [ExperienceRecord.model_validate({
                **json.loads(row["payload_json"]),
                **{key: row[key] for key in (
                    "experience_id", "experience_version", "status", "reviewed_at", "reviewed_by",
                )},
            }) for row in raw]
        except (ValueError, KeyError, TypeError):
            availability["experiences"] = "invalid"
            gaps.append("experiences:invalid_record")
    counts = None
    if availability["experiences"] == "available":
        counts = {state: sum(record.status.value == state for record in records) for state in (
            "accepted", "candidate", "blocked", "ignored", "merged", "closed", "superseded",
        )}

    runs = read("runs", ledger_db,
                "select run_id,validation_report_json,experience_hits_json,created_at from research_runs")
    valid_ids = set()
    existing_ids = set()
    run_summary = None
    if runs is not None:
        try:
            existing_ids = {row["run_id"] for row in runs}
            valid_ids = {row["run_id"] for row in runs
                         if json.loads(row["validation_report_json"]).get("valid") is True}
            with_hits = sum(bool(json.loads(row["experience_hits_json"])) for row in runs)
            run_summary = {"total": len(runs), "validator_passed": len(valid_ids),
                           "with_experience_hits": with_hits,
                           "latest_at": max((row["created_at"] for row in runs), default=None)}
        except (ValueError, TypeError, AttributeError):
            availability["runs"] = "invalid"
            valid_ids, existing_ids = set(), set()
            gaps.append("runs:invalid_record")

    checks = read("regressions", governance_db,
                  "select experience_id,last_run_id,last_checked_at,next_due_at,last_status from experience_regression_status")
    by_id = {row["experience_id"]: row for row in checks or []}
    bindings = {}
    if checks:
        try:
            bindings = {row["experience_id"]: row for row in _read_rows(
                governance_db, "select * from experience_regression_bindings",
            )}
        except (OSError, sqlite3.Error):
            pass  # Legacy checks are displayed as requiring a recheck, never as current passes.
    code = software_digest()
    readonly_audit, audited_results = _readonly_audit(audit_path, records, code, now)
    reports = read("regression_reports", governance_db,
                   "select report_json from regression_runs order by completed_at desc limit 1")
    latest_report = None
    if reports:
        try:
            report = json.loads(reports[0]["report_json"])
            latest_report = {key: report[key] for key in (
                "run_id", "completed_at", "accepted_examined", "passed", "failed", "unverified",
            )}
        except (ValueError, KeyError, TypeError):
            availability["regression_reports"] = "invalid"
            gaps.append("regression_reports:invalid_record")

    active = [row for row in records if row.status.value in {"candidate", "accepted"}]
    conflicts = detect_experience_conflicts(active)
    blocking_ids = {eid for conflict in conflicts if conflict.severity == "blocking"
                    for eid in (conflict.left_experience_id, conflict.right_experience_id)}
    methods = []
    for record in records:
        refs = set(record.source_run_refs)
        run_count = len(refs & existing_ids) if run_summary is not None else None
        valid_count = len(refs & valid_ids) if run_summary is not None else None
        unsupported = [ref for ref in record.validation_refs if not PytestRegressionExecutor.supports(ref)]
        state = _regression_state(record, by_id.get(record.experience_id), now,
                                   bindings.get(record.experience_id), code) if checks is not None else "unknown"
        verification_source = "governance_ledger"
        checked_at = by_id.get(record.experience_id, {}).get("last_checked_at")
        next_due = by_id.get(record.experience_id, {}).get("next_due_at")
        binding = bindings.get(record.experience_id)
        audit_result = audited_results.get(record.experience_id)
        audit_checked = _instant(readonly_audit.get("completed_at"))
        if audit_result and audit_checked and (not _instant(checked_at) or audit_checked >= _instant(checked_at)):
            state = "current" if audit_result.status == "passed" else audit_result.status
            checked_at = readonly_audit["completed_at"]
            next_due = (audit_checked + timedelta(days=readonly_audit["cadence_days"])).isoformat()
            verification_source = "readonly_audit"
            binding = {"last_run_id": readonly_audit["run_id"], "method_digest": method_digest(record), "software_digest": code}
        methods.append({
            "experience_id": record.experience_id, "title": record.title,
            "status": record.status.value, "experience_version": record.experience_version,
            "source_ref_count": len(refs), "existing_source_runs": run_count,
            "validator_passed_source_runs": valid_count,
            "unresolved_source_refs": sorted(refs - existing_ids) if run_summary is not None else None,
            "unsupported_validation_refs": unsupported,
            "verification_notes": [PytestRegressionExecutor.UNVERIFIED_REASONS[ref]
                                   for ref in unsupported if ref in PytestRegressionExecutor.UNVERIFIED_REASONS],
            "blocking_conflict": record.experience_id in blocking_ids,
            "regression_state": state,
            "last_checked_at": checked_at, "next_due_at": next_due,
            "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
            "reviewed_by": record.reviewed_by,
            "verification_binding": binding, "verification_source": verification_source,
        })
    accepted = [row for row in methods if row["status"] == "accepted"]
    regression_counts = None if counts is None or (checks is None and readonly_audit.get("availability") != "current") else {
        state: sum(row["regression_state"] == state for row in accepted)
        for state in ("current", "due", "never_checked", "needs_recheck", "unverified", "failed")
    }
    freshness = _freshness(freshness_path, today)
    availability["freshness"] = freshness["availability"]
    if freshness["availability"] != "available":
        gaps.append(f"freshness:{freshness['availability']}")
    return {
        "contract_version": "v8_learning_status_v1", "generated_at": now.isoformat(),
        "observation_date": today.isoformat(), "timezone": "Asia/Shanghai",
        "availability": availability, "gaps": gaps,
        "counts": counts, "runs": run_summary, "regression_counts": regression_counts,
        "current_software_digest": code,
        "latest_regression": latest_report,
        "readonly_audit": readonly_audit,
        "conflicts": [row.model_dump(mode="json") for row in conflicts],
        "methods": methods, "freshness": freshness,
        "market_updates": market_update_status(snapshot_dir=market_snapshot_dir, now=now),
        "quality_evaluation": {"status": "not_measured", "accuracy": None,
                               "reason": "尚无独立留出题集的前后对照；库存、调用和回归通过均不等于研究准确率。"},
        "automation": {"promotion": "on_candidate_or_feedback", "minimum_source_runs": 2,
                       "periodic_verification": "explicit_command", "schedule_status": "not_observed"},
        "read_only": True, "not_evidence": True,
    }
