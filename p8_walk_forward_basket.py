"""Tradable weekly P8 v2 basket with suspension, one-price and cost controls."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from data_refresh import atomic_write_json
from market_activity import MarketActivityRepository
from p8_backtest_v2 import CONTRACT_VERSION, TEST_YEARS, _benchmarks, _calendar_membership, _latest_records, _prices
from p8_research import P8ResearchRepository, build_run, canonical_json, content_id
from settings import DATA_ROOT, MARKET_ACTIVITY_DB, MARKET_CONTEXT_DB, P8_RESEARCH_DB


PRIMARY_COST = 0.005
SENSITIVITY_COSTS = (0.002, 0.010)
DEFAULT_BASE_DB = DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"


def _connect_ro(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _fallback_trade_states(path: Path, start: str, through: str) -> dict[tuple[str, str], dict[str, bool]]:
    result: dict[tuple[str, str], dict[str, bool]] = {}
    with _connect_ro(path) as connection:
        for row in connection.execute(
            "select symbol,trade_date,is_trading,is_suspended,is_limit_up,is_limit_down,is_one_word_limit "
            "from trading_status_daily where trade_date between ? and ?", (start, through),
        ):
            trading = bool(row[2]) and not bool(row[3])
            one_word = bool(row[6])
            result[(str(row[0]), str(row[1]))] = {
                "buy": trading and not (one_word and bool(row[4])),
                "sell": trading and not (one_word and bool(row[5])),
                "known": True,
            }
    return result


def load_trade_states(
    *, market_activity_database: Path, base_database: Path,
    start: str, through: str,
) -> dict[tuple[str, str], dict[str, bool]]:
    result = _fallback_trade_states(base_database, start, through)
    for fact in MarketActivityRepository(market_activity_database).latest_facts(
        start_date=start, through=through,
    ):
        known = (
            fact.suspension_status != "unknown"
            and fact.one_price_limit is not None
            and not fact.limit_state_conflict
        )
        one_price_up = bool(fact.one_price_limit and fact.limit_status == 3)
        one_price_down = bool(fact.one_price_limit and fact.limit_status == 6)
        if fact.one_price_limit and fact.limit_status not in {3, 6}:
            one_price_up = bool(
                fact.close is not None and fact.up_limit is not None
                and abs(fact.close - fact.up_limit) <= max(.0001, abs(fact.up_limit) * 1e-6)
            )
            one_price_down = bool(
                fact.close is not None and fact.down_limit is not None
                and abs(fact.close - fact.down_limit) <= max(.0001, abs(fact.down_limit) * 1e-6)
            )
        trading = fact.suspension_status == "trading"
        result[(fact.symbol, fact.trade_date)] = {
            "buy": bool(known and trading and not one_price_up),
            "sell": bool(known and trading and not one_price_down),
            "known": bool(known),
        }
    return result


def _delisting_dates(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    with _connect_ro(path) as connection:
        for row in connection.execute(
            "select symbol,expected_price_end_date from stocks_meta "
            "where list_status='D' and expected_price_end_date is not null and expected_price_end_date!=''"
        ):
            result[str(row[0])] = str(row[1])[:10]
    return result


def _target_schedule(
    calendar: list[str], funnel: list[dict[str, Any]], *, excluded_symbols: set[str],
    excluded_lanes: set[str],
) -> dict[str, set[str]]:
    by_decision: dict[str, set[str]] = defaultdict(set)
    for item in funnel:
        symbol = str(item.get("symbol") or "")
        lane = str(item.get("primary_lane") or "")
        if symbol not in excluded_symbols and lane not in excluded_lanes:
            by_decision[str(item.get("decision_date") or "")].add(symbol)
    index = {day: position for position, day in enumerate(calendar)}
    schedule: dict[str, set[str]] = {}
    for decision, symbols in by_decision.items():
        position = index.get(decision)
        if position is not None and position + 1 < len(calendar):
            schedule[calendar[position + 1]] = set(symbols)
    return schedule


def _max_drawdown(values: list[float]) -> float | None:
    if not values:
        return None
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1)
    return worst


def _weekly_win_rate(
    nav_by_day: dict[str, float], benchmark: dict[str, float], calendar: list[str],
) -> float | None:
    week_ends: dict[tuple[int, int], str] = {}
    for day in calendar:
        iso = __import__("datetime").date.fromisoformat(day).isocalendar()
        week_ends[(iso.year, iso.week)] = day
    days = sorted(week_ends.values())
    wins = total = 0
    for left, right in zip(days, days[1:]):
        if left not in nav_by_day or right not in nav_by_day or left not in benchmark or right not in benchmark:
            continue
        portfolio_return = nav_by_day[right] / nav_by_day[left] - 1
        benchmark_return = benchmark[right] / benchmark[left] - 1
        wins += portfolio_return > benchmark_return
        total += 1
    return wins / total if total else None


def simulate_year(
    *, year: int, calendar: list[str], funnel: list[dict[str, Any]],
    prices: dict[str, dict[str, float]], trade_states: dict[tuple[str, str], dict[str, bool]],
    benchmark: dict[str, float], delisting_dates: dict[str, str], cost: float,
    excluded_symbols: set[str] | None = None, excluded_lanes: set[str] | None = None,
) -> dict[str, Any]:
    excluded_symbols = excluded_symbols or set()
    excluded_lanes = excluded_lanes or set()
    days = [day for day in calendar if day.startswith(f"{year}-")]
    year_funnel = [item for item in funnel if int(item.get("test_year") or 0) == year]
    schedule = _target_schedule(
        days, year_funnel, excluded_symbols=excluded_symbols, excluded_lanes=excluded_lanes,
    )
    cash = 1.0
    shares: dict[str, float] = {}
    marks: dict[str, float] = {}
    active_target: set[str] = set()
    pending_buys: set[str] = set()
    pending_sells: set[str] = set()
    contribution: dict[str, float] = defaultdict(float)
    nav_by_day: dict[str, float] = {}
    trade_ledger: list[dict[str, Any]] = []
    total_gross = 0.0
    cash_ratios: list[float] = []
    unknown_attempts = 0
    locked_sell_days = 0
    expired_buy_count = 0
    delist_settlements = 0

    def mark(day: str) -> float:
        nonlocal cash, delist_settlements
        for symbol in list(shares):
            current = prices.get(symbol, {}).get(day)
            prior = marks.get(symbol)
            if current is not None:
                if prior is not None:
                    contribution[symbol] += shares[symbol] * (current - prior)
                marks[symbol] = current
            elif delisting_dates.get(symbol, "9999-12-31") <= day:
                lost = shares[symbol] * (prior or 0.0)
                contribution[symbol] -= lost
                shares.pop(symbol, None)
                marks.pop(symbol, None)
                pending_sells.discard(symbol)
                pending_buys.discard(symbol)
                delist_settlements += 1
        return cash + sum(shares[symbol] * marks.get(symbol, 0.0) for symbol in shares)

    for day in days:
        nav = mark(day)
        rebalance = day in schedule
        if rebalance:
            expired_buy_count += len(pending_buys)
            active_target = set(schedule[day])
            pending_buys = set(active_target)
            pending_sells.update(set(shares) - active_target)
            pending_sells.difference_update(active_target)

        # Sell exits first; failed exits remain pending beyond the current week.
        for symbol in sorted(list(pending_sells)):
            price = prices.get(symbol, {}).get(day)
            state = trade_states.get((symbol, day), {"known": False, "sell": False})
            if price is None or not state.get("known"):
                unknown_attempts += 1
                continue
            if not state.get("sell"):
                locked_sell_days += 1
                continue
            quantity = shares.pop(symbol, 0.0)
            marks.pop(symbol, None)
            gross = quantity * price
            fee = gross * cost
            cash += gross - fee
            total_gross += gross
            contribution[symbol] -= fee
            pending_sells.discard(symbol)
            trade_ledger.append({
                "trade_date": day, "symbol": symbol, "side": "sell",
                "gross": gross, "cost": fee, "reason": "weekly_rebalance_or_persistent_exit",
            })

        if rebalance:
            nav = mark(day)
            locked_value = sum(
                shares[symbol] * marks.get(symbol, 0.0)
                for symbol in shares if symbol not in active_target
            )
            allocatable = max(0.0, nav - locked_value)
            desired = allocatable / len(active_target) if active_target else 0.0
            # Trim target holdings before funding new target positions.
            for symbol in sorted(active_target & set(shares)):
                price = prices.get(symbol, {}).get(day)
                state = trade_states.get((symbol, day), {"known": False, "sell": False})
                current_value = shares[symbol] * (price or marks.get(symbol, 0.0))
                excess = current_value - desired
                if excess <= 1e-12:
                    continue
                if price is None or not state.get("known") or not state.get("sell"):
                    continue
                quantity = min(shares[symbol], excess / price)
                gross = quantity * price
                fee = gross * cost
                shares[symbol] -= quantity
                cash += gross - fee
                total_gross += gross
                contribution[symbol] -= fee
                trade_ledger.append({
                    "trade_date": day, "symbol": symbol, "side": "sell",
                    "gross": gross, "cost": fee, "reason": "weekly_equal_weight_trim",
                })

        # New buys remain valid until the next target schedule replaces them.
        if active_target:
            nav = mark(day)
            locked_value = sum(
                shares[symbol] * marks.get(symbol, 0.0)
                for symbol in shares if symbol not in active_target
            )
            desired = max(0.0, nav - locked_value) / len(active_target)
            for symbol in sorted(list(pending_buys)):
                if symbol not in active_target:
                    pending_buys.discard(symbol)
                    continue
                price = prices.get(symbol, {}).get(day)
                state = trade_states.get((symbol, day), {"known": False, "buy": False})
                if price is None or not state.get("known"):
                    unknown_attempts += 1
                    continue
                if not state.get("buy"):
                    continue
                current_value = shares.get(symbol, 0.0) * price
                deficit = max(0.0, desired - current_value)
                gross = min(deficit, cash / (1 + cost))
                if gross <= 1e-12:
                    pending_buys.discard(symbol)
                    continue
                fee = gross * cost
                quantity = gross / price
                shares[symbol] = shares.get(symbol, 0.0) + quantity
                marks[symbol] = price
                cash -= gross + fee
                total_gross += gross
                contribution[symbol] -= fee
                pending_buys.discard(symbol)
                trade_ledger.append({
                    "trade_date": day, "symbol": symbol, "side": "buy",
                    "gross": gross, "cost": fee, "reason": "weekly_target",
                })
        nav = mark(day)
        nav_by_day[day] = nav
        cash_ratios.append(cash / nav if nav > 0 else 0.0)

    if not days:
        return {"year": year, "status": "unavailable", "reason": "calendar_empty"}
    first_day, last_day = days[0], days[-1]
    portfolio_return = nav_by_day[last_day] - 1
    benchmark_return = (
        benchmark[last_day] / benchmark[first_day] - 1
        if benchmark.get(first_day) and benchmark.get(last_day) else None
    )
    excess = portfolio_return - benchmark_return if benchmark_return is not None else None
    annualized = (
        nav_by_day[last_day] ** (252 / len(days)) - 1
        if nav_by_day[last_day] > 0 else -1.0
    )
    return {
        "year": year,
        "status": "observable" if benchmark_return is not None else "benchmark_unavailable",
        "cost_one_way": cost,
        "calendar_day_count": len(days),
        "decision_count": len(schedule),
        "selected_symbol_count": len({str(item["symbol"]) for item in year_funnel}),
        "trade_count": len(trade_ledger),
        "portfolio_return": portfolio_return,
        "annualized_return": annualized,
        "st_benchmark_return": benchmark_return,
        "excess_return_st": excess,
        "max_drawdown": _max_drawdown([nav_by_day[day] for day in days]),
        "weekly_win_rate": _weekly_win_rate(nav_by_day, benchmark, days),
        "gross_turnover_on_initial_capital": total_gross,
        "mean_cash_ratio": statistics.mean(cash_ratios) if cash_ratios else None,
        "unknown_trade_state_attempts": unknown_attempts,
        "locked_sell_days": locked_sell_days,
        "expired_buy_count": expired_buy_count,
        "delist_total_loss_settlements": delist_settlements,
        "open_position_count": len(shares),
        "contribution_by_symbol": dict(sorted(contribution.items())),
        "trade_ledger": trade_ledger,
        "nav_by_day": nav_by_day,
    }


def _compound(values: list[float]) -> float | None:
    if not values:
        return None
    result = 1.0
    for value in values:
        result *= 1 + value
    return result - 1


def build_basket_report(
    *, base_database: Path, market_context_database: Path,
    market_activity_database: Path, repository: P8ResearchRepository,
) -> dict[str, Any]:
    funnel_run_id, funnel_digest, funnel = _latest_records(
        repository, "p8_historical_funnel_v2", "p8_historical_funnel_item_v2",
    )
    if not funnel:
        raise ValueError("缺 p8_historical_funnel_v2")
    calendar, _memberships = _calendar_membership(market_context_database, "2023-01-01", "2025-12-31")
    price_rows = _prices(base_database, "2023-01-01", "2025-12-31")
    prices = {symbol: dict(rows) for symbol, rows in price_rows.items()}
    benchmarks = _benchmarks(market_context_database, "2023-01-01", "2025-12-31")
    st_benchmark = benchmarks.get("st_equal_weight_v1", {})
    trade_states = load_trade_states(
        market_activity_database=market_activity_database,
        base_database=base_database, start="2023-01-01", through="2025-12-31",
    )
    delisting = _delisting_dates(base_database)

    primary = [
        simulate_year(
            year=year, calendar=calendar, funnel=funnel, prices=prices,
            trade_states=trade_states, benchmark=st_benchmark,
            delisting_dates=delisting, cost=PRIMARY_COST,
        ) for year in TEST_YEARS
    ]
    top_two_by_year: dict[str, list[str]] = {}
    stress: list[dict[str, Any]] = []
    for item in primary:
        year = int(item["year"])
        top = [
            symbol for symbol, _value in sorted(
                item.get("contribution_by_symbol", {}).items(), key=lambda pair: (-pair[1], pair[0]),
            )[:2]
        ]
        top_two_by_year[str(year)] = top
        stress.append(simulate_year(
            year=year, calendar=calendar, funnel=funnel, prices=prices,
            trade_states=trade_states, benchmark=st_benchmark,
            delisting_dates=delisting, cost=PRIMARY_COST,
            excluded_symbols=set(top),
        ))
    without_persistent = [
        simulate_year(
            year=year, calendar=calendar, funnel=funnel, prices=prices,
            trade_states=trade_states, benchmark=st_benchmark,
            delisting_dates=delisting, cost=PRIMARY_COST,
            excluded_lanes={"persistent_activity"},
        ) for year in TEST_YEARS
    ]
    sensitivities: dict[str, list[dict[str, Any]]] = {}
    for cost in SENSITIVITY_COSTS:
        sensitivities[f"{int(cost * 10000)}bp"] = [
            simulate_year(
                year=year, calendar=calendar, funnel=funnel, prices=prices,
                trade_states=trade_states, benchmark=st_benchmark,
                delisting_dates=delisting, cost=cost,
            ) for year in TEST_YEARS
        ]
    yearly_excess = [float(item["excess_return_st"]) for item in primary if item.get("excess_return_st") is not None]
    overall_portfolio = _compound([float(item["portfolio_return"]) for item in primary])
    overall_benchmark = _compound([float(item["st_benchmark_return"]) for item in primary])
    overall_excess = (
        overall_portfolio - overall_benchmark
        if overall_portfolio is not None and overall_benchmark is not None else None
    )
    stress_portfolio = _compound([float(item["portfolio_return"]) for item in stress])
    stress_benchmark = _compound([float(item["st_benchmark_return"]) for item in stress])
    stress_overall = (
        stress_portfolio - stress_benchmark
        if stress_portfolio is not None and stress_benchmark is not None else None
    )
    positive_years = sum(value > 0 for value in yearly_excess)
    if len(yearly_excess) < 3:
        decision = "unavailable"
    elif positive_years < 2 or stress_overall is None or stress_overall <= 0:
        decision = "killed"
    else:
        decision = "supported"
    without_portfolio = _compound([float(item["portfolio_return"]) for item in without_persistent])
    without_benchmark = _compound([float(item["st_benchmark_return"]) for item in without_persistent])
    without_overall = (
        without_portfolio - without_benchmark
        if without_portfolio is not None and without_benchmark is not None else None
    )
    return {
        "record_id": content_id("P8BASKET", {
            "contract": CONTRACT_VERSION, "funnel_digest": funnel_digest,
            "cost": PRIMARY_COST, "top_two": top_two_by_year,
        }),
        "contract_version": CONTRACT_VERSION,
        "source_funnel_run_id": funnel_run_id,
        "source_funnel_digest": funnel_digest,
        "start_date": "2023-01-01",
        "through": "2025-12-31",
        "primary_cost_one_way": PRIMARY_COST,
        "status": decision,
        "positive_excess_year_count": positive_years,
        "overall_compounded_excess_st": overall_excess,
        "top_two_removed_compounded_excess_st": stress_overall,
        "top_two_removed_by_year": top_two_by_year,
        "persistent_lane_incremental_compounded_excess_st": (
            overall_excess - without_overall
            if overall_excess is not None and without_overall is not None else None
        ),
        "per_year": primary,
        "top_two_removed_per_year": stress,
        "without_persistent_lane_per_year": without_persistent,
        "cost_sensitivity": sensitivities,
        "not_a_trading_signal": True,
    }


def persist_basket(repository: P8ResearchRepository, report: dict[str, Any]) -> str:
    run = build_run(
        run_kind="p8_walk_forward_basket_v2", contract_version=CONTRACT_VERSION,
        start_date="2023-01-01", through="2025-12-31",
        source_run_ids=[str(report["source_funnel_run_id"])],
        source_digests={"historical_funnel": str(report["source_funnel_digest"])},
        record_payloads={"p8_walk_forward_basket_v2": [report]},
    )
    repository.persist(run=run, records={"p8_walk_forward_basket_v2": [report]})
    return run.run_id


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-database", type=Path, default=DEFAULT_BASE_DB)
    parser.add_argument("--market-context-database", type=Path, default=MARKET_CONTEXT_DB)
    parser.add_argument("--market-activity-database", type=Path, default=MARKET_ACTIVITY_DB)
    parser.add_argument("--repository", type=Path, default=P8_RESEARCH_DB)
    parser.add_argument("--output-json", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repository = P8ResearchRepository(args.repository)
    report = build_basket_report(
        base_database=args.base_database,
        market_context_database=args.market_context_database,
        market_activity_database=args.market_activity_database,
        repository=repository,
    )
    run_id = persist_basket(repository, report)
    report["run_id"] = run_id
    atomic_write_json(args.output_json, report)
    print(json.dumps({
        "run_id": run_id, "status": report["status"],
        "positive_excess_year_count": report["positive_excess_year_count"],
        "overall_compounded_excess_st": report["overall_compounded_excess_st"],
        "top_two_removed_compounded_excess_st": report["top_two_removed_compounded_excess_st"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
