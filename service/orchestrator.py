from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from answer_engine import (
    AnswerCard,
    card_calendar_regime_evidence,
    card_consolidation_checklist,
    card_next_node_gap,
    card_province_mapping_debt,
    card_st_status_timeline,
    card_two_week_move,
)
from contracts.v8_copilot_api_contract_v0.models import (
    Degradation,
    FallbackResult,
    QuestionInterpretation,
    ResearchObject,
    ResearchRequest,
    ResearchResponse,
    ResearchStreamEvent,
    RouteDecision,
    ValidatedClaim,
)
from evals.deterministic_router_v0 import RoutePrediction, route_question
from service.providers import (
    ClaimProvider,
    InterpretationProvider,
    backing_catalog,
    validate_claims,
)


@dataclass(frozen=True)
class RoutedRequest:
    interpretation: QuestionInterpretation
    route: RouteDecision
    degradations: tuple[Degradation, ...] = ()


def _normalized(text: str) -> str:
    return "".join(text.lower().split())


def _research_object(request: ResearchRequest) -> ResearchObject:
    if request.object is not None:
        return request.object
    if request.context and request.context.symbol:
        return ResearchObject(kind="stock", ref=request.context.symbol)
    symbol_match = re.search(r"(?<!\d)(\d{6})(?!\d)", request.question)
    if symbol_match:
        return ResearchObject(kind="stock", ref=symbol_match.group(1))
    if "沐邦" in request.question:
        return ResearchObject(kind="stock", ref="603398", display_name="沐邦")
    return ResearchObject(kind="unknown")


def _interpret(request: ResearchRequest) -> QuestionInterpretation:
    text = _normalized(request.question)
    obj = _research_object(request)
    dimensions = [
        label
        for term, label in (
            ("公告", "公告"),
            ("价格", "价格"),
            ("省份", "省份"),
            ("阶段", "阶段"),
            ("股东", "股东"),
            ("时间", "时间"),
        )
        if term in text
    ]
    topics = [
        label
        for term, label in (
            ("重整", "重整"),
            ("st", "ST 生命周期"),
            ("日历", "日历效应"),
            ("月份", "日历效应"),
            ("控制权", "控制权"),
            ("拍卖", "股东行为"),
            ("两周", "价格行为"),
            ("平台", "价格行为"),
        )
        if term in text
    ]
    topics = list(dict.fromkeys(topics))
    ambiguities = []
    if obj.kind == "unknown" and any(term in text for term in ("它", "这个股票", "这只票")):
        ambiguities.append("缺少可绑定的股票或事件对象")

    if "相似案例" in text or "哪些case" in text:
        intent = "similar_case_search"
    elif "为什么st" in text:
        intent = "st_status_timeline"
    elif "窗口" in text or "平台" in text:
        intent = "stock_observation_window"
    elif "下一个公告节点" in text or "进入下一阶段" in text:
        intent = "event_timing_query"
    elif "证据" in text or "历史先验" in text:
        intent = "evidence_review"
    else:
        intent = "open_research_question"

    return QuestionInterpretation(
        request_id=request.request_id,
        object=obj,
        intent=intent,
        time_scope=request.context,
        requested_dimensions=dimensions,
        ambiguities=ambiguities,
        candidate_topics=topics,
    )


def _safe_note(prediction: RoutePrediction) -> str:
    if prediction.predicted_route == "refuse_or_rewrite":
        return "该请求超出研究产品边界，已改写为证据问题。"
    return prediction.route_note


def _route(request: ResearchRequest, interpretation: QuestionInterpretation) -> RouteDecision:
    prediction = route_question({
        "user_question": request.question,
        "object": interpretation.object.model_dump(mode="json"),
    })
    return RouteDecision(
        request_id=request.request_id,
        route=prediction.predicted_route,
        status=prediction.expected_status,
        view=prediction.expected_view,
        required_lens_behavior=prediction.required_lens_behavior,
        data_debt_refs=prediction.required_data_debt_refs,
        question_card_refs=prediction.required_question_card_refs,
        matched_rules=prediction.matched_rules,
        note=_safe_note(prediction),
    )


def _symbol(request: ResearchRequest, interpretation: QuestionInterpretation) -> str | None:
    if interpretation.object.kind == "stock" and interpretation.object.ref:
        return interpretation.object.ref
    return request.context.symbol if request.context else None


def _real_card(
    request: ResearchRequest,
    interpretation: QuestionInterpretation,
    route: RouteDecision,
) -> AnswerCard | None:
    if route.route in {"clarify", "needs_review", "lens_gap", "refuse_or_rewrite"}:
        return None

    text = _normalized(request.question)
    rules = set(route.matched_rules)
    symbol = _symbol(request, interpretation)

    if "restructuring_next_node_query" in rules:
        return card_next_node_gap()
    if "stock_observation_window_checklist" in rules and symbol:
        return card_consolidation_checklist(symbol)
    if "stock_st_status_timeline" in rules and symbol:
        return card_st_status_timeline(symbol)
    if "calendar_regime_evidence_lenses" in rules:
        release_id = "RL-A-002" if "rl-a-002" in text else "RL-A-001"
        return card_calendar_regime_evidence(release_id)
    if "release_library_lens_detail" in rules:
        return card_calendar_regime_evidence("RL-A-003")
    if route.data_debt_refs == ["D-051A"]:
        return card_province_mapping_debt()
    if "两周" in text and any(term in text for term in ("涨跌", "异动", "大盘", "微盘", "st")):
        return card_two_week_move()
    return None


