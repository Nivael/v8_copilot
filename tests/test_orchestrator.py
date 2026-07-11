from api_contract import ResearchObject, ResearchRequest
from orchestrator import orchestrate, route_only, stream_events


def request(question: str, *, kind: str, ref: str, llm_mode: str = "off") -> ResearchRequest:
    return ResearchRequest.model_validate({
        "request_id": "req-test",
        "question": question,
        "object": {"kind": kind, "ref": ref},
        "llm_mode": llm_mode,
    })


def test_restructuring_question_executes_real_answer_card() -> None:
    response = orchestrate(request(
        "重整投资人公开招募后，下一个公告节点通常多久？",
        kind="episode_type",
        ref="restructuring_investor_recruitment",
    ))

    assert response.route.route == "answer_query"
    assert response.answer_card is not None
    assert response.answer_card["view"] == "query"
    assert [row["中位(天)"] for row in response.answer_card["body_rows"]] == [4, 10, 14]
    assert response.llm_used is False
    assert response.degraded is False


def test_evidence_question_uses_frozen_lens() -> None:
    response = orchestrate(request(
        "日历月份效应的证据等级和反例是什么？",
        kind="lens_cluster",
        ref="C03",
    ))

    assert response.route.route == "answer_evidence"
    assert response.answer_card is not None
    assert response.answer_card["view"] == "evidence"
    assert response.answer_card["lens_invocations"][0]["release_id"] == "RL-A-001"


def test_c17_evidence_question_uses_release_record_a003() -> None:
    response = orchestrate(request(
        "C17 均线回踩 lens 的证据等级、N 和反例是什么？",
        kind="lens",
        ref="RL-A-003",
    ))

    assert response.route.route == "answer_evidence"
    assert response.answer_card is not None
    assert response.answer_card["lens_invocations"][0]["release_id"] == "RL-A-003"


def test_control_question_returns_methodology_not_evidence() -> None:
    response = orchestrate(request(
        "控股股东司法拍卖和控制权变化应该怎么观察？",
        kind="stock",
        ref="603398",
    ))

    assert response.route.route == "answer_methodology"
    assert response.answer_card is not None
    assert response.answer_card["view"] == "methodology"
    assert response.answer_card["evidence_grade"] == "context_only"


def test_registered_data_debt_builds_valid_answer_card() -> None:
    response = orchestrate(request(
        "同一重整招募问题按省份分层如何？",
        kind="cohort",
        ref="restructuring_investor_recruitment",
    ))

    assert response.route.route == "data_debt"
    assert response.answer_card is not None
    assert response.answer_card["data_debt_refs"] == ["D-051A"]


def test_shareholder_count_uses_existing_d021_debt() -> None:
    response = orchestrate(request(
        "沐邦 ST 前后股东人数变化是否异常？",
        kind="stock",
        ref="603398",
    ))

    assert response.route.route == "data_debt"
    assert response.route.data_debt_refs == ["D-021"]
    assert response.answer_card is not None
    assert response.answer_card["data_debt_refs"] == ["D-021"]


def test_unassigned_data_gap_returns_stable_response_without_card() -> None:
    response = orchestrate(request(
        "董秘语气和论坛热度能不能解释沐邦这段平台？",
        kind="stock",
        ref="603398",
    ))

    assert response.route.route == "data_debt"
    assert response.answer_card is None
    assert response.degraded is False
    assert response.gaps[0].kind == "execution_gap"
    assert any(candidate.kind == "data_debt" for candidate in response.sedimentation_candidates)


def test_unknown_question_stably_degrades_to_lens_gap() -> None:
    response = orchestrate(request(
        "一个当前完全没有覆盖的新研究问题",
        kind="cluster",
        ref="new_topic",
    ))

    assert response.route.route == "lens_gap"
    assert response.answer_card is None
    assert response.gaps[0].gap_id == "deterministic_unknown_fallback"


def test_boundary_request_has_safe_rewrite_reason() -> None:
    response = orchestrate(request(
        "这票目标价看到多少？",
        kind="stock",
        ref="603398",
    ))

    assert response.route.route == "refuse_or_rewrite"
    assert response.answer_card is None
    assert response.route.reason == "该请求属于行动指令边界，已改写为可验证的研究问题。"


def test_auto_llm_mode_returns_deterministic_result_with_degraded_marker() -> None:
    response = orchestrate(request(
        "沐邦接下来该看哪些窗口？",
        kind="stock",
        ref="603398",
        llm_mode="auto",
    ))

    assert response.answer_card is not None
    assert response.llm_used is False
    assert response.degraded is True
    assert "LLM adapter 尚未注入" in response.degraded_reasons[0]


def test_stream_contains_only_domain_events_and_verified_claims() -> None:
    research_request = request(
        "日历月份效应的证据等级和反例是什么？",
        kind="lens_cluster",
        ref="C03",
    )
    response = orchestrate(research_request)
    events = stream_events(research_request, response)

    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    assert "answer_card" in [event.event for event in events]
    assert "claim_block" in [event.event for event in events]
    assert all("token" not in event.event and "delta" not in event.event for event in events)
    claim_event = next(event for event in events if event.event == "claim_block")
    assert claim_event.payload["claims"] == [
        claim.model_dump(mode="json") for claim in response.claims
    ]


def test_route_only_does_not_query_answer_data() -> None:
    route = route_only(request(
        "那它呢？",
        kind="unknown",
        ref="pronoun",
    ))

    assert route.route == "clarify"


def test_selected_event_executes_stock_event_window_template() -> None:
    research_request = ResearchRequest.model_validate({
        "request_id": "req-event-window",
        "question": "这个节点前后发生了什么？",
        "object": {"kind": "stock", "ref": "603398"},
        "context": {
            "symbol": "603398",
            "selected_event": {
                "event_id": "announcement:1221766612",
                "date": "2025-11-25",
                "title": "控股股东相关公告",
            },
        },
        "llm_mode": "off",
    })

    response = orchestrate(research_request)

    assert response.route.route == "answer_query"
    assert response.answer_card is not None
    assert response.answer_card["body_rows"][0]["事件编号"] == "announcement:1221766612"
    assert response.answer_card["body_rows"][0]["标题"] != "控股股东相关公告"
    assert response.answer_card["source_freshness"]["price_data_as_of"] == "2026-06-26"


def test_unresolved_client_event_cannot_generate_an_answer_card() -> None:
    research_request = ResearchRequest.model_validate({
        "request_id": "req-fake-event",
        "question": "这个节点前后发生了什么？",
        "object": {"kind": "stock", "ref": "603398"},
        "context": {"symbol": "603398", "selected_event": {
            "event_id": "announcement:FAKE",
            "date": "2025-11-25",
            "title": "虚构公告",
        }},
        "llm_mode": "off",
    })

    response = orchestrate(research_request)

    assert response.route.route == "clarify"
    assert response.route.status == "clarify"
    assert response.answer_card is None
    assert response.gaps[0].kind == "execution_gap"


def test_missing_stock_status_returns_stable_empty_timeline() -> None:
    response = orchestrate(request(
        "999999 为什么 ST？",
        kind="stock",
        ref="999999",
    ))

    assert response.answer_card is not None
    assert response.answer_card["body_rows"] == [
        {"row_id": "st_interval_missing", "状态": "当前快照无 ST 生命周期记录"}
    ]


def test_missing_stock_cannot_generate_checklist_or_false_provenance() -> None:
    response = orchestrate(request(
        "999999 接下来该看哪些窗口？",
        kind="stock",
        ref="999999",
    ))

    assert response.route.route == "clarify"
    assert response.route.status == "clarify"
    assert response.answer_card is None
