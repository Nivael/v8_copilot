"""Leakage-safe P7 turnover anomaly features and activity episodes."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import statistics
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from market_activity import MarketActivityFact


CONTRACT_VERSION = "p7_activity_anomaly_v1"
PROFILE_THRESHOLDS = {
    "broad": (95.0, 3.0),
    "balanced": (97.5, 4.0),
    "strict": (99.0, 5.0),
}
RISK_COPY = "异常量价只表示相对历史的交易活跃变化，不证明资金主体、方向、内幕信息或未来收益。"
FORBIDDEN_TERMS = ("资金流入", "主力埋伏", "内幕资金", "买入信号", "胜率", "目标价")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ActivityAnomaly(StrictModel):
    anomaly_id: str = Field(pattern=r"^P7AD-[A-F0-9]{20}$")
    symbol: str = Field(pattern=r"^\d{6}$")
    trade_date: str
    history_count: int = Field(ge=0, le=120)
    turnover_rate_f: float | None = None
    turnover_median_120: float | None = None
    turnover_mad_120: float | None = None
    turnover_percentile_120: float | None = None
    turnover_robust_z_120: float | None = None
    broad: bool = False
    balanced: bool = False
    strict: bool = False
    zero_mad_breakout: bool = False
    post_suspension: bool = False
    calculable: bool = False
    exclusion_reasons: list[str] = Field(default_factory=list)
    pct_chg: float | None = None
    amplitude_pct: float | None = None
    amount: float | None = None
    turnover_rate: float | None = None
    volume_ratio: float | None = None
    total_mv_10k_cny: float | None = None
    st_equal_weight_pct_chg: float | None = None
    csi_2000_pct_chg: float | None = None
    qfq_return_1d: float | None = None
    qfq_return_3d: float | None = None
    qfq_return_5d: float | None = None
    relative_st_1d: float | None = None
    relative_csi_2000_1d: float | None = None
    narrative: str


class ActivityEpisode(StrictModel):
    episode_id: str = Field(pattern=r"^P7AE-[A-F0-9]{20}$")
    symbol: str = Field(pattern=r"^\d{6}$")
    profile: Literal["broad", "balanced", "strict"]
    merge_gap: Literal[3, 5, 10]
    start_date: str
    end_date: str
    hit_count: int = Field(ge=1)
    member_dates: list[str]
    peak_turnover_rate_f: float
    peak_robust_z: float


class AnomalyRun(StrictModel):
    run_id: str = Field(pattern=r"^P7AR-[A-F0-9]{20}$")
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    generated_at: str
    start_date: str
    through: str
    fact_count: int = Field(ge=0)
    calculable_count: int = Field(ge=0)
    broad_hit_count: int = Field(ge=0)
    balanced_hit_count: int = Field(ge=0)
    strict_hit_count: int = Field(ge=0)
    zero_mad_breakout_count: int = Field(ge=0)
    episode_counts: dict[str, int]
    anomalies: list[ActivityAnomaly]
    episodes: list[ActivityEpisode]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _id(prefix: str, *parts: Any) -> str:
    return f"{prefix}-{_digest(parts)[:20].upper()}"


def _feature(
    fact: MarketActivityFact,
    history: list[float],
    *,
    post_suspension: bool,
    benchmarks: dict[tuple[str, str], float | None],
    qfq_returns: dict[tuple[str, str], tuple[float | None, float | None, float | None]],
) -> ActivityAnomaly:
    reasons = list(fact.exclusion_reasons)
    if post_suspension:
        reasons.append("post_suspension_recovery")
    current = fact.turnover_rate_f
    calculable = not reasons and current is not None and len(history) >= 60
    if not reasons and len(history) < 60:
        reasons.append("insufficient_history")
    median = mad = percentile = robust_z = None
    zero_breakout = False
    flags = {key: False for key in PROFILE_THRESHOLDS}
    if calculable and current is not None:
        baseline = history[-120:]
        median = float(statistics.median(baseline))
        deviations = [abs(value - median) for value in baseline]
        mad = float(statistics.median(deviations))
        lower = sum(value < current for value in baseline)
        equal = sum(value == current for value in baseline)
        percentile = (lower + 0.5 * equal) / len(baseline) * 100.0
        if mad > 0:
            robust_z = 0.67448975 * (current - median) / mad
            for profile, (percentile_gate, z_gate) in PROFILE_THRESHOLDS.items():
                flags[profile] = percentile >= percentile_gate and robust_z >= z_gate
        elif current > max(baseline):
            zero_breakout = True
    anomaly_id = _id("P7AD", fact.symbol, fact.trade_date, CONTRACT_VERSION)
    if flags["balanced"]:
        narrative = (
            f"自由流通换手率 {current:.2f}%，处于此前 {len(history[-120:])} 个合格交易日的"
            f" {percentile:.1f}% 分位，robust z={robust_z:.2f}；这是异常交易活跃描述，不是资金身份判断。"
        )
    elif calculable:
        narrative = "活动事实可计算，但未命中预注册 balanced shadow 阈值。"
    else:
        narrative = "活动事实因覆盖、资格或历史长度不足而不生成异常判断。"
    return_1, return_3, return_5 = qfq_returns.get((fact.symbol, fact.trade_date), (None, None, None))
    st_return = benchmarks.get((fact.trade_date, "st_equal_weight_v1"))
    csi_return = benchmarks.get((fact.trade_date, "csi_2000"))
    return ActivityAnomaly(
        anomaly_id=anomaly_id,
        symbol=fact.symbol,
        trade_date=fact.trade_date,
        history_count=min(len(history), 120),
        turnover_rate_f=current,
        turnover_median_120=round(median, 8) if median is not None else None,
        turnover_mad_120=round(mad, 8) if mad is not None else None,
        turnover_percentile_120=round(percentile, 8) if percentile is not None else None,
        turnover_robust_z_120=round(robust_z, 8) if robust_z is not None else None,
        broad=flags["broad"],
        balanced=flags["balanced"],
        strict=flags["strict"],
        zero_mad_breakout=zero_breakout,
        post_suspension=post_suspension,
        calculable=calculable,
        exclusion_reasons=reasons,
        pct_chg=fact.pct_chg,
        amplitude_pct=fact.amplitude_pct,
        amount=fact.amount,
        turnover_rate=fact.turnover_rate,
        volume_ratio=fact.volume_ratio,
        total_mv_10k_cny=fact.total_mv_10k_cny,
        st_equal_weight_pct_chg=st_return,
        csi_2000_pct_chg=csi_return,
        qfq_return_1d=return_1,
        qfq_return_3d=return_3,
        qfq_return_5d=return_5,
        relative_st_1d=(round(return_1 - st_return, 8) if return_1 is not None and st_return is not None else None),
        relative_csi_2000_1d=(round(return_1 - csi_return, 8) if return_1 is not None and csi_return is not None else None),
        narrative=narrative,
    )


def compute_anomalies(
    facts: list[MarketActivityFact],
    *,
    benchmarks: dict[tuple[str, str], float | None] | None = None,
    qfq_closes: dict[tuple[str, str], float] | None = None,
) -> list[ActivityAnomaly]:
    """Compute features using only prior eligible observations; current is appended last."""

    benchmark_map = benchmarks or {}
    qfq_map = qfq_closes or {}
    qfq_history: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=5))
    qfq_returns: dict[tuple[str, str], tuple[float | None, float | None, float | None]] = {}
    for fact in sorted(facts, key=lambda item: (item.trade_date, item.symbol)):
        current_close = qfq_map.get((fact.symbol, fact.trade_date))
        prior_closes = list(qfq_history[fact.symbol])
        returns: list[float | None] = []
        for horizon in (1, 3, 5):
            base = prior_closes[-horizon] if len(prior_closes) >= horizon else None
            returns.append(round((current_close / base - 1) * 100, 8) if current_close is not None and base not in (None, 0) else None)
        qfq_returns[(fact.symbol, fact.trade_date)] = (returns[0], returns[1], returns[2])
        if current_close is not None:
            qfq_history[fact.symbol].append(current_close)
    history: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=120))
    recent_suspension: dict[str, deque[bool]] = defaultdict(lambda: deque(maxlen=5))
    result: list[ActivityAnomaly] = []
    for fact in sorted(facts, key=lambda item: (item.trade_date, item.symbol)):
        prior = list(history[fact.symbol])
        post_suspension = any(recent_suspension[fact.symbol])
        result.append(_feature(
            fact, prior, post_suspension=post_suspension, benchmarks=benchmark_map,
            qfq_returns=qfq_returns,
        ))
        recent_suspension[fact.symbol].append(fact.suspension_status == "suspended")
        if fact.eligible_for_anomaly and not post_suspension and fact.turnover_rate_f is not None:
            history[fact.symbol].append(fact.turnover_rate_f)
    return result


def build_activity_episodes(
    anomalies: list[ActivityAnomaly], *, profile: str, merge_gap: int,
) -> list[ActivityEpisode]:
    if profile not in PROFILE_THRESHOLDS:
        raise ValueError(f"未知 profile: {profile}")
    if merge_gap not in {3, 5, 10}:
        raise ValueError("merge_gap 必须是 3、5 或 10")
    eligible_by_symbol: dict[str, list[ActivityAnomaly]] = defaultdict(list)
    for item in anomalies:
        if item.calculable:
            eligible_by_symbol[item.symbol].append(item)
    episodes: list[ActivityEpisode] = []
    for symbol, rows in eligible_by_symbol.items():
        rows.sort(key=lambda item: item.trade_date)
        index_by_date = {item.trade_date: index for index, item in enumerate(rows)}
        hits = [item for item in rows if bool(getattr(item, profile))]
        groups: list[list[ActivityAnomaly]] = []
        for hit in hits:
            if not groups or index_by_date[hit.trade_date] - index_by_date[groups[-1][-1].trade_date] > merge_gap:
                groups.append([hit])
            else:
                groups[-1].append(hit)
        for group in groups:
            dates = [item.trade_date for item in group]
            peak_turnover = max(item.turnover_rate_f or 0.0 for item in group)
            peak_z = max(item.turnover_robust_z_120 or 0.0 for item in group)
            episodes.append(ActivityEpisode(
                episode_id=_id("P7AE", symbol, profile, merge_gap, dates),
                symbol=symbol,
                profile=profile,  # type: ignore[arg-type]
                merge_gap=merge_gap,  # type: ignore[arg-type]
                start_date=dates[0],
                end_date=dates[-1],
                hit_count=len(group),
                member_dates=dates,
                peak_turnover_rate_f=peak_turnover,
                peak_robust_z=peak_z,
            ))
    return sorted(episodes, key=lambda item: (item.start_date, item.symbol, item.profile, item.merge_gap))


def build_anomaly_run(
    facts: list[MarketActivityFact], *,
    benchmarks: dict[tuple[str, str], float | None] | None = None,
    qfq_closes: dict[tuple[str, str], float] | None = None,
) -> AnomalyRun:
    anomalies = compute_anomalies(facts, benchmarks=benchmarks, qfq_closes=qfq_closes)
    episodes = [
        episode
        for profile in PROFILE_THRESHOLDS
        for gap in (3, 5, 10)
        for episode in build_activity_episodes(anomalies, profile=profile, merge_gap=gap)
    ]
    identity = {
        "contract_version": CONTRACT_VERSION,
        "anomalies": [item.model_dump(mode="json") for item in anomalies],
        "episodes": [item.model_dump(mode="json") for item in episodes],
    }
    return AnomalyRun(
        run_id=_id("P7AR", identity),
        generated_at=datetime.now(timezone.utc).isoformat(),
        start_date=min((item.trade_date for item in anomalies), default=""),
        through=max((item.trade_date for item in anomalies), default=""),
        fact_count=len(facts),
        calculable_count=sum(item.calculable for item in anomalies),
        broad_hit_count=sum(item.broad for item in anomalies),
        balanced_hit_count=sum(item.balanced for item in anomalies),
        strict_hit_count=sum(item.strict for item in anomalies),
        zero_mad_breakout_count=sum(item.zero_mad_breakout for item in anomalies),
        episode_counts={
            f"{profile}_{gap}": sum(item.profile == profile and item.merge_gap == gap for item in episodes)
            for profile in PROFILE_THRESHOLDS for gap in (3, 5, 10)
        },
        anomalies=anomalies,
        episodes=episodes,
    )


class P7IntelligenceRepository:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.executescript("""
            create table if not exists p7_runs (
                run_id text primary key,
                run_kind text not null,
                contract_version text not null,
                start_date text not null,
                through text not null,
                payload_json text not null,
                created_at text not null
            );
            create table if not exists activity_anomalies (
                run_id text not null,
                anomaly_id text not null,
                symbol text not null,
                trade_date text not null,
                payload_json text not null,
                primary key(run_id,anomaly_id)
            );
            create table if not exists activity_episodes (
                run_id text not null,
                episode_id text not null,
                symbol text not null,
                start_date text not null,
                end_date text not null,
                profile text not null,
                merge_gap integer not null,
                payload_json text not null,
                primary key(run_id,episode_id)
            );
        """)
        return connection

    def store_anomaly_run(self, run: AnomalyRun) -> None:
        summary = run.model_dump(mode="json", exclude={"anomalies", "episodes", "generated_at"})
        with self._connect() as connection:
            existing = connection.execute("select payload_json from p7_runs where run_id=?", (run.run_id,)).fetchone()
            if existing is not None and json.loads(existing[0]) != summary:
                raise ValueError("P7 anomaly run ID 已绑定不同内容")
            connection.execute(
                "insert or ignore into p7_runs values (?,?,?,?,?,?,?)",
                (run.run_id, "anomaly", CONTRACT_VERSION, run.start_date, run.through, _canonical(summary), run.generated_at),
            )
            connection.executemany(
                "insert or ignore into activity_anomalies values (?,?,?,?,?)",
                [
                    (run.run_id, item.anomaly_id, item.symbol, item.trade_date, _canonical(item.model_dump(mode="json")))
                    for item in run.anomalies
                ],
            )
            connection.executemany(
                "insert or ignore into activity_episodes values (?,?,?,?,?,?,?,?)",
                [
                    (run.run_id, item.episode_id, item.symbol, item.start_date, item.end_date, item.profile, item.merge_gap, _canonical(item.model_dump(mode="json")))
                    for item in run.episodes
                ],
            )

    def latest_run(self, *, run_kind: str = "anomaly") -> dict[str, Any] | None:
        if not self.path.is_file():
            return None
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            row = connection.execute(
                "select payload_json from p7_runs where run_kind=? order by created_at desc limit 1",
                (run_kind,),
            ).fetchone()
        return json.loads(row[0]) if row else None


def validate_research_language(value: Any) -> None:
    text = _canonical(value)
    hits = [term for term in FORBIDDEN_TERMS if term in text]
    if hits:
        raise ValueError(f"P7 输出含禁止推断词: {', '.join(hits)}")