def _fallback(route: RouteDecision) -> FallbackResult:
    common = {
        "question_card_refs": route.question_card_refs,
        "data_debt_refs": route.data_debt_refs,
    }
    if route.route == "refuse_or_rewrite":
        return FallbackResult(
            kind="refuse",
            title="请求已改写为研究问题",
            message="本系统只提供历史证据、观察窗口和数据缺口，不提供交易操作判断。",
            suggested_question="这只股票当前有哪些关键事件、历史路径、证据和数据缺口？",
            **common,
        )
    if route.route == "clarify":
        return FallbackResult(
            kind="clarify",
            title="需要补充研究对象或口径",
            message="当前问题缺少可绑定的股票、事件节点或影响口径。",
            suggested_question="请补充股票代码、事件节点和希望观察的时间窗口。",
            **common,
        )
    if route.route == "data_debt":
        return FallbackResult(
            kind="data_debt",
            title="当前字段不足",
            message="请求所需字段尚未冻结或覆盖不足，缺口已保留，不提供推断值。",
            **common,
        )
    if route.route == "needs_review":
        return FallbackResult(
            kind="needs_review",
            title="需要先冻结方法",
            message="该问题依赖尚未冻结的方法或人审边界，已进入待审候选。",
            **common,
        )
    return FallbackResult(
        kind="lens_gap",
        title="当前没有可执行的证据路径",
        message="确定性执行器或可用 lens 尚未覆盖该问题，已保留为待验证候选。",
        **common,
    )


class ResearchOrchestrator:
    """Deterministic authority with an optional, non-authoritative claim provider."""

    def __init__(
        self,
        claim_provider: ClaimProvider | None = None,
        interpretation_provider: InterpretationProvider | None = None,
    ):
        self.claim_provider = claim_provider
        self.interpretation_provider = interpretation_provider

    def route(self, request: ResearchRequest) -> RoutedRequest:
        interpretation = _interpret(request)
        degradations: list[Degradation] = []
        if request.llm_mode == "auto" and self.interpretation_provider is not None:
            try:
                interpretation = self.interpretation_provider.interpret(
                    request=request,
                    deterministic=interpretation,
                )
            except Exception:
                degradations.append(Degradation(
                    code="llm_output_rejected",
                    message="LLM 问题解释未通过契约，已使用确定性解释。",
                ))
        return RoutedRequest(
            interpretation=interpretation,
            route=_route(request, interpretation),
            degradations=tuple(degradations),
        )

    def _answer_routed(self, request: ResearchRequest, routed: RoutedRequest) -> ResearchResponse:
        card = _real_card(request, routed.interpretation, routed.route)
        if card is not None:
            card.question = request.question
            card.validate()
        answer_card = card.to_dict() if card is not None else None
        fallback = None if answer_card is not None else _fallback(routed.route)
        claims: list[ValidatedClaim] = []
        degradations: list[Degradation] = list(routed.degradations)

        if answer_card is not None and request.llm_mode == "auto":
            if self.claim_provider is None or not self.claim_provider.available:
                degradations.append(Degradation(
                    code="llm_unavailable",
                    message="LLM 叙述层不可用，已返回确定性 AnswerCard。",
                ))
            else:
                try:
                    claims = self.claim_provider.compose(
                        request=request,
                        answer_card=answer_card,
                        backing_catalog=backing_catalog(answer_card),
                    )
                    validate_claims(answer_card, claims)
                except Exception:
                    claims = []
                    degradations.append(Degradation(
                        code="llm_output_rejected",
                        message="LLM 输出未通过 backing 校验，已仅返回确定性 AnswerCard。",
                    ))

        return ResearchResponse(
            request_id=request.request_id,
            status="degraded" if degradations else "complete",
            interpretation=routed.interpretation,
            route=routed.route,
            answer_card=answer_card,
            fallback=fallback,
            claims=claims,
            degradations=degradations,
        )

    def answer(self, request: ResearchRequest) -> ResearchResponse:
        return self._answer_routed(request, self.route(request))

    def events(self, request: ResearchRequest) -> Iterator[ResearchStreamEvent]:
        sequence = 1
        yield ResearchStreamEvent(
            request_id=request.request_id,
            sequence=sequence,
            event="accepted",
            payload={"llm_mode": request.llm_mode},
        )
        try:
            routed = self.route(request)
            sequence += 1
            yield ResearchStreamEvent(
                request_id=request.request_id,
                sequence=sequence,
                event="interpreted",
                payload={"interpretation": routed.interpretation.model_dump(mode="json")},
            )
            sequence += 1
            yield ResearchStreamEvent(
                request_id=request.request_id,
                sequence=sequence,
                event="routed",
                payload={"route": routed.route.model_dump(mode="json")},
            )
            response = self._answer_routed(request, routed)
            if response.answer_card is not None:
                sequence += 1
                yield ResearchStreamEvent(
                    request_id=request.request_id,
                    sequence=sequence,
                    event="answer_card",
                    payload={"answer_card": response.answer_card},
                )
            for claim in response.claims:
                sequence += 1
                yield ResearchStreamEvent(
                    request_id=request.request_id,
                    sequence=sequence,
                    event="claim_block",
                    payload={"claim": claim.model_dump(mode="json")},
                )
            for degradation in response.degradations:
                sequence += 1
                yield ResearchStreamEvent(
                    request_id=request.request_id,
                    sequence=sequence,
                    event="degraded",
                    payload={"degradation": degradation.model_dump(mode="json")},
                )
            sequence += 1
            yield ResearchStreamEvent(
                request_id=request.request_id,
                sequence=sequence,
                event="completed",
                payload={"response": response.model_dump(mode="json")},
            )
        except Exception:
            sequence += 1
            yield ResearchStreamEvent(
                request_id=request.request_id,
                sequence=sequence,
                event="error",
                payload={
                    "code": "research_execution_failed",
                    "message": "确定性研究执行失败；未返回未经验证的结果。",
                },
            )
