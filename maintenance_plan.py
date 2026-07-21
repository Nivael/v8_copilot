"""Read-only full-universe maintenance planning."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PlannedSource(StrictModel):
    source_id: str
    target: str
    current_symbols: list[str]
    stale_symbols: list[str]
    missing_baseline_symbols: list[str]
    task_symbols: list[str]
    estimated_minimum_requests: int = Field(ge=0)


class MaintenancePlan(StrictModel):
    contract_version: Literal["v8_maintenance_plan_v1"] = "v8_maintenance_plan_v1"
    generated_at: str
    universe_snapshot_id: str = ""
    universe_as_of: str = ""
    symbol_count: int = Field(ge=1)
    symbols: list[str]
    sources: list[PlannedSource]
    warnings: list[str] = Field(default_factory=list)


def build_maintenance_plan(
    *,
    database: Path,
    announcement_refresh_dir: Path,
    state_database: Path,
    symbols: list[str],
    price_through: str,
    announcement_through: str,
    universe_snapshot_id: str = "",
    universe_as_of: str = "",
) -> MaintenancePlan:
    normalized = sorted(set(symbols))
    if not normalized:
        raise ValueError("maintenance plan 不能为空")
    price_target = _iso_date(price_through, "price_through")
    announcement_target = _iso_date(announcement_through, "announcement_through")
    price_max: dict[str, str] = {}
    announcement_max: dict[str, str] = {}
    if database.is_file():
        placeholders = ",".join("?" for _ in normalized)
        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
            price_max = {
                str(symbol): str(observed or "")[:10]
                for symbol, observed in connection.execute(
                    f"select symbol,max(trade_date) from daily_prices where adjust='qfq' "
                    f"and symbol in ({placeholders}) group by symbol",
                    normalized,
                )
            }
            announcement_max = {
                str(symbol): str(observed or "")[:10]
                for symbol, observed in connection.execute(
                    f"select symbol,max(announcement_date) from company_announcements "
                    f"where symbol in ({placeholders}) group by symbol",
                    normalized,
                )
            }
    checkpoints = _checkpoints(state_database, normalized)
    announcement_checks = _announcement_checks(announcement_refresh_dir, normalized)

    price_current: list[str] = []
    price_stale: list[str] = []
    price_missing: list[str] = []
    announcement_current: list[str] = []
    announcement_stale: list[str] = []
    announcement_missing: list[str] = []
    for symbol in normalized:
        price_checked = checkpoints.get(("tushare_daily_qfq", symbol), "")
        if price_checked >= price_target or price_max.get(symbol, "") >= price_target:
            price_current.append(symbol)
        elif price_max.get(symbol):
            price_stale.append(symbol)
        else:
            price_missing.append(symbol)

        announcement_checked = max(
            checkpoints.get(("cninfo_announcements", symbol), ""),
            announcement_checks.get(symbol, ""),
        )
        if announcement_checked >= announcement_target:
            announcement_current.append(symbol)
        elif announcement_max.get(symbol) or announcement_checked:
            announcement_stale.append(symbol)
        else:
            announcement_missing.append(symbol)

    price_tasks = sorted(price_stale + price_missing)
    announcement_tasks = sorted(announcement_stale + announcement_missing)
    warnings: list[str] = []
    if price_missing:
        warnings.append(
            f"{len(price_missing)} 只股票没有价格基线；必须逐股声明 bootstrap start date。"
        )
    if announcement_missing:
        warnings.append(
            f"{len(announcement_missing)} 只股票没有公告基线；必须逐股声明 bootstrap start date。"
        )
    return MaintenancePlan(
        generated_at=datetime.now(timezone.utc).isoformat(),
        universe_snapshot_id=universe_snapshot_id,
        universe_as_of=universe_as_of,
        symbol_count=len(normalized),
        symbols=normalized,
        sources=[
            PlannedSource(
                source_id="tushare_daily_qfq",
                target=price_target,
                current_symbols=price_current,
                stale_symbols=price_stale,
                missing_baseline_symbols=price_missing,
                task_symbols=price_tasks,
                estimated_minimum_requests=len(price_tasks) * 2,
            ),
            PlannedSource(
                source_id="cninfo_announcements",
                target=announcement_target,
                current_symbols=announcement_current,
                stale_symbols=announcement_stale,
                missing_baseline_symbols=announcement_missing,
                task_symbols=announcement_tasks,
                estimated_minimum_requests=len(announcement_tasks),
            ),
        ],
        warnings=warnings,
    )


def _iso_date(value: str, field: str) -> str:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是 YYYY-MM-DD: {value!r}") from exc


def _checkpoints(path: Path, symbols: list[str]) -> dict[tuple[str, str], str]:
    if not path.is_file():
        return {}
    placeholders = ",".join("?" for _ in symbols)
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            rows = connection.execute(
                f"select source_id,symbol,checked_through from refresh_checkpoints "
                f"where status='success' and symbol in ({placeholders})",
                symbols,
            ).fetchall()
    except sqlite3.Error:
        return {}
    return {(str(source), str(symbol)): str(checked or "")[:10] for source, symbol, checked in rows}


def _announcement_checks(root: Path, symbols: list[str]) -> dict[str, str]:
    checks: dict[str, str] = {}
    for symbol in symbols:
        path = root / f"{symbol}.json"
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("source") == "cninfo" and str(payload.get("symbol")) == symbol:
                checks[symbol] = str(payload.get("checked_through") or "")[:10]
        except (OSError, json.JSONDecodeError):
            continue
    return checks
