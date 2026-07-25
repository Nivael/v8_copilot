"""Read-only P6B same-day ST market-cap size position."""
from __future__ import annotations

import argparse
import bisect
import json
import sqlite3
from calendar import monthrange
from datetime import date
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


class FixedTwelveMonthSizeChange(StrictModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    status: Literal["ready", "partial", "unavailable"]
    gap_codes: list[str] = Field(default_factory=list)
    end_date: str
    comparison_date: str = ""
    month_window: Literal[12] = 12
    end_position: SameDaySizePosition
    comparison_position: SameDaySizePosition | None = None
    percentile_change_points: float | None = None
    start_membership_count: int = Field(default=0, ge=0)
    end_membership_count: int = Field(default=0, ge=0)
    cohort_turnover: float | None = Field(default=None, ge=0, le=1)
    membership_composition_noise: bool = False
    warning: str = SIZE_POSITION_WARNING


class LastValidSizePosition(StrictModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    valuation_date: str
    target_traded_on_valuation_date: bool
    status: Literal["ready", "unavailable"]
    gap_code: Literal[
        "",
        "calendar_unavailable",
        "target_price_history_unavailable",
        "last_valid_snapshot_unavailable",
    ] = ""
    last_valid_trade_date: str = ""
    trading_day_distance: int | None = Field(default=None, ge=0)
    position: SameDaySizePosition | None = None
    warning: str = SIZE_POSITION_WARNING


def _symbol(value: str) -> str:
    compact = str(value).strip()
    if len(compact) != 6 or not compact.isdigit():
        raise ValueError(f"股票代码必须是六位数字: {value!r}")
    return compact


def _calendar_dates(
    *, market_context_database: Path, through: str, start: str = "",
) -> list[str]:
    if not market_context_database.is_file():
        return []
    where = "trade_date<=?"
    params: list[str] = [through]
    if start:
        where += " and trade_date>=?"
        params.append(start)
    try:
        with sqlite3.connect(
            f"file:{market_context_database}?mode=ro", uri=True,
        ) as connection:
            return [
                str(row[0])
                for row in connection.execute(
                    "select trade_date from benchmark_daily "
                    "where benchmark_id='csi_all_share' and "
                    f"{where} order by trade_date",
                    params,
                )
            ]
    except sqlite3.Error:
        return []


def _shift_year(day: str, years: int) -> str:
    parsed = date.fromisoformat(day)
    year = parsed.year + years
    return date(
        year, parsed.month, min(parsed.day, monthrange(year, parsed.month)[1]),
    ).isoformat()


def _membership(
    *, market_context_database: Path, trade_date: str,
) -> set[str]:
    if not market_context_database.is_file():
        return set()
    try:
        with sqlite3.connect(
            f"file:{market_context_database}?mode=ro", uri=True,
        ) as connection:
            return {
                str(row[0])
                for row in connection.execute(
                    "select symbol from st_membership_daily where trade_date=?",
                    (trade_date,),
                )
            }
    except sqlite3.Error:
        return set()


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


def fixed_twelve_month_size_change(
    *,
    market_factor_database: Path,
    market_context_database: Path,
    symbol: str,
    end_date: str,
    coverage_threshold: float = 0.95,
    minimum_cohort_size: int = 20,
    composition_noise_threshold: float = 0.30,
) -> FixedTwelveMonthSizeChange:
    """Compare fixed 12-month size positions without selecting a favorable window."""

    compact = _symbol(symbol)
    if not 0 <= composition_noise_threshold <= 1:
        raise ValueError("composition_noise_threshold 必须在 [0,1]")
    calendar = _calendar_dates(
        market_context_database=market_context_database,
        through=end_date,
    )
    if not calendar:
        end_position = same_day_size_position(
            database=market_factor_database,
            symbol=compact,
            trade_date=end_date,
            coverage_threshold=coverage_threshold,
            minimum_cohort_size=minimum_cohort_size,
        )
        return FixedTwelveMonthSizeChange(
            symbol=compact,
            status="unavailable",
            gap_codes=["calendar_unavailable"],
            end_date=end_date,
            end_position=end_position,
        )
    end_session = calendar[-1]
    anniversary = _shift_year(end_session, -1)
    comparison_candidates = [day for day in calendar if day <= anniversary]
    comparison_date = comparison_candidates[-1] if comparison_candidates else ""
    end_position = same_day_size_position(
        database=market_factor_database,
        symbol=compact,
        trade_date=end_session,
        coverage_threshold=coverage_threshold,
        minimum_cohort_size=minimum_cohort_size,
    )
    if not comparison_date:
        return FixedTwelveMonthSizeChange(
            symbol=compact,
            status="unavailable",
            gap_codes=["comparison_calendar_unavailable"],
            end_date=end_session,
            end_position=end_position,
        )
    comparison_position = same_day_size_position(
        database=market_factor_database,
        symbol=compact,
        trade_date=comparison_date,
        coverage_threshold=coverage_threshold,
        minimum_cohort_size=minimum_cohort_size,
    )
    start_members = _membership(
        market_context_database=market_context_database,
        trade_date=comparison_date,
    )
    end_members = _membership(
        market_context_database=market_context_database,
        trade_date=end_session,
    )
    union = start_members | end_members
    turnover = (
        1 - len(start_members & end_members) / len(union)
        if union else None
    )
    gaps = []
    if end_position.status != "ready":
        gaps.append(f"end_position:{end_position.gap_code}")
    if comparison_position.status != "ready":
        gaps.append(f"comparison_position:{comparison_position.gap_code}")
    if not start_members or not end_members:
        gaps.append("membership_unavailable")
    percentile_change = None
    if (
        end_position.percentile is not None
        and comparison_position.percentile is not None
    ):
        percentile_change = round(
            (end_position.percentile - comparison_position.percentile) * 100,
            6,
        )
    ready = not gaps and percentile_change is not None and turnover is not None
    partial = not ready and bool(
        percentile_change is not None or turnover is not None
    )
    return FixedTwelveMonthSizeChange(
        symbol=compact,
        status="ready" if ready else ("partial" if partial else "unavailable"),
        gap_codes=gaps,
        end_date=end_session,
        comparison_date=comparison_date,
        end_position=end_position,
        comparison_position=comparison_position,
        percentile_change_points=percentile_change,
        start_membership_count=len(start_members),
        end_membership_count=len(end_members),
        cohort_turnover=round(turnover, 8) if turnover is not None else None,
        membership_composition_noise=(
            turnover is not None and turnover > composition_noise_threshold
        ),
    )


def last_valid_size_position(
    *,
    market_factor_database: Path,
    market_context_database: Path,
    price_database: Path,
    symbol: str,
    valuation_date: str,
    coverage_threshold: float = 0.95,
    minimum_cohort_size: int = 20,
) -> LastValidSizePosition:
    """Expose an exact prior position for a suspended target; never stale-fill peers."""

    compact = _symbol(symbol)
    calendar = _calendar_dates(
        market_context_database=market_context_database,
        through=valuation_date,
    )
    if not calendar:
        return LastValidSizePosition(
            symbol=compact,
            valuation_date=valuation_date,
            target_traded_on_valuation_date=False,
            status="unavailable",
            gap_code="calendar_unavailable",
        )
    valuation_session = calendar[-1]
    if not price_database.is_file():
        last_trade = ""
    else:
        try:
            with sqlite3.connect(
                f"file:{price_database}?mode=ro", uri=True,
            ) as connection:
                row = connection.execute(
                    "select max(trade_date) from daily_prices "
                    "where symbol=? and adjust='qfq' and trade_date<=? "
                    "and close is not null",
                    (compact, valuation_session),
                ).fetchone()
            last_trade = str(row[0] or "")
        except sqlite3.Error:
            last_trade = ""
    if not last_trade:
        return LastValidSizePosition(
            symbol=compact,
            valuation_date=valuation_session,
            target_traded_on_valuation_date=False,
            status="unavailable",
            gap_code="target_price_history_unavailable",
        )
    distance = sum(last_trade < day <= valuation_session for day in calendar)
    position = same_day_size_position(
        database=market_factor_database,
        symbol=compact,
        trade_date=last_trade,
        coverage_threshold=coverage_threshold,
        minimum_cohort_size=minimum_cohort_size,
    )
    if position.status != "ready":
        return LastValidSizePosition(
            symbol=compact,
            valuation_date=valuation_session,
            target_traded_on_valuation_date=last_trade == valuation_session,
            status="unavailable",
            gap_code="last_valid_snapshot_unavailable",
            last_valid_trade_date=last_trade,
            trading_day_distance=distance,
            position=position,
        )
    return LastValidSizePosition(
        symbol=compact,
        valuation_date=valuation_session,
        target_traded_on_valuation_date=last_trade == valuation_session,
        status="ready",
        last_valid_trade_date=last_trade,
        trading_day_distance=distance,
        position=position,
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
