"""Read-only feasibility plan for P6B valuation episodes and market factors."""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from settings import DATA_ROOT, MARKET_CONTEXT_DB, MARKET_FACTOR_DB


CONTRACT_VERSION = "v8_p6b_dry_plan_v1"
STALE_WINDOWS = (0, 5, 20)
MARKET_CAP_COVERAGE_GATE = 0.95
MIN_MARKET_CAP_COHORT = 20
DEFAULT_BASE_DATABASE = (
    DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"
)
DEFAULT_EPISODE_INDEX = (
    DATA_ROOT / "shared_data/v7/episode_index_v0/episode_index.jsonl"
)
DEFAULT_EPISODE_MANIFEST = (
    DATA_ROOT / "shared_data/v7/episode_index_v0/builder_run_manifest.json"
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceInventory(StrictModel):
    source_id: str
    row_count: int = Field(ge=0)
    symbol_count: int = Field(ge=0)
    min_date: str = ""
    max_date: str = ""
    notes: list[str] = Field(default_factory=list)


class ValuationEpisodeCandidate(StrictModel):
    episode_id: str
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    start_date: str
    end_date: str
    membership_trade_days: int = Field(ge=1)
    is_open: bool
    repricing_anchor_date: str = ""
    start_price_lag_trading_days: int | None = Field(default=None, ge=0)
    boundary_gap_adjacent: bool
    m6_restructuring_candidate_count: int = Field(ge=0)


class EpisodeSummary(StrictModel):
    episode_count: int = Field(ge=0)
    symbol_count: int = Field(ge=0)
    repeated_symbol_count: int = Field(ge=0)
    open_episode_count: int = Field(ge=0)
    min_start_date: str = ""
    max_end_date: str = ""
    membership_calendar_gap_count: int = Field(ge=0)
    gap_adjacent_episode_count: int = Field(ge=0)
    unique_market_cap_anchor_dates: int = Field(ge=0)
    exact_start_price_count: int = Field(ge=0)
    within_5_start_price_count: int = Field(ge=0)
    within_20_start_price_count: int = Field(ge=0)
    m6_restructuring_candidate_episode_count: int = Field(ge=0)


class StaleCoverageYear(StrictModel):
    year: str = Field(pattern=r"^[0-9]{4}$")
    trade_date_count: int = Field(ge=0)
    member_observations: int = Field(ge=0)
    exact_price_coverage: float = Field(ge=0, le=1)
    within_5_price_coverage: float = Field(ge=0, le=1)
    within_20_price_coverage: float = Field(ge=0, le=1)
    exact_gate_pass_dates: int = Field(ge=0)
    within_5_gate_pass_dates: int = Field(ge=0)
    within_20_gate_pass_dates: int = Field(ge=0)
    first_within_5_gate_date: str = ""
    last_within_5_gate_date: str = ""


class MarketCapRequestPlan(StrictModel):
    request_basis: Literal["one_full_market_daily_basic_call_per_trade_date"] = (
        "one_full_market_daily_basic_call_per_trade_date"
    )
    unique_trade_date_count: int = Field(ge=0)
    min_trade_date: str = ""
    max_trade_date: str = ""
    trade_dates_by_year: dict[str, int]
    benchmark_date_ranges: dict[str, str]
    probe_trade_dates: list[str]


class StatusHistoryAudit(StrictModel):
    row_count: int = Field(ge=0)
    symbol_count: int = Field(ge=0)
    open_row_count: int = Field(ge=0)
    evidence_status_counts: dict[str, int]
    recommended_episode_source: Literal["market_context.st_membership_daily"] = (
        "market_context.st_membership_daily"
    )
    status_history_usable_as_primary_episode_source: Literal[False] = False
    reason: str


class M6CandidateSummary(StrictModel):
    total_episode_records: int = Field(ge=0)
    restructuring_records: int = Field(ge=0)
    restructuring_symbols: int = Field(ge=0)
    capital_structure_records: int = Field(ge=0)
    delisting_terminal_records: int = Field(ge=0)
    exact_adjuster_records: int = Field(ge=0)
    evidence_status_counts: dict[str, int]


class CapitalAndTerminalAudit(StrictModel):
    market_factor_snapshot_count: int = Field(ge=0)
    market_factor_min_date: str = ""
    market_factor_max_date: str = ""
    historical_share_change_guard_available: bool
    trading_status_rows: int = Field(ge=0)
    trading_status_symbols: int = Field(ge=0)
    explicit_suspension_rows: int = Field(ge=0)
    delisted_status_symbols: int = Field(ge=0)
    delisted_symbols_with_any_qfq: int = Field(ge=0)
    notes: list[str] = Field(default_factory=list)


class HumanDecision(StrictModel):
    decision_id: str
    decision: str
    recommendation: str
    evidence: str


class P6BDryPlan(StrictModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    plan_id: str = Field(pattern=r"^P6B0-[A-F0-9]{20}$")
    generated_at: str
    as_of: str
    source_inventory: list[SourceInventory]
    episode_summary: EpisodeSummary
    episodes: list[ValuationEpisodeCandidate]
    stale_coverage_by_year: list[StaleCoverageYear]
    market_cap_requests: MarketCapRequestPlan
    status_history_audit: StatusHistoryAudit
    m6_candidates: M6CandidateSummary
    capital_and_terminal_audit: CapitalAndTerminalAudit
    human_decisions: list[HumanDecision]
    next_phase_blockers: list[str]
    warnings: list[str]


def _connect_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _iso_date(value: str, *, field: str) -> str:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是 YYYY-MM-DD: {value!r}") from exc


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 8) if denominator else 0.0


def _load_prices(
    database: Path, *, through: str
) -> tuple[dict[str, list[str]], SourceInventory]:
    with _connect_read_only(database) as connection:
        rows = connection.execute(
            "select symbol,trade_date from daily_prices "
            "where adjust='qfq' and trade_date<=? order by symbol,trade_date",
            (through,),
        ).fetchall()
    by_symbol: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        by_symbol[str(row["symbol"])].append(str(row["trade_date"])[:10])
    all_dates = [day for dates in by_symbol.values() for day in dates]
    return dict(by_symbol), SourceInventory(
        source_id="base.daily_prices.qfq",
        row_count=len(rows),
        symbol_count=len(by_symbol),
        min_date=min(all_dates, default=""),
        max_date=max(all_dates, default=""),
    )


def _load_membership(
    market_database: Path, *, through: str
) -> tuple[
    list[tuple[str, str]],
    list[str],
    list[str],
    SourceInventory,
    dict[str, tuple[str, str]],
]:
    with _connect_read_only(market_database) as connection:
        rows = connection.execute(
            "select trade_date,symbol from st_membership_daily "
            "where trade_date<=? order by trade_date,symbol",
            (through,),
        ).fetchall()
        benchmarks = connection.execute(
            "select benchmark_id,min(trade_date) min_date,max(trade_date) max_date "
            "from benchmark_daily where trade_date<=? group by benchmark_id",
            (through,),
        ).fetchall()
        all_share_dates = connection.execute(
            "select trade_date from benchmark_daily "
            "where benchmark_id='csi_all_share' and trade_date<=? "
            "order by trade_date",
            (through,),
        ).fetchall()
    membership = [
        (str(row["trade_date"])[:10], str(row["symbol"])) for row in rows
    ]
    dates = sorted({day for day, _ in membership})
    symbols = {symbol for _, symbol in membership}
    trading_calendar = [
        str(row["trade_date"])[:10] for row in all_share_dates
        if not dates or str(row["trade_date"])[:10] >= dates[0]
    ]
    if not trading_calendar:
        trading_calendar = dates.copy()
    calendar_gaps = sorted(set(trading_calendar) - set(dates))
    benchmark_ranges = {
        str(row["benchmark_id"]): (
            str(row["min_date"] or "")[:10], str(row["max_date"] or "")[:10]
        )
        for row in benchmarks
    }
    return membership, dates, trading_calendar, SourceInventory(
        source_id="market_context.st_membership_daily",
        row_count=len(membership),
        symbol_count=len(symbols),
        min_date=min(dates, default=""),
        max_date=max(dates, default=""),
        notes=[
            "连续 episode 以逐交易日 membership 观测序列构造。",
            f"相对中证全指交易日历缺 {len(calendar_gaps)} 个 membership 日期；"
            "空洞不解释为成分退出。",
        ],
    ), benchmark_ranges


def _load_status_history(database: Path, *, through: str) -> StatusHistoryAudit:
    with _connect_read_only(database) as connection:
        row = connection.execute(
            "select count(*) rows,count(distinct symbol) symbols,"
            "sum(case when end_date is null then 1 else 0 end) open_rows "
            "from st_status_history where start_date<=?",
            (through,),
        ).fetchone()
        evidence = connection.execute(
            "select evidence_status,count(*) rows from st_status_history_evidence "
            "where start_date<=? group by evidence_status",
            (through,),
        ).fetchall()
    return StatusHistoryAudit(
        row_count=int(row["rows"] or 0),
        symbol_count=int(row["symbols"] or 0),
        open_row_count=int(row["open_rows"] or 0),
        evidence_status_counts={
            str(item["evidence_status"]): int(item["rows"]) for item in evidence
        },
        reason=(
            "稀疏状态事件包含重叠和无结束日期记录；用于来源交叉核查，"
            "不能替代逐日 membership 切分连续 episode。"
        ),
    )


def _jsonl_records(path: Path, *, through: str) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    records: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"M6 JSONL 非法: {path}:{line_number}: {exc}") from exc
        window = record.get("window") or {}
        start = str(window.get("start_date") or "")
        anchors = record.get("anchor_events") or []
        anchor_dates = [
            str(item.get("anchor_date") or "")[:10]
            for item in anchors if item.get("anchor_date")
        ]
        if not start and anchor_dates:
            start = min(anchor_dates)
        if start and start[:10] <= through:
            records.append(record)
    return records


