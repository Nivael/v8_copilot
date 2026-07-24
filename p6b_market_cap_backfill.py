"""Resumable P6B historical market-cap backfill over frozen anchor dates."""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from data_refresh import TushareHttpClient, atomic_write_json
from market_factors import (
    MarketFactorRepository,
    MarketFactorService,
    advance_market_factor_current,
    build_market_factor_manifest,
    write_market_factor_dated_manifest,
)
from settings import (
    MARKET_CONTEXT_DB,
    MARKET_FACTOR_DB,
    MARKET_FACTOR_MANIFEST_DIR,
    MARKET_FACTOR_MANIFEST_PATH,
    PROJECT_ROOT,
)


CONTRACT_VERSION = "v8_p6b_market_cap_backfill_v1"
RUN_CONTRACT_VERSION = "v8_p6b_market_cap_backfill_run_v1"
SOURCE_DRY_PLAN_ID = "P6B0-BE1B382B7CF794EBAECA"
SOURCE_PROVIDER_PROBE_ID = "P6BP-574C9D1EEA97E0DF953B"
DEFAULT_PLAN_PATH = (
    PROJECT_ROOT
    / "contracts/v8_p6b_market_cap_backfill_v1/plan.json"
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DailyBasicProvider(Protocol):
    def fetch_daily_basic(self, *, trade_date: str) -> list[dict[str, Any]]: ...


class AnchorDateAdjustment(StrictModel):
    source_episode_start_date: str
    market_cap_anchor_trade_date: str
    reason: Literal["next_csi_all_share_trade_date"] = (
        "next_csi_all_share_trade_date"
    )


class MarketCapBackfillPlan(StrictModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    plan_id: str = Field(pattern=r"^P6B1P-[A-F0-9]{20}$")
    source_dry_plan_id: Literal[SOURCE_DRY_PLAN_ID] = SOURCE_DRY_PLAN_ID
    source_provider_probe_id: Literal[SOURCE_PROVIDER_PROBE_ID] = (
        SOURCE_PROVIDER_PROBE_ID
    )
    as_of: str
    source_episode_start_count: int = Field(ge=1)
    anchor_date_adjustments: list[AnchorDateAdjustment]
    trade_dates: list[str] = Field(min_length=1)


class BackfillDateResult(StrictModel):
    trade_date: str
    action: Literal["fetched", "existing_snapshot", "error"]
    snapshot_id: str = ""
    manifest_id: str = ""
    membership_count: int = Field(default=0, ge=0)
    valid_total_market_value_count: int = Field(default=0, ge=0)
    coverage_ratio: float = Field(default=0, ge=0, le=1)
    status: Literal["ready", "gaps", "error"]
    error: str = ""


class MarketCapBackfillRun(StrictModel):
    contract_version: Literal[RUN_CONTRACT_VERSION] = RUN_CONTRACT_VERSION
    run_id: str = Field(pattern=r"^P6B1R-[A-F0-9]{20}$")
    plan_id: str
    started_at: str
    finished_at: str
    status: Literal["complete", "partial", "failed"]
    planned_date_count: int = Field(ge=1)
    snapshot_date_count: int = Field(ge=0)
    ready_date_count: int = Field(ge=0)
    gap_date_count: int = Field(ge=0)
    missing_date_count: int = Field(ge=0)
    fetched_date_count: int = Field(ge=0)
    existing_date_count: int = Field(ge=0)
    current_pointer_advanced: bool
    results: list[BackfillDateResult]
    missing_dates: list[str]


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _identifier(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical(payload).encode()).hexdigest()
    return prefix + digest[:20].upper()


def _trading_calendar(database: Path, *, as_of: str) -> list[str]:
    if not database.is_file():
        raise FileNotFoundError(database)
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "select trade_date from benchmark_daily "
            "where benchmark_id='csi_all_share' and trade_date<=? "
            "order by trade_date",
            (as_of,),
        ).fetchall()
    calendar = [str(row[0])[:10] for row in rows]
    if not calendar:
        raise ValueError("中证全指交易日历为空")
    return calendar


def build_backfill_plan(
    dry_plan_payload: dict[str, Any],
    *,
    trading_calendar: list[str],
) -> MarketCapBackfillPlan:
    source_id = str(dry_plan_payload.get("plan_id") or "")
    if source_id != SOURCE_DRY_PLAN_ID:
        raise ValueError(
            f"dry plan id 不匹配: {source_id or 'missing'} != {SOURCE_DRY_PLAN_ID}"
        )
    as_of = str(dry_plan_payload.get("as_of") or "")
    source_dates = sorted({
        str(item.get("start_date") or "")
        for item in (dry_plan_payload.get("episodes") or [])
        if item.get("start_date")
    })
    if not source_dates:
        raise ValueError("dry plan 没有 candidate episode start_date")
    if any(len(day) != 10 for day in source_dates):
        raise ValueError("dry plan 包含非法 anchor date")
    calendar = sorted(set(trading_calendar))
    if not calendar:
        raise ValueError("trading_calendar 为空")
    dates: list[str] = []
    adjustments: list[AnchorDateAdjustment] = []
    for source_date in source_dates:
        index = bisect.bisect_left(calendar, source_date)
        if index >= len(calendar):
            raise ValueError(f"{source_date} 之后没有可用交易日")
        anchor_date = calendar[index]
        dates.append(anchor_date)
        if anchor_date != source_date:
            adjustments.append(AnchorDateAdjustment(
                source_episode_start_date=source_date,
                market_cap_anchor_trade_date=anchor_date,
            ))
    dates = sorted(set(dates))
    payload = {
        "contract_version": CONTRACT_VERSION,
        "source_dry_plan_id": SOURCE_DRY_PLAN_ID,
        "source_provider_probe_id": SOURCE_PROVIDER_PROBE_ID,
        "as_of": as_of,
        "source_episode_start_count": len(source_dates),
        "anchor_date_adjustments": [
            item.model_dump(mode="json") for item in adjustments
        ],
        "trade_dates": dates,
    }
    return MarketCapBackfillPlan(
        plan_id=_identifier("P6B1P-", payload),
        **payload,
    )


def load_backfill_plan(path: Path) -> MarketCapBackfillPlan:
    if not path.is_file():
        raise FileNotFoundError(path)
    plan = MarketCapBackfillPlan.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if plan.trade_dates != sorted(set(plan.trade_dates)):
        raise ValueError("backfill trade_dates 必须严格升序且不重复")
    expected_payload = plan.model_dump(mode="json", exclude={"plan_id"})
    expected = _identifier("P6B1P-", expected_payload)
    if plan.plan_id != expected:
        raise ValueError(f"backfill plan content hash 不匹配: {plan.plan_id}")
    return plan


def _retry(
    operation: Callable[[], Any],
    *,
    max_attempts: int,
    backoff_seconds: float,
) -> Any:
    if max_attempts < 1:
        raise ValueError("max_attempts 必须至少为 1")
    if backoff_seconds < 0:
        raise ValueError("backoff_seconds 不能为负数")
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except Exception:
            if attempt == max_attempts:
                raise
            time.sleep(backoff_seconds * (2 ** (attempt - 1)))
    raise AssertionError("unreachable")


def _date_result(
    *,
    trade_date: str,
    action: Literal["fetched", "existing_snapshot"],
    repository: MarketFactorRepository,
    manifest_directory: Path,
    coverage_threshold: float,
) -> BackfillDateResult:
    snapshot = repository.latest_snapshot(trade_date)
    if snapshot is None:
        raise ValueError(f"{trade_date} snapshot 写入后不可见")
    manifest = build_market_factor_manifest(
        repository=repository,
        snapshot_id=snapshot.snapshot_id,
        coverage_threshold=coverage_threshold,
    )
    write_market_factor_dated_manifest(
        manifest,
        manifest_directory=manifest_directory,
    )
    return BackfillDateResult(
        trade_date=trade_date,
        action=action,
        snapshot_id=snapshot.snapshot_id,
        manifest_id=str(manifest["manifest_id"]),
        membership_count=snapshot.membership_count,
        valid_total_market_value_count=(
            snapshot.valid_total_market_value_count
        ),
        coverage_ratio=snapshot.coverage_ratio,
        status="ready" if manifest["status"] == "ready" else "gaps",
    )


def _inventory(
    plan: MarketCapBackfillPlan,
    *,
    repository: MarketFactorRepository,
    manifest_directory: Path,
    coverage_threshold: float,
) -> tuple[list[str], int, int]:
    missing: list[str] = []
    ready = 0
    gaps = 0
    for day in plan.trade_dates:
        snapshot = repository.latest_snapshot(day)
        dated = manifest_directory / f"{day}.json"
        if snapshot is None or not dated.is_file():
            missing.append(day)
            continue
        manifest = build_market_factor_manifest(
            repository=repository,
            snapshot_id=snapshot.snapshot_id,
            coverage_threshold=coverage_threshold,
        )
        if manifest["status"] == "ready":
            ready += 1
        else:
            gaps += 1
    return missing, ready, gaps


def run_backfill(
    *,
    plan: MarketCapBackfillPlan,
    provider: DailyBasicProvider,
    market_context_database: Path,
    market_factor_database: Path,
    manifest_directory: Path,
    current_manifest_path: Path,
    coverage_threshold: float = 0.95,
    max_fetches: int = 0,
    max_attempts: int = 3,
    retry_backoff_seconds: float = 1.0,
    request_delay_seconds: float = 0.0,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> MarketCapBackfillRun:
    if not 0 < coverage_threshold <= 1:
        raise ValueError("coverage_threshold 必须在 (0,1]")
    if max_fetches < 0:
        raise ValueError("max_fetches 不能为负数")
    if request_delay_seconds < 0:
        raise ValueError("request_delay_seconds 不能为负数")
    started = datetime.now(timezone.utc).isoformat()
    repository = MarketFactorRepository(market_factor_database)
    service = MarketFactorService(
        provider=provider,
        repository=repository,
        market_context_database=market_context_database,
    )
    results: list[BackfillDateResult] = []
    fetched = 0
    stopped_on_error = False
    for day in plan.trade_dates:
        existing = repository.latest_snapshot(day)
        if existing is not None:
            result = _date_result(
                trade_date=day,
                action="existing_snapshot",
                repository=repository,
                manifest_directory=manifest_directory,
                coverage_threshold=coverage_threshold,
            )
            results.append(result)
            continue
        if max_fetches and fetched >= max_fetches:
            break
        try:
            _retry(
                lambda day=day: service.refresh(as_of=day),
                max_attempts=max_attempts,
                backoff_seconds=retry_backoff_seconds,
            )
            fetched += 1
            result = _date_result(
                trade_date=day,
                action="fetched",
                repository=repository,
                manifest_directory=manifest_directory,
                coverage_threshold=coverage_threshold,
            )
        except Exception as exc:
            result = BackfillDateResult(
                trade_date=day,
                action="error",
                status="error",
                error=f"{type(exc).__name__}: {exc}",
            )
            stopped_on_error = True
        results.append(result)
        if progress is not None:
            progress({
                "trade_date": result.trade_date,
                "action": result.action,
                "status": result.status,
                "coverage_ratio": result.coverage_ratio,
                "fetched": fetched,
            })
        if stopped_on_error:
            break
        if request_delay_seconds:
            time.sleep(request_delay_seconds)
    missing, ready, gaps = _inventory(
        plan,
        repository=repository,
        manifest_directory=manifest_directory,
        coverage_threshold=coverage_threshold,
    )
    current_advanced = False
    if not missing:
        latest_snapshot = repository.latest_snapshot(plan.trade_dates[-1])
        if latest_snapshot is None:
            raise AssertionError("complete inventory 缺 latest snapshot")
        latest_manifest = build_market_factor_manifest(
            repository=repository,
            snapshot_id=latest_snapshot.snapshot_id,
            coverage_threshold=coverage_threshold,
        )
        current_advanced = advance_market_factor_current(
            latest_manifest,
            current_path=current_manifest_path,
        )
    if not missing:
        status = "complete"
    elif results and all(item.action == "error" for item in results):
        status = "failed"
    else:
        status = "partial"
    finished = datetime.now(timezone.utc).isoformat()
    report_payload = {
        "contract_version": RUN_CONTRACT_VERSION,
        "plan_id": plan.plan_id,
        "started_at": started,
        "finished_at": finished,
        "status": status,
        "planned_date_count": len(plan.trade_dates),
        "snapshot_date_count": len(plan.trade_dates) - len(missing),
        "ready_date_count": ready,
        "gap_date_count": gaps,
        "missing_date_count": len(missing),
        "fetched_date_count": sum(
            item.action == "fetched" for item in results
        ),
        "existing_date_count": sum(
            item.action == "existing_snapshot" for item in results
        ),
        "current_pointer_advanced": current_advanced,
        "results": [item.model_dump(mode="json") for item in results],
        "missing_dates": missing,
    }
    return MarketCapBackfillRun(
        run_id=_identifier("P6B1R-", report_payload),
        **report_payload,
    )


def _load_provider_env(path: Path | None) -> None:
    if path is None:
        return
    if not path.is_file():
        raise FileNotFoundError(path)
    allowed = {"TUSHARE_TOKEN", "TUSHARE_HTTP_URL"}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in allowed:
            os.environ.setdefault(key, value.strip().strip("'\""))


def _plan_command(args: argparse.Namespace) -> int:
    dry_plan = json.loads(args.dry_plan_json.read_text(encoding="utf-8"))
    calendar = _trading_calendar(
        args.market_context_database,
        as_of=str(dry_plan.get("as_of") or ""),
    )
    plan = build_backfill_plan(
        dry_plan,
        trading_calendar=calendar,
    )
    atomic_write_json(args.output, plan.model_dump(mode="json"))
    print(json.dumps({
        "plan_id": plan.plan_id,
        "trade_date_count": len(plan.trade_dates),
        "anchor_date_adjustment_count": len(plan.anchor_date_adjustments),
        "first": plan.trade_dates[0],
        "last": plan.trade_dates[-1],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


def _run_command(args: argparse.Namespace) -> int:
    _load_provider_env(args.env_file)
    plan = load_backfill_plan(args.plan)
    progress_counter = 0

    def show_progress(payload: dict[str, Any]) -> None:
        nonlocal progress_counter
        progress_counter += 1
        if (
            payload["status"] == "error"
            or progress_counter % args.progress_every == 0
        ):
            print(
                json.dumps({"p6b1_backfill": payload}, ensure_ascii=False),
                flush=True,
            )

    report = run_backfill(
        plan=plan,
        provider=TushareHttpClient(),
        market_context_database=args.market_context_database,
        market_factor_database=args.market_factor_database,
        manifest_directory=args.manifest_directory,
        current_manifest_path=args.current_manifest,
        coverage_threshold=args.coverage_threshold,
        max_fetches=args.max_fetches,
        max_attempts=args.max_attempts,
        retry_backoff_seconds=args.retry_backoff_seconds,
        request_delay_seconds=args.request_delay_seconds,
        progress=show_progress,
    )
    if args.output:
        atomic_write_json(args.output, report.model_dump(mode="json"))
    print(json.dumps({
        "run_id": report.run_id,
        "status": report.status,
        "planned": report.planned_date_count,
        "snapshots": report.snapshot_date_count,
        "ready": report.ready_date_count,
        "gaps": report.gap_date_count,
        "missing": report.missing_date_count,
        "fetched": report.fetched_date_count,
        "output": str(args.output or ""),
    }, ensure_ascii=False))
    return 0 if report.status == "complete" else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="P6B-1 锚点日 market-cap plan 与可恢复回填"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--dry-plan-json", type=Path, required=True)
    plan_parser.add_argument(
        "--market-context-database",
        type=Path,
        default=MARKET_CONTEXT_DB,
    )
    plan_parser.add_argument(
        "--output", type=Path, default=DEFAULT_PLAN_PATH
    )
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN_PATH)
    run_parser.add_argument("--env-file", type=Path)
    run_parser.add_argument(
        "--market-context-database", type=Path, default=MARKET_CONTEXT_DB
    )
    run_parser.add_argument(
        "--market-factor-database", type=Path, default=MARKET_FACTOR_DB
    )
    run_parser.add_argument(
        "--manifest-directory",
        type=Path,
        default=MARKET_FACTOR_MANIFEST_DIR,
    )
    run_parser.add_argument(
        "--current-manifest",
        type=Path,
        default=MARKET_FACTOR_MANIFEST_PATH,
    )
    run_parser.add_argument("--coverage-threshold", type=float, default=0.95)
    run_parser.add_argument("--max-fetches", type=int, default=0)
    run_parser.add_argument("--max-attempts", type=int, default=3)
    run_parser.add_argument(
        "--retry-backoff-seconds", type=float, default=1.0
    )
    run_parser.add_argument(
        "--request-delay-seconds", type=float, default=0.0
    )
    run_parser.add_argument("--progress-every", type=int, default=10)
    run_parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.command == "plan":
        return _plan_command(args)
    if args.progress_every < 1:
        parser.error("--progress-every 必须至少为 1")
    return _run_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
