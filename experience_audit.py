"""Run current method checks on a small isolated copy, preserving the owner's ledger."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile

from canonical_json import digest
from data_refresh import atomic_write_json
from experience_governance import ExperienceGovernanceRepository, PytestRegressionExecutor, run_due_regressions
from experience_verification import READONLY_AUDIT_PATH, SOFTWARE_INPUT_SCOPE, inventory_digest, method_digest, software_digest
from research_repository import ExperienceRepository
from settings import EXPERIENCE_REPOSITORY_DB


AUDIT_PATH = READONLY_AUDIT_PATH


def audit_inventory(*, source: Path = EXPERIENCE_REPOSITORY_DB, output: Path = AUDIT_PATH, executor=None) -> dict:
    if not source.is_file():
        raise FileNotFoundError("experience repository is unavailable")
    original = ExperienceRepository(source)
    records = original.list(limit=None)
    before = inventory_digest(records)
    code = software_digest()
    with tempfile.TemporaryDirectory(prefix="v8-experience-audit-") as temporary:
        root = Path(temporary)
        copy = root / "experiences.sqlite3"
        with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as incoming:
            with closing(sqlite3.connect(copy)) as destination:
                incoming.backup(destination)
        copied = ExperienceRepository(copy)
        copied_before = inventory_digest(copied.list(limit=None))
        report = run_due_regressions(copied, ExperienceGovernanceRepository(root / "checks.sqlite3"),
                                     executor=executor or PytestRegressionExecutor(), due_only=False,
                                     registry_output=root / "registry.json")
    after = inventory_digest(original.list(limit=None))
    unchanged = before == copied_before == after and code == software_digest()
    accepted = [row for row in records if row.status.value == "accepted"]
    complete = unchanged and len(accepted) == report.accepted_examined
    audit = {
        "audit_version": "readonly_experience_audit_v1", "completed_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if complete else "input_changed_or_incomplete",
        "source_inventory_digest": before, "source_file": source.name,
        "software_digest": code, "source_unchanged": before == after,
        "software_input_scope": SOFTWARE_INPUT_SCOPE,
        "scope": "software_rule_checks_only", "not_evidence": True,
        "bindings": {row.experience_id: method_digest(row) for row in accepted},
        "report": report.model_dump(mode="json"),
    }
    audit["content_digest"] = digest(audit)
    atomic_write_json(output.parent / "reports" / f"{audit['content_digest']}.json", audit)
    atomic_write_json(output, audit)
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=EXPERIENCE_REPOSITORY_DB)
    parser.add_argument("--output", type=Path, default=AUDIT_PATH)
    args = parser.parse_args()
    audit = audit_inventory(source=args.source, output=args.output)
    print(json.dumps({"status": audit["status"], "source_unchanged": audit["source_unchanged"],
                      **{key: audit["report"][key] for key in ("accepted_examined", "passed", "failed", "unverified")}}, ensure_ascii=False))
    return 0 if audit["status"] == "complete" and not audit["report"]["failed"] and not audit["report"]["unverified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
