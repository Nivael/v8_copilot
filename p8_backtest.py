"""Five-scorecard P8 retrospective evaluation with frozen, direction-separated outcomes."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sqlite3
import statistics
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from p8_event_graph import SPEC_BY_NODE
from p8_research import P8ResearchRepository, build_run, canonical_json, content_id
from p7_daily import load_valuation_stage_map
from settings import DATA_ROOT, MARKET_CONTEXT_DB, P8_RESEARCH_DB, VALUATION_EPISODE_DB


CONTRACT_VERSION = "v8_p8_backtest_v1"
HORIZONS = (5, 10, 20, 60)
SIGNAL_LABELS = {
    "persistent_activity_price_stable",
    "persistent_activity_price_down",
    "single_day_activity_price_jump",
}
DEFAULT_BASE_DB = DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class P8BacktestReport(StrictModel):
    record_id: str = Field(pattern=r"^P8BT-[A-F0-9]{20}$")
    contract_version: str = CONTRACT_VERSION
    start_date: str
    through: str
    source_run_ids: list[str]
    frozen_inputs: dict[str, Any]
    replay_anchors: dict[str, Any]
    extraction_scorecard: dict[str, Any]
    precursor_scorecard: dict[str, Any]
    activity_scorecard: dict[str, Any]
    scenario_reference_scorecard: dict[str, Any]
    funnel_scorecard: dict[str, Any]
    limitations: list[str]
    evidence_status: str = "descriptive_only"
    not_a_trading_signal: bool = True


def _connect_ro(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _calendar(path: Path, start_date: str, through: str) -> list[str]:
    with _connect_ro(path) as connection:
        return [str(row[0]) for row in connection.execute(
            "select trade_date from benchmark_daily where benchmark_id='csi_all_share' "
            "and trade_date between ? and ? order by trade_date", (start_date, through),
        )]


def _prices(path: Path, start_date: str, through: str) -> dict[str, list[tuple[str, float]]]:
    result: dict[str, list[tuple[str, float]]] = defaultdict(list)
    with _connect_ro(path) as connection:
        for row in connection.execute(
            "select symbol,trade_date,close from daily_prices where adjust='qfq' "
            "and trade_date between ? and ? and close>0 order by symbol,trade_date",
            (start_date, through),
        ):
            result[str(row[0])].append((str(row[1]), float(row[2])))
    return result


def _benchmarks(path: Path, start_date: str, through: str) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = defaultdict(dict)
    with _connect_ro(path) as connection:
        for row in connection.execute(
            "select benchmark_id,trade_date,close from benchmark_daily "
            "where benchmark_id in ('st_equal_weight_v1','csi_2000') "
            "and trade_date between ? and ? and close>0", (start_date, through),
        ):
            result[str(row[0])][str(row[1])] = float(row[2])
    return result


def _mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[int((len(ordered) - 1) * q)]


def _wilson(successes: int, observations: int) -> list[float] | None:
    if observations <= 0:
        return None
    z = 1.959963984540054
    p = successes / observations
    denominator = 1 + z * z / observations
    centre = (p + z * z / (2 * observations)) / denominator
    half = z * math.sqrt(p * (1 - p) / observations + z * z / (4 * observations * observations)) / denominator
    return [max(0.0, centre - half), min(1.0, centre + half)]


def _bootstrap_difference(
    rows: list[tuple[str, bool, float]], *, seed: int = 20260904, repetitions: int = 500,
) -> list[float] | None:
    grouped: dict[str, list[tuple[bool, float]]] = defaultdict(list)
    for cluster, signal, value in rows:
        grouped[cluster].append((signal, value))
    keys = sorted(grouped)
    if len(keys) < 5:
        return None
    generator = random.Random(seed)
    estimates: list[float] = []
    for _ in range(repetitions):
        sample = [generator.choice(keys) for _ in keys]
        signal_values = [value for key in sample for signal, value in grouped[key] if signal]
        control_values = [value for key in sample for signal, value in grouped[key] if not signal]
        if signal_values and control_values:
            estimates.append(statistics.mean(signal_values) - statistics.mean(control_values))
    return [_quantile(estimates, .025), _quantile(estimates, .975)] if estimates else None  # type: ignore[list-item]


def _entry_index(rows: list[tuple[str, float]], day: str) -> int | None:
    dates = [item[0] for item in rows]
    position = bisect_left(dates, day)
    return position if position < len(rows) else None


def _return_observation(
    *, symbol: str, day: str, horizon: int,
    prices: dict[str, list[tuple[str, float]]], benchmarks: dict[str, dict[str, float]],
) -> dict[str, Any]:
    rows = prices.get(symbol, [])
    entry = _entry_index(rows, day)
    target = entry + horizon if entry is not None else None
    if entry is None or target is None or target >= len(rows):
        return {"observed": False}
    start_day, start_price = rows[entry]
    end_day, end_price = rows[target]
    stock = end_price / start_price - 1 if start_price > 0 else None
    result: dict[str, Any] = {
        "observed": stock is not None, "entry_date": start_day,
        "exit_date": end_day, "stock_qfq_return": stock,
    }
    for benchmark_id, key in (("st_equal_weight_v1", "excess_return_st"), ("csi_2000", "excess_return_csi2000")):
        left = benchmarks[benchmark_id].get(start_day)
        right = benchmarks[benchmark_id].get(end_day)
        benchmark_return = right / left - 1 if left and right else None
        result[key] = stock - benchmark_return if stock is not None and benchmark_return is not None else None
    return result


def _event_outcomes(
    events: list[dict[str, Any]], calendar: list[str],
) -> dict[str, list[dict[str, Any]]]:
    calendar_index = {day: index for index, day in enumerate(calendar)}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if str(event.get("evidence_status")) not in {"body_verified", "deterministic_verified"}:
            continue
        day = str(event.get("available_as_of") or "")
        position = bisect_left(calendar, day)
        if position >= len(calendar):
            continue
        copy = dict(event)
        copy["calendar_index"] = position
        grouped[str(event.get("symbol") or "")].append(copy)
    for rows in grouped.values():
        rows.sort(key=lambda item: (item["calendar_index"], str(item.get("event_id"))))
    return grouped


def _next_outcome_counts(
    *, symbol: str, day: str, horizon: int, calendar: list[str],
    outcomes: dict[str, list[dict[str, Any]]],
) -> dict[str, int] | None:
    start = bisect_left(calendar, day)
    if start >= len(calendar) or start + horizon >= len(calendar):
        return None
    found = Counter()
    for event in outcomes.get(symbol, []):
        gap = int(event["calendar_index"]) - start
        if 0 < gap <= horizon:
            found[f"process_{event.get('process_direction') or 'unknown'}"] += 1
            effect = str(event.get("old_equity_effect") or "unknown")
            found[f"old_equity_{effect if effect in {'supportive','adverse'} else 'mixed_or_unknown'}"] += 1
    return dict(found)


def _episode_starts(features: list[dict[str, Any]], calendar: list[str]) -> list[dict[str, Any]]:
    index = {day: position for position, day in enumerate(calendar)}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in features:
        label = str(item.get("shape_label") or "unknown")
        if label in SIGNAL_LABELS and str(item.get("trade_date") or "") in index:
            grouped[(str(item.get("symbol") or ""), label)].append(item)
    starts: list[dict[str, Any]] = []
    for rows in grouped.values():
        rows.sort(key=lambda item: str(item["trade_date"]))
        last_index: int | None = None
        for item in rows:
            current = index[str(item["trade_date"])]
            if last_index is None or current - last_index > 5:
                starts.append(item)
            last_index = current
    return sorted(starts, key=lambda item: (str(item["trade_date"]), str(item["symbol"])))


def _activity_metrics(
    entries: list[dict[str, Any]], *, calendar: list[str],
    outcomes: dict[str, list[dict[str, Any]]],
    prices: dict[str, list[tuple[str, float]]], benchmarks: dict[str, dict[str, float]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for label in sorted(SIGNAL_LABELS):
        selected = [item for item in entries if item.get("shape_label") == label]
        horizon_metrics: dict[str, Any] = {}
        for horizon in HORIZONS:
            returns: list[dict[str, Any]] = []
            direction_rows: list[dict[str, int]] = []
            for item in selected:
                symbol, day = str(item["symbol"]), str(item["trade_date"])
                observation = _return_observation(
                    symbol=symbol, day=day, horizon=horizon,
                    prices=prices, benchmarks=benchmarks,
                )
                if observation.get("observed"):
                    returns.append(observation)
                directions = _next_outcome_counts(
                    symbol=symbol, day=day, horizon=horizon,
                    calendar=calendar, outcomes=outcomes,
                )
                if directions is not None:
                    direction_rows.append(directions)
            direction_keys = (
                "process_advance", "process_rollback", "old_equity_supportive",
                "old_equity_adverse", "old_equity_mixed_or_unknown",
            )
            horizon_metrics[str(horizon)] = {
                "completed_return_n": len(returns),
                "right_censored_return_n": len(selected) - len(returns),
                "median_stock_qfq_return": _median([float(item["stock_qfq_return"]) for item in returns if item.get("stock_qfq_return") is not None]),
                "median_excess_return_st": _median([float(item["excess_return_st"]) for item in returns if item.get("excess_return_st") is not None]),
                "median_excess_return_csi2000": _median([float(item["excess_return_csi2000"]) for item in returns if item.get("excess_return_csi2000") is not None]),
                "direction_observation_n": len(direction_rows),
                "direction_rates": {
                    key: (sum(bool(item.get(key)) for item in direction_rows) / len(direction_rows) if direction_rows else None)
                    for key in direction_keys
                },
                "direction_wilson_95": {
                    key: _wilson(sum(bool(item.get(key)) for item in direction_rows), len(direction_rows))
                    for key in direction_keys
                },
                "status": "descriptive_only" if len(returns) >= 30 else "insufficient_completed_observations",
            }
        result[label] = {
            "episode_count": len(selected),
            "company_count": len({str(item["symbol"]) for item in selected}),
            "by_horizon": horizon_metrics,
        }
    return result


def _control_uncertainty(
    entries: list[dict[str, Any]], features: list[dict[str, Any]], *,
    prices: dict[str, list[tuple[str, float]]],
    benchmarks: dict[str, dict[str, float]],
    stage_map: dict[tuple[str, str], str], horizon: int = 20,
) -> dict[str, Any]:
    def board(symbol: str) -> str:
        if symbol.startswith("300"):
            return "gem"
        if symbol.startswith("688"):
            return "star"
        if symbol.startswith(("8", "9")):
            return "bse"
        return "main"

    quiet_by_date_board: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    quiet_by_date_board_stage: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    quiet_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in features:
        if bool(item.get("calculable")) and item.get("shape_label") == "quiet":
            day, symbol = str(item["trade_date"]), str(item["symbol"])
            quiet_by_date_board[(day, board(symbol))].append(item)
            quiet_by_date[day].append(item)
            stage = stage_map.get((symbol, day), "unknown")
            if stage != "unknown":
                quiet_by_date_board_stage[(day, board(symbol), stage)].append(item)
    for rows in (
        list(quiet_by_date_board.values())
        + list(quiet_by_date.values())
        + list(quiet_by_date_board_stage.values())
    ):
        rows.sort(key=lambda item: str(item["symbol"]))

    rows: list[tuple[str, str, bool, float]] = []
    matched = 0
    match_types: Counter[str] = Counter()
    for item in entries:
        symbol, day = str(item["symbol"]), str(item["trade_date"])
        signal_observation = _return_observation(
            symbol=symbol, day=day, horizon=horizon,
            prices=prices, benchmarks=benchmarks,
        )
        signal_value = signal_observation.get("excess_return_st")
        if signal_value is None:
            continue
        stage = stage_map.get((symbol, day), "unknown")
        candidates = (
            quiet_by_date_board_stage.get((day, board(symbol), stage), [])
            if stage != "unknown" else []
        )
        match_type = "p6_or_body_verified_stage_same_day_board"
        if not candidates:
            candidates = quiet_by_date_board.get((day, board(symbol))) or quiet_by_date.get(day) or []
            match_type = "stage_free_same_day_board"
        candidates = [candidate for candidate in candidates if str(candidate["symbol"]) != symbol]
        if not candidates:
            continue
        target_mv = item.get("point_in_time_total_mv_10k_cny")
        with_mv = [candidate for candidate in candidates if candidate.get("point_in_time_total_mv_10k_cny") not in (None, 0)]
        if target_mv not in (None, 0) and with_mv:
            control = min(with_mv, key=lambda candidate: (
                abs(math.log(float(candidate["point_in_time_total_mv_10k_cny"])) - math.log(float(target_mv))),
                str(candidate["symbol"]),
            ))
            match_type += "_nearest_mv"
        else:
            selector = int(hashlib.sha256(f"{symbol}|{day}".encode()).hexdigest()[:12], 16)
            control = candidates[selector % len(candidates)]
            match_type += "_mv_unavailable"
        control_symbol = str(control["symbol"])
        control_observation = _return_observation(
            symbol=control_symbol, day=day, horizon=horizon,
            prices=prices, benchmarks=benchmarks,
        )
        control_value = control_observation.get("excess_return_st")
        if control_value is None:
            continue
        matched += 1
        match_types[match_type] += 1
        rows.append((symbol, day[:7], True, float(signal_value)))
        rows.append((control_symbol, day[:7], False, float(control_value)))
    signal_values = [value for _, _, signal, value in rows if signal]
    control_values = [value for _, _, signal, value in rows if not signal]
    paired_by_company = [(symbol, signal, value) for symbol, _month, signal, value in rows]
    paired_by_month = [(month, signal, value) for _symbol, month, signal, value in rows]
    return {
        "horizon": horizon,
        "signal_observation_n": len(signal_values),
        "quiet_control_observation_n": len(control_values),
        "matched_episode_count": matched,
        "matched_episode_ratio": matched / len(entries) if entries else None,
        "match_type_counts": dict(sorted(match_types.items())),
        "mean_excess_return_st_signal": _mean(signal_values),
        "mean_excess_return_st_quiet_control": _mean(control_values),
        "mean_difference": (
            statistics.mean(signal_values) - statistics.mean(control_values)
            if signal_values and control_values else None
        ),
        "company_cluster_bootstrap_95": _bootstrap_difference(paired_by_company),
        "calendar_month_block_bootstrap_95": _bootstrap_difference(paired_by_month, seed=20260905),
        "matching_status": "P6/body-verified stage first; stage-free same-day board fallback; nearest point-in-time MV when available",
        "status": "descriptive_only",
    }


def _replay_anchors(calendar: list[str], entries: list[dict[str, Any]], through: str) -> dict[str, Any]:
    if len(calendar) < 253:
        return {"status": "unavailable", "reason": "calendar_too_short"}
    positions = {
        "past_week": max(0, len(calendar) - 6),
        "past_month": max(0, len(calendar) - 22),
        "past_year": max(0, len(calendar) - 253),
    }
    result: dict[str, Any] = {}
    for label, position in positions.items():
        anchor = calendar[position]
        active = [item for item in entries if str(item.get("trade_date")) == anchor]
        result[label] = {
            "anchor_date": anchor,
            "elapsed_trading_days_to_through": len(calendar) - position - 1,
            "activity_candidate_count": len(active),
            "symbols": sorted({str(item.get("symbol")) for item in active}),
            "shape_counts": dict(sorted(Counter(str(item.get("shape_label")) for item in active).items())),
            "interpretation": "historical snapshot only; right-censoring retained",
        }
    return result


def _precursor_scorecard(events: list[dict[str, Any]], calendar: list[str]) -> dict[str, Any]:
    main = [item for item in events if item.get("evidence_status") == "body_verified"]
    sensitivity = [item for item in events if item.get("evidence_status") in {"provisional", "title_derived"}]
    verified_outcomes = _event_outcomes(events, calendar)

    def evaluate(rows: list[dict[str, Any]]) -> dict[str, Any]:
        observations = {20: [], 60: []}
        gap_values: list[int] = []
        branch_counts: Counter[str] = Counter()
        completed_60 = 0
        right_censored_60 = 0
        for item in rows:
            advance = set(item.get("possible_successors") or [])
            failure = set(item.get("failure_successors") or [])
            successors = advance | failure
            if not successors or not bool(item.get("not_hard_outcome")):
                continue
            start = bisect_left(calendar, str(item.get("available_as_of") or ""))
            candidates = [
                (int(outcome["calendar_index"]) - start, outcome)
                for outcome in verified_outcomes.get(str(item.get("symbol") or ""), [])
                if 0 < int(outcome["calendar_index"]) - start <= 60
                and str(outcome.get("node")) in successors
            ]
            if start + 60 >= len(calendar):
                right_censored_60 += 1
            else:
                completed_60 += 1
                if candidates:
                    gap, outcome = min(candidates, key=lambda pair: pair[0])
                    gap_values.append(gap)
                    node = str(outcome.get("node"))
                    branch_counts["failure_branch" if node in failure else "advance_branch"] += 1
                else:
                    branch_counts["still_unresolved_at_60"] += 1
            for horizon in (20, 60):
                if start + horizon >= len(calendar):
                    continue
                hit = any(gap <= horizon for gap, _outcome in candidates)
                observations[horizon].append(hit)
        metrics = {
            str(horizon): {
                "completed_n": len(values), "successor_hits": sum(values),
                "direct_successor_rate": sum(values) / len(values) if values else None,
                "wilson_95": _wilson(sum(values), len(values)),
            } for horizon, values in observations.items()
        }
        return {
            "by_horizon": metrics,
            "completed_60_n": completed_60,
            "right_censored_60_n": right_censored_60,
            "branch_counts": dict(sorted(branch_counts.items())),
            "median_gap_trading_days": _median([float(value) for value in gap_values]),
            "gap_p25": _quantile([float(value) for value in gap_values], .25),
            "gap_p75": _quantile([float(value) for value in gap_values], .75),
        }

    def reverse_recall(rows: list[dict[str, Any]]) -> dict[str, Any]:
        by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in rows:
            by_symbol[str(item.get("symbol") or "")].append(item)
        values = {20: [], 60: []}
        for symbol, outcomes_for_symbol in verified_outcomes.items():
            for outcome in outcomes_for_symbol:
                node = str(outcome.get("node") or "")
                valid_precursors = {
                    spec.node for spec in SPEC_BY_NODE.values()
                    if node in set(spec.possible_successors) | set(spec.failure_successors)
                }
                if not valid_precursors:
                    continue
                outcome_index = int(outcome["calendar_index"])
                for horizon in (20, 60):
                    values[horizon].append(any(
                        0 < outcome_index - bisect_left(calendar, str(item.get("available_as_of") or "")) <= horizon
                        and str(item.get("node") or "") in valid_precursors
                        for item in by_symbol.get(symbol, [])
                    ))
        return {
            str(horizon): {
                "outcome_n": len(items), "recalled_n": sum(items),
                "recall": sum(items) / len(items) if items else None,
                "wilson_95": _wilson(sum(items), len(items)),
            } for horizon, items in values.items()
        }

    return {
        "body_verified_main": {
            "precursor_count": len(main), "metrics": evaluate(main),
            "reverse_recall": reverse_recall(main),
            "status": "descriptive_only" if main else "unavailable_no_body_verified_events",
        },
        "title_or_provisional_sensitivity": {
            "precursor_count": len(sensitivity), "metrics": evaluate(sensitivity),
            "reverse_recall": reverse_recall(sensitivity),
            "status": "sensitivity_only",
        },
        "reverse_recall_status": (
            "descriptive_only" if main else "unavailable_until_body_verified_precursor_inventory"
        ),
    }


def _stage_map(
    *, valuation_episode_database: Path, dates: list[str],
    events: list[dict[str, Any]], include_title_sensitivity: bool = False,
) -> dict[tuple[str, str], str]:
    result = load_valuation_stage_map(valuation_episode_database, dates=dates)
    body_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        admitted = {"body_verified"}
        if include_title_sensitivity:
            admitted.update({"provisional", "title_derived"})
        if event.get("evidence_status") in admitted:
            body_events[str(event.get("symbol") or "")].append(event)
    for rows in body_events.values():
        rows.sort(key=lambda item: (str(item.get("available_as_of")), str(item.get("event_id"))))
    for symbol, rows in body_events.items():
        for day in dates:
            key = (symbol, day)
            if key in result:
                continue
            eligible = [item for item in rows if str(item.get("available_as_of") or "") <= day]
            if eligible:
                result[key] = str(eligible[-1].get("node") or "unknown")
    return result


def build_report(
    *, repository: P8ResearchRepository, base_database: Path,
    market_context_database: Path, valuation_episode_database: Path,
    start_date: str, through: str,
) -> P8BacktestReport:
    runs = {
        kind: repository.latest_run(kind) for kind in (
            "event_graph", "activity_features", "return_paths",
            "scenario_references", "chip_proxies", "funnel", "portfolio",
        )
    }
    if runs["event_graph"] is None or runs["activity_features"] is None:
        raise ValueError("P8 回测至少需要 event_graph 与 activity_features")
    events = repository.records(run_id=runs["event_graph"].run_id, record_type="derived_event")  # type: ignore[union-attr]
    extractions = repository.records(run_id=runs["event_graph"].run_id, record_type="llm_announcement_extraction")  # type: ignore[union-attr]
    features = repository.records(run_id=runs["activity_features"].run_id, record_type="activity_feature")  # type: ignore[union-attr]
    references = repository.records(run_id=runs["scenario_references"].run_id, record_type="scenario_reference") if runs["scenario_references"] else []
    funnels = repository.records(run_id=runs["funnel"].run_id, record_type="funnel_item") if runs["funnel"] else []
    portfolios = repository.records(run_id=runs["portfolio"].run_id, record_type="portfolio_summary") if runs["portfolio"] else []
    calendar = _calendar(market_context_database, start_date, through)
    prices = _prices(base_database, start_date, through)
    benchmarks = _benchmarks(market_context_database, start_date, through)
    outcomes = _event_outcomes(events, calendar)
    entries = _episode_starts(features, calendar)
    stages = _stage_map(
        valuation_episode_database=valuation_episode_database,
        dates=sorted({str(item.get("trade_date") or "") for item in features}),
        events=events,
    )
    title_sensitivity_stages = _stage_map(
        valuation_episode_database=valuation_episode_database,
        dates=sorted({str(item.get("trade_date") or "") for item in features}),
        events=events, include_title_sensitivity=True,
    )
    activity = _activity_metrics(
        entries, calendar=calendar, outcomes=outcomes,
        prices=prices, benchmarks=benchmarks,
    )
    by_year = {
        year: _activity_metrics(
            [item for item in entries if str(item.get("trade_date", "")).startswith(year)],
            calendar=calendar, outcomes=outcomes, prices=prices, benchmarks=benchmarks,
        ) for year in sorted({str(item.get("trade_date", ""))[:4] for item in entries})
    }
    reporting_season = _activity_metrics(
        [item for item in entries if str(item.get("trade_date", ""))[5:7] in {"01", "02", "03", "04"}],
        calendar=calendar, outcomes=outcomes, prices=prices, benchmarks=benchmarks,
    )
    exact = [item for item in references if item.get("value_status") == "exact_old_equity"]
    range_only = [item for item in references if item.get("value_status") == "range_old_equity"]
    identity = {
        "contract": CONTRACT_VERSION, "start_date": start_date, "through": through,
        "source_run_ids": sorted(item.run_id for item in runs.values() if item),
        "event_count": len(events), "feature_count": len(features), "reference_count": len(references),
    }
    return P8BacktestReport(
        record_id=content_id("P8BT", identity), start_date=start_date, through=through,
        source_run_ids=identity["source_run_ids"],
        frozen_inputs={
            "shape_profile": next((item.get("shape_profile") for item in features if item.get("shape_profile")), "unknown"),
            "event_registry": next((item.get("extractor_version") for item in events if item.get("extractor_version")), "unknown"),
            "horizons": list(HORIZONS), "thresholds_selected_with_outcomes": False,
            "outcomes_direction_separated": True,
        },
        replay_anchors=_replay_anchors(calendar, entries, through),
        extraction_scorecard={
            "body_shortlist_extraction_count": len(extractions),
            "completed_count": sum(item.get("reconciliation") != "failed" for item in extractions),
            "body_verified_event_count": sum(item.get("evidence_status") == "body_verified" for item in events),
            "source_span_count": sum(len(item.get("source_spans") or []) for item in events),
            "status": "descriptive_only" if extractions else "unavailable_external_llm_authorization_pending",
            "accuracy_status": "unvalidated_without_independent_body-labelled_sample",
        },
        precursor_scorecard=_precursor_scorecard(events, calendar),
        activity_scorecard={
            "episode_definition": "first frozen-shape observation after >5 trading-day gap",
            "overall": activity, "walk_forward_test_years": by_year,
            "reporting_season_jan_apr": reporting_season,
            "same_universe_quiet_control": _control_uncertainty(
                entries, features, prices=prices, benchmarks=benchmarks,
                stage_map=stages,
            ),
            "p7_title_stage_sensitivity": _control_uncertainty(
                entries, features, prices=prices, benchmarks=benchmarks,
                stage_map=title_sensitivity_stages,
            ),
            "status": "descriptive_only_not_threshold_selection",
        },
        scenario_reference_scorecard={
            "reference_count": len(references),
            "family_counts": dict(sorted(Counter(str(item.get("family")) for item in references).items())),
            "exact_old_equity_count": len(exact), "range_old_equity_count": len(range_only),
            "unknown_or_fact_only_count": len(references) - len(exact) - len(range_only),
            "containment_status": "unavailable" if not exact else "pending",
            "interval_score_status": "unavailable" if not (exact or range_only) else "pending",
            "p_star_validation_status": "unavailable" if not exact else "pending",
        },
        funnel_scorecard={
            "latest_item_count": len(funnels),
            "latest_lane_counts": dict(sorted(Counter(str(item.get("primary_lane")) for item in funnels).items())),
            "human_actions_required": 0,
            "historical_daily_shadow_count": 1 if funnels else 0,
            "concurrent_portfolio": portfolios[-1] if portfolios else None,
            "concurrent_portfolio_status": (
                str(portfolios[-1].get("evidence_status")) if portfolios
                else "unavailable_until_multiple_forward_shadow_days"
            ),
            "owner_keep_is_market_truth": False,
        },
        limitations=[
            "公告正文外部 LLM 授权未完成时，正文抽取成绩单保持 unavailable。",
            "旧股东精确权益账为 0，情景包含率、interval score 与 p* 不可计算。",
            "当前只形成一个真实 P8 每日漏斗，不能伪造历史同期组合。",
            "活动对照当前是同 universe 的 quiet 观察，不冒充同阶段近市值匹配。",
            "历史结果不替代至少 60 个真实交易日的前瞻 shadow。",
        ],
    )


def persist_report(report: P8BacktestReport, repository: P8ResearchRepository):
    payload = report.model_dump(mode="json")
    records = {"backtest_report": [payload]}
    run = build_run(
        run_kind="backtest", contract_version=CONTRACT_VERSION,
        start_date=report.start_date, through=report.through,
        source_run_ids=report.source_run_ids,
        source_digests={"report": hashlib.sha256(canonical_json(payload).encode()).hexdigest()},
        record_payloads=records,
    )
    repository.persist(run=run, records=records)
    return run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--through", required=True)
    parser.add_argument("--base-database", type=Path, default=DEFAULT_BASE_DB)
    parser.add_argument("--market-context-database", type=Path, default=MARKET_CONTEXT_DB)
    parser.add_argument("--valuation-episode-database", type=Path, default=VALUATION_EPISODE_DB)
    parser.add_argument("--repository", type=Path, default=P8_RESEARCH_DB)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    report = build_report(
        repository=P8ResearchRepository(args.repository),
        base_database=args.base_database,
        market_context_database=args.market_context_database,
        valuation_episode_database=args.valuation_episode_database,
        start_date=args.start_date, through=args.through,
    )
    run = persist_report(report, P8ResearchRepository(args.repository))
    output = {"run_id": run.run_id, **report.model_dump(mode="json")}
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "run_id": run.run_id, "report_id": report.record_id,
        "activity_entry_count": sum(value["episode_count"] for value in report.activity_scorecard["overall"].values()),
        "body_verified_event_count": report.extraction_scorecard["body_verified_event_count"],
        "exact_old_equity_count": report.scenario_reference_scorecard["exact_old_equity_count"],
        "funnel_shadow_days": report.funnel_scorecard["historical_daily_shadow_count"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
