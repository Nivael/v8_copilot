"""Frozen P8 v2 point-in-time scores, historical funnel and rank evaluation."""
from __future__ import annotations

import argparse
import bisect
import hashlib
import html
import json
import math
import random
import sqlite3
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from data_refresh import atomic_write_json
from p7_daily import load_valuation_stage_map
from p8_research import P8ResearchRepository, build_run, canonical_json, content_id
from settings import DATA_ROOT, MARKET_CONTEXT_DB, P8_RESEARCH_DB, VALUATION_EPISODE_DB


CONTRACT_VERSION = "v8_p8_backtest_v2"
TEST_YEARS = (2023, 2024, 2025)
MIN_CELL_OBSERVATIONS = 12
MIN_CELL_COMPANIES = 8
MIN_SIGNAL_OBSERVATIONS = 100
MIN_SIGNAL_COMPANIES = 40
BOOTSTRAP_REPETITIONS = 500
DEFAULT_BASE_DB = DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"
VERIFIED_EVENT_STATUSES = {"body_verified", "deterministic_verified"}
PERSISTENT_LABELS = {"persistent_activity_price_stable", "persistent_activity_price_down"}
LANE_QUOTAS = {"event_frontier": 6, "scenario_tension": 5, "persistent_activity": 5, "chip_or_exploration": 4}


