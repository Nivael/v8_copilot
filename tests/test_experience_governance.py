from __future__ import annotations

import json

from experience_contract import (
    ExperienceCandidateInput,
    ExperienceReviewRequest,
    ExperienceStatus,
    ExperienceType,
)
from experience_governance import (
    ExperienceGovernanceRepository,
    RegressionCheckResult,
    detect_experience_conflicts,
    export_accepted_registry,
    run_due_regressions,
)
from research_repository import ExperienceRepository


def candidate(*, title: str = "主回答先给判断", validation_ref: str = "regression:test") -> ExperienceCandidateInput:
    return ExperienceCandidateInput(
        experience_type=ExperienceType.PRESENTATION_RULE,
        title=title,
        value_summary="把精度下沉到依据层。",
        trigger_conditions=["比较问题"], scope=["comparison"],
        required_inputs=["evidence_pack"], query_plan=["识别实质差异"],
        definitions=["主回答可独立读懂"], answer_rubric=["首段直接回答"],
        anti_patterns=["字段清单开头"], coverage_boundaries=["不改变证据等级"],
        validation_refs=[validation_ref], source_run_refs=["migration:test"],
    )


def accept(repository: ExperienceRepository, value: ExperienceCandidateInput):
    record = repository.propose(value)
    return repository.review(record.experience_id, ExperienceReviewRequest(
        action="accept", actor_type="human", reviewed_by="owner",
    ))


def test_registry_export_is_versioned_sanitized_and_not_evidence(tmp_path) -> None:
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    accepted = accept(repository, candidate())
    output = tmp_path / "registry.json"

    registry = export_accepted_registry(repository, output=output, registry_version="v3")

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert registry.registry_version == "v3"
    assert registry.accepted_count == 1
    assert payload["records"][0]["experience_id"] == accepted.experience_id
    assert "source_run_refs" not in payload["records"][0]
    assert payload["ordinary_success_auto_capture"] is False
    assert payload["not_evidence"] is True


def test_conflict_detector_blocks_rubric_that_another_rule_forbids(tmp_path) -> None:
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    left = repository.propose(candidate(title="规则甲"))
    value = candidate(title="规则乙").model_copy(update={
        "answer_rubric": ["保留必要日期"],
        "anti_patterns": ["首段直接回答"],
    })
    right = repository.propose(value)

    conflicts = detect_experience_conflicts([left, right])

    assert any(row.kind == "rubric_vs_antipattern" and row.severity == "blocking" for row in conflicts)


class FakeExecutor:
    def __init__(self, status: str):
        self.status = status
        self.calls = 0

    def run(self, validation_ref: str) -> RegressionCheckResult:
        self.calls += 1
        return RegressionCheckResult(
            validation_ref=validation_ref, status=self.status, detail="deterministic test result",
        )


def test_failed_periodic_regression_auto_blocks_and_removes_from_registry(tmp_path) -> None:
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    record = accept(repository, candidate())
    governance = ExperienceGovernanceRepository(tmp_path / "governance.sqlite3")
    registry = tmp_path / "registry.json"

    report = run_due_regressions(
        repository, governance, executor=FakeExecutor("failed"),
        cadence_days=30, due_only=True, registry_output=registry,
    )

    assert report.failed == 1
    assert report.results[0].auto_blocked is True
    assert repository.get(record.experience_id).status == ExperienceStatus.BLOCKED
    assert json.loads(registry.read_text(encoding="utf-8"))["accepted_count"] == 0


def test_successful_regression_is_not_repeated_before_next_due_date(tmp_path) -> None:
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    accept(repository, candidate())
    governance = ExperienceGovernanceRepository(tmp_path / "governance.sqlite3")
    executor = FakeExecutor("passed")

    first = run_due_regressions(repository, governance, executor=executor, due_only=True)
    second = run_due_regressions(repository, governance, executor=executor, due_only=True)

    assert first.passed == 1
    assert second.accepted_examined == 0
    assert executor.calls == 1
