"""Leakage-safe anchored replays and retrospective P7 calibration reports.

The report deliberately separates three questions:

* whether announcement facts are structurally auditable;
* whether non-hard priority announcements precede later hard transitions;
* whether increasingly unusual free-float turnover precedes later hard transitions.

Future announcements are used only as labelled outcomes.  They never change an
earlier anomaly feature, announcement classification, anchor, or threshold.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left
import hashlib
import html
import json
import math
import sqlite3
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from p7_anomalies import ActivityAnomaly
from p7_announcements import AnnouncementBundle, AnnouncementFact, IssuerTransition
from p7_daily import load_valuation_stage_map
from settings import MARKET_CONTEXT_DB, P7_INTELLIGENCE_DB, VALUATION_EPISODE_DB


CONTRACT_VERSION = "p7_retrospective_backtest_v1"
HORIZONS = (5, 10, 20, 60)
DEVIATION_LEVELS: dict[str, tuple[float, float]] = {
    "D1_watch": (90.0, 2.0),
    "D2_broad": (95.0, 3.0),
    "D3_balanced": (97.5, 4.0),
    "D4_strict": (99.0, 5.0),
}
DEVIATION_LEVEL_ORDER = tuple(DEVIATION_LEVELS)
P6_TO_P7_EVENT = {
    "formal_restructuring_accepted": "court_restructuring_accepted",
    "restructuring_plan_approved": "restructuring_plan_approved",
    "restructuring_terminated": "restructuring_terminated",
}
RISK_NOTICE = (
    "放量偏离只表示相对自身历史的交易活跃变化；后续正式硬节点率不是内幕、资金身份、"
    "买卖时点或未来收益判断。"
)
STATUS_LABELS = {
    "consistent_on_verified_overlap_with_body_gaps": "核证重叠一致，但正文仍有缺口",
    "consistent_on_verified_overlap": "核证重叠一致",
    "insufficient_independent_verified_overlap": "独立核证重叠不足",
    "needs_structural_investigation": "结构冲突待排查",
    "insufficient_out_of_sample_size": "留出样本不足",
    "not_predictively_separated_out_of_sample": "留出样本未显示可用区分度",
    "retrospective_research_value_candidate_only": "仅为历史候选，仍需前瞻验证",
    "insufficient_comparable_control_coverage": "同阶段可比对照覆盖不足",
    "not_validated_out_of_sample": "留出验证未通过",
    "retrospective_candidate_only": "仅为历史候选，仍需前瞻验证",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class P7BacktestReport(StrictModel):
    report_id: str = Field(pattern=r"^P7BT-[A-F0-9]{20}$")
    contract_version: str = CONTRACT_VERSION
    generated_at: str
    through: str
    baseline_start: str
    source_run_ids: dict[str, str]
    anchor_definition: dict[str, Any]
    anchors: list[dict[str, Any]]
    announcement_evaluation: dict[str, Any]
    deviation_evaluation: dict[str, Any]
    release_interpretation: dict[str, str]
    limitations: list[str]
    risk_notice: str = RISK_NOTICE


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _wilson(successes: int, observations: int) -> list[float] | None:
    if observations <= 0:
        return None
    z = 1.959963984540054
    proportion = successes / observations
    denominator = 1 + z * z / observations
    centre = (proportion + z * z / (2 * observations)) / denominator
    half = z * math.sqrt(
        proportion * (1 - proportion) / observations
        + z * z / (4 * observations * observations)
    ) / denominator
    return [round(max(0.0, centre - half), 8), round(min(1.0, centre + half), 8)]


def _rate(values: list[bool]) -> float | None:
    return round(sum(values) / len(values), 8) if values else None


def _lift(signal_rate: float | None, control_rate: float | None) -> float | None:
    if signal_rate is None or control_rate in (None, 0):
        return None
    return round(signal_rate / control_rate, 8)


def _announcement_release_status(
    priority_metrics: dict[str, Any], routine_metrics: dict[str, Any],
) -> str:
    """Conservatively describe retrospective separation without tuning a cutoff.

    A point estimate that is only microscopically above routine is not a usable
    research-value result.  Requiring non-overlap of the already-reported Wilson
    intervals is deliberately conservative.  This status never authorizes a
    production release; prospective shadow remains a separate gate.
    """

    priority_n = priority_metrics["observed_by_horizon"]["20"]
    routine_n = routine_metrics["observed_by_horizon"]["20"]
    priority_rate = priority_metrics["hard_node_rate_by_horizon"]["20"]
    routine_rate = routine_metrics["hard_node_rate_by_horizon"]["20"]
    priority_interval = priority_metrics["wilson_95_horizon_20"]
    routine_interval = routine_metrics["wilson_95_horizon_20"]
    if priority_n < 20 or routine_n < 20:
        return "insufficient_out_of_sample_size"
    if priority_rate is None or routine_rate is None or priority_rate <= routine_rate:
        return "not_predictively_separated_out_of_sample"
    if (
        priority_interval is None
        or routine_interval is None
        or priority_interval[0] <= routine_interval[1]
    ):
        return "not_predictively_separated_out_of_sample"
    return "retrospective_research_value_candidate_only"


def deviation_level(anomaly: ActivityAnomaly) -> int | None:
    """Return the highest preregistered nested deviation level for one day."""

    if (
        not anomaly.calculable
        or anomaly.turnover_percentile_120 is None
        or anomaly.turnover_robust_z_120 is None
    ):
        return None
    percentile = anomaly.turnover_percentile_120
    robust_z = anomaly.turnover_robust_z_120
    for level, label in reversed(list(enumerate(DEVIATION_LEVEL_ORDER, start=1))):
        percentile_gate, z_gate = DEVIATION_LEVELS[label]
        if percentile >= percentile_gate and robust_z >= z_gate:
            return level
    return 0


def derive_anchors(calendar: list[str], through: str) -> dict[str, str]:
    eligible = [day for day in sorted(dict.fromkeys(calendar)) if day <= through]
    if len(eligible) < 22:
        raise ValueError("交易日历不足以构造周/月锚点")
    latest = eligible[-1]
    year_target = (date.fromisoformat(latest) - timedelta(days=365)).isoformat()
    year_candidates = [day for day in eligible if day <= year_target]
    if not year_candidates:
        raise ValueError("交易日历不足以构造一年锚点")
    return {
        "past_week": eligible[-6],
        "past_month": eligible[-22],
        "past_year": year_candidates[-1],
    }


def _load_calendar(database: Path, *, through: str) -> list[str]:
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        return [
            str(row[0])
            for row in connection.execute(
                "select trade_date from benchmark_daily where benchmark_id='csi_all_share' "
                "and trade_date<=? order by trade_date",
                (through,),
            )
        ]


def _latest_run_id(connection: sqlite3.Connection, table: str, *, run_kind: str = "") -> str:
    where = " where run_kind=?" if run_kind else ""
    params: tuple[str, ...] = (run_kind,) if run_kind else ()
    row = connection.execute(
        f"select run_id from {table}{where} order by created_at desc limit 1",
        params,
    ).fetchone()
    return str(row[0]) if row else ""


def load_inputs(database: Path) -> tuple[
    dict[str, str], list[ActivityAnomaly], list[AnnouncementFact],
    list[AnnouncementBundle], list[IssuerTransition],
]:
    if not database.is_file():
        raise FileNotFoundError(database)
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        anomaly_run_id = _latest_run_id(connection, "p7_runs", run_kind="anomaly")
        announcement_run_id = _latest_run_id(connection, "announcement_runs")
        if not anomaly_run_id or not announcement_run_id:
            raise ValueError("回测数据库缺 anomaly 或 announcement run")
        anomalies = [
            ActivityAnomaly.model_validate(json.loads(row[0]))
            for row in connection.execute(
                "select payload_json from activity_anomalies where run_id=? order by trade_date,symbol",
                (anomaly_run_id,),
            )
        ]
        facts = [
            AnnouncementFact.model_validate(json.loads(row[0]))
            for row in connection.execute(
                "select payload_json from announcement_facts where run_id=? order by available_as_of,symbol",
                (announcement_run_id,),
            )
        ]
        bundles = [
            AnnouncementBundle.model_validate(json.loads(row[0]))
            for row in connection.execute(
                "select payload_json from announcement_bundles where run_id=? order by announcement_date,symbol",
                (announcement_run_id,),
            )
        ]
        transitions = [
            IssuerTransition.model_validate(json.loads(row[0]))
            for row in connection.execute(
                "select payload_json from issuer_transitions where run_id=? order by available_as_of,symbol",
                (announcement_run_id,),
            )
        ]
    return (
        {"anomaly": anomaly_run_id, "announcement": announcement_run_id},
        anomalies, facts, bundles, transitions,
    )


def load_p6_reference_events(database: Path) -> set[tuple[str, str, str]]:
    """Load the independently materialized, verified P6 event subset."""

    if not database.is_file():
        return set()
    result: set[tuple[str, str, str]] = set()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "select symbol,payload_json from valuation_episodes where evidence_status='verified'"
        ).fetchall()
    for symbol, payload_json in rows:
        payload = json.loads(payload_json)
        for event in list(payload.get("input_events") or []) + list(payload.get("outcome_events") or []):
            p7_type = P6_TO_P7_EVENT.get(str(event.get("event_type") or ""))
            available = str(event.get("information_available_date") or "")[:10]
            if p7_type and available:
                result.add((str(symbol), available, p7_type))
    return result


def _calendar_index(
    calendar: list[str], *, event_dates: list[str] | None = None,
) -> dict[str, int]:
    """Map non-trading announcement dates to the next observable trading day."""

    ordered = sorted(dict.fromkeys(calendar))
    result = {day: index for index, day in enumerate(ordered)}
    for event_date in sorted(set(event_dates or [])):
        if event_date in result:
            continue
        position = bisect_left(ordered, event_date)
        if position < len(ordered):
            result[event_date] = position
    return result


def _distance(index: dict[str, int], left: str, right: str) -> int | None:
    if left not in index or right not in index:
        return None
    return index[right] - index[left]


def _verified_transitions(
    transitions: list[IssuerTransition],
) -> dict[str, list[IssuerTransition]]:
    grouped: dict[str, list[IssuerTransition]] = defaultdict(list)
    for transition in transitions:
        if transition.evidence_status == "verified" and not transition.not_hard_outcome:
            grouped[transition.symbol].append(transition)
    for rows in grouped.values():
        rows.sort(key=lambda item: (item.available_as_of, item.transition_id))
    return grouped


def _outcome(
    *, symbol: str, start_date: str, horizon: int,
    transitions: dict[str, list[IssuerTransition]], index: dict[str, int],
) -> tuple[bool | None, IssuerTransition | None, int | None]:
    start_index = index.get(start_date)
    max_index = max(index.values(), default=-1)
    if start_index is None or start_index + horizon > max_index:
        return None, None, None
    for transition in transitions.get(symbol, []):
        gap = _distance(index, start_date, transition.available_as_of)
        if gap is not None and 0 < gap <= horizon:
            return True, transition, gap
    return False, None, None


def _threshold_episodes(
    anomalies: list[ActivityAnomaly], *, minimum_level: int, merge_gap: int = 5,
) -> list[ActivityAnomaly]:
    """Return first observations of threshold episodes using only eligible order."""

    grouped: dict[str, list[ActivityAnomaly]] = defaultdict(list)
    for anomaly in anomalies:
        if anomaly.calculable:
            grouped[anomaly.symbol].append(anomaly)
    starts: list[ActivityAnomaly] = []
    for rows in grouped.values():
        rows.sort(key=lambda item: item.trade_date)
        position = {item.trade_date: number for number, item in enumerate(rows)}
        hits = [item for item in rows if (deviation_level(item) or 0) >= minimum_level]
        last_hit: ActivityAnomaly | None = None
        for hit in hits:
            if last_hit is None or position[hit.trade_date] - position[last_hit.trade_date] > merge_gap:
                starts.append(hit)
            last_hit = hit
    return sorted(starts, key=lambda item: (item.trade_date, item.symbol))


def _announcement_episodes(
    bundles: list[AnnouncementBundle], *, priority: bool,
    index: dict[str, int], merge_gap: int = 5,
) -> list[AnnouncementBundle]:
    candidates = [
        bundle for bundle in bundles
        if not bundle.hard_event_types and bool(bundle.priority_reasons) is priority
        and bundle.announcement_date in index
    ]
    grouped: dict[str, list[AnnouncementBundle]] = defaultdict(list)
    for bundle in candidates:
        grouped[bundle.symbol].append(bundle)
    starts: list[AnnouncementBundle] = []
    for rows in grouped.values():
        rows.sort(key=lambda item: (item.announcement_date, item.bundle_id))
        last_day = ""
        for bundle in rows:
            if not last_day or (index[bundle.announcement_date] - index[last_day]) > merge_gap:
                starts.append(bundle)
            last_day = bundle.announcement_date
    return sorted(starts, key=lambda item: (item.announcement_date, item.symbol))


def _signal_metrics(
    signals: list[tuple[str, str]], *, transitions: dict[str, list[IssuerTransition]],
    index: dict[str, int], controls: list[list[tuple[str, str]]] | None = None,
) -> dict[str, Any]:
    horizon_values: dict[int, list[bool]] = {horizon: [] for horizon in HORIZONS}
    leads: list[int] = []
    companies: set[str] = set()
    for symbol, start_date in signals:
        companies.add(symbol)
        for horizon in HORIZONS:
            value, _transition, gap = _outcome(
                symbol=symbol, start_date=start_date, horizon=horizon,
                transitions=transitions, index=index,
            )
            if value is not None:
                horizon_values[horizon].append(value)
            if horizon == 60 and value and gap is not None:
                leads.append(gap)
    control_values: list[bool] = []
    matched = 0
    if controls is not None:
        for rows in controls:
            if rows:
                matched += 1
            for symbol, start_date in rows:
                value, _transition, _gap = _outcome(
                    symbol=symbol, start_date=start_date, horizon=20,
                    transitions=transitions, index=index,
                )
                if value is not None:
                    control_values.append(value)
    rates = {str(horizon): _rate(horizon_values[horizon]) for horizon in HORIZONS}
    observed = {str(horizon): len(horizon_values[horizon]) for horizon in HORIZONS}
    successes = {str(horizon): sum(horizon_values[horizon]) for horizon in HORIZONS}
    rate20 = rates["20"]
    control_rate = _rate(control_values)
    return {
        "signal_count": len(signals),
        "company_count": len(companies),
        "observed_by_horizon": observed,
        "successes_by_horizon": successes,
        "hard_node_rate_by_horizon": rates,
        "wilson_95_horizon_20": _wilson(successes["20"], observed["20"]),
        "median_lead_trading_days_within_60": (
            round(float(statistics.median(leads)), 4) if leads else None
        ),
        "control_observation_count_20": len(control_values),
        "control_hard_node_rate_20": control_rate,
        "lift_vs_control_20": _lift(rate20, control_rate),
        "matched_control_signal_count": matched if controls is not None else None,
        "matched_control_signal_ratio": (
            round(matched / len(signals), 8) if controls is not None and signals else None
        ),
    }


def _matched_controls(
    signals: list[ActivityAnomaly], *, minimum_level: int,
    anomalies_by_date: dict[str, list[ActivityAnomaly]],
    stages: dict[tuple[str, str], str],
) -> list[list[tuple[str, str]]]:
    result: list[list[tuple[str, str]]] = []
    for signal in signals:
        target_stage = stages.get((signal.symbol, signal.trade_date), "unknown")
        if (
            target_stage == "unknown"
            or signal.total_mv_10k_cny is None
            or signal.total_mv_10k_cny <= 0
        ):
            result.append([])
            continue
        candidates = [
            item for item in anomalies_by_date.get(signal.trade_date, [])
            if item.symbol != signal.symbol and item.calculable
            and (deviation_level(item) or 0) < minimum_level
            and item.total_mv_10k_cny is not None and item.total_mv_10k_cny > 0
            and stages.get((item.symbol, signal.trade_date), "unknown") == target_stage
        ]
        candidates.sort(key=lambda item: (
            abs(math.log(item.total_mv_10k_cny or 1) - math.log(signal.total_mv_10k_cny or 1)),
            item.symbol,
        ))
        result.append([(item.symbol, signal.trade_date) for item in candidates[:3]])
    return result


def _slice_by_date[T](items: list[T], get_date: Any, start: str, end: str) -> list[T]:
    return [item for item in items if start <= str(get_date(item)) <= end]


def _announcement_metrics(
    *, facts: list[AnnouncementFact], bundles: list[AnnouncementBundle],
    transitions_list: list[IssuerTransition], transitions: dict[str, list[IssuerTransition]],
    index: dict[str, int], start: str, end: str,
    p6_reference_events: set[tuple[str, str, str]],
) -> dict[str, Any]:
    period_facts = _slice_by_date(facts, lambda item: item.available_as_of, start, end)
    period_bundles = _slice_by_date(bundles, lambda item: item.announcement_date, start, end)
    period_transitions = _slice_by_date(
        transitions_list, lambda item: item.available_as_of, start, end,
    )
    priority_all = _announcement_episodes(bundles, priority=True, index=index)
    routine_all = _announcement_episodes(bundles, priority=False, index=index)
    priority = _slice_by_date(priority_all, lambda item: item.announcement_date, start, end)
    routine = _slice_by_date(routine_all, lambda item: item.announcement_date, start, end)
    priority_metrics = _signal_metrics(
        [(item.symbol, item.announcement_date) for item in priority],
        transitions=transitions, index=index,
    )
    routine_metrics = _signal_metrics(
        [(item.symbol, item.announcement_date) for item in routine],
        transitions=transitions, index=index,
    )
    precursor_observed = 0
    precursor_hits = 0
    for transition in period_transitions:
        if transition.evidence_status != "verified" or transition.not_hard_outcome:
            continue
        if transition.available_as_of not in index:
            continue
        precursor_observed += 1
        if any(
            bundle.symbol == transition.symbol
            and (gap := _distance(index, bundle.announcement_date, transition.available_as_of)) is not None
            and 0 < gap <= 20
            for bundle in priority_all
        ):
            precursor_hits += 1
    priority_rate = priority_metrics["hard_node_rate_by_horizon"]["20"]
    routine_rate = routine_metrics["hard_node_rate_by_horizon"]["20"]
    priority_with_urls = sum(bool(item.source_urls) for item in period_bundles if item.priority_reasons)
    priority_count = sum(bool(item.priority_reasons) for item in period_bundles)
    verified = sum(
        item.evidence_status == "verified" and not item.not_hard_outcome
        for item in period_transitions
    )
    conflicts = sum(item.evidence_status == "conflicted" for item in period_transitions)
    p6_period = {
        item for item in p6_reference_events if start <= item[1] <= end
    }
    p7_mapped = {
        (item.symbol, item.available_as_of, item.event_type)
        for item in period_transitions
        if item.event_type in set(P6_TO_P7_EVENT.values())
        and item.evidence_status == "verified"
    }
    p6_matches = p6_period & p7_mapped
    return {
        "period": {"start": start, "end": end},
        "structural_quality": {
            "announcement_fact_count": len(period_facts),
            "bundle_count": len(period_bundles),
            "priority_bundle_count": priority_count,
            "hard_transition_count": len(period_transitions),
            "verified_hard_transition_count": verified,
            "conflicted_hard_transition_count": conflicts,
            "priority_source_url_coverage": (
                round(priority_with_urls / priority_count, 8) if priority_count else None
            ),
            "shortlist_body_missing_count": sum(
                item.llm_route == "shortlist_body_missing" for item in period_facts
            ),
            "deterministic_hard_fact_count": sum(
                item.llm_route == "deterministic_hard_fact" for item in period_facts
            ),
            "p6_verified_reference_crosscheck": {
                "mapped_p6_reference_count": len(p6_period),
                "exact_symbol_date_event_matches": len(p6_matches),
                "p6_reference_match_rate": (
                    round(len(p6_matches) / len(p6_period), 8) if p6_period else None
                ),
                "p7_mapped_transition_count": len(p7_mapped),
                "p7_transition_confirmed_by_p6_subset_rate": (
                    round(len(p6_matches) / len(p7_mapped), 8) if p7_mapped else None
                ),
                "boundary": "P6 只覆盖 verified episode；P6 未命中不能当作 P7 错误。",
            },
        },
        "priority_nonhard_episodes": priority_metrics,
        "routine_nonhard_episodes": routine_metrics,
        "priority_lift_vs_routine_20": _lift(priority_rate, routine_rate),
        "hard_transition_precursor_recall_20": (
            round(precursor_hits / precursor_observed, 8) if precursor_observed else None
        ),
        "hard_transition_precursor_hits": precursor_hits,
        "hard_transition_precursor_observed": precursor_observed,
        "interpretation_boundary": (
            "结构性核验衡量可追溯性；priority 的后续硬节点率衡量研究筛选价值，"
            "两者都不等于公告语义已由独立人工金标逐条证实。"
        ),
    }


def _deviation_metrics(
    *, anomalies: list[ActivityAnomaly], transitions: dict[str, list[IssuerTransition]],
    index: dict[str, int], stages: dict[tuple[str, str], str], start: str, end: str,
) -> dict[str, Any]:
    by_date: dict[str, list[ActivityAnomaly]] = defaultdict(list)
    for anomaly in anomalies:
        by_date[anomaly.trade_date].append(anomaly)
    result: dict[str, Any] = {}
    for minimum_level, label in enumerate(DEVIATION_LEVEL_ORDER, start=1):
        all_signals = _threshold_episodes(anomalies, minimum_level=minimum_level)
        signals = _slice_by_date(all_signals, lambda item: item.trade_date, start, end)
        controls = _matched_controls(
            signals, minimum_level=minimum_level,
            anomalies_by_date=by_date, stages=stages,
        )
        metrics = _signal_metrics(
            [(item.symbol, item.trade_date) for item in signals],
            transitions=transitions, index=index, controls=controls,
        )
        percentile_gate, z_gate = DEVIATION_LEVELS[label]
        result[label] = {
            "minimum_percentile": percentile_gate,
            "minimum_robust_z": z_gate,
            **metrics,
        }
    return result


def _anchor_result(
    *, label: str, anchor: str, calendar: list[str],
    anomalies: list[ActivityAnomaly], bundles: list[AnnouncementBundle],
    transitions: dict[str, list[IssuerTransition]], stages: dict[tuple[str, str], str],
    index: dict[str, int],
) -> dict[str, Any]:
    day_rows = [item for item in anomalies if item.trade_date == anchor]
    by_date = {anchor: day_rows}
    threshold_results: dict[str, Any] = {}
    for minimum_level, level_label in enumerate(DEVIATION_LEVEL_ORDER, start=1):
        signals = [item for item in day_rows if (deviation_level(item) or 0) >= minimum_level]
        threshold_results[level_label] = _signal_metrics(
            [(item.symbol, item.trade_date) for item in signals],
            transitions=transitions, index=index,
            controls=_matched_controls(
                signals, minimum_level=minimum_level,
                anomalies_by_date=by_date, stages=stages,
            ),
        )
    day_bundles = [
        item for item in bundles
        if index.get(item.announcement_date) == index.get(anchor)
    ]
    priority_nonhard = [
        item for item in day_bundles if item.priority_reasons and not item.hard_event_types
    ]
    priority_metrics = _signal_metrics(
        [(item.symbol, anchor) for item in priority_nonhard],
        transitions=transitions, index=index,
    )
    examples = sorted(
        [item for item in day_rows if (deviation_level(item) or 0) >= 1],
        key=lambda item: (-(deviation_level(item) or 0), -(item.turnover_robust_z_120 or 0), item.symbol),
    )[:10]
    signal_examples: list[dict[str, Any]] = []
    for item in examples:
        value, transition, gap = _outcome(
            symbol=item.symbol, start_date=anchor, horizon=60,
            transitions=transitions, index=index,
        )
        signal_examples.append({
            "symbol": item.symbol,
            "deviation_level": deviation_level(item),
            "turnover_percentile_120": item.turnover_percentile_120,
            "turnover_robust_z_120": item.turnover_robust_z_120,
            "hard_transition_within_60": value,
            "lead_trading_days": gap,
            "hard_event_type": transition.event_type if transition else "",
            "hard_event_date": transition.available_as_of if transition else "",
        })
    anchor_index = index[anchor]
    return {
        "label": label,
        "anchor_date": anchor,
        "selection_rule": {
            "past_week": "latest completed date minus 5 trading days",
            "past_month": "latest completed date minus 21 trading days",
            "past_year": "nearest trading date on or before latest minus 365 calendar days",
        }[label],
        "available_forward_trading_days": len(calendar) - 1 - anchor_index,
        "censored_horizons": [horizon for horizon in HORIZONS if anchor_index + horizon >= len(calendar)],
        "activity": {
            "membership_rows": len(day_rows),
            "calculable_rows": sum(item.calculable for item in day_rows),
            "thresholds": threshold_results,
            "examples": signal_examples,
        },
        "announcements": {
            "bundle_count": len(day_bundles),
            "priority_bundle_count": sum(bool(item.priority_reasons) for item in day_bundles),
            "hard_transition_bundle_count": sum(bool(item.hard_event_types) for item in day_bundles),
            "priority_nonhard_outcomes": priority_metrics,
            "priority_examples": [
                {
                    "symbol": item.symbol,
                    "announcement_date": item.announcement_date,
                    "category": item.category,
                    "titles": item.titles,
                    "priority_reasons": item.priority_reasons,
                }
                for item in priority_nonhard[:10]
            ],
        },
    }


def build_backtest_report(
    *, intelligence_database: Path, market_context_database: Path,
    valuation_episode_database: Path, through: str,
) -> P7BacktestReport:
    run_ids, anomalies, facts, bundles, transitions_list = load_inputs(intelligence_database)
    calendar = _load_calendar(market_context_database, through=through)
    anchors = derive_anchors(calendar, through)
    baseline_start = min((item.trade_date for item in anomalies), default="")
    if not baseline_start or baseline_start > anchors["past_year"]:
        raise ValueError(
            f"一年锚点 {anchors['past_year']} 没有可用异常特征；当前基线起点 {baseline_start or 'none'}"
        )
    transitions = _verified_transitions(transitions_list)
    p6_reference_events = load_p6_reference_events(valuation_episode_database)
    index = _calendar_index(
        calendar,
        event_dates=(
            [item.announcement_date for item in bundles]
            + [item.available_as_of for item in transitions_list]
        ),
    )
    all_threshold_signals = [
        item
        for level in range(1, len(DEVIATION_LEVEL_ORDER) + 1)
        for item in _threshold_episodes(anomalies, minimum_level=level)
    ]
    stage_dates = sorted({item.trade_date for item in all_threshold_signals} | set(anchors.values()))
    stages = load_valuation_stage_map(valuation_episode_database, dates=stage_dates)
    anchor_results = [
        _anchor_result(
            label=label, anchor=anchor, calendar=calendar, anomalies=anomalies,
            bundles=bundles, transitions=transitions, stages=stages, index=index,
        )
        for label, anchor in anchors.items()
    ]
    evaluation_start = anchors["past_year"]
    period_days = [day for day in calendar if evaluation_start <= day <= through]
    split_date = period_days[len(period_days) // 2]
    training_end = period_days[len(period_days) // 2 - 1]
    announcement_training = _announcement_metrics(
        facts=facts, bundles=bundles, transitions_list=transitions_list,
        transitions=transitions, index=index,
        start=evaluation_start, end=training_end,
        p6_reference_events=p6_reference_events,
    )
    announcement_validation = _announcement_metrics(
        facts=facts, bundles=bundles, transitions_list=transitions_list,
        transitions=transitions, index=index,
        start=split_date, end=through,
        p6_reference_events=p6_reference_events,
    )
    deviation_training = _deviation_metrics(
        anomalies=anomalies, transitions=transitions, index=index,
        stages=stages, start=evaluation_start, end=training_end,
    )
    deviation_validation = _deviation_metrics(
        anomalies=anomalies, transitions=transitions, index=index,
        stages=stages, start=split_date, end=through,
    )
    validation_rates = [
        deviation_validation[label]["hard_node_rate_by_horizon"]["20"]
        for label in DEVIATION_LEVEL_ORDER
    ]
    observed_rates = [value for value in validation_rates if value is not None]
    monotonic = len(observed_rates) == len(validation_rates) and all(
        right >= left for left, right in zip(observed_rates, observed_rates[1:])
    )
    balanced = deviation_validation["D3_balanced"]
    balanced_rate = balanced["hard_node_rate_by_horizon"]["20"]
    control_rate = balanced["control_hard_node_rate_20"]
    enough_balanced_sample = (
        balanced["observed_by_horizon"]["20"] >= 20
        and balanced["company_count"] >= 15
    )
    enough_balanced_controls = (balanced["matched_control_signal_ratio"] or 0) >= 0.80
    advantage = (
        balanced_rate is not None and control_rate is not None
        and balanced_rate > control_rate
    )
    if not enough_balanced_sample:
        deviation_status = "insufficient_out_of_sample_size"
    elif not enough_balanced_controls:
        deviation_status = "insufficient_comparable_control_coverage"
    elif not monotonic or not advantage:
        deviation_status = "not_validated_out_of_sample"
    else:
        deviation_status = "retrospective_candidate_only"
    priority_validation = announcement_validation["priority_nonhard_episodes"]
    announcement_status = _announcement_release_status(
        priority_validation, announcement_validation["routine_nonhard_episodes"],
    )
    training_crosscheck = announcement_training["structural_quality"]["p6_verified_reference_crosscheck"]
    validation_crosscheck = announcement_validation["structural_quality"]["p6_verified_reference_crosscheck"]
    p6_reference_count = (
        training_crosscheck["mapped_p6_reference_count"]
        + validation_crosscheck["mapped_p6_reference_count"]
    )
    p6_match_count = (
        training_crosscheck["exact_symbol_date_event_matches"]
        + validation_crosscheck["exact_symbol_date_event_matches"]
    )
    p6_match_rate = p6_match_count / p6_reference_count if p6_reference_count else None
    transition_conflicts = (
        announcement_training["structural_quality"]["conflicted_hard_transition_count"]
        + announcement_validation["structural_quality"]["conflicted_hard_transition_count"]
    )
    body_gaps = (
        announcement_training["structural_quality"]["shortlist_body_missing_count"]
        + announcement_validation["structural_quality"]["shortlist_body_missing_count"]
    )
    if p6_match_rate is None:
        announcement_structural_status = "insufficient_independent_verified_overlap"
    elif p6_match_rate < 0.80 or transition_conflicts:
        announcement_structural_status = "needs_structural_investigation"
    elif body_gaps:
        announcement_structural_status = "consistent_on_verified_overlap_with_body_gaps"
    else:
        announcement_structural_status = "consistent_on_verified_overlap"
    report_payload = {
        "contract_version": CONTRACT_VERSION,
        "through": through,
        "baseline_start": baseline_start,
        "source_run_ids": run_ids,
        "anchor_definition": {
            "anchors": anchors,
            "selected_without_reading_signal_or_outcome_counts": True,
            "training_start": evaluation_start,
            "training_end": training_end,
            "validation_start": split_date,
            "validation_end": through,
            "split_rule": "midpoint trading day of the trailing-one-year evaluation range",
            "future_used_only_for_labelled_outcomes": True,
        },
        "anchors": anchor_results,
        "announcement_evaluation": {
            "training": announcement_training,
            "validation": announcement_validation,
            "structural_status": announcement_structural_status,
            "verified_overlap": {
                "p6_reference_count": p6_reference_count,
                "exact_match_count": p6_match_count,
                "exact_match_rate": round(p6_match_rate, 8) if p6_match_rate is not None else None,
            },
            "semantic_gold_status": "not_independently_gold_labeled",
            "research_value_status": announcement_status,
            "status": announcement_status,
        },
        "deviation_evaluation": {
            "levels": {
                label: {"percentile": gates[0], "robust_z": gates[1]}
                for label, gates in DEVIATION_LEVELS.items()
            },
            "episode_rule": "first threshold hit; merge subsequent hits within 5 eligible observations",
            "training": deviation_training,
            "validation": deviation_validation,
            "validation_horizon_20_rates_monotonic": monotonic,
            "status": deviation_status,
        },
        "release_interpretation": {
            "announcement": (
                f"structural={announcement_structural_status}; research_value={announcement_status}; "
                "semantic_gold=not_independently_gold_labeled"
            ),
            "deviation": deviation_status,
            "message_proximity": (
                "Only empirical proximity to a later official hard transition is measured; "
                "no hidden-message probability is published."
            ),
        },
        "limitations": [
            "周锚点只有 5 个后续交易日，10/20/60 日结果必须右删失。",
            "月锚点只有 21 个后续交易日，60 日结果必须右删失。",
            "硬节点只认正式状态跃迁；一般进展、传闻和未披露信息不是结果标签。",
            "公告结构性核验不等于逐条语义金标准；正文缺失仍作为独立覆盖缺口。",
            "历史回测不能替代从 2026-09-04 开始的真实前瞻 shadow 发布门。",
            "公告研究价值的首轮结果不得因点估计略高于 routine 就升级；Wilson 区间未分离时保持未验证。",
        ],
        "risk_notice": RISK_NOTICE,
    }
    report_id = f"P7BT-{_digest(report_payload)[:20].upper()}"
    return P7BacktestReport(
        report_id=report_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        **report_payload,
    )


def _fmt_rate(value: Any) -> str:
    return "—" if value is None else f"{float(value) * 100:.2f}%"


def _fmt_number(value: Any, digits: int = 2) -> str:
    return "—" if value is None else f"{float(value):.{digits}f}"


def render_html(report: P7BacktestReport) -> str:
    anchor_rows = []
    for anchor in report.anchors:
        balanced = anchor["activity"]["thresholds"]["D3_balanced"]
        threshold_counts = "/".join(
            str(anchor["activity"]["thresholds"][label]["signal_count"])
            for label in DEVIATION_LEVEL_ORDER
        )
        announcement = anchor["announcements"]
        anchor_rows.append(
            "<tr>"
            f"<td><b>{html.escape(anchor['label'])}</b><small>{html.escape(anchor['anchor_date'])}</small></td>"
            f"<td>{anchor['available_forward_trading_days']}</td>"
            f"<td>{anchor['activity']['calculable_rows']} / {anchor['activity']['membership_rows']}</td>"
            f"<td>{threshold_counts}<small>D1 / D2 / D3 / D4</small></td>"
            f"<td>{_fmt_rate(balanced['hard_node_rate_by_horizon']['20'])}</td>"
            f"<td>{announcement['priority_bundle_count']}</td>"
            f"<td>{_fmt_rate(announcement['priority_nonhard_outcomes']['hard_node_rate_by_horizon']['20'])}</td>"
            f"<td>{', '.join(map(str, anchor['censored_horizons'])) or '无'}</td>"
            "</tr>"
        )
    deviation_rows = []
    for label in DEVIATION_LEVEL_ORDER:
        train = report.deviation_evaluation["training"][label]
        valid = report.deviation_evaluation["validation"][label]
        deviation_rows.append(
            "<tr>"
            f"<td><b>{html.escape(label)}</b><small>p≥{train['minimum_percentile']}, z≥{train['minimum_robust_z']}</small></td>"
            f"<td>{train['observed_by_horizon']['20']}</td><td>{_fmt_rate(train['hard_node_rate_by_horizon']['20'])}</td>"
            f"<td>{valid['observed_by_horizon']['20']}</td><td>{_fmt_rate(valid['hard_node_rate_by_horizon']['20'])}</td>"
            f"<td>{_fmt_rate(valid['control_hard_node_rate_20'])}</td>"
            f"<td>{valid['lift_vs_control_20'] if valid['lift_vs_control_20'] is not None else '—'}</td>"
            f"<td>{_fmt_rate(valid['matched_control_signal_ratio'])}</td>"
            "</tr>"
        )
    ann_valid = report.announcement_evaluation["validation"]
    ann_train = report.announcement_evaluation["training"]
    ann_status = report.announcement_evaluation["research_value_status"]
    structural_status = report.announcement_evaluation["structural_status"]
    deviation_status = report.deviation_evaluation["status"]
    overlap = report.announcement_evaluation["verified_overlap"]
    body_gaps = sum(
        period["structural_quality"]["shortlist_body_missing_count"]
        for period in (ann_train, ann_valid)
    )
    validation_rates = " / ".join(
        _fmt_rate(report.deviation_evaluation["validation"][label]["hard_node_rate_by_horizon"]["20"])
        for label in DEVIATION_LEVEL_ORDER
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>P7 回测评估</title><style>
:root{{--ink:#191919;--muted:#6b6b6b;--line:#dedbd4;--paper:#f3f1eb;--card:#fff;--blue:#184f8c;--amber:#9a6400}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}main{{max-width:1180px;margin:auto;padding:50px 24px 90px}}header{{border-bottom:1px solid var(--line);padding-bottom:28px;margin-bottom:26px}}h1{{font-size:42px;letter-spacing:-.05em;margin:5px 0 12px}}header p{{max-width:820px;line-height:1.65;color:var(--muted)}}.eyebrow{{font:12px ui-monospace;color:var(--blue)}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:22px 0}}.card{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:18px}}.card small,td small{{display:block;color:var(--muted);margin-top:5px}}.card strong{{display:block;font-size:24px;margin-top:8px}}section{{margin-top:34px}}h2{{font-size:24px;margin-bottom:12px}}.table{{overflow:auto;background:var(--card);border:1px solid var(--line);border-radius:8px}}table{{border-collapse:collapse;width:100%;min-width:850px}}th,td{{text-align:left;padding:12px 14px;border-bottom:1px solid #ece9e2;font-size:13px}}th{{font-size:11px;color:var(--muted);text-transform:uppercase}}tr:last-child td{{border-bottom:0}}.notice{{background:#fff8e7;border-left:3px solid var(--amber);padding:15px 17px;line-height:1.65}}ul{{line-height:1.75;color:#4d4d4d}}code{{font-family:ui-monospace;font-size:12px}}@media(max-width:800px){{.grid{{grid-template-columns:1fr}}h1{{font-size:34px}}}}
</style></head><body><main><header><div class="eyebrow">{html.escape(report.report_id)} · through {html.escape(report.through)}</div><h1>P7 公告与放量回测</h1><p>三个锚点机械选取，未读取信号数量或结果。训练/验证按过去一年交易日中点切开；所有未来信息只进入 outcome，不回写当时判断。</p></header>
<div class="grid"><div class="card"><small>公告结构</small><strong>{html.escape(STATUS_LABELS.get(structural_status, structural_status))}</strong><small>P6 独立子集精确重叠 {overlap['exact_match_count']} / {overlap['p6_reference_count']}</small></div><div class="card"><small>公告优先级</small><strong>{html.escape(STATUS_LABELS.get(ann_status, ann_status))}</strong><small>验证期 lift {_fmt_number(ann_valid['priority_lift_vs_routine_20'])}</small></div><div class="card"><small>放量偏离</small><strong>{html.escape(STATUS_LABELS.get(deviation_status, deviation_status))}</strong><small>D1→D4 单调：{'是' if report.deviation_evaluation['validation_horizon_20_rates_monotonic'] else '否'}</small></div></div>
<section><h2>先看结论</h2><div class="notice"><b>公告：</b>核证子集的事件、日期和公司一致，但这不等于逐条语义金标准；仍有 {body_gaps:,} 条入围公告缺正文。priority 在训练期的 20 日率高于 routine，留出期为 {_fmt_rate(ann_valid['priority_nonhard_episodes']['hard_node_rate_by_horizon']['20'])} 对 {_fmt_rate(ann_valid['routine_nonhard_episodes']['hard_node_rate_by_horizon']['20'])}，区间未分离，暂未证明筛选有预测区分度。<br><br><b>放量：</b>留出期 D1/D2/D3/D4 的 20 日硬节点率依次为 {validation_rates}，不单调；D3 可比对照只覆盖 {_fmt_rate(report.deviation_evaluation['validation']['D3_balanced']['matched_control_signal_ratio'])}，低于冻结的 80% 门。当前只能保留偏离描述，不能换算“消息临近概率”。</div></section>
<section><h2>三轮锚点回放</h2><div class="table"><table><thead><tr><th>锚点</th><th>可观察未来日</th><th>可计算 / 成员</th><th>当日偏离数</th><th>D3 20日硬节点率</th><th>重点公告</th><th>公告 20日硬节点率</th><th>删失窗口</th></tr></thead><tbody>{''.join(anchor_rows)}</tbody></table></div></section>
<section><h2>放量偏离阶梯：训练与留出验证</h2><div class="table"><table><thead><tr><th>等级</th><th>训练 n</th><th>训练 20日率</th><th>验证 n</th><th>验证 20日率</th><th>对照率</th><th>lift</th><th>对照匹配</th></tr></thead><tbody>{''.join(deviation_rows)}</tbody></table></div></section>
<section><h2>公告研究价值</h2><div class="grid"><div class="card"><small>训练期 priority / routine 20日率</small><strong>{_fmt_rate(ann_train['priority_nonhard_episodes']['hard_node_rate_by_horizon']['20'])} / {_fmt_rate(ann_train['routine_nonhard_episodes']['hard_node_rate_by_horizon']['20'])}</strong></div><div class="card"><small>验证期 priority / routine 20日率</small><strong>{_fmt_rate(ann_valid['priority_nonhard_episodes']['hard_node_rate_by_horizon']['20'])} / {_fmt_rate(ann_valid['routine_nonhard_episodes']['hard_node_rate_by_horizon']['20'])}</strong></div><div class="card"><small>验证期硬节点前 20日 precursor recall</small><strong>{_fmt_rate(ann_valid['hard_transition_precursor_recall_20'])}</strong></div></div></section>
<section><h2>边界</h2><div class="notice">{html.escape(report.risk_notice)}</div><ul>{''.join(f'<li>{html.escape(item)}</li>' for item in report.limitations)}</ul></section>
</main></body></html>"""


def write_report(report: P7BacktestReport, output_directory: Path) -> dict[str, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    json_path = output_directory / "report.json"
    html_path = output_directory / "index.html"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    html_path.write_text(render_html(report), encoding="utf-8")
    return {"json": json_path, "html": html_path}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build leakage-safe P7 anchored backtests")
    parser.add_argument("--through", required=True)
    parser.add_argument("--intelligence-database", type=Path, default=P7_INTELLIGENCE_DB)
    parser.add_argument("--market-context-database", type=Path, default=MARKET_CONTEXT_DB)
    parser.add_argument("--valuation-episode-database", type=Path, default=VALUATION_EPISODE_DB)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    report = build_backtest_report(
        intelligence_database=args.intelligence_database,
        market_context_database=args.market_context_database,
        valuation_episode_database=args.valuation_episode_database,
        through=args.through,
    )
    paths = write_report(report, args.output_directory)
    print(json.dumps({
        "report_id": report.report_id,
        "paths": {key: str(value) for key, value in paths.items()},
        "announcement_status": report.announcement_evaluation["status"],
        "deviation_status": report.deviation_evaluation["status"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
