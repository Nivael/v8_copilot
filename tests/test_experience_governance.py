from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess

import pytest

from experience_contract import (
    ExperienceCandidateInput,
    ExperienceReviewRequest,
    ExperienceStatus,
    ExperienceType,
)
from experience_governance import (
    ExperienceGovernanceRepository,
    PytestRegressionExecutor,
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


@pytest.mark.parametrize("exit_code,xml,expected", [
    (0, '<testsuite><testcase name="checked"/></testsuite>', "passed"),
    (1, '<testsuite><testcase name="checked"><failure/></testcase></testsuite>', "failed"),
    (0, '<testsuite><testcase name="skipped"><skipped/></testcase></testsuite>', "unverified"),
    (0, '<testsuite/>', "unverified"),
    (1, '<testsuite><testcase name="setup"><error/></testcase></testsuite>', "unverified"),
    (2, '<testsuite/>', "unverified"),
    (5, '<testsuite/>', "unverified"),
])
def test_runner_requires_actual_executed_test_evidence(monkeypatch, exit_code, xml, expected):
    def run(command, **_kwargs):
        assert "--frozen" in command
        Path(command[-1]).write_text(xml)
        return subprocess.CompletedProcess(command, exit_code, stdout="controlled test output", stderr="")
    monkeypatch.setattr(subprocess, "run", run)
    result = PytestRegressionExecutor().run("regression:source_absence_scope")
    assert result.status == expected


def test_runner_timeout_is_unverified_instead_of_failed(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("pytest", 900)
    monkeypatch.setattr(subprocess, "run", timeout)
    assert PytestRegressionExecutor().run("regression:source_absence_scope").status == "unverified"


def test_partial_discipline_checks_run_without_certifying_the_method_or_promotion():
    result = PytestRegressionExecutor().run("regression:discipline_taxonomy")
    assert result.status == "unverified"
    assert "没有处分类型" in result.detail
    assert "局部事实匹配检查通过" in result.detail
    assert "failures=0, errors=0, skipped=0" in result.detail
    assert not PytestRegressionExecutor.supports("regression:discipline_taxonomy")


def test_method_change_invalidates_a_recent_pass_even_without_version_increment(tmp_path):
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    record = accept(repository, candidate())
    governance = ExperienceGovernanceRepository(tmp_path / "governance.sqlite3")
    executor = FakeExecutor("passed")
    run_due_regressions(repository, governance, executor=executor)
    updated = repository.propose(candidate(validation_ref="regression:new_check"))
    assert updated.experience_version == record.experience_version
    assert governance.due(updated, now=datetime.now(timezone.utc))
    second = run_due_regressions(repository, governance, executor=executor)
    assert second.accepted_examined == 1
    assert executor.calls == 3  # first check, then both the original and the new check


def test_code_change_during_failed_check_does_not_block_method(tmp_path, monkeypatch):
    import experience_governance
    versions = iter(["a" * 64, "b" * 64])
    monkeypatch.setattr(experience_governance, "software_digest", lambda *_: next(versions))
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    record = accept(repository, candidate())
    governance = ExperienceGovernanceRepository(tmp_path / "governance.sqlite3")
    report = run_due_regressions(repository, governance, executor=FakeExecutor("failed"))
    assert report.unverified == 1
    assert report.failed == 0
    assert repository.get(record.experience_id).status == ExperienceStatus.ACCEPTED
    assert not report.results[0].auto_blocked


def test_recent_pass_is_due_again_after_only_a_rule_config_changes(tmp_path):
    from experience_verification import software_digest
    root=tmp_path/'software';root.mkdir();config=root/'rules.json';config.write_text('{"limit":1}')
    repository=ExperienceRepository(tmp_path/'experiences.sqlite3');record=accept(repository,candidate())
    governance=ExperienceGovernanceRepository(tmp_path/'governance.sqlite3');executor=FakeExecutor('passed');executor.project_root=root
    report=run_due_regressions(repository,governance,executor=executor)
    assert report.passed==1 and not governance.due(record,now=datetime.now(timezone.utc),code_digest=software_digest(root))
    config.write_text('{"limit":2}')
    assert governance.due(record,now=datetime.now(timezone.utc),code_digest=software_digest(root))
    second=run_due_regressions(repository,governance,executor=executor)
    assert second.accepted_examined==1 and second.passed==1


@pytest.mark.parametrize('check_status',['passed','failed'])
def test_rule_config_change_during_check_is_unverified_and_preserves_acceptance(tmp_path,check_status):
    root=tmp_path/'software';root.mkdir();config=root/'rules.json';config.write_text('{"limit":1}')
    class ConfigChangingExecutor:
        project_root=root
        def run(self,ref):
            config.write_text('{"limit":2}')
            return RegressionCheckResult(validation_ref=ref,status=check_status,detail='controlled check with changed configuration')
    repository=ExperienceRepository(tmp_path/'experiences.sqlite3');record=accept(repository,candidate())
    governance=ExperienceGovernanceRepository(tmp_path/'governance.sqlite3')
    report=run_due_regressions(repository,governance,executor=ConfigChangingExecutor())
    assert report.unverified==1 and report.failed==report.passed==0
    assert report.results[0].auto_blocked is False and repository.get(record.experience_id).status==ExperienceStatus.ACCEPTED
    assert '规则配置发生变化' in report.results[0].checks[-1].detail