def _record_window(record: dict[str, Any]) -> tuple[str, str]:
    window = record.get("window") or {}
    anchors = record.get("anchor_events") or []
    anchor_dates = sorted(
        str(item.get("anchor_date") or "")[:10]
        for item in anchors
        if item.get("anchor_date")
    )
    start = str(window.get("start_date") or "")[:10]
    end = str(window.get("end_date") or "")[:10]
    return start or (anchor_dates[0] if anchor_dates else ""), end or (
        anchor_dates[-1] if anchor_dates else start
    )


def _load_m6(
    index_path: Path, manifest_path: Path, *, through: str
) -> tuple[
    list[dict[str, Any]], M6CandidateSummary, SourceInventory, list[str]
]:
    records = _jsonl_records(index_path, through=through)
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_type = Counter(str(record.get("episode_type") or "unknown") for record in records)
    evidence = Counter(
        str(record.get("evidence_status") or "unknown") for record in records
    )
    restructuring = [
        record for record in records
        if record.get("episode_type") == "restructuring_path"
    ]
    date_values = [
        value
        for record in records
        for value in _record_window(record)
        if value
    ]
    exact_adjusters = int(
        ((manifest.get("c09_discipline") or {}).get(
            "records_with_exact_adjuster_fields"
        ) or 0)
    )
    capital_dates = [
        _record_window(record)[0]
        for record in records
        if record.get("episode_type") == "capital_structure_adjustment_path"
        and _record_window(record)[0]
    ]
    return restructuring, M6CandidateSummary(
        total_episode_records=len(records),
        restructuring_records=len(restructuring),
        restructuring_symbols=len({
            str(record.get("symbol") or "") for record in restructuring
        }),
        capital_structure_records=by_type["capital_structure_adjustment_path"],
        delisting_terminal_records=by_type["delisting_terminal_path"],
        exact_adjuster_records=exact_adjusters,
        evidence_status_counts=dict(sorted(evidence.items())),
    ), SourceInventory(
        source_id="m6.episode_index",
        row_count=len(records),
        symbol_count=len({
            str(record.get("symbol") or "") for record in records
        }),
        min_date=min(date_values, default=""),
        max_date=max(date_values, default=""),
        notes=["case_note_only 只生成候选，不直接晋级 valuation episode。"],
    ), sorted(set(capital_dates))


