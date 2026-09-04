"""Backfill a scoped qfq overlay for historical ST members missing early coverage."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from data_refresh import TushareHttpClient, TusharePriceBatch, atomic_write_json
from p8_research import canonical_json
from settings import DATA_ROOT, MARKET_CONTEXT_DB, P8_QFQ_DB


CONTRACT_VERSION = "v8_p8_qfq_overlay_v1"
START_DATE = "2021-03-17"
THROUGH = "2026-09-03"
DEFAULT_BASE_DB = DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"
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


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.executescript("""
        create table if not exists daily_prices (
            symbol text not null, trade_date text not null, adjust text not null,
            open real, high real, low real, close real, volume real, amount real,
            amplitude real, pct_change real, change_amount real, turnover_rate real,
            source text not null, fetched_at text not null default current_timestamp,
            primary key(symbol,trade_date,adjust)
        );
        create table if not exists qfq_backfill_checkpoints (
            symbol text primary key, status text not null, start_date text not null,
            through text not null, row_count integer not null, latest_adj_factor real,
            content_digest text not null, error text not null,
            updated_at text not null default current_timestamp
        );
    """)
    return connection


def missing_prefix_symbols(
    *, base_database: Path, market_context_database: Path,
) -> list[tuple[str, str]]:
    with sqlite3.connect(f"file:{market_context_database}?mode=ro", uri=True) as connection:
        membership_min = dict(connection.execute(
            "select symbol,min(trade_date) from st_membership_daily "
            "where trade_date between '2021-03-17' and '2025-12-31' group by symbol"
        ))
    with sqlite3.connect(f"file:{base_database}?mode=ro", uri=True) as connection:
        qfq_min = dict(connection.execute(
            "select symbol,min(trade_date) from daily_prices where adjust='qfq' group by symbol"
        ))
    return sorted(
        (str(symbol), str(start)) for symbol, start in membership_min.items()
        if str(qfq_min.get(symbol) or "9999-12-31") > str(start)
    )


def _fetch(
    *, symbol: str, start: str, attempts: int,
    client_factory: Callable[[], TushareHttpClient],
) -> tuple[str, str, TusharePriceBatch | None, str]:
    error = ""
    for attempt in range(max(1, attempts)):
        try:
            return symbol, start, client_factory().fetch_qfq(
                symbol=symbol, start_date=start, end_date=THROUGH,
            ), "complete"
        except Exception as exc:
            error = f"{type(exc).__name__}:{' '.join(str(exc).split())[:200]}"
            if attempt + 1 < max(1, attempts):
                time.sleep(float(2 ** attempt))
    return symbol, start, None, f"failed:{error}"


def _persist_batch(connection: sqlite3.Connection, symbol: str, start: str, batch: TusharePriceBatch) -> None:
    rows = batch.rows
    connection.executemany(
        "insert into daily_prices(symbol,trade_date,adjust,open,high,low,close,volume,amount,"
        "amplitude,pct_change,change_amount,turnover_rate,source) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "on conflict(symbol,trade_date,adjust) do update set open=excluded.open,high=excluded.high,"
        "low=excluded.low,close=excluded.close,volume=excluded.volume,amount=excluded.amount,"
        "pct_change=excluded.pct_change,change_amount=excluded.change_amount,source=excluded.source,"
        "fetched_at=current_timestamp",
        [(
            symbol, item["trade_date"], "qfq", item.get("open"), item.get("high"),
            item.get("low"), item.get("close"), item.get("volume"), item.get("amount"),
            item.get("amplitude"), item.get("pct_change"), item.get("change_amount"),
            item.get("turnover_rate"), item.get("source") or "tushare:daily+adj_factor:qfq",
        ) for item in rows],
    )
    digest = hashlib.sha256(canonical_json(rows).encode()).hexdigest()
    connection.execute(
        "insert into qfq_backfill_checkpoints(symbol,status,start_date,through,row_count,latest_adj_factor,content_digest,error) "
        "values(?,?,?,?,?,?,?,?) on conflict(symbol) do update set status=excluded.status,"
        "start_date=excluded.start_date,through=excluded.through,row_count=excluded.row_count,"
        "latest_adj_factor=excluded.latest_adj_factor,content_digest=excluded.content_digest,error='',"
        "updated_at=current_timestamp",
        (symbol, "complete", start, THROUGH, len(rows), batch.latest_adj_factor, digest, ""),
    )


def backfill(
    *, base_database: Path, market_context_database: Path, overlay_database: Path,
    allow_provider: bool, workers: int = 2, attempts: int = 3,
    client_factory: Callable[[], TushareHttpClient] = _client,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if not allow_provider:
        raise ValueError("qfq overlay 回填必须显式传 --allow-provider")
    planned = missing_prefix_symbols(
        base_database=base_database, market_context_database=market_context_database,
    )
    with _connect(overlay_database) as connection:
        complete = {
            str(row[0]) for row in connection.execute(
                "select symbol from qfq_backfill_checkpoints where status='complete' and through=?",
                (THROUGH,),
            )
        }
    targets = [(symbol, start) for symbol, start in planned if symbol not in complete]
    failures: dict[str, str] = {}
    completed = 0
    with _connect(overlay_database) as connection, ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(
                _fetch, symbol=symbol, start=start, attempts=attempts,
                client_factory=client_factory,
            ): symbol for symbol, start in targets
        }
        for future in as_completed(futures):
            symbol, start, batch, status = future.result()
            if batch is None:
                failures[symbol] = status
                connection.execute(
                    "insert into qfq_backfill_checkpoints(symbol,status,start_date,through,row_count,latest_adj_factor,content_digest,error) "
                    "values(?,?,?,?,?,?,?,?) on conflict(symbol) do update set status=excluded.status,error=excluded.error,updated_at=current_timestamp",
                    (symbol, "failed", start, THROUGH, 0, None, "", status),
                )
            else:
                _persist_batch(connection, symbol, start, batch)
            connection.commit()
            completed += 1
            if progress:
                progress({"completed": completed, "total": len(targets), "symbol": symbol, "status": status})
    with sqlite3.connect(f"file:{overlay_database}?mode=ro", uri=True) as connection:
        row_count, company_count = connection.execute(
            "select count(*),count(distinct symbol) from daily_prices where adjust='qfq'"
        ).fetchone()
    return {
        "contract_version": CONTRACT_VERSION, "start_date": START_DATE, "through": THROUGH,
        "planned_symbol_count": len(planned), "requested_symbol_count": len(targets),
        "checkpoint_skip_count": len(planned) - len(targets),
        "failed_symbol_count": len(failures), "failed_symbols": sorted(failures),
        "row_count": int(row_count), "company_count": int(company_count),
        "status": "complete" if not failures else "partial",
        "outcomes_read": False, "returns_computed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-database", type=Path, default=DEFAULT_BASE_DB)
    parser.add_argument("--market-context-database", type=Path, default=MARKET_CONTEXT_DB)
    parser.add_argument("--overlay-database", type=Path, default=P8_QFQ_DB)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--allow-provider", action="store_true")
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    _load_env(args.env_file)
    result = backfill(
        base_database=args.base_database, market_context_database=args.market_context_database,
        overlay_database=args.overlay_database, allow_provider=args.allow_provider,
        workers=args.workers, attempts=args.attempts,
        progress=lambda item: print(json.dumps({"progress": item}, ensure_ascii=False), flush=True),
    )
    atomic_write_json(args.output_json, result)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
