"""Versioned export, conflict checks, and periodic regression for accepted methods."""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import uuid4
from xml.etree import ElementTree

from pydantic import BaseModel, ConfigDict, Field, model_validator

from experience_contract import ExperienceRecord, ExperienceReviewRequest, ExperienceStatus
from research_repository import ExperienceRepository
from experience_verification import method_digest, software_digest
from settings import (
    ACCEPTED_EXPERIENCE_REGISTRY_PATH,
    EXPERIENCE_GOVERNANCE_DB,
    EXPERIENCE_REPOSITORY_DB,
    PROJECT_ROOT,
)

from canonical_json import canonical_json as _canonical, digest as _digest


REGISTRY_CONTRACT_VERSION = "v8_accepted_experience_registry_v1"
REGRESSION_REPORT_VERSION = "v8_experience_regression_report_v1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AcceptedRegistryRecord(StrictModel):
    experience_id: str = Field(pattern=r"^EXP-[A-F0-9]{20}$")
    experience_version: int = Field(ge=1)
    experience_type: str
    title: str
    value_summary: str
    trigger_conditions: list[str]
    topic_tags: list[str] = Field(default_factory=list)
    scope: list[str]
    required_inputs: list[str]
    query_plan: list[str]
    definitions: list[str]
    answer_rubric: list[str]
    anti_patterns: list[str]
    coverage_boundaries: list[str]
    validation_refs: list[str]
    supersedes: list[str]
    not_evidence: Literal[True] = True


class AcceptedExperienceRegistry(StrictModel):
    contract_version: Literal[REGISTRY_CONTRACT_VERSION] = REGISTRY_CONTRACT_VERSION
    registry_version: str = Field(pattern=r"^v[0-9]+$")
    registry_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    exported_at: str
    accepted_count: int = Field(ge=0)
    records: list[AcceptedRegistryRecord]
    ordinary_success_auto_capture: Literal[False] = False
    not_evidence: Literal[True] = True

    @model_validator(mode="after")
    def digest_matches_records(self) -> "AcceptedExperienceRegistry":
        content = {
            "contract_version": self.contract_version,
            "registry_version": self.registry_version,
            "accepted_count": self.accepted_count,
            "records": [row.model_dump(mode="json") for row in self.records],
            "ordinary_success_auto_capture": self.ordinary_success_auto_capture,
            "not_evidence": self.not_evidence,
        }
        if _digest(content) != self.registry_digest:
            raise ValueError("accepted registry digest 不匹配")
        return self


class ExperienceConflict(StrictModel):
    conflict_id: str = Field(pattern=r"^XCF-[A-F0-9]{20}$")
    kind: Literal["rubric_vs_antipattern", "supersedes_cycle", "overlapping_policy"]
    severity: Literal["blocking", "review"]
    left_experience_id: str
    right_experience_id: str
    detail: str


class RegressionCheckResult(StrictModel):
    validation_ref: str
    status: Literal["passed", "failed", "unverified"]
    detail: str


class ExperienceRegressionResult(StrictModel):
    experience_id: str
    status: Literal["passed", "failed", "unverified"]
    checks: list[RegressionCheckResult]
    auto_blocked: bool = False


class RegressionReport(StrictModel):
    contract_version: Literal[REGRESSION_REPORT_VERSION] = REGRESSION_REPORT_VERSION
    run_id: str = Field(pattern=r"^XRG-[A-F0-9]{20}$")
    started_at: str
    completed_at: str
    cadence_days: int = Field(ge=1)
    due_only: bool
    accepted_examined: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    unverified: int = Field(ge=0)
    results: list[ExperienceRegressionResult]