def _calendar_lag(calendar: list[str], target: str, observed: str) -> int | None:
    target_index = bisect.bisect_left(calendar, target)
    if target_index >= len(calendar) or calendar[target_index] != target:
        return None
    observed_index = bisect.bisect_right(calendar, observed) - 1
    if observed_index < 0:
        return None
    return target_index - observed_index


def _last_price(
    price_dates: list[str], *, target: str, strict_before: bool
) -> str:
    index = (
        bisect.bisect_left(price_dates, target)
        if strict_before else bisect.bisect_right(price_dates, target)
    ) - 1
    return price_dates[index] if index >= 0 else ""


def _candidate_episodes(
    membership: list[tuple[str, str]],
    membership_dates: list[str],
    trading_calendar: list[str],
    prices: dict[str, list[str]],
    restructuring_records: list[dict[str, Any]],
) -> list[ValuationEpisodeCandidate]:
    date_index = {day: index for index, day in enumerate(membership_dates)}
    symbol_dates: dict[str, list[str]] = defaultdict(list)
    for day, symbol in membership:
        symbol_dates[symbol].append(day)
    restructuring_by_symbol: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for record in restructuring_records:
        start, end = _record_window(record)
        if start:
            restructuring_by_symbol[str(record.get("symbol") or "")].append(
                (start, end or start)
            )
    final_date = membership_dates[-1]
    membership_date_set = set(membership_dates)
    trading_index = {day: index for index, day in enumerate(trading_calendar)}
    candidates: list[ValuationEpisodeCandidate] = []
    for symbol in sorted(symbol_dates):
        dates = symbol_dates[symbol]
        groups: list[list[str]] = []
        current: list[str] = []
        previous_index: int | None = None
        for day in dates:
            index = date_index[day]
            if previous_index is None or index == previous_index + 1:
                current.append(day)
            else:
                groups.append(current)
                current = [day]
            previous_index = index
        if current:
            groups.append(current)
        for group in groups:
            start, end = group[0], group[-1]
            price_dates = prices.get(symbol, [])
            repricing_anchor = _last_price(
                price_dates, target=start, strict_before=True
            )
            latest_at_start = _last_price(
                price_dates, target=start, strict_before=False
            )
            lag = (
                _calendar_lag(trading_calendar, start, latest_at_start)
                if latest_at_start else None
            )
            start_index = trading_index.get(start)
            end_index = trading_index.get(end)
            boundary_gap_adjacent = bool(
                start_index is not None
                and start_index > 0
                and trading_calendar[start_index - 1] not in membership_date_set
            ) or bool(
                end_index is not None
                and end_index + 1 < len(trading_calendar)
                and trading_calendar[end_index + 1] not in membership_date_set
            )
            m6_count = sum(
                1 for item_start, item_end in restructuring_by_symbol.get(symbol, [])
                if item_start <= end and item_end >= start
            )
            candidates.append(ValuationEpisodeCandidate(
                episode_id=f"VE-CAND-{symbol}-{start}",
                symbol=symbol,
                start_date=start,
                end_date=end,
                membership_trade_days=len(group),
                is_open=end == final_date,
                repricing_anchor_date=repricing_anchor,
                start_price_lag_trading_days=lag,
                boundary_gap_adjacent=boundary_gap_adjacent,
                m6_restructuring_candidate_count=m6_count,
            ))
    return candidates


