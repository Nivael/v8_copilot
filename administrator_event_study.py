"""Availability-safe price context around administrator appointment events."""
from __future__ import annotations

import sqlite3
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from market_comparison import (
    MARKET_BENCHMARK,
    REQUIRED_BENCHMARKS,
    SMALL_CAP_BENCHMARK,
    ST_BENCHMARK,
)
from restructuring_administrators import AdministratorRepository


WINDOW_SESSIONS = {"post5": 5, "post20": 20, "post60": 60}
APPOINTMENT_KIND_LABELS = {
    "temporary_administrator": "预重整临时管理人",
    "administrator": "正式重整管理人",
}
EVENT_TYPE_LABELS = {
    "administrator_appointed": "管理人任命",
    "pre_restructuring_started": "预重整启动",
    "formal_restructuring_accepted": "法院正式受理重整",
    "investor_recruitment_started": "重整投资人公开招募",
    "restructuring_plan_published": "重整计划草案披露",
    "restructuring_plan_approved": "法院批准重整计划",
    "restructuring_completed": "重整执行完毕或程序终结",
    "restructuring_terminated": "重整或预重整终止",
}


@dataclass(frozen=True)
class EventWindowMetric:
    window: str
    start_date: str
    end_date: str
    stock_return_pct: float | None
    benchmark_returns_pct: dict[str, float] = field(default_factory=dict)
    relative_returns_pp: dict[str, float] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AdministratorEventStudy:
    event_id: str
    case_id: str
    assignment_id: str
    organization_id: str
    organization_name: str
    symbol: str
    appointment_kind: str
    event_type: str
    information_available_date: str
    baseline_date: str
    t0_date: str
    windows: dict[str, EventWindowMetric]
    max_runup_60_pct: float | None
    max_drawdown_60_pct: float | None
    gaps: list[str] = field(default_factory=list)

    @property
    def has_observation(self) -> bool:
        return bool(self.baseline_date and self.t0_date)


def _return_pct(start: float, end: float) -> float:
    if start == 0:
        raise ValueError("price series baseline is zero")
    return round(end / start * 100 - 100, 8)


def _stock_series(price_database: Path, symbol: str) -> list[tuple[str, float]]:
    if not price_database.is_file():
        return []
    with sqlite3.connect(f"file:{price_database}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "select trade_date,close from daily_prices where symbol=? and adjust='qfq' "
            "and close is not null order by trade_date",
            (symbol,),
        ).fetchall()
    return [(str(day), float(close)) for day, close in rows]


def _benchmark_metric(
    market_database: Path,
    *,
    start_date: str,
    end_date: str,
    coverage_threshold: float,
) -> tuple[dict[str, float], list[str]]:
    if not market_database.is_file():
        return {}, ["market-context 数据库不存在"]
    with sqlite3.connect(f"file:{market_database}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "select benchmark_id,trade_date,close,coverage_ratio "
            "from benchmark_daily where benchmark_id in (?,?,?) "
            "and trade_date in (?,?)",
            (*REQUIRED_BENCHMARKS, start_date, end_date),
        ).fetchall()
    values: dict[str, dict[str, float]] = {
        benchmark_id: {} for benchmark_id in REQUIRED_BENCHMARKS
    }
    st_coverage: dict[str, float] = {}
    for benchmark_id, trade_date, close, coverage in rows:
        if close is not None:
            values[str(benchmark_id)][str(trade_date)] = float(close)
        if benchmark_id == ST_BENCHMARK and coverage is not None:
            st_coverage[str(trade_date)] = float(coverage)
    returns: dict[str, float] = {}
    gaps: list[str] = []
    for benchmark_id in REQUIRED_BENCHMARKS:
        missing = [
            day for day in (start_date, end_date)
            if day not in values[benchmark_id]
        ]
        if missing:
            gaps.append(
                f"{benchmark_id} 缺事件共同交易日，不插值: {','.join(missing)}"
            )
            continue
        if benchmark_id == ST_BENCHMARK:
            low_coverage = [
                day for day in (start_date, end_date)
                if st_coverage.get(day, 0) < coverage_threshold
            ]
            if low_coverage:
                gaps.append(
                    "st_equal_weight_v1 覆盖率低于门槛: "
                    + ",".join(low_coverage)
                )
                continue
        returns[benchmark_id] = _return_pct(
            values[benchmark_id][start_date],
            values[benchmark_id][end_date],
        )
    return returns, gaps


