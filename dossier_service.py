"""Read-only stock dossier payload builder for the W1 API."""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import date

from api_contract import (
    DateRange,
    DossierDataGap,
    DossierEvent,
    DossierLensSummary,
    PricePoint,
    ResearchContext,
    StatusInterval,
    StockDossierPayload,
    TimelineLane,
)
from answer_engine import (
    BASE_DB,
    EPISODE_INDEX,
)
from lens_binding import LensRegistry


class DossierNotFoundError(LookupError):
    pass


LANES = {
    "restructuring": {
        "label": "重整与预重整",
        "episode_types": {"restructuring_path"},
    },
    "st_risk": {
        "label": "ST 与退市风险",
        "episode_types": {
            "st_entry_or_escalation_path",
            "delisting_terminal_path",
            "risk_warning_removal_path",
        },
    },
    "control": {
        "label": "控制权与股东",
        "episode_types": {"control_or_investor_path"},
    },
    "regulatory": {
        "label": "监管",
        "episode_types": {"regulatory_pressure_path"},
    },
    "financial": {
        "label": "财报与资金占用",
        "episode_types": {
            "financial_reporting_path",
            "fund_occupation_resolution_path",
            "other_event_path",
        },
    },
}

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


def _lane_for(episode_type: str) -> tuple[str, str]:
    for lane_id, lane in LANES.items():
        if episode_type in lane["episode_types"]:
            return lane_id, str(lane["label"])
    return "financial", str(LANES["financial"]["label"])


def _display_name(status_rows: list[tuple]) -> str:
    if not status_rows:
        return "未命名股票"
    status_name = str(status_rows[-1][2])
    return status_name.split(":", 1)[0]


def _load_events(symbol: str) -> list[DossierEvent]:
    seen: set[tuple[str, str, str]] = set()
    events: list[DossierEvent] = []
    with EPISODE_INDEX.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if symbol not in line:
                continue
            try:
                episode = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"episode index JSON 非法: {EPISODE_INDEX}:{line_number}: {exc}"
                ) from exc
            if episode.get("symbol") != symbol:
                continue
            episode_type = str(episode.get("episode_type", "other_event_path"))
            lane_id, lane_label = _lane_for(episode_type)
            for anchor in episode.get("anchor_events", []):
                announcement_date = anchor.get("announcement_date")
                if not announcement_date:
                    continue
                title = str(anchor.get("title") or "未命名公告").strip()
                source_ids = [str(item) for item in anchor.get("source_material_ids", [])]
                source_id = source_ids[0] if source_ids else ""
                key = (str(announcement_date), title, source_id)
                if key in seen:
                    continue
                seen.add(key)
                subtypes = anchor.get("event_subtypes") or []
                subtype = str(subtypes[0]) if subtypes else None
                related_lenses = (
                    ["RL-C-002", "RL-C-003"] if lane_id == "control" else []
                )
                event_id = source_id or f"{symbol}:{announcement_date}:{len(events) + 1}"
                events.append(DossierEvent(
                    event_id=event_id,
                    date=date.fromisoformat(str(announcement_date)[:10]),
                    title=title,
                    episode_type=episode_type,
                    episode_label=EPISODE_LABELS.get(episode_type, "其他事件"),
                    subtype=subtype,
                    subtype_label=SUBTYPE_LABELS.get(subtype or "", "其他已分类事件"),
                    timeline_lane=lane_id,
                    timeline_label=lane_label,
                    provenance_refs=source_ids,
                    related_lens_ids=related_lenses,
                ))
    events.sort(key=lambda event: (event.date, event.event_id))
    return events


def _append_announcement_focus(
    symbol: str,
    event_id: str | None,
    events: list[DossierEvent],
) -> None:
    """Resolve one non-episode announcement from SQLite for dossier deep links."""
    if not event_id:
        return
    announcement_id = (
        event_id.split(":", 1)[1]
        if event_id.startswith("announcement:")
        else event_id
    )
    resolved_id = f"announcement:{announcement_id}"
    if resolved_id in {event.event_id for event in events}:
        return
    with sqlite3.connect(f"file:{BASE_DB}?mode=ro", uri=True) as connection:
        row = connection.execute(
            "select announcement_id,announcement_date,title from company_announcements "
            "where symbol=? and announcement_id=? limit 1",
            (symbol, announcement_id),
        ).fetchone()
    if not row:
        return
    resolved_id = f"announcement:{row[0]}"
    events.append(DossierEvent(
        event_id=resolved_id,
        date=date.fromisoformat(str(row[1])[:10]),
        title=str(row[2]),
        episode_type="other_event_path",
        episode_label="公开公告（未纳入事件段）",
        subtype="announcement_unclassified",
        subtype_label="其他公开公告",
        timeline_lane="financial",
        timeline_label=str(LANES["financial"]["label"]),
        provenance_refs=[resolved_id],
        related_lens_ids=[],
    ))
    events.sort(key=lambda event: (event.date, event.event_id))


