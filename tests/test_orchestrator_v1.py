from api_contract import ResearchRequest
from api_contract_v1 import ResearchResponseV1
from orchestrator import orchestrate
from orchestrator_v1 import enrich_response_v1, stream_events_v1


def response_v1(question: str, *, kind: str, ref: str) -> ResearchResponseV1:
    request = ResearchRequest(
        request_id="req-v1-test",
        question=question,
        object={"kind": kind, "ref": ref},
        llm_mode="off",
    )
    return enrich_response_v1(request, orchestrate(request))


def test_query_response_exposes_template_and_question_cards() -> None:
    response = response_v1(
        "重整投资人公开招募后，下一个公告节点通常多久？",
        kind="episode_type",
        ref="restructuring_investor_recruitment",
    )

    assert response.query_template_id == "QT-001"
    assert {card.id for card in response.question_cards} == {
        "QC-20260710-009", "QC-20260710-010"
    }
    assert all(card.status == "answerable" for card in response.question_cards)
    assert {item.kind for item in response.navigation_refs} >= {
        "lens", "provenance"
    }


def test_data_debt_response_has_typed_drawer_candidates() -> None:
    response = response_v1(
        "同一重整招募问题按省份分层如何？",
        kind="cohort",
        ref="restructuring_investor_recruitment",
    )

    assert response.query_template_id == "QT-005"
    assert response.question_cards[0].debt_ref == "D-051A"
    assert response.data_debt_candidates[0].debt_ref == "D-051A"
    assert any(item.kind == "data_debt" for item in response.navigation_refs)


def test_unknown_question_produces_full_question_card_object() -> None:
    response = response_v1(
        "当前没有覆盖的新问题",
        kind="unknown",
        ref="unknown",
    )

    assert response.answer_card is None
    assert len(response.question_cards) == 1
    assert response.question_cards[0].status == "needs_review"
    assert response.question_cards[0].id.startswith("QC-CAND-")


def test_v1_stream_completed_event_contains_v1_response() -> None:
    request = ResearchRequest(
        request_id="req-v1-stream",
        question="沐邦为什么 ST？",
        object={"kind": "stock", "ref": "603398"},
        llm_mode="off",
    )
    response = enrich_response_v1(request, orchestrate(request))
    events = stream_events_v1(request, response)

    assert events[-1].payload["response"]["contract_version"] == (
        "v8_copilot_api_contract_v1"
    )


def test_event_and_debt_responses_cover_all_navigation_kinds() -> None:
    event_request = ResearchRequest.model_validate({
        "request_id": "req-v1-event",
        "question": "这个节点前后发生了什么？",
        "object": {"kind": "stock_event", "ref": "announcement:1221766612"},
        "context": {"symbol": "603398", "selected_episode": "restructuring_path",
                    "selected_lenses": ["RL-A-003"], "selected_event": {
            "event_id": "announcement:1221766612",
            "date": "2025-11-25",
            "title": "控股股东相关公告",
        }},
        "llm_mode": "off",
    })
    event_response = enrich_response_v1(event_request, orchestrate(event_request))
    debt_response = response_v1(
        "同一重整招募问题按省份分层如何？",
        kind="cohort",
        ref="restructuring_investor_recruitment",
    )

    kinds = {item.kind for item in event_response.navigation_refs}
    kinds.update(item.kind for item in debt_response.navigation_refs)
    assert kinds == {
        "stock", "date", "announcement", "episode", "lens", "provenance",
        "data_debt",
    }
    assert any(
        item.source_kind == "answer_row" and item.kind == "announcement"
        for item in event_response.navigation_refs
    )
    answer_row_link = next(
        item for item in event_response.navigation_refs
        if item.source_kind == "answer_row" and item.kind == "announcement"
    )
    assert "date=" in answer_row_link.href
    assert "title=" in answer_row_link.href
    provenance_link = next(
        item for item in event_response.navigation_refs
        if item.kind == "provenance"
    )
    assert "object_kind=stock_event" in provenance_link.href
    assert "event=announcement%3A1221766612" in provenance_link.href
    assert "episode=restructuring_path" in provenance_link.href
    assert "lens=RL-A-003" in provenance_link.href


def test_boundary_request_sediments_only_the_safe_rewrite() -> None:
    response = response_v1(
        "这票目标价看到多少？",
        kind="stock",
        ref="603398",
    )

    assert len(response.question_cards) == 1
    assert response.question_cards[0].status == "answerable"
    assert response.question_cards[0].view == "checklist"
    assert "目标价" not in response.question_cards[0].question
    assert response.question_cards[0].question == "603398 接下来该看哪些窗口？"

    rewritten_request = ResearchRequest(
        question=response.question_cards[0].question,
        object={"kind": "stock", "ref": "603398"},
        llm_mode="off",
    )
    rewritten_response = orchestrate(rewritten_request)
    assert rewritten_response.route.route == "answer_checklist"
    assert rewritten_response.answer_card is not None


def test_st_only_distribution_does_not_inherit_microcap_debt() -> None:
    response = response_v1(
        "ST 面板自身两周涨跌分布如何？",
        kind="universe",
        ref="ST panel",
    )

    assert response.answer_card is not None
    assert response.answer_card["data_debt_refs"] == []
    assert response.question_cards[0].status == "answerable"
    assert response.question_cards[0].debt_ref is None


def test_unresolved_event_is_clarify_and_not_answerable_question_card() -> None:
    request = ResearchRequest.model_validate({
        "question": "这个节点前后发生了什么？",
        "object": {"kind": "stock", "ref": "603398"},
        "context": {"symbol": "603398", "selected_event": {
            "event_id": "announcement:FAKE",
            "date": "2025-11-25",
            "title": "虚构公告",
        }},
        "llm_mode": "off",
    })
    response = enrich_response_v1(request, orchestrate(request))

    assert response.route.route == "clarify"
    assert response.answer_card is None
    assert response.question_cards[0].status == "needs_review"
