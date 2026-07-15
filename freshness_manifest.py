"""Unified, local-only freshness manifest for every v8 research source.

The manifest reports observed source state.  It never fetches data and never writes
research databases.  A separately authorized maintenance task may write the
manifest after upstream refresh jobs complete.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from answer_engine import BASE_DB, EPISODE_INDEX, EPISODE_MANIFEST, SHAREHOLDER_DB
from lens_binding import RELEASE_LIBRARY
from settings import (
    ANNOUNCEMENT_BODY_CACHE_DIR,
    ANNOUNCEMENT_REFRESH_DIR,
    DATA_MAINTENANCE_DB,
    FRESHNESS_MANIFEST_PATH,
    RECRUITMENT_DEADLINE_MATERIALIZATION,
)
from snapshot_metadata import load_episode_snapshot, load_price_snapshot, load_table_snapshot


FRESHNESS_MANIFEST_VERSION = "v8_freshness_manifest_v0"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceFreshness(StrictModel):
    source_id: str
    label: str
    source_ref: str
    status: Literal["current", "stale", "observed", "missing", "error"]
    as_of: str = ""
    checked_at: str = ""
    expected_through: str = ""
    row_count: int = Field(default=0, ge=0)
    coverage_count: int = Field(default=0, ge=0)
    details: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class FreshnessManifest(StrictModel):
    contract_version: Literal[FRESHNESS_MANIFEST_VERSION] = FRESHNESS_MANIFEST_VERSION
    manifest_id: str = Field(pattern=r"^FM-[A-F0-9]{20}$")
    generated_at: str
    overall_status: Literal["ready", "gaps", "observed"]
    expected_price_through: str = ""
    expected_announcement_checked_through: str = ""
    research_symbols: list[str] = Field(default_factory=list)
    sources: list[SourceFreshness]
    blocking_gaps: list[str] = Field(default_factory=list)
    coverage_gaps: list[str] = Field(default_factory=list)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _iso_date(value: str, *, field: str) -> str:
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是 YYYY-MM-DD: {value!r}") from exc


def _mtime_date(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()


def _sqlite_count(database: Path, table: str, expression: str = "count(*)") -> int:
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        return int(connection.execute(f"select {expression} from {table}").fetchone()[0])


def _maintenance_checkpoints(source_id: str, symbols: list[str]) -> dict[str, dict[str, Any]]:
    if not DATA_MAINTENANCE_DB.is_file() or not symbols:
        return {}
    placeholders = ",".join("?" for _ in symbols)
    try:
        with sqlite3.connect(f"file:{DATA_MAINTENANCE_DB}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"select symbol,checked_through,observed_as_of,status,last_attempted_at,"
                f"last_success_at,rows_seen,rows_written,error from refresh_checkpoints "
                f"where source_id=? and symbol in ({placeholders})",
                [source_id, *symbols],
            ).fetchall()
        return {str(row["symbol"]): dict(row) for row in rows}
    except sqlite3.Error:
        return {}


def _price_source(expected: str, symbols: list[str]) -> SourceFreshness:
    try:
        snapshot = load_price_snapshot(BASE_DB)
        per_symbol: dict[str, str] = {}
        if symbols:
            placeholders = ",".join("?" for _ in symbols)
            with sqlite3.connect(f"file:{BASE_DB}?mode=ro", uri=True) as connection:
                per_symbol = {
                    str(symbol): str(as_of)[:10]
                    for symbol, as_of in connection.execute(
                        f"select symbol,max(trade_date) from daily_prices "
                        f"where adjust='qfq' and symbol in ({placeholders}) group by symbol",
                        symbols,
                    )
                }
        missing = [symbol for symbol in symbols if symbol not in per_symbol]
        stale = [symbol for symbol in symbols if per_symbol.get(symbol, "") < expected]
        if expected and symbols:
            status: Literal["current", "stale", "observed", "missing", "error"] = (
                "stale" if missing or stale else "current"
            )
        else:
            status = "observed"
        checkpoints = _maintenance_checkpoints("tushare_daily_qfq", symbols)
        return SourceFreshness(
            source_id="daily_prices",
            label="前复权日线价格",
            source_ref="shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3::daily_prices",
            status=status,
            as_of=(
                min(per_symbol.values())
                if symbols and len(per_symbol) == len(symbols)
                else snapshot.as_of
            ),
            checked_at=_mtime_date(BASE_DB),
            expected_through=expected,
            row_count=snapshot.row_count,
            coverage_count=snapshot.symbol_count,
            details={
                "min_date": snapshot.min_date,
                "global_as_of": snapshot.as_of,
                "return_observations": snapshot.return_observation_count,
                "requested_symbols": symbols,
                "per_symbol_as_of": per_symbol,
                "missing_symbols": missing,
                "stale_symbols": stale,
                "maintenance_checkpoints": checkpoints,
            },
        )
    except Exception as exc:
        return SourceFreshness(
            source_id="daily_prices", label="前复权日线价格",
            source_ref="shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3::daily_prices",
            status="error", expected_through=expected, notes=[str(exc)],
        )


def _announcement_overlay() -> tuple[int, int, str, str, dict[str, str], list[str]]:
    record_count = 0
    latest_announcement = ""
    latest_check = ""
    symbol_checks: dict[str, str] = {}
    errors: list[str] = []
    if not ANNOUNCEMENT_REFRESH_DIR.is_dir():
        return 0, 0, "", "", {}, []
    for path in sorted(ANNOUNCEMENT_REFRESH_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            symbol = str(payload.get("symbol") or "")
            rows = payload.get("records")
            if payload.get("source") != "cninfo" or not symbol or not isinstance(rows, list):
                raise ValueError("source/symbol/records 不合法")
            checked_at = str(payload.get("checked_through") or "")[:10] or _mtime_date(path)
            checked_at = _iso_date(checked_at, field=f"{symbol}.checked_through")
            symbol_checks[symbol] = checked_at
            latest_check = max(latest_check, checked_at)
            record_count += len(rows)
            for row in rows:
                if not isinstance(row, dict) or not row.get("announcement_id"):
                    raise ValueError("records 含非法公告")
                announcement_date = _iso_date(
                    str(row.get("announcement_date") or ""), field=f"{symbol}.announcement_date"
                )
                latest_announcement = max(latest_announcement, announcement_date)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{path.name}: {exc}")
    return len(symbol_checks), record_count, latest_announcement, latest_check, symbol_checks, errors


def _announcement_source(expected_check: str, symbols: list[str]) -> SourceFreshness:
    try:
        base = load_table_snapshot(BASE_DB, table="company_announcements", date_column="announcement_date")
        base_symbol_count = _sqlite_count(BASE_DB, "company_announcements", "count(distinct symbol)")
        overlay_symbols, overlay_rows, overlay_as_of, latest_check, checks, errors = _announcement_overlay()
        missing = [symbol for symbol in symbols if symbol not in checks]
        stale = [symbol for symbol in symbols if checks.get(symbol, "") < expected_check]
        if errors:
            status: Literal["current", "stale", "observed", "missing", "error"] = "error"
        elif expected_check and (missing or stale):
            status = "stale"
        elif expected_check and symbols:
            status = "current"
        else:
            status = "observed"
        checkpoints = _maintenance_checkpoints("cninfo_announcements", symbols)
        return SourceFreshness(
            source_id="company_announcements",
            label="公司正式公告",
            source_ref="shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3::company_announcements + local_data/v8_copilot/announcement_refresh",
            status=status,
            as_of=max(base.as_of, overlay_as_of),
            checked_at=latest_check or _mtime_date(BASE_DB),
            expected_through=expected_check,
            row_count=base.row_count + overlay_rows,
            coverage_count=base_symbol_count,
            details={
                "base_as_of": base.as_of,
                "overlay_as_of": overlay_as_of,
                "overlay_symbol_count": overlay_symbols,
                "requested_symbols": symbols,
                "missing_refresh_symbols": missing,
                "stale_refresh_symbols": stale,
                "maintenance_checkpoints": checkpoints,
            },
            notes=errors,
        )
    except Exception as exc:
        return SourceFreshness(
            source_id="company_announcements", label="公司正式公告",
            source_ref="shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3::company_announcements + local_data/v8_copilot/announcement_refresh",
            status="error", expected_through=expected_check, notes=[str(exc)],
        )


def _body_cache_source() -> SourceFreshness:
    rows = 0
    latest_date = ""
    latest_check = ""
    errors: list[str] = []
    if ANNOUNCEMENT_BODY_CACHE_DIR.is_dir():
        for path in ANNOUNCEMENT_BODY_CACHE_DIR.glob("*/*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if not payload.get("announcement_id") or not payload.get("text"):
                    raise ValueError("缺 announcement_id/text")
                rows += 1
                latest_date = max(latest_date, _iso_date(
                    str(payload.get("announcement_date") or ""), field="announcement body date"
                ))
                latest_check = max(latest_check, _mtime_date(path))
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                errors.append(f"{path.name}: {exc}")
    return SourceFreshness(
        source_id="announcement_bodies", label="公告正文缓存",
        source_ref="local_data/v8_copilot/announcement_bodies",
        status="error" if errors else ("observed" if rows else "missing"),
        as_of=latest_date, checked_at=latest_check, row_count=rows,
        coverage_count=rows, notes=errors,
    )


def _episode_source() -> SourceFreshness:
    try:
        snapshot = load_episode_snapshot(EPISODE_INDEX, EPISODE_MANIFEST)
        return SourceFreshness(
            source_id="episode_index", label="事件段索引",
            source_ref="shared_data/v7/episode_index_v0/episode_index.jsonl",
            status="observed", as_of=snapshot.as_of,
            checked_at=_mtime_date(EPISODE_MANIFEST), row_count=snapshot.row_count,
            details={"builder_version": snapshot.version},
        )
    except Exception as exc:
        return SourceFreshness(
            source_id="episode_index", label="事件段索引",
            source_ref="shared_data/v7/episode_index_v0/episode_index.jsonl",
            status="error", notes=[str(exc)],
        )


def _lens_source() -> SourceFreshness:
    try:
        payload = json.loads(RELEASE_LIBRARY.read_text(encoding="utf-8"))
        records = payload.get("records")
        if not isinstance(records, list) or not payload.get("library_version"):
            raise ValueError("release library 缺 records/library_version")
        frozen_at = _iso_date(str(payload.get("frozen_at") or ""), field="lens.frozen_at")
        return SourceFreshness(
            source_id="lens_library", label="冻结 Lens 库",
            source_ref="shared_data/v7/release_library_v1/release_library.json",
            status="observed", as_of=frozen_at, checked_at=_mtime_date(RELEASE_LIBRARY),
            row_count=len(records), coverage_count=len(records),
            details={"library_version": payload["library_version"]},
        )
    except Exception as exc:
        return SourceFreshness(
            source_id="lens_library", label="冻结 Lens 库",
            source_ref="shared_data/v7/release_library_v1/release_library.json",
            status="error", notes=[str(exc)],
        )


def _optional_json_source(source_id: str, label: str, path: Path, source_ref: str) -> SourceFreshness:
    if not path.is_file():
        return SourceFreshness(
            source_id=source_id, label=label, source_ref=source_ref, status="missing",
            notes=["本地材料化尚不存在"],
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("cases")
        if not isinstance(rows, list):
            raise ValueError("缺 cases list")
        dates = [str(row.get("announcement_date") or "")[:10] for row in rows if isinstance(row, dict)]
        return SourceFreshness(
            source_id=source_id, label=label, source_ref=source_ref, status="observed",
            as_of=max(dates, default=""), checked_at=_mtime_date(path),
            row_count=len(rows), coverage_count=len({row.get("symbol") for row in rows if isinstance(row, dict)}),
            details={"materialized_at": str(payload.get("materialized_at") or "")},
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return SourceFreshness(
            source_id=source_id, label=label, source_ref=source_ref, status="error", notes=[str(exc)],
        )


def _shareholder_source() -> SourceFreshness:
    if not SHAREHOLDER_DB.is_file():
        return SourceFreshness(
            source_id="shareholder_equity", label="股东户数与股权事件",
            source_ref="shared_data/v7/shareholder_count_pilot/shareholder_count.sqlite3",
            status="missing",
        )
    try:
        with sqlite3.connect(f"file:{SHAREHOLDER_DB}?mode=ro", uri=True) as connection:
            tables = {str(row[0]) for row in connection.execute("select name from sqlite_master where type='table'")}
            details: dict[str, Any] = {}
            dates: list[str] = []
            rows = 0
            for table, date_column in (
                ("shareholder_count_snapshots", "report_date"),
                ("equity_timeline_events", "event_date"),
            ):
                if table not in tables:
                    continue
                row = connection.execute(
                    f"select max({date_column}),count(*) from {table}"
                ).fetchone()
                details[table] = {"as_of": str(row[0] or "")[:10], "row_count": int(row[1])}
                if row[0]:
                    dates.append(str(row[0])[:10])
                rows += int(row[1])
        return SourceFreshness(
            source_id="shareholder_equity", label="股东户数与股权事件",
            source_ref="shared_data/v7/shareholder_count_pilot/shareholder_count.sqlite3",
            status="observed", as_of=max(dates, default=""), checked_at=_mtime_date(SHAREHOLDER_DB),
            row_count=rows, details=details,
        )
    except Exception as exc:
        return SourceFreshness(
            source_id="shareholder_equity", label="股东户数与股权事件",
            source_ref="shared_data/v7/shareholder_count_pilot/shareholder_count.sqlite3",
            status="error", notes=[str(exc)],
        )


def _maintenance_source(symbols: list[str]) -> SourceFreshness:
    if not DATA_MAINTENANCE_DB.is_file():
        return SourceFreshness(
            source_id="maintenance_checkpoints", label="数据更新 checkpoint",
            source_ref="local_data/v8_copilot/data_maintenance.sqlite3",
            status="missing", notes=["尚未运行可恢复增量维护器。"],
        )
    try:
        with sqlite3.connect(f"file:{DATA_MAINTENANCE_DB}?mode=ro", uri=True) as connection:
            suffix = ""
            parameters: list[str] = []
            if symbols:
                placeholders = ",".join("?" for _ in symbols)
                suffix = f" where symbol in ({placeholders})"
                parameters = symbols
            row = connection.execute(
                "select count(*),max(last_attempted_at),max(last_success_at) "
                f"from refresh_checkpoints{suffix}",
                parameters,
            ).fetchone()
            failed_where = f"{suffix} and" if suffix else " where"
            failed = int(connection.execute(
                f"select count(*) from refresh_checkpoints{failed_where} status='failed'",
                parameters,
            ).fetchone()[0])
        return SourceFreshness(
            source_id="maintenance_checkpoints", label="数据更新 checkpoint",
            source_ref="local_data/v8_copilot/data_maintenance.sqlite3",
            status="error" if failed else "observed",
            checked_at=str(row[1] or "")[:10], row_count=int(row[0]),
            coverage_count=int(row[0]),
            details={
                "requested_symbols": symbols,
                "last_success_at": str(row[2] or ""),
                "failed_checkpoints": failed,
            },
            notes=["存在失败 checkpoint；上次成功游标已保留。"] if failed else [],
        )
    except sqlite3.Error as exc:
        return SourceFreshness(
            source_id="maintenance_checkpoints", label="数据更新 checkpoint",
            source_ref="local_data/v8_copilot/data_maintenance.sqlite3",
            status="error", notes=[str(exc)],
        )


def build_freshness_manifest(
    *,
    expected_price_through: str = "",
    expected_announcement_checked_through: str = "",
    research_symbols: list[str] | None = None,
) -> FreshnessManifest:
    expected_price = _iso_date(expected_price_through, field="expected_price_through") if expected_price_through else ""
    expected_announcements = (
        _iso_date(expected_announcement_checked_through, field="expected_announcement_checked_through")
        if expected_announcement_checked_through else ""
    )
    symbols = sorted(set(research_symbols or []))
    for symbol in symbols:
        if len(symbol) != 6 or not symbol.isdigit():
            raise ValueError(f"研究股票代码非法: {symbol}")
    sources = [
        _price_source(expected_price, symbols),
        _announcement_source(expected_announcements, symbols),
        _body_cache_source(),
        _episode_source(),
        _lens_source(),
        _shareholder_source(),
        _maintenance_source(symbols),
        _optional_json_source(
            "recruitment_deadlines", "公开招募截止日材料化",
            RECRUITMENT_DEADLINE_MATERIALIZATION,
            "local_data/v8_copilot/recruitment_deadlines.json",
        ),
    ]
    blocking_gaps: list[str] = []
    coverage_gaps: list[str] = []
    critical = {source.source_id: source for source in sources if source.source_id in {"daily_prices", "company_announcements"}}
    if not expected_price:
        coverage_gaps.append("未声明价格应更新到哪个交易日，当前只报告 observed。")
    if not expected_announcements:
        coverage_gaps.append("未声明公告应核查到哪一天，当前只报告 observed。")
    if (expected_price or expected_announcements) and not symbols:
        blocking_gaps.append("未声明研究股票范围，不能逐股判定价格和公告覆盖。")
    for source in sources:
        if source.status in {"error", "missing"}:
            message = f"{source.label}: {source.status}。"
            if source.source_id in {"daily_prices", "company_announcements", "episode_index", "lens_library"}:
                blocking_gaps.append(message)
            else:
                coverage_gaps.append(message)
    for source in critical.values():
        if source.status == "stale":
            blocking_gaps.append(f"{source.label}未达到声明的 freshness 目标。")
    if blocking_gaps:
        overall: Literal["ready", "gaps", "observed"] = "gaps"
    elif expected_price and expected_announcements and symbols:
        overall = "ready"
    else:
        overall = "observed"
    payload = {
        "contract_version": FRESHNESS_MANIFEST_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall,
        "expected_price_through": expected_price,
        "expected_announcement_checked_through": expected_announcements,
        "research_symbols": symbols,
        "sources": [source.model_dump(mode="json") for source in sources],
        "blocking_gaps": blocking_gaps,
        "coverage_gaps": coverage_gaps,
    }
    digest = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
    return FreshnessManifest.model_validate({**payload, "manifest_id": f"FM-{digest[:20].upper()}"})


def write_freshness_manifest(manifest: FreshnessManifest, path: Path = FRESHNESS_MANIFEST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            json.dump(manifest.model_dump(mode="json"), target, ensure_ascii=False, indent=2)
            target.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def load_freshness_manifest(path: Path = FRESHNESS_MANIFEST_PATH) -> FreshnessManifest:
    return FreshnessManifest.model_validate_json(path.read_text(encoding="utf-8"))
