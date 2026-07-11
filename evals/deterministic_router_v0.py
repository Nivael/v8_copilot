from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class RoutePrediction:
    predicted_route: str
    expected_status: str
    expected_view: str
    required_lens_behavior: str
    required_data_debt_refs: list[str] = field(default_factory=list)
    required_question_card_refs: list[str] = field(default_factory=list)
    matched_rules: list[str] = field(default_factory=list)
    route_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _norm(text: str) -> str:
    return "".join(text.lower().split())


def _has_any(text: str, terms: list[str]) -> bool:
    return any(term.lower() in text for term in terms)


def _prediction(
    route: str,
    status: str,
    view: str,
    lens_behavior: str,
    *,
    debt_refs: list[str] | None = None,
    question_refs: list[str] | None = None,
    rules: list[str] | None = None,
    note: str = "",
) -> RoutePrediction:
    return RoutePrediction(
        predicted_route=route,
        expected_status=status,
        expected_view=view,
        required_lens_behavior=lens_behavior,
        required_data_debt_refs=debt_refs or [],
        required_question_card_refs=question_refs or [],
        matched_rules=rules or [],
        route_note=note,
    )


def route_question(row: dict[str, Any]) -> RoutePrediction:
    """Route one user-style question to a lawful product output.

    This is a deterministic fallback for W2 acceptance. It deliberately routes
    only the question/object shape; it does not calculate facts or generate
    AnswerCards. W1 remains the source of answer contracts and research facts.
    """
    raw_question = str(row.get("user_question", ""))
    text = _norm(raw_question)
    obj = row.get("object", {}) or {}
    object_kind = str(obj.get("kind", ""))

    # Product boundary outranks missing context: a forbidden request stays
    # forbidden even when the referenced stock or event is ambiguous.
    if _has_any(text, [
        "能买吗", "该买", "买入", "卖出", "目标价", "仓位", "加仓", "减仓",
        "最值得买", "推荐买", "抄底", "割肉", "满仓", "交易信号", "埋伏",
        "上车", "买点", "卖点", "止损", "止盈", "持有还是", "继续持有",
        "会涨停",
    ]):
        return _prediction(
            "refuse_or_rewrite",
            "boundary",
            "boundary",
            "not_applicable",
            rules=["trading_advice_boundary"],
            note="交易建议/目标价/仓位请求必须拒绝或改写为研究问题。",
        )

    missing_referent = object_kind == "unknown" and _has_any(
        text, ["那它呢", "它怎么样", "这只票", "这个股票", "这个节点"],
    )
    if missing_referent or text in {"那它呢?", "那它呢？", "那它呢"}:
        return _prediction(
            "clarify",
            "clarify",
            "clarify",
            "not_applicable",
            rules=["missing_object_or_context"],
            note="缺少可绑定的 stock/event/context，先澄清。",
        )

    if _has_any(text, ["这个节点影响大吗", "节点影响大吗"]):
        return _prediction(
            "clarify",
            "clarify",
            "clarify",
            "not_applicable",
            rules=["missing_node_or_metric"],
            note="缺节点定义和影响口径，先澄清。",
        )

    if _has_any(text, ["像历史上哪些case", "像历史上哪些案例", "相似案例"]):
        return _prediction(
            "needs_review",
            "needs_review",
            "query",
            "lens_gap_required",
            question_refs=["QC-20260710-002"],
            rules=["similarity_method_not_frozen"],
            note="相似案例方法未冻结，先进入 review。",
        )

    debt_refs: list[str] = []
    q_refs: list[str] = []
    gap_rules: list[str] = []
    if "省份" in text:
        debt_refs.append("D-051A")
        q_refs.append("QC-20260710-011")
        gap_rules.append("missing_province_mapping")
    if _has_any(text, ["庭外", "庭内"]) or ("重整" in text and "阶段" in text and "分层" in text):
        debt_refs.append("D-051B")
        q_refs.append("QC-20260710-012")
        gap_rules.append("missing_out_of_court_flag")
    if "相对大盘" in text:
        debt_refs.append("D-051C")
        q_refs.append("QC-20260710-014")
        gap_rules.append("missing_market_index_series")
    if "微盘" in text:
        debt_refs.append("C14")
        q_refs.append("QC-20260710-013")
        gap_rules.append("missing_market_cap_cohort")
    if "股东人数" in text:
        q_refs.append("QC-20260710-006")
        gap_rules.append("missing_shareholder_count_full_coverage")
    if _has_any(text, ["董秘", "论坛热度", "热度", "语气"]):
        gap_rules.append("missing_ir_tone_or_forum_heat")

    # A hard debt id blocks the requested split even when another part of the
    # question is answerable. Preserve every softer gap on the same prediction.
    if debt_refs:
        return _prediction(
            "data_debt",
            "needs_data",
            "data_debt",
            "lens_gap_required",
            debt_refs=debt_refs,
            question_refs=q_refs,
            rules=gap_rules,
            note="可回答部分不能吞掉硬字段缺口。",
        )

    if _has_any(text, ["某节点前后", "某个节点前后"]) and _has_any(text, ["公告", "价格"]):
        return _prediction(
            "answer_query",
            "answerable",
            "query",
            "lens_invocations_or_gap",
            question_refs=["QC-20260710-004", "QC-20260710-008", *q_refs],
            rules=["stock_event_context_query", *gap_rules],
            note="多表节点前后汇总可以先给可得字段，并显式列缺口。",
        )

    if gap_rules:
        return _prediction(
            "data_debt",
            "needs_data",
            "data_debt",
            "lens_gap_required",
            question_refs=q_refs,
            rules=gap_rules,
            note="请求包含当前未冻结或覆盖不足的字段。",
        )

    if _has_any(text, ["哪些lens能解释", "哪些lens"]):
        return _prediction(
            "lens_gap",
            "needs_data",
            "lens_gap",
            "lens_invocations_or_gap",
            question_refs=["QC-20260710-003"],
            rules=["lens_inventory_gap"],
            note="需要可查询的 lens inventory / rejected boundary 后才能完整回答。",
        )

    if _has_any(text, ["c17", "均线回踩lens", "均线回踩"]) and _has_any(text, ["证据等级", "反例", "禁用措辞", "n"]):
        return _prediction(
            "answer_evidence",
            "answerable",
            "evidence",
            "lens_invocation_required",
            question_refs=["QC-20260710-005"],
            rules=["release_library_lens_detail"],
            note="直接读取 release library 中的 lens 字段。",
        )

    if _has_any(text, ["日历月份", "月份效应", "哪些月份"]):
        return _prediction(
            "answer_evidence",
            "answerable",
            "evidence",
            "lens_invocation_required",
            rules=["calendar_regime_evidence_lenses"],
            note="调用 RL-A-001/RL-A-002 日历 regime evidence。",
        )

    if "公告密度" in text and _has_any(text, ["历史先验", "作为一个历史先验"]):
        return _prediction(
            "lens_gap",
            "needs_review",
            "lens_gap",
            "lens_gap_required",
            question_refs=["QC-20260710-007"],
            rules=["query_to_evidence_promotion_gate"],
            note="公告密度 query 可做，历史先验需要验证闸。",
        )

    if _has_any(text, ["控股股东", "控制权", "拍卖"]):
        return _prediction(
            "answer_methodology",
            "answerable",
            "methodology",
            "lens_invocation_required",
            rules=["control_structure_methodology"],
            note="只作为 methodology/checklist，不升级成 evidence。",
        )

    if object_kind == "stock" and _has_any(
        text, ["横", "窗口", "爆发点", "最晚", "投资协议", "平台"]
    ):
        lens_behavior = "lens_gap_required" if _has_any(text, ["最晚", "投资协议"]) else "lens_invocations_or_gap"
        return _prediction(
            "answer_checklist",
            "answerable",
            "checklist",
            lens_behavior,
            question_refs=["QC-20260710-015"],
            rules=["stock_observation_window_checklist"],
            note="预测式问法改写为可观察窗口。",
        )

    if "为什么st" in text or ("为什么" in text and "st" in text):
        return _prediction(
            "answer_query",
            "answerable",
            "query",
            "lens_invocations_or_gap",
            question_refs=["QC-20260710-001"],
            rules=["stock_st_status_timeline"],
            note="ST 原因和关键节点落到状态/公告/episode 时间线。",
        )

    if _has_any(text, ["前后发生了什么", "异动公告前后"]):
        return _prediction(
            "answer_query",
            "answerable",
            "query",
            "lens_invocations_or_gap",
            question_refs=["QC-20260710-004"],
            rules=["stock_event_around_window"],
            note="事件前后用公告、价格和 episode 汇总。",
        )

    if "公告密度" in text:
        return _prediction(
            "answer_query",
            "answerable",
            "query",
            "lens_invocations_or_gap",
            question_refs=["QC-20260710-007"],
            rules=["announcement_density_query"],
            note="公告密度是 descriptive query，不自动升 evidence。",
        )

    if _has_any(text, ["重整投资人招募", "公开招募", "进入下一阶段", "下一个公告节点"]):
        return _prediction(
            "answer_query",
            "answerable",
            "query",
            "lens_invocations_or_gap",
            question_refs=["QC-20260710-009", "QC-20260710-010"],
            rules=["restructuring_next_node_query"],
            note="输出多定义 timing 分布和 lens_gap。",
        )

    if _has_any(text, ["st面板自身", "两周涨跌分布"]):
        return _prediction(
            "answer_query",
            "answerable",
            "query",
            "lens_gap_required",
            question_refs=["QC-20260710-013"],
            rules=["st_panel_two_week_distribution"],
            note="ST 面板自身分布可答，但无验证 lens。",
        )

    if "退市风险警示" in text:
        return _prediction(
            "answer_query",
            "answerable",
            "query",
            "lens_invocations_or_gap",
            rules=["delisting_path_episode_query"],
            note="episode index 路径汇总，不预测退市结果。",
        )

    return _prediction(
        "lens_gap",
        "needs_review",
        "lens_gap",
        "lens_gap_required",
        question_refs=["question_card:new"],
        rules=["deterministic_unknown_fallback"],
        note="已知规则未覆盖；稳定降级为 lens_gap/question_card 候选。",
    )
