from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date
from typing import Any, Iterable

from answer_engine import BASE_DB, EPISODE_INDEX, card_consolidation_checklist
from contracts.v8_copilot_api_contract_v0.models import (
    DossierLensSummary,
    EventNode,
    PricePoint,
    StatusInterval,
    StockDossierPayload,
    TimelineLane,
)


class DossierNotFound(LookupError):
    pass


LANES = [
    ("restructuring", "重整/预重整", "#b45309", {"restructuring_path"}),
    (
        "st_risk",
        "ST/退市风险",
        "#dc2626",
        {"st_entry_or_escalation_path", "delisting_terminal_path", "risk_warning_removal_path"},
    ),
    ("control", "控制权/股东", "#7c3aed", {"control_or_investor_path"}),
    ("regulatory", "监管", "#475569", {"regulatory_pressure_path"}),
    (
        "financial",
        "财报/资金占用",
        "#0d9488",
        {"financial_reporting_path", "fund_occupation_resolution_path", "other_event_path"},
    ),
]

EPISODE_LABELS = {
    "restructuring_path": "重整路径",
    "st_entry_or_escalation_path": "ST 风险进入或升级",
    "delisting_terminal_path": "终止上市风险",
    "risk_warning_removal_path": "风险警示撤销路径",
    "control_or_investor_path": "控制权或投资人变化",
    "regulatory_pressure_path": "监管压力",
    "financial_reporting_path": "财报与审计",
    "fund_occupation_resolution_path": "资金占用处置",
    "other_event_path": "其他事件",
}

SUBTYPE_LABELS = {
    "annual_report_release": "年报或定期报告披露",
    "annual_report_st_continues": "年报后风险警示延续",
    "annual_report_st_start_problem": "年报触发风险警示问题",
    "audit_opinion_issue_resolved": "审计意见相关问题消除",
    "audit_opinion_nonstandard": "非标审计意见或内控问题",
    "audit_progress": "年报编制或审计进展",
    "controlling_shareholder_pledge_or_execution": "控股股东质押、冻结或执行",
    "delisting_possible_termination": "可能终止上市风险提示",
    "earnings_forecast_or_preannouncement": "业绩预告或业绩预披露",
    "fund_occupation_rectification": "资金占用整改",
    "fund_occupation_repayment_or_clearing": "资金占用清偿",
    "fund_occupation_special_report": "资金占用专项报告",
    "investor_or_control_change": "投资人或控制权变化",
    "regulatory_discipline_or_measure": "监管措施或纪律处分",
    "regulatory_inquiry_delay": "监管问询延期回复",
    "regulatory_inquiry_letter": "监管问询函",
    "regulatory_inquiry_reply": "监管问询回复",
    "regulatory_investigation_opened": "监管立案或调查启动",
    "regulatory_letter": "监管工作函",
    "regulatory_penalty_decision": "行政处罚告知或决定",
    "restructuring_pre_restructuring_started": "预重整启动",
    "restructuring_progress_update": "重整或预重整进展",
    "risk_warning_removal_application": "申请撤销风险警示",
}

EVIDENCE_GRADE_LABELS = {
    "aggregate_weak": "汇总弱证据",
    "small_n_case_notes": "小样本案例证据",
    "anecdotal_support": "个案支持",
    "descriptive_query": "描述性查询",
}

COHORT_LABELS = {
    "C17:stock_price_behavior_episode": "股价行为事件样本",
    "C04:stock_event_episode": "股票事件段样本",
}

LENS_KIND_LABELS = {
    "evidence": "证据",
    "methodology": "方法论",
    "query": "查询",
    "checklist": "观察清单",
    "data_debt": "数据债",
}

RELEASE_ROLE_LABELS = {
    "evidence_lens": "证据 lens",
    "case_note_evidence": "案例证据",
    "methodology_frame": "方法论框架",
    "checklist_lens": "清单 lens",
    "query_template": "查询模板",
    "data_debt": "数据债",
}


def _db() -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{BASE_DB}?mode=ro", uri=True)
    connection.execute("PRAGMA query_only = ON")
    return connection


def _lane(episode_type: str) -> tuple[str, str]:
    for lane_id, label, _, members in LANES:
        if episode_type in members:
            return lane_id, label
    return "financial", "财报/资金占用"


def _material_label(value: str | None) -> str:
    if not value:
        return "无"
    if value.startswith("announcement:"):
        return f"公告编号 {value.split(':', 1)[1]}"
    return "来源编号已记录"


def _iter_symbol_episodes(symbol: str) -> Iterable[dict[str, Any]]:
    with EPISODE_INDEX.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if symbol not in line:
                continue
            try:
                episode = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"episode index JSON invalid at line {line_number}"
                ) from exc
            if episode.get("symbol") == symbol:
                yield episode


