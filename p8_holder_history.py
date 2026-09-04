"""Backfill point-in-time holder-number changes for historical ST members."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from bisect import bisect_left, bisect_right
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from data_refresh import TushareHttpClient, atomic_write_json
from p8_research import P8ResearchRepository, build_run, canonical_json, content_id
from settings import DATA_ROOT, MARKET_CONTEXT_DB, P8_RESEARCH_DB


CONTRACT_VERSION = "v8_p8_holder_history_v1"
START_DATE = "2021-03-17"
THROUGH = "2025-12-31"
QUERY_START = "2020-01-01"
DEFAULT_CACHE_DIR = DATA_ROOT / "local_data/v8_copilot/p8_holder_history_cache"
_thread_local = threading.local()


def _client() -> TushareHttpClient:
    client = getattr(_thread_local, "client", None)
    if client is None:
        client = TushareHttpClient()
        _thread_local.client = client
    return client


def _load_env(path: Path | None) -> None:
    if path is None:
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in {"TUSHARE_TOKEN", "TUSHARE_HTTP_URL"}:
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _compact(value: Any) -> str:
    match = re.match(r"(\d{6})", str(value or ""))
    return match.group(1) if match else ""


def _iso(value: Any) -> str:
    raw = str(value or "")
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}" if len(raw) == 8 and raw.isdigit() else raw


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _universe(path: Path) -> tuple[list[str], list[str], dict[str, set[str]]]:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "select trade_date,symbol from st_membership_daily "
            "where trade_date between ? and ? order by trade_date,symbol",
            (START_DATE, THROUGH),
        ).fetchall()
    members: dict[str, set[str]] = {}
    for day, symbol in rows:
        members.setdefault(str(day), set()).add(str(symbol))
    calendar = sorted(members)
    symbols = sorted({symbol for values in members.values() for symbol in values})
    return symbols, calendar, members


def _cache_path(cache_dir: Path, symbol: str) -> Path:
    return cache_dir / f"{symbol}_{QUERY_START}_{THROUGH}.json"


def _fetch_one(
    *, symbol: str, cache_dir: Path, client_factory: Callable[[], TushareHttpClient],
    attempts: int,
) -> tuple[str, list[dict[str, Any]], bool, str]:
    path = _cache_path(cache_dir, symbol)
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return symbol, list(payload["rows"]), True, "complete"
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            pass
    error = ""
    for attempt in range(max(1, attempts)):
        try:
            rows = list(client_factory().fetch_holder_numbers(
                symbol=symbol, start_date=QUERY_START, end_date=THROUGH,
            ))
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(path, {"symbol": symbol, "rows": rows})
            return symbol, rows, False, "complete"
        except Exception as exc:
            error = f"{type(exc).__name__}:{' '.join(str(exc).split())[:200]}"
            if attempt + 1 < max(1, attempts):
                time.sleep(float(2 ** attempt))
    return symbol, [], False, f"failed:{error}"


def _next_trade_day(calendar: list[str], disclosure: str) -> str:
    index = bisect_right(calendar, disclosure)
    return calendar[index] if index < len(calendar) else ""


def _membership_day(calendar: list[str], disclosure: str) -> str:
    index = bisect_right(calendar, disclosure) - 1
    return calendar[index] if index >= 0 else ""


def _records_for_symbol(
    *, symbol: str, rows: list[dict[str, Any]], calendar: list[str],
    memberships: dict[str, set[str]],
) -> list[dict[str, Any]]:
    # A later report period disclosed on the same date is the best then-current fact.
    by_disclosure: dict[str, dict[str, Any]] = {}
    for row in rows:
        disclosure = _iso(row.get("ann_date"))
        holder_num = _number(row.get("holder_num"))
        if not disclosure or holder_num is None:
            continue
        candidate = dict(row)
        existing = by_disclosure.get(disclosure)
        if existing is None or str(candidate.get("end_date") or "") > str(existing.get("end_date") or ""):
            by_disclosure[disclosure] = candidate
    ordered = sorted(by_disclosure.items())
    result: list[dict[str, Any]] = []
    prior_num: float | None = None
    prior_disclosure = ""
    for disclosure, row in ordered:
        holder_num = _number(row.get("holder_num"))
        assert holder_num is not None
        change = holder_num / prior_num - 1 if prior_num else None
        observation_day = _next_trade_day(calendar, disclosure)
        member_day = _membership_day(calendar, disclosure)
        is_st_member = bool(member_day and symbol in memberships.get(member_day, set()))
        if (
            START_DATE <= disclosure <= THROUGH and observation_day
            and is_st_member and change is not None
        ):
            source = {
                "ts_code": str(row.get("ts_code") or symbol),
                "ann_date": str(row.get("ann_date") or ""),
                "end_date": str(row.get("end_date") or ""),
                "holder_num": holder_num,
            }
            identity = {
                "contract": CONTRACT_VERSION, "symbol": symbol,
                "available_as_of": disclosure, "observation_trade_date": observation_day,
                "source": source, "prior_disclosure": prior_disclosure,
                "prior_holder_num": prior_num,
            }
            result.append({
                "record_id": content_id("P8HOLDER", identity),
                "symbol": symbol,
                "available_as_of": disclosure,
                "trade_date": observation_day,
                "membership_as_of": member_day,
                "report_period_end": _iso(row.get("end_date")),
                "holder_num": holder_num,
                "prior_holder_num": prior_num,
                "prior_available_as_of": prior_disclosure,
                "holder_change_pct": change,
                "source_row_digest": hashlib.sha256(canonical_json(source).encode()).hexdigest(),
                "evidence_status": "derived_point_in_time",
                "not_fund_flow": True,
                "not_a_trading_signal": True,
            })
        prior_num = holder_num
        prior_disclosure = disclosure
    return result


def backfill_holder_history(
    *, market_context_database: Path, repository: P8ResearchRepository,
    cache_dir: Path, allow_provider: bool, workers: int = 2, attempts: int = 3,
    client_factory: Callable[[], TushareHttpClient] = _client,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if not allow_provider:
        raise ValueError("历史股东户数回填必须显式传 --allow-provider")
    symbols, calendar, memberships = _universe(market_context_database)
    all_rows: dict[str, list[dict[str, Any]]] = {}
    cache_hits = failures = 0
    statuses: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(
                _fetch_one, symbol=symbol, cache_dir=cache_dir,
                client_factory=client_factory, attempts=attempts,
            ): symbol for symbol in symbols
        }
        completed = 0
        for future in as_completed(futures):
            symbol, rows, hit, status = future.result()
            all_rows[symbol] = rows
            statuses[symbol] = status
            cache_hits += int(hit)
            failures += int(status.startswith("failed:"))
            completed += 1
            if progress:
                progress({"completed": completed, "total": len(symbols), "symbol": symbol, "status": status})
    records = [
        record for symbol in symbols
        for record in _records_for_symbol(
            symbol=symbol, rows=all_rows.get(symbol, []),
            calendar=calendar, memberships=memberships,
        )
    ]
    source_digests = {
        symbol: hashlib.sha256(canonical_json(all_rows.get(symbol, [])).encode()).hexdigest()
        for symbol in symbols if not statuses.get(symbol, "").startswith("failed:")
    }
    run = build_run(
        run_kind="p8_holder_history_v2", contract_version=CONTRACT_VERSION,
        start_date=START_DATE, through=THROUGH, source_run_ids=[],
        source_digests={"provider_rows": hashlib.sha256(canonical_json(source_digests).encode()).hexdigest()},
        record_payloads={"p8_holder_history_v2": records},
    )
    repository.persist(run=run, records={"p8_holder_history_v2": records})
    return {
        "contract_version": CONTRACT_VERSION,
        "run_id": run.run_id,
        "status": "complete" if failures == 0 else "partial",
        "symbol_count": len(symbols),
        "provider_request_count": len(symbols) - cache_hits,
        "cache_hit_count": cache_hits,
        "failed_symbol_count": failures,
        "failed_symbols": sorted(symbol for symbol, status in statuses.items() if status.startswith("failed:")),
        "record_count": len(records),
        "company_count": len({record["symbol"] for record in records}),
        "by_year": {
            str(year): sum(str(record["trade_date"]).startswith(str(year)) for record in records)
            for year in range(2021, 2026)
        },
        "outcomes_read": False,
        "returns_computed": False,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market-context-database", type=Path, default=MARKET_CONTEXT_DB)
    parser.add_argument("--repository", type=Path, default=P8_RESEARCH_DB)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--allow-provider", action="store_true")
    parser.add_argument("--output-json", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    _load_env(args.env_file)
    result = backfill_holder_history(
        market_context_database=args.market_context_database,
        repository=P8ResearchRepository(args.repository), cache_dir=args.cache_dir,
        allow_provider=args.allow_provider, workers=args.workers, attempts=args.attempts,
        progress=lambda item: print(json.dumps({"progress": item}, ensure_ascii=False), flush=True),
    )
    atomic_write_json(args.output_json, result)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