class RegressionExecutor(Protocol):
    def run(self, validation_ref: str) -> RegressionCheckResult: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            json.dump(payload, target, ensure_ascii=False, indent=2)
            target.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def export_accepted_registry(
    repository: ExperienceRepository,
    *,
    output: Path = ACCEPTED_EXPERIENCE_REGISTRY_PATH,
    registry_version: str = "v1",
) -> AcceptedExperienceRegistry:
    records = []
    for row in sorted(repository.list(status=ExperienceStatus.ACCEPTED, limit=None), key=lambda item: item.experience_id):
        records.append(AcceptedRegistryRecord(
            experience_id=row.experience_id,
            experience_version=row.experience_version,
            experience_type=row.experience_type.value,
            title=row.title,
            value_summary=row.value_summary,
            trigger_conditions=row.trigger_conditions,
            topic_tags=row.topic_tags,
            scope=row.scope,
            required_inputs=row.required_inputs,
            query_plan=row.query_plan,
            definitions=row.definitions,
            answer_rubric=row.answer_rubric,
            anti_patterns=row.anti_patterns,
            coverage_boundaries=row.coverage_boundaries,
            validation_refs=row.validation_refs,
            supersedes=row.supersedes,
        ))
    content = {
        "contract_version": REGISTRY_CONTRACT_VERSION,
        "registry_version": registry_version,
        "accepted_count": len(records),
        "records": [row.model_dump(mode="json") for row in records],
        "ordinary_success_auto_capture": False,
        "not_evidence": True,
    }
    registry = AcceptedExperienceRegistry.model_validate({
        **content, "registry_digest": _digest(content), "exported_at": _now(),
    })
    _atomic_write(output, registry.model_dump(mode="json"))
    return registry


def _normalized_phrases(values: list[str]) -> set[str]:
    return {
        re.sub(r"[\W_]+", "", value.casefold())
        for value in values if re.sub(r"[\W_]+", "", value.casefold())
    }


def detect_experience_conflicts(records: list[ExperienceRecord]) -> list[ExperienceConflict]:
    conflicts: dict[str, ExperienceConflict] = {}
    by_id = {record.experience_id: record for record in records}

    def add(kind: str, severity: str, left: str, right: str, detail: str) -> None:
        ordered = sorted((left, right))
        seed = {"kind": kind, "left": ordered[0], "right": ordered[1], "detail": detail}
        conflict_id = f"XCF-{_digest(seed)[:20].upper()}"
        conflicts[conflict_id] = ExperienceConflict(
            conflict_id=conflict_id, kind=kind, severity=severity,
            left_experience_id=ordered[0], right_experience_id=ordered[1], detail=detail,
        )

    graph = {record.experience_id: set(record.supersedes) & set(by_id) for record in records}
    for start in graph:
        stack: list[tuple[str, list[str]]] = [(start, [start])]
        while stack:
            current, path = stack.pop()
            for target in graph.get(current, set()):
                if target == start:
                    add("supersedes_cycle", "blocking", start, current, "supersedes 关系形成环。")
                elif target not in path:
                    stack.append((target, [*path, target]))

    for index, left in enumerate(records):
        left_rubric = _normalized_phrases(left.answer_rubric)
        left_anti = _normalized_phrases(left.anti_patterns)
        for phrase in left_rubric & left_anti:
            add("rubric_vs_antipattern", "blocking", left.experience_id, left.experience_id,
                f"同一经验把“{phrase}”同时列为输出要求与反模式。")
        for right in records[index + 1:]:
            right_rubric = _normalized_phrases(right.answer_rubric)
            right_anti = _normalized_phrases(right.anti_patterns)
            contradictory = (left_rubric & right_anti) | (right_rubric & left_anti)
            if contradictory:
                phrase = sorted(contradictory)[0]
                add("rubric_vs_antipattern", "blocking", left.experience_id, right.experience_id,
                    f"一条经验要求“{phrase}”，另一条把它列为反模式。")
            trigger_overlap = _normalized_phrases(left.trigger_conditions) & _normalized_phrases(right.trigger_conditions)
            scope_overlap = {item.casefold() for item in left.scope} & {item.casefold() for item in right.scope}
            if (
                left.experience_type == right.experience_type and trigger_overlap and scope_overlap
                and left_rubric != right_rubric
            ):
                add("overlapping_policy", "review", left.experience_id, right.experience_id,
                    "同类型经验具有重叠触发条件和范围，但输出要求不同，需人工确认是否合并或排序。")
    return sorted(conflicts.values(), key=lambda row: (row.severity != "blocking", row.conflict_id))