def _stale_coverage(
    membership: list[tuple[str, str]],
    trading_calendar: list[str],
    prices: dict[str, list[str]],
) -> list[StaleCoverageYear]:
    yearly: dict[str, Counter[str]] = defaultdict(Counter)
    per_date: dict[str, Counter[str]] = defaultdict(Counter)
    for day, symbol in membership:
        year = day[:4]
        price_dates = prices.get(symbol, [])
        observed = _last_price(price_dates, target=day, strict_before=False)
        lag = _calendar_lag(trading_calendar, day, observed) if observed else None
        yearly[year]["observations"] += 1
        per_date[day]["observations"] += 1
        for window in STALE_WINDOWS:
            if lag is not None and lag <= window:
                yearly[year][f"within_{window}"] += 1
                per_date[day][f"within_{window}"] += 1
    results: list[StaleCoverageYear] = []
    for year in sorted(yearly):
        dates = sorted(day for day in per_date if day.startswith(year))
        passing_dates = {
            window: [
                day for day in dates
                if per_date[day]["observations"] >= MIN_MARKET_CAP_COHORT
                and _ratio(
                    per_date[day][f"within_{window}"],
                    per_date[day]["observations"],
                ) >= MARKET_CAP_COVERAGE_GATE
            ]
            for window in STALE_WINDOWS
        }
        observations = yearly[year]["observations"]
        results.append(StaleCoverageYear(
            year=year,
            trade_date_count=len(dates),
            member_observations=observations,
            exact_price_coverage=_ratio(yearly[year]["within_0"], observations),
            within_5_price_coverage=_ratio(yearly[year]["within_5"], observations),
            within_20_price_coverage=_ratio(yearly[year]["within_20"], observations),
            exact_gate_pass_dates=len(passing_dates[0]),
            within_5_gate_pass_dates=len(passing_dates[5]),
            within_20_gate_pass_dates=len(passing_dates[20]),
            first_within_5_gate_date=min(passing_dates[5], default=""),
            last_within_5_gate_date=max(passing_dates[5], default=""),
        ))
    return results


