"""P8E observable qfq paths and fail-closed old-shareholder equity status."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from market_activity import MarketActivityRepository
from p8_research import P8ResearchRepository, build_run, content_id
from settings import (
    DATA_ROOT, MARKET_ACTIVITY_DB, MARKET_CONTEXT_DB, MARKET_FACTOR_DB, P8_RESEARCH_DB,
    VALUATION_EPISODE_DB,
)


CONTRACT_VERSION = "p8_stage_return_paths_v1"
HORIZONS = (5, 10, 20, 60)
DEFAULT_BASE_DB = DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class HorizonReturn(StrictModel):
    horizon: int
    exit_date: str = ""
    stock_qfq_return: float | None = None
    excess_return_st: float | None = None
    excess_return_csi2000: float | None = None
    observed: bool
    right_censored: bool
    capital_structure_status: Literal["unchanged_observed", "changed", "unknown"]


class ReturnPath(StrictModel):
    path_id: str = Field(pattern=r"^P8RP-[A-F0-9]{20}$")
    symbol: str = Field(pattern=r"^\d{6}$")
    anchor_id: str
    anchor_kind: Literal["episode_start", "event"]
    anchor_node: str
    anchor_available_as_of: str
    entry_date: str = ""
    entry_tradeability_status: Literal[
        "eligible_verified", "price_observed_but_tradeability_unknown", "unavailable"
    ]
    entry_delay_price_rows: int = Field(ge=0)
    entry_exclusion_reasons: list[str] = Field(default_factory=list)
    direction: str
    old_equity_effect: str
    evidence_status: str
    horizons: list[HorizonReturn]
    delisted_known: bool
    last_exchange_date: str = ""
    last_exchange_observable_return: float | None = None
    total_loss_stress: float | None = None
    old_shareholder_equity_path_status: Literal["exact", "range", "unknown"]
    notice: Literal["qfq 路径是可观察市场路径，不等于精确旧股东权益回报"] = (
        "qfq 路径是可观察市场路径，不等于精确旧股东权益回报"
    )


class ReturnMaterializationResult(StrictModel):
    run_id: str
    start_date: str
    through: str
    path_count: int
    episode_anchor_count: int
    event_anchor_count: int
    evidence_status_counts: dict[str, int]
    completed_horizon_counts: dict[str, int]
    capital_structure_status_counts: dict[str, int]
    delisted_path_count: int
    exact_old_shareholder_path_count: int
    entry_tradeability_status_counts: dict[str, int]


def _connect_ro(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_episodes(path: Path, *, start_date: str, through: str) -> tuple[str, list[dict[str, Any]]]:
    with _connect_ro(path) as connection:
        run = connection.execute(
            "select run_id from valuation_episode_runs order by rowid desc limit 1"
        ).fetchone()
        episodes = [
            json.loads(str(row[0])) for row in connection.execute(
                "select payload_json from valuation_episodes where evidence_status='verified' "
                "and start_date<=? and end_date>=? order by symbol,start_date",
                (through, start_date),
            )
        ]
    return str(run[0]) if run else "", episodes


def _load_prices(
    path: Path, *, symbols: set[str], start_date: str, through: str,
) -> dict[str, list[tuple[str, float]]]:
    result: dict[str, list[tuple[str, float]]] = defaultdict(list)
    with _connect_ro(path) as connection:
        for row in connection.execute(
            "select symbol,trade_date,close from daily_prices where adjust='qfq' "
            "and trade_date between ? and ? and close>0 order by symbol,trade_date",
            (start_date, through),
        ):
            symbol = str(row[0])
            if symbol in symbols:
                result[symbol].append((str(row[1]), float(row[2])))
    return result


def _load_benchmarks(path: Path, *, start_date: str, through: str) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = defaultdict(dict)
    with _connect_ro(path) as connection:
        for row in connection.execute(
            "select benchmark_id,trade_date,close from benchmark_daily "
            "where benchmark_id in ('st_equal_weight_v1','csi_2000') "
            "and trade_date between ? and ? and close>0",
            (start_date, through),
        ):
            result[str(row[0])][str(row[1])] = float(row[2])
    return result


def _load_shares(path: Path, *, symbols: set[str]) -> dict[str, list[tuple[str, float]]]:
    result: dict[str, list[tuple[str, float]]] = defaultdict(list)
    with _connect_ro(path) as connection:
        for row in connection.execute(
            "select d.symbol,d.trade_date,d.total_shares from market_cap_daily d "
            "join market_factor_snapshots s on s.snapshot_id=d.snapshot_id "
            "where d.total_shares is not null order by d.symbol,d.trade_date,s.created_at"
        ):
            symbol = str(row[0])
            if symbol in symbols:
                point = (str(row[1]), float(row[2]))
                if result[symbol] and result[symbol][-1][0] == point[0]:
                    result[symbol][-1] = point
                else:
                    result[symbol].append(point)
    return result


def _delisted_symbols(path: Path) -> set[str]:
    with _connect_ro(path) as connection:
        return {
            str(row[0]) for row in connection.execute(
                "select distinct symbol from st_status_history "
                "where upper(coalesce(notes,'')) like '%FINAL_STATUS%DELISTED%'"
            )
        }


def _first_strictly_after(rows: list[tuple[str, float]], day: str) -> int | None:
    for index, (trade_date, _close) in enumerate(rows):
        if trade_date > day:
            return index
    return None


def _first_on_or_after(rows: list[tuple[str, float]], day: str) -> int | None:
    for index, (trade_date, _close) in enumerate(rows):
        if trade_date >= day:
            return index
    return None


def _first_tradeable(
    rows: list[tuple[str, float]], day: str, *, strictly_after: bool,
    activity: dict[tuple[str, str], dict[str, Any]], symbol: str,
) -> tuple[int | None, str, int, list[str]]:
    first_candidate: int | None = None
    exclusions: list[str] = []
    for index, (trade_date, _close) in enumerate(rows):
        if trade_date < day or (strictly_after and trade_date == day):
            continue
        if first_candidate is None:
            first_candidate = index
        fact = activity.get((symbol, trade_date))
        if fact is None:
            return (
                index, "price_observed_but_tradeability_unknown",
                index - first_candidate, exclusions,
            )
        reasons: list[str] = []
        if fact.get("suspension_status") == "suspended":
            reasons.append("suspended")
        if fact.get("one_price_limit") is True:
            reasons.append("one_price_limit")
        if reasons:
            exclusions.extend(f"{trade_date}:{reason}" for reason in reasons)
            continue
        return index, "eligible_verified", index - first_candidate, exclusions
    return None, "unavailable", 0, exclusions


def _benchmark_return(series: dict[str, float], start: str, end: str) -> float | None:
    left, right = series.get(start), series.get(end)
    if left is None or right is None or left <= 0:
        return None
    return right / left - 1


def _share_at(points: list[tuple[str, float]], day: str) -> float | None:
    eligible = [value for point_day, value in points if point_day <= day]
    return eligible[-1] if eligible else None


def _capital_status(points: list[tuple[str, float]], start: str, end: str) -> str:
    left, right = _share_at(points, start), _share_at(points, end)
    if left is None or right is None:
        return "unknown"
    return "changed" if abs(right - left) > max(1.0, abs(left) * 1e-8) else "unchanged_observed"


def _path(
    *, anchor: dict[str, Any], prices: dict[str, list[tuple[str, float]]],
    benchmarks: dict[str, dict[str, float]], shares: dict[str, list[tuple[str, float]]],
    activity: dict[tuple[str, str], dict[str, Any]], delisted: set[str], through: str,
) -> ReturnPath:
    symbol = str(anchor["symbol"])
    day = str(anchor["available_as_of"])
    rows = prices.get(symbol, [])
    entry_index, tradeability, delay, exclusions = _first_tradeable(
        rows, day,
        strictly_after=anchor["anchor_kind"] != "episode_start",
        activity=activity, symbol=symbol,
    )
    entry_date = rows[entry_index][0] if entry_index is not None else ""
    entry_close = rows[entry_index][1] if entry_index is not None else None
    horizons: list[HorizonReturn] = []
    for horizon in HORIZONS:
        target = entry_index + horizon if entry_index is not None else None
        observed = target is not None and target < len(rows) and rows[target][0] <= through
        exit_date = rows[target][0] if observed and target is not None else ""
        stock_return = (
            rows[target][1] / entry_close - 1
            if observed and target is not None and entry_close is not None and entry_close > 0 else None
        )
        st_return = _benchmark_return(benchmarks["st_equal_weight_v1"], entry_date, exit_date) if observed else None
        csi_return = _benchmark_return(benchmarks["csi_2000"], entry_date, exit_date) if observed else None
        horizons.append(HorizonReturn(
            horizon=horizon,
            exit_date=exit_date,
            stock_qfq_return=stock_return,
            excess_return_st=stock_return - st_return if stock_return is not None and st_return is not None else None,
            excess_return_csi2000=stock_return - csi_return if stock_return is not None and csi_return is not None else None,
            observed=observed,
            right_censored=not observed,
            capital_structure_status=(
                _capital_status(shares.get(symbol, []), entry_date, exit_date)
                if observed else "unknown"
            ),  # type: ignore[arg-type]
        ))
    last_date = rows[-1][0] if rows else ""
    last_return = (
        rows[-1][1] / entry_close - 1
        if entry_close is not None and entry_close > 0 and rows else None
    )
    known_delisted = symbol in delisted
    identity = {
        "contract": CONTRACT_VERSION,
        "anchor_id": anchor["anchor_id"],
        "entry_date": entry_date,
        "horizons": [item.model_dump(mode="json") for item in horizons],
    }
    return ReturnPath(
        path_id=content_id("P8RP", identity),
        symbol=symbol,
        anchor_id=str(anchor["anchor_id"]),
        anchor_kind=anchor["anchor_kind"],
        anchor_node=str(anchor["anchor_node"]),
        anchor_available_as_of=day,
        entry_date=entry_date,
        entry_tradeability_status=tradeability,  # type: ignore[arg-type]
        entry_delay_price_rows=delay,
        entry_exclusion_reasons=exclusions,
        direction=str(anchor.get("direction") or "unknown"),
        old_equity_effect=str(anchor.get("old_equity_effect") or "unknown"),
        evidence_status=str(anchor.get("evidence_status") or "unknown"),
        horizons=horizons,
        delisted_known=known_delisted,
        last_exchange_date=last_date if known_delisted else "",
        last_exchange_observable_return=last_return if known_delisted else None,
        total_loss_stress=-1.0 if known_delisted and entry_close is not None else None,
        old_shareholder_equity_path_status="unknown",
    )


def materialize_return_paths(
    *, base_database: Path, market_context_database: Path,
    market_factor_database: Path, market_activity_database: Path,
    valuation_episode_database: Path,
    repository: P8ResearchRepository, start_date: str, through: str,
) -> ReturnMaterializationResult:
    event_run = repository.latest_run("event_graph")
    if event_run is None:
        raise ValueError("P8E 需要先物化 event_graph")
    events = repository.records(run_id=event_run.run_id, record_type="derived_event")
    p6_run_id, episodes = _load_episodes(
        valuation_episode_database, start_date=start_date, through=through,
    )
    anchors = [
        {
            "anchor_id": item["episode_id"], "anchor_kind": "episode_start",
            "anchor_node": item.get("current_stage", "st_distress_only"),
            "available_as_of": item["start_date"], "symbol": item["symbol"],
            "direction": "unknown", "old_equity_effect": "unknown",
            "evidence_status": item.get("evidence_status", "verified"),
        }
        for item in episodes
    ]
    anchors.extend({
        "anchor_id": item["event_id"], "anchor_kind": "event",
        "anchor_node": item["node"], "available_as_of": item["available_as_of"],
        "symbol": item["symbol"], "direction": item["process_direction"],
        "old_equity_effect": item["old_equity_effect"],
        "evidence_status": item["evidence_status"],
    } for item in events)
    symbols = {str(item["symbol"]) for item in anchors}
    prices = _load_prices(
        base_database, symbols=symbols, start_date=start_date, through=through,
    )
    benchmarks = _load_benchmarks(
        market_context_database, start_date=start_date, through=through,
    )
    shares = _load_shares(market_factor_database, symbols=symbols)
    activity = {
        (item.symbol, item.trade_date): item.model_dump(mode="json")
        for item in MarketActivityRepository(market_activity_database).latest_facts(
            start_date=start_date, through=through,
        )
    }
    delisted = _delisted_symbols(base_database)
    paths = [
        _path(
            anchor=anchor, prices=prices, benchmarks=benchmarks,
            shares=shares, activity=activity, delisted=delisted, through=through,
        )
        for anchor in anchors
    ]
    records = {"return_path": [
        {
            **item.model_dump(mode="json"),
            "record_id": item.path_id,
            "available_as_of": item.anchor_available_as_of,
        }
        for item in paths
    ]}
    run = build_run(
        run_kind="return_paths", contract_version=CONTRACT_VERSION,
        start_date=start_date, through=through,
        source_run_ids=[item for item in (p6_run_id, event_run.run_id) if item],
        source_digests={
            "base_database": _file_digest(base_database),
            "market_context_v1": _file_digest(market_context_database),
            "market_factors_v1": _file_digest(market_factor_database),
            "market_activity_v1": _file_digest(market_activity_database),
        },
        record_payloads=records,
    )
    repository.persist(run=run, records=records)
    completed = Counter(
        str(item.horizon) for path in paths for item in path.horizons if item.observed
    )
    capital = Counter(
        item.capital_structure_status for path in paths for item in path.horizons
    )
    return ReturnMaterializationResult(
        run_id=run.run_id,
        start_date=start_date,
        through=through,
        path_count=len(paths),
        episode_anchor_count=sum(item.anchor_kind == "episode_start" for item in paths),
        event_anchor_count=sum(item.anchor_kind == "event" for item in paths),
        evidence_status_counts=dict(sorted(Counter(item.evidence_status for item in paths).items())),
        completed_horizon_counts=dict(sorted(completed.items())),
        capital_structure_status_counts=dict(sorted(capital.items())),
        delisted_path_count=sum(item.delisted_known for item in paths),
        exact_old_shareholder_path_count=sum(item.old_shareholder_equity_path_status == "exact" for item in paths),
        entry_tradeability_status_counts=dict(sorted(Counter(
            item.entry_tradeability_status for item in paths
        ).items())),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--through", required=True)
    parser.add_argument("--base-database", type=Path, default=DEFAULT_BASE_DB)
    parser.add_argument("--market-context-database", type=Path, default=MARKET_CONTEXT_DB)
    parser.add_argument("--market-factor-database", type=Path, default=MARKET_FACTOR_DB)
    parser.add_argument("--market-activity-database", type=Path, default=MARKET_ACTIVITY_DB)
    parser.add_argument("--valuation-episode-database", type=Path, default=VALUATION_EPISODE_DB)
    parser.add_argument("--repository", type=Path, default=P8_RESEARCH_DB)
    parser.add_argument("--output-json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = materialize_return_paths(
        base_database=args.base_database,
        market_context_database=args.market_context_database,
        market_factor_database=args.market_factor_database,
        market_activity_database=args.market_activity_database,
        valuation_episode_database=args.valuation_episode_database,
        repository=P8ResearchRepository(args.repository),
        start_date=args.start_date,
        through=args.through,
    )
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(result.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
