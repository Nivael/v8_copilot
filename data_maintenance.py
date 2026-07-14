"""CLI boundary for the dedicated ST data-maintenance task.

It validates and promotes already fetched announcement metadata, and publishes the
unified freshness manifest.  Network fetches and price writes stay in the upstream
producer; this consumer does not hide them inside an answer request.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from freshness_manifest import (
    FreshnessManifest,
    build_freshness_manifest,
    load_freshness_manifest,
    write_freshness_manifest,
)
from settings import ANNOUNCEMENT_REFRESH_DIR, FRESHNESS_MANIFEST_PATH


def _promote_announcement(input_path: Path, symbol: str) -> Path:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if payload.get("source") != "cninfo":
        raise ValueError("公告增量必须来自 cninfo")
    if str(payload.get("symbol")) != symbol:
        raise ValueError("公告增量 symbol 与目标不一致")
    rows = payload.get("records")
    if not isinstance(rows, list):
        raise ValueError("公告增量缺 records list")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("公告 records 必须全部为 object")
        announcement_id = str(row.get("announcement_id") or "")
        announcement_date = str(row.get("announcement_date") or "")[:10]
        if not announcement_id.isdigit() or len(announcement_date) != 10 or not row.get("title"):
            raise ValueError("公告增量存在缺失或非法字段")
        if announcement_id in seen:
            raise ValueError(f"公告增量 ID 重复: {announcement_id}")
        seen.add(announcement_id)
    destination = ANNOUNCEMENT_REFRESH_DIR / f"{symbol}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=destination.name, suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            json.dump(payload, target, ensure_ascii=False, indent=2)
            target.write("\n")
        os.replace(temp_name, destination)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return destination


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


def main() -> int:
    parser = argparse.ArgumentParser(description="ST Research data maintenance boundary")
    sub = parser.add_subparsers(dest="command", required=True)

    promote = sub.add_parser("promote-announcements")
    promote.add_argument("--input", type=Path, required=True)
    promote.add_argument("--symbol", required=True)

    manifest = sub.add_parser("manifest")
    manifest.add_argument("--expected-price-through", default="")
    manifest.add_argument("--expected-announcement-checked-through", default="")
    manifest.add_argument("--symbol", action="append", default=[])
    manifest.add_argument("--output", type=Path, default=FRESHNESS_MANIFEST_PATH)
    manifest.add_argument("--require-ready", action="store_true")

    show = sub.add_parser("show")
    show.add_argument("--manifest", type=Path, default=FRESHNESS_MANIFEST_PATH)

    args = parser.parse_args()
    if args.command == "promote-announcements":
        if len(args.symbol) != 6 or not args.symbol.isdigit():
            parser.error("--symbol 必须是六位股票代码")
        destination = _promote_announcement(args.input, args.symbol)
        print(json.dumps({"promoted": str(destination), "symbol": args.symbol}, ensure_ascii=False))
        return 0
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
