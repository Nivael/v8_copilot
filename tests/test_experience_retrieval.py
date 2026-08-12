from __future__ import annotations

from experience_backfill import candidates as backfill_candidates
from experience_contract import ExperienceReviewRequest, ExperienceType
from experience_distiller import distill_run_feedback
from research_repository import ExperienceRepository, ResearchRunCreate, ResearchRunLedger


def _run(ledger: ResearchRunLedger, *, question: str, intent: str = "research_question"):
    return ledger.record(ResearchRunCreate(
        request_id=f"req-{intent}", question_text=question, normalized_intent=intent,
        evidence_pack_ids=["EP-AAAAAAAAAAAAAAAAAAAA"], final_answer="核对正式材料后给出判断。",
        validation_report={"valid": True}, source_freshness={"announcement": "2026-08-11"},
        agent_surface="codex_desktop",
    ))


def test_backfill_compresses_all_24_runs_into_nine_clusters() -> None:
    rows = backfill_candidates()
    source_runs = {ref for row in rows for ref in row.source_run_refs}

    assert len(rows) == 9
    assert len(source_runs) == 24
    assert all(row.topic_tags for row in rows)


def test_chinese_topic_retrieval_prefers_same_day_evidence_bundle(tmp_path) -> None:
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    bundle = next(row for row in backfill_candidates() if row.title.startswith("同日关联公告"))
    event_path = next(row for row in backfill_candidates() if row.title.startswith("组合事件先例"))
    for candidate in (bundle, event_path):
        record = repository.propose(candidate)
        repository.review(record.experience_id, ExperienceReviewRequest(
            action="accept", actor_type="human", reviewed_by="owner",
        ))

    matches = repository.retrieve_accepted("十份回复函附件之间是什么逻辑链，摘星条件满足了吗？")

    assert matches[0]["title"] == bundle.title
    assert "公告证据包" in matches[0]["topic_tags"]
    assert repository.retrieve_accepted("今天天气如何？") == []


def test_run_aware_feedback_chooses_entity_boundary_template(tmp_path) -> None:
    ledger = ResearchRunLedger(tmp_path / "runs.sqlite3")
    run = _run(
        ledger,
        question="母公司公开招募后，子公司和孙公司共同重整的历史案例有哪些？",
        intent="cross_entity_restructuring_sequence_price_precedent",
    )
    from experience_contract import ExperienceFeedbackRequest

    candidate = distill_run_feedback(run, ExperienceFeedbackRequest(
        feedback_text="这个主体划分方法值得复用", category="query_plan",
    ))

    assert candidate is not None
    assert candidate.experience_type == ExperienceType.QUERY_PLAN
    assert candidate.title == "跨层级重整比较先冻结上市主体边界"
    assert "主体边界" in candidate.topic_tags


def test_run_aware_error_feedback_uses_a_bounded_error_family(tmp_path) -> None:
    ledger = ResearchRunLedger(tmp_path / "runs.sqlite3")
    run = _run(ledger, question="子公司进入预重整是否等于上市公司已经受理重整？")
    from experience_contract import ExperienceFeedbackRequest

    candidate = distill_run_feedback(run, ExperienceFeedbackRequest(
        feedback_text="这里混淆了母公司和子公司的法律主体", category="anti_pattern",
    ))

    assert candidate is not None
    assert candidate.title == "混淆上市主体与关联主体的程序"
    assert candidate.validation_refs == ["regression:entity_scope_boundary"]


def test_feedback_write_is_idempotent(tmp_path) -> None:
    ledger = ResearchRunLedger(tmp_path / "runs.sqlite3")
    run = _run(ledger, question="当前阶段是什么？")

    first = ledger.add_feedback(
        run.run_id, category="presentation", feedback_text="先给判断", submitted_by="owner",
    )
    second = ledger.add_feedback(
        run.run_id, category="presentation", feedback_text="先给判断", submitted_by="owner",
    )

    assert first == second
    assert ledger.get(run.run_id).feedback_count == 1
