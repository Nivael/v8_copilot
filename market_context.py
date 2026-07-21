"""Versioned benchmark series and transparent ST-sector index construction."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


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


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)