def _spread_sample(values: list[str], *, count: int = 3) -> list[str]:
    unique = sorted(set(values))
    if len(unique) <= count:
        return unique
    indices = {round(index * (len(unique) - 1) / (count - 1)) for index in range(count)}
    return [unique[index] for index in sorted(indices)]


def _probe_dates(
    anchor_dates: list[str],
    capital_dates: list[str],
    trading_calendar: list[str],
) -> list[str]:
    era_bounds = (
        ("2016-01-01", "2021-03-16"),
        ("2021-03-17", "2023-08-10"),
        ("2023-08-11", "9999-12-31"),
    )
    sampled: set[str] = set()
    for start, end in era_bounds:
        sampled.update(_spread_sample([
            day for day in anchor_dates if start <= day <= end
        ]))
    if anchor_dates:
        capital_trade_dates: list[str] = []
        for day in capital_dates:
            index = bisect.bisect_left(trading_calendar, day)
            if index < len(trading_calendar):
                trade_date = trading_calendar[index]
                if anchor_dates[0] <= trade_date <= anchor_dates[-1]:
                    capital_trade_dates.append(trade_date)
        sampled.update(_spread_sample(capital_trade_dates))
    return sorted(sampled)


def _capital_and_terminal_audit(
    base_database: Path,
    market_factor_database: Path,
    *,
    through: str,
    m6: M6CandidateSummary,
) -> tuple[CapitalAndTerminalAudit, SourceInventory]:
    with _connect_read_only(market_factor_database) as connection:
        factor = connection.execute(
            "select count(*) rows,min(trade_date) min_date,max(trade_date) max_date "
            "from market_factor_snapshots where trade_date<=?",
            (through,),
        ).fetchone()
    with _connect_read_only(base_database) as connection:
        trading = connection.execute(
            "select count(*) rows,count(distinct symbol) symbols,"
            "sum(case when is_suspended=1 then 1 else 0 end) suspended "
            "from trading_status_daily where trade_date<=?",
            (through,),
        ).fetchone()
        terminal = connection.execute(
            "select count(distinct symbol) symbols from st_status_history "
            "where status_type='delisted' and start_date<=?",
            (through,),
        ).fetchone()
        terminal_prices = connection.execute(
            "select count(distinct h.symbol) symbols "
            "from st_status_history h where h.status_type='delisted' "
            "and h.start_date<=? and exists ("
            "select 1 from daily_prices p where p.symbol=h.symbol and p.adjust='qfq')",
            (through,),
        ).fetchone()
    snapshot_count = int(factor["rows"] or 0)
    audit = CapitalAndTerminalAudit(
        market_factor_snapshot_count=snapshot_count,
        market_factor_min_date=str(factor["min_date"] or "")[:10],
        market_factor_max_date=str(factor["max_date"] or "")[:10],
        historical_share_change_guard_available=(
            snapshot_count > 1
            and str(factor["min_date"] or "") != str(factor["max_date"] or "")
            and m6.exact_adjuster_records > 0
        ),
        trading_status_rows=int(trading["rows"] or 0),
        trading_status_symbols=int(trading["symbols"] or 0),
        explicit_suspension_rows=int(trading["suspended"] or 0),
        delisted_status_symbols=int(terminal["symbols"] or 0),
        delisted_symbols_with_any_qfq=int(terminal_prices["symbols"] or 0),
        notes=[
            "价格陈旧覆盖只是本地可用性代理；历史股本变化 guard 尚未满足。",
            "trading_status_daily 没有显式停牌行时，不能据此声称历史无停牌。",
        ],
    )
    return audit, SourceInventory(
        source_id="market_factors.market_factor_snapshots",
        row_count=snapshot_count,
        symbol_count=0,
        min_date=audit.market_factor_min_date,
        max_date=audit.market_factor_max_date,
        notes=["P6B 历史 market-cap 锚点尚未回填。"],
    )