def _dossier_lens_summaries(events: list[DossierEvent]) -> tuple[list[DossierLensSummary], int]:
    """Bind only lenses supported by actual dossier event content.

    A generic stock dossier must not inherit the Mubon consolidation checklist. Broad
    event lanes receive methodology frames only where their topic is an exact match;
    narrow evidence/case lenses require an explicit title-level trigger.
    """
    registry = LensRegistry()
    selected: list[tuple[str, str]] = []
    if any(event.timeline_lane == "control" for event in events):
        selected.extend([
            ("RL-C-002", "股东行为与拍卖节点的核查框架"),
            ("RL-C-003", "控制权结构变化的核查框架"),
        ])
    titles = "\n".join(event.title for event in events)
    if "共益债" in titles or "公益债" in titles:
        selected.append(("RL-B-002", "共益债相关个案材料，仅作个案支持"))
    if "重大资产重组" in titles or "资产注入" in titles:
        selected.append(("RL-C-004", "重大资产重组与资产注入的核查框架"))

    summaries: list[DossierLensSummary] = []
    for release_id, section in selected:
        invocation = registry.invoke(registry.get(release_id), section)
        summaries.append(DossierLensSummary(
            release_id=invocation.release_id,
            lens_kind=invocation.lens_kind,
            display_label=invocation.contributed_section,
            evidence_grade=invocation.evidence_grade,
            contributed_section=invocation.contributed_section,
            provenance_refs=invocation.provenance_refs,
        ))
    return summaries, len(registry.records)


def build_stock_dossier(
    symbol: str,
    announcement_focus: str | None = None,
) -> StockDossierPayload:
    if len(symbol) != 6 or not symbol.isdigit():
        raise ValueError(f"股票代码必须是 6 位数字: {symbol!r}")

    with sqlite3.connect(f"file:{BASE_DB}?mode=ro", uri=True) as connection:
        price_rows = connection.execute(
            "select trade_date,close from daily_prices "
            "where symbol=? and adjust='qfq' order by trade_date",
            (symbol,),
        ).fetchall()
        status_rows = connection.execute(
            "select start_date,end_date,status_name,status_type,source "
            "from st_status_history where symbol=? order by start_date,source",
            (symbol,),
        ).fetchall()
    if not price_rows:
        raise DossierNotFoundError(f"当前快照无股票 {symbol} 的 qfq 价格数据")

    price_series = [
        PricePoint(date=date.fromisoformat(trade_date[:10]), close=float(close))
        for trade_date, close in price_rows
    ]
    status_intervals = [
        StatusInterval(
            start_date=date.fromisoformat(start_date[:10]),
            end_date=date.fromisoformat(end_date[:10]) if end_date else None,
            status_name=status_name,
            status_type=status_type,
            source=source,
        )
        for start_date, end_date, status_name, status_type, source in status_rows
    ]
    events = _load_events(symbol)
    _append_announcement_focus(symbol, announcement_focus, events)

    lane_events: dict[str, list[str]] = defaultdict(list)
    for event in events:
        lane_events[event.timeline_lane].append(event.event_id)
    timeline_lanes = [
        TimelineLane(
            lane_id=lane_id,
            label=str(lane["label"]),
            event_ids=lane_events[lane_id],
        )
        for lane_id, lane in LANES.items()
    ]

    lens_summaries, library_size = _dossier_lens_summaries(events)

    return StockDossierPayload(
        symbol=symbol,
        display_name=_display_name(status_rows),
        as_of=price_series[-1].date,
        status_intervals=status_intervals,
        price_series=price_series,
        events=events,
        timeline_lanes=timeline_lanes,
        lens_summaries=lens_summaries,
        data_gaps=[
            DossierDataGap(
                gap_id="shareholder_count_full_coverage",
                display_label="股东人数全量覆盖尚未完成",
                debt_ref="D-021",
            ),
            DossierDataGap(
                gap_id="exact_equity_timeline",
                display_label="精确股权与控制权字段覆盖仍有限",
            ),
        ],
        display_labels={
            "price_adjustment": "前复权",
            "event_count": f"{len(events)} 个已分类公告节点",
            "source_boundary": "本地只读历史快照",
            "lens_library_size": f"冻结库 {library_size} 条",
        },
        research_context=ResearchContext(
            symbol=symbol,
            date_range=DateRange(start=price_series[0].date, end=price_series[-1].date),
            selected_lenses=[summary.release_id for summary in lens_summaries],
        ),
        provenance=[
            "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3::daily_prices",
            "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3::st_status_history",
            "shared_data/v7/episode_index_v0/episode_index.jsonl",
            "shared_data/v7/release_library_v1/release_library.json",
        ],
    )
