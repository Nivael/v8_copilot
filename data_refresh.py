"""Authorized, resumable refresh services for Tushare prices and CNINFO metadata.

This module is imported only by the dedicated data-maintenance CLI.  The answer
path remains read-only.  Checkpoints live in a separate SQLite database so a
failed or repeated pull never masquerades as research-data freshness.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field


TUSHARE_SOURCE_ID = "tushare_daily_qfq"
CNINFO_SOURCE_ID = "cninfo_announcements"
TUSHARE_ROW_SOURCE = "tushare:daily+adj_factor:qfq"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MaintenanceCheckpoint(StrictModel):
    source_id: str
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    checked_through: str = ""
    observed_as_of: str = ""
    status: Literal["success", "failed"]
    last_attempted_at: str
    last_success_at: str = ""
    rows_seen: int = Field(default=0, ge=0)
    rows_written: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str = ""


class RefreshResult(StrictModel):
    run_id: str = Field(pattern=r"^DM-[A-F0-9]{20}$")
    source_id: str
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    requested_through: str
    fetch_start: str
    status: Literal["success", "skipped"]
    rows_seen: int = Field(default=0, ge=0)
    rows_written: int = Field(default=0, ge=0)
    rows_unchanged: int = Field(default=0, ge=0)
    observed_as_of: str = ""
    checkpoint_origin: str
    full_rebase: bool = False
    notes: list[str] = Field(default_factory=list)


class TusharePriceBatch(StrictModel):
    rows: list[dict[str, Any]]
    latest_adj_factor: float | None = None


class PriceProvider(Protocol):
    def fetch_qfq(self, *, symbol: str, start_date: str, end_date: str) -> TusharePriceBatch: ...


class AnnouncementProvider(Protocol):
    def fetch(self, *, symbol: str, start_date: str, end_date: str) -> list[dict[str, Any]]: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_date(value: str, *, field: str) -> str:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是 YYYY-MM-DD: {value!r}") from exc


def _symbol(value: str) -> str:
    compact = str(value).strip()
    if len(compact) != 6 or not compact.isdigit():
        raise ValueError(f"股票代码必须是六位数字: {value!r}")
    return compact


def _back(value: str, days: int) -> str:
    return (date.fromisoformat(value) - timedelta(days=days)).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


class MaintenanceStateRepository:
    """Append-only refresh audit plus one checkpoint per source and symbol."""

    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.executescript("""
            create table if not exists refresh_checkpoints (
                source_id text not null,
                symbol text not null,
                checked_through text not null,
                observed_as_of text not null,
                status text not null,
                last_attempted_at text not null,
                last_success_at text not null,
                rows_seen integer not null,
                rows_written integer not null,
                metadata_json text not null,
                error text not null,
                primary key (source_id, symbol)
            );
            create table if not exists refresh_runs (
                run_id text primary key,
                source_id text not null,
                symbol text not null,
                fetch_start text not null,
                requested_through text not null,
                status text not null,
                rows_seen integer not null,
                rows_written integer not null,
                metadata_json text not null,
                error text not null,
                started_at text not null,
                completed_at text not null
            );
        """)
        return connection

    def get(self, source_id: str, symbol: str) -> MaintenanceCheckpoint | None:
        if not self.path.is_file():
            return None
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "select * from refresh_checkpoints where source_id=? and symbol=?",
                (source_id, symbol),
            ).fetchone()
        return self._checkpoint(row) if row else None

    def list(self) -> list[MaintenanceCheckpoint]:
        if not self.path.is_file():
            return []
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "select * from refresh_checkpoints order by source_id,symbol"
            ).fetchall()
        return [self._checkpoint(row) for row in rows]

    def record_success(
        self,
        *,
        run_id: str,
        source_id: str,
        symbol: str,
        fetch_start: str,
        checked_through: str,
        observed_as_of: str,
        rows_seen: int,
        rows_written: int,
        metadata: dict[str, Any],
        started_at: str,
    ) -> MaintenanceCheckpoint:
        completed_at = _now()
        checkpoint = MaintenanceCheckpoint(
            source_id=source_id, symbol=symbol, checked_through=checked_through,
            observed_as_of=observed_as_of, status="success",
            last_attempted_at=completed_at, last_success_at=completed_at,
            rows_seen=rows_seen, rows_written=rows_written, metadata=metadata,
        )
        with self._connect() as connection:
            connection.execute(
                "insert into refresh_runs values (?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, source_id, symbol, fetch_start, checked_through, "success",
                 rows_seen, rows_written, _canonical(metadata), "", started_at, completed_at),
            )
            connection.execute(
                "insert into refresh_checkpoints values (?,?,?,?,?,?,?,?,?,?,?) "
                "on conflict(source_id,symbol) do update set "
                "checked_through=excluded.checked_through,observed_as_of=excluded.observed_as_of,"
                "status=excluded.status,last_attempted_at=excluded.last_attempted_at,"
                "last_success_at=excluded.last_success_at,rows_seen=excluded.rows_seen,"
                "rows_written=excluded.rows_written,metadata_json=excluded.metadata_json,error=''",
                (source_id, symbol, checked_through, observed_as_of, "success", completed_at,
                 completed_at, rows_seen, rows_written, _canonical(metadata), ""),
            )
        return checkpoint

    def record_failure(
        self,
        *,
        run_id: str,
        source_id: str,
        symbol: str,
        fetch_start: str,
        requested_through: str,
        error: str,
        started_at: str,
    ) -> None:
        completed_at = _now()
        previous = self.get(source_id, symbol)
        with self._connect() as connection:
            connection.execute(
                "insert into refresh_runs values (?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, source_id, symbol, fetch_start, requested_through, "failed",
                 0, 0, "{}", error, started_at, completed_at),
            )
            connection.execute(
                "insert into refresh_checkpoints values (?,?,?,?,?,?,?,?,?,?,?) "
                "on conflict(source_id,symbol) do update set status='failed',"
                "last_attempted_at=excluded.last_attempted_at,error=excluded.error",
                (
                    source_id, symbol,
                    previous.checked_through if previous else "",
                    previous.observed_as_of if previous else "",
                    "failed", completed_at,
                    previous.last_success_at if previous else "",
                    previous.rows_seen if previous else 0,
                    previous.rows_written if previous else 0,
                    _canonical(previous.metadata if previous else {}), error,
                ),
            )

    @staticmethod
    def _checkpoint(row: sqlite3.Row) -> MaintenanceCheckpoint:
        return MaintenanceCheckpoint(
            source_id=str(row["source_id"]), symbol=str(row["symbol"]),
            checked_through=str(row["checked_through"]),
            observed_as_of=str(row["observed_as_of"]), status=str(row["status"]),
            last_attempted_at=str(row["last_attempted_at"]),
            last_success_at=str(row["last_success_at"]), rows_seen=int(row["rows_seen"]),
            rows_written=int(row["rows_written"]), metadata=json.loads(row["metadata_json"]),
            error=str(row["error"]),
        )


class TushareHttpClient:
    def __init__(
        self,
        *,
        token: str | None = None,
        url: str | None = None,
        timeout_seconds: int = 20,
    ):
        self.token = str(token or os.environ.get("TUSHARE_TOKEN", "")).strip()
        self.url = str(url or os.environ.get("TUSHARE_HTTP_URL", "https://api.tushare.pro")).strip()
        self.timeout_seconds = timeout_seconds
        if not self.token:
            raise ValueError("缺少 TUSHARE_TOKEN；token 只能放在本地环境或 secrets 文件中")

    def _query(self, api_name: str, *, params: dict[str, str], fields: str) -> list[dict[str, Any]]:
        body = json.dumps({
            "api_name": api_name, "token": self.token, "params": params, "fields": fields,
        }).encode("utf-8")
        request = Request(
            self.url, data=body,
            headers={"Content-Type": "application/json", "User-Agent": "st-research-v8-maintainer/1.0"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if int(payload.get("code") or 0) != 0:
            raise RuntimeError(f"Tushare {api_name} 返回错误: {payload.get('msg') or 'unknown'}")
        data = payload.get("data") or {}
        names = list(data.get("fields") or [])
        return [dict(zip(names, item, strict=False)) for item in list(data.get("items") or [])]

    def fetch_qfq(self, *, symbol: str, start_date: str, end_date: str) -> TusharePriceBatch:
        compact = _symbol(symbol)
        start = _iso_date(start_date, field="start_date").replace("-", "")
        end = _iso_date(end_date, field="end_date").replace("-", "")
        params = {"ts_code": self._ts_code(compact), "start_date": start, "end_date": end}
        daily = self._query(
            "daily", params=params,
            fields="ts_code,trade_date,open,high,low,close,vol,amount,pct_chg,change",
        )
        factors = self._query(
            "adj_factor", params=params, fields="ts_code,trade_date,adj_factor",
        )
        factor_by_date = {
            str(row.get("trade_date") or ""): float(row["adj_factor"])
            for row in factors if row.get("trade_date") and row.get("adj_factor") not in (None, "")
        }
        latest_factor = factor_by_date.get(max(factor_by_date)) if factor_by_date else None
        rows: list[dict[str, Any]] = []
        for raw in daily:
            raw_date = str(raw.get("trade_date") or "")
            if len(raw_date) != 8:
                continue
            factor = factor_by_date.get(raw_date)
            if latest_factor is None or factor is None:
                raise ValueError(f"Tushare {compact} {raw_date} 缺复权因子，拒绝写入伪 qfq")
            scale = factor / latest_factor
            rows.append({
                "symbol": compact,
                "trade_date": f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}",
                "adjust": "qfq",
                "open": _scaled(raw.get("open"), scale),
                "high": _scaled(raw.get("high"), scale),
                "low": _scaled(raw.get("low"), scale),
                "close": _scaled(raw.get("close"), scale),
                "volume": _number(raw.get("vol")),
                "amount": _number(raw.get("amount")),
                "amplitude": None,
                "pct_change": _number(raw.get("pct_chg")),
                "change_amount": _scaled(raw.get("change"), scale),
                "turnover_rate": None,
                "source": TUSHARE_ROW_SOURCE,
            })
        unique = {row["trade_date"]: row for row in rows}
        return TusharePriceBatch(
            rows=[unique[key] for key in sorted(unique)], latest_adj_factor=latest_factor,
        )

    @staticmethod
    def _ts_code(symbol: str) -> str:
        if symbol.startswith(("5", "6", "9")):
            suffix = "SH"
        elif symbol.startswith(("0", "2", "3")):
            suffix = "SZ"
        else:
            suffix = "BJ"
        return f"{symbol}.{suffix}"


class CninfoHttpClient:
    URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"

    def __init__(self, *, timeout_seconds: int = 20, page_size: int = 50, max_pages: int = 100):
        self.timeout_seconds = timeout_seconds
        self.page_size = page_size
        self.max_pages = max_pages

    def fetch(self, *, symbol: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
        compact = _symbol(symbol)
        start = _iso_date(start_date, field="start_date")
        end = _iso_date(end_date, field="end_date")
        records: dict[str, dict[str, Any]] = {}
        for page in range(1, self.max_pages + 1):
            form = urlencode({
                "pageNum": str(page), "pageSize": str(self.page_size), "column": "",
                "tabName": "fulltext", "plate": "", "stock": "", "searchkey": compact,
                "secid": "", "category": "", "trade": "", "seDate": f"{start}~{end}",
                "sortName": "", "sortType": "", "isHLtitle": "true",
            }).encode("utf-8")
            request = Request(
                self.URL, data=form,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "User-Agent": "Mozilla/5.0 st-research-v8-maintainer/1.0",
                    "Referer": "https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
                    "Accept": "application/json, text/plain, */*",
                },
                method="POST",
            )
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            items = list(payload.get("announcements") or [])
            if not items:
                break
            for item in items:
                row = self._normalize(item, compact)
                if row:
                    records[row["announcement_id"]] = row
            if len(items) < self.page_size:
                break
        else:
            raise RuntimeError(f"CNINFO {compact} 分页达到安全上限 {self.max_pages}")
        return sorted(
            records.values(), key=lambda row: (row["announcement_date"], row["announcement_id"]),
            reverse=True,
        )

    @staticmethod
    def _normalize(item: dict[str, Any], symbol: str) -> dict[str, Any] | None:
        sec_code = str(item.get("secCode") or "")
        if sec_code and sec_code != symbol:
            return None
        millis = item.get("announcementTime")
        if isinstance(millis, (int, float)):
            announcement_date = datetime.fromtimestamp(
                millis / 1000, tz=ZoneInfo("Asia/Shanghai")
            ).date().isoformat()
        else:
            announcement_date = str(millis or "")[:10]
            try:
                announcement_date = date.fromisoformat(announcement_date).isoformat()
            except ValueError:
                return None
        title = unescape(re.sub(r"<[^>]+>", "", str(item.get("announcementTitle") or ""))).strip()
        announcement_id = str(item.get("announcementId") or "").strip()
        if not title:
            return None
        if not announcement_id:
            seed = f"{symbol}|{announcement_date}|{title}"
            announcement_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
        adjunct = str(item.get("adjunctUrl") or "").lstrip("/")
        pdf_url = f"https://static.cninfo.com.cn/{adjunct}" if adjunct else None
        event_time = f"{announcement_date}T00:00:00+08:00"
        return {
            "announcement_id": announcement_id, "symbol": symbol,
            "event_time": event_time, "announcement_date": announcement_date,
            "announcement_type": str(item.get("category") or "公告"),
            "published_at": event_time, "title": title, "url": pdf_url,
            "body_text": None, "pdf_url": pdf_url, "page_count": None,
            "security_name": unescape(re.sub(r"<[^>]+>", "", str(item.get("secName") or ""))).strip(),
            "raw_item": item,
        }


class PriceRefreshService:
    def __init__(self, *, database: Path, state: MaintenanceStateRepository, provider: PriceProvider):
        self.database = database
        self.state = state
        self.provider = provider

    def refresh(
        self,
        *,
        symbol: str,
        through: str,
        start_date: str = "",
        overlap_days: int = 7,
        force: bool = False,
    ) -> RefreshResult:
        compact = _symbol(symbol)
        target = _iso_date(through, field="through")
        observed_min, observed_max = self._bounds(compact)
        checkpoint = self.state.get(TUSHARE_SOURCE_ID, compact)
        if checkpoint and checkpoint.status == "success" and checkpoint.checked_through >= target and not force:
            return RefreshResult(
                run_id=f"DM-{uuid4().hex[:20].upper()}", source_id=TUSHARE_SOURCE_ID,
                symbol=compact, requested_through=target, fetch_start="", status="skipped",
                observed_as_of=observed_max, checkpoint_origin="maintenance_checkpoint",
                notes=[f"已成功核查到 {checkpoint.checked_through}，未重复请求 Tushare。"],
            )
        if start_date:
            fetch_start = _iso_date(start_date, field="start_date")
            origin = "explicit_start"
        else:
            cursor = checkpoint.checked_through if checkpoint and checkpoint.checked_through else observed_max
            if not cursor:
                raise ValueError(f"{compact} 没有价格基线；首次刷新必须传 --start-date")
            fetch_start = _back(cursor, overlap_days)
            origin = "maintenance_checkpoint" if checkpoint else "canonical_price_max"
        if fetch_start > target:
            fetch_start = target
        run_id = f"DM-{uuid4().hex[:20].upper()}"
        started = _now()
        full_rebase = False
        try:
            batch = self.provider.fetch_qfq(symbol=compact, start_date=fetch_start, end_date=target)
            previous_factor = checkpoint.metadata.get("latest_adj_factor") if checkpoint else None
            factor_changed = (
                previous_factor is not None and batch.latest_adj_factor is not None
                and abs(float(previous_factor) - batch.latest_adj_factor) > 1e-10
            )
            basis_mismatch = previous_factor is None and self._qfq_basis_mismatch(compact, batch.rows)
            if (factor_changed or basis_mismatch) and observed_min and fetch_start > observed_min:
                fetch_start = observed_min
                batch = self.provider.fetch_qfq(symbol=compact, start_date=fetch_start, end_date=target)
                full_rebase = True
            written, unchanged = self._upsert_changed(compact, batch.rows)
            _, new_max = self._bounds(compact)
            metadata = {
                "provider": "tushare", "adjust": "qfq", "latest_adj_factor": batch.latest_adj_factor,
                "overlap_days": overlap_days, "full_rebase": full_rebase,
            }
            self.state.record_success(
                run_id=run_id, source_id=TUSHARE_SOURCE_ID, symbol=compact,
                fetch_start=fetch_start, checked_through=target, observed_as_of=new_max,
                rows_seen=len(batch.rows), rows_written=written, metadata=metadata,
                started_at=started,
            )
            return RefreshResult(
                run_id=run_id, source_id=TUSHARE_SOURCE_ID, symbol=compact,
                requested_through=target, fetch_start=fetch_start, status="success",
                rows_seen=len(batch.rows), rows_written=written, rows_unchanged=unchanged,
                observed_as_of=new_max, checkpoint_origin=origin, full_rebase=full_rebase,
            )
        except Exception as exc:
            self.state.record_failure(
                run_id=run_id, source_id=TUSHARE_SOURCE_ID, symbol=compact,
                fetch_start=fetch_start, requested_through=target,
                error=f"{type(exc).__name__}: {exc}", started_at=started,
            )
            raise

    def _bounds(self, symbol: str) -> tuple[str, str]:
        if not self.database.is_file():
            raise FileNotFoundError(self.database)
        with sqlite3.connect(self.database) as connection:
            columns = {str(row[1]) for row in connection.execute("pragma table_info(daily_prices)")}
            required = {"symbol", "trade_date", "adjust", "open", "high", "low", "close", "source"}
            if not required.issubset(columns):
                raise ValueError(f"daily_prices schema 缺字段: {sorted(required - columns)}")
            row = connection.execute(
                "select min(trade_date),max(trade_date) from daily_prices where symbol=? and adjust='qfq'",
                (symbol,),
            ).fetchone()
        return str(row[0] or "")[:10], str(row[1] or "")[:10]

    def _qfq_basis_mismatch(self, symbol: str, rows: list[dict[str, Any]]) -> bool:
        closes = {
            str(row.get("trade_date") or ""): row.get("close")
            for row in rows if row.get("trade_date") and row.get("close") is not None
        }
        if not closes:
            return False
        placeholders = ",".join("?" for _ in closes)
        with sqlite3.connect(f"file:{self.database}?mode=ro", uri=True) as connection:
            existing = connection.execute(
                f"select trade_date,close from daily_prices where symbol=? and adjust='qfq' "
                f"and trade_date in ({placeholders})",
                [symbol, *closes],
            ).fetchall()
        return any(
            current is not None
            and abs(float(current) - float(closes[str(trade_date)])) > 1e-5
            for trade_date, current in existing
        )

    def _upsert_changed(self, symbol: str, rows: list[dict[str, Any]]) -> tuple[int, int]:
        unique = {str(row.get("trade_date") or ""): row for row in rows}
        if not unique:
            return 0, 0
        dates = sorted(unique)
        with sqlite3.connect(self.database) as connection:
            connection.row_factory = sqlite3.Row
            existing = {
                str(row["trade_date"]): dict(row)
                for row in connection.execute(
                    "select trade_date,open,high,low,close,volume,amount,amplitude,pct_change,"
                    "change_amount,turnover_rate,source from daily_prices "
                    "where symbol=? and adjust='qfq' and trade_date between ? and ?",
                    (symbol, dates[0], dates[-1]),
                )
            }
            changed: list[dict[str, Any]] = []
            fields = (
                "open", "high", "low", "close", "volume", "amount", "amplitude",
                "pct_change", "change_amount", "turnover_rate", "source",
            )
            for trade_date in dates:
                row = unique[trade_date]
                previous = existing.get(trade_date)
                if previous and all(previous.get(field) == row.get(field) for field in fields):
                    continue
                changed.append(row)
            connection.executemany(
                "insert into daily_prices (symbol,trade_date,adjust,open,high,low,close,volume,"
                "amount,amplitude,pct_change,change_amount,turnover_rate,source) "
                "values (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "on conflict(symbol,trade_date,adjust) do update set "
                "open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,"
                "volume=excluded.volume,amount=excluded.amount,amplitude=excluded.amplitude,"
                "pct_change=excluded.pct_change,change_amount=excluded.change_amount,"
                "turnover_rate=excluded.turnover_rate,source=excluded.source,fetched_at=current_timestamp",
                [(
                    symbol, row["trade_date"], "qfq", row.get("open"), row.get("high"),
                    row.get("low"), row.get("close"), row.get("volume"), row.get("amount"),
                    row.get("amplitude"), row.get("pct_change"), row.get("change_amount"),
                    row.get("turnover_rate"), row.get("source") or TUSHARE_ROW_SOURCE,
                ) for row in changed],
            )
        return len(changed), len(rows) - len(changed)


class AnnouncementRefreshService:
    def __init__(
        self,
        *,
        refresh_dir: Path,
        base_database: Path,
        state: MaintenanceStateRepository,
        provider: AnnouncementProvider,
    ):
        self.refresh_dir = refresh_dir
        self.base_database = base_database
        self.state = state
        self.provider = provider

    def refresh(
        self,
        *,
        symbol: str,
        through: str,
        start_date: str = "",
        overlap_days: int = 14,
        force: bool = False,
    ) -> RefreshResult:
        compact = _symbol(symbol)
        target = _iso_date(through, field="through")
        current, legacy_checked = self._load_overlay(compact)
        checkpoint = self.state.get(CNINFO_SOURCE_ID, compact)
        if checkpoint and checkpoint.status == "success" and checkpoint.checked_through >= target and not force:
            return RefreshResult(
                run_id=f"DM-{uuid4().hex[:20].upper()}", source_id=CNINFO_SOURCE_ID,
                symbol=compact, requested_through=target, fetch_start="", status="skipped",
                observed_as_of=max((str(row.get("announcement_date") or "") for row in current), default=""),
                checkpoint_origin="maintenance_checkpoint",
                notes=[f"已成功核查到 {checkpoint.checked_through}，未重复请求 CNINFO。"],
            )
        if start_date:
            fetch_start = _iso_date(start_date, field="start_date")
            origin = "explicit_start"
        else:
            cursor = checkpoint.checked_through if checkpoint and checkpoint.checked_through else legacy_checked
            origin = "maintenance_checkpoint" if checkpoint else "legacy_overlay_mtime"
            if not cursor:
                cursor = self._base_max(compact)
                origin = "canonical_announcement_max"
            if not cursor:
                raise ValueError(f"{compact} 没有公告基线；首次刷新必须传 --start-date")
            fetch_start = _back(cursor, overlap_days)
        if fetch_start > target:
            fetch_start = target
        run_id = f"DM-{uuid4().hex[:20].upper()}"
        started = _now()
        try:
            fetched = self.provider.fetch(symbol=compact, start_date=fetch_start, end_date=target)
            merged = {str(row.get("announcement_id") or ""): row for row in current}
            changed = 0
            unchanged = 0
            for row in fetched:
                normalized = validate_announcement_row(row, compact)
                announcement_id = normalized["announcement_id"]
                previous = merged.get(announcement_id, {})
                candidate = {**previous, **normalized}
                if previous.get("body_text") and not normalized.get("body_text"):
                    candidate["body_text"] = previous["body_text"]
                if previous and _canonical(previous) == _canonical(candidate):
                    unchanged += 1
                else:
                    changed += 1
                merged[announcement_id] = candidate
            records = sorted(
                merged.values(),
                key=lambda row: (str(row.get("announcement_date") or ""), str(row.get("announcement_id") or "")),
                reverse=True,
            )
            payload = {
                "symbol": compact, "source": "cninfo", "count": len(records),
                "include_body": False, "fetched_at": _now(), "checked_through": target,
                "fetch_window": {"start": fetch_start, "end": target, "overlap_days": overlap_days},
                "records": records,
            }
            destination = self.refresh_dir / f"{compact}.json"
            atomic_write_json(destination, payload)
            observed = max((str(row.get("announcement_date") or "") for row in records), default="")
            self.state.record_success(
                run_id=run_id, source_id=CNINFO_SOURCE_ID, symbol=compact,
                fetch_start=fetch_start, checked_through=target, observed_as_of=observed,
                rows_seen=len(fetched), rows_written=changed,
                metadata={"provider": "cninfo", "overlap_days": overlap_days, "overlay_count": len(records)},
                started_at=started,
            )
            return RefreshResult(
                run_id=run_id, source_id=CNINFO_SOURCE_ID, symbol=compact,
                requested_through=target, fetch_start=fetch_start, status="success",
                rows_seen=len(fetched), rows_written=changed, rows_unchanged=unchanged,
                observed_as_of=observed, checkpoint_origin=origin,
            )
        except Exception as exc:
            self.state.record_failure(
                run_id=run_id, source_id=CNINFO_SOURCE_ID, symbol=compact,
                fetch_start=fetch_start, requested_through=target,
                error=f"{type(exc).__name__}: {exc}", started_at=started,
            )
            raise

    def _load_overlay(self, symbol: str) -> tuple[list[dict[str, Any]], str]:
        path = self.refresh_dir / f"{symbol}.json"
        if not path.is_file():
            return [], ""
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("source") != "cninfo" or str(payload.get("symbol") or "") != symbol:
            raise ValueError(f"现有公告 overlay 非法: {path.name}")
        rows = payload.get("records")
        if not isinstance(rows, list):
            raise ValueError(f"现有公告 overlay 缺 records: {path.name}")
        validated = [validate_announcement_row(row, symbol) for row in rows]
        checked = str(payload.get("checked_through") or "")[:10]
        if not checked:
            checked = datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
        return validated, checked

    def _base_max(self, symbol: str) -> str:
        if not self.base_database.is_file():
            return ""
        with sqlite3.connect(f"file:{self.base_database}?mode=ro", uri=True) as connection:
            row = connection.execute(
                "select max(announcement_date) from company_announcements where symbol=?", (symbol,)
            ).fetchone()
        return str(row[0] or "")[:10]


def validate_announcement_row(row: dict[str, Any], symbol: str) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("公告 records 必须全部为 object")
    normalized = dict(row)
    announcement_id = str(normalized.get("announcement_id") or "").strip()
    announcement_date = _iso_date(str(normalized.get("announcement_date") or ""), field="announcement_date")
    title = str(normalized.get("title") or "").strip()
    row_symbol = str(normalized.get("symbol") or symbol)
    if not announcement_id or not title or row_symbol != symbol:
        raise ValueError("公告增量存在缺失字段或 symbol 不一致")
    normalized.update({
        "announcement_id": announcement_id, "announcement_date": announcement_date,
        "symbol": symbol, "title": title,
    })
    return normalized


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            json.dump(payload, target, ensure_ascii=False, indent=2)
            target.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _scaled(value: Any, scale: float) -> float | None:
    number = _number(value)
    return round(number * scale, 6) if number is not None else None
