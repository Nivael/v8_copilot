from p8_backtest_v2_publish import build_final_report, render_html
from p8_gold_review_panel import MAX_BATCH, _eligible, _stratified_first, render_html as render_review_html
from p8_research import P8ResearchRepository, build_run


def _persist(repository, run_kind, record_type, payload):
    run = build_run(
        run_kind=run_kind, contract_version="test",
        start_date="2023-01-01", through="2025-12-31",
        source_run_ids=[], source_digests={}, record_payloads={record_type: [payload]},
    )
    repository.persist(run=run, records={record_type: [payload]})
    return run


def test_final_report_resolves_accumulation_only_after_basket(tmp_path) -> None:
    repository = P8ResearchRepository(tmp_path / "p8.sqlite3")
    rank = {
        "record_id": "rank", "signal_scorecards": [
            {"signal_family": "p8c_accumulation", "status": "supported_pending_basket"},
            {"signal_family": "p8a_p_star", "status": "unavailable"},
        ],
        "source_run_ids": [], "source_digests": {},
    }
    basket = {
        "record_id": "basket", "status": "supported", "positive_excess_year_count": 2,
        "overall_compounded_excess_st": .1, "top_two_removed_compounded_excess_st": .02,
        "persistent_lane_incremental_compounded_excess_st": .01,
        "per_year": [],
    }
    _persist(repository, "p8_backtest_v2_report", "p8_backtest_v2_report", rank)
    _persist(repository, "p8_walk_forward_basket_v2", "p8_walk_forward_basket_v2", basket)
    report = build_final_report(repository)
    accumulation = next(item for item in report["scorecards"] if item["signal_family"] == "p8c_accumulation")
    assert accumulation["status"] == "supported"
    assert "不构成交易建议" in render_html(report)


def test_gold_panel_is_capped_and_requires_completed_llm_with_spans() -> None:
    events = []
    for index in range(MAX_BATCH + 10):
        events.append({
            "event_id": f"E{index}", "symbol": f"{index:06d}",
            "available_as_of": f"202{index % 3 + 3}-01-02",
            "track": "judicial" if index % 2 else "plan",
            "process_direction": "advance", "old_equity_effect": "supportive",
            "llm_status": "completed", "evidence_status": "body_verified",
            "source_spans": [{"source_ref": f"A{index}", "excerpt": "法院裁定受理"}],
        })
    events.append({
        "event_id": "not-run", "llm_status": "not_run", "source_spans": [{}],
        "evidence_status": "body_verified",
    })
    eligible = _eligible(events)
    selected = _stratified_first(eligible, MAX_BATCH)
    assert len(selected) == MAX_BATCH
    assert all(item["llm_status"] == "completed" for item in selected)
    queue = {
        "review_session_id": "P8GOLD-TEST", "review_version": "test",
        "source_packet": "run", "card_count": 0, "cards": [],
        "empty_reason": "等待正文抽取",
    }
    panel = render_review_html(queue)
    assert "导出决定 JSON" in panel
    assert "等待正文抽取" in panel
