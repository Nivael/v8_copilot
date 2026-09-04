"""Append-only P7 market activity facts and resumable date-only maintenance."""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from data_refresh import atomic_write_json


CONTRACT_VERSION = "market_activity_v1"
MANIFEST_VERSION = "market_activity_manifest_v1"
SOURCE = "tushare:daily+daily_basic+suspend_d+stk_limit"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MarketActivityFact(StrictModel):
    symbol: str = Field(pattern=r"^\d{6}$")
    ts_code: str
    name: str = ""
    trade_date: str
    risk_type: str = ""
    risk_type_name: str = ""
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    pre_close: float | None = None
    change: float | None = None
    pct_chg: float | None = None
    volume: float | None = None
    amount: float | None = None
    amplitude_pct: float | None = None
    turnover_rate: float | None = None
    turnover_rate_f: float | None = None
    volume_ratio: float | None = None
    total_share_10k: float | None = None
    float_share_10k: float | None = None
    free_share_10k: float | None = None
    total_mv_10k_cny: float | None = None
    circ_mv_10k_cny: float | None = None
    limit_status: int | None = None
    up_limit: float | None = None
    down_limit: float | None = None
    suspend_timing: str = ""
    suspend_type: str = ""
    suspension_status: Literal["trading", "suspended", "unknown"]
    one_price_limit: bool | None = None
    limit_state_conflict: bool = False
    terminal_phase_status: Literal["not_terminal", "terminal", "unknown"]
    eligible_for_anomaly: bool
    exclusion_reasons: list[str] = Field(default_factory=list)
    source: Literal[SOURCE] = SOURCE


class MarketActivitySnapshot(StrictModel):
    snapshot_id: str = Field(pattern=r"^MAS-[A-F0-9]{20}$")
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    trade_date: str
    membership_count: int = Field(ge=0)
    row_count: int = Field(ge=0)
    daily_row_count: int = Field(ge=0)
    daily_basic_row_count: int = Field(ge=0)
    suspend_row_count: int = Field(ge=0)
    limit_row_count: int = Field(ge=0)
    valid_turnover_rate_f_count: int = Field(ge=0)
    eligible_count: int = Field(ge=0)
    coverage_ratio: float = Field(ge=0, le=1)
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    fetched_at: str


