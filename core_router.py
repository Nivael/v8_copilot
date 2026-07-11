"""Deterministic interpretation and final routing for the W1 API."""
from __future__ import annotations

from api_contract import (
    QuestionInterpretation,
    ResearchObject,
    ResearchRequest,
    RouteDecision,
)
from evals.deterministic_router_v0 import route_question
from stock_resolver import resolve_stock


def _infer_object(request: ResearchRequest) -> ResearchObject:
    if request.object is not None:
        return request.object
    if request.context and request.context.symbol:
        return ResearchObject(kind="stock", ref=request.context.symbol)
    resolution = resolve_stock(request.question)
    if resolution:
        return ResearchObject(kind="stock", ref=resolution.symbol)
    return ResearchObject(kind="unknown", ref="unknown")


def interpret_request(request: ResearchRequest) -> QuestionInterpretation:
    """Extract request shape only; this function does not query research data."""
    question = "".join(request.question.lower().split())
    research_object = _infer_object(request)

    intent = "research_question"
    if any(term in question for term in ("能买吗", "目标价", "仓位", "买入", "卖出")):
        intent = "trading_advice_boundary"
    elif any(term in question for term in ("多久", "下一个节点", "下一阶段")):
        intent = "event_timing"
    elif any(term in question for term in ("哪些月份", "月份效应", "证据等级", "反例")):
        intent = "evidence_review"
    elif any(term in question for term in ("哪些窗口", "爆发点", "平台")):
        intent = "observation_checklist"
    elif any(term in question for term in ("相似案例", "哪些case", "哪些案例")):
        intent = "similarity_review"
    elif any(term in question for term in ("为什么st", "为什么被st", "为何st", "st原因")):
        intent = "st_status_timeline"

    dimensions: list[str] = []
    dimension_terms = {
        "省份": "province",
        "阶段": "stage",
        "相对大盘": "market_relative",
        "微盘": "market_cap_cohort",
        "股东人数": "shareholder_count",
        "股权": "equity",
        "股本": "capital_structure",
        "公告": "announcement",
        "价格": "price",
        "股价": "price",
        "控制权": "control_structure",
    }
    for term, dimension in dimension_terms.items():
        if term in question:
            dimensions.append(dimension)

    candidate_topics: list[str] = []
    topic_terms = {
        "重整": "restructuring",
        "st": "st_lifecycle",
        "月份": "calendar_regime",
        "均线": "price_behavior",
        "控股股东": "control_structure",
        "拍卖": "control_structure",
    }
    for term, topic in topic_terms.items():
        if term in question and topic not in candidate_topics:
            candidate_topics.append(topic)

    ambiguities: list[str] = []
    if research_object.kind == "unknown":
        ambiguities.append("缺少可绑定的股票、事件或 cohort 对象")
    if "影响大吗" in question:
        ambiguities.append("缺少影响指标和比较窗口定义")

    return QuestionInterpretation(
        object=research_object,
        intent=intent,
        time_range=request.context.date_range if request.context else None,
        dimensions=dimensions,
        ambiguities=ambiguities,
        candidate_topics=candidate_topics,
    )


def decide_route(
    request: ResearchRequest,
    interpretation: QuestionInterpretation,
) -> RouteDecision:
    prediction = route_question({
        "user_question": request.question,
        "object": interpretation.object.model_dump(mode="json"),
    })
    reason = prediction.route_note
    if prediction.predicted_route == "refuse_or_rewrite":
        reason = "该请求属于行动指令边界，已改写为可验证的研究问题。"
    data_debt_refs = list(prediction.required_data_debt_refs)
    if (
        "missing_shareholder_count_full_coverage" in prediction.matched_rules
        and "D-021" not in data_debt_refs
    ):
        data_debt_refs.append("D-021")
    return RouteDecision(
        route=prediction.predicted_route,
        status=prediction.expected_status,
        view=prediction.expected_view,
        reason=reason,
        matched_rules=prediction.matched_rules,
        data_debt_refs=data_debt_refs,
        question_card_refs=prediction.required_question_card_refs,
        required_lens_behavior=prediction.required_lens_behavior,
    )
