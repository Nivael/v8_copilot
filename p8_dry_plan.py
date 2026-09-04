"""P8-0 outcome-blind local inventory and capacity gate."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sqlite3
import subprocess
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from data_refresh import atomic_write_json
from market_activity import MarketActivityRepository
from p8_activity import build_activity_features, choose_capacity_profile, profile_capacity
from p8_llm_extraction import (
    CALL_TIMEOUT_SECONDS,
    EXTRACTION_CONTRACT_VERSION,
    MAX_CALL_ATTEMPTS,
    PROMPT_VERSION,
    RETRY_BACKOFF_SECONDS,
    _body_chunks,
)
from p8_regimes import REGISTRY_VERSION as REGIME_REGISTRY_VERSION, regime_for_date
from settings import (
    ANNOUNCEMENT_BODY_CACHE_DIR,
    ANNOUNCEMENT_REFRESH_DIR,
    DATA_ROOT,
    MARKET_ACTIVITY_DB,
    MARKET_CONTEXT_DB,
    MARKET_FACTOR_DB,
    P7_INTELLIGENCE_DB,
    VALUATION_EPISODE_DB,
    VALUATION_FACTS_DB,
)


CONTRACT_VERSION = "v8_p8_0_dry_plan_v1"
DEFAULT_BASE_DB = DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"
STRATEGIC_TERMS = (
    "重整投资协议", "重整投资人", "产业投资人", "财务投资人",
    "投资人招募", "投资人遴选", "出资人权益调整",
)
PUBLIC_NODE_TYPES = {
    "court_restructuring_accepted", "restructuring_plan_approved",
    "plan_executed", "risk_warning_removed", "delisting_decision",
}
ADJACENT_STAGE_GROUPS = {
    "distress_entry": {"st_distress_only", "restructuring_application_disclosed"},
    "pre_judicial": {"pre_restructuring_started", "investor_recruitment"},
    "formal_process": {"formal_restructuring_accepted", "investor_agreement_signed"},
    "plan_resolution": {"plan_key_terms_disclosed", "plan_approved"},
    "execution_exit": {"plan_executed", "risk_warning_removed"},
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class P8DryPlan(StrictModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    plan_id: str = Field(pattern=r"^P8DP-[A-F0-9]{20}$")
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    generated_at: str
    as_of: str
    git_provenance: dict[str, Any]
    input_inventory: list[dict[str, Any]]
    source_boundaries: dict[str, Any]
    scenario_reference_inventory: dict[str, Any]
    cell_occupancy: dict[str, Any]
    relaxation_capacity: dict[str, Any]
    body_inventory: dict[str, Any]
    event_graph_inventory: dict[str, Any]
    llm_request_budget: dict[str, Any]
    activity_feature_capacity: dict[str, Any]
    frozen_shape_profile: str
    chip_provider_probe: dict[str, Any]
    return_endpoint_inventory: dict[str, Any]
    request_budget: dict[str, Any]
    storage_budget: dict[str, Any]
    hard_blockers: list[str]
    non_blocking_gaps: list[str]
    safe_defaults: list[str]
    recommended_next_step: str
    human_decisions_required: list[dict[str, Any]]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _connect_ro(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source(path: Path, source_id: str) -> dict[str, Any]:
    if not path.is_file():
        return {"source_id": source_id, "path": str(path), "available": False}
    return {
        "source_id": source_id,
        "path": str(path),
        "available": True,
        "size_bytes": path.stat().st_size,
        "digest": _file_sha256(path),
        "digest_kind": "sha256_file",
    }


def _git_provenance(repo: Path) -> dict[str, str]:
    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=repo, check=True, capture_output=True, text=True,
        ).stdout.strip()
    return {"commit": run("rev-parse", "HEAD"), "branch": run("branch", "--show-current")}


def _months_before(day: str, months: int) -> str:
    value = date.fromisoformat(day)
    index = value.year * 12 + value.month - 1 - months
    year, month_zero = divmod(index, 12)
    month = month_zero + 1
    while True:
        try:
            return date(year, month, value.day).isoformat()
        except ValueError:
            value = value.replace(day=value.day - 1)


def _board(symbol: str) -> str:
    if symbol.startswith("300"):
        return "创业板"
    if symbol.startswith("688"):
        return "科创板"
    if symbol.startswith(("8", "9")):
        return "北交所"
    return "主板"


def _latest_announcement_run(connection: sqlite3.Connection) -> str:
    row = connection.execute(
        "select run_id from announcement_runs order by created_at desc,run_id desc limit 1"
    ).fetchone()
    if row is None:
        raise ValueError("p7_intelligence 缺 announcement run")
    return str(row[0])


def _load_p7_announcement_facts(path: Path) -> tuple[str, list[dict[str, Any]]]:
    with _connect_ro(path) as connection:
        run_id = _latest_announcement_run(connection)
        rows = connection.execute(
            "select payload_json from announcement_facts where run_id=? order by available_as_of,announcement_id",
            (run_id,),
        )
        return run_id, [json.loads(str(row[0])) for row in rows]


def build_body_missing_queue(path: Path) -> dict[str, Any]:
    run_id, facts = _load_p7_announcement_facts(path)
    records = [
        {
            "announcement_id": str(item.get("announcement_id") or ""),
            "symbol": str(item.get("symbol") or ""),
            "available_as_of": str(item.get("available_as_of") or ""),
            "title": str(item.get("title") or ""),
            "category": str(item.get("category") or ""),
            "source": str(item.get("source") or ""),
            "url": str(item.get("url") or ""),
            "missing_reason": "shortlist_body_missing",
        }
        for item in facts
        if str(item.get("llm_route") or "") == "shortlist_body_missing"
    ]
    identity = {
        "contract_version": "p8_body_missing_queue_v1",
        "source_announcement_run_id": run_id,
        "records": records,
    }
    return {
        "contract_version": identity["contract_version"],
        "source_announcement_run_id": run_id,
        "record_count": len(records),
        "content_digest": _digest(identity),
        "records": records,
    }


def _strict_anomaly_keys(path: Path, *, through: str) -> set[tuple[str, str]]:
    with _connect_ro(path) as connection:
        row = connection.execute(
            "select run_id from p7_runs where run_kind='anomaly' and through<=? "
            "order by through desc,created_at desc limit 1",
            (through,),
        ).fetchone()
        if row is None:
            return set()
        return {
            (str(item[0]), str(item[1]))
            for item in connection.execute(
                "select symbol,trade_date from activity_anomalies "
                "where run_id=? and json_extract(payload_json,'$.strict')=1",
                (str(row[0]),),
            )
        }


def _load_verified_episodes(path: Path) -> list[dict[str, Any]]:
    with _connect_ro(path) as connection:
        return [
            json.loads(str(row[0])) for row in connection.execute(
                "select payload_json from valuation_episodes where evidence_status='verified' order by symbol,start_date"
            )
        ]


def _pilot_inventory(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "unavailable", "case_count": 0}
    with _connect_ro(path) as connection:
        row = connection.execute(
            "select payload_json from pilot_runs order by created_at desc,run_id desc limit 1"
        ).fetchone()
    if row is None:
        return {"status": "unavailable", "case_count": 0}
    payload = json.loads(str(row[0]))
    cases = list(payload.get("cases") or [])
    ledgers = [dict(item.get("old_shareholder_ledger") or {}) for item in cases]
    return {
        "status": "pilot_only",
        "run_id": payload.get("run_id", ""),
        "case_count": len(cases),
        "exact_old_equity_count": sum(bool(item.get("exact_closure")) for item in ledgers),
        "range_or_non_exact_count": sum(not bool(item.get("exact_closure")) for item in ledgers),
        "ledger_status_counts": dict(sorted(Counter(str(item.get("status") or "unknown") for item in ledgers).items())),
        "full_scale_equity_output": payload.get("full_scale_equity_output", "unknown"),
    }


def _reference_inventory(
    facts: list[dict[str, Any]], episodes: list[dict[str, Any]], pilot: dict[str, Any],
) -> dict[str, Any]:
    strategic = [
        item for item in facts
        if item.get("category") == "restructuring_and_pre_restructuring"
        and any(term in str(item.get("title") or "") for term in STRATEGIC_TERMS)
    ]
    closed = [item for item in episodes if not bool(item.get("is_open"))]
    public_events = []
    for item in episodes:
        for event in list(item.get("input_events") or []) + list(item.get("outcome_events") or []):
            if str(event.get("event_type") or "") in PUBLIC_NODE_TYPES:
                public_events.append(event)
    return {
        "strategic_entry_reference": {
            "candidate_count": len(strategic),
            "company_count": len({str(item.get("symbol")) for item in strategic}),
            "body_available_count": sum(bool(item.get("body_available")) for item in strategic),
            "exact_old_equity_count": 0,
            "status": "candidate_only_requires_terms_extraction",
        },
        "failure_exit_reference": {
            "closed_verified_episode_count": len(closed),
            "company_count": len({str(item.get("symbol")) for item in closed}),
            "exchange_terminal_verified_count": 0,
            "exact_old_equity_count": 0,
            "status": "requires_terminal_endpoint_reconciliation",
        },
        "public_node_reference": {
            "verified_p6_event_count": len(public_events),
            "company_count": len({str(item.get("symbol")) for item in public_events}),
            "exact_old_equity_count": 0,
            "status": "market_endpoint_can_be_built; old_equity_requires_capital_structure_ledger",
        },
        "p6b2_old_equity_pilot": pilot,
        "combined_distribution_allowed": False,
    }


def _cell_occupancy(episodes: list[dict[str, Any]], *, as_of: str) -> tuple[dict[str, Any], dict[str, Any]]:
    exact: dict[str, dict[str, int]] = {}
    relaxation: dict[str, Any] = {}
    for months in (12, 18, 24):
        start = _months_before(as_of, months)
        selected = [item for item in episodes if str(item.get("end_date") or "") >= start]
        cells: dict[str, set[str]] = defaultdict(set)
        observations: Counter[str] = Counter()
        groups: dict[str, set[str]] = defaultdict(set)
        group_observations: Counter[str] = Counter()
        for item in selected:
            stage = str(item.get("current_stage") or "unknown")
            symbol = str(item.get("symbol") or "")
            board = _board(symbol)
            # Risk and regime must not be guessed from today's labels.
            regime = regime_for_date(str(item.get("end_date") or as_of)).regime_version
            key = f"{stage}|unknown|{board}|{regime}"
            observations[key] += 1
            cells[key].add(symbol)
            group = next((name for name, members in ADJACENT_STAGE_GROUPS.items() if stage in members), "unknown")
            group_key = f"{group}|unknown|{regime}"
            group_observations[group_key] += 1
            groups[group_key].add(symbol)
        exact[str(months)] = {
            key: {"n": observations[key], "company_n": len(cells[key])}
            for key in sorted(observations)
        }
        dropped_board: dict[str, dict[str, int]] = {}
        aggregate: dict[str, set[str]] = defaultdict(set)
        aggregate_n: Counter[str] = Counter()
        for item in selected:
            stage = str(item.get("current_stage") or "unknown")
            symbol = str(item.get("symbol") or "")
            regime = regime_for_date(str(item.get("end_date") or as_of)).regime_version
            key = f"{stage}|unknown|{regime}"
            aggregate_n[key] += 1
            aggregate[key].add(symbol)
        dropped_board = {
            key: {"n": aggregate_n[key], "company_n": len(aggregate[key])}
            for key in sorted(aggregate_n)
        }
        adjacent = {
            key: {"n": group_observations[key], "company_n": len(groups[key])}
            for key in sorted(group_observations)
        }
        relaxation[str(months)] = {
            "exact_cell_pass_count": sum(value["n"] >= 8 and value["company_n"] >= 5 for value in exact[str(months)].values()),
            "drop_board_pass_count": sum(value["n"] >= 8 and value["company_n"] >= 5 for value in dropped_board.values()),
            "adjacent_stage_pass_count": sum(value["n"] >= 8 and value["company_n"] >= 5 for value in adjacent.values()),
            "drop_board": dropped_board,
            "adjacent_stage": adjacent,
        }
    return {
        "semantic_status": "episode_capacity_only_not_reference_distribution",
        "risk_type_status": "unknown_until_point_in_time_reason_registry",
        "regime_version_status": "registered",
        "regime_registry_version": REGIME_REGISTRY_VERSION,
        "by_window_months": exact,
    }, relaxation


def _body_inventory(
    facts: list[dict[str, Any]], *, base_database: Path, body_cache_directory: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    routed = [item for item in facts if str(item.get("llm_route") or "") != "not_required"]
    shortlist = [item for item in routed if str(item.get("llm_route") or "").startswith("shortlist_")]
    shortlist_ids = {str(item.get("announcement_id")) for item in shortlist}
    content_digests: set[str] = set()
    body_lengths: list[int] = []
    body_chunk_counts: list[int] = []
    raw_paths = 0
    with _connect_ro(base_database) as connection:
        for row in connection.execute(
            "select announcement_id,body_text,raw_path from company_announcements where body_text is not null and length(trim(body_text))>0"
        ):
            if str(row[0]) not in shortlist_ids:
                continue
            body = str(row[1])
            content_digests.add(hashlib.sha256(body.encode("utf-8")).hexdigest())
            body_lengths.append(len(body))
            body_chunk_counts.append(len(_body_chunks(body)))
            raw_paths += bool(str(row[2] or "").strip())
    cache_files = list(body_cache_directory.rglob("*.json")) if body_cache_directory.is_dir() else []
    route_counts = Counter(str(item.get("llm_route") or "unknown") for item in facts)
    category_counts = Counter(str(item.get("category") or "unknown") for item in shortlist)
    inventory = {
        "announcement_run_id": "",
        "fact_count": len(facts),
        "route_counts": dict(sorted(route_counts.items())),
        "shortlist_count": len(shortlist),
        "shortlist_body_available_count": sum(bool(item.get("body_available")) for item in shortlist),
        "shortlist_body_located_count": len(body_lengths),
        "body_availability_mismatch_count": abs(
            sum(bool(item.get("body_available")) for item in shortlist) - len(body_lengths)
        ),
        "shortlist_body_missing_count": sum(not bool(item.get("body_available")) for item in shortlist),
        "shortlist_unique_content_digest_count": len(content_digests),
        "shortlist_raw_path_count": raw_paths,
        "shortlist_category_counts": dict(sorted(category_counts.items())),
        "local_body_cache_file_count": len(cache_files),
        "body_character_count": sum(body_lengths),
        "body_length_median": sorted(body_lengths)[len(body_lengths) // 2] if body_lengths else 0,
        "body_length_maximum": max(body_lengths, default=0),
        "body_chunk_call_count": sum(body_chunk_counts),
        "multi_chunk_announcement_count": sum(value > 1 for value in body_chunk_counts),
        "pdf_scan_status": "not_inferable_from_existing_text_only_inventory",
    }
    missing = inventory["shortlist_body_missing_count"]
    llm_budget = {
        "deterministic_hard_fact_count": route_counts.get("deterministic_hard_fact", 0),
        "structured_llm_existing_body_announcement_jobs": inventory["shortlist_body_located_count"],
        "structured_llm_existing_body_chunk_calls": inventory["body_chunk_call_count"],
        "body_fetch_jobs_after_announcement_id_dedup": missing,
        "maximum_structured_llm_announcement_jobs_after_body_fill": len(shortlist),
        "future_chunk_calls": "unknown_until_missing_bodies_are_fetched",
        "extraction_contract_version": EXTRACTION_CONTRACT_VERSION,
        "prompt_version": PROMPT_VERSION,
        "input_character_count": inventory["body_character_count"],
        "default_workers": 4,
        "maximum_call_attempts": MAX_CALL_ATTEMPTS,
        "timeout_seconds_per_attempt": CALL_TIMEOUT_SECONDS,
        "four_worker_all_attempts_timeout_upper_bound_seconds": (
            ((inventory["body_chunk_call_count"] + 3) // 4)
            * (MAX_CALL_ATTEMPTS * CALL_TIMEOUT_SECONDS + sum(RETRY_BACKOFF_SECONDS))
        ),
        "billing_cost_status": "unknown_until_owner_approves_model_and_current_provider_pricing",
        "batch_key": "announcement_id+content_digest+chunk_index+extractor_version+model+prompt_version",
        "current_llm_execution_status": "not_run",
    }
    return inventory, llm_budget


def _event_graph_inventory(path: Path, run_id: str) -> dict[str, Any]:
    with _connect_ro(path) as connection:
        rows = [
            json.loads(str(row[0])) for row in connection.execute(
                "select payload_json from issuer_transitions where run_id=? order by available_as_of,transition_id",
                (run_id,),
            )
        ]
    event_types = Counter(str(item.get("event_type") or "unknown") for item in rows)
    dimensions = Counter(str(item.get("dimension") or "unknown") for item in rows)
    evidence = Counter(str(item.get("evidence_status") or "unknown") for item in rows)
    return {
        "p7_title_transition_count": len(rows),
        "company_count": len({str(item.get("symbol")) for item in rows}),
        "event_type_counts": dict(sorted(event_types.items())),
        "dimension_counts": dict(sorted(dimensions.items())),
        "evidence_status_counts": dict(sorted(evidence.items())),
        "body_verified_count": 0,
        "track_registry_status": "required_before_materialization",
        "p7_title_verified_is_p8_body_verified": False,
    }


def _load_qfq_and_benchmarks(
    *, base_database: Path, context_database: Path, symbols: set[str], start_date: str, through: str,
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], float]]:
    qfq: dict[tuple[str, str], float] = {}
    with _connect_ro(base_database) as connection:
        for row in connection.execute(
            "select symbol,trade_date,close from daily_prices where adjust='qfq' and trade_date between ? and ? and close>0",
            (start_date, through),
        ):
            if str(row[0]) in symbols:
                qfq[(str(row[0]), str(row[1]))] = float(row[2])
    benchmarks: dict[tuple[str, str], float] = {}
    with _connect_ro(context_database) as connection:
        for row in connection.execute(
            "select benchmark_id,trade_date,close from benchmark_daily where benchmark_id in ('st_equal_weight_v1','csi_2000') and trade_date between ? and ? and close>0",
            (start_date, through),
        ):
            benchmarks[(str(row[0]), str(row[1]))] = float(row[2])
    return qfq, benchmarks


def _return_endpoint_inventory(
    episodes: list[dict[str, Any]], *, base_database: Path, as_of: str, pilot: dict[str, Any],
) -> dict[str, Any]:
    start_exact = 0
    end_exact = 0
    both = 0
    closed = 0
    delisted = 0
    with _connect_ro(base_database) as connection:
        delisted_symbols = {
            str(row[0]) for row in connection.execute(
                "select distinct symbol from st_status_history "
                "where upper(coalesce(notes,'')) like '%FINAL_STATUS%DELISTED%'"
            )
        }
        for item in episodes:
            symbol = str(item.get("symbol") or "")
            start_date = str(item.get("start_date") or "")
            end_date = str(item.get("end_date") or "")
            start_row = connection.execute(
                "select trade_date from daily_prices where symbol=? and adjust='qfq' and trade_date>=? and close>0 order by trade_date limit 1",
                (symbol, start_date),
            ).fetchone()
            end_row = connection.execute(
                "select trade_date from daily_prices where symbol=? and adjust='qfq' and trade_date>=? and trade_date<=? and close>0 order by trade_date limit 1",
                (symbol, end_date, as_of),
            ).fetchone()
            start_exact += bool(start_row)
            end_exact += bool(end_row)
            both += bool(start_row and end_row)
            closed += not bool(item.get("is_open"))
            delisted += symbol in delisted_symbols
    return {
        "verified_episode_count": len(episodes),
        "closed_episode_count": closed,
        "qfq_start_endpoint_count": start_exact,
        "qfq_end_or_asof_endpoint_count": end_exact,
        "observable_qfq_path_count": both,
        "delisted_symbol_episode_count": delisted,
        "delisting_dual_terminal_materialized_count": 0,
        "old_shareholder_equity_path": {
            "exact": int(pilot.get("exact_old_equity_count") or 0),
            "range_or_non_exact": int(pilot.get("range_or_non_exact_count") or 0),
            "unknown_outside_pilot": max(0, len(episodes) - int(pilot.get("case_count") or 0)),
            "scope": "p6b2_pilot_only",
        },
        "capital_structure_contamination_materialized_count": 0,
        "concurrent_calendar_portfolio_status": "price_inputs_available_not_materialized",
    }


def build_p8_dry_plan(
    *, base_database: Path, market_context_database: Path,
    market_factor_database: Path, valuation_episode_database: Path,
    valuation_facts_database: Path, p7_intelligence_database: Path,
    market_activity_database: Path, announcement_body_cache_directory: Path,
    as_of: str, repo: Path, chip_provider_probe: dict[str, Any] | None = None,
) -> P8DryPlan:
    date.fromisoformat(as_of)
    inputs = [
        _source(base_database, "base_database"),
        _source(market_context_database, "market_context_v1"),
        _source(market_factor_database, "market_factors_v1"),
        _source(valuation_episode_database, "valuation_episode_v1"),
        _source(valuation_facts_database, "valuation_facts_v1"),
        _source(p7_intelligence_database, "p7_intelligence_v1"),
        _source(market_activity_database, "market_activity_v1"),
    ]
    facts_run_id, facts = _load_p7_announcement_facts(p7_intelligence_database)
    episodes = _load_verified_episodes(valuation_episode_database)
    pilot = _pilot_inventory(valuation_facts_database)
    reference_inventory = _reference_inventory(facts, episodes, pilot)
    cells, relaxation = _cell_occupancy(episodes, as_of=as_of)
    body, llm_budget = _body_inventory(
        facts, base_database=base_database,
        body_cache_directory=announcement_body_cache_directory,
    )
    body["announcement_run_id"] = facts_run_id
    graph = _event_graph_inventory(p7_intelligence_database, facts_run_id)

    activity_facts = MarketActivityRepository(market_activity_database).latest_facts(through=as_of)
    symbols = {item.symbol for item in activity_facts}
    activity_start = min((item.trade_date for item in activity_facts), default=as_of)
    qfq, benchmarks = _load_qfq_and_benchmarks(
        base_database=base_database, context_database=market_context_database,
        symbols=symbols, start_date=activity_start, through=as_of,
    )
    features = build_activity_features(
        activity_facts, qfq_close_by_symbol_date=qfq,
        benchmark_close_by_id_date=benchmarks,
    )
    strict_keys = _strict_anomaly_keys(p7_intelligence_database, through=as_of)
    strict_feature_ids = {
        item.feature_id for item in features if (item.symbol, item.trade_date) in strict_keys
    }
    capacity = profile_capacity(features, strict_feature_ids=strict_feature_ids)
    selected_profile = choose_capacity_profile(capacity)
    calculable = sum(item.calculable for item in features)
    feature_capacity = {
        "activity_fact_count": len(activity_facts),
        "feature_count": len(features),
        "calculable_count": calculable,
        "calculable_rate": round(calculable / len(features), 8) if features else 0.0,
        "first_calculable_date": min((item.trade_date for item in features if item.calculable), default=""),
        "last_calculable_date": max((item.trade_date for item in features if item.calculable), default=""),
        "field_non_null_rates": {
            field: round(sum(getattr(item, field) is not None for item in features) / len(features), 8) if features else 0.0
            for field in (
                "cum_turnover_log_excess_10", "cum_turnover_log_excess_20",
                "elevated_day_ratio_20", "range_compression_20", "price_drift_20",
                "excess_return_st_20", "excess_return_csi2000_20",
                "amount_weighted_log_price_slope_20", "single_day_qfq_return",
                "single_day_excess_return_st", "single_day_amplitude_ratio",
                "st_turnover_regime_change_20",
            )
        },
        "profiles": capacity,
        "strict_single_day_input_count": len(strict_feature_ids),
        "threshold_selection_uses_outcomes": False,
    }
    return_inventory = _return_endpoint_inventory(
        episodes, base_database=base_database, as_of=as_of, pilot=pilot,
    )

    chip = chip_provider_probe or {
        endpoint: {"status": "not_probed", "blocking": False}
        for endpoint in ("stk_holdernumber", "top_list", "top_inst", "block_trade", "margin_detail")
    }
    blockers = []
    if pilot.get("exact_old_equity_count", 0) == 0:
        blockers.append("现有 P6B-2 pilot 的精确旧股东权益账为 0；P8A p* 与 P8E 精确权益账必须保持 unknown。")
    if not features or selected_profile == "unavailable":
        blockers.append("P8C 没有可运营的 outcome-blind 容量 profile。")

    gaps = [
        f"shortlist 仍有 {body['shortlist_body_missing_count']} 条正文缺失，P8B 只能先物化 body-available 子集。",
        "P7 标题状态机不是 P8 body-verified 阶段真值。",
    ]
    if any(item.get("status") in {"not_probed", "unavailable", "permission_denied"} for item in chip.values()):
        gaps.append("一个或多个筹码代理尚未可用；它们保持 unavailable，不阻塞核心漏斗。")

    request_budget = {
        "body_fetch_jobs": body["shortlist_body_missing_count"],
        "structured_llm_announcement_jobs_now": body["shortlist_body_located_count"],
        "structured_llm_chunk_calls_now": body["body_chunk_call_count"],
        "structured_llm_announcement_jobs_after_body_fill_max": body["shortlist_count"],
        "structured_llm_chunk_calls_after_body_fill": "unknown_until_missing_bodies_are_fetched",
        "chip_probe_calls": 5,
        "production_provider_calls_in_p8_0a": 0,
    }
    storage_budget = {
        "current_input_bytes": sum(int(item.get("size_bytes") or 0) for item in inputs),
        "p8_0_production_database_writes": 0,
        "body_text_character_count_in_shortlist": body["body_character_count"],
        "append_only_p8_database_estimate": "depends_on_body_fill_and_llm_payload; preserve source spans without copying PDFs",
    }
    source_boundaries = {
        "p6_p7_mutated": False,
        "production_database_writes": 0,
        "outcomes_read_for_shape_thresholds": False,
        "title_only_promoted_to_body_verified": False,
        "reference_families_combined": False,
        "unknown_merged_into_known_cells": False,
    }
    safe_defaults = [
        "先实现 body-available 子集并导出正文缺口队列，不伪造 LLM 已运行。",
        "三类成交情景参考分账；旧股东口径不闭合就 range/unknown。",
        f"P8C 形态 profile 冻结为 {selected_profile}，选择只使用覆盖与每日容量。",
        (
            "筹码接口小样本均可用；仍按各自 available-date 与缺失语义保存，不以零值替代。"
            if chip and all(item.get("status") in {"success", "empty_valid"} for item in chip.values())
            else "筹码接口不可用时保留缺失语义，不以零值替代。"
        ),
    ]
    identity = {
        "contract_version": CONTRACT_VERSION,
        "as_of": as_of,
        "input_digests": {item["source_id"]: item.get("digest", "") for item in inputs},
        "scenario_reference_inventory": reference_inventory,
        "cell_occupancy": cells,
        "body_inventory": body,
        "activity_feature_capacity": feature_capacity,
        "frozen_shape_profile": selected_profile,
        "chip_provider_probe": chip,
        "return_endpoint_inventory": return_inventory,
    }
    content_digest = _digest(identity)
    return P8DryPlan(
        plan_id=f"P8DP-{content_digest[:20].upper()}",
        content_digest=content_digest,
        generated_at=datetime.now(timezone.utc).isoformat(),
        as_of=as_of,
        git_provenance=_git_provenance(repo),
        input_inventory=inputs,
        source_boundaries=source_boundaries,
        scenario_reference_inventory=reference_inventory,
        cell_occupancy=cells,
        relaxation_capacity=relaxation,
        body_inventory=body,
        event_graph_inventory=graph,
        llm_request_budget=llm_budget,
        activity_feature_capacity=feature_capacity,
        frozen_shape_profile=selected_profile,
        chip_provider_probe=chip,
        return_endpoint_inventory=return_inventory,
        request_budget=request_budget,
        storage_budget=storage_budget,
        hard_blockers=blockers,
        non_blocking_gaps=gaps,
        safe_defaults=safe_defaults,
        recommended_next_step=(
            "物化 P8 append-only repository、body-available 事件图、P8C 特征与 P8E qfq 观察账；"
            "筹码代理先按日小步增量，不做无边界全历史回填。"
        ),
        human_decisions_required=[],
    )


def render_markdown(plan: P8DryPlan) -> str:
    refs = plan.scenario_reference_inventory
    features = plan.activity_feature_capacity
    return "\n".join([
        "# P8-0 数据门真实盘点",
        "",
        f"- plan：`{plan.plan_id}`",
        f"- 截止：{plan.as_of}",
        f"- 形态容量 profile：`{plan.frozen_shape_profile}`（未读取未来结果）",
        f"- 公告 shortlist：{plan.body_inventory['shortlist_count']:,} 条；已有正文 "
        f"{plan.body_inventory['shortlist_body_available_count']:,}，缺失 "
        f"{plan.body_inventory['shortlist_body_missing_count']:,}",
        f"- 累积特征：{features['calculable_count']:,}/{features['feature_count']:,} 可完整计算",
        f"- qfq episode 路径：{plan.return_endpoint_inventory['observable_qfq_path_count']:,}/"
        f"{plan.return_endpoint_inventory['verified_episode_count']:,}",
        f"- 精确旧股东权益账：{refs['p6b2_old_equity_pilot'].get('exact_old_equity_count', 0)}（现有 pilot）",
        f"- owner 必须判断：{len(plan.human_decisions_required)} 项",
        "",
        "## 结论",
        "",
        "P8C 的持续型量价和 P8E 的 qfq 观察账可以直接开工；P8B 先处理已有正文子集，再按公告 ID"
        "补齐。P8A 可以搭好三类参考、已登记的退出制度版本与降级路径，但公司自身同口径成功/"
        "失败旧股东权益账未闭合前，不发布统一分位或 p*。这不是失败，而是本轮数据边界。",
        "",
        "## 硬阻塞（只阻塞对应输出）",
        "",
        *[f"- {item}" for item in plan.hard_blockers],
        "",
        "## 安全默认",
        "",
        *[f"- {item}" for item in plan.safe_defaults],
        "",
        "## 三类参考库存",
        "",
        "| 类型 | 候选/episode | 公司 | 正文/端点状态 | 精确旧股东口径 |",
        "| --- | ---: | ---: | --- | ---: |",
        f"| 战略投资人 | {refs['strategic_entry_reference']['candidate_count']} | "
        f"{refs['strategic_entry_reference']['company_count']} | 正文 "
        f"{refs['strategic_entry_reference']['body_available_count']} | 0 |",
        f"| 失败退出 | {refs['failure_exit_reference']['closed_verified_episode_count']} | "
        f"{refs['failure_exit_reference']['company_count']} | 终端待核证 | 0 |",
        f"| 公开节点 | {refs['public_node_reference']['verified_p6_event_count']} | "
        f"{refs['public_node_reference']['company_count']} | 市场端点可建 | 0 |",
        "",
        "## 下一步",
        "",
        plan.recommended_next_step,
        "",
    ])


def render_html(plan: P8DryPlan) -> str:
    body = plan.body_inventory
    features = plan.activity_feature_capacity
    cards = [
        ("公告正文", f"{body['shortlist_body_available_count']:,} / {body['shortlist_count']:,}", "已有正文 / shortlist"),
        ("累积特征", f"{features['calculable_count']:,} / {features['feature_count']:,}", "完整可计算"),
        ("qfq 路径", f"{plan.return_endpoint_inventory['observable_qfq_path_count']:,} / {plan.return_endpoint_inventory['verified_episode_count']:,}", "episode"),
        ("人类必审", str(len(plan.human_decisions_required)), "项"),
    ]
    card_html = "".join(
        f"<article><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong><small>{html.escape(note)}</small></article>"
        for label, value, note in cards
    )
    blockers = "".join(f"<li>{html.escape(item)}</li>" for item in plan.hard_blockers)
    defaults = "".join(f"<li>{html.escape(item)}</li>" for item in plan.safe_defaults)
    return f"""<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>P8-0 数据门</title><style>
