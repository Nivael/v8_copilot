"""Read-only, trading-day-aligned stock and benchmark comparison windows."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from settings import MARKET_CONTEXT_DB, MARKET_CONTEXT_MANIFEST_PATH, ST_UNIVERSE_DIR


ST_BENCHMARK = "st_equal_weight_v1"
SMALL_CAP_BENCHMARK = "csi_2000"
MARKET_BENCHMARK = "csi_all_share"
REQUIRED_BENCHMARKS = (
    ST_BENCHMARK,
    SMALL_CAP_BENCHMARK,
    MARKET_BENCHMARK,
)


@dataclass(frozen=True)
class ComparisonPoint:
    trade_date: str
    normalized: dict[str, float]


@dataclass(frozen=True)
class MarketComparisonWindow:
    status: str
    symbol: str | None
    sessions: int
    start_date: str = ""
    end_date: str = ""
    returns_pct: dict[str, float] = field(default_factory=dict)
    relative_pp: dict[str, float] = field(default_factory=dict)
    points: list[ComparisonPoint] = field(default_factory=list)
    minimum_st_coverage: float | None = None
    manifest_id: str = ""
    manifest_generated_at: str = ""
    universe_snapshot_id: str = ""
    universe_as_of: str = ""
    gaps: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    def summary_row(self) -> dict[str, object]:
        if not self.ready:
            return {
                "row_id": "market_comparison_gap",
                "记录类型": "市场对比缺口",
                "目标窗口": f"最近 {self.sessions} 个交易日",
                "缺口": "；".join(self.gaps),
                "manifest_id": self.manifest_id or "unavailable",
            }
        values: dict[str, object] = {
            "row_id": "market_comparison_summary",
            "记录类型": "市场对比摘要",
            "窗口起点": self.start_date,
            "窗口终点": self.end_date,
            "交易日跨度": self.sessions,
            "ST等权收益": _pct(self.returns_pct[ST_BENCHMARK]),
            "中证2000收益": _pct(self.returns_pct[SMALL_CAP_BENCHMARK]),
            "中证全指收益": _pct(self.returns_pct[MARKET_BENCHMARK]),
            "ST相对中证2000": _pp(self.relative_pp["st_minus_csi2000"]),
            "ST相对全市场": _pp(self.relative_pp["st_minus_market"]),
            "中证2000相对全市场": _pp(
                self.relative_pp["csi2000_minus_market"]
            ),
            "ST最低覆盖率": _pct((self.minimum_st_coverage or 0) * 100),
            "manifest_id": self.manifest_id,
            "universe_snapshot_id": self.universe_snapshot_id,
        }
        if self.symbol:
            values = {
                **values,
                "股票代码": self.symbol,
                "个股收益": _pct(self.returns_pct["stock"]),
                "个股相对ST": _pp(self.relative_pp["stock_minus_st"]),
                "个股相对中证2000": _pp(
                    self.relative_pp["stock_minus_csi2000"]
                ),
                "个股相对全市场": _pp(self.relative_pp["stock_minus_market"]),
            }
        return values

    def series_rows(self) -> list[dict[str, object]]:
        if not self.ready:
            return []
        return [
            {
                "row_id": f"market_comparison_point_{index:02d}",
                "记录类型": "市场对比序列",
                "日期": point.trade_date,
                "date": point.trade_date,
                "stock_normalized": point.normalized.get("stock"),
                "st_normalized": point.normalized[ST_BENCHMARK],
                "csi2000_normalized": point.normalized[SMALL_CAP_BENCHMARK],
                "market_normalized": point.normalized[MARKET_BENCHMARK],
            }
            for index, point in enumerate(self.points, 1)
        ]


def load_market_comparison(
    *,
    price_database: Path,
    symbol: str | None = None,
    sessions: int = 10,
    coverage_threshold: float = 0.95,
    market_database: Path = MARKET_CONTEXT_DB,
    manifest_path: Path = MARKET_CONTEXT_MANIFEST_PATH,
    universe_current_path: Path = ST_UNIVERSE_DIR / "current.json",
) -> MarketComparisonWindow:
    if symbol is not None and (len(symbol) != 6 or not symbol.isdigit()):
        raise ValueError("symbol 必须是六位股票代码")
    if sessions < 1:
        raise ValueError("sessions 必须至少为 1")
    if not 0 < coverage_threshold <= 1:
        raise ValueError("coverage_threshold 必须在 (0,1]")

    manifest, manifest_gaps = _load_manifest(manifest_path)
    manifest_id = str(manifest.get("manifest_id") or "")
    generated_at = str(manifest.get("generated_at") or "")
    if manifest_gaps:
        return MarketComparisonWindow(
            status="gaps", symbol=symbol, sessions=sessions,
            manifest_id=manifest_id, manifest_generated_at=generated_at,
            gaps=manifest_gaps,
        )
    common_window = manifest["pool_common_window"]
    assert isinstance(common_window, dict)
    through = str(common_window["end"])
    universe, universe_gaps = _load_universe_pointer(
        universe_current_path, through=through
    )
    universe_snapshot_id = str(universe.get("snapshot_id") or "")
    universe_as_of = str(universe.get("as_of") or "")
    if universe_gaps:
        return MarketComparisonWindow(
            status="gaps", symbol=symbol, sessions=sessions,
            manifest_id=manifest_id, manifest_generated_at=generated_at,
            universe_snapshot_id=universe_snapshot_id,
            universe_as_of=universe_as_of,
            gaps=universe_gaps,
        )
    if not market_database.is_file():
        return MarketComparisonWindow(
            status="gaps", symbol=symbol, sessions=sessions,
            manifest_id=manifest_id, manifest_generated_at=generated_at,
            universe_snapshot_id=universe_snapshot_id,
            universe_as_of=universe_as_of,
            gaps=["market-context 数据库不存在"],
        )

    try:
        benchmark_values, st_coverage, dates = _benchmark_window(
            market_database=market_database,
            sessions=sessions,
            coverage_threshold=coverage_threshold,
            through=through,
        )
    except (sqlite3.Error, ValueError) as exc:
        return MarketComparisonWindow(
            status="gaps", symbol=symbol, sessions=sessions,
            manifest_id=manifest_id, manifest_generated_at=generated_at,
            universe_snapshot_id=universe_snapshot_id,
            universe_as_of=universe_as_of,
            gaps=[str(exc)],
        )

    values: dict[str, dict[str, float]] = dict(benchmark_values)
    if symbol:
        stock, gaps = _stock_window(price_database, symbol=symbol, dates=dates)
        if gaps:
            return MarketComparisonWindow(
                status="gaps", symbol=symbol, sessions=sessions,
                start_date=dates[0], end_date=dates[-1],
                minimum_st_coverage=min(st_coverage.values()),
                manifest_id=manifest_id, manifest_generated_at=generated_at,
                universe_snapshot_id=universe_snapshot_id,
                universe_as_of=universe_as_of,
                gaps=gaps,
            )
        values["stock"] = stock

    try:
        normalized = {
            series_id: _normalize_series(series, dates)
            for series_id, series in values.items()
        }
        returns = {
            series_id: round(
                series[dates[-1]] / series[dates[0]] * 100 - 100, 8
            )
            for series_id, series in values.items()
        }
    except (KeyError, ZeroDivisionError, ValueError) as exc:
        return MarketComparisonWindow(
            status="gaps", symbol=symbol, sessions=sessions,
            start_date=dates[0], end_date=dates[-1],
            minimum_st_coverage=min(st_coverage.values()),
            manifest_id=manifest_id, manifest_generated_at=generated_at,
            universe_snapshot_id=universe_snapshot_id,
            universe_as_of=universe_as_of,
            gaps=[f"市场比较序列无法计算: {exc}"],
        )
    relative = {
        "st_minus_csi2000": round(
            returns[ST_BENCHMARK] - returns[SMALL_CAP_BENCHMARK], 8
        ),
        "st_minus_market": round(
            returns[ST_BENCHMARK] - returns[MARKET_BENCHMARK], 8
        ),
        "csi2000_minus_market": round(
            returns[SMALL_CAP_BENCHMARK] - returns[MARKET_BENCHMARK], 8
        ),
    }
    if symbol:
        relative.update({
            "stock_minus_st": round(returns["stock"] - returns[ST_BENCHMARK], 8),
            "stock_minus_csi2000": round(
                returns["stock"] - returns[SMALL_CAP_BENCHMARK], 8
            ),
            "stock_minus_market": round(
                returns["stock"] - returns[MARKET_BENCHMARK], 8
            ),
        })
    points = [
        ComparisonPoint(
            trade_date=trade_date,
            normalized={
                series_id: series[trade_date]
                for series_id, series in normalized.items()
            },
        )
        for trade_date in dates
    ]
    return MarketComparisonWindow(
        status="ready", symbol=symbol, sessions=sessions,
        start_date=dates[0], end_date=dates[-1],
        returns_pct=returns, relative_pp=relative, points=points,
        minimum_st_coverage=min(st_coverage.values()),
        manifest_id=manifest_id, manifest_generated_at=generated_at,
        universe_snapshot_id=universe_snapshot_id,
        universe_as_of=universe_as_of,
    )


def _load_manifest(path: Path) -> tuple[dict[str, object], list[str]]:
    if not path.is_file():
        return {}, ["market-context manifest 不存在"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"market-context manifest 无法读取: {exc}"]
    if not isinstance(payload, dict):
        return {}, ["market-context manifest 顶层必须是对象"]
    gaps: list[str] = []
    if payload.get("current_status") != "ready":
        gaps.append("market-context manifest 当前不是 ready")
    required = set(payload.get("current_required_benchmarks") or [])
    missing = sorted(set(REQUIRED_BENCHMARKS) - required)
    if missing:
        gaps.append("manifest 缺 required benchmark: " + ",".join(missing))
    common = payload.get("pool_common_window") or {}
    if not isinstance(common, dict) or not common.get("end"):
        gaps.append("manifest 缺 pool_common_window.end")
    return payload, gaps


def _load_universe_pointer(
    path: Path, *, through: str
) -> tuple[dict[str, object], list[str]]:
    if not path.is_file():
        return {}, ["ST universe current pointer 不存在"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"ST universe current pointer 无法读取: {exc}"]
    if not isinstance(payload, dict):
        return {}, ["ST universe current pointer 顶层必须是对象"]
    gaps = []
    if not payload.get("snapshot_id"):
        gaps.append("ST universe current pointer 缺 snapshot_id")
    if payload.get("as_of") != through:
        gaps.append(
            f"ST universe as-of 与市场窗口终点不一致: "
            f"{payload.get('as_of') or 'missing'} != {through}"
        )
    return payload, gaps


def _benchmark_window(
    *, market_database: Path, sessions: int, coverage_threshold: float,
    through: str,
) -> tuple[dict[str, dict[str, float]], dict[str, float], list[str]]:
    with sqlite3.connect(f"file:{market_database}?mode=ro", uri=True) as connection:
        latest = {
            str(benchmark_id): str(end_date or "")
            for benchmark_id, end_date in connection.execute(
                "select benchmark_id,max(trade_date) from benchmark_daily "
                "where benchmark_id in (?,?,?) group by benchmark_id",
                REQUIRED_BENCHMARKS,
            )
        }
        missing_ids = sorted(set(REQUIRED_BENCHMARKS) - set(latest))
        if missing_ids:
            raise ValueError("market-context 缺 benchmark: " + ",".join(missing_ids))
        stale_ids = sorted(
            benchmark_id for benchmark_id, end_date in latest.items()
            if end_date < through
        )
        if stale_ids:
            raise ValueError(
                f"benchmark 未覆盖 manifest 终点 {through}: "
                + ",".join(stale_ids)
            )
        dates = [
            str(row[0])
            for row in connection.execute(
                "select trade_date from benchmark_daily where benchmark_id=? "
                "and trade_date<=? order by trade_date desc limit ?",
                (MARKET_BENCHMARK, through, sessions + 1),
            )
        ][::-1]
        if len(dates) != sessions + 1:
            raise ValueError(f"共同窗口不足 {sessions + 1} 个端点")
        if dates[-1] != through:
            raise ValueError(f"全市场序列缺 manifest 终点: {through}")
        placeholders = ",".join("?" for _ in dates)
        rows = connection.execute(
            "select benchmark_id,trade_date,close,coverage_ratio "
            "from benchmark_daily where benchmark_id in (?,?,?) "
            f"and trade_date in ({placeholders})",
            (*REQUIRED_BENCHMARKS, *dates),
        ).fetchall()
    values = {benchmark_id: {} for benchmark_id in REQUIRED_BENCHMARKS}
    st_coverage: dict[str, float] = {}
    for benchmark_id, trade_date, close, coverage in rows:
        if close is not None:
            values[str(benchmark_id)][str(trade_date)] = float(close)
        if benchmark_id == ST_BENCHMARK and coverage is not None:
            st_coverage[str(trade_date)] = float(coverage)
    for benchmark_id, series in values.items():
        missing_dates = [day for day in dates if day not in series]
        if missing_dates:
            raise ValueError(
                f"{benchmark_id} 缺共同交易日: {','.join(missing_dates)}"
            )
    coverage_gaps = [
        day for day in dates
        if st_coverage.get(day, 0) < coverage_threshold
    ]
    if coverage_gaps:
        raise ValueError(
            "ST 等权覆盖率低于门槛: " + ",".join(coverage_gaps)
        )
    return values, st_coverage, dates


def _stock_window(
    price_database: Path, *, symbol: str, dates: list[str]
) -> tuple[dict[str, float], list[str]]:
    if not price_database.is_file():
        return {}, ["个股价格数据库不存在"]
    placeholders = ",".join("?" for _ in dates)
    try:
        with sqlite3.connect(f"file:{price_database}?mode=ro", uri=True) as connection:
            rows = connection.execute(
                "select trade_date,close from daily_prices where symbol=? "
                "and adjust='qfq' "
                f"and trade_date in ({placeholders})",
                (symbol, *dates),
            ).fetchall()
    except sqlite3.Error as exc:
        return {}, [f"个股价格窗口查询失败: {exc}"]
    values = {
        str(trade_date): float(close)
        for trade_date, close in rows if close is not None
    }
    missing = [day for day in dates if day not in values]
    if missing:
        return values, [
            f"{symbol} 缺共同交易日价格，不插值: {','.join(missing)}"
        ]
    return values, []


def _normalize_series(values: dict[str, float], dates: list[str]) -> dict[str, float]:
    base = values[dates[0]]
    if base == 0:
        raise ValueError("序列起点为 0，无法归一化")
    return {
        trade_date: round(values[trade_date] / base * 100, 6)
        for trade_date in dates
    }


def _pct(value: float) -> str:
    return f"{value:.2f}%"


def _pp(value: float) -> str:
    return f"{value:+.2f}个百分点"