class ActivityBootstrapResult(StrictModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    plan_id: str = Field(pattern=r"^MAP-[A-F0-9]{20}$")
    start_date: str
    through: str
    requested_date_count: int = Field(ge=0)
    completed_date_count: int = Field(ge=0)
    skipped_date_count: int = Field(ge=0)
    failed_date_count: int = Field(ge=0)
    snapshots: list[str]
    failures: dict[str, str]


class ActivityProvider(Protocol):
    def fetch_daily(self, *, trade_date: str) -> list[dict[str, Any]]: ...
    def fetch_daily_basic(self, *, trade_date: str) -> list[dict[str, Any]]: ...
    def fetch_suspend_daily(self, *, trade_date: str) -> list[dict[str, Any]]: ...
    def fetch_stock_limits(self, *, trade_date: str) -> list[dict[str, Any]]: ...


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _iso(value: Any, *, field: str = "date") -> str:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是 YYYY-MM-DD: {value!r}") from exc


def _provider_date(value: Any) -> str:
    raw = str(value or "")
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return _iso(raw, field="provider trade_date")


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _integer(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _rows_by_symbol(
    rows: list[dict[str, Any]], *, trade_date: str, allow_multiple: bool = False,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in rows:
        code = str(raw.get("ts_code") or "").strip().upper()
        symbol = code.split(".", 1)[0]
        if len(symbol) != 6 or not symbol.isdigit():
            raise ValueError(f"provider 返回非法 ts_code: {code!r}")
        if _provider_date(raw.get("trade_date")) != trade_date:
            raise ValueError(f"provider {symbol} 日期与请求不一致")
        if symbol in result and not allow_multiple and result[symbol] != raw:
            raise ValueError(f"provider 同日重复冲突: {trade_date} {symbol}")
        if symbol in result and allow_multiple:
            previous = result[symbol]
            previous["suspend_timing"] = "；".join(filter(None, [
                str(previous.get("suspend_timing") or ""),
                str(raw.get("suspend_timing") or ""),
            ]))
            previous["suspend_type"] = "；".join(filter(None, [
                str(previous.get("suspend_type") or ""),
                str(raw.get("suspend_type") or ""),
            ]))
        else:
            result[symbol] = dict(raw)
    return result


def _same_price(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return False
    return abs(left - right) <= max(0.0001, abs(right) * 1e-6)


def normalize_activity_rows(
    *,
    trade_date: str,
    memberships: list[dict[str, Any]],
    daily_rows: list[dict[str, Any]],
    daily_basic_rows: list[dict[str, Any]],
    suspend_rows: list[dict[str, Any]],
    limit_rows: list[dict[str, Any]],
    suspension_query_complete: bool = True,
) -> list[MarketActivityFact]:
    """Create exactly one auditable fact for every point-in-time ST member."""

    day = _iso(trade_date, field="trade_date")
    daily = _rows_by_symbol(daily_rows, trade_date=day)
    basics = _rows_by_symbol(daily_basic_rows, trade_date=day)
    suspensions = _rows_by_symbol(
        suspend_rows, trade_date=day, allow_multiple=True,
    )
    limits = _rows_by_symbol(limit_rows, trade_date=day)
    unique_members: dict[str, dict[str, Any]] = {}
    for member in memberships:
        symbol = str(member.get("symbol") or "").strip()
        if len(symbol) != 6 or not symbol.isdigit():
            raise ValueError(f"membership symbol 非法: {symbol!r}")
        if symbol in unique_members and unique_members[symbol] != member:
            raise ValueError(f"membership 同日重复冲突: {day} {symbol}")
        unique_members[symbol] = member

    facts: list[MarketActivityFact] = []
    for symbol in sorted(unique_members):
        member = unique_members[symbol]
        raw = daily.get(symbol, {})
        basic = basics.get(symbol, {})
        suspension = suspensions.get(symbol)
        limit = limits.get(symbol, {})
        open_value = _number(raw.get("open"))
        high = _number(raw.get("high"))
        low = _number(raw.get("low"))
        close = _number(raw.get("close"))
        pre_close = _number(raw.get("pre_close"))
        amplitude = (
            (high - low) / pre_close * 100
            if high is not None and low is not None and pre_close is not None and pre_close > 0
            else None
        )
        limit_status = _integer(basic.get("limit_status"))
        vendor_one_price = limit_status in {3, 6} if limit_status is not None else None
        up_limit = _number(limit.get("up_limit"))
        down_limit = _number(limit.get("down_limit"))
        raw_one_price = None
        if None not in (open_value, high, low, close) and limit:
            flat = _same_price(open_value, high) and _same_price(high, low) and _same_price(low, close)
            raw_one_price = bool(flat and (_same_price(close, up_limit) or _same_price(close, down_limit)))
        conflict = (
            vendor_one_price is not None
            and raw_one_price is not None
            and vendor_one_price != raw_one_price
        )
        one_price = vendor_one_price if vendor_one_price is not None else raw_one_price
        if suspension is not None:
            suspension_status: Literal["trading", "suspended", "unknown"] = "suspended"
        elif suspension_query_complete:
            suspension_status = "trading"
        else:
            suspension_status = "unknown"
        risk_text = " ".join([
            str(member.get("risk_type") or ""),
            str(member.get("risk_type_name") or ""),
            str(member.get("name") or ""),
        ])
        if "退市整理" in risk_text:
            terminal: Literal["not_terminal", "terminal", "unknown"] = "terminal"
        elif member.get("risk_type") or member.get("risk_type_name"):
            terminal = "not_terminal"
        else:
            terminal = "unknown"
        reasons: list[str] = []
        if suspension_status == "suspended":
            reasons.append("suspended")
        elif suspension_status == "unknown":
            reasons.append("suspension_status_unknown")
        if one_price is True:
            reasons.append("one_price_limit")
        elif one_price is None:
            reasons.append("limit_status_unknown")
        if conflict:
            reasons.append("limit_state_conflict")
        if terminal == "terminal":
            reasons.append("delisting_period")
        elif terminal == "unknown":
            reasons.append("terminal_phase_unknown")
        if symbol not in daily:
            reasons.append("daily_missing")
        if symbol not in basics:
            reasons.append("daily_basic_missing")
        if _number(basic.get("turnover_rate_f")) is None:
            reasons.append("turnover_rate_f_missing")
        facts.append(MarketActivityFact(
            symbol=symbol,
            ts_code=str(member.get("ts_code") or raw.get("ts_code") or basic.get("ts_code") or symbol),
            name=str(member.get("name") or ""),
            trade_date=day,
            risk_type=str(member.get("risk_type") or ""),
            risk_type_name=str(member.get("risk_type_name") or ""),
            open=open_value,
            high=high,
            low=low,
            close=close,
            pre_close=pre_close,
            change=_number(raw.get("change")),
            pct_chg=_number(raw.get("pct_chg")),
            volume=_number(raw.get("vol")),
            amount=_number(raw.get("amount")),
            amplitude_pct=round(amplitude, 8) if amplitude is not None else None,
            turnover_rate=_number(basic.get("turnover_rate")),
            turnover_rate_f=_number(basic.get("turnover_rate_f")),
            volume_ratio=_number(basic.get("volume_ratio")),
            total_share_10k=_number(basic.get("total_share")),
            float_share_10k=_number(basic.get("float_share")),
            free_share_10k=_number(basic.get("free_share")),
            total_mv_10k_cny=_number(basic.get("total_mv")),
            circ_mv_10k_cny=_number(basic.get("circ_mv")),
            limit_status=limit_status,
            up_limit=up_limit,
            down_limit=down_limit,
            suspend_timing=str((suspension or {}).get("suspend_timing") or ""),
            suspend_type=str((suspension or {}).get("suspend_type") or ""),
            suspension_status=suspension_status,
            one_price_limit=one_price,
            limit_state_conflict=conflict,
            terminal_phase_status=terminal,
            eligible_for_anomaly=not reasons,
            exclusion_reasons=reasons,
        ))
    return facts


class MarketActivityRepository:
    """Content-addressed day snapshots with append-only revisions and checkpoints."""

    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.executescript("""
            pragma foreign_keys=on;
            create table if not exists activity_snapshots (
                snapshot_id text primary key,
                contract_version text not null,
                trade_date text not null,
                membership_count integer not null,
                row_count integer not null,
                daily_row_count integer not null,
                daily_basic_row_count integer not null,
                suspend_row_count integer not null,
                limit_row_count integer not null,
                valid_turnover_rate_f_count integer not null,
                eligible_count integer not null,
                coverage_ratio real not null,
                content_digest text not null,
                fetched_at text not null
            );
            create index if not exists idx_activity_snapshot_date
                on activity_snapshots(trade_date,fetched_at);
            create table if not exists market_activity_daily (
                snapshot_id text not null,
                symbol text not null,
                trade_date text not null,
                payload_json text not null,
                primary key(snapshot_id,symbol),
                foreign key(snapshot_id) references activity_snapshots(snapshot_id)
            );
            create index if not exists idx_activity_daily_symbol_date
                on market_activity_daily(symbol,trade_date);
            create table if not exists activity_checkpoints (
                plan_id text not null,
                trade_date text not null,
                status text not null,
                snapshot_id text not null,
                error text not null,
                updated_at text not null,
                primary key(plan_id,trade_date)
            );
        """)
        return connection

    def store_snapshot(
        self,
        *,
        trade_date: str,
        facts: list[MarketActivityFact],
        daily_row_count: int,
        daily_basic_row_count: int,
        suspend_row_count: int,
        limit_row_count: int,
        fetched_at: str | None = None,
    ) -> MarketActivitySnapshot:
        day = _iso(trade_date, field="trade_date")
        if any(fact.trade_date != day for fact in facts):
            raise ValueError("activity fact 日期与 snapshot 不一致")
        if len({fact.symbol for fact in facts}) != len(facts):
            raise ValueError("activity fact 同日 symbol 重复")
        fact_payload = [fact.model_dump(mode="json") for fact in sorted(facts, key=lambda x: x.symbol)]
        digest = _digest({"contract_version": CONTRACT_VERSION, "trade_date": day, "facts": fact_payload})
        snapshot = MarketActivitySnapshot(
            snapshot_id=f"MAS-{digest[:20].upper()}",
            trade_date=day,
            membership_count=len(facts),
            row_count=len(facts),
            daily_row_count=daily_row_count,
            daily_basic_row_count=daily_basic_row_count,
            suspend_row_count=suspend_row_count,
            limit_row_count=limit_row_count,
            valid_turnover_rate_f_count=sum(fact.turnover_rate_f is not None for fact in facts),
            eligible_count=sum(fact.eligible_for_anomaly for fact in facts),
            coverage_ratio=(
                round(sum(fact.turnover_rate_f is not None for fact in facts) / len(facts), 8)
                if facts else 0.0
            ),
            content_digest=digest,
            fetched_at=fetched_at or datetime.now(timezone.utc).isoformat(),
        )
        with self._connect() as connection:
            existing = connection.execute(
                "select content_digest from activity_snapshots where snapshot_id=?",
                (snapshot.snapshot_id,),
            ).fetchone()
            if existing and str(existing[0]) != digest:
                raise ValueError("activity snapshot ID digest 冲突")
            connection.execute(
                "insert or ignore into activity_snapshots values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                tuple(snapshot.model_dump(mode="json").values()),
            )
            connection.executemany(
                "insert or ignore into market_activity_daily values (?,?,?,?)",
                [
                    (snapshot.snapshot_id, fact.symbol, day, _canonical(fact.model_dump(mode="json")))
                    for fact in facts
                ],
            )
        return snapshot

    def checkpoint(self, *, plan_id: str, trade_date: str) -> sqlite3.Row | None:
        if not self.path.is_file():
            return None
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            return connection.execute(
                "select * from activity_checkpoints where plan_id=? and trade_date=?",
                (plan_id, trade_date),
            ).fetchone()

    def record_checkpoint(
        self, *, plan_id: str, trade_date: str, status: str,
        snapshot_id: str = "", error: str = "",
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "insert into activity_checkpoints values (?,?,?,?,?,?) "
                "on conflict(plan_id,trade_date) do update set "
                "status=excluded.status,snapshot_id=excluded.snapshot_id,"
                "error=excluded.error,updated_at=excluded.updated_at",
                (plan_id, trade_date, status, snapshot_id, error, datetime.now(timezone.utc).isoformat()),
            )

    def snapshots(self, *, start_date: str = "", through: str = "") -> list[MarketActivitySnapshot]:
        if not self.path.is_file():
            return []
        clauses = []
        params: list[str] = []
        if start_date:
            clauses.append("trade_date>=?")
            params.append(_iso(start_date, field="start_date"))
        if through:
            clauses.append("trade_date<=?")
            params.append(_iso(through, field="through"))
        where = " where " + " and ".join(clauses) if clauses else ""
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "select * from activity_snapshots" + where + " order by trade_date,fetched_at",
                params,
            ).fetchall()
        return [MarketActivitySnapshot.model_validate(dict(row)) for row in rows]

    def latest_valid_snapshot(self, trade_date: str) -> MarketActivitySnapshot | None:
        day = _iso(trade_date, field="trade_date")
        if not self.path.is_file():
            return None
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "select * from activity_snapshots where trade_date=? and daily_row_count>0 "
                "and daily_basic_row_count>0 and limit_row_count>0 "
                "order by fetched_at desc,snapshot_id desc limit 1",
                (day,),
            ).fetchone()
        return MarketActivitySnapshot.model_validate(dict(row)) if row else None

    def latest_facts(self, *, start_date: str = "", through: str = "") -> list[MarketActivityFact]:
        if not self.path.is_file():
            return []
        clauses = []
        params: list[str] = []
        if start_date:
            clauses.append("s.trade_date>=?")
            params.append(_iso(start_date, field="start_date"))
        if through:
            clauses.append("s.trade_date<=?")
            params.append(_iso(through, field="through"))
        where = " where " + " and ".join(clauses) if clauses else ""
        valid_day = "s.daily_row_count>0 and s.daily_basic_row_count>0 and s.limit_row_count>0"
        if where:
            where += " and " + valid_day
        else:
            where = " where " + valid_day
        query = (
            "with ranked as (select s.*,row_number() over (partition by s.trade_date "
            "order by s.fetched_at desc,s.snapshot_id desc) rank_no from activity_snapshots s"
            + where + ") select d.payload_json from ranked s join market_activity_daily d "
            "on d.snapshot_id=s.snapshot_id where s.rank_no=1 order by d.trade_date,d.symbol"
        )
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            rows = connection.execute(query, params).fetchall()
        return [MarketActivityFact.model_validate(json.loads(row[0])) for row in rows]


def load_memberships(
    market_context_database: Path, *, start_date: str, through: str,
) -> dict[str, list[dict[str, Any]]]:
    start = _iso(start_date, field="start_date")
    end = _iso(through, field="through")
    if not market_context_database.is_file():
        raise FileNotFoundError(market_context_database)
    with sqlite3.connect(f"file:{market_context_database}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "select m.trade_date,m.symbol,m.ts_code,m.name,m.risk_type,m.risk_type_name "
            "from st_membership_daily m where m.trade_date between ? and ? "
            "and exists (select 1 from benchmark_daily b where b.benchmark_id='csi_all_share' "
            "and b.trade_date=m.trade_date) "
            "order by m.trade_date,m.symbol",
            (start, end),
        ).fetchall()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["trade_date"]), []).append(dict(row))
    return grouped


