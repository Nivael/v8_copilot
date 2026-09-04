"""Materialize bounded, point-in-time public chip proxies for current ST members."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from data_refresh import TushareHttpClient
from p8_research import P8ResearchRepository, build_run, canonical_json, content_id
from settings import DATA_ROOT, MARKET_CONTEXT_DB, P8_RESEARCH_DB


CONTRACT_VERSION = "p8_chip_proxy_v1"
DEFAULT_CACHE_DIR = DATA_ROOT / "local_data/v8_copilot/p8_chip_proxy_cache"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ChipProxyRecord(StrictModel):
    record_id: str = Field(pattern=r"^P8CP-[A-F0-9]{20}$")
    symbol: str = Field(pattern=r"^\d{6}$")
    available_as_of: str
    holder_status: Literal["observed", "unknown"]
    holder_num: float | None = None
    prior_holder_num: float | None = None
    holder_change_pct: float | None = None
    holder_latest_announcement_date: str = ""
    top_list_status: Literal["triggered", "not_triggered_in_complete_cross_section", "unknown"]
    top_list_net_amount: float | None = None
    top_institution_status: Literal["reported", "not_reported_in_complete_cross_section", "unknown"]
    top_institution_net_buy: float | None = None
    block_trade_status: Literal["reported", "none_in_complete_cross_section", "unknown"]
    block_trade_count: int | None = None
    block_trade_amount: float | None = None
    block_trade_vwap: float | None = None
    margin_status: Literal["reported", "not_covered_or_missing", "unknown"]
    margin_balance: float | None = None
    financing_purchase: float | None = None
    source_status: dict[str, str]
    source_row_digests: dict[str, str]
    evidence_status: Literal["derived_point_in_time", "partial", "unknown"]
    not_fund_flow: Literal[True] = True
    not_a_trading_signal: Literal[True] = True


class ChipMaterializationResult(StrictModel):
    run_id: str
    as_of: str
    member_count: int
    record_count: int
    holder_observed_count: int
    top_list_trigger_count: int
    top_institution_reported_count: int
    block_trade_reported_count: int
    margin_reported_count: int
    provider_request_count: int
    cache_hit_count: int
    failed_request_count: int
    records: list[ChipProxyRecord]


_thread_local = threading.local()


def _client() -> TushareHttpClient:
    client = getattr(_thread_local, "client", None)
    if client is None:
        client = TushareHttpClient()
        _thread_local.client = client
    return client


def _compact(value: Any) -> str:
    match = re.match(r"(\d{6})", str(value or ""))
    return match.group(1) if match else ""


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _digest_rows(rows: list[dict[str, Any]]) -> str:
    return hashlib.sha256(canonical_json(rows).encode("utf-8")).hexdigest()


def _cache_file(cache_dir: Path, endpoint: str, key: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", key)
    return cache_dir / endpoint / f"{safe}.json"


def _cached_call(
    *, cache_dir: Path, endpoint: str, key: str, operation: Any,
) -> tuple[list[dict[str, Any]], bool, str]:
    path = _cache_file(cache_dir, endpoint, key)
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return list(payload["rows"]), True, "complete"
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            pass
    error = ""
    for attempt in range(3):
        try:
            rows = list(operation())
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"rows": rows}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
            return rows, False, "complete"
        except Exception as exc:
            error = f"{type(exc).__name__}:{' '.join(str(exc).split())[:160]}"
            if attempt < 2:
                time.sleep(1.0 + attempt)
    return [], False, f"failed:{error}"


def _members(path: Path, as_of: str) -> list[str]:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        day_row = connection.execute(
            "select max(trade_date) from st_membership_daily where trade_date<=?", (as_of,),
        ).fetchone()
        day = str(day_row[0] or "")
        if not day:
            raise ValueError("没有可用的 point-in-time ST membership")
        return [str(row[0]) for row in connection.execute(
            "select symbol from st_membership_daily where trade_date=? order by symbol", (day,),
        )]


def _one_year_before(day: str) -> str:
    value = date.fromisoformat(day)
    try:
        return value.replace(year=value.year - 1).isoformat()
    except ValueError:
        return value.replace(year=value.year - 1, day=28).isoformat()


def materialize_chip_proxies(
    *, market_context_database: Path, repository: P8ResearchRepository,
    as_of: str, cache_dir: Path, workers: int = 4,
    client_factory: Any = _client,
) -> ChipMaterializationResult:
    members = _members(market_context_database, as_of)
    start = _one_year_before(as_of)
    request_count = 0
    cache_hits = 0
    failures = 0
    holder_rows: dict[str, list[dict[str, Any]]] = {}
    holder_status: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(
                _cached_call, cache_dir=cache_dir, endpoint="stk_holdernumber",
                key=f"{symbol}_{start}_{as_of}",
                operation=lambda symbol=symbol: client_factory().fetch_holder_numbers(
                    symbol=symbol, start_date=start, end_date=as_of,
                ),
            ): symbol for symbol in members
        }
        for future in as_completed(futures):
            symbol = futures[future]
            rows, hit, status = future.result()
            holder_rows[symbol] = rows
            holder_status[symbol] = status
            request_count += int(not hit)
            cache_hits += int(hit)
            failures += int(status.startswith("failed:"))

    endpoint_rows: dict[str, list[dict[str, Any]]] = {}
    endpoint_status: dict[str, str] = {}
    operations = {
        "top_list": lambda: client_factory().fetch_top_list(trade_date=as_of),
        "top_inst": lambda: client_factory().fetch_top_institutions(trade_date=as_of),
        "block_trade": lambda: client_factory().fetch_block_trades(trade_date=as_of),
        "margin_detail": lambda: client_factory().fetch_margin_details(trade_date=as_of),
    }
    for endpoint, operation in operations.items():
        rows, hit, status = _cached_call(
            cache_dir=cache_dir, endpoint=endpoint, key=as_of, operation=operation,
        )
        endpoint_rows[endpoint] = rows
        endpoint_status[endpoint] = status
        request_count += int(not hit)
        cache_hits += int(hit)
        failures += int(status.startswith("failed:"))

    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {
        endpoint: defaultdict(list) for endpoint in operations
    }
    for endpoint, rows in endpoint_rows.items():
        for row in rows:
            symbol = _compact(row.get("ts_code"))
            if symbol in set(members):
                grouped[endpoint][symbol].append(row)

    records: list[ChipProxyRecord] = []
    for symbol in members:
        holder = sorted(
            holder_rows.get(symbol, []),
            key=lambda row: (str(row.get("ann_date") or ""), str(row.get("end_date") or "")),
            reverse=True,
        )
        latest_num = _number(holder[0].get("holder_num")) if holder else None
        prior_num = _number(holder[1].get("holder_num")) if len(holder) > 1 else None
        holder_change = (
            (latest_num / prior_num - 1.0) if latest_num is not None and prior_num not in (None, 0) else None
        )
        top_rows = grouped["top_list"].get(symbol, [])
        institution_rows = grouped["top_inst"].get(symbol, [])
        block_rows = grouped["block_trade"].get(symbol, [])
        margin_rows = grouped["margin_detail"].get(symbol, [])
        complete = {key: value == "complete" for key, value in endpoint_status.items()}
        block_amounts = [(_number(row.get("amount")) or 0.0) for row in block_rows]
        block_volumes = [(_number(row.get("vol")) or 0.0) for row in block_rows]
        vwap_denominator = sum(block_volumes)
        vwap = (
            sum((_number(row.get("price")) or 0.0) * volume for row, volume in zip(block_rows, block_volumes, strict=False)) / vwap_denominator
            if vwap_denominator > 0 else None
        )
        source_status = {
            "stk_holdernumber": holder_status.get(symbol, "unknown"),
            **endpoint_status,
        }
        source_digests = {
            "stk_holdernumber": _digest_rows(holder),
            **{endpoint: _digest_rows(grouped[endpoint].get(symbol, [])) for endpoint in operations},
        }
        known_count = sum(not status.startswith("failed:") for status in source_status.values())
        evidence = "derived_point_in_time" if known_count == len(source_status) else ("partial" if known_count else "unknown")
        identity = {"contract": CONTRACT_VERSION, "symbol": symbol, "as_of": as_of, "source_row_digests": source_digests}
        records.append(ChipProxyRecord(
            record_id=content_id("P8CP", identity), symbol=symbol, available_as_of=as_of,
            holder_status="observed" if latest_num is not None else "unknown",
            holder_num=latest_num, prior_holder_num=prior_num, holder_change_pct=holder_change,
            holder_latest_announcement_date=(
                f"{str(holder[0].get('ann_date'))[:4]}-{str(holder[0].get('ann_date'))[4:6]}-{str(holder[0].get('ann_date'))[6:8]}"
                if holder and len(str(holder[0].get("ann_date") or "")) == 8 else ""
            ),
            top_list_status=("triggered" if top_rows else "not_triggered_in_complete_cross_section" if complete["top_list"] else "unknown"),
            top_list_net_amount=sum((_number(row.get("net_amount")) or 0.0) for row in top_rows) if top_rows else None,
            top_institution_status=("reported" if institution_rows else "not_reported_in_complete_cross_section" if complete["top_inst"] else "unknown"),
            top_institution_net_buy=sum((_number(row.get("net_buy")) or 0.0) for row in institution_rows) if institution_rows else None,
            block_trade_status=("reported" if block_rows else "none_in_complete_cross_section" if complete["block_trade"] else "unknown"),
            block_trade_count=len(block_rows) if complete["block_trade"] else None,
            block_trade_amount=sum(block_amounts) if block_rows else (0.0 if complete["block_trade"] else None),
            block_trade_vwap=vwap,
            margin_status="reported" if margin_rows else "not_covered_or_missing" if complete["margin_detail"] else "unknown",
            margin_balance=sum((_number(row.get("rzrqye")) or 0.0) for row in margin_rows) if margin_rows else None,
            financing_purchase=sum((_number(row.get("rzmre")) or 0.0) for row in margin_rows) if margin_rows else None,
            source_status=source_status, source_row_digests=source_digests,
            evidence_status=evidence,  # type: ignore[arg-type]
        ))
    payloads = [item.model_dump(mode="json") for item in records]
    source_digest = hashlib.sha256(canonical_json([item.source_row_digests for item in records]).encode()).hexdigest()
    run = build_run(
        run_kind="chip_proxies", contract_version=CONTRACT_VERSION,
        start_date=as_of, through=as_of, source_run_ids=[],
        source_digests={"provider_rows": source_digest},
        record_payloads={"chip_proxy": payloads},
    )
    repository.persist(run=run, records={"chip_proxy": payloads})
    return ChipMaterializationResult(
        run_id=run.run_id, as_of=as_of, member_count=len(members), record_count=len(records),
        holder_observed_count=sum(item.holder_status == "observed" for item in records),
        top_list_trigger_count=sum(item.top_list_status == "triggered" for item in records),
        top_institution_reported_count=sum(item.top_institution_status == "reported" for item in records),
        block_trade_reported_count=sum(item.block_trade_status == "reported" for item in records),
        margin_reported_count=sum(item.margin_status == "reported" for item in records),
        provider_request_count=request_count, cache_hit_count=cache_hits,
        failed_request_count=failures, records=records,
    )


def _load_env_file(path: Path | None) -> None:
    if path is None:
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in {"TUSHARE_TOKEN", "TUSHARE_HTTP_URL"}:
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--market-context-database", type=Path, default=MARKET_CONTEXT_DB)
    parser.add_argument("--repository", type=Path, default=P8_RESEARCH_DB)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--allow-provider", action="store_true")
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    if not args.allow_provider:
        parser.error("真实 provider 读取必须显式传 --allow-provider")
    date.fromisoformat(args.as_of)
    _load_env_file(args.env_file)
    result = materialize_chip_proxies(
        market_context_database=args.market_context_database,
        repository=P8ResearchRepository(args.repository), as_of=args.as_of,
        cache_dir=args.cache_dir, workers=args.workers,
    )
    payload = result.model_dump(mode="json")
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "records"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
