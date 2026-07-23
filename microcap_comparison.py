"""Read-only microcap/ST cohort comparison bound to window-start market cap."""
from __future__ import annotations

import json
import math
import sqlite3
import statistics
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from market_factors import MICROCAP_DEFINITION_ID, MarketFactorRepository
from settings import (
    MARKET_FACTOR_DB,
    MARKET_FACTOR_MANIFEST_DIR,
    MARKET_FACTOR_MANIFEST_PATH,
)


@dataclass(frozen=True)
class MicrocapComparison:
    status: str
    start_date: str
    end_date: str
    factor_snapshot_id: str = ""
    manifest_id: str = ""
    membership_count: int = 0
    factor_coverage_ratio: float = 0.0
    cutoff_market_value: float | None = None
    microcap_symbols: list[str] = field(default_factory=list)
    other_symbols: list[str] = field(default_factory=list)
    microcap_stats: dict[str, float | int] = field(default_factory=dict)
    other_stats: dict[str, float | int] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    def body_rows(self) -> list[dict[str, object]]:
        if not self.ready:
            return [{
                "row_id": "microcap_comparison_gap",
                "记录类型": "市值分层缺口",
                "收益窗口": f"{self.start_date}~{self.end_date}",
                "缺口": "；".join(self.gaps),
                "factor_snapshot_id": self.factor_snapshot_id or "unavailable",
                "manifest_id": self.manifest_id or "unavailable",
            }]
        assert self.cutoff_market_value is not None
        return [
            {
                "row_id": "microcap_definition",
                "记录类型": "市值分层定义",
                "定义ID": MICROCAP_DEFINITION_ID,
                "收益窗口起点": self.start_date,
                "收益窗口终点": self.end_date,
                "因子日期": self.start_date,
                "因子字段": "总市值",
                "微盘口径": "窗口起点 ST 总市值最小 30%；阈值同值一并纳入",
                "微盘阈值": _yi(self.cutoff_market_value),
                "ST成员数": self.membership_count,
                "有效市值数": len(self.microcap_symbols) + len(self.other_symbols),
                "市值覆盖率": _pct(self.factor_coverage_ratio * 100),
                "factor_snapshot_id": self.factor_snapshot_id,
                "manifest_id": self.manifest_id,
            },
            _cohort_row(
                row_id="microcap_distribution",
                label="微盘ST",
                symbols=self.microcap_symbols,
                stats=self.microcap_stats,
            ),
            _cohort_row(
                row_id="other_st_distribution",
                label="普通ST",
                symbols=self.other_symbols,
                stats=self.other_stats,
            ),
            {
                "row_id": "microcap_comparison_summary",
                "记录类型": "市值分层比较摘要",
                "微盘减普通ST平均收益": _pp(
                    float(self.microcap_stats["mean_return"])
                    - float(self.other_stats["mean_return"])
                ),
                "微盘减普通ST中位收益": _pp(
                    float(self.microcap_stats["median_return"])
                    - float(self.other_stats["median_return"])
                ),
                "解释边界": "百分点差只描述该窗口历史分布，不是 alpha 或交易信号",
            },
        ]