class ExperienceGovernanceRepository:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.executescript("""
            create table if not exists regression_runs (
                run_id text primary key,
                report_json text not null,
                started_at text not null,
                completed_at text not null
            );
            create table if not exists experience_regression_status (
                experience_id text primary key,
                last_run_id text not null,
                last_status text not null,
                last_checked_at text not null,
                next_due_at text not null
            );
            create table if not exists experience_regression_bindings (
                experience_id text primary key,
                last_run_id text not null,
                method_digest text not null,
                software_digest text not null
            );
        """)
        return connection

    def due(self, record: ExperienceRecord, *, now: datetime, code_digest: str | None = None) -> bool:
        if not self.path.is_file():
            return True
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            try:
                row = connection.execute(
                    "select s.last_status,s.next_due_at,b.method_digest,b.software_digest,s.last_checked_at "
                    "from experience_regression_status s left join experience_regression_bindings b "
                    "on b.experience_id=s.experience_id and b.last_run_id=s.last_run_id "
                    "where s.experience_id=?", (record.experience_id,),
                ).fetchone()
            except sqlite3.OperationalError:
                return True  # Legacy results are readable, but not bound to current inputs.
        if row is None or row[0] != "passed" or row[2] != method_digest(record) or row[3] != (code_digest or software_digest()):
            return True
        try:
            due_at = datetime.fromisoformat(str(row[1]))
            checked_at = datetime.fromisoformat(str(row[4]))
            return due_at.tzinfo is None or checked_at.tzinfo is None or checked_at > now or due_at <= now
        except ValueError:
            return True

    def record(self, report: RegressionReport, *, bindings: dict[str, dict[str, str]] | None = None) -> None:
        next_due = (
            datetime.fromisoformat(report.completed_at) + timedelta(days=report.cadence_days)
        ).isoformat()
        with self._connect() as connection:
            connection.execute(
                "insert into regression_runs values (?,?,?,?)",
                (report.run_id, _canonical(report.model_dump(mode="json")), report.started_at, report.completed_at),
            )
            for result in report.results:
                connection.execute(
                    "insert into experience_regression_status values (?,?,?,?,?) "
                    "on conflict(experience_id) do update set last_run_id=excluded.last_run_id,"
                    "last_status=excluded.last_status,last_checked_at=excluded.last_checked_at,"
                    "next_due_at=excluded.next_due_at",
                    (result.experience_id, report.run_id, result.status, report.completed_at, next_due),
                )
                binding = (bindings or {}).get(result.experience_id)
                if binding:
                    connection.execute(
                        "insert into experience_regression_bindings values (?,?,?,?) "
                        "on conflict(experience_id) do update set last_run_id=excluded.last_run_id,"
                        "method_digest=excluded.method_digest,software_digest=excluded.software_digest",
                        (result.experience_id, report.run_id, binding["method_digest"], binding["software_digest"]),
                    )

    def latest_report(self) -> RegressionReport | None:
        if not self.path.is_file():
            return None
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            row = connection.execute(
                "select report_json from regression_runs order by completed_at desc limit 1"
            ).fetchone()
        return RegressionReport.model_validate_json(row[0]) if row else None


