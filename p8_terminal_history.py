"""Backfill provider-reported delisting endpoints for historical ST members."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable

from data_refresh import TushareHttpClient, atomic_write_json
from p8_research import P8ResearchRepository, build_run, canonical_json, content_id
from settings import DATA_ROOT, MARKET_CONTEXT_DB, P8_RESEARCH_DB


CONTRACT_VERSION = "v8_p8_terminal_history_v1"
START_DATE = "2021-03-17"
THROUGH = "2025-12-31"
DEFAULT_CACHE = DATA_ROOT / "local_data/v8_copilot/p8_terminal_history/stock_basic_D.json"


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
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}" if len(raw) == 8 and raw.isdigit() else ""


def _historical_symbols(path: Path) -> set[str]:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        return {
            str(row[0]) for row in connection.execute(
                "select distinct symbol from st_membership_daily "
                "where trade_date between ? and ?", (START_DATE, THROUGH),
            )
        }


def _records(rows: list[dict[str, Any]], *, historical_symbols: set[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        symbol = _compact(row.get("symbol") or row.get("ts_code"))
        delist_date = _iso(row.get("delist_date"))
        if symbol not in historical_symbols or not delist_date:
            continue
        source = {
            "ts_code": str(row.get("ts_code") or ""),
            "symbol": symbol,
            "name": str(row.get("name") or ""),
            "market": str(row.get("market") or ""),
            "exchange": str(row.get("exchange") or ""),
            "list_status": str(row.get("list_status") or ""),
            "list_date": str(row.get("list_date") or ""),
            "delist_date": str(row.get("delist_date") or ""),
        }
        identity = {
            "contract": CONTRACT_VERSION,
            "symbol": symbol,
            "delist_date": delist_date,
            "source": source,
        }
        result.append({
            "record_id": content_id("P8TERM", identity),
            "symbol": symbol,
            "available_as_of": delist_date,
            "delist_date": delist_date,
            "list_date": _iso(row.get("list_date")),
            "list_status": "D",
            "source": "tushare:stock_basic",
            "source_row_digest": hashlib.sha256(canonical_json(source).encode()).hexdigest(),
            "evidence_status": "provider_reported_terminal",
            "total_loss_stress": -1.0,
            "not_a_trading_signal": True,
        })
    return sorted(result, key=lambda item: (item["delist_date"], item["symbol"]))


def backfill_terminal_history(
    *, market_context_database: Path, repository: P8ResearchRepository,
    cache_path: Path, allow_provider: bool,
    provider_factory: Callable[[], TushareHttpClient] = TushareHttpClient,
) -> dict[str, Any]:
    if not allow_provider:
        raise ValueError("退市终点回填必须显式传 --allow-provider")
    cache_hit = cache_path.is_file()
    if cache_hit:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        rows = list(payload.get("rows") or [])
    else:
        rows = list(provider_factory().fetch_stock_basics(list_status="D"))
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(cache_path, {"list_status": "D", "rows": rows})
    symbols = _historical_symbols(market_context_database)
    records = _records(rows, historical_symbols=symbols)
    source_digest = hashlib.sha256(canonical_json(rows).encode()).hexdigest()
    run = build_run(
        run_kind="p8_terminal_history_v2",
        contract_version=CONTRACT_VERSION,
        start_date=START_DATE,
        through=THROUGH,
        source_run_ids=[],
        source_digests={"tushare_stock_basic_D": source_digest},
        record_payloads={"p8_terminal_outcome_v2": records},
    )
    repository.persist(run=run, records={"p8_terminal_outcome_v2": records})
    return {
        "contract_version": CONTRACT_VERSION,
        "run_id": run.run_id,
        "status": "complete",
        "provider_request_count": 0 if cache_hit else 1,
        "cache_hit": cache_hit,
        "provider_row_count": len(rows),
        "historical_st_symbol_count": len(symbols),
        "terminal_record_count": len(records),
        "terminal_company_count": len({item["symbol"] for item in records}),
        "by_year": {
            str(year): sum(str(item["delist_date"]).startswith(str(year)) for item in records)
            for year in range(2021, 2027)
        },
        "outcomes_read": True,
        "returns_computed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market-context-database", type=Path, default=MARKET_CONTEXT_DB)
    parser.add_argument("--repository", type=Path, default=P8_RESEARCH_DB)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--allow-provider", action="store_true")
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    _load_env(args.env_file)
    result = backfill_terminal_history(
        market_context_database=args.market_context_database,
        repository=P8ResearchRepository(args.repository),
        cache_path=args.cache,
        allow_provider=args.allow_provider,
    )
    atomic_write_json(args.output_json, result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
