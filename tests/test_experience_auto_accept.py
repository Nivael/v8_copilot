from __future__ import annotations

import json

from experience_auto_accept import POLICY_ID, auto_accept_all, auto_accept_candidate
from experience_contract import ExperienceCandidateInput, ExperienceStatus, ExperienceType
from experience_governance import RegressionCheckResult
from research_repository import ExperienceRepository, ResearchRunCreate, ResearchRunLedger


class FakeExecutor:
    def __init__(self, status: str = "passed"):
        self.status = status
        self.calls: list[str] = []

    def run(self, validation_ref: str) -> RegressionCheckResult:
        self.calls.append(validation_ref)
        return RegressionCheckResult(
            validation_ref=validation_ref, status=self.status, detail="fake regression",
        )


class RaisingExecutor:
    def run(self, validation_ref: str) -> RegressionCheckResult:
        raise RuntimeError("runner unavailable")


def _run(ledger: ResearchRunLedger, request_id: str) -> str:
    return ledger.record(ResearchRunCreate(
        request_id=request_id, question_text="两只股票怎么比较？",
        normalized_intent="stock_comparison",
        evidence_pack_ids=["EP-AAAAAAAAAAAAAAAAAAAA"], final_answer="先统一主体。",
        validation_report={"valid": True}, source_freshness={"announcement": "2026-08-12"},
        agent_surface="codex_desktop",
    )).run_id


def _candidate(source_runs: list[str]) -> ExperienceCandidateInput:
    return ExperienceCandidateInput(
        experience_type=ExperienceType.REASONING_RULE,
        title="比较题先统一主体",
        value_summary="先区分上市公司和关联主体，再作比较。",
        trigger_conditions=["股票比较"], topic_tags=["主体边界", "横截面比较"],
        scope=["comparison"], required_inputs=["entity_scope"],
        query_plan=["确认主体", "统一截止日"], definitions=["主体按法律实体区分"],
        answer_rubric=["先给单维度判断"], anti_patterns=["混淆母子公司"],
        coverage_boundaries=["不升级为整体优劣"],
        validation_refs=["regression:entity_scope_boundary"],
        source_run_refs=source_runs,
    )


def test_single_run_waits_without_running_regression(tmp_path) -> None:
    ledger = ResearchRunLedger(tmp_path / "runs.sqlite3")
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    record = repository.propose(_candidate([_run(ledger, "req-1")]))
    executor = FakeExecutor()

    result = auto_accept_candidate(
        record, repository=repository, ledger=ledger, executor=executor,
        registry_output=tmp_path / "registry.json",
    )

    assert result.outcome == "waiting_for_replication"
    assert executor.calls == []
    assert repository.get(record.experience_id).status == ExperienceStatus.CANDIDATE


def test_two_runs_and_passing_regression_auto_accept(tmp_path) -> None:
    ledger = ResearchRunLedger(tmp_path / "runs.sqlite3")
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    record = repository.propose(_candidate([
        _run(ledger, "req-1"), _run(ledger, "req-2"),
    ]))
    output = tmp_path / "registry.json"

    result = auto_accept_candidate(
        record, repository=repository, ledger=ledger, executor=FakeExecutor(),
        registry_output=output,
    )

    accepted = repository.get(record.experience_id)
    assert result.outcome == "accepted"
    assert accepted.status == ExperienceStatus.ACCEPTED
    assert accepted.reviewed_by == POLICY_ID
    assert json.loads(output.read_text())["accepted_count"] == 1


def test_failed_regression_blocks_instead_of_auto_accepting(tmp_path) -> None:
    ledger = ResearchRunLedger(tmp_path / "runs.sqlite3")
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    record = repository.propose(_candidate([
        _run(ledger, "req-1"), _run(ledger, "req-2"),
    ]))

    result = auto_accept_candidate(
        record, repository=repository, ledger=ledger, executor=FakeExecutor("failed"),
        registry_output=tmp_path / "registry.json",
    )

    assert result.outcome == "blocked"
    assert repository.get(record.experience_id).status == ExperienceStatus.BLOCKED


def test_regression_runner_exception_fails_closed(tmp_path) -> None:
    ledger = ResearchRunLedger(tmp_path / "runs.sqlite3")
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    record = repository.propose(_candidate([
        _run(ledger, "req-1"), _run(ledger, "req-2"),
    ]))

    result = auto_accept_candidate(
        record, repository=repository, ledger=ledger, executor=RaisingExecutor(),
        registry_output=tmp_path / "registry.json",
    )

    assert result.outcome == "blocked"
    assert result.checks[0].status == "unverified"
    assert "RuntimeError" in result.checks[0].detail


def test_batch_reuses_the_same_regression_result(tmp_path) -> None:
    ledger = ResearchRunLedger(tmp_path / "runs.sqlite3")
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    source_runs = [_run(ledger, "req-1"), _run(ledger, "req-2")]
    first = _candidate(source_runs)
    second = first.model_copy(update={
        "experience_type": ExperienceType.QUERY_PLAN,
        "title": "比较题先统一截止日",
    })
    repository.propose(first)
    repository.propose(second)
    executor = FakeExecutor()

    results = auto_accept_all(
        repository=repository, ledger=ledger, executor=executor,
        registry_output=tmp_path / "registry.json",
    )

    assert [row.outcome for row in results] == ["accepted", "accepted"]
    assert executor.calls == ["regression:entity_scope_boundary"]
