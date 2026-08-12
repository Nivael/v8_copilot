"""Owner-preauthorized automatic promotion for corroborated experience candidates."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from experience_contract import ExperienceRecord, ExperienceReviewRequest, ExperienceStatus
from experience_governance import (
    PytestRegressionExecutor,
    RegressionCheckResult,
    detect_experience_conflicts,
    export_accepted_registry,
)
from research_repository import ExperienceRepository, ResearchRunLedger
from settings import (
    ACCEPTED_EXPERIENCE_REGISTRY_PATH,
    EXPERIENCE_REPOSITORY_DB,
    RESEARCH_RUN_LEDGER_DB,
)


POLICY_ID = "owner_preapproved_replicated_v1"


class RegressionExecutor(Protocol):
    def run(self, validation_ref: str) -> RegressionCheckResult: ...


class CachedRegressionExecutor:
    """Reuse identical regression results during one batch promotion run."""

    def __init__(self, delegate: RegressionExecutor):
        self.delegate = delegate
        self.results: dict[str, RegressionCheckResult] = {}

    def run(self, validation_ref: str) -> RegressionCheckResult:
        if validation_ref not in self.results:
            self.results[validation_ref] = self.delegate.run(validation_ref)
        return self.results[validation_ref]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AutoAcceptanceResult(StrictModel):
    experience_id: str
    outcome: Literal["accepted", "waiting_for_replication", "blocked", "unchanged"]
    policy_id: Literal[POLICY_ID] = POLICY_ID
    distinct_source_runs: int = Field(ge=0)
    minimum_source_runs: int = Field(default=2, ge=2)
    reason: str
    checks: list[RegressionCheckResult] = Field(default_factory=list)


def _existing_run_ids(record: ExperienceRecord, ledger: ResearchRunLedger) -> list[str]:
    result = []
    for run_id in sorted(set(record.source_run_refs)):
        if not run_id.startswith("RUN-"):
            continue
        try:
            ledger.get(run_id)
        except KeyError:
            continue
        result.append(run_id)
    return result


def _block_candidate(
    record: ExperienceRecord,
    repository: ExperienceRepository,
    *,
    note: str,
) -> None:
    if record.status == ExperienceStatus.CANDIDATE:
        repository.review(record.experience_id, ExperienceReviewRequest(
            action="block", actor_type="system", reviewed_by=POLICY_ID, note=note,
        ))


def auto_accept_candidate(
    record: ExperienceRecord,
    *,
    repository: ExperienceRepository,
    ledger: ResearchRunLedger,
    executor: RegressionExecutor | None = None,
    registry_output: Path = ACCEPTED_EXPERIENCE_REGISTRY_PATH,
    minimum_source_runs: int = 2,
) -> AutoAcceptanceResult:
    """Promote only replicated, executable and conflict-free methods."""
    if record.status == ExperienceStatus.ACCEPTED:
        return AutoAcceptanceResult(
            experience_id=record.experience_id, outcome="unchanged",
            distinct_source_runs=len(_existing_run_ids(record, ledger)),
            minimum_source_runs=minimum_source_runs, reason="经验已经 accepted。",
        )
    if record.status not in {ExperienceStatus.CANDIDATE, ExperienceStatus.BLOCKED}:
        return AutoAcceptanceResult(
            experience_id=record.experience_id, outcome="unchanged",
            distinct_source_runs=len(_existing_run_ids(record, ledger)),
            minimum_source_runs=minimum_source_runs,
            reason=f"状态 {record.status.value} 不参加自动晋级。",
        )
    run_ids = _existing_run_ids(record, ledger)
    if len(run_ids) < minimum_source_runs:
        return AutoAcceptanceResult(
            experience_id=record.experience_id, outcome="waiting_for_replication",
            distinct_source_runs=len(run_ids), minimum_source_runs=minimum_source_runs,
            reason=f"需要至少 {minimum_source_runs} 个真实运行复现；当前 {len(run_ids)} 个。",
        )
    unsupported = [
        ref for ref in record.validation_refs if not PytestRegressionExecutor.supports(ref)
    ]
    if unsupported:
        note = f"owner policy 无法执行 validation_refs: {unsupported}"
        _block_candidate(record, repository, note=note)
        return AutoAcceptanceResult(
            experience_id=record.experience_id, outcome="blocked",
            distinct_source_runs=len(run_ids), minimum_source_runs=minimum_source_runs,
            reason=note,
        )
    active = repository.list(status=ExperienceStatus.ACCEPTED, limit=1000)
    blocking = [
        conflict for conflict in detect_experience_conflicts([*active, record])
        if conflict.severity == "blocking" and record.experience_id in {
            conflict.left_experience_id, conflict.right_experience_id,
        }
    ]
    if blocking:
        note = f"owner policy 检出 blocking conflict: {blocking[0].detail}"
        _block_candidate(record, repository, note=note)
        return AutoAcceptanceResult(
            experience_id=record.experience_id, outcome="blocked",
            distinct_source_runs=len(run_ids), minimum_source_runs=minimum_source_runs,
            reason=note,
        )
    runner = executor or PytestRegressionExecutor()
    checks = []
    for ref in dict.fromkeys(record.validation_refs):
        try:
            checks.append(runner.run(ref))
        except Exception as exc:  # fail closed if the executable check cannot run
            checks.append(RegressionCheckResult(
                validation_ref=ref,
                status="unverified",
                detail=f"回归执行异常：{type(exc).__name__}",
            ))
    failed = [check for check in checks if check.status != "passed"]
    if failed:
        note = "owner policy 回归未通过: " + "; ".join(
            f"{check.validation_ref}={check.status}" for check in failed
        )
        _block_candidate(record, repository, note=note)
        return AutoAcceptanceResult(
            experience_id=record.experience_id, outcome="blocked", checks=checks,
            distinct_source_runs=len(run_ids), minimum_source_runs=minimum_source_runs,
            reason=note,
        )
    try:
        repository.review(record.experience_id, ExperienceReviewRequest(
            action="accept", actor_type="owner_policy", reviewed_by=POLICY_ID,
            note=(
                f"Owner 预授权自动晋级：{len(run_ids)} 个真实运行复现；"
                f"{len(checks)} 个 validation_ref 通过；无 blocking conflict。"
            ),
        ))
    except ValueError as exc:
        note = f"owner policy 通用性校验失败: {exc}"
        _block_candidate(record, repository, note=note)
        return AutoAcceptanceResult(
            experience_id=record.experience_id, outcome="blocked", checks=checks,
            distinct_source_runs=len(run_ids), minimum_source_runs=minimum_source_runs,
            reason=note,
        )
    export_accepted_registry(repository, output=registry_output)
    return AutoAcceptanceResult(
        experience_id=record.experience_id, outcome="accepted", checks=checks,
        distinct_source_runs=len(run_ids), minimum_source_runs=minimum_source_runs,
        reason="满足 owner 预授权门，已自动写入 accepted registry。",
    )


def auto_accept_all(
    *,
    repository: ExperienceRepository,
    ledger: ResearchRunLedger,
    executor: RegressionExecutor | None = None,
    registry_output: Path = ACCEPTED_EXPERIENCE_REGISTRY_PATH,
) -> list[AutoAcceptanceResult]:
    runner = CachedRegressionExecutor(executor or PytestRegressionExecutor())
    records = [
        *repository.list(status=ExperienceStatus.CANDIDATE, limit=1000),
        *repository.list(status=ExperienceStatus.BLOCKED, limit=1000),
    ]
    return [
        auto_accept_candidate(
            record, repository=repository, ledger=ledger, executor=runner,
            registry_output=registry_output,
        )
        for record in records
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="only report current candidate counts")
    args = parser.parse_args()
    repository = ExperienceRepository(EXPERIENCE_REPOSITORY_DB)
    ledger = ResearchRunLedger(RESEARCH_RUN_LEDGER_DB)
    if args.dry_run:
        rows = [
            *repository.list(status=ExperienceStatus.CANDIDATE, limit=1000),
            *repository.list(status=ExperienceStatus.BLOCKED, limit=1000),
        ]
        print(json.dumps({"policy_id": POLICY_ID, "eligible_status_count": len(rows)}, ensure_ascii=False))
        return 0
    results = auto_accept_all(repository=repository, ledger=ledger)
    print(json.dumps([row.model_dump(mode="json") for row in results], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