class PytestRegressionExecutor:
    NAMED_TARGETS = {
        "regression:judgment_first_readability": [
            "tests/test_real_question_recovery.py", "tests/test_evidence_gateway.py",
        ],
        "regression:source_absence_scope": [
            "tests/test_real_question_recovery.py", "tests/test_evidence_gateway.py",
        ],
        "regression:entity_scope_boundary": ["tests/test_experience_retrieval.py", "tests/test_p2_4_analysis_engine.py", "tests/test_research_judgments.py"],
        "regression:same_day_evidence_bundle": ["tests/test_experience_retrieval.py", "tests/test_experience_semantics.py::test_same_day_bundles_keep_issuer_date_and_sources_separate"],
        "regression:right_censoring": ["tests/test_experience_retrieval.py", "tests/test_experience_semantics.py::test_history_dedupes_cases_and_keeps_unobserved_followups", "tests/test_experience_semantics.py::test_conflicting_duplicate_case_fails_instead_of_choosing_an_outcome"],
        "regression:point_in_time_universe": ["tests/test_experience_retrieval.py", "tests/test_universe.py"],
    }
    UNVERIFIED_REASONS = {
        "regression:discipline_taxonomy": "当前只有主题检索测试，没有处分类型、受罚对象与时点的语义检查；不把检索通过当作方法复验通过。",
    }
    ALLOWED_TEST_FILES = {
        "tests/test_recruitment_precedent.py",
        "tests/test_p2_4_analysis_engine.py",
    }

    @classmethod
    def supports(cls, validation_ref: str) -> bool:
        return validation_ref in cls.NAMED_TARGETS or validation_ref in cls.ALLOWED_TEST_FILES

    def __init__(self, project_root: Path = PROJECT_ROOT):
        self.project_root = project_root

    def run(self, validation_ref: str) -> RegressionCheckResult:
        targets = self.NAMED_TARGETS.get(validation_ref)
        if targets is None and validation_ref in self.ALLOWED_TEST_FILES:
            targets = [validation_ref]
        if targets is None:
            return RegressionCheckResult(
                validation_ref=validation_ref, status="unverified",
                detail=self.UNVERIFIED_REASONS.get(validation_ref, "validation_ref 尚未绑定到允许执行的回归检查。"),
            )
        environment = dict(os.environ)
        environment.setdefault("UV_CACHE_DIR", str(self.project_root / ".uv-cache"))
        try:
            with tempfile.TemporaryDirectory(prefix="v8-experience-regression-") as temporary:
                report_path = Path(temporary) / "pytest.xml"
                process = subprocess.run(
                    ["uv", "run", "--frozen", "pytest", "-q", *targets, "--junitxml", str(report_path)],
                    cwd=self.project_root, env=environment, capture_output=True, text=True, timeout=900, check=False,
                )
                report = ElementTree.parse(report_path)
                cases = list(report.iter("testcase"))
                failures = sum(case.find("failure") is not None for case in cases)
                errors = sum(case.find("error") is not None for case in cases)
                skipped = sum(case.find("skipped") is not None for case in cases)
        except (OSError, subprocess.TimeoutExpired, ElementTree.ParseError) as exc:
            return RegressionCheckResult(validation_ref=validation_ref, status="unverified",
                                         detail=f"回归未能完成：{type(exc).__name__}")
        output = (process.stdout + "\n" + process.stderr).strip()[-4000:]
        status = "unverified"
        if cases and not errors and not skipped:
            if process.returncode == 0 and not failures:
                status = "passed"
            elif process.returncode == 1 and failures:
                status = "failed"
        return RegressionCheckResult(
            validation_ref=validation_ref,
            status=status,
            detail=f"tests={len(cases)}, failures={failures}, errors={errors}, skipped={skipped}; pytest exit {process.returncode}\n{output}",
        )


