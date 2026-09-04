"""Concurrent-calendar shadow portfolio for accumulated P8 funnel runs."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from market_activity import MarketActivityRepository
from p8_research import P8ResearchRepository, build_run, canonical_json, content_id
from p8_returns import _first_tradeable
from settings import DATA_ROOT, MARKET_ACTIVITY_DB, MARKET_CONTEXT_DB, P8_RESEARCH_DB


CONTRACT_VERSION = "p8_concurrent_shadow_portfolio_v1"
PRIMARY_HOLDING_DAYS = 20
DEFAULT_BASE_DB = DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ShadowPosition(StrictModel):
    record_id: str = Field(pattern=r"^P8SP-[A-F0-9]{20}$")
    symbol: str = Field(pattern=r"^\d{6}$")
    selected_as_of: str
    funnel_item_id: str
    entry_date: str = ""
    exit_date: str = ""
    entry_tradeability_status: str
    position_status: Literal["open", "completed", "entry_unavailable"]
    holding_days: int = PRIMARY_HOLDING_DAYS
    qfq_return: float | None = None
    evidence_status: str = "observable_market_path"
    not_a_recommendation: Literal[True] = True


class PortfolioResult(StrictModel):
    record_id: str = Field(pattern=r"^P8PS-[A-F0-9]{20}$")
    start_date: str
    through: str
    source_funnel_run_ids: list[str]
    selected_item_count: int
    position_count: int
    completed_position_count: int
    open_position_count: int
    entry_unavailable_count: int
    observed_calendar_day_count: int
    concurrent_qfq_return: float | None = None
    concurrent_excess_return_st: float | None = None
    concurrent_excess_return_csi2000: float | None = None
    evidence_status: Literal["observable", "right_censored", "unavailable"]
    positions: list[ShadowPosition]


def _funnel_runs(repository: P8ResearchRepository, start_date: str, through: str) -> list[tuple[str, str]]:
    if not repository.path.is_file():
        return []
    with sqlite3.connect(f"file:{repository.path}?mode=ro", uri=True) as connection:
        rows = list(connection.execute(
            "select run_id,through,created_at from p8_runs where run_kind='funnel' "
            "and through between ? and ? order by through,created_at,run_id",
            (start_date, through),
        ))
    latest_by_day = {str(row[1]): str(row[0]) for row in rows}
    return [(run_id, day) for day, run_id in sorted(latest_by_day.items())]


def _prices(path: Path, start_date: str, through: str) -> dict[str, list[tuple[str, float]]]:
    result: dict[str, list[tuple[str, float]]] = defaultdict(list)
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        for row in connection.execute(
            "select symbol,trade_date,close from daily_prices where adjust='qfq' "
            "and trade_date between ? and ? and close>0 order by symbol,trade_date",
            (start_date, through),
        ):
            result[str(row[0])].append((str(row[1]), float(row[2])))
    return result


def _benchmarks(path: Path, start_date: str, through: str) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = defaultdict(dict)
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        for row in connection.execute(
            "select benchmark_id,trade_date,close from benchmark_daily where benchmark_id in ('st_equal_weight_v1','csi_2000') "
            "and trade_date between ? and ? and close>0", (start_date, through),
        ):
            result[str(row[0])][str(row[1])] = float(row[2])
    return result


def _compound(values: list[float]) -> float | None:
    if not values:
        return None
    wealth = 1.0
    for value in values:
        wealth *= 1.0 + value
    return wealth - 1.0


def materialize_portfolio(
    *, repository: P8ResearchRepository, base_database: Path,
    market_context_database: Path, market_activity_database: Path,
    start_date: str, through: str,
) -> PortfolioResult:
    funnel_runs = _funnel_runs(repository, start_date, through)
    selections: list[dict[str, Any]] = []
    for run_id, _day in funnel_runs:
        selections.extend(repository.records(run_id=run_id, record_type="funnel_item"))
    selections = list({str(item.get("item_id")): item for item in selections}.values())
    prices = _prices(base_database, start_date, through)
    activity = {
        (item.symbol, item.trade_date): item.model_dump(mode="json")
        for item in MarketActivityRepository(market_activity_database).latest_facts(
            start_date=start_date, through=through,
        )
    }
    positions: list[ShadowPosition] = []
    last_exit_by_symbol: dict[str, str] = {}
    for item in sorted(selections, key=lambda value: (str(value.get("as_of")), str(value.get("symbol")))):
        symbol, selected = str(item["symbol"]), str(item["as_of"])
        if last_exit_by_symbol.get(symbol, "") >= selected:
            continue
        rows = prices.get(symbol, [])
        entry_index, tradeability, _delay, _exclusions = _first_tradeable(
            rows, selected, strictly_after=True, activity=activity, symbol=symbol,
        )
        if entry_index is None:
            entry_date = exit_date = ""
            status = "entry_unavailable"
            value = None
        else:
            entry_date = rows[entry_index][0]
            target = entry_index + PRIMARY_HOLDING_DAYS
            if target < len(rows) and rows[target][0] <= through:
                exit_date = rows[target][0]
                value = rows[target][1] / rows[entry_index][1] - 1
                status = "completed"
                last_exit_by_symbol[symbol] = exit_date
            else:
                exit_date = rows[-1][0] if rows and rows[-1][0] >= entry_date else ""
                value = None
                status = "open"
                last_exit_by_symbol[symbol] = through
        identity = {
            "contract": CONTRACT_VERSION, "item_id": item.get("item_id"),
            "entry_date": entry_date, "holding_days": PRIMARY_HOLDING_DAYS,
        }
        positions.append(ShadowPosition(
            record_id=content_id("P8SP", identity), symbol=symbol,
            selected_as_of=selected, funnel_item_id=str(item.get("item_id") or ""),
            entry_date=entry_date, exit_date=exit_date,
            entry_tradeability_status=tradeability,
            position_status=status, qfq_return=value,  # type: ignore[arg-type]
        ))

    daily_returns: list[tuple[str, float]] = []
    all_dates = sorted({day for rows in prices.values() for day, _close in rows})
    price_maps = {symbol: dict(rows) for symbol, rows in prices.items()}
    for previous_day, current_day in zip(all_dates, all_dates[1:]):
        live = [
            item for item in positions
            if item.entry_date and item.entry_date <= previous_day
            and (not item.exit_date or current_day <= item.exit_date)
            and previous_day in price_maps.get(item.symbol, {})
            and current_day in price_maps.get(item.symbol, {})
        ]
        returns = [
            price_maps[item.symbol][current_day] / price_maps[item.symbol][previous_day] - 1
            for item in live if price_maps[item.symbol][previous_day] > 0
        ]
        if returns:
            daily_returns.append((current_day, sum(returns) / len(returns)))
    portfolio_return = _compound([value for _day, value in daily_returns])
    benchmarks = _benchmarks(market_context_database, start_date, through)
    first_day = daily_returns[0][0] if daily_returns else ""
    last_day = daily_returns[-1][0] if daily_returns else ""
    benchmark_returns: dict[str, float | None] = {}
    for benchmark_id in ("st_equal_weight_v1", "csi_2000"):
        left = benchmarks[benchmark_id].get(first_day)
        right = benchmarks[benchmark_id].get(last_day)
        benchmark_returns[benchmark_id] = right / left - 1 if left and right else None
    status = (
        "unavailable" if not positions or not daily_returns
        else "right_censored" if any(item.position_status == "open" for item in positions)
        else "observable"
    )
    identity = {
        "contract": CONTRACT_VERSION, "start_date": start_date, "through": through,
        "funnel_runs": [item[0] for item in funnel_runs],
        "positions": [item.model_dump(mode="json") for item in positions],
    }
    return PortfolioResult(
        record_id=content_id("P8PS", identity), start_date=start_date, through=through,
        source_funnel_run_ids=[item[0] for item in funnel_runs],
        selected_item_count=len(selections), position_count=len(positions),
        completed_position_count=sum(item.position_status == "completed" for item in positions),
        open_position_count=sum(item.position_status == "open" for item in positions),
        entry_unavailable_count=sum(item.position_status == "entry_unavailable" for item in positions),
        observed_calendar_day_count=len(daily_returns), concurrent_qfq_return=portfolio_return,
        concurrent_excess_return_st=(
            portfolio_return - benchmark_returns["st_equal_weight_v1"]
            if portfolio_return is not None and benchmark_returns["st_equal_weight_v1"] is not None else None
        ),
        concurrent_excess_return_csi2000=(
            portfolio_return - benchmark_returns["csi_2000"]
            if portfolio_return is not None and benchmark_returns["csi_2000"] is not None else None
        ),
        evidence_status=status, positions=positions,  # type: ignore[arg-type]
    )


def persist(result: PortfolioResult, repository: P8ResearchRepository):
    summary = result.model_dump(mode="json", exclude={"positions"})
    records = {
        "shadow_position": [item.model_dump(mode="json") for item in result.positions],
        "portfolio_summary": [summary],
    }
    run = build_run(
        run_kind="portfolio", contract_version=CONTRACT_VERSION,
        start_date=result.start_date, through=result.through,
        source_run_ids=result.source_funnel_run_ids,
        source_digests={"result": hashlib.sha256(canonical_json(summary).encode()).hexdigest()},
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
    parser.add_argument("--market-activity-database", type=Path, default=MARKET_ACTIVITY_DB)
    parser.add_argument("--repository", type=Path, default=P8_RESEARCH_DB)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    repository = P8ResearchRepository(args.repository)
    result = materialize_portfolio(
        repository=repository, base_database=args.base_database,
        market_context_database=args.market_context_database,
        market_activity_database=args.market_activity_database,
        start_date=args.start_date, through=args.through,
    )
    run = persist(result, repository)
    payload = {"run_id": run.run_id, **result.model_dump(mode="json")}
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "positions"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