:root{{--ink:#17211c;--muted:#647067;--paper:#f3f0e8;--card:#fffdf8;--line:#d9d2c2;--green:#315c48;--amber:#9a6218}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}
main{{max-width:1080px;margin:auto;padding:56px 28px 80px}}h1{{font:700 clamp(34px,6vw,66px)/1.05 Georgia,"Songti SC",serif;margin:10px 0 14px}}.eyebrow{{letter-spacing:.13em;text-transform:uppercase;color:var(--green);font-weight:700}}.lead{{max-width:800px;font-size:20px;color:var(--muted)}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:34px 0}}article,section{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px}}article span,article small{{display:block;color:var(--muted)}}article strong{{display:block;font:700 30px/1.2 Georgia,serif;margin:10px 0}}section{{margin-top:16px}}h2{{margin:0 0 12px;font-size:20px}}li{{margin:8px 0}}.status{{display:inline-block;padding:5px 10px;border-radius:99px;background:#dfeade;color:var(--green);font-weight:700}}.warn{{border-left:5px solid var(--amber)}}footer{{margin-top:28px;color:var(--muted);font-size:13px}}
@media(max-width:760px){{.grid{{grid-template-columns:1fr 1fr}}}}@media(max-width:440px){{.grid{{grid-template-columns:1fr}}main{{padding:30px 16px}}}}
</style><main><div class=\"eyebrow\">P8 / outcome-blind capacity gate</div><h1>管道能做什么，先由数据说。</h1>
<p class=\"lead\">这不是信号成绩单。它只盘点覆盖、口径和工作量，并把无法诚实计算的部分留空。</p>
<span class=\"status\">{html.escape(plan.frozen_shape_profile)} profile · owner 必审 0</span><div class=\"grid\">{card_html}</div>
<section class=\"warn\"><h2>当前边界</h2><ul>{blockers}</ul></section><section><h2>系统自动采用的安全默认</h2><ul>{defaults}</ul></section>
<section><h2>下一步</h2><p>{html.escape(plan.recommended_next_step)}</p></section>
<footer>{html.escape(plan.plan_id)} · 截止 {html.escape(plan.as_of)} · 结果摘要 {html.escape(plan.content_digest[:16])}</footer></main></html>"""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--base-database", type=Path, default=DEFAULT_BASE_DB)
    parser.add_argument("--market-context-database", type=Path, default=MARKET_CONTEXT_DB)
    parser.add_argument("--market-factor-database", type=Path, default=MARKET_FACTOR_DB)
    parser.add_argument("--valuation-episode-database", type=Path, default=VALUATION_EPISODE_DB)
    parser.add_argument("--valuation-facts-database", type=Path, default=VALUATION_FACTS_DB)
    parser.add_argument("--p7-intelligence-database", type=Path, default=P7_INTELLIGENCE_DB)
    parser.add_argument("--market-activity-database", type=Path, default=MARKET_ACTIVITY_DB)
    parser.add_argument("--announcement-body-cache-directory", type=Path, default=ANNOUNCEMENT_BODY_CACHE_DIR)
    parser.add_argument("--chip-provider-probe-json", type=Path)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path)
    parser.add_argument("--output-html", type=Path)
    parser.add_argument("--output-body-missing-json", type=Path)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    chip_probe = None
    if args.chip_provider_probe_json:
        probe_payload = json.loads(args.chip_provider_probe_json.read_text(encoding="utf-8"))
        chip_probe = probe_payload.get("endpoint_summary", probe_payload)
    plan = build_p8_dry_plan(
        base_database=args.base_database,
        market_context_database=args.market_context_database,
        market_factor_database=args.market_factor_database,
        valuation_episode_database=args.valuation_episode_database,
        valuation_facts_database=args.valuation_facts_database,
        p7_intelligence_database=args.p7_intelligence_database,
        market_activity_database=args.market_activity_database,
        announcement_body_cache_directory=args.announcement_body_cache_directory,
        as_of=args.as_of,
        repo=args.repo,
        chip_provider_probe=chip_probe,
    )
    atomic_write_json(args.output_json, plan.model_dump(mode="json"))
    body_missing_path = (
        args.output_body_missing_json
        or args.output_json.with_name("p8_body_missing_queue_v1.json")
    )
    atomic_write_json(
        body_missing_path,
        build_body_missing_queue(args.p7_intelligence_database),
    )
    if args.output_markdown:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(render_markdown(plan), encoding="utf-8")
    if args.output_html:
        args.output_html.parent.mkdir(parents=True, exist_ok=True)
        args.output_html.write_text(render_html(plan), encoding="utf-8")
    print(json.dumps({
        "plan_id": plan.plan_id,
        "output_json": str(args.output_json),
        "body_missing_queue_json": str(body_missing_path),
        "human_decisions_required": len(plan.human_decisions_required),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
