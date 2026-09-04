"""Bounded P8 chip-proxy provider probe; never writes canonical data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from data_refresh import TushareHttpClient


CONTRACT_VERSION = "v8_p8_chip_provider_probe_v1"
REQUIRED_FIELDS = {
    "stk_holdernumber": {"ts_code", "ann_date", "end_date", "holder_num"},
    "top_list": {
        "trade_date", "ts_code", "close", "pct_change", "turnover_rate",
        "amount", "l_sell", "l_buy", "net_amount", "reason",
    },
    "top_inst": {"trade_date", "ts_code", "exalter", "side", "buy", "sell", "net_buy", "reason"},
    "block_trade": {"ts_code", "trade_date", "price", "vol", "amount", "buyer", "seller"},
    "margin_detail": {"trade_date", "ts_code", "rzye", "rqye", "rzmre", "rzche", "rzrqye"},
}
ROW_LIMITS = {
    "stk_holdernumber": 3000,
    "top_list": 10000,
    "top_inst": 10000,
    "block_trade": 1000,
    "margin_detail": 6000,
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ChipEndpointObservation(StrictModel):
    endpoint: str
    probe_key: str
    status: Literal["success", "empty_valid", "permission_denied", "rate_limited", "provider_error"]
    row_count: int = Field(ge=0)
    returned_fields: list[str]
    missing_required_fields: list[str]
    field_completeness: dict[str, float]
    response_not_truncated: bool | None
    elapsed_ms: int = Field(ge=0)
    available_date_field: str
    missing_semantics: str
    error: str = ""


class P8ChipProviderProbe(StrictModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    probe_id: str = Field(pattern=r"^P8PP-[A-F0-9]{20}$")
    source_dry_plan_id: str
    source_dry_plan_digest: str
    generated_at: str
    probe_symbol: str
    trade_date: str
    observations: list[ChipEndpointObservation]
    endpoint_summary: dict[str, Any]
    request_budget: dict[str, Any]
    production_writes: Literal[0] = 0


class ChipProvider(Protocol):
    def fetch_holder_numbers(self, *, symbol: str, start_date: str, end_date: str) -> list[dict[str, Any]]: ...
    def fetch_top_list(self, *, trade_date: str) -> list[dict[str, Any]]: ...
    def fetch_top_institutions(self, *, trade_date: str) -> list[dict[str, Any]]: ...
    def fetch_block_trades(self, *, trade_date: str) -> list[dict[str, Any]]: ...
    def fetch_margin_details(self, *, trade_date: str) -> list[dict[str, Any]]: ...


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _safe_error(exc: Exception) -> tuple[str, str]:
    text = " ".join(str(exc).split())[:240]
    lower = text.lower()
    if any(term in lower for term in ("权限", "积分", "permission", "privilege")):
        return "permission_denied", f"{type(exc).__name__}: {text}"
    if any(term in lower for term in ("limit", "频率", "rate", "每分钟")):
        return "rate_limited", f"{type(exc).__name__}: {text}"
    return "provider_error", f"{type(exc).__name__}: {text}"


def _observe(
    endpoint: str, probe_key: str, operation: Any,
) -> ChipEndpointObservation:
    started = time.monotonic()
    available_date_field = "ann_date" if endpoint == "stk_holdernumber" else "trade_date"
    missing_semantics = {
        "stk_holdernumber": "无返回只表示供应商未覆盖该披露，不表示户数没有变化。",
        "top_list": "龙虎榜为事件触发数据；无返回不表示没有机构或大额交易。",
        "top_inst": "无机构席位明细不表示没有机构交易。",
        "block_trade": "完整日期截面成功且无记录时才可称当日无公开大宗交易。",
        "margin_detail": "非两融标的缺失不是零融资余额。",
    }[endpoint]
    try:
        rows = operation()
        fields = sorted({str(key) for row in rows for key in row})
        required = REQUIRED_FIELDS[endpoint]
        return ChipEndpointObservation(
            endpoint=endpoint, probe_key=probe_key,
            status="success" if rows else "empty_valid",
            row_count=len(rows), returned_fields=fields,
            missing_required_fields=sorted(required - set(fields)) if rows else [],
            field_completeness={
                field: round(sum(row.get(field) not in (None, "") for row in rows) / len(rows), 8)
                if rows else 0.0 for field in sorted(required)
            },
            response_not_truncated=len(rows) < ROW_LIMITS[endpoint],
            elapsed_ms=int((time.monotonic() - started) * 1000),
            available_date_field=available_date_field,
            missing_semantics=missing_semantics,
        )
    except Exception as exc:
        status, error = _safe_error(exc)
        return ChipEndpointObservation(
            endpoint=endpoint, probe_key=probe_key, status=status,  # type: ignore[arg-type]
            row_count=0, returned_fields=[],
            missing_required_fields=sorted(REQUIRED_FIELDS[endpoint]),
            field_completeness={}, response_not_truncated=None,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            available_date_field=available_date_field,
            missing_semantics=missing_semantics, error=error,
        )


def build_chip_probe(
    *, provider: ChipProvider, source_dry_plan: dict[str, Any],
    probe_symbol: str, trade_date: str,
) -> P8ChipProviderProbe:
    year = int(trade_date[:4]) - 1
    holder_start = f"{year:04d}-{trade_date[5:]}"
    operations = {
        "stk_holdernumber": (
            f"{probe_symbol}:{holder_start}:{trade_date}",
            lambda: provider.fetch_holder_numbers(symbol=probe_symbol, start_date=holder_start, end_date=trade_date),
        ),
        "top_list": (trade_date, lambda: provider.fetch_top_list(trade_date=trade_date)),
        "top_inst": (trade_date, lambda: provider.fetch_top_institutions(trade_date=trade_date)),
        "block_trade": (trade_date, lambda: provider.fetch_block_trades(trade_date=trade_date)),
        "margin_detail": (trade_date, lambda: provider.fetch_margin_details(trade_date=trade_date)),
    }
    observations = [
        _observe(endpoint, key, operation)
        for endpoint, (key, operation) in operations.items()
    ]
    summary = {
        item.endpoint: {
            "status": item.status,
            "row_count": item.row_count,
            "schema_complete": not item.missing_required_fields,
            "response_not_truncated": item.response_not_truncated,
            "blocking": False,
            "available_date_field": item.available_date_field,
            "missing_semantics": item.missing_semantics,
        }
        for item in observations
    }
    identity = {
        "contract_version": CONTRACT_VERSION,
        "source_dry_plan_id": source_dry_plan.get("plan_id", ""),
        "source_dry_plan_digest": source_dry_plan.get("content_digest", ""),
        "probe_symbol": probe_symbol,
        "trade_date": trade_date,
        "observations": [item.model_dump(mode="json") for item in observations],
    }
    return P8ChipProviderProbe(
        probe_id=f"P8PP-{_digest(identity)[:20].upper()}",
        source_dry_plan_id=str(source_dry_plan.get("plan_id") or ""),
        source_dry_plan_digest=str(source_dry_plan.get("content_digest") or ""),
        generated_at=datetime.now(timezone.utc).isoformat(),
        probe_symbol=probe_symbol, trade_date=trade_date,
        observations=observations, endpoint_summary=summary,
        request_budget={
            "probe_calls": len(observations),
            "documented_minimum_points": 2000,
            "full_history_plan": "not_authorized_by_probe",
            "daily_cross_section_calls_if_enabled": 4,
            "holder_number_requests": "symbol-bounded; use announcement date as available_as_of",
        },
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
    parser.add_argument("--source-dry-plan", type=Path, required=True)
    parser.add_argument("--probe-symbol", default="000010")
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--probe-provider", action="store_true")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    if not args.probe_provider:
        parser.error("provider probe 必须显式传 --probe-provider")
    date.fromisoformat(args.trade_date)
    _load_env_file(args.env_file)
    source = json.loads(args.source_dry_plan.read_text(encoding="utf-8"))
    result = build_chip_probe(
        provider=TushareHttpClient(), source_dry_plan=source,
        probe_symbol=args.probe_symbol, trade_date=args.trade_date,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "probe_id": result.probe_id,
        "endpoint_summary": result.endpoint_summary,
        "production_writes": result.production_writes,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