def _event_id(symbol: str, event_date: str, title: str) -> str:
    digest = hashlib.sha256(f"{symbol}|{event_date}|{title}".encode()).hexdigest()[:16]
    return f"event_{digest}"


def _event_nodes(symbol: str) -> list[EventNode]:
    seen: set[tuple[str, str]] = set()
    nodes: list[EventNode] = []
    for episode in _iter_symbol_episodes(symbol):
        episode_type = str(episode.get("episode_type") or "other_event_path")
        lane_id, lane_label = _lane(episode_type)
        for event in episode.get("anchor_events", []):
            event_date = event.get("announcement_date")
            if not event_date:
                continue
            title = str(event.get("title") or "公告节点").strip()
            dedupe_key = (str(event_date), title[:20])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            subtype = next(iter(event.get("event_subtypes") or []), None)
            source_ref = next(iter(event.get("source_material_ids") or []), None)
            nodes.append(EventNode(
                event_id=_event_id(symbol, str(event_date), title),
                date=str(event_date)[:10],
                title=title,
                lane_id=lane_id,
                lane_label=lane_label,
                episode_type_id=episode_type,
                episode_label=EPISODE_LABELS.get(episode_type, "其他事件"),
                subtype_id=subtype,
                subtype_label=SUBTYPE_LABELS.get(str(subtype), "未归类") if subtype else "无",
                source_material_ref=source_ref,
                source_material_label=_material_label(source_ref),
            ))
    return sorted(nodes, key=lambda node: (node.date, node.event_id))


def _lens_summaries(symbol: str) -> list[DossierLensSummary]:
    card = card_consolidation_checklist(symbol).to_dict()
    summaries: list[DossierLensSummary] = []
    for invocation in card.get("lens_invocations", []):
        lens_kind = LENS_KIND_LABELS.get(invocation.get("lens_kind"), "研究框架")
        release_role = RELEASE_ROLE_LABELS.get(invocation.get("release_role"), "已发布 lens")
        summaries.append(DossierLensSummary(
            release_id=invocation["release_id"],
            lens_label=f"{lens_kind}/{release_role}",
            contributed_section=str(invocation.get("contributed_section", "")).replace(
                "C17 wording", "历史股价行为样本措辞边界"
            ),
            evidence_grade_label=EVIDENCE_GRADE_LABELS.get(
                invocation.get("evidence_grade"), ""
            ),
            cohort_label=COHORT_LABELS.get(invocation.get("cohort_id"), ""),
        ))
    return summaries


def load_stock_dossier(symbol: str) -> StockDossierPayload:
    if len(symbol) != 6 or not symbol.isdigit():
        raise DossierNotFound(f"invalid symbol: {symbol}")

    with _db() as connection:
        price_rows = connection.execute(
            "select trade_date,close from daily_prices "
            "where symbol=? and adjust='qfq' order by trade_date",
            (symbol,),
        ).fetchall()
        status_rows = connection.execute(
            "select start_date,end_date,status_name,status_type,source "
            "from st_status_history where symbol=? order by start_date",
            (symbol,),
        ).fetchall()

    nodes = _event_nodes(symbol)
    if not price_rows and not status_rows and not nodes:
        raise DossierNotFound(f"no dossier data for symbol: {symbol}")

    prices = [PricePoint(date=row[0], close=float(row[1])) for row in price_rows]
    statuses = [
        StatusInterval(
            start_date=row[0],
            end_date=row[1],
            display_name=row[2],
            status_type_id=row[3],
            source=row[4],
        )
        for row in status_rows
    ]
    as_of_candidates = [point.date for point in prices] + [node.date for node in nodes]
    as_of = max(as_of_candidates, default=date.today())
    display_name = statuses[-1].display_name if statuses else symbol

    return StockDossierPayload(
        symbol=symbol,
        display_name=display_name,
        as_of=as_of,
        price_series=prices,
        status_intervals=statuses,
        event_nodes=nodes,
        timeline_lanes=[
            TimelineLane(lane_id=lane_id, display_label=label, color=color)
            for lane_id, label, color, _ in LANES
        ],
        lens_invocations=_lens_summaries(symbol),
        source_freshness={
            "price_data_as_of": str(prices[-1].date) if prices else "unavailable",
            "episode_index_as_of": str(nodes[-1].date) if nodes else "unavailable",
        },
        provenance=[
            f"shared_data/v5/.../st_stocks_v5_backup.sqlite3::daily_prices[{symbol}]",
            f"shared_data/v5/.../st_stocks_v5_backup.sqlite3::st_status_history[{symbol}]",
            "shared_data/v7/episode_index_v0/episode_index.jsonl",
            "shared_data/v7/release_library_v1/release_library.json",
        ],
    )
