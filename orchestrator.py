"""Deterministic W1 orchestration; LLM integration is injected later by W2."""
from __future__ import annotations

from uuid import uuid4

from api_contract import (
    ClaimBacking,
    GapDescriptor,
    QuestionInterpretation,
    ResearchRequest,
    ResearchResponse,
    ResearchStreamEvent,
    RouteDecision,
    SedimentationCandidate,
    VerifiedClaim,
)
from answer_engine import (
    AnswerCard,
    card_consolidation_checklist,
    card_control_structure_methodology,
    card_data_debt,
    card_next_node_gap,
    card_release_lens_evidence,
    card_st_status_timeline,
    card_two_week_move,
)
from core_router import decide_route, interpret_request


def _request_id(request: ResearchRequest) -> str:
    return request.request_id or f"req-{uuid4().hex}"


def _symbol(
    request: ResearchRequest,
    interpretation: QuestionInterpretation,
) -> str | None:
    if interpretation.object.kind == "stock":
        return interpretation.object.ref
    if request.context and request.context.symbol:
        return request.context.symbol
    return None


def _object_ref(interpretation: QuestionInterpretation) -> str:
    return f"{interpretation.object.kind}:{interpretation.object.ref}"


def _execute_answer(
    request: ResearchRequest,
    interpretation: QuestionInterpretation,
    route: RouteDecision,
) -> AnswerCard | None:
    rules = set(route.matched_rules)
    card: AnswerCard | None = None

    if route.route == "answer_query":
        if "restructuring_next_node_query" in rules:
            card = card_next_node_gap()
        elif "st_panel_two_week_distribution" in rules:
            card = card_two_week_move()
        elif "stock_st_status_timeline" in rules:
            symbol = _symbol(request, interpretation)
            if symbol:
                card = card_st_status_timeline(symbol)
    elif route.route == "answer_checklist" and "stock_observation_window_checklist" in rules:
        symbol = _symbol(request, interpretation)
        if symbol:
            card = card_consolidation_checklist(symbol)
    elif route.route == "answer_evidence":
        if "release_library_lens_detail" in rules:
            card = card_release_lens_evidence("RL-A-003")
        elif "calendar_regime_evidence_lenses" in rules:
            release_id = "RL-A-002" if any(
                term in request.question for term in ("8月", "11月", "八月", "十一月")
            ) else "RL-A-001"
            card = card_release_lens_evidence(release_id)
    elif route.route == "answer_methodology" and "control_structure_methodology" in rules:
        card = card_control_structure_methodology()
    elif route.route == "data_debt":
        refs = route.data_debt_refs
        if refs:
            card = card_data_debt(
                question=request.question,
                object_ref=_object_ref(interpretation),
                debt_refs=refs,
            )

    if card is not None:
        card.question = request.question
        card.validate()
    return card


def _verified_claims(card: AnswerCard | None) -> list[VerifiedClaim]:
    if card is None:
        return []
    return [
        VerifiedClaim(
            text=claim.text,
            claim_type=claim.claim_type,
            backing=ClaimBacking(kind=claim.backing.kind, ref=claim.backing.ref),
        )
        for claim in card.analysis_claims
    ]


def _gaps(card: AnswerCard | None, route: RouteDecision) -> list[GapDescriptor]:
    gaps: list[GapDescriptor] = []
    if card is not None:
        gaps.extend(
            GapDescriptor(
                kind="lens_gap",
                gap_id=gap.gap_id,
                description=gap.missing_for,
                refs=[gap.sediment_as],
            )
            for gap in card.lens_gap
        )
        gaps.extend(
            GapDescriptor(
                kind="data_debt",
                gap_id=f"data_debt_{row.debt_ref.lower().replace('-', '_')}",
                description=f"{row.gap}：影响{row.affects}",
                refs=[row.debt_ref],
            )
            for row in card.data_debt
        )
        return gaps

    if route.route == "clarify":
        description = "需要补充股票、事件或比较口径后再执行研究查询。"
    elif route.route == "refuse_or_rewrite":
        description = "该请求超出研究边界；可改问公开节点、历史分布或观察窗口。"
    elif route.route == "needs_review":
        description = "当前方法尚未冻结，需要先进入方法人审。"
    elif route.route == "data_debt":
        description = "当前缺口尚未分配正式数据债 id，不能生成 data-debt AnswerCard。"
    else:
        description = "当前路由尚无确定性执行器，已稳定降级并保留问题候选。"
    gaps.append(GapDescriptor(
        kind="execution_gap",
        gap_id=route.matched_rules[0] if route.matched_rules else "unhandled_route",
        description=description,
        refs=[*route.data_debt_refs, *route.question_card_refs],
    ))
    return gaps


def _sedimentation_candidates(route: RouteDecision) -> list[SedimentationCandidate]:
    candidates = [
        SedimentationCandidate(
            kind="question_card",
            ref=None if ref == "question_card:new" else ref,
            reason="路由要求保留问题或方法缺口。",
        )
        for ref in route.question_card_refs
    ]
    candidates.extend(
        SedimentationCandidate(
            kind="data_debt",
            ref=ref,
            reason="回答依赖当前不可用字段。",
        )
        for ref in route.data_debt_refs
    )
    if route.route == "data_debt" and not route.data_debt_refs:
        candidates.append(SedimentationCandidate(
            kind="data_debt",
            reason="需要 W0/W1 分配正式数据债 id 后才能生成 AnswerCard。",
        ))
    return candidates


def orchestrate_with_card(
    request: ResearchRequest,
) -> tuple[ResearchResponse, AnswerCard | None]:
    """Run deterministic research and retain the validated card for W2 composition."""
    interpretation = interpret_request(request)
    route = decide_route(request, interpretation)
    card = _execute_answer(request, interpretation, route)

    degraded_reasons: list[str] = []
    if request.llm_mode != "off":
        degraded_reasons.append("LLM adapter 尚未注入，已返回确定性结果。")

    response = ResearchResponse(
        request_id=_request_id(request),
        interpretation=interpretation,
        route=route,
        answer_card=card.to_dict() if card else None,
        claims=_verified_claims(card),
        gaps=_gaps(card, route),
        sedimentation_candidates=_sedimentation_candidates(route),
        degraded=bool(degraded_reasons),
        degraded_reasons=degraded_reasons,
        llm_used=False,
    )
    return response, card


def orchestrate(request: ResearchRequest) -> ResearchResponse:
    return orchestrate_with_card(request)[0]


def route_only(request: ResearchRequest) -> RouteDecision:
    return decide_route(request, interpret_request(request))


def stream_events(
    request: ResearchRequest,
    response: ResearchResponse,
) -> list[ResearchStreamEvent]:
    events: list[ResearchStreamEvent] = []

    def append(event: str, payload: dict) -> None:
        events.append(ResearchStreamEvent(
            request_id=response.request_id,
            sequence=len(events) + 1,
            event=event,  # type: ignore[arg-type]
            payload=payload,
        ))

    append("accepted", {"llm_mode": request.llm_mode})
    append("interpreted", response.interpretation.model_dump(mode="json"))
    append("routed", response.route.model_dump(mode="json"))
    if response.answer_card is not None:
        append("answer_card", response.answer_card)
    if response.claims:
        append("claim_block", {
            "claims": [claim.model_dump(mode="json") for claim in response.claims]
        })
    if response.degraded:
        append("degraded", {"reasons": response.degraded_reasons})
    append("completed", {
        "route": response.route.route,
        "has_answer_card": response.answer_card is not None,
        "claim_count": len(response.claims),
        "response": response.model_dump(mode="json"),
    })
    return events
