"""Deterministic interpretation and final routing for the W1 API."""
from __future__ import annotations

from api_contract import (
    QuestionInterpretation,
    ResearchObject,
    ResearchRequest,
    RouteDecision,
)
from evals.deterministic_router_v0 import route_question
from stock_resolver import resolve_stock, resolve_stocks
from trading_boundary import is_trading_advice_request


def _infer_object(request: ResearchRequest) -> ResearchObject:
    if request.object is not None:
        return request.object
    if request.context and request.context.symbol:
        return ResearchObject(kind="stock", ref=request.context.symbol)
    resolutions = resolve_stocks(request.question)
    if len(resolutions) >= 2:
        return ResearchObject(
            kind="cohort",
            ref="comparison:" + ",".join(item.symbol for item in resolutions),
        )
    resolution = resolve_stock(request.question)
    if resolution:
        return ResearchObject(kind="stock", ref=resolution.symbol)
    return ResearchObject(kind="unknown", ref="unknown")


def interpret_request(request: ResearchRequest) -> QuestionInterpretation:
    """Extract request shape only; this function does not query research data."""
    question = "".join(request.question.lower().split())
    research_object = _infer_object(request)

    intent = "research_question"
    if is_trading_advice_request(request.question):
        intent = "trading_advice_boundary"
    elif research_object.kind == "cohort" and research_object.ref.startswith("comparison:"):
        intent = "stock_comparison"
    elif (
        any(term in question for term in ("先例", "历史上", "出现过"))
        and any(term in question for term in ("截止前", "截止日", "报名期限"))
    ):
        intent = "historical_event_window_precedent"
    elif any(term in question for term in ("多久", "下一个节点", "下一阶段")):
        intent = "event_timing"
    elif any(term in question for term in ("哪些月份", "月份效应", "证据等级", "反例")):
        intent = "evidence_review"
    elif any(term in question for term in (
        "说了什么", "公告内容", "为什么被申请", "是否已经", "有没有", "签订了吗",
    )):
        intent = "announcement_fact_query"
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
        "投资协议": "announcement",
        "公开招募": "announcement",
        "截止": "announcement",
        "预重整": "announcement",
        "价格": "price",
        "股价": "price",
        "跌停": "price",
        "换手率": "price",
        "控制权": "control_structure",
    }
    for term, dimension in dimension_terms.items():
        if term in question:
            dimensions.append(dimension)
    if research_object.kind == "cohort" and research_object.ref.startswith("comparison:"):
        dimensions = ["announcement", "price", "stage", "st_lifecycle"]
    elif research_object.kind == "stock" and any(
        term in question for term in ("分析一下", "分析下", "综合分析", "整体分析")
    ):
        dimensions = list(dict.fromkeys([
            *dimensions, "announcement", "price", "shareholder_count", "equity",
        ]))

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
