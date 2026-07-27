"""Verified P6B valuation episodes built from lifecycle and official event facts."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from p6b_dry_plan import build_p6b_dry_plan


CONTRACT_VERSION = "valuation_episode_v1"
MATERIALIZER_VERSION = "v1.0.3"
STAGES = (
    "st_distress_only",
    "restructuring_application_disclosed",
    "pre_restructuring_started",
    "formal_restructuring_accepted",
    "investor_recruitment",
    "plan_key_terms_disclosed",
)
STAGE_EVENT = {
    "restructuring_application_disclosed": "restructuring_application_disclosed",
    "pre_restructuring_started": "pre_restructuring_started",
    "formal_restructuring_accepted": "formal_restructuring_accepted",
    "investor_recruitment_started": "investor_recruitment",
    "restructuring_plan_published": "plan_key_terms_disclosed",
}
RELATED_ENTITY_TERMS = ("子公司", "孙公司", "控股股东", "参股公司")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PilotSymbol(StrictModel):
    symbol: str = Field(pattern=r"^\d{6}$")
    selection_tags: list[str]


class EpisodePilotManifest(StrictModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    pilot_id: str
    as_of: str
    short_membership_gap_max_trade_days: Literal[3] = 3
    selection_rule: str
    symbols: list[PilotSymbol] = Field(min_length=5, max_length=10)

    @model_validator(mode="after")
    def frozen(self) -> "EpisodePilotManifest":
        _iso(self.as_of)
        if len({item.symbol for item in self.symbols}) != len(self.symbols):
            raise ValueError("pilot symbols 不得重复")
        return self


class VerifiedEvent(StrictModel):
    event_id: str
    symbol: str
    event_type: str
    event_date: str
    information_available_date: str
    source_kind: Literal["p6a_verified_fact", "official_title_exact"]
    source_ref: str
    title: str
    evidence_status: Literal["verified_official_source"] = "verified_official_source"


class ValuationEpisode(StrictModel):
    episode_id: str
    symbol: str
    start_date: str
    end_date: str
    is_open: bool
    component_candidate_ids: list[str]
    merged_membership_gap_trade_days: int = 0
    start_boundary_status: Literal["exact_status_start", "status_interval_covered", "membership_only"]
    end_boundary_status: Literal[
        "open", "exact_status_end", "status_end_nearby", "membership_only"
    ]
    current_stage: str
    max_stage_reached: str
    procedure_status: Literal[
        "none", "active", "terminated", "plan_boundary_reached"
    ]
    p6c_boundary_date: str = ""
    input_stop_date: str = ""
    input_events: list[VerifiedEvent]
    outcome_events: list[VerifiedEvent]
    boundary_conflicts: list[str]
    m6_candidate_count: int
    evidence_status: Literal["verified", "provisional_boundary"]


class ReviewCluster(StrictModel):
    cluster_id: str
    family: str
    recommendation: str
    affected_episode_count: int
    representative_episode_ids: list[str]
    resolution: Literal[
        "auto_merge", "auto_dedupe", "keep_same_episode", "stop_input",
        "need_more_evidence"
    ]
    human_required: bool = False


class EpisodeRunResult(StrictModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    run_id: str
    pilot_id: str
    as_of: str
    generated_at: str
    materializer_version: Literal[MATERIALIZER_VERSION] = MATERIALIZER_VERSION
    source_manifest_digest: str
    candidate_episode_count: int
    verified_episode_count: int
    provisional_episode_count: int
    merged_gap_count: int
    verified_event_count: int
    p6a_raw_event_count: int
    p6a_deduped_event_count: int
    stage_counts: dict[str, int]
    review_clusters: list[ReviewCluster]
    human_required_cluster_count: int
    pilot_episodes: list[ValuationEpisode]
    conclusions: list[str]


def _iso(value: object) -> str:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"非法日期: {value!r}") from exc


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _id(prefix: str, *parts: object) -> str:
    return f"{prefix}-{_digest(parts)[:20].upper()}"


def _connect_ro(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def classify_official_title(title: str) -> str | None:
    if any(term in title for term in RELATED_ENTITY_TERMS):
        return None
    if any(term in title for term in ("重整计划执行完毕", "执行完毕重整计划", "重整程序终结")):
        return "restructuring_completed"
    if any(term in title for term in ("终止预重整", "终止重整", "终结预重整", "宣告破产")):
        return "restructuring_terminated"
    if any(term in title for term in ("裁定批准重整计划", "批准公司重整计划", "法院批准重整计划")):
        return "restructuring_plan_approved"
    if any(term in title for term in ("重整计划（草案）", "重整计划(草案)", "重整计划草案")):
        deadline_only = any(
            term in title
            for term in ("延期提交", "提交重整计划草案期限", "不计入提交", "延长提交")
        )
        actual_terms = any(
            term in title
            for term in (
                "重整计划草案之出资人权益调整方案",
                "重整计划草案之经营方案",
            )
        ) or title.rstrip("：: ").endswith(
            ("重整计划草案", "重整计划（草案）", "重整计划(草案)")
        )
        if not deadline_only and actual_terms:
            return "restructuring_plan_published"
    if (
        "重整投资人" in title
        and any(term in title for term in ("公开招募", "招募和遴选", "招募重整投资人"))
    ):
        return "investor_recruitment_started"
    if any(term in title for term in ("裁定受理公司重整", "法院受理公司重整", "裁定受理重整")):
        return "formal_restructuring_accepted"
    if any(
        term in title
        for term in ("启动预重整", "预重整决定书", "受理预重整", "延长预重整期限决定书")
    ):
        return "pre_restructuring_started"
    if any(
        term in title
        for term in (
            "拟向法院申请破产重整", "申请重整及预重整", "被申请重整",
            "债权人申请公司重整", "向法院申请重整及预重整",
        )
    ):
        return "restructuring_application_disclosed"
    return None


def _load_title_events(database: Path, *, as_of: str) -> list[VerifiedEvent]:
    with _connect_ro(database) as connection:
        rows = connection.execute(
            "select announcement_id,symbol,announcement_date,title,coalesce(url,'') url "
            "from company_announcements where announcement_date<=? "
            "and (title like '%重整%' or title like '%破产%') "
            "order by announcement_date,announcement_id",
            (as_of,),
        ).fetchall()
        alias_rows = connection.execute(
            "select symbol,name from stocks_meta union all "
            "select symbol,old_name from name_changes where old_name is not null union all "
            "select symbol,new_name from name_changes union all "
            "select symbol,status_name from st_status_history"
        ).fetchall()
    aliases: dict[str, set[str]] = defaultdict(set)
    for row in alias_rows:
        alias = str(row[1] or "").split(":", 1)[0]
        alias = alias.replace("*ST", "").replace("ST", "").replace("退", "")
        alias = alias.strip(" *")
        if len(alias) >= 2:
            aliases[str(row[0])].add(alias)
    events = []
    for row in rows:
        event_type = classify_official_title(str(row["title"]))
        if event_type is None:
            continue
        title = str(row["title"])
        if event_type == "restructuring_plan_published":
            generic = title.startswith(
                ("重整计划", "预重整计划", "《重整计划")
            )
            if not generic and not any(
                alias in title for alias in aliases.get(str(row["symbol"]), set())
            ):
                continue
        source_ref = f"cninfo:{row['announcement_id']}"
        day = _iso(row["announcement_date"])
        events.append(VerifiedEvent(
            event_id=_id("VEVT", row["symbol"], event_type, day, source_ref),
            symbol=str(row["symbol"]),
            event_type=event_type,
            event_date=day,
            information_available_date=day,
            source_kind="official_title_exact",
            source_ref=source_ref,
            title=title,
        ))
    return events


def _load_p6a_events(database: Path, *, as_of: str) -> tuple[list[VerifiedEvent], int]:
    if not database.is_file():
        return [], 0
    with _connect_ro(database) as connection:
        rows = connection.execute(
            "select c.symbol,e.event_type,e.event_date,e.information_available_date,"
            "e.source_document_id,d.payload_json from restructuring_events e "
            "join restructuring_cases c on c.case_id=e.case_id "
            "join source_documents d on d.document_id=e.source_document_id "
            "where e.information_available_date<=? order by e.information_available_date,e.event_id",
            (as_of,),
        ).fetchall()
    unique: dict[tuple[str, str, str, str], VerifiedEvent] = {}
    for row in rows:
        payload = json.loads(str(row["payload_json"]))
        title = str(payload.get("title") or "")
        if (
            str(row["event_type"]) == "restructuring_plan_published"
            and classify_official_title(title) != "restructuring_plan_published"
        ):
            continue
        key = (
            str(row["symbol"]), str(row["event_type"]),
            str(row["information_available_date"]), str(row["source_document_id"]),
        )
        unique.setdefault(key, VerifiedEvent(
            event_id=_id("VEVT", *key),
            symbol=key[0],
            event_type=key[1],
            event_date=_iso(row["event_date"]),
            information_available_date=_iso(row["information_available_date"]),
            source_kind="p6a_verified_fact",
            source_ref=str(row["source_document_id"]),
            title=title,
        ))
    return list(unique.values()), len(rows)


def load_verified_events(
    *, base_database: Path, p6a_database: Path, as_of: str
) -> tuple[list[VerifiedEvent], int, int]:
    p6a, raw_count = _load_p6a_events(p6a_database, as_of=as_of)
    titles = _load_title_events(base_database, as_of=as_of)
    merged: dict[tuple[str, str, str], VerifiedEvent] = {}
    for event in titles:
        merged[(
            event.symbol, event.event_type,
            event.information_available_date,
        )] = event
    for event in p6a:
        merged[(
            event.symbol, event.event_type,
            event.information_available_date,
        )] = event
    return sorted(
        merged.values(),
        key=lambda item: (item.symbol, item.information_available_date, item.event_type),
    ), raw_count, len(p6a)


def _status_intervals(database: Path, *, as_of: str) -> dict[str, list[tuple[str, str]]]:
    with _connect_ro(database) as connection:
        rows = connection.execute(
            "select symbol,start_date,coalesce(end_date,'') end_date,status_type "
            "from st_status_history where start_date<=? order by symbol,start_date",
            (as_of,),
        ).fetchall()
    result: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row in rows:
        if str(row["status_type"]) == "delisted":
            continue
        result[str(row["symbol"])].append((
            _iso(row["start_date"]),
            min(_iso(row["end_date"]), as_of) if row["end_date"] else as_of,
        ))
    return result


def _trading_calendar(market_database: Path, *, as_of: str) -> list[str]:
    with _connect_ro(market_database) as connection:
        rows = connection.execute(
            "select trade_date from benchmark_daily where benchmark_id='csi_all_share' "
            "and trade_date<=? order by trade_date",
            (as_of,),
        ).fetchall()
    return [str(row["trade_date"]) for row in rows]


def _gap_days(calendar: list[str], left: str, right: str) -> int:
    return sum(left < day < right for day in calendar)


def _covering_interval(
    intervals: list[tuple[str, str]], start: str, end: str
) -> tuple[str, str] | None:
    return next((item for item in intervals if item[0] <= start and item[1] >= end), None)


def _boundary_status(
    intervals: list[tuple[str, str]], start: str, end: str, is_open: bool
) -> tuple[str, str]:
    start_status = (
        "exact_status_start"
        if any(item[0] == start for item in intervals)
        else "status_interval_covered"
        if any(item[0] <= start <= item[1] for item in intervals)
        else "membership_only"
    )
    if is_open:
        end_status = "open"
    elif any(item[1] == end for item in intervals):
        end_status = "exact_status_end"
    elif any(0 <= (date.fromisoformat(item[1]) - date.fromisoformat(end)).days <= 3 for item in intervals):
        end_status = "status_end_nearby"
    else:
        end_status = "membership_only"
    return start_status, end_status


def _stage_episode(
    *,
    symbol: str,
    start: str,
    end: str,
    events: list[VerifiedEvent],
) -> tuple[str, str, str, str, list[VerifiedEvent], list[VerifiedEvent], list[str]]:
    scoped = [
        event for event in events
        if event.symbol == symbol and start <= event.information_available_date <= end
    ]
    boundary = next((
        event.information_available_date for event in scoped
        if event.event_type == "restructuring_plan_published"
    ), "")
    inputs = [
        event for event in scoped
        if not boundary or event.information_available_date <= boundary
    ]
    outcomes = [
        event for event in scoped
        if boundary and event.information_available_date > boundary
    ]
    current = "st_distress_only"
    max_stage = current
    procedure = "none"
    rank = {stage: index for index, stage in enumerate(STAGES)}
    for event in inputs:
        if event.event_type == "restructuring_terminated":
            current = "st_distress_only"
            procedure = "terminated"
            continue
        stage = STAGE_EVENT.get(event.event_type)
        if stage:
            current = stage if rank[stage] >= rank[current] or procedure == "terminated" else current
            max_stage = max((max_stage, stage), key=rank.get)
            procedure = "plan_boundary_reached" if stage == "plan_key_terms_disclosed" else "active"
    conflicts = []
    if not boundary and any(
        event.event_type in {"restructuring_plan_approved", "restructuring_completed"}
        for event in scoped
    ):
        conflicts.append("outcome_without_verified_plan_boundary")
    return current, max_stage, procedure, boundary, inputs, outcomes, conflicts


def build_verified_episodes(
    *,
    dry_plan: Any,
    base_database: Path,
    market_context_database: Path,
    p6a_database: Path,
    as_of: str,
    gap_limit: int = 3,
) -> tuple[list[ValuationEpisode], int, int, int]:
    events, p6a_raw, p6a_deduped = load_verified_events(
        base_database=base_database, p6a_database=p6a_database, as_of=as_of
    )
    intervals = _status_intervals(base_database, as_of=as_of)
    calendar = _trading_calendar(market_context_database, as_of=as_of)
    by_symbol: dict[str, list[Any]] = defaultdict(list)
    for item in dry_plan.episodes:
        by_symbol[item.symbol].append(item)
    episodes: list[ValuationEpisode] = []
    for symbol, candidates in sorted(by_symbol.items()):
        groups: list[list[Any]] = []
        for candidate in sorted(candidates, key=lambda item: item.start_date):
            if not groups:
                groups.append([candidate])
                continue
            previous = groups[-1][-1]
            gap = _gap_days(calendar, previous.end_date, candidate.start_date)
            covered = _covering_interval(
                intervals.get(symbol, []),
                groups[-1][0].start_date,
                candidate.end_date,
            )
            if gap <= gap_limit and covered is not None:
                groups[-1].append(candidate)
            else:
                groups.append([candidate])
        for group in groups:
            start, end = group[0].start_date, group[-1].end_date
            is_open = group[-1].is_open
            merged_gap = sum(
                _gap_days(calendar, left.end_date, right.start_date)
                for left, right in zip(group, group[1:])
            )
            start_status, end_status = _boundary_status(
                intervals.get(symbol, []), start, end, is_open
            )
            current, maximum, procedure, boundary, inputs, outcomes, conflicts = _stage_episode(
                symbol=symbol, start=start, end=end, events=events
            )
            evidence_status = (
                "verified"
                if start_status != "membership_only" and end_status != "membership_only"
                else "provisional_boundary"
            )
            episode_id = _id("VEP", symbol, start, end)
            episodes.append(ValuationEpisode(
                episode_id=episode_id,
                symbol=symbol,
                start_date=start,
                end_date=end,
                is_open=is_open,
                component_candidate_ids=[item.episode_id for item in group],
                merged_membership_gap_trade_days=merged_gap,
                start_boundary_status=start_status,
                end_boundary_status=end_status,
                current_stage=current,
                max_stage_reached=maximum,
                procedure_status=procedure,
                p6c_boundary_date=boundary,
                input_stop_date=boundary,
                input_events=inputs,
                outcome_events=outcomes,
                boundary_conflicts=conflicts,
                m6_candidate_count=sum(item.m6_restructuring_candidate_count for item in group),
                evidence_status=evidence_status,
            ))
    return episodes, len(events), p6a_raw, p6a_deduped


def _review_clusters(
    episodes: list[ValuationEpisode], *, p6a_raw: int, p6a_deduped: int
) -> list[ReviewCluster]:
    definitions = [
        (
            "short_membership_gap",
            [item for item in episodes if len(item.component_candidate_ids) > 1],
            "≤3 个交易日空洞且 status_history 连续时合并。",
            "auto_merge",
        ),
        (
            "duplicate_assignment_event",
            episodes[:1] if p6a_raw > p6a_deduped else [],
            "联合管理人产生的同文档同节点只保留一个事件。",
            "auto_dedupe",
        ),
        (
            "termination_within_st_episode",
            [item for item in episodes if any(e.event_type == "restructuring_terminated" for e in item.input_events)],
            "程序终止只重置阶段，不拆 ST episode。",
            "keep_same_episode",
        ),
        (
            "plan_boundary",
            [item for item in episodes if item.p6c_boundary_date],
            "方案关键条款披露日停止 P6B 输入，之后只记结果。",
            "stop_input",
        ),
        (
            "provisional_boundary",
            [item for item in episodes if item.evidence_status == "provisional_boundary"],
            "边界缺 status_history 支持时保持 provisional，不进入阶段统计。",
            "need_more_evidence",
        ),
    ]
    clusters = []
    for family, affected, recommendation, resolution in definitions:
        if not affected:
            continue
        clusters.append(ReviewCluster(
            cluster_id=_id("VCL", family),
            family=family,
            recommendation=recommendation,
            affected_episode_count=len(affected),
            representative_episode_ids=[item.episode_id for item in affected[:5]],
            resolution=resolution,
            human_required=False,
        ))
    return clusters


class EpisodeRepository:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.executescript("""
            create table if not exists valuation_episodes (
                episode_id text primary key, symbol text not null, start_date text not null,
                end_date text not null, evidence_status text not null, payload_json text not null
            );
            create table if not exists valuation_episode_events (
                event_id text primary key, symbol text not null,
                information_available_date text not null, payload_json text not null
            );
            create table if not exists valuation_episode_runs (
                run_id text primary key, as_of text not null, payload_json text not null
            );
            create table if not exists valuation_episode_versions (
                episode_id text not null, content_digest text not null,
                symbol text not null, start_date text not null, end_date text not null,
                evidence_status text not null, payload_json text not null,
                primary key (episode_id,content_digest)
            );
            create table if not exists valuation_episode_run_members (
                run_id text not null, episode_id text not null, content_digest text not null,
                primary key (run_id,episode_id)
            );
            create table if not exists valuation_episode_run_events (
                run_id text not null, event_id text not null,
                primary key (run_id,event_id)
            );
        """)
        return connection

    def persist(self, episodes: list[ValuationEpisode], result: EpisodeRunResult) -> None:
        with self._connect() as connection:
            for episode in episodes:
                payload = _canonical(episode.model_dump(mode="json"))
                content_digest = _digest(episode.model_dump(mode="json"))
                connection.execute(
                    "insert or ignore into valuation_episodes values (?,?,?,?,?,?)",
                    (episode.episode_id, episode.symbol, episode.start_date, episode.end_date,
                     episode.evidence_status, payload),
                )
                connection.execute(
                    "insert or ignore into valuation_episode_versions values (?,?,?,?,?,?,?)",
                    (
                        episode.episode_id, content_digest, episode.symbol,
                        episode.start_date, episode.end_date, episode.evidence_status, payload,
                    ),
                )
                connection.execute(
                    "insert or ignore into valuation_episode_run_members values (?,?,?)",
                    (result.run_id, episode.episode_id, content_digest),
                )
                for event in episode.input_events + episode.outcome_events:
                    connection.execute(
                        "insert or ignore into valuation_episode_events values (?,?,?,?)",
                        (event.event_id, event.symbol, event.information_available_date,
                         _canonical(event.model_dump(mode="json"))),
                    )
                    connection.execute(
                        "insert or ignore into valuation_episode_run_events values (?,?)",
                        (result.run_id, event.event_id),
                    )
            payload = _canonical(result.model_dump(mode="json"))
            existing = connection.execute(
                "select payload_json from valuation_episode_runs where run_id=?", (result.run_id,)
            ).fetchone()
            if existing:
                old, new = json.loads(str(existing[0])), json.loads(payload)
                old.pop("generated_at", None)
                new.pop("generated_at", None)
                if old != new:
                    raise ValueError(f"run_id 冲突: {result.run_id}")
                return
            connection.execute(
                "insert into valuation_episode_runs values (?,?,?)",
                (result.run_id, result.as_of, payload),
            )


def run_materialization(
    *,
    manifest: EpisodePilotManifest,
    base_database: Path,
    market_context_database: Path,
    market_factor_database: Path,
    episode_index: Path,
    episode_manifest: Path,
    p6a_database: Path,
    repository: EpisodeRepository,
) -> EpisodeRunResult:
    dry_plan = build_p6b_dry_plan(
        base_database=base_database,
        market_context_database=market_context_database,
        market_factor_database=market_factor_database,
        episode_index=episode_index,
        episode_manifest=episode_manifest,
        as_of=manifest.as_of,
    )
    episodes, event_count, p6a_raw, p6a_deduped = build_verified_episodes(
        dry_plan=dry_plan,
        base_database=base_database,
        market_context_database=market_context_database,
        p6a_database=p6a_database,
        as_of=manifest.as_of,
        gap_limit=manifest.short_membership_gap_max_trade_days,
    )
    clusters = _review_clusters(episodes, p6a_raw=p6a_raw, p6a_deduped=p6a_deduped)
    pilot_symbols = {item.symbol for item in manifest.symbols}
    identity = {
        "materializer_version": MATERIALIZER_VERSION,
        "manifest": manifest.model_dump(mode="json"),
        "episodes": [item.model_dump(mode="json") for item in episodes],
    }
    result = EpisodeRunResult(
        run_id=f"P6B3R-{_digest(identity)[:20].upper()}",
        pilot_id=manifest.pilot_id,
        as_of=manifest.as_of,
        generated_at=datetime.now(timezone.utc).isoformat(),
        source_manifest_digest=_digest(manifest.model_dump(mode="json")),
        candidate_episode_count=len(dry_plan.episodes),
        verified_episode_count=sum(item.evidence_status == "verified" for item in episodes),
        provisional_episode_count=sum(item.evidence_status != "verified" for item in episodes),
        merged_gap_count=sum(len(item.component_candidate_ids) - 1 for item in episodes),
        verified_event_count=event_count,
        p6a_raw_event_count=p6a_raw,
        p6a_deduped_event_count=p6a_deduped,
        stage_counts=dict(sorted(Counter(
            item.current_stage
            for item in episodes if item.evidence_status == "verified"
        ).items())),
        review_clusters=clusters,
        human_required_cluster_count=sum(item.human_required for item in clusters),
        pilot_episodes=[item for item in episodes if item.symbol in pilot_symbols],
        conclusions=[
            "valuation episode 由连续 ST 状态定义；程序终止、重招募和完成不另拆 episode。",
            "M6 case_note 只保留候选计数；阶段只来自官方精确标题或 P6A 核证事实。",
            "方案关键条款披露日是 P6B 输入停止点，之后事件只作结果标签。",
            "边界缺权威状态支持的 episode 保持 provisional，不进入阶段统计。",
        ],
    )
    repository.persist(episodes, result)
    return result


def render_markdown(result: EpisodeRunResult) -> str:
    lines = [
        "# P6B-3 valuation episode 核证结果", "",
        f"- run：`{result.run_id}`", f"- 截止：{result.as_of}",
        f"- 候选：{result.candidate_episode_count}",
        f"- 核证：{result.verified_episode_count}",
        f"- provisional：{result.provisional_episode_count}",
        f"- 自动合并 membership 假断点：{result.merged_gap_count}",
        f"- 核证事件：{result.verified_event_count}",
        f"- 人类必审 cluster：{result.human_required_cluster_count}", "",
        "## Pilot", "",
        "| 股票 | 区间 | 当前阶段 | 最高阶段 | 程序状态 | P6C 边界 | 边界质量 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in result.pilot_episodes:
        lines.append(
            f"| {item.symbol} | {item.start_date}..{item.end_date} | "
            f"`{item.current_stage}` | `{item.max_stage_reached}` | "
            f"`{item.procedure_status}` | {item.p6c_boundary_date or '—'} | "
            f"`{item.evidence_status}` |"
        )
    lines.extend(["", "## 冻结结论", "", *[f"- {item}" for item in result.conclusions]])
    return "\n".join(lines) + "\n"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "manifest", "base_database", "market_context_database", "market_factor_database",
        "episode_index", "episode_manifest", "p6a_database", "database",
        "output_json", "output_markdown",
    ):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = EpisodePilotManifest.model_validate_json(
        args.manifest.read_text(encoding="utf-8")
    )
    result = run_materialization(
        manifest=manifest,
        base_database=args.base_database,
        market_context_database=args.market_context_database,
        market_factor_database=args.market_factor_database,
        episode_index=args.episode_index,
        episode_manifest=args.episode_manifest,
        p6a_database=args.p6a_database,
        repository=EpisodeRepository(args.database),
    )
    _write(args.output_json, json.dumps(
        result.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2
    ) + "\n")
    _write(args.output_markdown, render_markdown(result))
    print(_canonical({
        "run_id": result.run_id,
        "verified": result.verified_episode_count,
        "provisional": result.provisional_episode_count,
        "human_required": result.human_required_cluster_count,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
