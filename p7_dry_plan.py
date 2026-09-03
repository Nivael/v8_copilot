"""P7-0a local-only inventory and post-bootstrap capacity report."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import statistics
import subprocess
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from market_activity import MarketActivityRepository
from p7_anomalies import build_anomaly_run
from p7_announcements import classify_announcement, classify_hard_event
from settings import (
    ANNOUNCEMENT_REFRESH_DIR, DATA_ROOT, MARKET_ACTIVITY_DB,
    MARKET_CONTEXT_DB, MARKET_FACTOR_DB,
)


CONTRACT_VERSION = "v8_p7_0_dry_plan_v1"
DEFAULT_BASE_DB = DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"
DEFAULT_EPISODE_DB = DATA_ROOT / "local_data/v8_copilot/valuation_episode_v1.sqlite3"
MAIN_HISTORY_START = "2021-03-17"
EXPLORATORY_START = "2016-08-09"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class P7DryPlan(StrictModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    plan_id: str = Field(pattern=r"^P7DP-[A-F0-9]{20}$")
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    generated_at: str
    as_of: str
    git_provenance: dict[str, Any]
    input_inventory: list[dict[str, Any]]
    source_boundaries: dict[str, Any]
    provider_permission_matrix: dict[str, Any]
    field_coverage: dict[str, Any]
    request_budget: dict[str, Any]
    eligibility_summary: dict[str, Any]
    exclusion_summary: dict[str, Any]
    trigger_budget_by_profile: dict[str, Any]
    activity_episode_budget: dict[str, Any]
    announcement_inventory: dict[str, Any]
    hard_node_candidate_inventory: dict[str, Any]
    terminal_phase_inventory: dict[str, Any]
    exchange_reference_status: dict[str, Any]
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
        "source_id": source_id, "path": str(path), "available": True,
        "size_bytes": path.stat().st_size,
        "digest": _file_sha256(path), "digest_kind": "sha256_file",
    }


def _scalar(connection: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> Any:
    row = connection.execute(query, params).fetchone()
    return row[0] if row else None


def _quantile(values: list[int], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _daily_budget(dates: list[str], hits: list[str]) -> dict[str, Any]:
    counts = Counter(hits)
    values = [counts.get(day, 0) for day in dates]
    buckets = Counter(
        "0" if value == 0 else "1-5" if value <= 5 else "6-10" if value <= 10
        else "11-20" if value <= 20 else "21-30" if value <= 30 else ">30"
        for value in values
    )
    return {
        "hit_count": len(hits), "trade_date_count": len(dates),
        "daily_mean": round(statistics.mean(values), 4) if values else 0.0,
        "daily_median": statistics.median(values) if values else 0.0,
        "daily_p90": round(_quantile(values, 0.90), 4),
        "daily_p95": round(_quantile(values, 0.95), 4),
        "daily_max": max(values, default=0),
        "day_bucket_ratio": {
            key: round(buckets.get(key, 0) / len(values), 8) if values else 0.0
            for key in ("0", "1-5", "6-10", "11-20", "21-30", ">30")
        },
    }


def _git_provenance(repo: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=repo, check=True, capture_output=True, text=True,
        ).stdout.strip()
    commit = run("rev-parse", "HEAD")
    baseline_ok = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "130ca0d", commit], cwd=repo,
        check=False, capture_output=True,
    ).returncode == 0
    return {"commit": commit, "branch": run("branch", "--show-current"), "contains_130ca0d": baseline_ok}


def build_p7_dry_plan(
    *, base_database: Path, market_context_database: Path,
    market_factor_database: Path, valuation_episode_database: Path,
    announcement_refresh_directory: Path, market_activity_database: Path,
    as_of: str, repo: Path,
    provider_probe: dict[str, Any] | None = None,
) -> P7DryPlan:
    through = date.fromisoformat(as_of).isoformat()
    git = _git_provenance(repo)
    if not git["contains_130ca0d"]:
        raise ValueError("wrong_baseline: current branch does not contain 130ca0d")
    inputs = [
        _source(base_database, "base_database"),
        _source(market_context_database, "market_context_v1"),
        _source(market_factor_database, "market_factors_v1"),
        _source(valuation_episode_database, "valuation_episode_v1"),
    ]
    if market_activity_database.is_file():
        inputs.append(_source(market_activity_database, "market_activity_v1"))

    with _connect_ro(base_database) as base:
        price = dict(base.execute(
            "select count(*) rows,count(distinct symbol) symbols,min(trade_date) min_date,"
            "max(trade_date) max_date,sum(amplitude is not null) amplitude_rows,"
            "sum(turnover_rate is not null) turnover_rows from daily_prices"
        ).fetchone())
        price["amplitude_rate"] = round(price["amplitude_rows"] / price["rows"], 8) if price["rows"] else 0
        price["turnover_rate"] = round(price["turnover_rows"] / price["rows"], 8) if price["rows"] else 0
        by_year = [dict(row) for row in base.execute(
            "select substr(trade_date,1,4) year,count(*) rows,"
            "sum(amplitude is not null) amplitude_rows,sum(turnover_rate is not null) turnover_rows "
            "from daily_prices group by substr(trade_date,1,4) order by year"
        )]
        announcement_rows = base.execute(
            "select announcement_id,symbol,announcement_date,title,coalesce(announcement_type,'') announcement_type,"
            "case when body_text is not null and length(trim(body_text))>0 then 1 else 0 end body_available "
            "from company_announcements where announcement_date<=?",
            (through,),
        )
        category_counts: Counter[str] = Counter()
        daily_announcement_counts: Counter[str] = Counter()
        bundle_keys: set[tuple[str, str, str, str]] = set()
        hard_counts: Counter[str] = Counter()
        progress_false_positive = 0
        body_count = 0
        announcement_count = 0
        announcement_symbols: set[str] = set()
        for row in announcement_rows:
            announcement_count += 1
            announcement_symbols.add(str(row["symbol"]))
            body_count += int(row["body_available"])
            category, _basis = classify_announcement(str(row["title"]), str(row["announcement_type"]))
            category_counts[category] += 1
            day = str(row["announcement_date"])
            daily_announcement_counts[day] += 1
            topic = str(row["title"]).replace("进展公告", "").replace("公告", "")[:32]
            bundle_keys.add((str(row["symbol"]), day, category, topic))
            hard, _dimension, _state = classify_hard_event(str(row["title"]))
            if hard:
                hard_counts[hard] += 1
            if "进展" in str(row["title"]) and hard:
                progress_false_positive += 1
        terminal = {
            "delisted_status_rows": _scalar(base, "select count(*) from st_status_history where status_type='delisted'"),
            "delisted_symbols": _scalar(base, "select count(distinct symbol) from st_status_history where status_type='delisted'"),
            "trading_status_rows": _scalar(base, "select count(*) from trading_status_daily"),
            "explicit_suspension_rows": _scalar(base, "select count(*) from trading_status_daily where is_suspended=1"),
            "explicit_one_price_rows": _scalar(base, "select count(*) from trading_status_daily where is_one_word_limit=1"),
            "verified_delisting_period_boundaries": 0,
            "boundary_status": "unknown_requires_fail_closed",
        }

    with _connect_ro(market_context_database) as context:
        membership = dict(context.execute(
            "select count(*) rows,count(distinct symbol) symbols,count(distinct trade_date) dates,"
            "min(trade_date) min_date,max(trade_date) max_date from st_membership_daily where trade_date<=?",
            (through,),
        ).fetchone())
        trade_dates = [str(row[0]) for row in context.execute(
            "select distinct m.trade_date from st_membership_daily m "
            "where m.trade_date between ? and ? and exists ("
            "select 1 from benchmark_daily b where b.benchmark_id='csi_all_share' "
            "and b.trade_date=m.trade_date) order by m.trade_date",
            (MAIN_HISTORY_START, through),
        )]
        latest_dates = trade_dates[-121:] if trade_dates else []
        benchmark_bounds = {
            str(row[0]): {"min_date": str(row[1]), "max_date": str(row[2]), "rows": int(row[3])}
            for row in context.execute(
                "select benchmark_id,min(trade_date),max(trade_date),count(*) from benchmark_daily group by benchmark_id"
            )
        }
    with _connect_ro(market_factor_database) as factors:
        c14 = dict(factors.execute(
            "select count(*) snapshots,count(distinct trade_date) dates,min(trade_date) min_date,max(trade_date) max_date "
            "from market_factor_snapshots"
        ).fetchone())
        c14["symbol_days"] = _scalar(factors, "select count(*) from market_cap_daily")
        c14["semantic_boundary"] = "valuation anchors only; not continuous P7 activity"
    with _connect_ro(valuation_episode_database) as episodes:
        episode_counts = {
            str(row[0]): int(row[1])
            for row in episodes.execute("select evidence_status,count(*) from valuation_episodes group by evidence_status")
        }
        stage_counts: Counter[str] = Counter()
        for row in episodes.execute("select payload_json from valuation_episodes"):
            payload = json.loads(row[0])
            stage_counts[str(payload.get("current_stage") or "unknown")] += 1

    activity_facts = MarketActivityRepository(market_activity_database).latest_facts(
        start_date=MAIN_HISTORY_START, through=through,
    ) if market_activity_database.is_file() else []
    if activity_facts:
        anomaly_run = build_anomaly_run(activity_facts)
        activity_dates = sorted({item.trade_date for item in anomaly_run.anomalies})
        trigger_budget = {}
        for profile in ("broad", "balanced", "strict"):
            hits = [item for item in anomaly_run.anomalies if bool(getattr(item, profile))]
            symbol_counts = Counter(item.symbol for item in hits)
            top_ten = symbol_counts.most_common(10)
            trigger_budget[profile] = {
                **_daily_budget(activity_dates, [item.trade_date for item in hits]),
                "by_year": dict(Counter(item.trade_date[:4] for item in hits)),
                "top_10_symbols": dict(top_ten),
                "top_10_hit_share": round(sum(count for _symbol, count in top_ten) / len(hits), 8) if hits else 0.0,
                "max_single_symbol_hits": max(symbol_counts.values(), default=0),
                "stage_stratification": "reported in P7D after verified point-in-time stage join",
                "market_context_stratification": "reported in P7D; thresholds were not selected from outcomes",
            }
        episode_budget = {}
        for profile in ("broad", "balanced", "strict"):
            for gap in (3, 5, 10):
                selected_episodes = [item for item in anomaly_run.episodes if item.profile == profile and item.merge_gap == gap]
                episode_budget[f"{profile}_{gap}"] = {
                    "episode_count": len(selected_episodes),
                    "company_count": len({item.symbol for item in selected_episodes}),
                    "median_hit_count": statistics.median([item.hit_count for item in selected_episodes]) if selected_episodes else 0,
                    "max_hit_count": max((item.hit_count for item in selected_episodes), default=0),
                    "median_peak_robust_z": round(statistics.median([item.peak_robust_z for item in selected_episodes]), 4) if selected_episodes else 0.0,
                }
        snapshots = MarketActivityRepository(market_activity_database).snapshots(
            start_date=MAIN_HISTORY_START, through=through,
        )
        valid_snapshots = [item for item in snapshots if item.daily_row_count and item.daily_basic_row_count and item.limit_row_count]
        coverages = [item.coverage_ratio for item in valid_snapshots]
        eligibility = {
            "activity_symbol_days": len(activity_facts),
            "calculable_symbol_days": anomaly_run.calculable_count,
            "calculable_rate": round(anomaly_run.calculable_count / len(activity_facts), 8),
            "date_count": len(activity_dates),
            "daily_activity_coverage": {
                "mean": round(statistics.mean(coverages), 8) if coverages else 0.0,
                "median": round(statistics.median(coverages), 8) if coverages else 0.0,
                "p10": round(_quantile([round(value * 1_000_000) for value in coverages], 0.10) / 1_000_000, 8) if coverages else 0.0,
                "worst": min(coverages, default=0.0),
                "gate_pass_ratio": {
                    str(gate): round(sum(value >= gate for value in coverages) / len(coverages), 8) if coverages else 0.0
                    for gate in (0.90, 0.95, 0.98)
                },
            },
            "zero_mad_breakout_count": anomaly_run.zero_mad_breakout_count,
            "post_suspension_recovery_count": sum(item.post_suspension for item in anomaly_run.anomalies),
            "post_suspension_public_guard": "exclude_current_and_baseline_for_5_symbol_observations",
        }
        exclusions = Counter(reason for item in anomaly_run.anomalies for reason in item.exclusion_reasons)
        field_coverage = {
            "market_activity_status": "available",
            "turnover_rate_f": round(sum(item.turnover_rate_f is not None for item in activity_facts) / len(activity_facts), 8),
            "amplitude_pct": round(sum(item.amplitude_pct is not None for item in activity_facts) / len(activity_facts), 8),
            "suspension_known": round(sum(item.suspension_status != "unknown" for item in activity_facts) / len(activity_facts), 8),
            "limit_known": round(sum(item.one_price_limit is not None for item in activity_facts) / len(activity_facts), 8),
        }
        hard_blockers: list[str] = []
    else:
        trigger_budget = {profile: {"status": "unavailable_missing_turnover_rate_f_history"} for profile in ("broad", "balanced", "strict")}
        episode_budget = {"status": "unavailable_until_minimal_bootstrap"}
        eligibility = {"activity_symbol_days": 0, "calculable_symbol_days": 0, "date_count": 0}
        exclusions = Counter({"market_activity_not_bootstrapped": int(membership.get("rows") or 0)})
        field_coverage = {
            "market_activity_status": "not_bootstrapped",
            "legacy_daily_prices": price,
            "legacy_by_year": by_year,
        }
        hard_blockers = ["market_activity_v1 尚无 turnover_rate_f 历史，不能计算 frozen profiles"]

    probe_matrix = (provider_probe or {}).get("provider_permission_matrix", {})
    if provider_probe:
        required_ready = all(
            probe_matrix.get(name, {}).get("status") in {"success", "empty_valid"}
            for name in ("daily", "daily_basic", "suspend_d", "stk_limit")
        )
        if not required_ready:
            hard_blockers.append("当前账号的 P7B 必需 provider 接口未全部通过")
        hard_blockers.extend(
            f"P7B publication only: {item}; shadow 使用 raw OHLC + stk_limit 双源 fail-closed"
            for item in provider_probe.get("hard_blockers", [])
        )
    else:
        hard_blockers.append("P7-0b provider probe 尚未关联")
    request_budget = {
        "request_basis": "one full-market request per trade date per required endpoint",
        "latest_120_bootstrap_trade_dates": len(latest_dates),
        "latest_120_required_calls": len(latest_dates) * 4,
        "main_history_trade_dates": len(trade_dates),
        "main_history_required_calls": len(trade_dates) * 4,
        "daily_increment_calls": 4,
        "exploratory_history": "pending provider coverage; not authorized by default",
    }
    announcements = {
        "status": "candidate_only", "announcement_count": announcement_count,
        "symbol_count": len(announcement_symbols), "body_available_count": body_count,
        "body_coverage": round(body_count / announcement_count, 8) if announcement_count else 0.0,
        "category_candidate_counts": dict(category_counts),
        "daily_mean": round(statistics.mean(daily_announcement_counts.values()), 4) if daily_announcement_counts else 0.0,
        "daily_max": max(daily_announcement_counts.values(), default=0),
        "bundle_count_before": announcement_count,
        "bundle_count_after_candidate_compression": len(bundle_keys),
    }
    hard_inventory = {
        "status": "candidate_only", "candidate_counts": dict(hard_counts),
        "progress_title_hard_false_positive_count": progress_false_positive,
        "valuation_episode_evidence_status_counts": episode_counts,
        "valuation_episode_current_stage_counts": dict(stage_counts),
    }
    source_boundaries = {
        "price": {"checked_through": price["max_date"]},
        "membership": membership,
        "benchmarks": benchmark_bounds,
        "c14": c14,
        "announcements": {"checked_through": max(daily_announcement_counts, default="")},
        "main_history_start": MAIN_HISTORY_START,
        "exploratory_history_start": EXPLORATORY_START,
    }
    non_blocking = [
        "交易所 stk_shock/stk_high_shock/stk_alert 无权限时仅使新颖性对照 unavailable",
        "退市整理期尚无完整 verified 起止边界；公开异常按 unknown fail closed",
        "公告正文覆盖不全；确定性标题无法判定时保持 unknown，不转成人工逐条流水线",
    ]
    safe_defaults = [
        "balanced=97.5% 分位且 robust z>=4，仅 shadow",
        "主历史从 2021-03-17 开始，先做最新 universe 最小 bootstrap",
        "5 个合格交易日合并 activity episode；3/10 日仅做工作量旁证",
        "低于 95% 活动覆盖不称全体 ST 异常榜",
        "P7A 可独立 descriptive；P7B/P7C 保持 shadow",
    ]
    identity = {
        "contract_version": CONTRACT_VERSION, "as_of": through, "git": git,
        "inputs": inputs, "source_boundaries": source_boundaries,
        "provider_permission_matrix": probe_matrix, "field_coverage": field_coverage,
        "request_budget": request_budget, "eligibility": eligibility,
        "exclusions": dict(exclusions), "trigger_budget": trigger_budget,
        "episode_budget": episode_budget, "announcements": announcements,
        "hard_inventory": hard_inventory, "terminal": terminal,
        "hard_blockers": sorted(set(hard_blockers)), "non_blocking": non_blocking,
        "safe_defaults": safe_defaults,
    }
    digest = _digest(identity)
    return P7DryPlan(
        plan_id=f"P7DP-{digest[:20].upper()}", content_digest=digest,
        generated_at=datetime.now(timezone.utc).isoformat(), as_of=through,
        git_provenance=git, input_inventory=inputs,
        source_boundaries=source_boundaries,
        provider_permission_matrix=probe_matrix,
        field_coverage=field_coverage, request_budget=request_budget,
        eligibility_summary=eligibility, exclusion_summary=dict(exclusions),
        trigger_budget_by_profile=trigger_budget,
        activity_episode_budget=episode_budget,
        announcement_inventory=announcements,
        hard_node_candidate_inventory=hard_inventory,
        terminal_phase_inventory=terminal,
        exchange_reference_status={
            name: probe_matrix.get(name, {"status": "not_probed"})
            for name in ("stk_shock", "stk_high_shock", "stk_alert")
        },
        hard_blockers=sorted(set(hard_blockers)), non_blocking_gaps=non_blocking,
        safe_defaults=safe_defaults,
        recommended_next_step=(
            "P7A 可进入 descriptive；P7B/P7C 仅进入 shadow，保留发布阻塞"
            if hard_blockers else "进入 P7A，并保持 P7B/P7C shadow"
        ),
        human_decisions_required=[],
    )


def render_markdown(plan: P7DryPlan) -> str:
    status = "可继续" if not plan.hard_blockers else "有前置缺口"
    lines = [
        "# P7-0 数据可行性与容量盘点", "",
        f"- 结论：**{status}**", f"- Plan：`{plan.plan_id}`", f"- 截止日：{plan.as_of}",
        f"- 人工决定：{len(plan.human_decisions_required)} 项", "",
        "## 一页结论", "",
        "P7A 的公告库存足以开工；P7B 是否可继续由 provider 探针和独立活动库覆盖决定。",
        "当前报告不会用普通换手率冒充自由流通换手率，也不会按回测结果选择阈值。", "",
        "### Hard blockers", "",
    ]
    lines.extend([f"- {item}" for item in plan.hard_blockers] or ["- 无"])
    lines.extend(["", "### Safe defaults", ""])
    lines.extend(f"- {item}" for item in plan.safe_defaults)
    lines.extend(["", "## 请求预算", "", "```json", json.dumps(plan.request_budget, ensure_ascii=False, indent=2), "```", ""])
    lines.extend(["## 字段与资格", "", "```json", json.dumps({"field_coverage": plan.field_coverage, "eligibility": plan.eligibility_summary, "exclusions": plan.exclusion_summary}, ensure_ascii=False, indent=2), "```", ""])
    lines.extend(["## 异常容量（只看工作量，不看后果）", "", "```json", json.dumps({"profiles": plan.trigger_budget_by_profile, "episodes": plan.activity_episode_budget}, ensure_ascii=False, indent=2), "```", ""])
    lines.extend(["## 公告库存", "", "```json", json.dumps({"announcements": plan.announcement_inventory, "hard_nodes": plan.hard_node_candidate_inventory}, ensure_ascii=False, indent=2), "```", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="P7-0a local read-only inventory")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--base-database", type=Path, default=DEFAULT_BASE_DB)
    parser.add_argument("--market-context-database", type=Path, default=MARKET_CONTEXT_DB)
    parser.add_argument("--market-factor-database", type=Path, default=MARKET_FACTOR_DB)
    parser.add_argument("--valuation-episode-database", type=Path, default=DEFAULT_EPISODE_DB)
    parser.add_argument("--announcement-refresh-directory", type=Path, default=ANNOUNCEMENT_REFRESH_DIR)
    parser.add_argument("--market-activity-database", type=Path, default=MARKET_ACTIVITY_DB)
    parser.add_argument("--provider-probe", type=Path)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args()
    probe = json.loads(args.provider_probe.read_text(encoding="utf-8")) if args.provider_probe else None
    plan = build_p7_dry_plan(
        base_database=args.base_database,
        market_context_database=args.market_context_database,
        market_factor_database=args.market_factor_database,
        valuation_episode_database=args.valuation_episode_database,
        announcement_refresh_directory=args.announcement_refresh_directory,
        market_activity_database=args.market_activity_database,
        as_of=args.as_of, repo=Path(__file__).resolve().parent,
        provider_probe=probe,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    args.output_markdown.write_text(render_markdown(plan), encoding="utf-8")
    print(json.dumps({"plan_id": plan.plan_id, "json": str(args.output_json), "markdown": str(args.output_markdown), "hard_blockers": plan.hard_blockers}, ensure_ascii=False, indent=2))
    return 2 if plan.hard_blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
