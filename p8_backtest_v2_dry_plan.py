"""Outcome-blind capacity inventory for the frozen P8 backtest v2 contract."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sqlite3
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_refresh import atomic_write_json
from p7_daily import load_valuation_stage_map
from p8_backtest_v2 import build_holder_scores
from p8_research import P8ResearchRepository, build_run, canonical_json, content_id
from p8_regimes import REGISTRY_VERSION as REGIME_REGISTRY_VERSION, regime_for_date
from settings import (
    DATA_ROOT,
    MARKET_ACTIVITY_DB,
    MARKET_CONTEXT_DB,
    P8_RESEARCH_DB,
    VALUATION_EPISODE_DB,
)


CONTRACT_VERSION = "v8_p8_backtest_dry_plan_v1"
START_DATE = "2021-03-17"
THROUGH = "2025-12-31"
TEST_YEARS = (2023, 2024, 2025)
MIN_CELL_OBSERVATIONS = 12
MIN_CELL_COMPANIES = 8
MIN_SIGNAL_OBSERVATIONS = 100
MIN_SIGNAL_COMPANIES = 40
DEFAULT_BASE_DB = DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"
CONTRACT_FILE = Path(__file__).resolve().parent / "V8_P8_BACKTEST_DRY_PLAN_CONTRACT.md"


def _connect_ro(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _file_digest(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _git_provenance(repo: Path) -> dict[str, str]:
    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=repo, check=True, capture_output=True, text=True,
        ).stdout.strip()

    return {
        "commit": run("rev-parse", "HEAD"),
        "branch": run("branch", "--show-current"),
        "worktree_status": "clean" if not run("status", "--short") else "dirty",
        "contract_digest": _file_digest(CONTRACT_FILE),
        "materializer_digest": _file_digest(Path(__file__).resolve()),
    }


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


def _latest_run_id(connection: sqlite3.Connection, run_kind: str) -> str:
    row = connection.execute(
        "select run_id from p8_runs where run_kind=? "
        "order by created_at desc,run_id desc limit 1", (run_kind,),
    ).fetchone()
    return str(row[0]) if row else ""


def _p8_source_digest(path: Path) -> str:
    """Hash upstream run identities, not the DB file that will receive this plan."""

    if not path.is_file():
        return ""
    source_kinds = (
        "activity_features", "event_graph", "scenario_references",
        "chip_proxies", "p8_holder_history_v2", "funnel", "portfolio", "return_paths",
    )
    latest: dict[str, dict[str, str]] = {}
    with _connect_ro(path) as connection:
        for kind in source_kinds:
            row = connection.execute(
                "select run_id,content_digest from p8_runs where run_kind=? "
                "order by created_at desc,run_id desc limit 1", (kind,),
            ).fetchone()
            if row:
                latest[kind] = {"run_id": str(row[0]), "content_digest": str(row[1])}
    return _digest(latest)


def _latest_records(path: Path, run_kind: str, record_type: str) -> tuple[str, list[dict[str, Any]]]:
    if not path.is_file():
        return "", []
    with _connect_ro(path) as connection:
        run_id = _latest_run_id(connection, run_kind)
        if not run_id:
            return "", []
        rows = connection.execute(
            "select payload_json from p8_records where run_id=? and record_type=? "
            "order by available_as_of,record_id", (run_id, record_type),
        )
        return run_id, [json.loads(str(row[0])) for row in rows]


def _calendar_and_membership(path: Path) -> tuple[list[str], dict[str, set[str]]]:
    with _connect_ro(path) as connection:
        calendar = [str(row[0]) for row in connection.execute(
            "select trade_date from benchmark_daily where benchmark_id='csi_all_share' "
            "and trade_date between ? and ? order by trade_date", (START_DATE, THROUGH),
        )]
        members: dict[str, set[str]] = defaultdict(set)
        for row in connection.execute(
            "select trade_date,symbol from st_membership_daily "
            "where trade_date between ? and ? order by trade_date,symbol", (START_DATE, THROUGH),
        ):
            members[str(row[0])].add(str(row[1]))
    return calendar, dict(members)


def _benchmark_dates(path: Path) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    with _connect_ro(path) as connection:
        for row in connection.execute(
            "select benchmark_id,trade_date from benchmark_daily "
            "where benchmark_id in ('st_equal_weight_v1','csi_2000') "
            "and trade_date between ? and ? and close>0", (START_DATE, THROUGH),
        ):
            result[str(row[0])].add(str(row[1]))
    return dict(result)


def _qfq_keys(path: Path) -> set[tuple[str, str]]:
    with _connect_ro(path) as connection:
        return {
            (str(row[0]), str(row[1])) for row in connection.execute(
                "select symbol,trade_date from daily_prices where adjust='qfq' "
                "and trade_date between ? and ? and close>0", (START_DATE, THROUGH),
            )
        }


def _activity_by_day(path: Path) -> tuple[dict[str, dict[str, Any]], int, int]:
    if not path.is_file():
        return {}, 0, 0
    with _connect_ro(path) as connection:
        rows = connection.execute(
            "with ranked as (select *,row_number() over(partition by trade_date "
            "order by fetched_at desc,snapshot_id desc) rn from activity_snapshots "
            "where trade_date between ? and ?) "
            "select * from ranked where rn=1 order by trade_date", (START_DATE, THROUGH),
        ).fetchall()
        latest = {str(row["trade_date"]): dict(row) for row in rows}
        fact_count = 0
        complete_trade_state = 0
        if latest:
            placeholders = ",".join("?" for _ in latest)
            snapshot_ids = [str(item["snapshot_id"]) for item in latest.values()]
            for row in connection.execute(
                f"select payload_json from market_activity_daily where snapshot_id in ({placeholders})",
                snapshot_ids,
            ):
                item = json.loads(str(row[0]))
                fact_count += 1
                if (
                    item.get("suspension_status") != "unknown"
                    and item.get("one_price_limit") is not None
                    and not bool(item.get("limit_state_conflict"))
                ):
                    complete_trade_state += 1
    return latest, fact_count, complete_trade_state


def _date_coverage(
    *, calendar: list[str], memberships: dict[str, set[str]],
    benchmarks: dict[str, set[str]], qfq: set[tuple[str, str]],
    activity: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    missing_activity: list[str] = []
    complete_dates: list[str] = []
    for day in calendar:
        members = memberships.get(day, set())
        member_n = len(members)
        qfq_n = sum((symbol, day) in qfq for symbol in members)
        snapshot = activity.get(day)
        turnover_n = int(snapshot.get("valid_turnover_rate_f_count") or 0) if snapshot else 0
        activity_member_n = int(snapshot.get("membership_count") or 0) if snapshot else 0
        membership_ready = member_n > 0
        qfq_coverage = qfq_n / member_n if member_n else 0.0
        turnover_coverage = turnover_n / member_n if member_n else 0.0
        activity_membership_matches = bool(snapshot and activity_member_n == member_n)
        st_ready = day in benchmarks.get("st_equal_weight_v1", set())
        csi_ready = day in benchmarks.get("csi_2000", set())
        complete = bool(
            membership_ready and activity_membership_matches
            and qfq_coverage >= .95 and turnover_coverage >= .95 and st_ready
            and int(snapshot.get("daily_row_count") or 0) > 0
            and int(snapshot.get("daily_basic_row_count") or 0) > 0
            and int(snapshot.get("limit_row_count") or 0) > 0
        ) if snapshot else False
        if not snapshot:
            missing_activity.append(day)
        if complete:
            complete_dates.append(day)
        records.append({
            "trade_date": day,
            "year": int(day[:4]),
            "membership_count": member_n,
            "membership_ready": membership_ready,
            "qfq_count": qfq_n,
            "qfq_coverage": round(qfq_coverage, 8),
            "activity_snapshot_id": str(snapshot.get("snapshot_id") or "") if snapshot else "",
            "activity_membership_matches": activity_membership_matches,
            "turnover_rate_f_count": turnover_n,
            "turnover_rate_f_coverage": round(turnover_coverage, 8),
            "st_benchmark_ready": st_ready,
            "csi2000_ready": csi_ready,
            "complete_for_v2_inputs": complete,
            "regime_version": regime_for_date(day).regime_version,
            "market_cap_rule_effective": day >= "2024-10-30",
            "annual_report_season": "04-01" <= day[5:] <= "06-30",
            "calendar_half": _half(day),
        })
    summary = {
        "start_date": calendar[0] if calendar else "",
        "through": calendar[-1] if calendar else "",
        "calendar_date_count": len(calendar),
        "membership_date_count": sum(bool(memberships.get(day)) for day in calendar),
        "activity_snapshot_date_count": sum(day in activity for day in calendar),
        "complete_input_date_count": len(complete_dates),
        "missing_activity_date_count": len(missing_activity),
        "missing_activity_dates": missing_activity,
        "by_year": {},
    }
    for year in range(2021, 2026):
        year_rows = [item for item in records if item["year"] == year]
        summary["by_year"][str(year)] = {
            "calendar_dates": len(year_rows),
            "membership_ready_dates": sum(bool(item["membership_ready"]) for item in year_rows),
            "activity_dates": sum(bool(item["activity_snapshot_id"]) for item in year_rows),
            "complete_input_dates": sum(bool(item["complete_for_v2_inputs"]) for item in year_rows),
            "st_benchmark_dates": sum(bool(item["st_benchmark_ready"]) for item in year_rows),
            "csi2000_dates": sum(bool(item["csi2000_ready"]) for item in year_rows),
        }
    return records, summary


def _feature_capacity(
    *, repository: Path, valuation_episode_database: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    run_id, features = _latest_records(repository, "activity_features", "activity_feature")
    test_features = [
        item for item in features if int(str(item.get("trade_date") or "0000")[:4] or 0) in TEST_YEARS
    ]
    dates = sorted({str(item.get("trade_date") or "") for item in test_features})
    stage_map = load_valuation_stage_map(valuation_episode_database, dates=dates)
    cell_members: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    cell_observations: Counter[tuple[str, str, str]] = Counter()
    relaxed_members: dict[tuple[str, str], set[str]] = defaultdict(set)
    relaxed_observations: Counter[tuple[str, str]] = Counter()
    accumulation_symbols: set[str] = set()
    accumulation_n = 0
    for item in test_features:
        symbol = str(item.get("symbol") or "")
        day = str(item.get("trade_date") or "")
        stage = stage_map.get((symbol, day), "unknown")
        if stage == "unknown":
            continue
        key = (stage, _half(day), _board(symbol))
        relaxed_key = (stage, _half(day))
        cell_observations[key] += 1
        cell_members[key].add(symbol)
        relaxed_observations[relaxed_key] += 1
        relaxed_members[relaxed_key].add(symbol)
        required = (
            item.get("cum_turnover_log_excess_20"),
            item.get("elevated_day_ratio_20"),
            item.get("excess_return_st_20"),
            item.get("range_compression_20"),
        )
        if all(value is not None for value in required):
            accumulation_n += 1
            accumulation_symbols.add(symbol)

    exact_cells = [
        {
            "stage": key[0], "calendar_half": key[1], "board": key[2],
            "observation_count": count, "company_count": len(cell_members[key]),
            "passes_cell_gate": count >= MIN_CELL_OBSERVATIONS and len(cell_members[key]) >= MIN_CELL_COMPANIES,
        }
        for key, count in sorted(cell_observations.items())
    ]
    relaxed_cells = [
        {
            "stage": key[0], "calendar_half": key[1], "board": "dropped",
            "observation_count": count, "company_count": len(relaxed_members[key]),
            "passes_cell_gate": count >= MIN_CELL_OBSERVATIONS and len(relaxed_members[key]) >= MIN_CELL_COMPANIES,
        }
        for key, count in sorted(relaxed_observations.items())
    ]
    holder_run_id, holder_records = _latest_records(
        repository, "p8_holder_history_v2", "p8_holder_history_v2",
    )
    holder_dates = sorted({str(item.get("trade_date") or "") for item in holder_records})
    holder_stage_map = load_valuation_stage_map(valuation_episode_database, dates=holder_dates)
    holder_scores = build_holder_scores(holder_records, stage_map=holder_stage_map)
    holder_test_scores = [
        item for item in holder_scores
        if int(str(item.get("trade_date") or "0000")[:4] or 0) in TEST_YEARS
    ]
    holder_symbols = {str(item.get("symbol") or "") for item in holder_test_scores}
    family_capacity = {
        "p8a_p_star": {"observation_count": 0, "company_count": 0, "status": "historical_input_absent"},
        "p8b_precursor": {"observation_count": 0, "company_count": 0, "status": "training_score_not_materialized"},
        "p8c_accumulation": {
            "observation_count": accumulation_n,
            "company_count": len(accumulation_symbols),
            "status": (
                "capacity_gate_passed" if accumulation_n >= MIN_SIGNAL_OBSERVATIONS
                and len(accumulation_symbols) >= MIN_SIGNAL_COMPANIES else "capacity_gate_failed"
            ),
        },
        "p8c_holder": {
            "source_run_id": holder_run_id,
            "source_record_count": len(holder_records),
            "observation_count": len(holder_test_scores),
            "company_count": len(holder_symbols),
            "status": (
                "capacity_gate_passed" if len(holder_test_scores) >= MIN_SIGNAL_OBSERVATIONS
                and len(holder_symbols) >= MIN_SIGNAL_COMPANIES
                else "historical_input_absent" if not holder_records
                else "capacity_gate_failed"
            ),
        },
    }
    return {
        "source_run_id": run_id,
        "source_feature_count": len(features),
        "test_year_feature_count": len(test_features),
        "test_year_feature_dates": len(dates),
        "family_capacity": family_capacity,
        "minimum_signal_observations": MIN_SIGNAL_OBSERVATIONS,
        "minimum_signal_companies": MIN_SIGNAL_COMPANIES,
    }, {"exact_cells": exact_cells, "relaxed_cells": relaxed_cells}


def _event_truth_inventory(repository: Path) -> dict[str, Any]:
    run_id, events = _latest_records(repository, "event_graph", "derived_event")
    status = Counter(str(item.get("evidence_status") or "unknown") for item in events)
    track = Counter(str(item.get("track") or "unknown") for item in events)
    direction = Counter(str(item.get("process_direction") or "unknown") for item in events)
    effect = Counter(str(item.get("old_equity_effect") or "unknown") for item in events)
    by_year = Counter(str(item.get("available_as_of") or "")[:4] for item in events)
    verified_hard = [
        item for item in events
        if item.get("evidence_status") in {"body_verified", "deterministic_verified"}
        and not bool(item.get("not_hard_outcome"))
    ]
    return {
        "source_run_id": run_id,
        "event_count": len(events),
        "by_evidence_status": dict(sorted(status.items())),
        "by_track": dict(sorted(track.items())),
        "by_process_direction": dict(sorted(direction.items())),
        "by_old_equity_effect": dict(sorted(effect.items())),
        "by_year": dict(sorted(by_year.items())),
        "verified_hard_event_count": len(verified_hard),
        "verified_hard_company_count": len({str(item.get("symbol") or "") for item in verified_hard}),
    }


def _gold_capacity(repository: Path) -> dict[str, Any]:
    _run_id, events = _latest_records(repository, "event_graph", "derived_event")
    candidates = [
        item for item in events
        if item.get("source_spans") and item.get("evidence_status") in {
            "body_verified", "deterministic_verified", "title_derived", "provisional",
        }
    ]
    unique_sources = {
        str(source)
        for item in candidates for source in (item.get("source_ids") or []) if source
    }
    return {
        "candidate_event_count": len(candidates),
        "unique_source_count": len(unique_sources),
        "sequential_targets": [60, 120, 200],
        "can_form_60": len(candidates) >= 60,
        "can_form_120": len(candidates) >= 120,
        "can_form_200": len(candidates) >= 200,
        "gold_answers_completed": 0,
        "llm_body_extraction_status": "unavailable_pending_explicit_egress_consent",
    }


def _historical_funnel_capacity(repository: Path) -> dict[str, Any]:
    if not repository.is_file():
        return {"dates_by_year": {}, "test_year_date_count": 0, "status": "absent"}
    with _connect_ro(repository) as connection:
        rows = connection.execute(
            "select through,count(*) from p8_runs where run_kind='funnel' "
            "and through between '2023-01-01' and '2025-12-31' group by through order by through"
        ).fetchall()
    by_year = Counter(str(row[0])[:4] for row in rows)
    return {
        "dates_by_year": {str(year): int(by_year.get(str(year), 0)) for year in TEST_YEARS},
        "test_year_date_count": len(rows),
        "status": "ready" if rows else "requires_point_in_time_replay",
    }


def _basket_capacity(date_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_year: dict[str, Any] = {}
    for year in TEST_YEARS:
        rows = [item for item in date_rows if item["year"] == year]
        complete = [item for item in rows if item["complete_for_v2_inputs"]]
        by_year[str(year)] = {
            "calendar_dates": len(rows),
            "complete_input_dates": len(complete),
            "potential_decision_weeks": len({item["trade_date"][:7] + f"-W{datetime.fromisoformat(item['trade_date']).isocalendar().week:02d}" for item in complete}),
            "st_benchmark_dates": sum(bool(item["st_benchmark_ready"]) for item in rows),
            "tradeability_orders_computed": 0,
        }
    return {
        "by_year": by_year,
        "net_values_computed": 0,
        "returns_read": False,
        "status": (
            "input_history_incomplete" if any(
                item["complete_input_dates"] < item["calendar_dates"]
                for item in by_year.values()
            ) else "input_calendar_ready"
        ),
    }


def build_dry_plan(
    *, base_database: Path, market_context_database: Path,
    market_activity_database: Path, valuation_episode_database: Path,
    p8_repository: Path, repo: Path,
) -> dict[str, Any]:
    calendar, memberships = _calendar_and_membership(market_context_database)
    benchmarks = _benchmark_dates(market_context_database)
    qfq = _qfq_keys(base_database)
    activity, activity_fact_count, complete_trade_state_count = _activity_by_day(market_activity_database)
    date_rows, date_summary = _date_coverage(
        calendar=calendar, memberships=memberships, benchmarks=benchmarks,
        qfq=qfq, activity=activity,
    )
    feature_capacity, stratum_capacity = _feature_capacity(
        repository=p8_repository, valuation_episode_database=valuation_episode_database,
    )
    event_inventory = _event_truth_inventory(p8_repository)
    funnel_capacity = _historical_funnel_capacity(p8_repository)
    basket_capacity = _basket_capacity(date_rows)
    missing_dates = list(date_summary["missing_activity_dates"])
    refresh_dates = [
        str(item["trade_date"]) for item in date_rows if not item["complete_for_v2_inputs"]
    ]
    average_snapshot_bytes = (
        market_activity_database.stat().st_size / max(1, len(activity))
        if market_activity_database.is_file() else 0
    )
    endpoint_plan = {
        endpoint: {"unique_trade_dates": len(refresh_dates), "dates": refresh_dates}
        for endpoint in ("daily", "daily_basic", "stk_limit", "suspend_d")
    }
    blockers: list[str] = []
    if refresh_dates:
        blockers.append(
            f"market_activity 有 {len(refresh_dates)} 个主范围交易日未通过完整输入门，"
            "需按日回填或确认合法停牌缺失后才可运行 v2。"
        )
    if not any(
        item["status"] == "capacity_gate_passed"
        for item in feature_capacity["family_capacity"].values()
    ):
        blockers.append("当前物化范围内没有 signal family 达到 100 个观察/40 家公司的最低门。")
    input_inventory = {
        "base_database": {"path": str(base_database), "digest": _file_digest(base_database)},
        "market_context_database": {"path": str(market_context_database), "digest": _file_digest(market_context_database)},
        "market_activity_database": {"path": str(market_activity_database), "digest": _file_digest(market_activity_database)},
        "valuation_episode_database": {"path": str(valuation_episode_database), "digest": _file_digest(valuation_episode_database)},
        "p8_repository": {"path": str(p8_repository), "digest": _p8_source_digest(p8_repository)},
    }
    identity = {
        "contract_version": CONTRACT_VERSION,
        "contract_digest": _file_digest(CONTRACT_FILE),
        "materializer_digest": _file_digest(Path(__file__).resolve()),
        "range": [START_DATE, THROUGH],
        "input_digests": {key: value["digest"] for key, value in input_inventory.items()},
        "date_summary": date_summary,
        "feature_capacity": feature_capacity,
        "stratum_capacity": stratum_capacity,
        "event_inventory": event_inventory,
        "funnel_capacity": funnel_capacity,
        "basket_capacity": basket_capacity,
    }
    digest = _digest(identity)
    result = {
        "record_id": content_id("P8BT2DP", identity),
        "contract_version": CONTRACT_VERSION,
        "plan_id": f"P8BT2DP-{digest[:20].upper()}",
        "content_digest": digest,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": THROUGH,
        "git_provenance": _git_provenance(repo),
        "input_inventory": input_inventory,
        "date_coverage": date_summary,
        "date_coverage_records": date_rows,
        "endpoint_request_plan": endpoint_plan,
        "feature_capacity": feature_capacity,
        "stratum_capacity": stratum_capacity,
        "event_truth_inventory": event_inventory,
        "gold_queue_capacity": _gold_capacity(p8_repository),
        "historical_funnel_capacity": funnel_capacity,
        "basket_execution_capacity": basket_capacity,
        "regime_boundaries": {
            "registry_version": REGIME_REGISTRY_VERSION,
            "global_2024_rule_effective": "2024-04-30",
            "market_cap_rule_effective": "2024-10-30",
        },
        "request_budget": {
            "date_only": True,
            "missing_trade_dates": len(missing_dates),
            "incomplete_or_missing_trade_dates": len(refresh_dates),
            "endpoint_requests": len(refresh_dates) * 4,
            "provider_calls_executed": 0,
        },
        "storage_budget": {
            "current_activity_bytes": market_activity_database.stat().st_size if market_activity_database.is_file() else 0,
            "average_bytes_per_snapshot": round(average_snapshot_bytes),
            "estimated_incremental_bytes": round(average_snapshot_bytes * len(refresh_dates)),
            "activity_fact_count": activity_fact_count,
            "complete_trade_state_fact_count": complete_trade_state_count,
        },
        "hard_blockers": blockers,
        "non_blocking_gaps": [
            "中证 2000 在 2023-08-11 前缺失，只影响辅助基准，不替代 ST 主基准。",
            "正文 LLM 未获外发授权，只阻塞 body_verified 抽取与金标准确率，不阻塞市场数据回填。",
        ],
        "recommended_next_step": (
            "数据门已通过；按冻结代码物化 score、历史 funnel，再一次性读取正式结果。"
            if not blockers else
            "先完成 hard_blockers 并重新运行本 dry-plan；未过门前不得读取正式结果。"
        ),
        "human_decisions_required": [],
        "outcomes_read": False,
        "returns_computed": False,
        "evidence_status": "outcome_blind_capacity_only",
    }
    return result


def render_markdown(plan: dict[str, Any]) -> str:
    dates = plan["date_coverage"]
    families = plan["feature_capacity"]["family_capacity"]
    return "\n".join([
        "# P8-BT2 无结果数据门",
        "",
        f"- plan：`{plan['plan_id']}`",
        f"- 契约提交：`{plan['git_provenance']['commit']}`",
        f"- 主范围：{START_DATE} 至 {THROUGH}",
        f"- 完整活动日期：{dates['complete_input_date_count']}/{dates['calendar_date_count']}",
        f"- 未通过完整输入门：{plan['request_budget']['incomplete_or_missing_trade_dates']} 天"
        f"（其中无 snapshot {dates['missing_activity_date_count']} 天；4 个端点合计 "
        f"{plan['request_budget']['endpoint_requests']} 次）",
        f"- 历史漏斗日期：{plan['historical_funnel_capacity']['test_year_date_count']}",
        f"- 核证 hard outcome：{plan['event_truth_inventory']['verified_hard_event_count']}",
        f"- 人类必须判断：{len(plan['human_decisions_required'])}",
        "",
        "## 结论",
        "",
        (
            "数据门已通过，可以按冻结代码物化历史漏斗并一次性读取正式结果。"
            if not plan["hard_blockers"] else
            "当前还不能跑正式 v2；下列输入门未通过。这不是信号无效的证据。"
        ) + " 本报告没有读取收益、命中率或股票贡献。",
        "",
        "## 四个信号方向的输入容量",
        "",
        "| 方向 | 观察 | 公司 | 状态 |",
        "| --- | ---: | ---: | --- |",
        *[
            f"| {key} | {value['observation_count']} | {value['company_count']} | {value['status']} |"
            for key, value in families.items()
        ],
        "",
        "## 未通过的数据门" if plan["hard_blockers"] else "## 数据门状态",
        "",
        *([f"- {item}" for item in plan["hard_blockers"]] or ["- 已通过；历史漏斗属于正式物化步骤，不是循环前置条件。"]),
        "",
        "## 下一步",
        "",
        plan["recommended_next_step"],
        "",
    ])


def render_html(plan: dict[str, Any]) -> str:
    dates = plan["date_coverage"]
    families = plan["feature_capacity"]["family_capacity"]
    family_rows = "".join(
        "<tr><td>{}</td><td>{:,}</td><td>{:,}</td><td><code>{}</code></td></tr>".format(
            html.escape(key), int(value["observation_count"]), int(value["company_count"]),
            html.escape(value["status"]),
        ) for key, value in families.items()
    )
    blockers = "".join(f"<li>{html.escape(item)}</li>" for item in plan["hard_blockers"])
    if not blockers:
        blockers = "<li>已通过；历史漏斗将在正式物化步骤中按冻结输入重放。</li>"
    cards = (
        ("完整活动日", f"{dates['complete_input_date_count']:,} / {dates['calendar_date_count']:,}", "输入容量"),
        ("未过输入门", f"{plan['request_budget']['incomplete_or_missing_trade_dates']:,}", f"{plan['request_budget']['endpoint_requests']:,} 次端点请求"),
        ("历史漏斗日", f"{plan['historical_funnel_capacity']['test_year_date_count']:,}", "不得拿当前候选倒填"),
        ("结果读取", "0", "收益 / 命中率 / 贡献"),
    )
    card_html = "".join(
        f"<article><small>{html.escape(label)}</small><strong>{html.escape(value)}</strong><span>{html.escape(note)}</span></article>"
        for label, value, note in cards
    )
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>P8-BT2 无结果数据门</title><style>
:root{{--ink:#14201a;--muted:#647168;--paper:#f1efe7;--card:#fffdf7;--line:#d8d1c1;--green:#24543d;--red:#984734}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}
main{{max-width:1120px;margin:auto;padding:54px 26px 80px}}h1{{font:700 clamp(36px,6vw,68px)/1.02 Georgia,"Songti SC",serif;margin:.15em 0}}
.kicker{{color:var(--green);font-weight:800;letter-spacing:.12em}}.lead{{font-size:20px;max-width:850px;color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:34px 0}}article,section{{background:var(--card);border:1px solid var(--line);border-radius:15px;padding:22px}}
article strong{{display:block;font:700 29px/1.2 Georgia,serif;margin:10px 0}}article small,article span{{color:var(--muted)}}section{{margin-top:16px}}h2{{margin-top:0}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:11px 8px;border-bottom:1px solid var(--line);text-align:left}}.stop{{border-left:5px solid var(--red)}}
.stamp{{display:inline-block;padding:6px 11px;border-radius:99px;background:#dce9df;color:var(--green);font-weight:700}}footer{{margin-top:28px;color:var(--muted);font-size:13px}}
@media(max-width:760px){{.grid{{grid-template-columns:1fr 1fr}}}}@media(max-width:480px){{.grid{{grid-template-columns:1fr}}main{{padding:30px 14px}}}}
</style><main><div class="kicker">P8 / OUTCOME-BLIND GATE</div><h1>先量尺子，不偷看答案。</h1>
<p class="lead">这张卡只说明历史输入够不够。它没有计算收益、节点命中率、胜率或股票贡献。</p>
<span class="stamp">contract {html.escape(plan['git_provenance']['commit'][:12])}</span><div class="grid">{card_html}</div>
<section><h2>四个方向的输入容量</h2><table><thead><tr><th>方向</th><th>观察</th><th>公司</th><th>状态</th></tr></thead><tbody>{family_rows}</tbody></table></section>
<section class="stop"><h2>{'未通过的数据门' if plan['hard_blockers'] else '数据门状态'}</h2><ul>{blockers}</ul></section>
<section><h2>下一步</h2><p>{html.escape(plan['recommended_next_step'])}</p></section>
<footer>{html.escape(plan['plan_id'])} · digest {html.escape(plan['content_digest'][:16])} · 人类必审 0</footer></main></html>'''


def persist_plan(repository: P8ResearchRepository, plan: dict[str, Any]) -> str:
    record = dict(plan)
    # The run ledger already timestamps persistence. Excluding wall-clock output time
    # keeps repeated outcome-blind inventories content-addressed and idempotent.
    record.pop("generated_at", None)
    run = build_run(
        run_kind="p8_backtest_v2_dry_plan",
        contract_version=CONTRACT_VERSION,
        start_date=START_DATE,
        through=THROUGH,
        source_run_ids=[
            value["source_run_id"] for value in (
                plan["feature_capacity"], plan["event_truth_inventory"],
            ) if value.get("source_run_id")
        ],
        source_digests={
            key: value["digest"] for key, value in plan["input_inventory"].items()
        },
        record_payloads={"p8_backtest_v2_dry_plan": [record]},
    )
    repository.persist(run=run, records={"p8_backtest_v2_dry_plan": [record]})
    return run.run_id


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-database", type=Path, default=DEFAULT_BASE_DB)
    parser.add_argument("--market-context-database", type=Path, default=MARKET_CONTEXT_DB)
    parser.add_argument("--market-activity-database", type=Path, default=MARKET_ACTIVITY_DB)
    parser.add_argument("--valuation-episode-database", type=Path, default=VALUATION_EPISODE_DB)
    parser.add_argument("--p8-repository", type=Path, default=P8_RESEARCH_DB)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path)
    parser.add_argument("--output-html", type=Path)
    parser.add_argument("--persist", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    plan = build_dry_plan(
        base_database=args.base_database,
        market_context_database=args.market_context_database,
        market_activity_database=args.market_activity_database,
        valuation_episode_database=args.valuation_episode_database,
        p8_repository=args.p8_repository,
        repo=args.repo,
    )
    atomic_write_json(args.output_json, plan)
    if args.output_markdown:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(render_markdown(plan), encoding="utf-8")
    if args.output_html:
        args.output_html.parent.mkdir(parents=True, exist_ok=True)
        args.output_html.write_text(render_html(plan), encoding="utf-8")
    run_id = persist_plan(P8ResearchRepository(args.p8_repository), plan) if args.persist else ""
    print(json.dumps({
        "plan_id": plan["plan_id"], "run_id": run_id,
        "missing_trade_dates": plan["date_coverage"]["missing_activity_date_count"],
        "endpoint_requests": plan["request_budget"]["endpoint_requests"],
        "outcomes_read": plan["outcomes_read"],
        "human_decisions_required": len(plan["human_decisions_required"]),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