def load_microcap_comparison(
    *, price_database: Path,
    start_date: str,
    end_date: str,
    factor_database: Path = MARKET_FACTOR_DB,
    manifest_path: Path = MARKET_FACTOR_MANIFEST_PATH,
    manifest_directory: Path = MARKET_FACTOR_MANIFEST_DIR,
    microcap_fraction: float = 0.30,
    return_coverage_threshold: float = 0.95,
) -> MicrocapComparison:
    start = _iso_date(start_date, field="start_date")
    end = _iso_date(end_date, field="end_date")
    if start >= end:
        raise ValueError("start_date 必须早于 end_date")
    if not 0 < microcap_fraction < 1:
        raise ValueError("microcap_fraction 必须在 (0,1)")
    if not 0 < return_coverage_threshold <= 1:
        raise ValueError("return_coverage_threshold 必须在 (0,1]")

    manifest, gaps = _load_manifest(
        manifest_path,
        manifest_directory=manifest_directory,
        start_date=start,
    )
    snapshot_id = str(manifest.get("factor_snapshot_id") or "")
    manifest_id = str(manifest.get("manifest_id") or "")
    if gaps:
        return MicrocapComparison(
            status="gaps", start_date=start, end_date=end,
            factor_snapshot_id=snapshot_id, manifest_id=manifest_id,
            gaps=gaps,
        )
    if not factor_database.is_file():
        return MicrocapComparison(
            status="gaps", start_date=start, end_date=end,
            factor_snapshot_id=snapshot_id, manifest_id=manifest_id,
            gaps=["point-in-time 市值数据库不存在"],
        )
    try:
        repository = MarketFactorRepository(factor_database)
        snapshot = repository.get_snapshot(snapshot_id)
        points = repository.points(snapshot_id)
    except (FileNotFoundError, sqlite3.Error, ValueError) as exc:
        return MicrocapComparison(
            status="gaps", start_date=start, end_date=end,
            factor_snapshot_id=snapshot_id, manifest_id=manifest_id,
            gaps=[f"point-in-time 市值快照无法读取: {exc}"],
        )
    if snapshot.trade_date != start:
        gaps.append(f"市值快照日期与收益窗口起点不一致: {snapshot.trade_date} != {start}")
    membership = manifest.get("membership") or {}
    if not isinstance(membership, dict):
        gaps.append("market-factor manifest membership 非对象")
    else:
        if membership.get("digest") != snapshot.membership_digest:
            gaps.append("market-factor manifest membership digest 与快照不一致")
        if membership.get("count") != snapshot.membership_count:
            gaps.append("market-factor manifest membership count 与快照不一致")
    valid_caps = {
        point.symbol: float(point.total_market_value)
        for point in points
        if point.total_market_value is not None and point.total_market_value > 0
    }
    if len(valid_caps) != snapshot.valid_total_market_value_count:
        gaps.append("market-cap 有效行数与快照元数据不一致")
    if gaps:
        return MicrocapComparison(
            status="gaps", start_date=start, end_date=end,
            factor_snapshot_id=snapshot_id, manifest_id=manifest_id,
            membership_count=snapshot.membership_count,
            factor_coverage_ratio=snapshot.coverage_ratio,
            gaps=gaps,
        )
    ordered = sorted(valid_caps.items(), key=lambda item: (item[1], item[0]))
    target_count = max(1, math.ceil(len(ordered) * microcap_fraction))
    cutoff = ordered[target_count - 1][1]
    microcap_symbols = [symbol for symbol, value in ordered if value <= cutoff]
    other_symbols = [symbol for symbol, value in ordered if value > cutoff]
    if not other_symbols:
        return MicrocapComparison(
            status="gaps", start_date=start, end_date=end,
            factor_snapshot_id=snapshot_id, manifest_id=manifest_id,
            membership_count=snapshot.membership_count,
            factor_coverage_ratio=snapshot.coverage_ratio,
            cutoff_market_value=cutoff,
            microcap_symbols=microcap_symbols,
            gaps=["市值阈值同值扩展后没有普通 ST 对照组"],
        )
    prices, price_gaps = _endpoint_returns(
        price_database=price_database,
        symbols=list(valid_caps),
        start_date=start,
        end_date=end,
    )
    if price_gaps:
        return MicrocapComparison(
            status="gaps", start_date=start, end_date=end,
            factor_snapshot_id=snapshot_id, manifest_id=manifest_id,
            membership_count=snapshot.membership_count,
            factor_coverage_ratio=snapshot.coverage_ratio,
            cutoff_market_value=cutoff,
            microcap_symbols=microcap_symbols,
            other_symbols=other_symbols,
            gaps=price_gaps,
        )
    cohort_returns = {
        "微盘ST": [prices[symbol] for symbol in microcap_symbols if symbol in prices],
        "普通ST": [prices[symbol] for symbol in other_symbols if symbol in prices],
    }
    cohort_sizes = {"微盘ST": len(microcap_symbols), "普通ST": len(other_symbols)}
    coverage_gaps = []
    for label, returns in cohort_returns.items():
        ratio = len(returns) / cohort_sizes[label]
        if ratio < return_coverage_threshold:
            coverage_gaps.append(
                f"{label}收益覆盖率 {ratio:.2%} 低于门槛 "
                f"{return_coverage_threshold:.2%}，缺失端点不插值"
            )
    if coverage_gaps:
        return MicrocapComparison(
            status="gaps", start_date=start, end_date=end,
            factor_snapshot_id=snapshot_id, manifest_id=manifest_id,
            membership_count=snapshot.membership_count,
            factor_coverage_ratio=snapshot.coverage_ratio,
            cutoff_market_value=cutoff,
            microcap_symbols=microcap_symbols,
            other_symbols=other_symbols,
            gaps=coverage_gaps,
        )
    return MicrocapComparison(
        status="ready", start_date=start, end_date=end,
        factor_snapshot_id=snapshot_id, manifest_id=manifest_id,
        membership_count=snapshot.membership_count,
        factor_coverage_ratio=snapshot.coverage_ratio,
        cutoff_market_value=cutoff,
        microcap_symbols=microcap_symbols,
        other_symbols=other_symbols,
        microcap_stats=_stats(
            cohort_returns["微盘ST"],
            caps=[valid_caps[symbol] for symbol in microcap_symbols],
            member_count=len(microcap_symbols),
        ),
        other_stats=_stats(
            cohort_returns["普通ST"],
            caps=[valid_caps[symbol] for symbol in other_symbols],
            member_count=len(other_symbols),
        ),
    )


