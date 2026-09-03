"""P7 linkage, historical shadow ledger, and read-only daily product payload."""
from __future__ import annotations

import hashlib
import json
import math
import random
import sqlite3
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from market_activity import MarketActivityRepository
from p7_anomalies import ActivityAnomaly, ActivityEpisode, AnomalyRun, RISK_COPY
from p7_announcements import AnnouncementBundle, AnnouncementRun, IssuerTransition
from valuation_episodes import STAGE_EVENT


CONTRACT_VERSION = "p7_daily_intelligence_v1"
LINK_RELATIONS = (
    "activity_before_announcement", "same_day_activity", "activity_after_announcement",
    "announcement_without_activity", "activity_without_announcement",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResearchQueueItem(StrictModel):
    item_id: str = Field(pattern=r"^P7QI-[A-F0-9]{20}$")
    symbol: str = Field(pattern=r"^\d{6}$")
    as_of: str
    priority: Literal["investigate_now", "monitor", "context_only"]
    relation: Literal[
        "activity_before_announcement", "same_day_activity", "activity_after_announcement",
        "announcement_without_activity", "activity_without_announcement",
    ]
    activity_episode_id: str = ""
    announcement_bundle_id: str = ""
    reasons: list[str]
    first_check: str
    p6_context: dict[str, Any] = Field(default_factory=dict)
    not_a_trading_signal: Literal[True] = True


class ShadowOutcome(StrictModel):
    shadow_id: str = Field(pattern=r"^P7SH-[A-F0-9]{20}$")
    episode_id: str
    symbol: str = Field(pattern=r"^\d{6}$")
    start_date: str
    restructuring_stage: str
    market_context: dict[str, float | None]
    mode: Literal["historical_replay", "prospective"]
    horizon_5: bool | None = None
    horizon_10: bool | None = None
    horizon_20: bool | None = None
    horizon_60: bool | None = None
    first_hard_transition_id: str = ""
    first_hard_transition_date: str = ""
    trading_days_to_hard_transition: int | None = None
    control_symbols: list[str]
    control_outcome_20: list[bool | None]
    exchange_reference_status: Literal[
        "already_publicly_flagged", "flagged_after", "not_flagged", "unavailable"
    ] = "unavailable"
    exchange_lead_trading_days: int | None = None
    censored_horizons: list[int]


class LinkageRun(StrictModel):
    run_id: str = Field(pattern=r"^P7LR-[A-F0-9]{20}$")
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    generated_at: str
    through: str
    anomaly_run_id: str
    announcement_run_id: str
    queue_items: list[ResearchQueueItem]
    shadow_outcomes: list[ShadowOutcome]
    relation_counts: dict[str, int]
    shadow_summary: dict[str, Any]


class DailyIntelligencePayload(StrictModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    as_of: str
    checked_through: dict[str, str]
    release_status: dict[str, Literal["descriptive", "shadow", "unavailable"]]
    coverage: dict[str, Any]
    hard_transitions: list[dict[str, Any]]
    priority_announcements: list[dict[str, Any]]
    activity_anomalies: list[dict[str, Any]]
    research_queue: list[dict[str, Any]]
    continuing_watch: list[dict[str, Any]]
    overflow_count: int = Field(ge=0)
    risk_notice: Literal[RISK_COPY] = RISK_COPY


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _id(prefix: str, *parts: Any) -> str:
    return f"{prefix}-{_digest(parts)[:20].upper()}"


def _distance(calendar_index: dict[str, int], left: str, right: str) -> int | None:
    if left not in calendar_index or right not in calendar_index:
        return None
    return calendar_index[right] - calendar_index[left]


def _nearest_bundle(
    episode: ActivityEpisode, bundles: list[AnnouncementBundle],
    calendar_index: dict[str, int], window: int = 20,
) -> tuple[AnnouncementBundle | None, str]:
    candidates: list[tuple[int, AnnouncementBundle]] = []
    for bundle in bundles:
        if bundle.symbol != episode.symbol or not bundle.priority_reasons:
            continue
        gap = _distance(calendar_index, episode.start_date, bundle.announcement_date)
        if gap is not None and abs(gap) <= window:
            candidates.append((gap, bundle))
    if not candidates:
        return None, "activity_without_announcement"
    gap, bundle = min(candidates, key=lambda item: (abs(item[0]), item[0], item[1].bundle_id))
    if gap > 0:
        return bundle, "activity_before_announcement"
    if gap == 0:
        return bundle, "same_day_activity"
    return bundle, "activity_after_announcement"


def _control_symbols(
    episode: ActivityEpisode,
    anomalies_by_date: dict[str, list[ActivityAnomaly]],
    valuation_stage_map: dict[tuple[str, str], str],
) -> list[str]:
    target = next((item for item in anomalies_by_date.get(episode.start_date, []) if item.symbol == episode.symbol), None)
    if target is None or target.total_mv_10k_cny is None or target.total_mv_10k_cny <= 0:
        return []
    target_stage = valuation_stage_map.get((episode.symbol, episode.start_date), "unknown")
    if target_stage == "unknown":
        return []
    candidates = [
        item for item in anomalies_by_date.get(episode.start_date, [])
        if item.symbol != episode.symbol and item.calculable and not item.balanced
        and item.total_mv_10k_cny is not None and item.total_mv_10k_cny > 0
        and valuation_stage_map.get((item.symbol, episode.start_date), "unknown") == target_stage
    ]
    candidates.sort(key=lambda item: (
        abs(math.log(item.total_mv_10k_cny or 1) - math.log(target.total_mv_10k_cny or 1)),
        item.symbol,
    ))
    return [item.symbol for item in candidates[:3]]


def _outcome_within(
    *, symbol: str, start_date: str, horizon: int,
    transitions_by_symbol: dict[str, list[IssuerTransition]],
    calendar_index: dict[str, int], max_index: int,
) -> tuple[bool | None, IssuerTransition | None, int | None]:
    start_index = calendar_index.get(start_date)
    if start_index is None or start_index + horizon > max_index:
        return None, None, None
    for transition in transitions_by_symbol.get(symbol, []):
        distance = _distance(calendar_index, start_date, transition.available_as_of)
        if distance is not None and 0 < distance <= horizon:
            return True, transition, distance
    return False, None, None


def _wilson_interval(successes: int, observations: int) -> list[float] | None:
    if observations <= 0:
        return None
    z = 1.959963984540054
    proportion = successes / observations
    denominator = 1 + z * z / observations
    centre = (proportion + z * z / (2 * observations)) / denominator
    half = z * math.sqrt(
        proportion * (1 - proportion) / observations
        + z * z / (4 * observations * observations)
    ) / denominator
    return [round(max(0.0, centre - half), 8), round(min(1.0, centre + half), 8)]


def _company_cluster_bootstrap_interval(
    outcomes: list[ShadowOutcome], *, samples: int = 2000,
) -> list[float] | None:
    clusters: dict[str, list[bool]] = defaultdict(list)
    for item in outcomes:
        if item.horizon_20 is not None:
            clusters[item.symbol].append(item.horizon_20)
    companies = sorted(clusters)
    if not companies:
        return None
    seed = int(_digest({key: clusters[key] for key in companies})[:16], 16)
    generator = random.Random(seed)
    rates: list[float] = []
    for _ in range(samples):
        selected = [generator.choice(companies) for _ in companies]
        observations = [value for company in selected for value in clusters[company]]
        rates.append(sum(value is True for value in observations) / len(observations))
    rates.sort()
    lower = rates[int((samples - 1) * .025)]
    upper = rates[int((samples - 1) * .975)]
    return [round(lower, 8), round(upper, 8)]


def build_linkage_run(
    *, anomaly_run: AnomalyRun, announcement_run: AnnouncementRun,
    trading_calendar: list[str], mode: Literal["historical_replay", "prospective"] = "historical_replay",
    exchange_references: dict[tuple[str, str], list[str]] | None = None,
    valuation_stage_map: dict[tuple[str, str], str] | None = None,
    shadow_start_date: str = "",
) -> LinkageRun:
    calendar = sorted(dict.fromkeys(trading_calendar))
    calendar_index = {day: index for index, day in enumerate(calendar)}
    bundles = announcement_run.bundles
    event_dates = {
        item.announcement_date for item in bundles
    } | {
        item.available_as_of for item in announcement_run.transitions
    } | {
        day for (_symbol, day) in (exchange_references or {})
    }
    for event_date in sorted(event_dates):
        if event_date in calendar_index:
            continue
        position = bisect_left(calendar, event_date)
        if position < len(calendar):
            calendar_index[event_date] = position
    stages = valuation_stage_map or {}
    balanced = [
        item for item in anomaly_run.episodes
        if item.profile == "balanced" and item.merge_gap == 5
    ]
    queue: list[ResearchQueueItem] = []
    linked_bundle_ids: set[str] = set()
    for episode in balanced:
        bundle, relation = _nearest_bundle(episode, bundles, calendar_index)
        if bundle:
            linked_bundle_ids.add(bundle.bundle_id)
        reasons = [
            "命中预注册 balanced 异常交易活跃阈值",
            {
                "activity_before_announcement": "异常早于重点公告，先排查信息缺口",
                "same_day_activity": "活动与公告同日，不能声称领先",
                "activity_after_announcement": "活动更可能是公开信息后的交易反应",
                "activity_without_announcement": "暂未覆盖对应重点正式公告，优先补证",
            }[relation],
        ]
        priority: Literal["investigate_now", "monitor", "context_only"] = (
            "investigate_now" if relation in {"activity_before_announcement", "activity_without_announcement"}
            else "monitor"
        )
        queue.append(ResearchQueueItem(
            item_id=_id("P7QI", episode.episode_id, bundle.bundle_id if bundle else "", relation),
            symbol=episode.symbol, as_of=episode.start_date, priority=priority,
            relation=relation, activity_episode_id=episode.episode_id,
            announcement_bundle_id=bundle.bundle_id if bundle else "",
            reasons=reasons,
            first_check=("核对公告覆盖、停牌/一字板排除及潜在未披露负债或程序变化" if relation == "activity_without_announcement" else "阅读正式公告并核对状态跃迁"),
            p6_context={
                "valuation_stage": stages.get((episode.symbol, episode.start_date), "unknown"),
                "asset_solvency_context": "withheld_until_p6_published",
                "changes_activity_truth": False,
            },
        ))
    balanced_by_symbol: dict[str, list[ActivityEpisode]] = defaultdict(list)
    for episode in balanced:
        balanced_by_symbol[episode.symbol].append(episode)
    for bundle in bundles:
        if not bundle.priority_reasons or bundle.bundle_id in linked_bundle_ids:
            continue
        # “无活动”只有在活动事实实际覆盖该日期时才成立；P7A 可以拥有更长的状态机历史。
        if not anomaly_run.start_date <= bundle.announcement_date <= anomaly_run.through:
            continue
        nearby = False
        for episode in balanced_by_symbol.get(bundle.symbol, []):
            gap = _distance(calendar_index, episode.start_date, bundle.announcement_date)
            if gap is not None and abs(gap) <= 20:
                nearby = True
                break
        if nearby:
            continue
        queue.append(ResearchQueueItem(
            item_id=_id("P7QI", bundle.bundle_id, "announcement_without_activity"),
            symbol=bundle.symbol, as_of=bundle.announcement_date,
            priority="investigate_now" if bundle.hard_event_types else "context_only",
            relation="announcement_without_activity",
            announcement_bundle_id=bundle.bundle_id,
            reasons=["重点正式公告未伴随合格 balanced 异常；公告事实仍需独立研究"],
            first_check="阅读正式公告并更新发行人状态或研究缺口",
            p6_context={
                "valuation_stage": stages.get((bundle.symbol, bundle.announcement_date), "unknown"),
                "asset_solvency_context": "withheld_until_p6_published",
                "changes_activity_truth": False,
            },
        ))

    transitions_by_symbol: dict[str, list[IssuerTransition]] = defaultdict(list)
    for transition in announcement_run.transitions:
        if transition.evidence_status == "verified" and not transition.not_hard_outcome:
            transitions_by_symbol[transition.symbol].append(transition)
    for rows in transitions_by_symbol.values():
        rows.sort(key=lambda item: item.available_as_of)
    anomalies_by_date: dict[str, list[ActivityAnomaly]] = defaultdict(list)
    for item in anomaly_run.anomalies:
        anomalies_by_date[item.trade_date].append(item)
    exchange = exchange_references or {}
    outcomes: list[ShadowOutcome] = []
    shadow_episodes = [
        episode for episode in balanced
        if mode == "historical_replay" or not shadow_start_date or episode.start_date >= shadow_start_date
    ]
    max_index = len(calendar) - 1
    for episode in shadow_episodes:
        values: dict[int, bool | None] = {}
        first: IssuerTransition | None = None
        first_distance: int | None = None
        censored: list[int] = []
        for horizon in (5, 10, 20, 60):
            value, transition, distance = _outcome_within(
                symbol=episode.symbol, start_date=episode.start_date, horizon=horizon,
                transitions_by_symbol=transitions_by_symbol,
                calendar_index=calendar_index, max_index=max_index,
            )
            values[horizon] = value
            if value is None:
                censored.append(horizon)
            if transition and (first_distance is None or (distance or 10**9) < first_distance):
                first, first_distance = transition, distance
        controls = _control_symbols(episode, anomalies_by_date, stages)
        control_outcomes = [
            _outcome_within(
                symbol=symbol, start_date=episode.start_date, horizon=20,
                transitions_by_symbol=transitions_by_symbol,
                calendar_index=calendar_index, max_index=max_index,
            )[0]
            for symbol in controls
        ]
        public_days = sorted({
            day for (symbol, day), _types in exchange.items() if symbol == episode.symbol and day in calendar_index
        })
        public_status: Literal["already_publicly_flagged", "flagged_after", "not_flagged", "unavailable"] = "unavailable"
        public_lead = None
        if exchange_references is not None:
            relevant = [(_distance(calendar_index, episode.start_date, day), day) for day in public_days]
            relevant = [(gap, day) for gap, day in relevant if gap is not None and -20 <= gap <= 20]
            if any(gap <= 0 for gap, _day in relevant):
                public_status = "already_publicly_flagged"
                public_lead = max(gap for gap, _day in relevant if gap <= 0)
            elif relevant:
                public_status = "flagged_after"
                public_lead = min(gap for gap, _day in relevant if gap > 0)
            else:
                public_status = "not_flagged"
        outcomes.append(ShadowOutcome(
            shadow_id=_id("P7SH", mode, episode.episode_id, announcement_run.run_id),
            episode_id=episode.episode_id, symbol=episode.symbol,
            start_date=episode.start_date, mode=mode,
            restructuring_stage=stages.get((episode.symbol, episode.start_date), "unknown"),
            market_context={
                "st_equal_weight_pct_chg": next((item.st_equal_weight_pct_chg for item in anomalies_by_date.get(episode.start_date, []) if item.symbol == episode.symbol), None),
                "csi_2000_pct_chg": next((item.csi_2000_pct_chg for item in anomalies_by_date.get(episode.start_date, []) if item.symbol == episode.symbol), None),
            },
            horizon_5=values[5], horizon_10=values[10],
            horizon_20=values[20], horizon_60=values[60],
            first_hard_transition_id=first.transition_id if first else "",
            first_hard_transition_date=first.available_as_of if first else "",
            trading_days_to_hard_transition=first_distance,
            control_symbols=controls, control_outcome_20=control_outcomes,
            exchange_reference_status=public_status,
            exchange_lead_trading_days=public_lead,
            censored_horizons=censored,
        ))
    observed20 = [item.horizon_20 for item in outcomes if item.horizon_20 is not None]
    controls20 = [value for item in outcomes for value in item.control_outcome_20 if value is not None]
    matched_control_episodes = sum(bool(item.control_symbols) for item in outcomes)
    shadow_summary = {
        "summary_contract": "p7d_shadow_summary_v2",
        "mode": mode,
        "episode_count": len(outcomes),
        "company_count": len({item.symbol for item in outcomes}),
        "observed_horizon_20_count": len(observed20),
        "episode_hard_node_rate_20": round(sum(value is True for value in observed20) / len(observed20), 8) if observed20 else None,
        "control_observation_count_20": len(controls20),
        "matched_control_episode_count": matched_control_episodes,
        "matched_control_episode_ratio": (
            round(matched_control_episodes / len(outcomes), 8) if outcomes else None
        ),
        "control_hard_node_rate_20": round(sum(value is True for value in controls20) / len(controls20), 8) if controls20 else None,
        "uncertainty": {
            "episode_wilson_95": _wilson_interval(sum(value is True for value in observed20), len(observed20)),
            "episode_company_cluster_bootstrap_95": _company_cluster_bootstrap_interval(outcomes),
            "control_wilson_95": _wilson_interval(sum(value is True for value in controls20), len(controls20)),
            "bootstrap_samples": 2000,
        },
        "cluster_unit": "company",
        "inference_status": "descriptive_only",
        "exchange_reference_status": "available" if exchange_references is not None else "unavailable",
        "shadow_start_date": shadow_start_date,
    }
    identity = {
        "contract_version": CONTRACT_VERSION,
        "summary_contract": "p7d_shadow_summary_v2",
        "anomaly_run_id": anomaly_run.run_id,
        "announcement_run_id": announcement_run.run_id,
        "queue": [item.model_dump(mode="json") for item in queue],
        "shadow": [item.model_dump(mode="json") for item in outcomes],
    }
    return LinkageRun(
        run_id=_id("P7LR", identity),
        generated_at=datetime.now(timezone.utc).isoformat(),
        through=max(anomaly_run.through, announcement_run.through),
        anomaly_run_id=anomaly_run.run_id,
        announcement_run_id=announcement_run.run_id,
        queue_items=sorted(queue, key=lambda item: (item.as_of, item.priority, item.symbol)),
        shadow_outcomes=outcomes,
        relation_counts=dict(Counter(item.relation for item in queue)),
        shadow_summary=shadow_summary,
    )


def load_valuation_stage_map(
    database: Path, *, dates: list[str],
) -> dict[tuple[str, str], str]:
    """Materialize verified point-in-time stages without using later episode state."""

    if not database.is_file() or not dates:
        return {}
    requested = sorted(set(dates))
    result: dict[tuple[str, str], str] = {}
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "select symbol,start_date,end_date,evidence_status,payload_json "
            "from valuation_episodes where evidence_status='verified'"
        ).fetchall()
    for symbol, start_date, end_date, _status, payload_json in rows:
        payload = json.loads(payload_json)
        events = sorted(
            payload.get("input_events") or [],
            key=lambda item: (str(item.get("information_available_date") or ""), str(item.get("event_id") or "")),
        )
        for day in requested:
            if not str(start_date) <= day <= str(end_date):
                continue
            stage = "st_distress_only"
            for event in events:
                if str(event.get("information_available_date") or "") > day:
                    break
                candidate = STAGE_EVENT.get(str(event.get("event_type") or ""))
                if candidate:
                    stage = candidate
            result[(str(symbol), day)] = stage
    return result


class LinkageRepository:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.executescript("""
            create table if not exists linkage_runs (
                run_id text primary key, contract_version text not null,
                through text not null, summary_json text not null, created_at text not null
            );
            create table if not exists research_queue_items (
                run_id text not null, item_id text not null, symbol text not null,
                as_of text not null, payload_json text not null,
                primary key(run_id,item_id)
            );
            create table if not exists shadow_outcomes (
                run_id text not null, shadow_id text not null, symbol text not null,
                start_date text not null, mode text not null, payload_json text not null,
                primary key(run_id,shadow_id)
            );
        """)
        return connection

    def store(self, run: LinkageRun) -> None:
        summary = run.model_dump(mode="json", exclude={"queue_items", "shadow_outcomes", "generated_at"})
        with self._connect() as connection:
            existing = connection.execute("select summary_json from linkage_runs where run_id=?", (run.run_id,)).fetchone()
            if existing is not None and json.loads(existing[0]) != summary:
                raise ValueError("P7 linkage run ID 已绑定不同内容")
            connection.execute(
                "insert or ignore into linkage_runs values (?,?,?,?,?)",
                (run.run_id, CONTRACT_VERSION, run.through, _canonical(summary), run.generated_at),
            )
            connection.executemany(
                "insert or ignore into research_queue_items values (?,?,?,?,?)",
                [(run.run_id, item.item_id, item.symbol, item.as_of, _canonical(item.model_dump(mode="json"))) for item in run.queue_items],
            )
            connection.executemany(
                "insert or ignore into shadow_outcomes values (?,?,?,?,?,?)",
                [(run.run_id, item.shadow_id, item.symbol, item.start_date, item.mode, _canonical(item.model_dump(mode="json"))) for item in run.shadow_outcomes],
            )


def _latest_run_id(connection: sqlite3.Connection, table: str) -> str:
    row = connection.execute(f"select run_id from {table} order by created_at desc limit 1").fetchone()
    return str(row[0]) if row else ""


def build_daily_payload(
    *, as_of: str, activity_database: Path, intelligence_database: Path,
    top_n: int = 20,
) -> DailyIntelligencePayload:
    activity = MarketActivityRepository(activity_database)
    facts = [item for item in activity.latest_facts(start_date=as_of, through=as_of)]
    snapshot = next((item for item in reversed(activity.snapshots(start_date=as_of, through=as_of))), None)
    activity_dates = sorted({
        item.trade_date for item in activity.snapshots(through=as_of)
        if item.daily_row_count and item.daily_basic_row_count and item.limit_row_count
    })
    activity_date_index = {day: index for index, day in enumerate(activity_dates)}
    hard: list[dict[str, Any]] = []
    announcements: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []
    queue: list[dict[str, Any]] = []
    continuing: list[dict[str, Any]] = []
    announcement_run_available = False
    anomaly_run_available = False
    linkage_run_available = False
    release_decisions: dict[str, str] = {}
    checked = {"market_activity": snapshot.trade_date if snapshot else "", "announcements": "", "linkage": ""}
    if intelligence_database.is_file():
        with sqlite3.connect(f"file:{intelligence_database}?mode=ro", uri=True) as connection:
            announcement_run = _latest_run_id(connection, "announcement_runs")
            anomaly_run = _latest_run_id(connection, "p7_runs")
            linkage_run = _latest_run_id(connection, "linkage_runs")
            if announcement_run:
                announcement_run_available = True
                row = connection.execute("select through from announcement_runs where run_id=?", (announcement_run,)).fetchone()
                checked["announcements"] = str(row[0])
                hard = [json.loads(row[0]) for row in connection.execute(
                    "select payload_json from issuer_transitions where run_id=? and available_as_of=? order by symbol",
                    (announcement_run, as_of),
                )]
                announcements = [json.loads(row[0]) for row in connection.execute(
                    "select payload_json from announcement_bundles where run_id=? and announcement_date=? order by symbol",
                    (announcement_run, as_of),
                ) if json.loads(row[0]).get("priority_reasons")]
            if anomaly_run:
                anomaly_run_available = True
                anomalies = [json.loads(row[0]) for row in connection.execute(
                    "select payload_json from activity_anomalies where run_id=? and trade_date=? order by symbol",
                    (anomaly_run, as_of),
                ) if json.loads(row[0]).get("balanced")]
                if as_of in activity_date_index:
                    for row in connection.execute(
                        "select payload_json from activity_episodes where run_id=? and profile='balanced' "
                        "and merge_gap=5 and end_date<? order by end_date desc,symbol",
                        (anomaly_run, as_of),
                    ):
                        episode = json.loads(row[0])
                        end_date = str(episode.get("end_date") or "")
                        if end_date not in activity_date_index:
                            continue
                        distance = activity_date_index[as_of] - activity_date_index[end_date]
                        if not 1 <= distance <= 5:
                            continue
                        continuing.append({
                            "episode_id": episode.get("episode_id"),
                            "symbol": episode.get("symbol"),
                            "start_date": episode.get("start_date"),
                            "last_hit_date": end_date,
                            "eligible_trading_days_since_last_hit": distance,
                            "reason": "balanced 异常 episode 仍在 5 个合格交易日合并观察窗内",
                            "next_check": "检查新正式公告；满 5 个合格交易日后关闭或由新命中延续",
                            "not_a_trading_signal": True,
                        })
            if linkage_run:
                linkage_run_available = True
                row = connection.execute("select through from linkage_runs where run_id=?", (linkage_run,)).fetchone()
                checked["linkage"] = str(row[0])
                queue = [json.loads(row[0]) for row in connection.execute(
                    "select payload_json from research_queue_items where run_id=? and as_of=? order by symbol",
                    (linkage_run, as_of),
                )]
            tables = {str(row[0]) for row in connection.execute("select name from sqlite_master where type='table'")}
            if "p7_review_decisions" in tables:
                for row in connection.execute(
                    "select decision_json from p7_review_decisions order by imported_at"
                ):
                    decision = json.loads(row[0])
                    release_decisions[str(decision.get("target_field") or "")] = str(decision.get("decision") or "")
    priority_rank = {"investigate_now": 0, "monitor": 1, "context_only": 2}
    queue.sort(key=lambda item: (priority_rank.get(item.get("priority"), 9), item.get("symbol", "")))
    overflow = max(0, len(queue) - top_n)
    return DailyIntelligencePayload(
        as_of=as_of,
        checked_through=checked,
        release_status={
            "p7a_announcements": (
                "unavailable" if not announcement_run_available or release_decisions.get("p7a_release_status") == "return_to_data_gap"
                else "descriptive" if release_decisions.get("p7a_release_status") == "publish_descriptive_only"
                else "shadow"
            ),
            "p7b_activity": (
                "unavailable" if not anomaly_run_available or release_decisions.get("p7bc_release_status") == "return_to_data_gap"
                else "shadow"
            ),
            "p7c_linkage": (
                "unavailable" if not linkage_run_available or release_decisions.get("p7bc_release_status") == "return_to_data_gap"
                else "shadow"
            ),
        },
        coverage={
            "membership_count": snapshot.membership_count if snapshot else 0,
            "activity_row_count": len(facts),
            "turnover_rate_f_coverage": snapshot.coverage_ratio if snapshot else 0.0,
            "full_universe_ready": bool(snapshot and snapshot.coverage_ratio >= 0.95),
        },
        hard_transitions=hard,
        priority_announcements=announcements,
        activity_anomalies=anomalies,
        research_queue=queue[:top_n],
        continuing_watch=continuing[:top_n],
        overflow_count=overflow,
    )