class MarketActivityBootstrapService:
    def __init__(
        self, *, provider: ActivityProvider, repository: MarketActivityRepository,
        market_context_database: Path,
    ):
        self.provider = provider
        self.repository = repository
        self.market_context_database = market_context_database

    def bootstrap(
        self, *, start_date: str, through: str, resume: bool = True,
        target_dates: list[str] | None = None,
        refresh_existing: bool = False,
        parallel_endpoints: bool = False,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> ActivityBootstrapResult:
        memberships = load_memberships(
            self.market_context_database, start_date=start_date, through=through,
        )
        if target_dates is None:
            dates = sorted(memberships)
        else:
            dates = sorted({_iso(item, field="target_date") for item in target_dates})
            outside = [day for day in dates if day < _iso(start_date) or day > _iso(through)]
            missing_membership = [day for day in dates if day not in memberships]
            if outside:
                raise ValueError(f"target_dates 超出 bootstrap 范围: {outside[:5]}")
            if missing_membership:
                raise ValueError(f"target_dates 缺 point-in-time membership: {missing_membership[:5]}")
        plan_id = f"MAP-{_digest({'start': start_date, 'through': through, 'dates': dates, 'membership': memberships})[:20].upper()}"
        snapshots: list[str] = []
        failures: dict[str, str] = {}
        skipped = 0
        for index, day in enumerate(dates, start=1):
            prior = self.repository.checkpoint(plan_id=plan_id, trade_date=day)
            if resume and prior is not None and str(prior["status"]) == "success":
                skipped += 1
                snapshots.append(str(prior["snapshot_id"]))
                continue
            existing = (
                self.repository.latest_valid_snapshot(day)
                if resume and not refresh_existing else None
            )
            if existing is not None:
                skipped += 1
                snapshots.append(existing.snapshot_id)
                self.repository.record_checkpoint(
                    plan_id=plan_id, trade_date=day, status="success",
                    snapshot_id=existing.snapshot_id,
                )
                if progress:
                    progress({"completed": index, "total": len(dates), "trade_date": day, "status": "reused"})
                continue
            try:
                operations = {
                    "daily": self.provider.fetch_daily,
                    "basics": self.provider.fetch_daily_basic,
                    "suspensions": self.provider.fetch_suspend_daily,
                    "limits": self.provider.fetch_stock_limits,
                }
                if parallel_endpoints:
                    with ThreadPoolExecutor(max_workers=4) as executor:
                        futures = {
                            key: executor.submit(operation, trade_date=day)
                            for key, operation in operations.items()
                        }
                        fetched = {key: future.result() for key, future in futures.items()}
                else:
                    fetched = {
                        key: operation(trade_date=day) for key, operation in operations.items()
                    }
                daily = fetched["daily"]
                basics = fetched["basics"]
                suspensions = fetched["suspensions"]
                limits = fetched["limits"]
                facts = normalize_activity_rows(
                    trade_date=day,
                    memberships=memberships[day],
                    daily_rows=daily,
                    daily_basic_rows=basics,
                    suspend_rows=suspensions,
                    limit_rows=limits,
                    suspension_query_complete=True,
                )
                snapshot = self.repository.store_snapshot(
                    trade_date=day,
                    facts=facts,
                    daily_row_count=len(daily),
                    daily_basic_row_count=len(basics),
                    suspend_row_count=len(suspensions),
                    limit_row_count=len(limits),
                )
                self.repository.record_checkpoint(
                    plan_id=plan_id, trade_date=day, status="success",
                    snapshot_id=snapshot.snapshot_id,
                )
                snapshots.append(snapshot.snapshot_id)
                if progress:
                    progress({"completed": index, "total": len(dates), "trade_date": day, "status": "success"})
            except Exception as exc:  # each date is an atomic auditable unit
                error = f"{type(exc).__name__}: {exc}"
                failures[day] = error
                self.repository.record_checkpoint(
                    plan_id=plan_id, trade_date=day, status="failed", error=error,
                )
                if progress:
                    progress({"completed": index, "total": len(dates), "trade_date": day, "status": "failed"})
        return ActivityBootstrapResult(
            plan_id=plan_id,
            start_date=_iso(start_date, field="start_date"),
            through=_iso(through, field="through"),
            requested_date_count=len(dates),
            completed_date_count=len(dates) - len(failures),
            skipped_date_count=skipped,
            failed_date_count=len(failures),
            snapshots=snapshots,
            failures=failures,
        )


def build_market_activity_manifest(
    repository: MarketActivityRepository, *, through: str = "",
    coverage_threshold: float = 0.95,
) -> dict[str, Any]:
    snapshots = repository.snapshots(through=through)
    latest: dict[str, MarketActivitySnapshot] = {}
    for snapshot in snapshots:
        latest[snapshot.trade_date] = snapshot
    selected = [
        latest[key] for key in sorted(latest)
        if latest[key].daily_row_count > 0
        and latest[key].daily_basic_row_count > 0
        and latest[key].limit_row_count > 0
    ]
    end = selected[-1].trade_date if selected else ""
    latest_snapshot = selected[-1] if selected else None
    payload = {
        "contract_version": MANIFEST_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": (
            "ready" if latest_snapshot and latest_snapshot.coverage_ratio >= coverage_threshold else
            "below_coverage_gate" if latest_snapshot else "unavailable"
        ),
        "checked_through": end,
        "date_count": len(selected),
        "ignored_non_trading_or_empty_snapshot_count": len(latest) - len(selected),
        "min_date": selected[0].trade_date if selected else "",
        "latest_snapshot_id": latest_snapshot.snapshot_id if latest_snapshot else "",
        "latest_membership_count": latest_snapshot.membership_count if latest_snapshot else 0,
        "latest_turnover_rate_f_coverage": latest_snapshot.coverage_ratio if latest_snapshot else 0.0,
        "coverage_threshold": coverage_threshold,
        "source": SOURCE,
        "blocking_gaps": (
            [] if latest_snapshot and latest_snapshot.coverage_ratio >= coverage_threshold
            else ["latest activity coverage is below the 95% full-universe gate"]
        ),
    }
    identity = {key: value for key, value in payload.items() if key != "generated_at"}
    payload["manifest_id"] = f"MAM-{_digest(identity)[:20].upper()}"
    return payload


def write_market_activity_manifest_set(
    payload: dict[str, Any], *, current_path: Path, manifest_directory: Path,
) -> Path:
    checked = _iso(payload["checked_through"], field="checked_through")
    manifest_directory.mkdir(parents=True, exist_ok=True)
    manifest_id = str(payload.get("manifest_id") or "")
    if not manifest_id.startswith("MAM-"):
        raise ValueError("activity manifest 缺合法 manifest_id")
    dated = manifest_directory / f"{checked}_{manifest_id}.json"
    if not dated.exists():
        atomic_write_json(dated, payload)
    if current_path.exists():
        current = json.loads(current_path.read_text(encoding="utf-8"))
        current_date = _iso(current.get("checked_through"), field="current.checked_through")
        if current_date > checked:
            return dated
    atomic_write_json(current_path, payload)
    return dated