def study_administrator_event(
    *,
    event: dict[str, Any],
    organization_id: str,
    price_database: Path,
    market_database: Path,
    coverage_threshold: float = 0.95,
) -> AdministratorEventStudy:
    """Align date-only disclosures to the first strictly later trading session.

    ``baseline_date`` is the last listed-company close on or before the
    information date. ``t0_date`` is the first close strictly after it.  This
    intentionally gives up the same-day move because the source does not prove
    that the announcement was available before that session opened.
    """
    symbol = str(event["symbol"])
    information_date = str(event["information_available_date"])
    series = _stock_series(price_database, symbol)
    baseline_index = max(
        (index for index, (day, _) in enumerate(series) if day <= information_date),
        default=-1,
    )
    if baseline_index < 0 or baseline_index + 1 >= len(series):
        return AdministratorEventStudy(
            event_id=str(event["event_id"]),
            case_id=str(event["case_id"]),
            assignment_id=str(event["assignment_id"]),
            organization_id=organization_id,
            organization_name=str(event["canonical_name"]),
            symbol=symbol,
            appointment_kind=str(event["appointment_kind"]),
            event_type=str(event["event_type"]),
            information_available_date=information_date,
            baseline_date="",
            t0_date="",
            windows={},
            max_runup_60_pct=None,
            max_drawdown_60_pct=None,
            gaps=["个股价格无法形成披露日前基线和披露后首个交易日"],
        )
    baseline_date, baseline_close = series[baseline_index]
    t0_date = series[baseline_index + 1][0]
    windows: dict[str, EventWindowMetric] = {}
    overall_gaps: list[str] = []

    if baseline_index >= 20:
        start_date, start_close = series[baseline_index - 20]
        benchmark_returns, gaps = _benchmark_metric(
            market_database,
            start_date=start_date,
            end_date=baseline_date,
            coverage_threshold=coverage_threshold,
        )
        stock_return = _return_pct(start_close, baseline_close)
        windows["pre20"] = EventWindowMetric(
            window="pre20",
            start_date=start_date,
            end_date=baseline_date,
            stock_return_pct=stock_return,
            benchmark_returns_pct=benchmark_returns,
            relative_returns_pp={
                benchmark_id: round(stock_return - value, 8)
                for benchmark_id, value in benchmark_returns.items()
            },
            gaps=gaps,
        )
    else:
        overall_gaps.append("pre20 个股历史交易日不足")

    for window, sessions in WINDOW_SESSIONS.items():
        end_index = baseline_index + sessions
        if end_index >= len(series):
            overall_gaps.append(f"{window} 个股披露后交易日不足")
            continue
        end_date, end_close = series[end_index]
        benchmark_returns, gaps = _benchmark_metric(
            market_database,
            start_date=baseline_date,
            end_date=end_date,
            coverage_threshold=coverage_threshold,
        )
        stock_return = _return_pct(baseline_close, end_close)
        windows[window] = EventWindowMetric(
            window=window,
            start_date=baseline_date,
            end_date=end_date,
            stock_return_pct=stock_return,
            benchmark_returns_pct=benchmark_returns,
            relative_returns_pp={
                benchmark_id: round(stock_return - value, 8)
                for benchmark_id, value in benchmark_returns.items()
            },
            gaps=gaps,
        )

    observed_60 = series[baseline_index + 1:baseline_index + 61]
    moves = [
        _return_pct(baseline_close, close)
        for _, close in observed_60
    ]
    running_peak = baseline_close
    drawdowns: list[float] = []
    for _, close in observed_60:
        running_peak = max(running_peak, close)
        drawdowns.append(_return_pct(running_peak, close))
    return AdministratorEventStudy(
        event_id=str(event["event_id"]),
        case_id=str(event["case_id"]),
        assignment_id=str(event["assignment_id"]),
        organization_id=organization_id,
        organization_name=str(event["canonical_name"]),
        symbol=symbol,
        appointment_kind=str(event["appointment_kind"]),
        event_type=str(event["event_type"]),
        information_available_date=information_date,
        baseline_date=baseline_date,
        t0_date=t0_date,
        windows=windows,
        max_runup_60_pct=max(moves) if moves else None,
        max_drawdown_60_pct=min(drawdowns) if drawdowns else None,
        gaps=overall_gaps,
    )


def organization_event_studies(
    *,
    repository: AdministratorRepository,
    organization_id: str,
    price_database: Path,
    market_database: Path,
) -> list[AdministratorEventStudy]:
    events = repository.events_for_organization(organization_id)
    # One case and milestone type is one observation. Repeated notices cannot
    # inflate the manager cohort.
    deduplicated: dict[tuple[str, str], dict[str, Any]] = {}
    for event in events:
        key = (str(event["case_id"]), str(event["event_type"]))
        previous = deduplicated.get(key)
        if previous is None or str(event["information_available_date"]) < str(
            previous["information_available_date"]
        ):
            deduplicated[key] = event
    return [
        study_administrator_event(
            event=event,
            organization_id=organization_id,
            price_database=price_database,
            market_database=market_database,
        )
        for event in sorted(
            deduplicated.values(),
            key=lambda item: (
                str(item["information_available_date"]),
                str(item["case_id"]),
            ),
        )
    ]


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile requires values")
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 8)


