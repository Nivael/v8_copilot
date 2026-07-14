from __future__ import annotations

import pytest

from experience_contract import (
    ExperienceCandidateInput,
    ExperienceFeedbackRequest,
    ExperienceReviewRequest,
    ExperienceStatus,
    ExperienceType,
)
from experience_distiller import distill_feedback
from research_repository import (
    ExperienceRepository,
    ResearchRunCreate,
    ResearchRunLedger,
)


def candidate(*, source: str = "RUN-AAAAAAAAAAAAAAAAAAAAAAAA") -> ExperienceCandidateInput:
    return ExperienceCandidateInput(
        experience_type=ExperienceType.PRESENTATION_RULE,
        title="主回答先给判断",
        value_summary="把证据精度放入依据层。",
        trigger_conditions=["比较问题"],
        scope=["comparison"],
        required_inputs=["evidence_pack"],
        query_plan=["识别实质差异"],
        definitions=["主回答可独立读懂"],
        answer_rubric=["首段直接回答"],
        anti_patterns=["字段清单开头"],
        coverage_boundaries=["不改变证据等级"],
        validation_refs=["regression:readability"],
        source_run_refs=[source],
    )


def test_experience_proposal_dedupes_and_merges_source_runs(tmp_path) -> None:
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    first = repository.propose(candidate())
    second = repository.propose(candidate(source="RUN-BBBBBBBBBBBBBBBBBBBBBBBB"))

    assert first.experience_id == second.experience_id
    assert second.status == ExperienceStatus.CANDIDATE
    assert second.source_run_refs == [
        "RUN-AAAAAAAAAAAAAAAAAAAAAAAA",
        "RUN-BBBBBBBBBBBBBBBBBBBBBBBB",
    ]


def test_read_endpoints_do_not_create_repository_files(tmp_path) -> None:
    experience_path = tmp_path / "experiences.sqlite3"
    run_path = tmp_path / "runs.sqlite3"

    assert ExperienceRepository(experience_path).list() == []
    assert ResearchRunLedger(run_path).list() == []
    assert not experience_path.exists()
    assert not run_path.exists()


def test_only_human_review_can_accept_experience(tmp_path) -> None:
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    record = repository.propose(candidate())

    with pytest.raises(PermissionError, match="human"):
        repository.review(record.experience_id, ExperienceReviewRequest(
            action="accept", actor_type="codex", reviewed_by="codex",
        ))

    accepted = repository.review(record.experience_id, ExperienceReviewRequest(
        action="accept", actor_type="human", reviewed_by="owner",
    ))
    assert accepted.status == ExperienceStatus.ACCEPTED
    assert accepted.reviewed_by == "owner"


def test_accepted_experience_is_retrieved_as_method_not_evidence(tmp_path) -> None:
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    record = repository.propose(candidate())
    repository.review(record.experience_id, ExperienceReviewRequest(
        action="accept", actor_type="human", reviewed_by="owner",
    ))

    matches = repository.retrieve_accepted("这两个对象怎么比较？")

    assert matches[0]["experience_id"] == record.experience_id
    assert matches[0]["not_evidence"] is True
    assert "final_answer" not in matches[0]


def test_run_ledger_is_separate_and_feedback_can_create_candidate(tmp_path) -> None:
    ledger = ResearchRunLedger(tmp_path / "runs.sqlite3")
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    run = ledger.record(ResearchRunCreate(
        request_id="req-1",
        question_text="怎么比较？",
        normalized_intent="stock_comparison",
        object_refs=["comparison"],
        evidence_pack_ids=["EP-AAAAAAAAAAAAAAAAAAAA"],
        final_answer="直接回答。",
        validation_report={"valid": True},
        source_freshness={"announcements": "2026-07-08"},
        agent_surface="codex_desktop",
    ))
    feedback = ExperienceFeedbackRequest(
        feedback_text="总览先说实质差异，不要先列字段。",
        category="presentation",
    )
    candidate_input = distill_feedback(run.run_id, feedback)
    assert candidate_input is not None
    experience = repository.propose(candidate_input)
    ledger.add_feedback(
        run.run_id,
        category=feedback.category,
        feedback_text=feedback.feedback_text,
        submitted_by=feedback.submitted_by,
    )
    ledger.link_experience(run.run_id, experience.experience_id, "candidate_source")

    listed = ledger.list()
    assert listed[0].question_text == "怎么比较？"
    assert listed[0].experience_candidate_ids == [experience.experience_id]


def test_routine_positive_feedback_does_not_create_experience() -> None:
    assert distill_feedback(
        "RUN-AAAAAAAAAAAAAAAAAAAAAAAA",
        ExperienceFeedbackRequest(feedback_text="这版可以", category="presentation"),
    ) is None
