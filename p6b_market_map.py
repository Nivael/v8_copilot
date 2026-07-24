"""Read-only P6B same-day ST market-cap size position."""
from __future__ import annotations

import argparse
import bisect
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from market_factors import MarketFactorRepository
from settings import MARKET_FACTOR_DB


CONTRACT_VERSION = "v8_p6b_market_map_v1"
SIZE_POSITION_WARNING = (
    "同日 ST 市值分位只表示规模位置；低尾不等于便宜，高尾不等于昂贵。"
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SameDaySizePosition(StrictModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    trade_date: str
    status: Literal["ready", "unavailable"]
    gap_code: Literal[
        "",
        "missing_snapshot",
        "cohort_too_small",
        "coverage_below_gate",
        "target_market_cap_unavailable",
    ] = ""
    snapshot_id: str = ""
    membership_count: int = Field(default=0, ge=0)
    valid_market_cap_count: int = Field(default=0, ge=0)
    coverage_ratio: float = Field(default=0, ge=0, le=1)
    coverage_threshold: float = Field(ge=0, le=1)
    minimum_cohort_size: int = Field(ge=1)
    total_market_value_rmb: float | None = Field(default=None, ge=0)
    percentile: float | None = Field(default=None, ge=0, le=1)
    average_rank: float | None = Field(default=None, ge=1)
    warning: str = SIZE_POSITION_WARNING
    source_ref: str = ""


def _symbol(value: str) -> str:
    compact = str(value).strip()
    if len(compact) != 6 or not compact.isdigit():
        raise ValueError(f"股票代码必须是六位数字: {value!r}")
    return compact


def same_day_size_position(
    *,
    database: Path,
    symbol: str,
    trade_date: str,
    coverage_threshold: float = 0.95,
    minimum_cohort_size: int = 20,
) -> SameDaySizePosition:
    compact = _symbol(symbol)
    if not 0 < coverage_threshold <= 1:
        raise ValueError("coverage_threshold 必须在 (0,1]")
    if minimum_cohort_size < 1:
        raise ValueError("minimum_cohort_size 必须至少为 1")
    repository = MarketFactorRepository(database)
    snapshot = repository.latest_snapshot(trade_date)
    base = {
        "symbol": compact,
        "trade_date": trade_date,
        "coverage_threshold": coverage_threshold,
        "minimum_cohort_size": minimum_cohort_size,
    }
    if snapshot is None:
        return SameDaySizePosition(
            **base,
            status="unavailable",
            gap_code="missing_snapshot",
        )
    points = [
        point for point in repository.points(snapshot.snapshot_id)
        if point.total_market_value is not None
        and point.total_market_value > 0
    ]
    shared = {
        **base,
        "snapshot_id": snapshot.snapshot_id,
        "membership_count": snapshot.membership_count,
        "valid_market_cap_count": len(points),
        "coverage_ratio": snapshot.coverage_ratio,
        "source_ref": (
            "local_data/v8_copilot/market_factors_v1.sqlite3"
            f"::market_cap_daily::{snapshot.snapshot_id}"
        ),
    }
    if len(points) < minimum_cohort_size:
        return SameDaySizePosition(
            **shared,
            status="unavailable",
            gap_code="cohort_too_small",
        )
    if snapshot.coverage_ratio < coverage_threshold:
        return SameDaySizePosition(
            **shared,
            status="unavailable",
            gap_code="coverage_below_gate",
        )
    target = next(
        (point for point in points if point.symbol == compact),
        None,
    )
    if target is None:
        return SameDaySizePosition(
            **shared,
            status="unavailable",
            gap_code="target_market_cap_unavailable",
        )
    values = sorted(float(point.total_market_value) for point in points)
    target_value = float(target.total_market_value)
    left = bisect.bisect_left(values, target_value)
    right = bisect.bisect_right(values, target_value)
    average_rank = (left + 1 + right) / 2
    percentile = (
        (average_rank - 1) / (len(values) - 1)
        if len(values) > 1
        else 0.5
    )
    return SameDaySizePosition(
        **shared,
        status="ready",
        total_market_value_rmb=target_value,
        percentile=round(percentile, 8),
        average_rank=average_rank,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="读取 P6B 同日 ST 市值规模位置"
    )
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--database", type=Path, default=MARKET_FACTOR_DB)
    parser.add_argument("--coverage-threshold", type=float, default=0.95)
    parser.add_argument("--minimum-cohort-size", type=int, default=20)
    args = parser.parse_args(argv)
    result = same_day_size_position(
        database=args.database,
        symbol=args.symbol,
        trade_date=args.trade_date,
        coverage_threshold=args.coverage_threshold,
        minimum_cohort_size=args.minimum_cohort_size,
    )
    print(json.dumps(
        result.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
    ))
    return 0 if result.status == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
