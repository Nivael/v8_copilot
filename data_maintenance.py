"""CLI boundary for the dedicated ST data-maintenance task.

Unlike the answer service, this command is explicitly allowed to fetch current
facts and update canonical inputs.  Every pull is resumable and audited.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

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
from market_context import BROAD_MARKET, MarketContextRepository, MarketContextService
from maintenance_plan import build_maintenance_plan
from settings import (
    ANNOUNCEMENT_REFRESH_DIR,
    DATA_MAINTENANCE_DB,
    FRESHNESS_MANIFEST_PATH,
    MARKET_CONTEXT_DB,
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
    refresh.add_argument("--output", type=Path, default=FRESHNESS_MANIFEST_PATH)

    checkpoints = sub.add_parser("checkpoints")
    checkpoints.add_argument("--state-db", type=Path, default=DATA_MAINTENANCE_DB)

    manifest = sub.add_parser("manifest")
    manifest.add_argument("--expected-price-through", default="")
    manifest.add_argument("--expected-announcement-checked-through", default="")
    manifest.add_argument("--symbol", action="append", default=[])
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
        points = MarketContextService(
            provider=TushareHttpClient(), repository=repository,
        ).refresh_provider_index(
            definition=BROAD_MARKET,
            start_date=args.start_date,
            end_date=args.through,
        )
        lower, upper, count = repository.bounds(BROAD_MARKET.benchmark_id)
        print(json.dumps({
            "benchmark_id": BROAD_MARKET.benchmark_id,
            "rows_seen": len(points),
            "stored_bounds": {"start": lower, "end": upper, "count": count},
            "database": str(args.database),
        }, ensure_ascii=False, indent=2))
        return 0
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
        symbols = _resolve_symbols(args, parser)
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
        for symbol in symbols:
            if price_service is not None:
                try:
                    result = price_service.refresh(
                        symbol=symbol, through=args.price_through,
                        start_date=args.price_start,
                        overlap_days=args.price_overlap_days, force=args.force,
                    )
                    results.append(result.model_dump(mode="json"))
                except Exception as exc:
                    failures.append({
                        "source_id": "tushare_daily_qfq", "symbol": symbol,
                        "error": f"{type(exc).__name__}: {exc}",
                    })
            if announcement_service is not None:
                try:
                    result = announcement_service.refresh(
                        symbol=symbol, through=args.announcement_through,
                        start_date=args.announcement_start,
                        overlap_days=args.announcement_overlap_days, force=args.force,
                    )
                    results.append(result.model_dump(mode="json"))
                except Exception as exc:
                    failures.append({
                        "source_id": "cninfo_announcements", "symbol": symbol,
                        "error": f"{type(exc).__name__}: {exc}",
                    })
        current = build_freshness_manifest(
            expected_price_through=args.price_through,
            expected_announcement_checked_through=args.announcement_through,
            research_symbols=symbols,
        )
        write_freshness_manifest(current, args.output)
        print(json.dumps({
            "results": results, "failures": failures,
            "manifest_id": current.manifest_id, "overall_status": current.overall_status,
            "blocking_gaps": current.blocking_gaps, "coverage_gaps": current.coverage_gaps,
        }, ensure_ascii=False, indent=2))
        return 2 if failures or current.overall_status != "ready" else 0
    if args.command == "show":
        current = load_freshness_manifest(args.manifest)
        _print_manifest(current, args.manifest)
        return 0
    current = build_freshness_manifest(
        expected_price_through=args.expected_price_through,
        expected_announcement_checked_through=args.expected_announcement_checked_through,
        research_symbols=args.symbol,
    )
    write_freshness_manifest(current, args.output)
    _print_manifest(current, args.output)
    if args.require_ready and current.overall_status != "ready":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
