"""Reusable query definitions; templates organize queries but never become evidence."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


QUERY_TEMPLATE_CONTRACT_VERSION = "v8_query_template_contract_v0"


class QueryTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    contract_version: Literal[QUERY_TEMPLATE_CONTRACT_VERSION] = (
        QUERY_TEMPLATE_CONTRACT_VERSION
    )
    template_id: str = Field(pattern=r"^QT-[0-9]{3}$")
    question_pattern: str = Field(min_length=1, max_length=1000)
    required_inputs: list[str] = Field(min_length=1, max_length=20)
    query_intent: str = Field(min_length=1, max_length=128)
    definition_variants: list[str] = Field(default_factory=list, max_length=20)
    default_caveats: list[str] = Field(default_factory=list, max_length=20)
    data_debt_fallbacks: list[str] = Field(default_factory=list, max_length=20)
    executor_key: str = Field(min_length=1, max_length=128)
    not_evidence: Literal[True] = True


TEMPLATES = (
    QueryTemplate(
        template_id="QT-001",
        question_pattern="某事件后下一个节点多久",
        required_inputs=["episode_type"],
        query_intent="event_next_node_timing",
        definition_variants=[
            "next_any_announcement",
            "next_classified_event",
            "next_stage_milestone",
        ],
        default_caveats=["不同节点定义必须并列展示"],
        data_debt_fallbacks=["D-051A", "D-051B"],
        executor_key="next_node_timing",
    ),
    QueryTemplate(
        template_id="QT-002",
        question_pattern="某节点前后公告、价格和 episode 发生了什么",
        required_inputs=["symbol", "event_id", "event_date"],
        query_intent="stock_event_window",
        default_caveats=["只描述可回链的历史窗口"],
        data_debt_fallbacks=["D-021"],
        executor_key="stock_event_window",
    ),
    QueryTemplate(
        template_id="QT-003",
        question_pattern="某股票 ST 前后时间线",
        required_inputs=["symbol"],
        query_intent="st_status_timeline",
        default_caveats=["状态名称不能替代触发原因公告"],
        executor_key="st_status_timeline",
    ),
    QueryTemplate(
        template_id="QT-004",
        question_pattern="某 cohort 两周分布",
        required_inputs=["cohort", "daily_prices"],
        query_intent="cohort_two_week_distribution",
        definition_variants=["t_plus_10_trading_days"],
        default_caveats=["横截面分布不构成交易阈值"],
        data_debt_fallbacks=["D-051C", "C14"],
        executor_key="two_week_distribution",
    ),
    QueryTemplate(
        template_id="QT-005",
        question_pattern="字段缺失时生成标准 data-debt 出口",
        required_inputs=["debt_ref"],
        query_intent="data_debt_exit",
        default_caveats=["缺字段时不得生成替代结论"],
        executor_key="data_debt",
    ),
    QueryTemplate(
        template_id="QT-006",
        question_pattern="单票当前应观察哪些公开窗口",
        required_inputs=["symbol", "daily_prices", "episode_index"],
        query_intent="stock_observation_windows",
        default_caveats=["观察窗口不预测方向或期限"],
        executor_key="observation_checklist",
    ),
    QueryTemplate(
        template_id="QT-007",
        question_pattern="读取 frozen release lens 的证据字段",
        required_inputs=["release_id"],
        query_intent="release_lens_detail",
        default_caveats=["历史先验不自动成为可交易信号"],
        executor_key="release_lens_detail",
    ),
    QueryTemplate(
        template_id="QT-008",
        question_pattern="读取控制权与股东行为方法论框架",
        required_inputs=["lens_cluster"],
        query_intent="control_structure_methodology",
        default_caveats=["methodology 不得升级为 evidence"],
        executor_key="control_methodology",
    ),
)

TEMPLATE_BY_ID = {template.template_id: template for template in TEMPLATES}

RULE_TO_TEMPLATE = {
    "restructuring_next_node_query": "QT-001",
    "stock_event_context_query": "QT-002",
    "stock_event_around_window": "QT-002",
    "stock_st_status_timeline": "QT-003",
    "st_panel_two_week_distribution": "QT-004",
    "missing_province_mapping": "QT-005",
    "missing_out_of_court_flag": "QT-005",
    "missing_market_index_series": "QT-005",
    "missing_market_cap_cohort": "QT-005",
    "missing_shareholder_count_full_coverage": "QT-005",
    "stock_observation_window_checklist": "QT-006",
    "release_library_lens_detail": "QT-007",
    "calendar_regime_evidence_lenses": "QT-007",
    "control_structure_methodology": "QT-008",
}


def template_for_rules(rules: list[str]) -> QueryTemplate | None:
    for rule in rules:
        template_id = RULE_TO_TEMPLATE.get(rule)
        if template_id:
            return TEMPLATE_BY_ID[template_id]
    return None
