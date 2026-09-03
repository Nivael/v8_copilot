"""Bounded P7-0b provider permission and schema probe; never writes canonical data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from data_refresh import TushareHttpClient


CONTRACT_VERSION = "v8_p7_0_provider_probe_v1"
REQUIRED_FIELDS = {
    "daily_basic": {
        "ts_code", "trade_date", "close", "turnover_rate", "turnover_rate_f",
        "volume_ratio", "total_share", "float_share", "free_share", "total_mv",
        "circ_mv", "limit_status",
    },
    "daily": {"ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"},
    "suspend_d": {"ts_code", "trade_date", "suspend_timing", "suspend_type"},
    "stk_limit": {"trade_date", "ts_code", "pre_close", "up_limit", "down_limit"},
}
FROZEN_DATES = ("2016-08-09", "2021-03-17", "2023-08-11")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EndpointObservation(StrictModel):
    endpoint: str
    trade_date: str
    status: Literal["success", "permission_denied", "rate_limited", "empty_valid", "provider_error"]
    row_count: int = Field(ge=0)
    returned_fields: list[str]
    missing_required_fields: list[str]
    field_completeness: dict[str, float]
    elapsed_ms: int = Field(ge=0)
    response_not_truncated: bool | None = None
    error: str = ""


class P7ProviderProbe(StrictModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    probe_id: str = Field(pattern=r"^P7PP-[A-F0-9]{20}$")
    source_dry_plan_id: str
    source_dry_plan_digest: str
    generated_at: str
    probe_dates: list[str]
    provider_permission_matrix: dict[str, Any]
    observations: list[EndpointObservation]
    current_account_points: Literal["unknown"] = "unknown"
    request_budget: dict[str, Any]
    hard_blockers: list[str]
    non_blocking_gaps: list[str]
    production_writes: Literal[0] = 0


class ProbeProvider(Protocol):
    def fetch_daily(self, *, trade_date: str) -> list[dict[str, Any]]: ...
    def fetch_daily_basic(self, *, trade_date: str) -> list[dict[str, Any]]: ...
    def fetch_suspend_daily(self, *, trade_date: str) -> list[dict[str, Any]]: ...
    def fetch_stock_limits(self, *, trade_date: str) -> list[dict[str, Any]]: ...
    def fetch_exchange_reference(self, *, api_name: str, trade_date: str) -> list[dict[str, Any]]: ...


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _safe_error(exc: Exception) -> tuple[str, str]:
    text = " ".join(str(exc).split())[:240]
    lower = text.lower()
    if any(term in lower for term in ("权限", "积分", "无法使用", "permission", "no privilege")):
        status = "permission_denied"
    elif any(term in lower for term in ("limit", "频率", "rate", "每分钟")):
        status = "rate_limited"
    else:
        status = "provider_error"
    return status, f"{type(exc).__name__}: {text}"


def _observe(
    endpoint: str, trade_date: str, operation: Any,
) -> EndpointObservation:
    started = time.monotonic()
    try:
        rows = operation()
        elapsed = int((time.monotonic() - started) * 1000)
        fields = sorted({str(key) for row in rows for key in row})
        required = REQUIRED_FIELDS.get(endpoint, set())
        missing_schema = sorted(required - set(fields)) if rows else []
        completeness = {
            field: round(sum(row.get(field) not in (None, "") for row in rows) / len(rows), 8)
            if rows else 0.0
            for field in sorted(required)
        }
        return EndpointObservation(
            endpoint=endpoint, trade_date=trade_date,
            status=("empty_valid" if not rows else "success"),
            row_count=len(rows), returned_fields=fields,
            missing_required_fields=missing_schema,
            field_completeness=completeness, elapsed_ms=elapsed,
            response_not_truncated=(len(rows) < 5000 if endpoint == "suspend_d" else None),
        )
    except Exception as exc:
        status, error = _safe_error(exc)
        return EndpointObservation(
            endpoint=endpoint, trade_date=trade_date, status=status,  # type: ignore[arg-type]
            row_count=0, returned_fields=[], missing_required_fields=sorted(REQUIRED_FIELDS.get(endpoint, set())),
            field_completeness={}, elapsed_ms=int((time.monotonic() - started) * 1000), error=error,
        )


def _matrix(observations: list[EndpointObservation]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    endpoints = sorted({item.endpoint for item in observations})
    for endpoint in endpoints:
        rows = [item for item in observations if item.endpoint == endpoint]
        statuses = CounterLike(item.status for item in rows)
        if any(item.status == "success" for item in rows):
            overall = "success"
        elif rows and all(item.status == "empty_valid" for item in rows):
            overall = "empty_valid"
        elif any(item.status == "permission_denied" for item in rows):
            overall = "permission_denied"
        elif any(item.status == "rate_limited" for item in rows):
            overall = "rate_limited"
        else:
            overall = "provider_error"
        result[endpoint] = {
            "status": overall,
            "observations": len(rows),
            "successful_or_empty": sum(item.status in {"success", "empty_valid"} for item in rows),
            "row_count": sum(item.row_count for item in rows),
            "missing_required_fields": sorted({field for item in rows for field in item.missing_required_fields}),
            "status_counts": statuses,
            "max_elapsed_ms": max((item.elapsed_ms for item in rows), default=0),
        }
    return result


def CounterLike(values: Any) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[str(value)] = result.get(str(value), 0) + 1
    return result


def build_provider_probe(
    *, provider: ProbeProvider, source_dry_plan: dict[str, Any], latest_trade_date: str,
) -> P7ProviderProbe:
    dates = [*FROZEN_DATES, latest_trade_date]
    observations: list[EndpointObservation] = []
    operations = {
        "daily": provider.fetch_daily,
        "daily_basic": provider.fetch_daily_basic,
        "suspend_d": provider.fetch_suspend_daily,
        "stk_limit": provider.fetch_stock_limits,
    }
    for day in dates:
        for endpoint, method in operations.items():
            observations.append(_observe(endpoint, day, lambda method=method, day=day: method(trade_date=day)))
    for endpoint in ("stk_shock", "stk_high_shock", "stk_alert"):
        observations.append(_observe(
            endpoint, latest_trade_date,
            lambda endpoint=endpoint: provider.fetch_exchange_reference(api_name=endpoint, trade_date=latest_trade_date),
        ))
    matrix = _matrix(observations)
    blockers: list[str] = []
    for endpoint in ("daily", "daily_basic", "suspend_d", "stk_limit"):
        status = matrix.get(endpoint, {}).get("status")
        if status not in {"success", "empty_valid"}:
            blockers.append(f"{endpoint} 当前账号不可用: {status}")
    daily_basic_missing = matrix.get("daily_basic", {}).get("missing_required_fields", [])
    for field in ("turnover_rate_f", "limit_status"):
        if field in daily_basic_missing:
            blockers.append(f"daily_basic 未返回必需字段 {field}")
    non_blocking = [
        f"{endpoint}: {matrix.get(endpoint, {}).get('status', 'not_probed')}"
        for endpoint in ("stk_shock", "stk_high_shock", "stk_alert")
        if matrix.get(endpoint, {}).get("status") not in {"success", "empty_valid"}
    ]
    identity = {
        "contract_version": CONTRACT_VERSION,
        "source_dry_plan_id": source_dry_plan.get("plan_id", ""),
        "source_dry_plan_digest": source_dry_plan.get("content_digest", ""),
        "dates": dates,
        "observations": [item.model_dump(mode="json") for item in observations],
    }
    return P7ProviderProbe(
        probe_id=f"P7PP-{_digest(identity)[:20].upper()}",
        source_dry_plan_id=str(source_dry_plan.get("plan_id") or ""),
        source_dry_plan_digest=str(source_dry_plan.get("content_digest") or ""),
        generated_at=datetime.now(timezone.utc).isoformat(),
        probe_dates=dates, provider_permission_matrix=matrix,
        observations=observations,
        request_budget={
            "probe_calls": len(observations),
            "latest_120_bootstrap_calls": 484,
            "daily_increment_calls": 4,
            "minimum_safe_interval_seconds": "unknown; use bounded maintenance retries",
            "daily_basic_documented_points": {"minimum": 2000, "unlimited_total": 5000},
        },
        hard_blockers=blockers, non_blocking_gaps=non_blocking,
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
    parser = argparse.ArgumentParser(description="P7-0b bounded provider probe")
    parser.add_argument("--source-dry-plan", type=Path, required=True)
    parser.add_argument("--latest-trade-date", required=True)
    parser.add_argument("--probe-provider", action="store_true")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    if not args.probe_provider:
        parser.error("provider probe 必须显式传 --probe-provider")
    _load_env_file(args.env_file)
    source = json.loads(args.source_dry_plan.read_text(encoding="utf-8"))
    result = build_provider_probe(
        provider=TushareHttpClient(), source_dry_plan=source,
        latest_trade_date=args.latest_trade_date,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(json.dumps({
        "probe_id": result.probe_id, "output": str(args.output_json),
        "provider_permission_matrix": result.provider_permission_matrix,
        "hard_blockers": result.hard_blockers, "non_blocking_gaps": result.non_blocking_gaps,
        "production_writes": result.production_writes,
    }, ensure_ascii=False, indent=2))
    return 2 if result.hard_blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
