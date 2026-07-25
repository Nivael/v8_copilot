"""P6B-1b read-only market repricing map and descriptive AnswerCard adapter."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from market_factors import MarketFactorRepository
from p6b_market_map import (
    FixedTwelveMonthSizeChange,
    LastValidSizePosition,
    fixed_twelve_month_size_change,
    last_valid_size_position,
)
from settings import DATA_ROOT, MARKET_CONTEXT_DB, MARKET_FACTOR_DB

if TYPE_CHECKING:
    from answer_engine import AnswerCard


CONTRACT_VERSION = "v8_p6b_market_repricing_v1"
ST_INDEX_START = "2021-03-17"
DEFAULT_PRICE_DATABASE = (
    DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CapitalStructureCheck(StrictModel):
    status: Literal["clear", "changed", "unknown"]
    start_date: str = ""
    end_date: str = ""
    start_total_shares: float | None = Field(default=None, ge=0)
    end_total_shares: float | None = Field(default=None, ge=0)
    share_count_change: float | None = None
    gap_code: Literal[
        "",
        "start_factor_unavailable",
        "end_factor_unavailable",
        "start_share_count_unavailable",
        "end_share_count_unavailable",
    ] = ""


class BenchmarkContextReturn(StrictModel):
    benchmark_id: Literal["csi_2000", "csi_all_share"]
    status: Literal["ready", "unavailable"]
    anchor_date: str
    end_date: str
    return_value: float | None = None
    gap_code: Literal["", "endpoint_unavailable"] = ""


class MarketCapChangeDecomposition(StrictModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    start_date: str
    end_date: str
    status: Literal["ready", "unavailable"]
    gap_code: Literal[
        "",
        "start_factor_unavailable",
        "end_factor_unavailable",
        "start_market_cap_unavailable",
        "end_market_cap_unavailable",
        "start_share_count_unavailable",
        "end_share_count_unavailable",
        "non_positive_endpoint",
    ] = ""
    start_market_value_rmb: float | None = Field(default=None, ge=0)
    end_market_value_rmb: float | None = Field(default=None, ge=0)
    start_total_shares: float | None = Field(default=None, ge=0)
    end_total_shares: float | None = Field(default=None, ge=0)
    total_market_value_change: float | None = None
    price_effect: float | None = None
    share_count_effect: float | None = None
    interaction_effect: float | None = None
    warning: str = (
        "价格效应与股本效应是乘法恒等分解，仅作描述，不代表老股东实际保留权益。"
    )


class EpisodeRelativeRepricing(StrictModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    episode_start_date: str
    valuation_date: str
    status: Literal["ready", "ready_with_coverage_warning", "unavailable"]
    validation_state: Literal["descriptive_only"] = "descriptive_only"
    gap_codes: list[str] = Field(default_factory=list)
    anchor_date: str = ""
    end_date: str = ""
    trading_day_count: int = Field(default=0, ge=0)
    target_qfq_return: float | None = None
    st_equal_weight_ex_target_return: float | None = None
    episode_relative_repricing: float | None = None
    minimum_daily_benchmark_coverage: float | None = Field(
        default=None, ge=0, le=1,
    )
    below_coverage_warning_day_count: int = Field(default=0, ge=0)
    coverage_warning_threshold: float = Field(default=0.95, ge=0, le=1)
    minimum_valid_benchmark_members: int = Field(default=20, ge=1)
    capital_structure: CapitalStructureCheck
    market_context: list[BenchmarkContextReturn] = Field(default_factory=list)
    warning: str = (
        "episode 相对重定价只描述进入本轮 ST 后相对 ST 组合的价格路径，"
        "不是 alpha、资金流或估值结论。"
    )


class P6BMarketMap(StrictModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    episode_start_date: str
    valuation_date: str
    validation_state: Literal["descriptive_only"] = "descriptive_only"
    last_valid_size_position: LastValidSizePosition
    twelve_month_size_change: FixedTwelveMonthSizeChange
    episode_repricing: EpisodeRelativeRepricing
    market_cap_decomposition: MarketCapChangeDecomposition
    evidence_gaps: list[str] = Field(default_factory=list)


def _symbol(value: str) -> str:
    compact = str(value).strip()
    if len(compact) != 6 or not compact.isdigit():
        raise ValueError(f"股票代码必须是六位数字: {value!r}")
    return compact


def _capital_structure_check(
    *, repository: MarketFactorRepository, symbol: str,
    start_date: str, end_date: str,
) -> CapitalStructureCheck:
    start_snapshot = repository.latest_snapshot(start_date)
    if start_snapshot is None:
        return CapitalStructureCheck(
            status="unknown", start_date=start_date, end_date=end_date,
            gap_code="start_factor_unavailable",
        )
    end_snapshot = repository.latest_snapshot(end_date)
    if end_snapshot is None:
        return CapitalStructureCheck(
            status="unknown", start_date=start_date, end_date=end_date,
            gap_code="end_factor_unavailable",
        )
    start = repository.point(start_snapshot.snapshot_id, symbol)
    end = repository.point(end_snapshot.snapshot_id, symbol)
    if start is None or start.total_shares is None:
        return CapitalStructureCheck(
            status="unknown", start_date=start_date, end_date=end_date,
            gap_code="start_share_count_unavailable",
        )
    if end is None or end.total_shares is None:
        return CapitalStructureCheck(
            status="unknown", start_date=start_date, end_date=end_date,
            gap_code="end_share_count_unavailable",
            start_total_shares=start.total_shares,
        )
    change = end.total_shares / start.total_shares - 1
    return CapitalStructureCheck(
        status="clear" if abs(change) <= 1e-10 else "changed",
        start_date=start_date,
        end_date=end_date,
        start_total_shares=start.total_shares,
        end_total_shares=end.total_shares,
        share_count_change=round(change, 10),
    )


def market_cap_change_decomposition(
    *,
    market_factor_database: Path,
    symbol: str,
    start_date: str,
    end_date: str,
) -> MarketCapChangeDecomposition:
    compact = _symbol(symbol)
    repository = MarketFactorRepository(market_factor_database)
    start_snapshot = repository.latest_snapshot(start_date)
    if start_snapshot is None:
        return MarketCapChangeDecomposition(
            symbol=compact, start_date=start_date, end_date=end_date,
            status="unavailable", gap_code="start_factor_unavailable",
        )
    end_snapshot = repository.latest_snapshot(end_date)
    if end_snapshot is None:
        return MarketCapChangeDecomposition(
            symbol=compact, start_date=start_date, end_date=end_date,
            status="unavailable", gap_code="end_factor_unavailable",
        )
    start = repository.point(start_snapshot.snapshot_id, compact)
    end = repository.point(end_snapshot.snapshot_id, compact)
    checks = (
        ("start_market_cap_unavailable", start, "total_market_value"),
        ("end_market_cap_unavailable", end, "total_market_value"),
        ("start_share_count_unavailable", start, "total_shares"),
        ("end_share_count_unavailable", end, "total_shares"),
    )
    for gap_code, point, field_name in checks:
        if point is None or getattr(point, field_name) is None:
            return MarketCapChangeDecomposition(
                symbol=compact, start_date=start_date, end_date=end_date,
                status="unavailable", gap_code=gap_code,
            )
    assert start is not None and end is not None
    assert start.total_market_value is not None
    assert end.total_market_value is not None
    assert start.total_shares is not None and end.total_shares is not None
    if min(
        start.total_market_value, end.total_market_value,
        start.total_shares, end.total_shares,
    ) <= 0:
        return MarketCapChangeDecomposition(
            symbol=compact, start_date=start_date, end_date=end_date,
            status="unavailable", gap_code="non_positive_endpoint",
        )
    total_change = end.total_market_value / start.total_market_value - 1
    share_effect = end.total_shares / start.total_shares - 1
    price_effect = (
        (end.total_market_value / end.total_shares)
        / (start.total_market_value / start.total_shares)
        - 1
    )
    interaction = price_effect * share_effect
    return MarketCapChangeDecomposition(
        symbol=compact,
        start_date=start_date,
        end_date=end_date,
        status="ready",
        start_market_value_rmb=start.total_market_value,
        end_market_value_rmb=end.total_market_value,
        start_total_shares=start.total_shares,
        end_total_shares=end.total_shares,
        total_market_value_change=round(total_change, 10),
        price_effect=round(price_effect, 10),
        share_count_effect=round(share_effect, 10),
        interaction_effect=round(interaction, 10),
    )


def _endpoint_context_return(
    connection: sqlite3.Connection,
    *, benchmark_id: Literal["csi_2000", "csi_all_share"],
    anchor_date: str, end_date: str,
) -> BenchmarkContextReturn:
    rows = {
        str(trade_date): float(close)
        for trade_date, close in connection.execute(
            "select trade_date,close from benchmark_daily "
            "where benchmark_id=? and trade_date in (?,?) and close is not null",
            (benchmark_id, anchor_date, end_date),
        )
    }
    if anchor_date not in rows or end_date not in rows or rows[anchor_date] <= 0:
        return BenchmarkContextReturn(
            benchmark_id=benchmark_id,
            status="unavailable",
            anchor_date=anchor_date,
            end_date=end_date,
            gap_code="endpoint_unavailable",
        )
    return BenchmarkContextReturn(
        benchmark_id=benchmark_id,
        status="ready",
        anchor_date=anchor_date,
        end_date=end_date,
        return_value=round(rows[end_date] / rows[anchor_date] - 1, 10),
    )


def episode_relative_repricing(
    *,
    market_context_database: Path,
    market_factor_database: Path,
    price_database: Path,
    symbol: str,
    episode_start_date: str,
    valuation_date: str,
    coverage_warning_threshold: float = 0.95,
    minimum_valid_benchmark_members: int = 20,
) -> EpisodeRelativeRepricing:
    """Compute target qfq return versus a daily-membership ST index ex target."""

    compact = _symbol(symbol)
    if not 0 < coverage_warning_threshold <= 1:
        raise ValueError("coverage_warning_threshold 必须在 (0,1]")
    if minimum_valid_benchmark_members < 1:
        raise ValueError("minimum_valid_benchmark_members 必须至少为 1")
    empty_structure = CapitalStructureCheck(
        status="unknown", start_date=episode_start_date,
        end_date=valuation_date, gap_code="start_factor_unavailable",
    )
    base = {
        "symbol": compact,
        "episode_start_date": episode_start_date,
        "valuation_date": valuation_date,
        "coverage_warning_threshold": coverage_warning_threshold,
        "minimum_valid_benchmark_members": minimum_valid_benchmark_members,
    }
    if episode_start_date <= ST_INDEX_START:
        return EpisodeRelativeRepricing(
            **base,
            status="unavailable",
            gap_codes=["st_equal_weight_history_unavailable"],
            capital_structure=empty_structure,
        )
    if not market_context_database.is_file() or not price_database.is_file():
        gaps = []
        if not market_context_database.is_file():
            gaps.append("market_context_database_unavailable")
        if not price_database.is_file():
            gaps.append("price_database_unavailable")
        return EpisodeRelativeRepricing(
            **base, status="unavailable", gap_codes=gaps,
            capital_structure=empty_structure,
        )
    try:
        with sqlite3.connect(
            f"file:{market_context_database}?mode=ro", uri=True,
        ) as market:
            market.execute("attach database ? as prices", (str(price_database),))
            anchor_row = market.execute(
                "select p.trade_date,p.close from prices.daily_prices p "
                "join benchmark_daily s on s.benchmark_id='st_equal_weight_v1' "
                "and s.trade_date=p.trade_date and s.close is not null "
                "where p.symbol=? and p.adjust='qfq' and p.close>0 "
                "and p.trade_date<? and p.trade_date>=? "
                "order by p.trade_date desc limit 1",
                (
                    compact, episode_start_date, ST_INDEX_START,
                ),
            ).fetchone()
            end_row = market.execute(
                "select p.trade_date,p.close from prices.daily_prices p "
                "join benchmark_daily s on s.benchmark_id='st_equal_weight_v1' "
                "and s.trade_date=p.trade_date and s.close is not null "
                "where p.symbol=? and p.adjust='qfq' and p.close>0 "
                "and p.trade_date<=? and p.trade_date>? "
                "order by p.trade_date desc limit 1",
                (
                    compact, valuation_date, episode_start_date,
                ),
            ).fetchone()
            if anchor_row is None or end_row is None:
                gaps = []
                if anchor_row is None:
                    gaps.append("common_anchor_unavailable")
                if end_row is None:
                    gaps.append("common_end_unavailable")
                return EpisodeRelativeRepricing(
                    **base, status="unavailable", gap_codes=gaps,
                    capital_structure=empty_structure,
                )
            anchor_date, anchor_close = str(anchor_row[0]), float(anchor_row[1])
            end_date, end_close = str(end_row[0]), float(end_row[1])
            contexts = [
                _endpoint_context_return(
                    market,
                    benchmark_id=benchmark_id,
                    anchor_date=anchor_date,
                    end_date=end_date,
                )
                for benchmark_id in ("csi_2000", "csi_all_share")
            ]
            dates = [
                str(row[0])
                for row in market.execute(
                    "select trade_date from benchmark_daily "
                    "where benchmark_id='csi_all_share' "
                    "and trade_date>? and trade_date<=? order by trade_date",
                    (anchor_date, end_date),
                )
            ]
            if not dates:
                return EpisodeRelativeRepricing(
                    **base, status="unavailable",
                    gap_codes=["empty_common_window"],
                    anchor_date=anchor_date, end_date=end_date,
                    capital_structure=empty_structure,
                    market_context=contexts,
                )
            aggregates = market.execute(
                "select m.trade_date,count(*) as member_count,"
                "count(p.pct_change) as valid_count,avg(p.pct_change) "
                "from st_membership_daily m "
                "left join prices.daily_prices p on p.symbol=m.symbol "
                "and p.trade_date=m.trade_date and p.adjust='qfq' "
                "where m.trade_date>? and m.trade_date<=? and m.symbol<>? "
                "group by m.trade_date order by m.trade_date",
                (anchor_date, end_date, compact),
            ).fetchall()
            by_date = {
                str(day): (int(members), int(valid), mean_return)
                for day, members, valid, mean_return in aggregates
            }
            missing_dates = [day for day in dates if day not in by_date]
            if missing_dates:
                return EpisodeRelativeRepricing(
                    **base, status="unavailable",
                    gap_codes=["membership_path_incomplete"],
                    anchor_date=anchor_date, end_date=end_date,
                    trading_day_count=len(dates),
                    capital_structure=empty_structure,
                    market_context=contexts,
                )
            coverage = [
                valid / members if members else 0.0
                for members, valid, _ in (by_date[day] for day in dates)
            ]
            if any(
                by_date[day][2] is None
                or by_date[day][1] < minimum_valid_benchmark_members
                for day in dates
            ):
                return EpisodeRelativeRepricing(
                    **base, status="unavailable",
                    gap_codes=["benchmark_path_too_few_valid_members"],
                    anchor_date=anchor_date, end_date=end_date,
                    trading_day_count=len(dates),
                    minimum_daily_benchmark_coverage=round(min(coverage), 8),
                    below_coverage_warning_day_count=sum(
                        value < coverage_warning_threshold
                        for value in coverage
                    ),
                    capital_structure=empty_structure,
                    market_context=contexts,
                )
            benchmark_gross = 1.0
            for day in dates:
                benchmark_gross *= 1 + float(by_date[day][2]) / 100
    except sqlite3.Error:
        return EpisodeRelativeRepricing(
            **base, status="unavailable",
            gap_codes=["source_query_failed"],
            capital_structure=empty_structure,
        )
    capital_structure = _capital_structure_check(
        repository=MarketFactorRepository(market_factor_database),
        symbol=compact,
        start_date=episode_start_date,
        end_date=end_date,
    )
    stock_gross = end_close / anchor_close
    if capital_structure.status != "clear":
        gap = (
            "capital_structure_contaminated"
            if capital_structure.status == "changed"
            else "capital_structure_unknown"
        )
        return EpisodeRelativeRepricing(
            **base,
            status="unavailable",
            gap_codes=[gap],
            anchor_date=anchor_date,
            end_date=end_date,
            trading_day_count=len(dates),
            minimum_daily_benchmark_coverage=round(min(coverage), 8),
            below_coverage_warning_day_count=sum(
                value < coverage_warning_threshold for value in coverage
            ),
            capital_structure=capital_structure,
            market_context=contexts,
        )
    low_coverage_days = sum(
        value < coverage_warning_threshold for value in coverage
    )
    return EpisodeRelativeRepricing(
        **base,
        status=(
            "ready_with_coverage_warning"
            if low_coverage_days else "ready"
        ),
        anchor_date=anchor_date,
        end_date=end_date,
        trading_day_count=len(dates),
        target_qfq_return=round(stock_gross - 1, 10),
        st_equal_weight_ex_target_return=round(benchmark_gross - 1, 10),
        episode_relative_repricing=round(stock_gross / benchmark_gross - 1, 10),
        minimum_daily_benchmark_coverage=round(min(coverage), 8),
        below_coverage_warning_day_count=low_coverage_days,
        capital_structure=capital_structure,
        market_context=contexts,
    )


def build_p6b_market_map(
    *,
    symbol: str,
    episode_start_date: str,
    valuation_date: str,
    market_factor_database: Path = MARKET_FACTOR_DB,
    market_context_database: Path = MARKET_CONTEXT_DB,
    price_database: Path = DEFAULT_PRICE_DATABASE,
) -> P6BMarketMap:
    compact = _symbol(symbol)
    last_position = last_valid_size_position(
        market_factor_database=market_factor_database,
        market_context_database=market_context_database,
        price_database=price_database,
        symbol=compact,
        valuation_date=valuation_date,
    )
    history = fixed_twelve_month_size_change(
        market_factor_database=market_factor_database,
        market_context_database=market_context_database,
        symbol=compact,
        end_date=valuation_date,
    )
    repricing = episode_relative_repricing(
        market_context_database=market_context_database,
        market_factor_database=market_factor_database,
        price_database=price_database,
        symbol=compact,
        episode_start_date=episode_start_date,
        valuation_date=valuation_date,
    )
    decomposition = market_cap_change_decomposition(
        market_factor_database=market_factor_database,
        symbol=compact,
        start_date=episode_start_date,
        end_date=repricing.end_date or valuation_date,
    )
    gaps = []
    if last_position.status != "ready":
        gaps.append(f"last_valid_size_position:{last_position.gap_code}")
    gaps.extend(
        f"twelve_month_size_change:{gap}" for gap in history.gap_codes
    )
    gaps.extend(f"episode_repricing:{gap}" for gap in repricing.gap_codes)
    if decomposition.status != "ready":
        gaps.append(f"market_cap_decomposition:{decomposition.gap_code}")
    return P6BMarketMap(
        symbol=compact,
        episode_start_date=episode_start_date,
        valuation_date=valuation_date,
        last_valid_size_position=last_position,
        twelve_month_size_change=history,
        episode_repricing=repricing,
        market_cap_decomposition=decomposition,
        evidence_gaps=list(dict.fromkeys(gaps)),
    )


def build_p6b_market_answer_card(result: P6BMarketMap) -> "AnswerCard":
    """Adapt the map to frozen AnswerCard v0 without publishing a new top level."""

    from answer_engine import (
        FIXED_CAVEATS,
        AnalysisClaim,
        AnswerCard,
        BackingRef,
    )
    from lens_binding import LensGap

    rows = [
        {
            "row_id": "p6b-boundary",
            "row_type": "information_boundary",
            "validation_state": result.validation_state,
            "statement": "本卡只描述规模位置与市场重定价，不判断价格是否合理。",
        },
        {
            "row_id": "p6b-size-position",
            "row_type": "same_day_size_position",
            **result.last_valid_size_position.model_dump(mode="json"),
        },
        {
            "row_id": "p6b-twelve-month",
            "row_type": "fixed_twelve_month_size_change",
            **result.twelve_month_size_change.model_dump(mode="json"),
        },
        {
            "row_id": "p6b-repricing",
            "row_type": "episode_relative_repricing",
            **result.episode_repricing.model_dump(mode="json"),
        },
        {
            "row_id": "p6b-market-cap-decomposition",
            "row_type": "market_cap_change_decomposition",
            **result.market_cap_decomposition.model_dump(mode="json"),
        },
    ]
    if result.evidence_gaps:
        rows.append({
            "row_id": "p6b-evidence-gaps",
            "row_type": "evidence_gap",
            "gaps": result.evidence_gaps,
        })
    claims = [
        AnalysisClaim(
            text="这些数字只用于描述市场路径，不能单独推出价格合理性。",
            claim_type="caveat",
            backing=BackingRef(kind="query_row", ref="p6b-boundary"),
        ),
    ]
    if result.evidence_gaps:
        claims.append(AnalysisClaim(
            text="存在未通过的数据或资本结构边界，相关数字已保持不可用。",
            claim_type="data_gap",
            backing=BackingRef(kind="query_row", ref="p6b-evidence-gaps"),
        ))
    card = AnswerCard(
        question=f"{result.symbol} 在本轮 ST episode 中如何被市场重定价？",
        object_ref=f"stock:{result.symbol}",
        view="query",
        as_of=result.valuation_date,
        sample_scope=(
            f"{result.symbol} episode {result.episode_start_date}"
            f" 至 {result.valuation_date}；历史 ST membership"
        ),
        evidence_grade="context_only",
        lens_gap=[LensGap(
            gap_id="LG-P6B-MARKET-MAP",
            missing_for="P6B 市场重定价方法 lens",
            sediment_as="question_card:QC-P6B-MARKET-MAP",
            note="当前使用冻结 PRD 契约与可复算数据，不冒充 v7.4 lens。",
        )],
        episode_index_version="p6b_candidate_episode_v1",
        data_snapshot_as_of=result.valuation_date,
        source_freshness={
            "market_factor": (
                result.last_valid_size_position.last_valid_trade_date
                or result.valuation_date
            ),
            "market_context": result.episode_repricing.end_date
            or result.valuation_date,
            "qfq_price": result.episode_repricing.end_date
            or result.valuation_date,
        },
        body_rows=rows,
        analysis_claims=claims,
        caveats=[
            *FIXED_CAVEATS,
            "同日 ST 市值分位只表示规模位置；低尾不等于便宜，高尾不等于昂贵。",
            "episode 相对重定价不是 alpha、资金流、估值偏离或交易信号。",
        ],
        provenance=[
            "local_data/v8_copilot/market_factors_v1.sqlite3",
            "local_data/v8_copilot/market_context_v1.sqlite3",
            "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3::daily_prices[qfq]",
        ],
    )
    card.validate()
    return card
