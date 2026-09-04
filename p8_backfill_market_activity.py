"""Execute the frozen P8-BT2 date-only market-activity backfill plan."""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from data_refresh import TushareHttpClient, atomic_write_json
from market_activity import MarketActivityBootstrapService, MarketActivityRepository
from settings import MARKET_ACTIVITY_DB, MARKET_CONTEXT_DB


EXPECTED_CONTRACT = "v8_p8_backtest_dry_plan_v1"


def _load_env(path: Path | None) -> None:
    if path is None:
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


class RetryingActivityProvider:
    def __init__(self, client: TushareHttpClient, *, attempts: int, backoff_seconds: float):
        self.client = client
        self.attempts = max(1, attempts)
        self.backoff_seconds = max(0.0, backoff_seconds)

    def _call(self, operation: Callable[[], list[dict[str, Any]]]) -> list[dict[str, Any]]:
        error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                return operation()
            except Exception as exc:
                error = exc
                if attempt + 1 < self.attempts:
                    time.sleep(self.backoff_seconds * (2 ** attempt))
        assert error is not None
        raise error

    def fetch_daily(self, *, trade_date: str) -> list[dict[str, Any]]:
        return self._call(lambda: self.client.fetch_daily(trade_date=trade_date))

    def fetch_daily_basic(self, *, trade_date: str) -> list[dict[str, Any]]:
        return self._call(lambda: self.client.fetch_daily_basic(trade_date=trade_date))

    def fetch_suspend_daily(self, *, trade_date: str) -> list[dict[str, Any]]:
        return self._call(lambda: self.client.fetch_suspend_daily(trade_date=trade_date))

    def fetch_stock_limits(self, *, trade_date: str) -> list[dict[str, Any]]:
        return self._call(lambda: self.client.fetch_stock_limits(trade_date=trade_date))


def _load_plan(path: Path) -> tuple[dict[str, Any], list[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("contract_version") != EXPECTED_CONTRACT:
        raise ValueError("dry-plan contract_version 与执行器不一致")
    if payload.get("outcomes_read") is not False or payload.get("returns_computed") is not False:
        raise ValueError("拒绝执行读取过 outcome/return 的计划")
    endpoint_plan = payload.get("endpoint_request_plan") or {}
    date_lists = [
        list((endpoint_plan.get(endpoint) or {}).get("dates") or [])
        for endpoint in ("daily", "daily_basic", "stk_limit", "suspend_d")
    ]
    if not date_lists[0] or any(items != date_lists[0] for items in date_lists[1:]):
        raise ValueError("四个 provider endpoint 必须使用同一冻结日期清单")
    if len(date_lists[0]) != int(payload["request_budget"]["incomplete_or_missing_trade_dates"]):
        raise ValueError("dry-plan 日期数与 request_budget 不一致")
    return payload, [str(day) for day in date_lists[0]]


def _retry_dates(
    *, plan: dict[str, Any], planned_dates: list[str], retry_report: Path,
) -> list[str]:
    prior = json.loads(retry_report.read_text(encoding="utf-8"))
    if (
        prior.get("source_plan_id") != plan.get("plan_id")
        or prior.get("source_plan_digest") != plan.get("content_digest")
    ):
        raise ValueError("retry report 与冻结 dry-plan 不匹配")
    failed = sorted(str(day) for day in (prior.get("result") or {}).get("failures", {}))
    if not failed or not set(failed).issubset(planned_dates):
        raise ValueError("retry report 没有合法失败日期")
    return failed


def execute_backfill(
    *, plan_path: Path, market_activity_database: Path,
    market_context_database: Path, allow_provider: bool,
    env_file: Path | None = None, max_attempts: int = 3,
    retry_backoff_seconds: float = 1.0, request_delay_seconds: float = 0.0,
    retry_report: Path | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if not allow_provider:
        raise ValueError("provider backfill 必须显式传 --allow-provider")
    plan, dates = _load_plan(plan_path)
    if retry_report is not None:
        dates = _retry_dates(
            plan=plan, planned_dates=dates, retry_report=retry_report,
        )
    _load_env(env_file)
    provider = RetryingActivityProvider(
        TushareHttpClient(), attempts=max_attempts,
        backoff_seconds=retry_backoff_seconds,
    )

    def report(item: dict[str, Any]) -> None:
        if progress:
            progress(item)
        if request_delay_seconds:
            time.sleep(request_delay_seconds)

    result = MarketActivityBootstrapService(
        provider=provider,
        repository=MarketActivityRepository(market_activity_database),
        market_context_database=market_context_database,
    ).bootstrap(
        start_date=str(plan["date_coverage"]["start_date"]),
        through=str(plan["date_coverage"]["through"]),
        target_dates=dates,
        refresh_existing=True,
        parallel_endpoints=True,
        resume=True,
        progress=report,
    )
    return {
        "contract_version": EXPECTED_CONTRACT,
        "source_plan_id": str(plan["plan_id"]),
        "source_plan_digest": str(plan["content_digest"]),
        "date_only": True,
        "retry_only": retry_report is not None,
        "provider_calls_expected": len(dates) * 4,
        "result": result.model_dump(mode="json"),
        "status": "complete" if result.failed_date_count == 0 else "partial",
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--market-activity-database", type=Path, default=MARKET_ACTIVITY_DB)
    parser.add_argument("--market-context-database", type=Path, default=MARKET_CONTEXT_DB)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-provider", action="store_true")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-backoff-seconds", type=float, default=1.0)
    parser.add_argument("--request-delay-seconds", type=float, default=0.0)
    parser.add_argument("--retry-report", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = execute_backfill(
        plan_path=args.plan,
        market_activity_database=args.market_activity_database,
        market_context_database=args.market_context_database,
        allow_provider=args.allow_provider,
        env_file=args.env_file,
        max_attempts=args.max_attempts,
        retry_backoff_seconds=args.retry_backoff_seconds,
        request_delay_seconds=args.request_delay_seconds,
        retry_report=args.retry_report,
        progress=lambda item: print(json.dumps({"progress": item}, ensure_ascii=False), flush=True),
    )
    atomic_write_json(args.output, result)
    print(json.dumps({
        "source_plan_id": result["source_plan_id"],
        "status": result["status"],
        "requested_dates": result["result"]["requested_date_count"],
        "failed_dates": result["result"]["failed_date_count"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