def run_due_regressions(
    repository: ExperienceRepository,
    governance: ExperienceGovernanceRepository,
    *,
    executor: RegressionExecutor,
    cadence_days: int = 30,
    due_only: bool = True,
    registry_output: Path = ACCEPTED_EXPERIENCE_REGISTRY_PATH,
) -> RegressionReport:
    started = _now()
    now = datetime.now(timezone.utc)
    verification_root = getattr(executor, "project_root", PROJECT_ROOT)
    code = software_digest(verification_root)
    accepted = repository.list(status=ExperienceStatus.ACCEPTED, limit=None)
    selected = [row for row in accepted if not due_only or governance.due(row, now=now, code_digest=code)]
    bindings = {row.experience_id: {"method_digest": method_digest(row), "software_digest": code} for row in selected}
    cache: dict[str, RegressionCheckResult] = {}
    results: list[ExperienceRegressionResult] = []
    for record in selected:
        checks = []
        for validation_ref in record.validation_refs:
            if validation_ref not in cache:
                try:
                    cache[validation_ref] = executor.run(validation_ref)
                except Exception as exc:
                    cache[validation_ref] = RegressionCheckResult(
                        validation_ref=validation_ref, status="unverified",
                        detail=f"回归执行异常：{type(exc).__name__}",
                    )
            checks.append(cache[validation_ref])
        if any(check.status == "failed" for check in checks):
            result_status: Literal["passed", "failed", "unverified"] = "failed"
        elif any(check.status == "unverified" for check in checks):
            result_status = "unverified"
        else:
            result_status = "passed"
        results.append(ExperienceRegressionResult(
            experience_id=record.experience_id, status=result_status,
            checks=checks,
        ))
    code_changed = software_digest(verification_root) != code
    for result in results:
        current = repository.get(result.experience_id)
        if code_changed or method_digest(current) != bindings[result.experience_id]["method_digest"]:
            result.status = "unverified"
            result.checks.append(RegressionCheckResult(
                validation_ref="verification_input_binding", status="unverified",
                detail="验证期间代码或方法发生变化；本轮不接受或封禁方法。",
            ))
        if result.status == "failed":
            repository.review(result.experience_id, ExperienceReviewRequest(
                action="block", actor_type="system", reviewed_by="experience_regression_runner",
                note="定期回归失败，自动 blocked；修复并由 owner 复审后方可重新接受。",
            ))
            result.auto_blocked = True
    report = RegressionReport(
        run_id=f"XRG-{uuid4().hex[:20].upper()}", started_at=started,
        completed_at=_now(), cadence_days=cadence_days, due_only=due_only,
        accepted_examined=len(results),
        passed=sum(row.status == "passed" for row in results),
        failed=sum(row.status == "failed" for row in results),
        unverified=sum(row.status == "unverified" for row in results),
        results=results,
    )
    governance.record(report, bindings=bindings)
    if any(row.auto_blocked for row in results):
        export_accepted_registry(repository, output=registry_output)
    return report


def governance_status(
    repository: ExperienceRepository,
    governance: ExperienceGovernanceRepository,
) -> dict[str, Any]:
    records = repository.list(limit=None)
    conflicts = detect_experience_conflicts([
        row for row in records if row.status in {ExperienceStatus.CANDIDATE, ExperienceStatus.ACCEPTED}
    ])
    latest = governance.latest_report()
    return {
        "accepted_count": sum(row.status == ExperienceStatus.ACCEPTED for row in records),
        "candidate_count": sum(row.status == ExperienceStatus.CANDIDATE for row in records),
        "blocked_count": sum(row.status == ExperienceStatus.BLOCKED for row in records),
        "conflicts": [row.model_dump(mode="json") for row in conflicts],
        "latest_regression": latest.model_dump(mode="json") if latest else None,
        "ordinary_success_auto_capture": False,
        "auto_accept_enabled": True,
        "auto_accept_min_distinct_runs": 2,
        "auto_accept_policy": "owner_preapproved_replicated_v1",
        "not_evidence": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Accepted experience governance")
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export")
    export.add_argument("--registry-version", default="v1")
    export.add_argument("--output", type=Path, default=ACCEPTED_EXPERIENCE_REGISTRY_PATH)
    verify = sub.add_parser("verify")
    verify.add_argument("--all", action="store_true")
    verify.add_argument("--cadence-days", type=int, default=30)
    status_parser = sub.add_parser("status")
    status_parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    repository = ExperienceRepository(EXPERIENCE_REPOSITORY_DB)
    governance = ExperienceGovernanceRepository(EXPERIENCE_GOVERNANCE_DB)
    if args.command == "export":
        result = export_accepted_registry(
            repository, output=args.output, registry_version=args.registry_version,
        )
        print(result.model_dump_json(indent=2))
        return 0
    if args.command == "verify":
        result = run_due_regressions(
            repository, governance, executor=PytestRegressionExecutor(),
            cadence_days=args.cadence_days, due_only=not args.all,
        )
        print(result.model_dump_json(indent=2))
        return 2 if result.failed else 0
    result = governance_status(repository, governance)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
