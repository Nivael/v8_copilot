"""Versioned benchmark series and transparent ST-sector index construction."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from data_refresh import atomic_write_json


MARKET_CONTEXT_CONTRACT_VERSION = "v8_market_context_v1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BenchmarkDefinition(StrictModel):
    benchmark_id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    kind: Literal["broad_market", "size", "st_sector_internal", "st_sector_vendor"]
    provider: str
    provider_code: str = ""
    methodology_version: str
    return_type: Literal["price_return", "total_return"] = "price_return"
    evidence_role: Literal["canonical", "context_only"] = "canonical"
    notes: list[str] = Field(default_factory=list)


BROAD_MARKET = BenchmarkDefinition(
    benchmark_id="csi_all_share",
    name="中证全指",
    kind="broad_market",
    provider="tushare:index_daily",
    provider_code="000985.CSI",
    methodology_version="provider_series_v1",
    notes=["用于大盘方向参照，不代表 ST 风格。"],
)

CSI_2000 = BenchmarkDefinition(
    benchmark_id="csi_2000",
    name="中证2000",
    kind="size",
    provider="tushare:index_daily",
    provider_code="932000.CSI",
    methodology_version="provider_series_v1",
    notes=[
        "用于中小盘风险偏好与资金风格参照。",
        "价格指数不是资金净流入数据，不得据此陈述净流入金额。",
    ],
)

ST_EQUAL_WEIGHT = BenchmarkDefinition(
    benchmark_id="st_equal_weight_v1",
    name="ST 等权研究指数 v1",
    kind="st_sector_internal",
    provider="derived:tushare_stock_st+tushare_daily_qfq",
    methodology_version="equal_weight_daily_membership_v1",
    notes=[
        "按当日 stock_st 名单及当日个股前复权收益等权计算。",
        "停牌或缺收益的成员不填零；通过 coverage_ratio 明示覆盖率。",
    ],
)

PROVIDER_BENCHMARKS = (BROAD_MARKET, CSI_2000)
CANONICAL_BENCHMARK_POOL = (ST_EQUAL_WEIGHT, CSI_2000, BROAD_MARKET)


class BenchmarkPoint(StrictModel):
    benchmark_id: str
    trade_date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    pct_change: float | None = None
    member_count: int | None = Field(default=None, ge=0)
    valid_member_count: int | None = Field(default=None, ge=0)
    coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    source: str


class IndexDailyProvider(Protocol):
    def fetch_index_daily(
        self, *, ts_code: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]: ...


class HistoricalMembershipProvider(Protocol):
    def fetch_st_universe_range(
        self,
        *,
        start_date: str,
        end_date: str,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]: ...


class HistoricalMembershipRow(StrictModel):
    trade_date: str
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    ts_code: str
    name: str
    risk_type: str = ""
    risk_type_name: str = ""
    source: Literal["tushare:stock_st"] = "tushare:stock_st"


class MembershipBackfillResult(StrictModel):
    range_id: str
    start_date: str
    end_date: str
    page_size: int
    pages_fetched: int
    rows_seen: int
    stored_rows: int
    distinct_dates: int
    next_offset: int
    status: Literal["complete", "partial"]


def _iso_date(value: str, *, field: str) -> str:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是 YYYY-MM-DD: {value!r}") from exc


def normalize_index_rows(
    *, definition: BenchmarkDefinition, rows: list[dict[str, Any]]
) -> list[BenchmarkPoint]:
    if not definition.provider_code:
        raise ValueError(f"{definition.benchmark_id} 缺 provider_code")
    unique: dict[str, BenchmarkPoint] = {}
    for raw in rows:
        code = str(raw.get("ts_code") or "").upper()
        if code != definition.provider_code:
            raise ValueError(f"指数响应代码 {code!r} 与 {definition.provider_code} 不一致")
        raw_date = str(raw.get("trade_date") or "")
        if len(raw_date) != 8 or not raw_date.isdigit():
            raise ValueError(f"指数响应日期非法: {raw_date!r}")
        trade_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        unique[trade_date] = BenchmarkPoint(
            benchmark_id=definition.benchmark_id,
            trade_date=trade_date,
            open=_number(raw.get("open")),
            high=_number(raw.get("high")),
            low=_number(raw.get("low")),
            close=_number(raw.get("close")),
            pct_change=_number(raw.get("pct_chg")),
            source=definition.provider,
        )
    return [unique[key] for key in sorted(unique)]


def build_st_equal_weight_points(
    *,
    membership_by_date: dict[str, set[str]],
    returns_by_date: dict[str, dict[str, float | None]],
    base_level: float = 1000.0,
) -> list[BenchmarkPoint]:
    """Build a survivorship-safe, equal-weight ST price-return series.

    Membership must be supplied for every computed day; the function never
    substitutes today's universe for historical dates.
    """

    if base_level <= 0:
        raise ValueError("base_level 必须大于 0")
    level = float(base_level)
    points: list[BenchmarkPoint] = []
    for trade_date in sorted(returns_by_date):
        _iso_date(trade_date, field="trade_date")
        if trade_date not in membership_by_date:
            raise ValueError(f"{trade_date} 缺当日 ST membership，拒绝引入幸存者偏差")
        members = membership_by_date[trade_date]
        observed = returns_by_date[trade_date]
        valid = [float(observed[symbol]) for symbol in members if observed.get(symbol) is not None]
        member_count = len(members)
        valid_count = len(valid)
        coverage = valid_count / member_count if member_count else 0.0
        daily_return = sum(valid) / valid_count if valid else None
        if daily_return is not None:
            level *= 1 + daily_return / 100.0
        points.append(BenchmarkPoint(
            benchmark_id=ST_EQUAL_WEIGHT.benchmark_id,
            trade_date=trade_date,
            close=round(level, 6) if daily_return is not None else None,
            pct_change=round(daily_return, 8) if daily_return is not None else None,
            member_count=member_count,
            valid_member_count=valid_count,
            coverage_ratio=round(coverage, 8),
            source=ST_EQUAL_WEIGHT.provider,
        ))
    return points


class MarketContextRepository:
    """Dedicated mutable store; it never shares tables with the stock base DB."""

    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.executescript("""
            create table if not exists benchmark_definitions (
                benchmark_id text primary key,
                contract_version text not null,
                definition_json text not null,
                updated_at text not null
            );
            create table if not exists benchmark_daily (
                benchmark_id text not null,
                trade_date text not null,
                open real,
                high real,
                low real,
                close real,
                pct_change real,
                member_count integer,
                valid_member_count integer,
                coverage_ratio real,
                source text not null,
                fetched_at text not null,
                primary key (benchmark_id, trade_date)
            );
            create table if not exists st_membership_daily (
                trade_date text not null,
                symbol text not null,
                ts_code text not null,
                name text not null,
                risk_type text not null,
                risk_type_name text not null,
                source text not null,
                fetched_at text not null,
                primary key (trade_date, symbol)
            );
            create table if not exists membership_backfills (
                range_id text primary key,
                start_date text not null,
                end_date text not null,
                page_size integer not null,
                next_offset integer not null,
                status text not null,
                rows_seen integer not null,
                updated_at text not null
            );
        """)
        return connection

    def upsert(
        self, *, definition: BenchmarkDefinition, points: list[BenchmarkPoint]
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        definition_json = json.dumps(
            definition.model_dump(mode="json"), ensure_ascii=False, sort_keys=True
        )
        for point in points:
            if point.benchmark_id != definition.benchmark_id:
                raise ValueError("benchmark point 与 definition 不一致")
        with self._connect() as connection:
            existing = connection.execute(
                "select definition_json from benchmark_definitions where benchmark_id=?",
                (definition.benchmark_id,),
            ).fetchone()
            if existing and str(existing[0]) != definition_json:
                raise ValueError(
                    f"benchmark definition 已冻结；请发布新的 benchmark_id: "
                    f"{definition.benchmark_id}"
                )
            connection.execute(
                "insert or ignore into benchmark_definitions values (?,?,?,?)",
                (
                    definition.benchmark_id,
                    MARKET_CONTEXT_CONTRACT_VERSION,
                    definition_json,
                    now,
                ),
            )
            connection.executemany(
                "insert into benchmark_daily values (?,?,?,?,?,?,?,?,?,?,?,?) "
                "on conflict(benchmark_id,trade_date) do update set "
                "open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,"
                "pct_change=excluded.pct_change,member_count=excluded.member_count,"
                "valid_member_count=excluded.valid_member_count,"
                "coverage_ratio=excluded.coverage_ratio,source=excluded.source,"
                "fetched_at=excluded.fetched_at",
                [(
                    point.benchmark_id,
                    point.trade_date,
                    point.open,
                    point.high,
                    point.low,
                    point.close,
                    point.pct_change,
                    point.member_count,
                    point.valid_member_count,
                    point.coverage_ratio,
                    point.source,
                    now,
                ) for point in points],
            )
        return len(points)

    def bounds(self, benchmark_id: str) -> tuple[str, str, int]:
        if not self.path.is_file():
            return "", "", 0
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            row = connection.execute(
                "select min(trade_date),max(trade_date),count(*) from benchmark_daily "
                "where benchmark_id=?",
                (benchmark_id,),
            ).fetchone()
        return str(row[0] or ""), str(row[1] or ""), int(row[2] or 0)

    def membership_state(self, range_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "select * from membership_backfills where range_id=?", (range_id,)
            ).fetchone()
        return dict(row) if row else None

    def write_membership_page(
        self,
        *,
        range_id: str,
        start_date: str,
        end_date: str,
        page_size: int,
        next_offset: int,
        rows_seen: int,
        rows: list[HistoricalMembershipRow],
        complete: bool,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.executemany(
                "insert into st_membership_daily values (?,?,?,?,?,?,?,?) "
                "on conflict(trade_date,symbol) do update set "
                "ts_code=excluded.ts_code,name=excluded.name,risk_type=excluded.risk_type,"
                "risk_type_name=excluded.risk_type_name,source=excluded.source,"
                "fetched_at=excluded.fetched_at",
                [(
                    row.trade_date, row.symbol, row.ts_code, row.name,
                    row.risk_type, row.risk_type_name, row.source, now,
                ) for row in rows],
            )
            connection.execute(
                "insert into membership_backfills values (?,?,?,?,?,?,?,?) "
                "on conflict(range_id) do update set "
                "next_offset=excluded.next_offset,status=excluded.status,"
                "rows_seen=excluded.rows_seen,updated_at=excluded.updated_at",
                (
                    range_id, start_date, end_date, page_size, next_offset,
                    "complete" if complete else "partial", rows_seen, now,
                ),
            )

    def membership_bounds(self) -> tuple[str, str, int, int]:
        with self._connect() as connection:
            row = connection.execute(
                "select min(trade_date),max(trade_date),count(*),"
                "count(distinct trade_date) from st_membership_daily"
            ).fetchone()
        return str(row[0] or ""), str(row[1] or ""), int(row[2] or 0), int(row[3] or 0)

    def upsert_membership_rows(self, rows: list[HistoricalMembershipRow]) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.executemany(
                "insert into st_membership_daily values (?,?,?,?,?,?,?,?) "
                "on conflict(trade_date,symbol) do update set "
                "ts_code=excluded.ts_code,name=excluded.name,risk_type=excluded.risk_type,"
                "risk_type_name=excluded.risk_type_name,source=excluded.source,"
                "fetched_at=excluded.fetched_at",
                [(
                    row.trade_date, row.symbol, row.ts_code, row.name,
                    row.risk_type, row.risk_type_name, row.source, now,
                ) for row in rows],
            )
        return len(rows)

    def missing_membership_trading_dates(
        self, *, start_date: str, end_date: str
    ) -> list[str]:
        start = _iso_date(start_date, field="start_date")
        end = _iso_date(end_date, field="end_date")
        with self._connect() as connection:
            return [str(row[0]) for row in connection.execute(
                "select b.trade_date from benchmark_daily b "
                "where b.benchmark_id=? and b.trade_date between ? and ? "
                "and not exists (select 1 from st_membership_daily m "
                "where m.trade_date=b.trade_date) order by b.trade_date",
                (BROAD_MARKET.benchmark_id, start, end),
            )]

    def materialize_st_equal_weight(
        self,
        *,
        price_database: Path,
        start_date: str,
        end_date: str,
        base_level: float | None = None,
    ) -> list[BenchmarkPoint]:
        start = _iso_date(start_date, field="start_date")
        end = _iso_date(end_date, field="end_date")
        if not price_database.is_file():
            raise FileNotFoundError(f"价格数据库不存在: {price_database}")
        with self._connect() as connection:
            if base_level is None:
                prior = connection.execute(
                    "select close from benchmark_daily where benchmark_id=? "
                    "and trade_date<? and close is not null order by trade_date desc limit 1",
                    (ST_EQUAL_WEIGHT.benchmark_id, start),
                ).fetchone()
                starting_level = float(prior[0]) if prior else 1000.0
            else:
                starting_level = float(base_level)
            connection.execute(
                "attach database ? as research",
                (str(price_database),),
            )
            aggregates = connection.execute(
                "select m.trade_date,count(*) as member_count,"
                "count(p.pct_change) as valid_count,avg(p.pct_change) as mean_return "
                "from st_membership_daily m "
                "join benchmark_daily calendar on calendar.benchmark_id=? "
                "and calendar.trade_date=m.trade_date "
                "left join research.daily_prices p on p.symbol=m.symbol "
                "and p.trade_date=m.trade_date and p.adjust='qfq' "
                "where m.trade_date between ? and ? group by m.trade_date "
                "order by m.trade_date",
                (BROAD_MARKET.benchmark_id, start, end),
            ).fetchall()
        if not aggregates:
            raise ValueError("声明窗口内没有 ST membership，无法物化指数")
        level = starting_level
        points: list[BenchmarkPoint] = []
        for trade_date, member_count, valid_count, mean_return in aggregates:
            coverage = int(valid_count) / int(member_count) if member_count else 0.0
            daily_return = float(mean_return) if mean_return is not None else None
            if daily_return is not None:
                level *= 1 + daily_return / 100.0
            points.append(BenchmarkPoint(
                benchmark_id=ST_EQUAL_WEIGHT.benchmark_id,
                trade_date=str(trade_date),
                close=round(level, 6) if daily_return is not None else None,
                pct_change=round(daily_return, 8) if daily_return is not None else None,
                member_count=int(member_count),
                valid_member_count=int(valid_count),
                coverage_ratio=round(coverage, 8),
                source=ST_EQUAL_WEIGHT.provider,
            ))
        self.upsert(definition=ST_EQUAL_WEIGHT, points=points)
        return points


class MarketContextService:
    def __init__(self, *, provider: IndexDailyProvider, repository: MarketContextRepository):
        self.provider = provider
        self.repository = repository

    def refresh_provider_index(
        self,
        *,
        definition: BenchmarkDefinition,
        start_date: str,
        end_date: str,
    ) -> list[BenchmarkPoint]:
        start = _iso_date(start_date, field="start_date")
        end = _iso_date(end_date, field="end_date")
        if start > end:
            raise ValueError("start_date 不得晚于 end_date")
        rows = self.provider.fetch_index_daily(
            ts_code=definition.provider_code, start_date=start, end_date=end
        )
        points = normalize_index_rows(definition=definition, rows=rows)
        self.repository.upsert(definition=definition, points=points)
        return points


class HistoricalStMembershipService:
    def __init__(
        self,
        *,
        provider: HistoricalMembershipProvider,
        repository: MarketContextRepository,
    ):
        self.provider = provider
        self.repository = repository

    def backfill(
        self,
        *,
        start_date: str,
        end_date: str,
        page_size: int = 1000,
        max_pages: int = 10000,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> MembershipBackfillResult:
        start = _iso_date(start_date, field="start_date")
        end = _iso_date(end_date, field="end_date")
        if start > end:
            raise ValueError("start_date 不得晚于 end_date")
        if not 1 <= page_size <= 1000:
            raise ValueError("page_size 必须在 1..1000")
        range_id = "MB-" + hashlib.sha256(
            f"{start}|{end}|{page_size}".encode("utf-8")
        ).hexdigest()[:20].upper()
        state = self.repository.membership_state(range_id)
        if state and str(state["status"]) == "complete":
            lower, upper, stored, dates = self.repository.membership_bounds()
            return MembershipBackfillResult(
                range_id=range_id, start_date=start, end_date=end,
                page_size=page_size, pages_fetched=0,
                rows_seen=int(state["rows_seen"]), stored_rows=stored,
                distinct_dates=dates, next_offset=int(state["next_offset"]),
                status="complete",
            )
        offset = int(state["next_offset"]) if state else 0
        cumulative = int(state["rows_seen"]) if state else 0
        pages = 0
        previous_identity: tuple[str, str, int] | None = None
        complete = False
        while pages < max_pages:
            raw = self.provider.fetch_st_universe_range(
                start_date=start, end_date=end, limit=page_size, offset=offset
            )
            normalized = _normalize_membership_rows(raw, start=start, end=end)
            identity = (
                normalized[0].trade_date if normalized else "",
                normalized[-1].trade_date if normalized else "",
                len(normalized),
            )
            if previous_identity == identity and normalized:
                raise RuntimeError("stock_st 分页未前进，拒绝无限循环")
            previous_identity = identity
            pages += 1
            cumulative += len(raw)
            next_offset = offset + len(raw)
            complete = len(raw) < page_size
            self.repository.write_membership_page(
                range_id=range_id, start_date=start, end_date=end,
                page_size=page_size, next_offset=next_offset,
                rows_seen=cumulative, rows=normalized, complete=complete,
            )
            if progress:
                progress({
                    "range_id": range_id, "page": pages, "offset": offset,
                    "rows": len(raw), "rows_seen": cumulative,
                    "status": "complete" if complete else "partial",
                })
            offset = next_offset
            if complete:
                break
        lower, upper, stored, dates = self.repository.membership_bounds()
        return MembershipBackfillResult(
            range_id=range_id, start_date=start, end_date=end,
            page_size=page_size, pages_fetched=pages, rows_seen=cumulative,
            stored_rows=stored, distinct_dates=dates, next_offset=offset,
            status="complete" if complete else "partial",
        )

    def repair_trading_date_gaps(
        self,
        *,
        start_date: str,
        end_date: str,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        missing = self.repository.missing_membership_trading_dates(
            start_date=start_date, end_date=end_date
        )
        repaired: list[str] = []
        unresolved: list[str] = []
        rows_seen = 0
        for index, trade_date in enumerate(missing, start=1):
            raw = self.provider.fetch_st_universe_range(
                start_date=trade_date, end_date=trade_date, limit=1000, offset=0
            )
            normalized = _normalize_membership_rows(
                raw, start=trade_date, end=trade_date
            )
            rows_seen += len(raw)
            if normalized:
                self.repository.upsert_membership_rows(normalized)
                repaired.append(trade_date)
            else:
                unresolved.append(trade_date)
            if progress:
                progress({
                    "completed": index, "total": len(missing),
                    "trade_date": trade_date, "rows": len(raw),
                    "status": "repaired" if normalized else "unresolved",
                })
        return {
            "requested_dates": missing,
            "repaired_dates": repaired,
            "unresolved_dates": unresolved,
            "rows_seen": rows_seen,
        }


def build_market_context_manifest(
    *, repository: MarketContextRepository, coverage_threshold: float = 0.95
) -> dict[str, Any]:
    if not 0 < coverage_threshold <= 1:
        raise ValueError("coverage_threshold 必须在 (0,1]")
    membership_start, membership_end, membership_rows, membership_dates = (
        repository.membership_bounds()
    )
    benchmarks: list[dict[str, Any]] = []
    declared_start = ""
    declared_end = ""
    missing_trading_dates: list[str] = []
    pre_source_trading_dates = 0
    continuous_from = ""
    if repository.path.is_file():
        with sqlite3.connect(f"file:{repository.path}?mode=ro", uri=True) as connection:
            declared = connection.execute(
                "select min(start_date),max(end_date) from membership_backfills "
                "where status='complete'"
            ).fetchone()
            declared_start = str(declared[0] or "")
            declared_end = str(declared[1] or "")
            if declared_start and declared_end and membership_start:
                pre_source_trading_dates = len(
                    repository.missing_membership_trading_dates(
                        start_date=declared_start, end_date=membership_start
                    )
                )
                missing_trading_dates = repository.missing_membership_trading_dates(
                    start_date=membership_start, end_date=declared_end
                )
                last_gap = max(missing_trading_dates, default="")
                if last_gap:
                    row = connection.execute(
                        "select min(trade_date) from benchmark_daily "
                        "where benchmark_id=? and trade_date>? and trade_date<=?",
                        (BROAD_MARKET.benchmark_id, last_gap, declared_end),
                    ).fetchone()
                    continuous_from = str(row[0] or "")
                else:
                    continuous_from = declared_start
            ids = [str(row[0]) for row in connection.execute(
                "select benchmark_id from benchmark_definitions order by benchmark_id"
            )]
            for benchmark_id in ids:
                lower, upper, count = repository.bounds(benchmark_id)
                coverage = connection.execute(
                    "select min(coverage_ratio),"
                    "sum(case when coverage_ratio>=? then 1 else 0 end),"
                    "sum(case when coverage_ratio is not null then 1 else 0 end) "
                    "from benchmark_daily where benchmark_id=?",
                    (coverage_threshold, benchmark_id),
                ).fetchone()
                coverage_rows = connection.execute(
                    "select trade_date,coverage_ratio,pct_change from benchmark_daily "
                    "where benchmark_id=? order by trade_date desc",
                    (benchmark_id,),
                ).fetchall()
                ready_streak: list[tuple[Any, ...]] = []
                for coverage_row in coverage_rows:
                    if coverage_row[1] is None or float(coverage_row[1]) < coverage_threshold:
                        break
                    ready_streak.append(coverage_row)
                recent = coverage_rows[:10]
                recent_coverage = [float(row[1]) for row in recent if row[1] is not None]
                recent_returns = [float(row[2]) for row in reversed(recent) if row[2] is not None]
                compounded = 1.0
                for daily_return in recent_returns:
                    compounded *= 1 + daily_return / 100.0
                benchmarks.append({
                    "benchmark_id": benchmark_id, "start": lower, "end": upper,
                    "row_count": count,
                    "minimum_coverage": coverage[0],
                    "ready_coverage_dates": int(coverage[1] or 0),
                    "coverage_observed_dates": int(coverage[2] or 0),
                    "latest_coverage": coverage_rows[0][1] if coverage_rows else None,
                    "current_ready_streak_start": (
                        str(ready_streak[-1][0]) if ready_streak else ""
                    ),
                    "current_ready_streak_dates": len(ready_streak),
                    "recent_10d_minimum_coverage": (
                        min(recent_coverage) if recent_coverage else None
                    ),
                    "recent_10d_return": (
                        round((compounded - 1) * 100, 8) if recent_returns else None
                    ),
                })
    st_row = next(
        (row for row in benchmarks if row["benchmark_id"] == ST_EQUAL_WEIGHT.benchmark_id),
        None,
    )
    broad_row = next(
        (row for row in benchmarks if row["benchmark_id"] == BROAD_MARKET.benchmark_id),
        None,
    )
    benchmark_by_id = {row["benchmark_id"]: row for row in benchmarks}
    required_ids = [item.benchmark_id for item in CANONICAL_BENCHMARK_POOL]
    required_rows = [
        benchmark_by_id[benchmark_id]
        for benchmark_id in required_ids
        if benchmark_id in benchmark_by_id
    ]
    required_starts = [row["start"] for row in required_rows if row["start"]]
    required_ends = [row["end"] for row in required_rows if row["end"]]
    pool_common_start = (
        max(required_starts + [continuous_from])
        if len(required_rows) == len(required_ids)
        and len(required_starts) == len(required_ids)
        and continuous_from
        else ""
    )
    pool_common_end = (
        min(required_ends)
        if len(required_rows) == len(required_ids)
        and len(required_ends) == len(required_ids)
        else ""
    )
    current_ready = bool(
        st_row and broad_row and declared_end
        and all(
            benchmark_by_id.get(benchmark_id, {}).get("end") == declared_end
            for benchmark_id in required_ids
        )
        and st_row["current_ready_streak_dates"] >= 10
    )
    payload = {
        "contract_version": "v8_market_context_manifest_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coverage_threshold": coverage_threshold,
        "current_status": "ready" if current_ready else "gaps",
        "historical_status": (
            "partial" if pre_source_trading_dates or missing_trading_dates
            or (pool_common_start and declared_start and pool_common_start > declared_start)
            or (st_row and st_row["ready_coverage_dates"] < st_row["coverage_observed_dates"])
            else "ready"
        ),
        "benchmark_pool": [
            {
                "benchmark_id": item.benchmark_id,
                "name": item.name,
                "kind": item.kind,
                "evidence_role": item.evidence_role,
                "provider": item.provider,
                "provider_code": item.provider_code,
                "methodology_version": item.methodology_version,
                "notes": item.notes,
            }
            for item in CANONICAL_BENCHMARK_POOL
        ],
        "current_required_benchmarks": required_ids,
        "pool_common_window": {
            "start": pool_common_start,
            "end": pool_common_end,
        },
        "membership": {
            "start": membership_start, "end": membership_end,
            "row_count": membership_rows, "date_count": membership_dates,
            "declared_start": declared_start, "declared_end": declared_end,
            "pre_source_trading_dates": pre_source_trading_dates,
            "missing_trading_date_count": len(missing_trading_dates),
            "missing_trading_dates": missing_trading_dates,
            "continuous_from": continuous_from,
        },
        "benchmarks": benchmarks,
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {**payload, "manifest_id": f"MC-{digest[:20].upper()}"}


def write_market_context_manifest(payload: dict[str, Any], path: Path) -> None:
    atomic_write_json(path, payload)


def _normalize_membership_rows(
    rows: list[dict[str, Any]], *, start: str, end: str
) -> list[HistoricalMembershipRow]:
    unique: dict[tuple[str, str], HistoricalMembershipRow] = {}
    for raw in rows:
        ts_code = str(raw.get("ts_code") or "").strip().upper()
        symbol = ts_code.split(".", 1)[0]
        raw_date = str(raw.get("trade_date") or "")
        if len(symbol) != 6 or not symbol.isdigit():
            raise ValueError(f"stock_st 返回非法 ts_code: {ts_code!r}")
        if len(raw_date) != 8 or not raw_date.isdigit():
            raise ValueError(f"stock_st 返回非法 trade_date: {raw_date!r}")
        trade_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        if not start <= trade_date <= end:
            raise ValueError(f"stock_st 日期越出请求范围: {trade_date}")
        row = HistoricalMembershipRow(
            trade_date=trade_date, symbol=symbol, ts_code=ts_code,
            name=str(raw.get("name") or ""),
            risk_type=str(raw.get("type") or ""),
            risk_type_name=str(raw.get("type_name") or ""),
        )
        key = (trade_date, symbol)
        if key in unique and unique[key] != row:
            raise ValueError(f"stock_st 历史行冲突: {trade_date} {symbol}")
        unique[key] = row
    return [unique[key] for key in sorted(unique, reverse=True)]


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)