def _plan_identifier(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return "P6B0-" + hashlib.sha256(canonical.encode()).hexdigest()[:20].upper()


def build_p6b_dry_plan(
    *,
    base_database: Path,
    market_context_database: Path,
    market_factor_database: Path,
    episode_index: Path,
    episode_manifest: Path,
    as_of: str = "",
) -> P6BDryPlan:
    requested_as_of = _iso_date(as_of, field="as_of") if as_of else ""
    membership, membership_dates, trading_calendar, membership_source, benchmark_ranges = (
        _load_membership(
            market_context_database,
            through=requested_as_of or "9999-12-31",
        )
    )
    if not membership_dates:
        raise ValueError("st_membership_daily 在指定 as_of 前为空")
    effective_as_of = min(requested_as_of, membership_dates[-1]) if requested_as_of else (
        membership_dates[-1]
    )
    if effective_as_of != membership_dates[-1]:
        membership, membership_dates, trading_calendar, membership_source, benchmark_ranges = (
            _load_membership(market_context_database, through=effective_as_of)
        )
    prices, price_source = _load_prices(base_database, through=effective_as_of)
    status_audit = _load_status_history(base_database, through=effective_as_of)
    restructuring, m6_summary, m6_source, capital_dates = _load_m6(
        episode_index, episode_manifest, through=effective_as_of
    )
    episodes = _candidate_episodes(
        membership, membership_dates, trading_calendar, prices, restructuring
    )
    stale = _stale_coverage(membership, trading_calendar, prices)
    capital_audit, factor_source = _capital_and_terminal_audit(
        base_database, market_factor_database,
        through=effective_as_of, m6=m6_summary,
    )
    per_symbol = Counter(item.symbol for item in episodes)
    anchor_dates = sorted({item.start_date for item in episodes})
    request_plan = MarketCapRequestPlan(
        unique_trade_date_count=len(anchor_dates),
        min_trade_date=min(anchor_dates, default=""),
        max_trade_date=max(anchor_dates, default=""),
        trade_dates_by_year=dict(sorted(Counter(
            day[:4] for day in anchor_dates
        ).items())),
        benchmark_date_ranges={
            benchmark_id: f"{start or 'unavailable'}..{end or 'unavailable'}"
            for benchmark_id, (start, end) in sorted(benchmark_ranges.items())
        },
        probe_trade_dates=_probe_dates(
            anchor_dates, capital_dates, trading_calendar
        ),
    )
    summary = EpisodeSummary(
        episode_count=len(episodes),
        symbol_count=len(per_symbol),
        repeated_symbol_count=sum(1 for count in per_symbol.values() if count > 1),
        open_episode_count=sum(item.is_open for item in episodes),
        min_start_date=min((item.start_date for item in episodes), default=""),
        max_end_date=max((item.end_date for item in episodes), default=""),
        membership_calendar_gap_count=len(set(trading_calendar) - set(membership_dates)),
        gap_adjacent_episode_count=sum(item.boundary_gap_adjacent for item in episodes),
        unique_market_cap_anchor_dates=len(anchor_dates),
        exact_start_price_count=sum(
            item.start_price_lag_trading_days == 0 for item in episodes
        ),
        within_5_start_price_count=sum(
            item.start_price_lag_trading_days is not None
            and item.start_price_lag_trading_days <= 5
            for item in episodes
        ),
        within_20_start_price_count=sum(
            item.start_price_lag_trading_days is not None
            and item.start_price_lag_trading_days <= 20
            for item in episodes
        ),
        m6_restructuring_candidate_episode_count=sum(
            item.m6_restructuring_candidate_count > 0 for item in episodes
        ),
    )
    benchmark_notes = [
        f"{benchmark_id}:{start or 'unavailable'}..{end or 'unavailable'}"
        for benchmark_id, (start, end) in sorted(benchmark_ranges.items())
    ]
    membership_source.notes.extend(benchmark_notes)
    warnings = [
        "陈旧覆盖由 qfq 价格可用性估算，不包含历史股本变化 guard；不能直接晋级 P6B-1。",
        "st_status_history 只作交叉核查；连续 valuation episode 以逐日 membership 构造。",
    ]
    if capital_audit.explicit_suspension_rows == 0:
        warnings.append(
            "trading_status_daily 没有显式停牌样本；停牌率以无当日 qfq 的价格缺口代理。"
        )
    if summary.membership_calendar_gap_count:
        warnings.append(
            f"membership 相对完整交易日历缺 {summary.membership_calendar_gap_count} 日；"
            f"{summary.gap_adjacent_episode_count} 轮候选边界邻近空洞，后续必须核证。"
        )
    blockers = []
    if capital_audit.market_factor_snapshot_count <= 1:
        blockers.append("历史 market-cap 快照未回填。")
    if not capital_audit.historical_share_change_guard_available:
        blockers.append("历史股本变化与老股东权益 guard 不可用。")
    if any(
        row.within_5_gate_pass_dates < row.trade_date_count for row in stale
    ):
        blockers.append(
            "本地 qfq 价格代理未形成连续 95% 覆盖区间；市场地图发布起点尚不能冻结。"
        )
    if m6_summary.exact_adjuster_records == 0:
        blockers.append("M6 没有精确资本结构 adjuster，qfq 不能替代老股东权益账。")
    if status_audit.open_row_count:
        blockers.append(
            "稀疏 st_status_history 含无结束日期记录，不能直接生成生产 valuation episode。"
        )
    human_decisions = [
        HumanDecision(
            decision_id="episode_primary_source",
            decision="确认连续 valuation episode 的主来源",
            recommendation="采用逐日 st_membership_daily；st_status_history 仅交叉核查。",
            evidence=(
                f"逐日 membership {membership_source.row_count} 行、"
                f"{membership_source.symbol_count} 只；稀疏历史有 "
                f"{status_audit.open_row_count} 条无结束日期记录；逐日源另有 "
                f"{summary.membership_calendar_gap_count} 个交易日空洞并已显式打标。"
            ),
        ),
        HumanDecision(
            decision_id="supported_history_boundary",
            decision="确认候选 inventory 与可发布市场地图使用不同历史边界",
            recommendation=(
                f"episode 候选不早于 {membership_source.min_date}；"
                "市场地图起点等价格/source probe 后再冻结。"
            ),
            evidence=(
                "membership 起点只证明能切候选 episode；当前 qfq 价格代理在多个年份"
                "未连续通过 95% 门。"
            ),
        ),
        HumanDecision(
            decision_id="stale_rule_release_gate",
            decision="确认 5 日陈旧规则何时可晋级",
            recommendation="完成 read-only daily_basic/股本 probe 前只报告价格可用性代理。",
            evidence="本地历史 market-factor 仅有单日快照，缺少股本变化 guard。",
        ),
    ]
    payload_without_id = {
        "contract_version": CONTRACT_VERSION,
        "as_of": effective_as_of,
        "source_inventory": [
            item.model_dump(mode="json")
            for item in [membership_source, price_source, m6_source, factor_source]
        ],
        "episode_summary": summary.model_dump(mode="json"),
        "episodes": [item.model_dump(mode="json") for item in episodes],
        "stale_coverage_by_year": [item.model_dump(mode="json") for item in stale],
        "market_cap_requests": request_plan.model_dump(mode="json"),
        "status_history_audit": status_audit.model_dump(mode="json"),
        "m6_candidates": m6_summary.model_dump(mode="json"),
        "capital_and_terminal_audit": capital_audit.model_dump(mode="json"),
        "human_decisions": [item.model_dump(mode="json") for item in human_decisions],
        "next_phase_blockers": blockers,
        "warnings": warnings,
    }
    return P6BDryPlan(
        plan_id=_plan_identifier(payload_without_id),
        generated_at=datetime.now(timezone.utc).isoformat(),
        **payload_without_id,
    )


def render_p6b_dry_plan_markdown(plan: P6BDryPlan) -> str:
    coverage_rows = "\n".join(
        f"| {row.year} | {row.trade_date_count} | "
        f"{row.exact_price_coverage:.1%} | {row.within_5_price_coverage:.1%} | "
        f"{row.within_20_price_coverage:.1%} | {row.within_5_gate_pass_dates} |"
        for row in plan.stale_coverage_by_year
    )
    decisions = "\n".join(
        f"{index}. **{item.decision}**：{item.recommendation} 证据：{item.evidence}"
        for index, item in enumerate(plan.human_decisions, 1)
    )
    blockers = "\n".join(f"- {item}" for item in plan.next_phase_blockers) or "- 无"
    warnings = "\n".join(f"- {item}" for item in plan.warnings) or "- 无"
    benchmark_ranges = "；".join(
        f"{benchmark_id} {date_range}"
        for benchmark_id, date_range
        in plan.market_cap_requests.benchmark_date_ranges.items()
    )
    return f"""# P6B-0 只读 dry plan

计划：`{plan.plan_id}`

数据截止：`{plan.as_of}`

契约：`{plan.contract_version}`

## 结论

- 逐日 membership 可构造 {plan.episode_summary.episode_count} 轮候选 episode，
  覆盖 {plan.episode_summary.symbol_count} 只股票；其中
  {plan.episode_summary.open_episode_count} 轮仍开放。
- membership 相对中证全指交易日历缺
  {plan.episode_summary.membership_calendar_gap_count} 日；
  {plan.episode_summary.gap_adjacent_episode_count} 轮候选边界邻近空洞，必须保持候选状态。
- 历史市值按交易日整市场拉取，共需
  {plan.market_cap_requests.unique_trade_date_count} 个唯一锚点日请求，而不是
  symbol × date 请求。
- read-only provider probe 只抽查
  {len(plan.market_cap_requests.probe_trade_dates)} 个日期：
  {", ".join(plan.market_cap_requests.probe_trade_dates)}。
- {plan.episode_summary.m6_restructuring_candidate_episode_count} 轮候选 episode
  命中 M6 重整候选；M6 仍是 `case_note_only`，不能直接晋级。
- 当前本地只有 {plan.capital_and_terminal_audit.market_factor_snapshot_count} 个
  market-factor snapshot；股本变化 guard
  `{"ready" if plan.capital_and_terminal_audit.historical_share_change_guard_available else "not_ready"}`。
- 市场语境实际区间：{benchmark_ranges}。

## 价格可用性代理

这些比例尚未通过历史股本变化 guard，只用于决定 source probe 和可支持历史边界。

| 年份 | 交易日 | 当日价 | 5日内 | 20日内 | 5日口径通过95%门的日期 |
| --- | ---: | ---: | ---: | ---: | ---: |
{coverage_rows}

## 下一阶段 blocker

{blockers}

## 人类只需确认

{decisions}

## 警告

{warnings}

本计划不联网、不修改生产数据库；provider probe 和历史回填是后续独立动作。
"""


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="生成 P6B-0 只读 episode/市值/停牌/股本可行性计划"
    )
    parser.add_argument("--base-database", type=Path, default=DEFAULT_BASE_DATABASE)
    parser.add_argument(
        "--market-context-database", type=Path, default=MARKET_CONTEXT_DB
    )
    parser.add_argument(
        "--market-factor-database", type=Path, default=MARKET_FACTOR_DB
    )
    parser.add_argument("--episode-index", type=Path, default=DEFAULT_EPISODE_INDEX)
    parser.add_argument(
        "--episode-manifest", type=Path, default=DEFAULT_EPISODE_MANIFEST
    )
    parser.add_argument("--as-of", default="")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    args = parser.parse_args(argv)
    plan = build_p6b_dry_plan(
        base_database=args.base_database,
        market_context_database=args.market_context_database,
        market_factor_database=args.market_factor_database,
        episode_index=args.episode_index,
        episode_manifest=args.episode_manifest,
        as_of=args.as_of,
    )
    markdown = render_p6b_dry_plan_markdown(plan)
    if args.output_json:
        _write_json(args.output_json, plan.model_dump(mode="json"))
    if args.output_markdown:
        _write_text(args.output_markdown, markdown)
    if not args.output_json and not args.output_markdown:
        print(markdown)
    else:
        print(json.dumps({
            "plan_id": plan.plan_id,
            "as_of": plan.as_of,
            "output_json": str(args.output_json or ""),
            "output_markdown": str(args.output_markdown or ""),
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