def cohort_distribution_rows(
    studies: list[AdministratorEventStudy],
    *,
    minimum_cases: int = 8,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    event_types = sorted({study.event_type for study in studies})
    for event_type in event_types:
        event_studies = [
            study for study in studies if study.event_type == event_type
        ]
        if len({study.case_id for study in event_studies}) < minimum_cases:
            continue
        for window in ("post5", "post20", "post60"):
            values = [
                metric.stock_return_pct
                for study in event_studies
                if (metric := study.windows.get(window)) is not None
                and metric.stock_return_pct is not None
            ]
            if len(values) < minimum_cases:
                continue
            numeric = [float(value) for value in values]
            relative_medians: dict[str, float | str] = {}
            for benchmark_id, label in (
                (ST_BENCHMARK, "相对ST中位数(百分点)"),
                (SMALL_CAP_BENCHMARK, "相对中证2000中位数(百分点)"),
                (MARKET_BENCHMARK, "相对中证全指中位数(百分点)"),
            ):
                relative_values = [
                    float(metric.relative_returns_pp[benchmark_id])
                    for study in event_studies
                    if (metric := study.windows.get(window)) is not None
                    and benchmark_id in metric.relative_returns_pp
                ]
                relative_medians[label] = (
                    round(statistics.median(relative_values), 8)
                    if len(relative_values) >= minimum_cases
                    else "同端点样本不足"
                )
            rows.append({
                "row_id": f"administrator_distribution_{event_type}_{window}",
                "记录类型": "管理人节点分布",
                "节点类型": EVENT_TYPE_LABELS.get(event_type, event_type),
                "node_type": event_type,
                "窗口": window,
                "案件数": len(numeric),
                "个股收益中位数": round(statistics.median(numeric), 8),
                "个股收益P25": _percentile(numeric, 0.25),
                "个股收益P75": _percentile(numeric, 0.75),
                **relative_medians,
                "口径": "按案件和节点类型去重的描述性分布",
            })
    return rows


def event_study_row(
    study: AdministratorEventStudy,
    *,
    row_id: str,
) -> dict[str, Any]:
    def value(window: str, source: str) -> float | str:
        metric = study.windows.get(window)
        if metric is None:
            return "缺数据"
        if source == "stock":
            return (
                round(float(metric.stock_return_pct), 4)
                if metric.stock_return_pct is not None else "缺数据"
            )
        result = metric.relative_returns_pp.get(source)
        return round(result, 4) if result is not None else "基准缺数据"

    gaps = [
        *study.gaps,
        *[
            gap
            for metric in study.windows.values()
            for gap in metric.gaps
        ],
    ]
    return {
        "row_id": row_id,
        "记录类型": "管理人节点案例",
        "管理人": study.organization_name,
        "股票": study.symbol,
        "任职类型": APPOINTMENT_KIND_LABELS.get(
            study.appointment_kind, study.appointment_kind
        ),
        "appointment_kind": study.appointment_kind,
        "节点类型": EVENT_TYPE_LABELS.get(study.event_type, study.event_type),
        "node_type": study.event_type,
        "信息可得日": study.information_available_date,
        "基线交易日": study.baseline_date or "缺数据",
        "首个可观察交易日": study.t0_date or "缺数据",
        "任职前20日个股收益(%)": value("pre20", "stock"),
        "任职后5日个股收益(%)": value("post5", "stock"),
        "任职后20日个股收益(%)": value("post20", "stock"),
        "任职后60日个股收益(%)": value("post60", "stock"),
        "后20日相对ST(百分点)": value("post20", ST_BENCHMARK),
        "后20日相对中证2000(百分点)": value("post20", SMALL_CAP_BENCHMARK),
        "后20日相对中证全指(百分点)": value("post20", MARKET_BENCHMARK),
        "后60日最大涨幅(%)": (
            round(study.max_runup_60_pct, 4)
            if study.max_runup_60_pct is not None else "缺数据"
        ),
        "后60日最大回撤(%)": (
            round(study.max_drawdown_60_pct, 4)
            if study.max_drawdown_60_pct is not None else "缺数据"
        ),
        "缺口": "；".join(dict.fromkeys(gaps)) if gaps else "无",
    }
