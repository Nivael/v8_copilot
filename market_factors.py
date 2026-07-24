"""Point-in-time market factors for survivorship-safe ST cohort research."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from data_refresh import atomic_write_json
from market_context import MarketContextRepository


MARKET_FACTOR_CONTRACT_VERSION = "v8_market_factors_v1"
MARKET_FACTOR_MANIFEST_VERSION = "v8_market_factor_manifest_v1"
MARKET_CAP_SOURCE = "tushare:daily_basic"
MICROCAP_DEFINITION_ID = "st_total_mv_bottom_30pct_v1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MarketCapPoint(StrictModel):
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    trade_date: str
    total_shares: float | None = Field(default=None, ge=0)
    float_shares: float | None = Field(default=None, ge=0)
    free_shares: float | None = Field(default=None, ge=0)
    total_market_value: float | None = Field(default=None, ge=0)
    circulating_market_value: float | None = Field(default=None, ge=0)
    turnover_rate: float | None = None
    source: Literal[MARKET_CAP_SOURCE] = MARKET_CAP_SOURCE


class MarketFactorSnapshot(StrictModel):
    snapshot_id: str = Field(pattern=r"^MFS-[A-F0-9]{20}$")
    contract_version: Literal[MARKET_FACTOR_CONTRACT_VERSION] = (
        MARKET_FACTOR_CONTRACT_VERSION
    )
    trade_date: str
    membership_source: Literal["tushare:stock_st"] = "tushare:stock_st"
    membership_count: int = Field(ge=1)
    membership_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    row_count: int = Field(ge=0)
    valid_total_market_value_count: int = Field(ge=0)
    coverage_ratio: float = Field(ge=0, le=1)
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: str


class DailyBasicProvider(Protocol):
    def fetch_daily_basic(self, *, trade_date: str) -> list[dict[str, Any]]: ...


def _iso_date(value: str, *, field: str) -> str:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是 YYYY-MM-DD: {value!r}") from exc


def _canonical(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        default=str,
    )


def _ten_thousand(value: Any) -> float | None:
    if value in (None, ""):
        return None
    number = float(value) * 10_000
    if number < 0:
        raise ValueError("daily_basic 数值不得为负")
    return number


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def normalize_market_cap_rows(
    *, rows: list[dict[str, Any]], trade_date: str,
    membership_symbols: list[str],
) -> list[MarketCapPoint]:
    day = _iso_date(trade_date, field="trade_date")
    raw_day = day.replace("-", "")
    members = set(membership_symbols)
    unique: dict[str, MarketCapPoint] = {}
    for raw in rows:
        code = str(raw.get("ts_code") or "").strip().upper()
        symbol = code.split(".", 1)[0]
        if symbol not in members:
            continue
        if len(symbol) != 6 or not symbol.isdigit():
            raise ValueError(f"daily_basic 返回非法 ts_code: {code!r}")
        if str(raw.get("trade_date") or "") != raw_day:
            raise ValueError(
                f"daily_basic {symbol} 日期与请求不一致: "
                f"{raw.get('trade_date')!r} != {raw_day}"
            )
        point = MarketCapPoint(
            symbol=symbol,
            trade_date=day,
            total_shares=_ten_thousand(raw.get("total_share")),
            float_shares=_ten_thousand(raw.get("float_share")),
            free_shares=_ten_thousand(raw.get("free_share")),
            total_market_value=_ten_thousand(raw.get("total_mv")),
            circulating_market_value=_ten_thousand(raw.get("circ_mv")),
            turnover_rate=_number(raw.get("turnover_rate")),
        )
        previous = unique.get(symbol)
        if previous is not None and previous != point:
            raise ValueError(f"daily_basic 同日重复行冲突: {day} {symbol}")
        unique[symbol] = point
    return [unique[symbol] for symbol in sorted(unique)]


class MarketFactorRepository:
    """Append-only factor snapshots, separate from prices and benchmarks."""

    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.executescript("""
            create table if not exists market_factor_snapshots (
                snapshot_id text primary key,
                contract_version text not null,
                trade_date text not null,
                membership_source text not null,
                membership_count integer not null,
                membership_digest text not null,
                row_count integer not null,
                valid_total_market_value_count integer not null,
                coverage_ratio real not null,
                content_digest text not null,
                created_at text not null
            );
            create index if not exists idx_market_factor_snapshot_date
                on market_factor_snapshots(trade_date,created_at);
            create table if not exists market_cap_daily (
                snapshot_id text not null,
                symbol text not null,
                trade_date text not null,
                total_shares real,
                float_shares real,
                free_shares real,
                total_market_value real,
                circulating_market_value real,
                turnover_rate real,
                source text not null,
                primary key (snapshot_id,symbol),
                foreign key (snapshot_id) references market_factor_snapshots(snapshot_id)
            );
        """)
        return connection

    def store_snapshot(
        self, *, trade_date: str, membership_symbols: list[str],
        points: list[MarketCapPoint],
    ) -> MarketFactorSnapshot:
        day = _iso_date(trade_date, field="trade_date")
        members = sorted(set(membership_symbols))
        if not members:
            raise ValueError(f"{day} 没有历史 ST membership")
        if any(len(symbol) != 6 or not symbol.isdigit() for symbol in members):
            raise ValueError("membership 包含非法股票代码")
        unique = {point.symbol: point for point in points}
        if len(unique) != len(points):
            raise ValueError("market-cap points 包含重复股票")
        outside = sorted(set(unique) - set(members))
        if outside:
            raise ValueError("market-cap points 越出历史 membership: " + ",".join(outside))
        if any(point.trade_date != day for point in points):
            raise ValueError("market-cap point 日期与 snapshot 日期不一致")
        ordered = [unique[symbol] for symbol in sorted(unique)]
        membership_digest = hashlib.sha256("\n".join(members).encode()).hexdigest()
        content = {
            "contract_version": MARKET_FACTOR_CONTRACT_VERSION,
            "trade_date": day,
            "membership_source": "tushare:stock_st",
            "membership_count": len(members),
            "membership_digest": membership_digest,
            "points": [point.model_dump(mode="json") for point in ordered],
        }
        content_digest = hashlib.sha256(_canonical(content).encode()).hexdigest()
        valid_count = sum(
            1 for point in ordered
            if point.total_market_value is not None and point.total_market_value > 0
        )
        created_at = datetime.now(timezone.utc).isoformat()
        snapshot = MarketFactorSnapshot(
            snapshot_id=f"MFS-{content_digest[:20].upper()}",
            trade_date=day,
            membership_count=len(members),
            membership_digest=membership_digest,
            row_count=len(ordered),
            valid_total_market_value_count=valid_count,
            coverage_ratio=round(valid_count / len(members), 8),
            content_digest=content_digest,
            created_at=created_at,
        )
        with self._connect() as connection:
            connection.execute(
                "insert or ignore into market_factor_snapshots values "
                "(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    snapshot.snapshot_id, snapshot.contract_version,
                    snapshot.trade_date, snapshot.membership_source,
                    snapshot.membership_count, snapshot.membership_digest,
                    snapshot.row_count, snapshot.valid_total_market_value_count,
                    snapshot.coverage_ratio, snapshot.content_digest,
                    snapshot.created_at,
                ),
            )
            connection.executemany(
                "insert or ignore into market_cap_daily values "
                "(?,?,?,?,?,?,?,?,?,?)",
                [(
                    snapshot.snapshot_id, point.symbol, point.trade_date,
                    point.total_shares, point.float_shares, point.free_shares,
                    point.total_market_value, point.circulating_market_value,
                    point.turnover_rate, point.source,
                ) for point in ordered],
            )
        return self.get_snapshot(snapshot.snapshot_id)

    def get_snapshot(self, snapshot_id: str) -> MarketFactorSnapshot:
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "select * from market_factor_snapshots where snapshot_id=?",
                (snapshot_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"未知 market factor snapshot: {snapshot_id}")
        return MarketFactorSnapshot.model_validate(dict(row))

    def latest_snapshot(self, trade_date: str) -> MarketFactorSnapshot | None:
        if not self.path.is_file():
            return None
        day = _iso_date(trade_date, field="trade_date")
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "select * from market_factor_snapshots where trade_date=? "
                "order by created_at desc limit 1",
                (day,),
            ).fetchone()
        return MarketFactorSnapshot.model_validate(dict(row)) if row else None

    def points(self, snapshot_id: str) -> list[MarketCapPoint]:
        if not self.path.is_file():
            return []
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "select symbol,trade_date,total_shares,float_shares,free_shares,"
                "total_market_value,circulating_market_value,turnover_rate,source "
                "from market_cap_daily where snapshot_id=? order by symbol",
                (snapshot_id,),
            ).fetchall()
        return [MarketCapPoint.model_validate(dict(row)) for row in rows]

    def snapshot_count(self) -> int:
        if not self.path.is_file():
            return 0
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            return int(connection.execute(
                "select count(*) from market_factor_snapshots"
            ).fetchone()[0])


class MarketFactorService:
    def __init__(
        self, *, provider: DailyBasicProvider,
        repository: MarketFactorRepository,
        market_context_database: Path,
    ):
        self.provider = provider
        self.repository = repository
        self.market_context = MarketContextRepository(market_context_database)

    def refresh(self, *, as_of: str) -> MarketFactorSnapshot:
        day = _iso_date(as_of, field="as_of")
        members = self.market_context.membership_symbols(day)
        if not members:
            raise ValueError(f"{day} 没有历史 ST membership，拒绝使用当前名单回填")
        rows = self.provider.fetch_daily_basic(trade_date=day)
        points = normalize_market_cap_rows(
            rows=rows, trade_date=day, membership_symbols=members,
        )
        return self.repository.store_snapshot(
            trade_date=day, membership_symbols=members, points=points,
        )


def build_market_factor_manifest(
    *, repository: MarketFactorRepository, snapshot_id: str,
    coverage_threshold: float = 0.95,
) -> dict[str, Any]:
    if not 0 < coverage_threshold <= 1:
        raise ValueError("coverage_threshold 必须在 (0,1]")
    snapshot = repository.get_snapshot(snapshot_id)
    gaps = []
    if snapshot.coverage_ratio < coverage_threshold:
        gaps.append(
            f"point-in-time 总市值覆盖率 {snapshot.coverage_ratio:.2%} "
            f"低于门槛 {coverage_threshold:.2%}"
        )
    payload: dict[str, Any] = {
        "contract_version": MARKET_FACTOR_MANIFEST_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready" if not gaps else "gaps",
        "factor_snapshot_id": snapshot.snapshot_id,
        "factor_date": snapshot.trade_date,
        "factor_definition": {
            "definition_id": MICROCAP_DEFINITION_ID,
            "primary_field": "total_market_value",
            "source": MARKET_CAP_SOURCE,
            "source_unit": "万元",
            "stored_unit": "人民币元",
            "cohort_rule": "窗口起点 ST universe 中总市值最小 30%；阈值同值一并纳入",
            "lookahead_rule": "只使用收益窗口起点当日因子，不使用窗口终点或当前市值",
        },
        "membership": {
            "source": snapshot.membership_source,
            "source_ref": (
                "local_data/v8_copilot/market_context_v1.sqlite3"
                "::st_membership_daily"
            ),
            "as_of": snapshot.trade_date,
            "count": snapshot.membership_count,
            "digest": snapshot.membership_digest,
        },
        "coverage": {
            "row_count": snapshot.row_count,
            "valid_total_market_value_count": (
                snapshot.valid_total_market_value_count
            ),
            "ratio": snapshot.coverage_ratio,
            "threshold": coverage_threshold,
        },
        "blocking_gaps": gaps,
    }
    digest = hashlib.sha256(_canonical(payload).encode()).hexdigest()
    return {**payload, "manifest_id": f"MF-{digest[:20].upper()}"}


def write_market_factor_manifest(payload: dict[str, Any], path: Path) -> None:
    atomic_write_json(path, payload)


def write_market_factor_manifest_set(
    payload: dict[str, Any], *, current_path: Path, manifest_directory: Path,
) -> Path:
    """Persist an immutable date manifest plus the replaceable current pointer."""

    dated_path = write_market_factor_dated_manifest(
        payload, manifest_directory=manifest_directory
    )
    advance_market_factor_current(payload, current_path=current_path)
    return dated_path


def write_market_factor_dated_manifest(
    payload: dict[str, Any], *, manifest_directory: Path,
) -> Path:
    """Persist one immutable date manifest without moving the current pointer."""

    factor_date = _iso_date(str(payload.get("factor_date") or ""), field="factor_date")
    dated_path = manifest_directory / f"{factor_date}.json"
    if dated_path.is_file():
        existing = json.loads(dated_path.read_text(encoding="utf-8"))
        if existing.get("factor_snapshot_id") != payload.get("factor_snapshot_id"):
            raise ValueError(f"{factor_date} dated manifest 已绑定不同 factor snapshot")
        return dated_path
    atomic_write_json(dated_path, payload)
    return dated_path


def advance_market_factor_current(
    payload: dict[str, Any], *, current_path: Path,
) -> bool:
    """Advance current monotonically; historical backfills never move it backward."""

    factor_date = _iso_date(str(payload.get("factor_date") or ""), field="factor_date")
    if current_path.is_file():
        existing = json.loads(current_path.read_text(encoding="utf-8"))
        existing_date = _iso_date(
            str(existing.get("factor_date") or ""),
            field="current.factor_date",
        )
        if existing_date > factor_date:
            return False
        if existing_date == factor_date:
            if (
                existing.get("factor_snapshot_id")
                != payload.get("factor_snapshot_id")
            ):
                raise ValueError(
                    f"{factor_date} current manifest 已绑定不同 factor snapshot"
                )
            return False
    atomic_write_json(current_path, payload)
    return True
