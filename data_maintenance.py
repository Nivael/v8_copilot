"""CLI boundary for the dedicated ST data-maintenance task.

Unlike the answer service, this command is explicitly allowed to fetch current
facts and update canonical inputs.  Every pull is resumable and audited.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Callable, TypeVar

from answer_engine import BASE_DB
from data_refresh import (
    AnnouncementRefreshService,
    CninfoHttpClient,
    MaintenanceStateRepository,
    PriceRefreshService,
    TushareHttpClient,
    atomic_write_json,
    validate_announcement_row,
)
from freshness_manifest import (
    FreshnessManifest,
    build_freshness_manifest,
    load_freshness_manifest,
    write_freshness_manifest,
)
from market_context import (
    PROVIDER_BENCHMARKS,
    HistoricalStMembershipService,
    MarketContextRepository,
    MarketContextService,
    build_market_context_manifest,
    write_market_context_manifest,
)
from maintenance_plan import build_maintenance_plan
from market_factors import (
    MarketFactorRepository,
    MarketFactorService,
    build_market_factor_manifest,
    write_market_factor_manifest_set,
)
from settings import (
    ANNOUNCEMENT_REFRESH_DIR,
    DATA_MAINTENANCE_DB,
    FRESHNESS_MANIFEST_PATH,
    MARKET_CONTEXT_DB,
    MARKET_CONTEXT_MANIFEST_PATH,
    MARKET_FACTOR_DB,
    MARKET_FACTOR_MANIFEST_DIR,
    MARKET_FACTOR_MANIFEST_PATH,
    ST_UNIVERSE_DIR,
)
from universe import StUniverseRepository, StUniverseService, StUniverseSnapshot


def _promote_announcement(input_path: Path, symbol: str, checked_through: str = "") -> Path:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if payload.get("source") != "cninfo":
        raise ValueError("公告增量必须来自 cninfo")
    if str(payload.get("symbol")) != symbol:
        raise ValueError("公告增量 symbol 与目标不一致")
    rows = payload.get("records")
    if not isinstance(rows, list):
        raise ValueError("公告增量缺 records list")
    seen: set[str] = set()
    incoming: dict[str, dict] = {}
    for row in rows:
        normalized = validate_announcement_row(row, symbol)
        announcement_id = normalized["announcement_id"]
        if announcement_id in seen:
            raise ValueError(f"公告增量 ID 重复: {announcement_id}")
        seen.add(announcement_id)
        incoming[announcement_id] = normalized
    destination = ANNOUNCEMENT_REFRESH_DIR / f"{symbol}.json"
    existing: dict[str, dict] = {}
    existing_payload: dict = {}
    if destination.is_file():
        existing_payload = json.loads(destination.read_text(encoding="utf-8"))
        if existing_payload.get("source") != "cninfo" or str(existing_payload.get("symbol")) != symbol:
            raise ValueError("现有公告 overlay 来源或 symbol 非法")
        for row in existing_payload.get("records") or []:
            normalized = validate_announcement_row(row, symbol)
            existing[normalized["announcement_id"]] = normalized
    for announcement_id, row in incoming.items():
        previous = existing.get(announcement_id, {})
        candidate = {**previous, **row}
        if previous.get("body_text") and not row.get("body_text"):
            candidate["body_text"] = previous["body_text"]
        existing[announcement_id] = candidate
    merged = sorted(
        existing.values(),
        key=lambda row: (row["announcement_date"], row["announcement_id"]),
        reverse=True,
    )
    from datetime import datetime, timezone

    checked = checked_through or str(payload.get("checked_through") or "")[:10]
    if not checked:
        checked = datetime.fromtimestamp(input_path.stat().st_mtime).date().isoformat()
    promoted = {
        **{key: value for key, value in existing_payload.items() if key not in {"records", "count"}},
        **{key: value for key, value in payload.items() if key not in {"records", "count"}},
        "symbol": symbol,
        "source": "cninfo",
        "count": len(merged),
        "include_body": False,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "checked_through": checked,
        "records": merged,
    }
    atomic_write_json(destination, promoted)
    return destination


def _load_env_file(path: Path | None) -> None:
    if path is None:
        return
    import os

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _print_manifest(manifest: FreshnessManifest, output: Path) -> None:
    print(json.dumps({
        "manifest_id": manifest.manifest_id,
        "output": str(output),
        "overall_status": manifest.overall_status,
        "sources": {
            source.source_id: {
                "status": source.status,
                "as_of": source.as_of,
                "checked_at": source.checked_at,
            }
            for source in manifest.sources
        },
        "blocking_gaps": manifest.blocking_gaps,
        "coverage_gaps": manifest.coverage_gaps,
    }, ensure_ascii=False, indent=2))


def _resolve_scope(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> tuple[list[str], StUniverseSnapshot | None]:
    symbols = set(getattr(args, "symbol", []) or [])
    snapshot = None
    snapshot_path = getattr(args, "universe_snapshot", None)
    if getattr(args, "universe_current", False):
        snapshot = StUniverseRepository(ST_UNIVERSE_DIR).load_current()
        if snapshot is None:
            parser.error("尚无 current ST universe；先运行 sync-universe")
        symbols.update(snapshot.symbols)
    if snapshot_path:
        loaded = StUniverseRepository.load(snapshot_path)
        if snapshot is not None and snapshot.snapshot_id != loaded.snapshot_id:
            parser.error("不能同时指定两个不同的 universe snapshot")
        snapshot = loaded
        symbols.update(loaded.symbols)
    for symbol in symbols:
        if len(symbol) != 6 or not symbol.isdigit():
            parser.error("--symbol 必须是六位股票代码")
    if not symbols:
        parser.error("至少指定一个 --symbol、--universe-current 或 --universe-snapshot")
    return sorted(symbols), snapshot


def _resolve_symbols(args: argparse.Namespace, parser: argparse.ArgumentParser) -> list[str]:
    return _resolve_scope(args, parser)[0]


def _validate_bootstrap_scope(
    *, symbols: list[str], price_start: str, announcement_start: str
) -> None:
    if len(symbols) > 1 and (price_start or announcement_start):
        raise ValueError(
            "多股票批次禁止共用 --price-start/--announcement-start；"
            "无基线股票必须逐股 bootstrap"
        )


def _slice_batch(symbols: list[str], *, offset: int, size: int) -> list[str]:
    if offset < 0 or size < 0:
        raise ValueError("--batch-offset/--batch-size 不能为负数")
    if offset >= len(symbols):
        return []
    return symbols[offset:] if size == 0 else symbols[offset:offset + size]


def _progress(*, completed: int, total: int, source_id: str, symbol: str, status: str) -> None:
    print(json.dumps({
        "progress": {"completed": completed, "total": total},
        "source_id": source_id,
        "symbol": symbol,
        "status": status,
    }, ensure_ascii=False), flush=True)


T = TypeVar("T")


def _with_retries(
    operation: Callable[[], T], *, max_attempts: int, backoff_seconds: float
) -> T:
    if max_attempts < 1:
        raise ValueError("--max-attempts 必须至少为 1")
    if backoff_seconds < 0:
        raise ValueError("--retry-backoff-seconds 不能为负数")
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except Exception:
            if attempt == max_attempts:
                raise
            time.sleep(backoff_seconds * (2 ** (attempt - 1)))
    raise AssertionError("unreachable")


def main() -> int:
    parser = argparse.ArgumentParser(description="ST Research data maintenance boundary")
    sub = parser.add_subparsers(dest="command", required=True)

    promote = sub.add_parser("promote-announcements")
    promote.add_argument("--input", type=Path, required=True)
    promote.add_argument("--symbol", required=True)
    promote.add_argument("--checked-through", default="")

    refresh = sub.add_parser("refresh")
    refresh.add_argument("--symbol", action="append", default=[])
    refresh.add_argument("--universe-current", action="store_true")
    refresh.add_argument("--universe-snapshot", type=Path)
    refresh.add_argument("--price-through", required=True)
    refresh.add_argument("--announcement-through", required=True)
    refresh.add_argument("--price-start", default="")
    refresh.add_argument("--announcement-start", default="")
    refresh.add_argument("--price-overlap-days", type=int, default=7)
    refresh.add_argument("--announcement-overlap-days", type=int, default=14)
    refresh.add_argument("--env-file", type=Path)
    refresh.add_argument("--force", action="store_true")
    refresh.add_argument("--skip-prices", action="store_true")
    refresh.add_argument("--skip-announcements", action="store_true")
    refresh.add_argument("--batch-offset", type=int, default=0)
    refresh.add_argument("--batch-size", type=int, default=0)
    refresh.add_argument("--request-delay-seconds", type=float, default=0.0)
    refresh.add_argument("--max-attempts", type=int, default=3)
    refresh.add_argument("--retry-backoff-seconds", type=float, default=1.0)
    refresh.add_argument("--output", type=Path)

    checkpoints = sub.add_parser("checkpoints")
    checkpoints.add_argument("--state-db", type=Path, default=DATA_MAINTENANCE_DB)

    manifest = sub.add_parser("manifest")
    manifest.add_argument("--expected-price-through", default="")
    manifest.add_argument("--expected-announcement-checked-through", default="")
    manifest.add_argument("--symbol", action="append", default=[])
    manifest.add_argument("--universe-current", action="store_true")
    manifest.add_argument("--universe-snapshot", type=Path)
    manifest.add_argument("--output", type=Path, default=FRESHNESS_MANIFEST_PATH)
    manifest.add_argument("--require-ready", action="store_true")

    show = sub.add_parser("show")
    show.add_argument("--manifest", type=Path, default=FRESHNESS_MANIFEST_PATH)

    sync_universe = sub.add_parser("sync-universe")
    sync_universe.add_argument("--as-of", required=True)
    sync_universe.add_argument("--env-file", type=Path)
    sync_universe.add_argument("--output-dir", type=Path, default=ST_UNIVERSE_DIR)

    show_universe = sub.add_parser("show-universe")
    show_universe.add_argument("--universe-dir", type=Path, default=ST_UNIVERSE_DIR)

    refresh_benchmarks = sub.add_parser("refresh-benchmarks")
    refresh_benchmarks.add_argument("--start-date", required=True)
    refresh_benchmarks.add_argument("--through", required=True)
    refresh_benchmarks.add_argument("--env-file", type=Path)
    refresh_benchmarks.add_argument("--database", type=Path, default=MARKET_CONTEXT_DB)
    refresh_benchmarks.add_argument(
        "--benchmark-id",
        action="append",
        choices=[item.benchmark_id for item in PROVIDER_BENCHMARKS],
        default=[],
        help="可重复；省略时刷新 pool 中全部 provider benchmark",
    )

    backfill_membership = sub.add_parser("backfill-membership")
    backfill_membership.add_argument("--start-date", required=True)
    backfill_membership.add_argument("--through", required=True)
    backfill_membership.add_argument("--page-size", type=int, default=1000)
    backfill_membership.add_argument("--max-pages", type=int, default=10000)
    backfill_membership.add_argument("--env-file", type=Path)
    backfill_membership.add_argument("--database", type=Path, default=MARKET_CONTEXT_DB)

    repair_membership = sub.add_parser("repair-membership-gaps")
    repair_membership.add_argument("--start-date", required=True)
    repair_membership.add_argument("--through", required=True)
    repair_membership.add_argument("--env-file", type=Path)
    repair_membership.add_argument("--database", type=Path, default=MARKET_CONTEXT_DB)

    materialize_st_index = sub.add_parser("materialize-st-index")
    materialize_st_index.add_argument("--start-date", required=True)
    materialize_st_index.add_argument("--through", required=True)
    materialize_st_index.add_argument("--database", type=Path, default=MARKET_CONTEXT_DB)
    materialize_st_index.add_argument(
        "--manifest", type=Path, default=MARKET_CONTEXT_MANIFEST_PATH
    )

    market_status = sub.add_parser("market-context-status")
    market_status.add_argument("--database", type=Path, default=MARKET_CONTEXT_DB)
    market_status.add_argument(
        "--manifest", type=Path, default=MARKET_CONTEXT_MANIFEST_PATH
    )
    market_status.add_argument("--coverage-threshold", type=float, default=0.95)

    refresh_market_caps = sub.add_parser("refresh-market-caps")
    refresh_market_caps.add_argument("--as-of", required=True)
    refresh_market_caps.add_argument("--env-file", type=Path)
    refresh_market_caps.add_argument(
        "--database", type=Path, default=MARKET_FACTOR_DB
    )
    refresh_market_caps.add_argument(
        "--market-context-database", type=Path, default=MARKET_CONTEXT_DB
    )
    refresh_market_caps.add_argument(
        "--manifest", type=Path, default=MARKET_FACTOR_MANIFEST_PATH
    )
    refresh_market_caps.add_argument(
        "--manifest-directory", type=Path, default=MARKET_FACTOR_MANIFEST_DIR
    )
    refresh_market_caps.add_argument(
        "--coverage-threshold", type=float, default=0.95
    )

    market_factor_status = sub.add_parser("market-factor-status")
    market_factor_status.add_argument("--as-of", required=True)
    market_factor_status.add_argument(
        "--database", type=Path, default=MARKET_FACTOR_DB
    )
    market_factor_status.add_argument(
        "--manifest", type=Path, default=MARKET_FACTOR_MANIFEST_PATH
    )
    market_factor_status.add_argument(
        "--manifest-directory", type=Path, default=MARKET_FACTOR_MANIFEST_DIR
    )
    market_factor_status.add_argument(
        "--coverage-threshold", type=float, default=0.95
    )

    plan = sub.add_parser("plan")
    plan.add_argument("--symbol", action="append", default=[])
    plan.add_argument("--universe-current", action="store_true")
    plan.add_argument("--universe-snapshot", type=Path)
    plan.add_argument("--price-through", required=True)
    plan.add_argument("--announcement-through", required=True)

    args = parser.parse_args()
    if args.command == "promote-announcements":
        if len(args.symbol) != 6 or not args.symbol.isdigit():
            parser.error("--symbol 必须是六位股票代码")
        destination = _promote_announcement(args.input, args.symbol, args.checked_through)
        print(json.dumps({"promoted": str(destination), "symbol": args.symbol}, ensure_ascii=False))
        return 0
    if args.command == "checkpoints":
        rows = MaintenanceStateRepository(args.state_db).list()
        print(json.dumps([row.model_dump(mode="json") for row in rows], ensure_ascii=False, indent=2))
        return 0
    if args.command == "sync-universe":
        _load_env_file(args.env_file)
        service = StUniverseService(
            provider=TushareHttpClient(),
            repository=StUniverseRepository(args.output_dir),
        )
        snapshot, destination = service.sync(as_of=args.as_of)
        print(json.dumps({
            "snapshot_id": snapshot.snapshot_id,
            "as_of": snapshot.as_of,
            "member_count": snapshot.member_count,
            "added_symbols": snapshot.added_symbols,
            "removed_symbols": snapshot.removed_symbols,
            "snapshot": str(destination),
        }, ensure_ascii=False, indent=2))
        return 0
    if args.command == "show-universe":
        current = StUniverseRepository(args.universe_dir).load_current()
        if current is None:
            parser.error("尚无 current ST universe")
        print(json.dumps(current.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 0
    if args.command == "refresh-benchmarks":
        _load_env_file(args.env_file)
        repository = MarketContextRepository(args.database)
        service = MarketContextService(
            provider=TushareHttpClient(), repository=repository,
        )
        selected = set(args.benchmark_id)
        definitions = [
            item for item in PROVIDER_BENCHMARKS
            if not selected or item.benchmark_id in selected
        ]
        summaries = []
        for definition in definitions:
            points = service.refresh_provider_index(
                definition=definition,
                start_date=args.start_date,
                end_date=args.through,
            )
            lower, upper, count = repository.bounds(definition.benchmark_id)
            summaries.append({
                "benchmark_id": definition.benchmark_id,
                "provider_code": definition.provider_code,
                "rows_seen": len(points),
                "stored_bounds": {"start": lower, "end": upper, "count": count},
            })
        print(json.dumps({
            "benchmarks": summaries,
            "database": str(args.database),
        }, ensure_ascii=False, indent=2))
        return 0
    if args.command == "backfill-membership":
        _load_env_file(args.env_file)
        repository = MarketContextRepository(args.database)
        result = HistoricalStMembershipService(
            provider=TushareHttpClient(), repository=repository,
        ).backfill(
            start_date=args.start_date,
            end_date=args.through,
            page_size=args.page_size,
            max_pages=args.max_pages,
            progress=lambda payload: print(
                json.dumps({"membership_progress": payload}, ensure_ascii=False),
                flush=True,
            ),
        )
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 0 if result.status == "complete" else 2
    if args.command == "repair-membership-gaps":
        _load_env_file(args.env_file)
        result = HistoricalStMembershipService(
            provider=TushareHttpClient(),
            repository=MarketContextRepository(args.database),
        ).repair_trading_date_gaps(
            start_date=args.start_date,
            end_date=args.through,
            progress=lambda payload: print(
                json.dumps({"membership_repair": payload}, ensure_ascii=False),
                flush=True,
            ),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result["unresolved_dates"] else 0
    if args.command == "materialize-st-index":
        repository = MarketContextRepository(args.database)
        points = repository.materialize_st_equal_weight(
            price_database=BASE_DB,
            start_date=args.start_date,
            end_date=args.through,
        )
        context = build_market_context_manifest(repository=repository)
        write_market_context_manifest(context, args.manifest)
        print(json.dumps({
            "benchmark_id": "st_equal_weight_v1",
            "rows_written": len(points),
            "start": points[0].trade_date,
            "end": points[-1].trade_date,
            "minimum_coverage": min(
                point.coverage_ratio for point in points
                if point.coverage_ratio is not None
            ),
            "manifest_id": context["manifest_id"],
            "manifest": str(args.manifest),
        }, ensure_ascii=False, indent=2))
        return 0
    if args.command == "market-context-status":
        context = build_market_context_manifest(
            repository=MarketContextRepository(args.database),
            coverage_threshold=args.coverage_threshold,
        )
        write_market_context_manifest(context, args.manifest)
        print(json.dumps(context, ensure_ascii=False, indent=2))
        return 0
    if args.command == "refresh-market-caps":
        _load_env_file(args.env_file)
        repository = MarketFactorRepository(args.database)
        snapshot = MarketFactorService(
            provider=TushareHttpClient(),
            repository=repository,
            market_context_database=args.market_context_database,
        ).refresh(as_of=args.as_of)
        factor_manifest = build_market_factor_manifest(
            repository=repository,
            snapshot_id=snapshot.snapshot_id,
            coverage_threshold=args.coverage_threshold,
        )
        dated_manifest = write_market_factor_manifest_set(
            factor_manifest,
            current_path=args.manifest,
            manifest_directory=args.manifest_directory,
        )
        print(json.dumps({
            "snapshot_id": snapshot.snapshot_id,
            "factor_date": snapshot.trade_date,
            "membership_count": snapshot.membership_count,
            "valid_total_market_value_count": (
                snapshot.valid_total_market_value_count
            ),
            "coverage_ratio": snapshot.coverage_ratio,
            "manifest_id": factor_manifest["manifest_id"],
            "status": factor_manifest["status"],
            "blocking_gaps": factor_manifest["blocking_gaps"],
            "database": str(args.database),
            "manifest": str(args.manifest),
            "dated_manifest": str(dated_manifest),
        }, ensure_ascii=False, indent=2))
        return 0 if factor_manifest["status"] == "ready" else 2
    if args.command == "market-factor-status":
        repository = MarketFactorRepository(args.database)
        snapshot = repository.latest_snapshot(args.as_of)
        if snapshot is None:
            parser.error(f"{args.as_of} 尚无 point-in-time 市值快照")
        factor_manifest = build_market_factor_manifest(
            repository=repository,
            snapshot_id=snapshot.snapshot_id,
            coverage_threshold=args.coverage_threshold,
        )
        write_market_factor_manifest_set(
            factor_manifest,
            current_path=args.manifest,
            manifest_directory=args.manifest_directory,
        )
        print(json.dumps(factor_manifest, ensure_ascii=False, indent=2))
        return 0 if factor_manifest["status"] == "ready" else 2
    if args.command == "plan":
        symbols, snapshot = _resolve_scope(args, parser)
        current = build_maintenance_plan(
            database=BASE_DB,
            announcement_refresh_dir=ANNOUNCEMENT_REFRESH_DIR,
            state_database=DATA_MAINTENANCE_DB,
            symbols=symbols,
            price_through=args.price_through,
            announcement_through=args.announcement_through,
            universe_snapshot_id=getattr(snapshot, "snapshot_id", ""),
            universe_as_of=getattr(snapshot, "as_of", ""),
        )
        print(json.dumps(current.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 2 if current.warnings else 0
    if args.command == "refresh":
        full_symbols, universe_snapshot = _resolve_scope(args, parser)
        try:
            symbols = _slice_batch(
                full_symbols, offset=args.batch_offset, size=args.batch_size
            )
        except ValueError as exc:
            parser.error(str(exc))
        if not symbols:
            parser.error("批次范围为空")
        if args.request_delay_seconds < 0:
            parser.error("--request-delay-seconds 不能为负数")
        if args.max_attempts < 1:
            parser.error("--max-attempts 必须至少为 1")
        if args.retry_backoff_seconds < 0:
            parser.error("--retry-backoff-seconds 不能为负数")
        if args.skip_prices and args.skip_announcements:
            parser.error("不能同时跳过价格和公告")
        try:
            _validate_bootstrap_scope(
                symbols=symbols,
                price_start=args.price_start,
                announcement_start=args.announcement_start,
            )
        except ValueError as exc:
            parser.error(str(exc))
        _load_env_file(args.env_file)
        state = MaintenanceStateRepository(DATA_MAINTENANCE_DB)
        results: list[dict] = []
        failures: list[dict] = []
        price_service = None
        if not args.skip_prices:
            try:
                price_service = PriceRefreshService(
                    database=BASE_DB, state=state, provider=TushareHttpClient(),
                )
            except Exception as exc:
                failures.extend({
                    "source_id": "tushare_daily_qfq", "symbol": symbol,
                    "error": f"{type(exc).__name__}: {exc}",
                } for symbol in symbols)
        announcement_service = AnnouncementRefreshService(
            refresh_dir=ANNOUNCEMENT_REFRESH_DIR, base_database=BASE_DB,
            state=state, provider=CninfoHttpClient(),
        ) if not args.skip_announcements else None
        total_operations = len(symbols) * (
            int(price_service is not None) + int(announcement_service is not None)
        )
        completed_operations = 0
        for symbol in symbols:
            if price_service is not None:
                try:
                    result = _with_retries(
                        lambda: price_service.refresh(
                            symbol=symbol, through=args.price_through,
                            start_date=args.price_start,
                            overlap_days=args.price_overlap_days, force=args.force,
                        ),
                        max_attempts=args.max_attempts,
                        backoff_seconds=args.retry_backoff_seconds,
                    )
                    results.append(result.model_dump(mode="json"))
                    completed_operations += 1
                    _progress(
                        completed=completed_operations, total=total_operations,
                        source_id=result.source_id, symbol=symbol, status=result.status,
                    )
                except Exception as exc:
                    failures.append({
                        "source_id": "tushare_daily_qfq", "symbol": symbol,
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                    completed_operations += 1
                    _progress(
                        completed=completed_operations, total=total_operations,
                        source_id="tushare_daily_qfq", symbol=symbol, status="failed",
                    )
                if args.request_delay_seconds:
                    time.sleep(args.request_delay_seconds)
            if announcement_service is not None:
                try:
                    result = _with_retries(
                        lambda: announcement_service.refresh(
                            symbol=symbol, through=args.announcement_through,
                            start_date=args.announcement_start,
                            overlap_days=args.announcement_overlap_days, force=args.force,
                        ),
                        max_attempts=args.max_attempts,
                        backoff_seconds=args.retry_backoff_seconds,
                    )
                    results.append(result.model_dump(mode="json"))
                    completed_operations += 1
                    _progress(
                        completed=completed_operations, total=total_operations,
                        source_id=result.source_id, symbol=symbol, status=result.status,
                    )
                except Exception as exc:
                    failures.append({
                        "source_id": "cninfo_announcements", "symbol": symbol,
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                    completed_operations += 1
                    _progress(
                        completed=completed_operations, total=total_operations,
                        source_id="cninfo_announcements", symbol=symbol, status="failed",
                    )
                if args.request_delay_seconds:
                    time.sleep(args.request_delay_seconds)
        current = build_freshness_manifest(
            expected_price_through=args.price_through,
            expected_announcement_checked_through=args.announcement_through,
            research_symbols=symbols,
            universe_snapshot=universe_snapshot,
        )
        output = args.output
        if output is None:
            if len(symbols) == len(full_symbols):
                output = FRESHNESS_MANIFEST_PATH
            else:
                batch_end = args.batch_offset + len(symbols) - 1
                output = FRESHNESS_MANIFEST_PATH.with_name(
                    f"freshness_manifest_batch_{args.batch_offset}_{batch_end}.json"
                )
        write_freshness_manifest(current, output)
        print(json.dumps({
            "results": results, "failures": failures,
            "manifest_id": current.manifest_id, "overall_status": current.overall_status,
            "scope": {
                "full_symbol_count": len(full_symbols),
                "batch_offset": args.batch_offset,
                "batch_size": len(symbols),
                "request_delay_seconds": args.request_delay_seconds,
                "max_attempts": args.max_attempts,
                "output": str(output),
            },
            "blocking_gaps": current.blocking_gaps, "coverage_gaps": current.coverage_gaps,
        }, ensure_ascii=False, indent=2))
        return 2 if failures or current.overall_status != "ready" else 0
    if args.command == "show":
        current = load_freshness_manifest(args.manifest)
        _print_manifest(current, args.manifest)
        return 0
    manifest_symbols = list(args.symbol)
    universe_snapshot = None
    if args.universe_current or args.universe_snapshot:
        manifest_symbols, universe_snapshot = _resolve_scope(args, parser)
    current = build_freshness_manifest(
        expected_price_through=args.expected_price_through,
        expected_announcement_checked_through=args.expected_announcement_checked_through,
        research_symbols=manifest_symbols,
        universe_snapshot=universe_snapshot,
    )
    write_freshness_manifest(current, args.output)
    _print_manifest(current, args.output)
    if args.require_ready and current.overall_status != "ready":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
