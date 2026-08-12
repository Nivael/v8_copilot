from __future__ import annotations

from experience_backfill import candidates as backfill_candidates
from experience_review import (
    ExperienceReviewDecision,
    ExperienceReviewDecisionExport,
    ExperienceReviewQueue,
    build_review_queue,
    validate_decision_export,
)
from research_repository import ExperienceRepository, ResearchRunCreate, ResearchRunLedger


def test_review_queue_is_clustered_bounded_and_has_machine_proposals(tmp_path) -> None:
    ledger = ResearchRunLedger(tmp_path / "runs.sqlite3")
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    run = ledger.record(ResearchRunCreate(
        request_id="req-review", question_text="全部回复函之间是什么逻辑链？",
        normalized_intent="announcement_fact_query",
        evidence_pack_ids=["EP-AAAAAAAAAAAAAAAAAAAA"], final_answer="这些附件是一套证据包。",
        validation_report={"valid": True}, source_freshness={"announcement": "2026-08-11"},
        agent_surface="codex_desktop",
    ))
    candidate = next(row for row in backfill_candidates() if row.title.startswith("同日关联公告"))
    repository.propose(candidate.model_copy(update={"source_run_refs": [run.run_id]}))

    queue = build_review_queue(repository, ledger, limit=10)

    assert len(queue.cards) == 1
    assert queue.max_pending == 10
    assert queue.cards[0].recommendation == "accept_suggested"
    assert queue.cards[0].evidence_examples[0].run_id == run.run_id
    assert len(queue.cards[0].options) == 4


def test_decision_export_round_trip_is_idempotent(tmp_path) -> None:
    ledger = ResearchRunLedger(tmp_path / "runs.sqlite3")
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    run = ledger.record(ResearchRunCreate(
        request_id="req-review", question_text="全部公告是什么逻辑链？",
        normalized_intent="announcement_fact_query",
        evidence_pack_ids=["EP-AAAAAAAAAAAAAAAAAAAA"], final_answer="先组成证据包。",
        validation_report={"valid": True}, source_freshness={"announcement": "2026-08-11"},
        agent_surface="codex_desktop",
    ))
    candidate = next(row for row in backfill_candidates() if row.title.startswith("同日关联公告"))
    record = repository.propose(candidate.model_copy(update={"source_run_refs": [run.run_id]}))
    queue = build_review_queue(repository, ledger)
    repository.save_review_queue(queue.model_dump(mode="json"))
    card = queue.cards[0]
    decision = ExperienceReviewDecision(
        card_id=card.card_id, decision="defer", affected_area=card.affected_area,
        recommended_decision=card.recommendation, question=card.decision_requested,
    )
    export = ExperienceReviewDecisionExport(
        review_session_id=queue.review_session_id, exported_at="2026-08-12T00:00:00Z",
        source_packet=queue.source_packet, decisions=[decision],
    )

    validate_decision_export(
        ExperienceReviewQueue.model_validate(repository.get_review_queue(queue.review_session_id)), export,
    )
    payload = decision.model_dump(mode="json")
    assert repository.record_review_decision(queue.review_session_id, record.experience_id, payload) is True
    assert repository.record_review_decision(queue.review_session_id, record.experience_id, payload) is False