def _connect_ro(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _latest_records(
    repository: P8ResearchRepository, run_kind: str, record_type: str,
) -> tuple[str, str, list[dict[str, Any]]]:
    if not repository.path.is_file():
        return "", "", []
    with _connect_ro(repository.path) as connection:
        row = connection.execute(
            "select run_id,content_digest from p8_runs where run_kind=? "
            "order by created_at desc,run_id desc limit 1", (run_kind,),
        ).fetchone()
        if row is None:
            return "", "", []
        run_id, run_digest = str(row[0]), str(row[1])
        records = [json.loads(str(item[0])) for item in connection.execute(
            "select payload_json from p8_records where run_id=? and record_type=? "
            "order by available_as_of,record_id", (run_id, record_type),
        )]
    return run_id, run_digest, records


def _board(symbol: str) -> str:
    if symbol.startswith("300"):
        return "创业板"
    if symbol.startswith("688"):
        return "科创板"
    if symbol.startswith(("8", "9")):
        return "北交所"
    return "主板"


def _half(day: str) -> str:
    return "H1" if int(day[5:7]) <= 6 else "H2"


def _midrank_percentile(values: list[float], current: float) -> float | None:
    if not values:
        return None
    left = bisect.bisect_left(values, current)
    right = bisect.bisect_right(values, current)
    return (left + .5 * (right - left)) / len(values)


class _RankCounter:
    """Coordinate-compressed counts; future values define bins but never counts."""

    def __init__(self, domain: Iterable[float]) -> None:
        self.domain = sorted(set(domain))
        self.tree = [0] * (len(self.domain) + 1)

    def add(self, value: float) -> None:
        index = bisect.bisect_left(self.domain, value) + 1
        while index < len(self.tree):
            self.tree[index] += 1
            index += index & -index

    def _prefix(self, count: int) -> int:
        total = 0
        while count > 0:
            total += self.tree[count]
            count -= count & -count
        return total

    def percentile(self, value: float, observations: int) -> float | None:
        if observations <= 0:
            return None
        index = bisect.bisect_left(self.domain, value)
        less = self._prefix(index)
        equal = self._prefix(index + 1) - less
        return (less + .5 * equal) / observations


class _History:
    def __init__(self, domains: dict[str, list[float]]) -> None:
        self.components = {key: _RankCounter(values) for key, values in domains.items()}
        self.companies: set[str] = set()
        self.observations = 0

    def ready(self) -> bool:
        return self.observations >= MIN_CELL_OBSERVATIONS and len(self.companies) >= MIN_CELL_COMPANIES

    def score(self, components: dict[str, float]) -> tuple[float, dict[str, float]] | None:
        ranks: dict[str, float] = {}
        for key, value in components.items():
            rank = self.components[key].percentile(value, self.observations)
            if rank is None:
                return None
            ranks[key] = rank
        return statistics.mean(ranks.values()), ranks

    def add(self, symbol: str, components: dict[str, float]) -> None:
        for key, value in components.items():
            self.components[key].add(value)
        self.companies.add(symbol)
        self.observations += 1


def _score_components(item: dict[str, Any]) -> dict[str, float] | None:
    raw = {
        "cum_turnover_log_excess_20": item.get("cum_turnover_log_excess_20"),
        "elevated_day_ratio_20": item.get("elevated_day_ratio_20"),
        "negative_abs_excess_return_st_20": (
            -abs(float(item["excess_return_st_20"]))
            if item.get("excess_return_st_20") is not None else None
        ),
        "negative_range_compression_20": (
            -float(item["range_compression_20"])
            if item.get("range_compression_20") is not None else None
        ),
    }
    if any(value is None or not math.isfinite(float(value)) for value in raw.values()):
        return None
    return {key: float(value) for key, value in raw.items()}


def build_accumulation_scores(
    features: list[dict[str, Any]], *, stage_map: dict[tuple[str, str], str],
) -> list[dict[str, Any]]:
    """Use only strictly earlier observations; same-day rows never rank one another."""

    prepared: list[tuple[str, str, str, dict[str, Any], dict[str, float]]] = []
    for item in features:
        day, symbol = str(item.get("trade_date") or ""), str(item.get("symbol") or "")
        if int(day[:4] or 0) < 2021 or not bool(item.get("calculable")):
            continue
        stage = stage_map.get((symbol, day), "unknown")
        components = _score_components(item)
        if stage == "unknown" or components is None:
            continue
        prepared.append((day, symbol, stage, item, components))
    prepared.sort(key=lambda value: (value[0], value[1]))
    exact_domains: dict[tuple[str, str, str], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    relaxed_domains: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for day, symbol, stage, _item, components in prepared:
        for key, value in components.items():
            exact_domains[(stage, _half(day), _board(symbol))][key].append(value)
            relaxed_domains[(stage, _half(day))][key].append(value)
    exact = {key: _History(dict(domains)) for key, domains in exact_domains.items()}
    relaxed = {key: _History(dict(domains)) for key, domains in relaxed_domains.items()}
    result: list[dict[str, Any]] = []
    offset = 0
    while offset < len(prepared):
        day = prepared[offset][0]
        end = offset
        while end < len(prepared) and prepared[end][0] == day:
            end += 1
        daily = prepared[offset:end]
        for current_day, symbol, stage, item, components in daily:
            exact_key = (stage, _half(current_day), _board(symbol))
            relaxed_key = (stage, _half(current_day))
            history = exact[exact_key]
            relaxation_path: list[str] = []
            stratum_key = "|".join(exact_key)
            if not history.ready():
                history = relaxed[relaxed_key]
                relaxation_path = ["drop_board"]
                stratum_key = "|".join(relaxed_key)
            scored = history.score(components) if history.ready() else None
            if scored is None:
                continue
            score, component_ranks = scored
            bucket = "low" if score < 1 / 3 else "high" if score > 2 / 3 else "middle"
            identity = {
                "contract": CONTRACT_VERSION, "family": "p8c_accumulation",
                "symbol": symbol, "trade_date": current_day,
                "source_feature_id": item.get("feature_id"),
                "history_observations": history.observations,
                "history_company_count": len(history.companies),
            }
            result.append({
                "record_id": content_id("P8SCORE", identity),
                "signal_family": "p8c_accumulation",
                "symbol": symbol,
                "trade_date": current_day,
                "available_as_of": current_day,
                "test_year": int(current_day[:4]),
                "stage": stage,
                "calendar_half": _half(current_day),
                "board": _board(symbol),
                "stratum_key": stratum_key,
                "relaxation_path": relaxation_path,
                "score": score,
                "component_values": components,
                "component_midrank_percentiles": component_ranks,
                "bucket": bucket,
                "history_observation_count": history.observations,
                "history_company_count": len(history.companies),
                "source_feature_id": str(item.get("feature_id") or item.get("record_id") or ""),
                "shape_label": str(item.get("shape_label") or "unknown"),
                "evidence_status": "derived_point_in_time",
            })
        # Same-day values become available only after all same-day scores are fixed.
        for current_day, symbol, stage, _item, components in daily:
            exact[(stage, _half(current_day), _board(symbol))].add(symbol, components)
            relaxed[(stage, _half(current_day))].add(symbol, components)
        offset = end
    return result


def _calendar_membership(path: Path, start: str, through: str) -> tuple[list[str], dict[str, set[str]]]:
    members: dict[str, set[str]] = defaultdict(set)
    with _connect_ro(path) as connection:
        calendar = [str(row[0]) for row in connection.execute(
            "select trade_date from benchmark_daily where benchmark_id='csi_all_share' "
            "and trade_date between ? and ? order by trade_date", (start, through),
        )]
        for row in connection.execute(
            "select trade_date,symbol from st_membership_daily where trade_date between ? and ?",
            (start, through),
        ):
            members[str(row[0])].add(str(row[1]))
    return calendar, dict(members)


def _membership_starts(calendar: list[str], memberships: dict[str, set[str]]) -> dict[tuple[str, str], str]:
    starts: dict[str, str] = {}
    result: dict[tuple[str, str], str] = {}
    previous: set[str] = set()
    for day in calendar:
        current = memberships.get(day, set())
        for symbol in current:
            if symbol not in previous:
                starts[symbol] = day
            result[(symbol, day)] = starts[symbol]
        previous = current
    return result


def _weekly_decision_dates(calendar: list[str]) -> list[str]:
    latest: dict[tuple[int, int], str] = {}
    for day in calendar:
        iso = date.fromisoformat(day).isocalendar()
        latest[(iso.year, iso.week)] = day
    return sorted(latest.values())


def build_historical_funnel(
    *, calendar: list[str], memberships: dict[str, set[str]],
    events: list[dict[str, Any]], features: list[dict[str, Any]],
    scores: list[dict[str, Any]], stage_map: dict[tuple[str, str], str],
) -> list[dict[str, Any]]:
    starts = _membership_starts(calendar, memberships)
    scores_by_key = {(str(item["symbol"]), str(item["trade_date"])): item for item in scores}
    features_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in features:
        features_by_day[str(item.get("trade_date") or "")].append(item)
    events_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in events:
        if item.get("evidence_status") not in VERIFIED_EVENT_STATUSES:
            continue
        if not (item.get("possible_successors") or item.get("failure_successors")):
            continue
        events_by_symbol[str(item.get("symbol") or "")].append(item)
    for rows in events_by_symbol.values():
        rows.sort(key=lambda item: (str(item.get("available_as_of") or ""), str(item.get("event_id") or "")))

    records: list[dict[str, Any]] = []
    for decision_day in _weekly_decision_dates(calendar):
        current = memberships.get(decision_day, set())
        same_day_event_symbols = {
            symbol for symbol in current for event in events_by_symbol.get(symbol, [])
            if str(event.get("available_as_of") or "") == decision_day
        }
        candidates: dict[str, dict[str, Any]] = {}
        event_order: list[str] = []
        for symbol in sorted(current):
            lower = starts.get((symbol, decision_day), decision_day)
            eligible = [
                item for item in events_by_symbol.get(symbol, [])
                if lower <= str(item.get("available_as_of") or "") <= decision_day
                and (date.fromisoformat(decision_day) - date.fromisoformat(str(item["available_as_of"]))).days <= 60
            ]
            if not eligible:
                continue
            latest = eligible[-1]
            candidates[symbol] = {
                "symbol": symbol, "matched_lanes": {"event_frontier"},
                "event": latest, "feature": None,
            }
            event_order.append(symbol)
        event_order.sort(key=lambda symbol: (
            0 if candidates[symbol]["event"].get("evidence_status") == "body_verified" else 1,
            -(date.fromisoformat(str(candidates[symbol]["event"]["available_as_of"])) - date(1900, 1, 1)).days,
            symbol,
        ))

        activity_order: list[str] = []
        for feature in features_by_day.get(decision_day, []):
            symbol = str(feature.get("symbol") or "")
            if symbol not in current or symbol in same_day_event_symbols:
                continue
            if feature.get("shape_label") not in PERSISTENT_LABELS:
                continue
            score = scores_by_key.get((symbol, decision_day))
            if score is None:
                continue
            candidate = candidates.setdefault(symbol, {
                "symbol": symbol, "matched_lanes": set(), "event": None, "feature": None,
            })
            candidate["matched_lanes"].add("persistent_activity")
            candidate["feature"] = feature
            activity_order.append(symbol)
        activity_order.sort(key=lambda symbol: (
            0 if str(candidates[symbol]["feature"].get("shape_label")) == "persistent_activity_price_stable" else 1,
            -float(scores_by_key[(symbol, decision_day)]["score"]), symbol,
        ))

        lane_orders = {"event_frontier": event_order, "persistent_activity": activity_order}
        selected: set[str] = set()
        ranks: dict[tuple[str, str], int] = {}
        for lane in ("event_frontier", "scenario_tension", "persistent_activity", "chip_or_exploration"):
            order = lane_orders.get(lane, [])
            order = sorted(order, key=lambda symbol: (-len(candidates[symbol]["matched_lanes"]), order.index(symbol)))
            accepted = [symbol for symbol in order if symbol not in selected][:LANE_QUOTAS[lane]]
            for rank, symbol in enumerate(accepted, start=1):
                selected.add(symbol)
                ranks[(lane, symbol)] = rank
                candidate = candidates[symbol]
                event = candidate.get("event") or {}
                feature = candidate.get("feature") or {}
                source_ids = [
                    value for value in (
                        event.get("event_id"), feature.get("feature_id"),
                    ) if value
                ]
                identity = {
                    "contract": CONTRACT_VERSION, "decision_date": decision_day,
                    "symbol": symbol, "primary_lane": lane, "source_ids": source_ids,
                }
                records.append({
                    "record_id": content_id("P8HF", identity),
                    "decision_date": decision_day,
                    "available_as_of": decision_day,
                    "test_year": int(decision_day[:4]),
                    "symbol": symbol,
                    "primary_lane": lane,
                    "matched_lanes": sorted(candidate["matched_lanes"]),
                    "lane_rank": rank,
                    "stage": stage_map.get((symbol, decision_day), "unknown"),
                    "score": scores_by_key.get((symbol, decision_day), {}).get("score"),
                    "shape_label": str(feature.get("shape_label") or ""),
                    "source_ids": source_ids,
                    "evidence_status": "historical_point_in_time_replay",
                })
    return records


def _prices(path: Path, start: str, through: str) -> dict[str, list[tuple[str, float]]]:
    result: dict[str, list[tuple[str, float]]] = defaultdict(list)
    with _connect_ro(path) as connection:
        for row in connection.execute(
            "select symbol,trade_date,close from daily_prices where adjust='qfq' "
            "and trade_date between ? and ? and close>0 order by symbol,trade_date", (start, through),
        ):
            result[str(row[0])].append((str(row[1]), float(row[2])))
    return dict(result)


def _benchmarks(path: Path, start: str, through: str) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = defaultdict(dict)
    with _connect_ro(path) as connection:
        for row in connection.execute(
            "select benchmark_id,trade_date,close from benchmark_daily "
            "where benchmark_id in ('st_equal_weight_v1','csi_2000') "
            "and trade_date between ? and ? and close>0", (start, through),
        ):
            result[str(row[0])][str(row[1])] = float(row[2])
    return dict(result)


def attach_outcomes(
    scores: list[dict[str, Any]], *, prices: dict[str, list[tuple[str, float]]],
    benchmarks: dict[str, dict[str, float]], events: list[dict[str, Any]],
    horizons: tuple[int, ...] = (60, 120),
) -> list[dict[str, Any]]:
    event_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event.get("evidence_status") in VERIFIED_EVENT_STATUSES and not bool(event.get("not_hard_outcome")):
            event_by_symbol[str(event.get("symbol") or "")].append(event)
    for rows in event_by_symbol.values():
        rows.sort(key=lambda item: str(item.get("available_as_of") or ""))
    result: list[dict[str, Any]] = []
    for score in scores:
        if int(score["test_year"]) not in TEST_YEARS:
            continue
        symbol, day = str(score["symbol"]), str(score["trade_date"])
        rows = prices.get(symbol, [])
        dates = [item[0] for item in rows]
        start_index = bisect.bisect_left(dates, day)
        if start_index >= len(rows) or rows[start_index][0] != day:
            continue
        observation = dict(score)
        for horizon in horizons:
            target = start_index + horizon
            prefix = f"h{horizon}"
            if target >= len(rows):
                observation[f"{prefix}_observed"] = False
                continue
            end_day, end_price = rows[target]
            start_price = rows[start_index][1]
            stock_return = end_price / start_price - 1
            st_left = benchmarks.get("st_equal_weight_v1", {}).get(day)
            st_right = benchmarks.get("st_equal_weight_v1", {}).get(end_day)
            csi_left = benchmarks.get("csi_2000", {}).get(day)
            csi_right = benchmarks.get("csi_2000", {}).get(end_day)
            observation.update({
                f"{prefix}_observed": bool(st_left and st_right),
                f"{prefix}_end_date": end_day,
                f"{prefix}_stock_qfq_return": stock_return,
                f"{prefix}_excess_return_st": (
                    stock_return - (st_right / st_left - 1) if st_left and st_right else None
                ),
                f"{prefix}_excess_return_csi2000": (
                    stock_return - (csi_right / csi_left - 1) if csi_left and csi_right else None
                ),
            })
            future_events = [
                event for event in event_by_symbol.get(symbol, [])
                if day < str(event.get("available_as_of") or "") <= end_day
            ]
            observation[f"{prefix}_positive_hard_node"] = any(
                event.get("process_direction") == "advance"
                and event.get("old_equity_effect") == "supportive" for event in future_events
            )
            observation[f"{prefix}_negative_hard_node"] = any(
                event.get("process_direction") == "rollback"
                or event.get("old_equity_effect") == "adverse" for event in future_events
            )
        result.append(observation)
    return result


def _mean(values: Iterable[float]) -> float | None:
    items = list(values)
    return statistics.mean(items) if items else None


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    left = int(position)
    right = min(left + 1, len(ordered) - 1)
    weight = position - left
    return ordered[left] * (1 - weight) + ordered[right] * weight


def _cell_equal_difference(rows: list[dict[str, Any]], value_key: str) -> float | None:
    cells: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for item in rows:
        value = item.get(value_key)
        bucket = str(item.get("bucket") or "")
        if value is not None and bucket in {"high", "low"}:
            cells[str(item["stratum_key"])][bucket].append(float(value))
    differences = [
        statistics.mean(values["high"]) - statistics.mean(values["low"])
        for values in cells.values() if values["high"] and values["low"]
    ]
    return statistics.mean(differences) if differences else None


def _cluster_bootstrap(
    rows: list[dict[str, Any]], *, value_key: str, cluster_key: str,
    seed: int, repetitions: int = BOOTSTRAP_REPETITIONS,
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in rows:
        if item.get(value_key) is not None and item.get("bucket") in {"high", "low"}:
            grouped[str(item[cluster_key])].append(item)
    keys = sorted(grouped)
    if len(keys) < 5:
        return {"cluster_count": len(keys), "ci95": None, "p_value_two_sided": None}
    generator = random.Random(seed)
    estimates: list[float] = []
    for _ in range(repetitions):
        sample = [generator.choice(keys) for _ in keys]
        sampled_rows = [item for key in sample for item in grouped[key]]
        estimate = _cell_equal_difference(sampled_rows, value_key)
        if estimate is not None:
            estimates.append(estimate)
    nonpositive = sum(value <= 0 for value in estimates)
    nonnegative = sum(value >= 0 for value in estimates)
    return {
        "cluster_count": len(keys),
        "repetitions": len(estimates),
        "ci95": [_quantile(estimates, .025), _quantile(estimates, .975)] if estimates else None,
        "p_value_two_sided": min(1.0, 2 * min(nonpositive, nonnegative) / len(estimates)) if estimates else None,
    }


def _rankdata(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    index = 0
    while index < len(order):
        end = index + 1
        while end < len(order) and values[order[end]] == values[order[index]]:
            end += 1
        rank = (index + end - 1) / 2 + 1
        for position in order[index:end]:
            ranks[position] = rank
        index = end
    return ranks


def _spearman(rows: list[dict[str, Any]], value_key: str) -> float | None:
    pairs = [(float(item["score"]), float(item[value_key])) for item in rows if item.get(value_key) is not None]
    if len(pairs) < 3:
        return None
    left, right = _rankdata([item[0] for item in pairs]), _rankdata([item[1] for item in pairs])
    left_mean, right_mean = statistics.mean(left), statistics.mean(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    denominator = math.sqrt(
        sum((a - left_mean) ** 2 for a in left) * sum((b - right_mean) ** 2 for b in right)
    )
    return numerator / denominator if denominator else None


def rank_scorecard(observations: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [item for item in observations if item.get("h120_excess_return_st") is not None]
    companies = {str(item["symbol"]) for item in eligible}
    if len(eligible) < MIN_SIGNAL_OBSERVATIONS or len(companies) < MIN_SIGNAL_COMPANIES:
        return {
            "signal_family": "p8c_accumulation", "status": "unavailable",
            "observation_count": len(eligible), "company_count": len(companies),
            "reason": "minimum_100_observations_40_companies_not_met",
        }
    prepared = [dict(item, calendar_month=str(item["trade_date"])[:7]) for item in eligible]
    per_year: dict[str, Any] = {}
    for year in TEST_YEARS:
        rows = [item for item in prepared if int(item["test_year"]) == year]
        per_year[str(year)] = {
            "observation_count": len(rows),
            "company_count": len({str(item["symbol"]) for item in rows}),
            "high_minus_low_120d_excess_st": _cell_equal_difference(rows, "h120_excess_return_st"),
            "spearman_score_vs_120d_excess_st": _spearman(rows, "h120_excess_return_st"),
            "positive_hard_node_high_count": sum(
                bool(item.get("h120_positive_hard_node")) and item.get("bucket") == "high" for item in rows
            ),
            "positive_hard_node_low_count": sum(
                bool(item.get("h120_positive_hard_node")) and item.get("bucket") == "low" for item in rows
            ),
        }
    point = _cell_equal_difference(prepared, "h120_excess_return_st")
    company = _cluster_bootstrap(
        prepared, value_key="h120_excess_return_st", cluster_key="symbol", seed=2026090501,
    )
    month = _cluster_bootstrap(
        prepared, value_key="h120_excess_return_st", cluster_key="calendar_month", seed=2026090502,
    )
    year_values = [
        item["high_minus_low_120d_excess_st"] for item in per_year.values()
        if item["high_minus_low_120d_excess_st"] is not None
    ]
    if len(year_values) >= 2 and sum(value <= 0 for value in year_values) >= 2 and (point or 0) <= 0:
        decision = "killed"
    else:
        company_ci, month_ci = company.get("ci95"), month.get("ci95")
        supported_intervals = bool(
            company_ci and month_ci and company_ci[0] is not None and month_ci[0] is not None
            and float(company_ci[0]) > 0 and float(month_ci[0]) > 0
        )
        decision = "supported_pending_basket" if sum(value > 0 for value in year_values) >= 2 and supported_intervals else "weak"
    return {
        "signal_family": "p8c_accumulation",
        "status": decision,
        "observation_count": len(prepared),
        "company_count": len(companies),
        "cell_equal_high_minus_low_120d_excess_st": point,
        "spearman_score_vs_120d_excess_st": _spearman(prepared, "h120_excess_return_st"),
        "company_cluster_bootstrap": company,
        "calendar_month_block_bootstrap": month,
        "raw_p_value": max(
            value for value in (
                company.get("p_value_two_sided"), month.get("p_value_two_sided"),
            ) if value is not None
        ) if any(value is not None for value in (company.get("p_value_two_sided"), month.get("p_value_two_sided"))) else None,
        "holm_adjusted_p_value": None,
        "per_year": per_year,
    }


def _holm(scorecards: list[dict[str, Any]]) -> None:
    available = sorted(
        [(index, float(item["raw_p_value"])) for index, item in enumerate(scorecards) if item.get("raw_p_value") is not None],
        key=lambda value: value[1],
    )
    running = 0.0
    count = len(available)
    for rank, (index, value) in enumerate(available):
        adjusted = min(1.0, value * (count - rank))
        running = max(running, adjusted)
        scorecards[index]["holm_adjusted_p_value"] = running


def persist_v2_inputs(
    repository: P8ResearchRepository, *, scores: list[dict[str, Any]],
    funnel: list[dict[str, Any]], source_run_id: str, source_digest: str,
) -> tuple[str, str]:
    score_run = build_run(
        run_kind="p8_signal_rank_v2", contract_version=CONTRACT_VERSION,
        start_date="2021-03-17", through="2025-12-31",
        source_run_ids=[source_run_id], source_digests={"activity_features": source_digest},
        record_payloads={"p8_signal_score_v2": scores},
    )
    repository.persist(run=score_run, records={"p8_signal_score_v2": scores})
    funnel_run = build_run(
        run_kind="p8_historical_funnel_v2", contract_version=CONTRACT_VERSION,
        start_date="2023-01-01", through="2025-12-31",
        source_run_ids=[source_run_id, score_run.run_id],
        source_digests={"activity_features": source_digest, "signal_scores": score_run.content_digest},
        record_payloads={"p8_historical_funnel_item_v2": funnel},
    )
    repository.persist(run=funnel_run, records={"p8_historical_funnel_item_v2": funnel})
    return score_run.run_id, funnel_run.run_id


def build_and_evaluate(
    *, base_database: Path, market_context_database: Path,
    valuation_episode_database: Path, repository: P8ResearchRepository,
    dry_plan_json: Path, allow_outcomes: bool,
) -> dict[str, Any]:
    if not allow_outcomes:
        raise ValueError("正式 v2 必须显式传 --allow-outcomes")
    dry_plan = json.loads(dry_plan_json.read_text(encoding="utf-8"))
    if dry_plan.get("outcomes_read") is not False or dry_plan.get("returns_computed") is not False:
        raise ValueError("输入 dry-plan 已读取 outcome/return")
    activity_run_id, activity_digest, features = _latest_records(
        repository, "activity_features", "activity_feature",
    )
    event_run_id, event_digest, events = _latest_records(repository, "event_graph", "derived_event")
    if not features:
        raise ValueError("缺 activity_features")
    feature_dates = sorted({str(item.get("trade_date") or "") for item in features if str(item.get("trade_date") or "") <= "2025-12-31"})
    stage_map = load_valuation_stage_map(valuation_episode_database, dates=feature_dates)
    historical_features = [
        item for item in features if str(item.get("trade_date") or "") <= "2025-12-31"
    ]
    scores = build_accumulation_scores(historical_features, stage_map=stage_map)
    calendar, memberships = _calendar_membership(market_context_database, "2021-03-17", "2025-12-31")
    decision_dates = _weekly_decision_dates([day for day in calendar if "2023-01-01" <= day <= "2025-12-31"])
    missing_stage_dates = sorted(set(decision_dates) - set(feature_dates))
    if missing_stage_dates:
        raise ValueError(f"历史 funnel 缺 feature decision dates: {missing_stage_dates[:5]}")
    decision_stage_map = load_valuation_stage_map(valuation_episode_database, dates=decision_dates)
    funnel = build_historical_funnel(
        calendar=[day for day in calendar if "2023-01-01" <= day <= "2025-12-31"],
        memberships=memberships, events=events, features=historical_features,
        scores=scores, stage_map=decision_stage_map,
    )
    score_run_id, funnel_run_id = persist_v2_inputs(
        repository, scores=scores, funnel=funnel,
        source_run_id=activity_run_id, source_digest=activity_digest,
    )
    prices = _prices(base_database, "2021-03-17", "2026-09-03")
    benchmarks = _benchmarks(market_context_database, "2021-03-17", "2026-09-03")
    observations = attach_outcomes(scores, prices=prices, benchmarks=benchmarks, events=events)
    cards = [
        {
            "signal_family": "p8a_p_star", "status": "unavailable",
            "reason": "company_same_claim_p_star_historical_inputs_absent",
        },
        {
            "signal_family": "p8b_precursor", "status": "unavailable",
            "reason": "verified_hard_outcomes_below_training_gate",
        },
        rank_scorecard(observations),
        {
            "signal_family": "p8c_holder", "status": "unavailable",
            "reason": "historical_available_date_holder_series_absent",
        },
    ]
    _holm(cards)
    result = {
        "record_id": content_id("P8BT2", {
            "contract": CONTRACT_VERSION, "dry_plan": dry_plan.get("content_digest"),
            "activity": activity_digest, "events": event_digest,
            "score_run": score_run_id, "funnel_run": funnel_run_id,
        }),
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start_date": "2023-01-01",
        "through": "2025-12-31",
        "source_dry_plan_id": str(dry_plan.get("plan_id") or ""),
        "source_run_ids": [activity_run_id, event_run_id, score_run_id, funnel_run_id],
        "source_digests": {"activity": activity_digest, "event": event_digest},
        "score_count": len(scores),
        "historical_funnel_item_count": len(funnel),
        "historical_funnel_decision_date_count": len({item["decision_date"] for item in funnel}),
        "rank_observation_count": len(observations),
        "signal_scorecards": cards,
        "verified_hard_event_count": sum(
            item.get("evidence_status") in VERIFIED_EVENT_STATUSES and not bool(item.get("not_hard_outcome"))
            for item in events
        ),
        "basket_status": "pending_separate_run",
        "not_a_trading_signal": True,
    }
    return result


def persist_report(repository: P8ResearchRepository, report: dict[str, Any]) -> str:
    record = dict(report)
    record.pop("generated_at", None)
    run = build_run(
        run_kind="p8_backtest_v2_report", contract_version=CONTRACT_VERSION,
        start_date="2023-01-01", through="2025-12-31",
        source_run_ids=list(report["source_run_ids"]), source_digests=dict(report["source_digests"]),
        record_payloads={"p8_backtest_v2_report": [record]},
    )
    repository.persist(run=run, records={"p8_backtest_v2_report": [record]})
    return run.run_id


def render_markdown(report: dict[str, Any]) -> str:
    rows = [
        "# P8-BT2 同阶段排序成绩单", "",
        f"- score：{report['score_count']:,}",
        f"- 历史漏斗：{report['historical_funnel_item_count']:,} 条 / {report['historical_funnel_decision_date_count']} 个决策日",
        f"- 核证 hard node：{report['verified_hard_event_count']}", "",
        "## 方向结论", "", "| 方向 | 状态 | 主差值 | 原因 |", "| --- | --- | ---: | --- |",
    ]
    for item in report["signal_scorecards"]:
        value = item.get("cell_equal_high_minus_low_120d_excess_st")
        rows.append(
            f"| {item['signal_family']} | {item['status']} | "
            f"{value:.2%}" if value is not None else f"| {item['signal_family']} | {item['status']} | —"
        )
        rows[-1] += f" | {item.get('reason', '')} |"
    rows.extend(["", "篓子是独立决定性测试；本表不把稀有节点率当主结论。", ""])
    return "\n".join(rows)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-database", type=Path, default=DEFAULT_BASE_DB)
    parser.add_argument("--market-context-database", type=Path, default=MARKET_CONTEXT_DB)
    parser.add_argument("--valuation-episode-database", type=Path, default=VALUATION_EPISODE_DB)
    parser.add_argument("--repository", type=Path, default=P8_RESEARCH_DB)
    parser.add_argument("--dry-plan-json", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path)
    parser.add_argument("--allow-outcomes", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repository = P8ResearchRepository(args.repository)
    report = build_and_evaluate(
        base_database=args.base_database,
        market_context_database=args.market_context_database,
        valuation_episode_database=args.valuation_episode_database,
        repository=repository,
        dry_plan_json=args.dry_plan_json,
        allow_outcomes=args.allow_outcomes,
    )
    run_id = persist_report(repository, report)
    report["run_id"] = run_id
    atomic_write_json(args.output_json, report)
    if args.output_markdown:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({
        "run_id": run_id, "score_count": report["score_count"],
        "historical_funnel_item_count": report["historical_funnel_item_count"],
        "signal_statuses": {item["signal_family"]: item["status"] for item in report["signal_scorecards"]},
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
