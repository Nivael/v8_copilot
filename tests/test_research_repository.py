from __future__ import annotations

import hashlib
import json

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


def evidence_pack_payload(**content) -> dict:
    digest = hashlib.sha256(json.dumps(
        content, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")).hexdigest()
    return {**content, "pack_id": f"EP-{digest[:20].upper()}", "pack_digest": digest}


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


def test_only_human_or_owner_policy_can_accept_experience(tmp_path) -> None:
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

    policy_record = repository.propose(candidate(source="RUN-BBBBBBBBBBBBBBBBBBBBBBBB").model_copy(
        update={"title": "主回答先给人话判断"}
    ))
    policy_accepted = repository.review(policy_record.experience_id, ExperienceReviewRequest(
        action="accept", actor_type="owner_policy",
        reviewed_by="owner_preapproved_replicated_v1",
    ))
    assert policy_accepted.status == ExperienceStatus.ACCEPTED


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


def test_run_ledger_persists_immutable_evidence_pack_and_decision_audit(tmp_path) -> None:
    ledger = ResearchRunLedger(tmp_path / "runs.sqlite3")
    pack = evidence_pack_payload(rows=[{"row_id": "row-1", "value": "fact"}])
    stored = ledger.store_evidence_pack(pack)
    run = ledger.record(ResearchRunCreate(
        request_id="req-audit",
        question_text="当前阶段是什么？",
        normalized_intent="stage",
        object_refs=["603398"],
        evidence_pack_ids=[stored.pack_id],
        final_answer="当前公开阶段可确认。",
        research_draft={"narrative": {"direct_answer": {"text": "当前公开阶段可确认。"}}},
        decision_audit={
            "weighting_method": "ordinal_evidence_weighting_v0",
            "judgment": "当前公开阶段可确认。",
            "judgment_backing": [{"kind": "query_row", "ref": "row-1"}],
            "confidence": "high",
            "factors": [],
            "alternatives": [],
            "not_hidden_chain_of_thought": True,
        },
        validation_report={"valid": True},
        source_freshness={"announcements": "2024-01-03"},
        agent_surface="codex_desktop",
    ))

    assert ledger.get_evidence_pack(stored.pack_id).payload["rows"][0]["row_id"] == "row-1"
    assert ledger.get(run.run_id).decision_audit["confidence"] == "high"
    assert ledger.list()[0].research_draft["narrative"]["direct_answer"]["text"]

    changed = {**pack, "rows": [{"row_id": "row-1", "value": "tampered"}]}
    with pytest.raises(ValueError, match="不匹配"):
        ledger.store_evidence_pack(changed)