def _load_manifest(
    path: Path, *, manifest_directory: Path, start_date: str,
) -> tuple[dict[str, Any], list[str]]:
    dated_path = manifest_directory / f"{start_date}.json"
    candidates = [dated_path, path]
    selected = next((candidate for candidate in candidates if candidate.is_file()), None)
    if selected is None:
        return {}, ["market-factor manifest 不存在"]
    try:
        payload = json.loads(selected.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"market-factor manifest 无法读取: {exc}"]
    if not isinstance(payload, dict):
        return {}, ["market-factor manifest 顶层必须是对象"]
    gaps = []
    if payload.get("status") != "ready":
        gaps.append("market-factor manifest 当前不是 ready")
    if payload.get("factor_date") != start_date:
        gaps.append(
            f"market-factor 日期不是收益窗口起点: "
            f"{payload.get('factor_date') or 'missing'} != {start_date}"
        )
    definition = payload.get("factor_definition") or {}
    if not isinstance(definition, dict) or definition.get("definition_id") != (
        MICROCAP_DEFINITION_ID
    ):
        gaps.append("market-factor manifest 缺冻结的微盘定义")
    if not payload.get("factor_snapshot_id"):
        gaps.append("market-factor manifest 缺 factor_snapshot_id")
    return payload, gaps


def _endpoint_returns(
    *, price_database: Path, symbols: list[str], start_date: str, end_date: str,
) -> tuple[dict[str, float], list[str]]:
    if not price_database.is_file():
        return {}, ["个股价格数据库不存在"]
    placeholders = ",".join("?" for _ in symbols)
    try:
        with sqlite3.connect(f"file:{price_database}?mode=ro", uri=True) as connection:
            rows = connection.execute(
                "select symbol,trade_date,close from daily_prices "
                f"where symbol in ({placeholders}) and adjust='qfq' "
                "and trade_date in (?,?)",
                (*symbols, start_date, end_date),
            ).fetchall()
    except sqlite3.Error as exc:
        return {}, [f"收益端点查询失败: {exc}"]
    by_symbol: dict[str, dict[str, float]] = {}
    for symbol, trade_date, close in rows:
        if close is not None and float(close) > 0:
            by_symbol.setdefault(str(symbol), {})[str(trade_date)] = float(close)
    returns = {
        symbol: round(values[end_date] / values[start_date] * 100 - 100, 8)
        for symbol, values in by_symbol.items()
        if start_date in values and end_date in values
    }
    return returns, []


def _stats(
    returns: list[float], *, caps: list[float], member_count: int,
) -> dict[str, float | int]:
    values = np.asarray(returns, dtype=float)
    return {
        "member_count": member_count,
        "valid_return_count": len(returns),
        "return_coverage": round(len(returns) / member_count, 8),
        "mean_return": round(float(np.mean(values)), 8),
        "median_return": round(float(np.median(values)), 8),
        "p05_return": round(float(np.percentile(values, 5)), 8),
        "p95_return": round(float(np.percentile(values, 95)), 8),
        "positive_ratio": round(float(np.mean(values > 0)), 8),
        "median_market_value": round(float(statistics.median(caps)), 2),
        "minimum_market_value": round(min(caps), 2),
        "maximum_market_value": round(max(caps), 2),
    }


def _cohort_row(
    *, row_id: str, label: str, symbols: list[str],
    stats: dict[str, float | int],
) -> dict[str, object]:
    examples = symbols[:12]
    return {
        "row_id": row_id,
        "记录类型": "市值分层分布",
        "分组": label,
        "成员数": stats["member_count"],
        "有效收益数": stats["valid_return_count"],
        "收益覆盖率": _pct(float(stats["return_coverage"]) * 100),
        "平均收益": _pct(float(stats["mean_return"])),
        "中位收益": _pct(float(stats["median_return"])),
        "p05": _pct(float(stats["p05_return"])),
        "p95": _pct(float(stats["p95_return"])),
        "上涨占比": _pct(float(stats["positive_ratio"]) * 100),
        "中位总市值": _yi(float(stats["median_market_value"])),
        "样本股票示例": ",".join(examples),
        "其余样本数": max(0, len(symbols) - len(examples)),
    }


def _iso_date(value: str, *, field: str) -> str:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是 YYYY-MM-DD: {value!r}") from exc


def _pct(value: float) -> str:
    return f"{value:.2f}%"


def _pp(value: float) -> str:
    return f"{value:+.2f}个百分点"


def _yi(value: float) -> str:
    return f"{value / 100_000_000:.2f}亿元"
