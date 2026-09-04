"""Versioned multi-track P8 precursor graph and deterministic candidate extraction."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from p8_research import (
    P8DerivedEvent,
    P8ResearchRepository,
    SourceSpan,
    build_run,
    canonical_json,
    content_id,
)
from settings import DATA_ROOT, P7_INTELLIGENCE_DB, P8_RESEARCH_DB, VALUATION_EPISODE_DB


CONTRACT_VERSION = "p8_precursor_graph_v1"
REGISTRY_VERSION = "p8_precursor_registry_v1"
DEFAULT_BASE_DB = DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"


@dataclass(frozen=True)
class NodeSpec:
    node: str
    track: str
    process_direction: str
    old_equity_effect: str
    terms: tuple[str, ...]
    possible_successors: tuple[str, ...]
    failure_successors: tuple[str, ...] = ()
    prerequisites: tuple[str, ...] = ()
    hard_outcome: bool = False


NODE_SPECS: tuple[NodeSpec, ...] = (
    NodeSpec(
        "restructuring_application_disclosed", "judicial", "advance", "unknown",
        ("申请公司重整", "申请重整及预重整", "被债权人申请重整", "申请预重整"),
        ("pre_restructuring_started", "formal_restructuring_accepted"),
        ("restructuring_rejected", "restructuring_terminated"),
    ),
    NodeSpec(
        "pre_restructuring_started", "judicial", "advance", "unknown",
        ("启动预重整", "决定对公司进行预重整", "同意公司预重整", "进入预重整程序"),
        ("investor_recruitment", "formal_restructuring_accepted"),
        ("restructuring_terminated",),
        ("restructuring_application_disclosed",),
    ),
    NodeSpec(
        "formal_restructuring_accepted", "judicial", "advance", "unknown",
        ("裁定受理公司重整", "法院受理公司重整", "裁定受理重整"),
        ("creditor_claims", "creditor_meeting", "plan_key_terms_disclosed"),
        ("restructuring_terminated",),
        ("restructuring_application_disclosed",), True,
    ),
    NodeSpec(
        "restructuring_rejected", "judicial", "rollback", "adverse",
        ("不予受理重整", "驳回重整申请", "不受理重整申请"),
        (), (), ("restructuring_application_disclosed",), True,
    ),
    NodeSpec(
        "restructuring_terminated", "judicial", "rollback", "adverse",
        ("终止预重整", "终止重整程序", "终结预重整", "终结重整程序"),
        (), (), (), True,
    ),
    NodeSpec(
        "investor_recruitment", "investor", "advance", "unknown",
        ("公开招募重整投资人", "招募重整投资人", "投资人招募"),
        ("investor_selected", "investor_agreement_signed"),
        ("investor_recruitment_failed",),
        ("restructuring_application_disclosed",),
    ),
    NodeSpec(
        "investor_selected", "investor", "advance", "unknown",
        ("确定重整投资人", "选定重整投资人", "遴选重整投资人"),
        ("investor_agreement_signed",),
        ("investor_recruitment_failed",),
        ("investor_recruitment",),
    ),
    NodeSpec(
        "investor_agreement_signed", "investor", "advance", "mixed",
        ("签署重整投资协议", "重整投资协议签署", "签订重整投资协议"),
        ("plan_key_terms_disclosed",),
        ("investor_agreement_terminated",),
        ("investor_recruitment",), True,
    ),
    NodeSpec(
        "investor_agreement_terminated", "investor", "rollback", "adverse",
        ("解除重整投资协议", "终止重整投资协议"),
        ("investor_recruitment",), (), ("investor_agreement_signed",), True,
    ),
    NodeSpec(
        "creditor_claims", "plan", "advance", "unknown",
        ("债权申报", "申报债权"),
        ("creditor_meeting", "plan_key_terms_disclosed"),
        (), ("formal_restructuring_accepted",),
    ),
    NodeSpec(
        "creditor_meeting", "plan", "advance", "unknown",
        ("债权人会议", "债权人会议召开"),
        ("plan_key_terms_disclosed", "plan_approved"),
        ("plan_rejected",), ("formal_restructuring_accepted",),
    ),
    NodeSpec(
        "plan_key_terms_disclosed", "plan", "advance", "mixed",
        ("重整计划草案", "出资人权益调整方案", "重整计划主要内容", "重整计划关键条款"),
        ("plan_approved",),
        ("plan_rejected", "restructuring_terminated"),
        ("formal_restructuring_accepted",),
    ),
    NodeSpec(
        "plan_approved", "plan", "advance", "mixed",
        ("裁定批准重整计划", "法院批准重整计划", "批准公司重整计划"),
        ("plan_executed",),
        ("restructuring_terminated",),
        ("plan_key_terms_disclosed",), True,
    ),
    NodeSpec(
        "plan_rejected", "plan", "rollback", "adverse",
        ("不批准重整计划", "驳回重整计划"),
        (), (), ("plan_key_terms_disclosed",), True,
    ),
    NodeSpec(
        "plan_executed", "execution", "advance", "mixed",
        ("重整计划执行完毕", "重整计划执行完毕报告", "裁定终结重整程序"),
        ("risk_warning_removed",), (), ("plan_approved",), True,
    ),
    NodeSpec(
        "risk_warning_removed", "risk_warning", "advance", "supportive",
        ("撤销退市风险警示", "撤销其他风险警示", "撤销风险警示"),
        (), (), (), True,
    ),
    NodeSpec(
        "delisting_decision", "risk_warning", "rollback", "adverse",
        ("终止上市决定", "决定终止公司股票上市"),
        (), (), (), True,
    ),
)

SPEC_BY_NODE = {item.node: item for item in NODE_SPECS}
P6_EVENT_TO_NODE = {
    "restructuring_application_disclosed": "restructuring_application_disclosed",
    "pre_restructuring_started": "pre_restructuring_started",
    "investor_recruitment_started": "investor_recruitment",
    "investor_agreement_signed": "investor_agreement_signed",
    "court_restructuring_accepted": "formal_restructuring_accepted",
    "restructuring_plan_disclosed": "plan_key_terms_disclosed",
    "restructuring_plan_approved": "plan_approved",
    "restructuring_plan_executed": "plan_executed",
    "risk_warning_removed": "risk_warning_removed",
    "restructuring_terminated": "restructuring_terminated",
    "delisting_decision": "delisting_decision",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CompanyFrontier(StrictModel):
    symbol: str = Field(pattern=r"^\d{6}$")
    current_nodes_by_track: dict[str, str]
    frontier_nodes: list[str]
    next_possible_successors: list[str]
    unmet_prerequisites: list[str]
    failure_branch_risk_flags: list[str]
    evidence_status: str


class EventGraphResult(StrictModel):
    contract_version: str = CONTRACT_VERSION
    registry_version: str = REGISTRY_VERSION
    start_date: str
    through: str
    source_run_ids: list[str]
    event_count: int
    evidence_status_counts: dict[str, int]
    node_counts: dict[str, int]
    company_count: int
    body_shortlist_count: int
    body_missing_count: int
    llm_completed_count: int
    frontiers: list[CompanyFrontier]
    events: list[P8DerivedEvent]


def _connect_ro(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _normalize(text: str) -> str:
    return re.sub(r"[\s（）()《》：:]", "", text or "")


def _find_span(text: str, term: str, source_ref: str) -> SourceSpan:
    position = text.find(term)
    if position < 0:
        position = _normalize(text).find(_normalize(term))
    if position < 0:
        position = 0
    start = max(0, position - 100)
    end = min(len(text), position + len(term) + 180)
    excerpt = re.sub(r"\s+", " ", text[start:end]).strip() or term
    return SourceSpan(
        source_ref=source_ref,
        excerpt=excerpt[:500],
        start_offset=start,
        end_offset=end,
    )


def _matched_specs(text: str) -> list[tuple[NodeSpec, str]]:
    normalized = _normalize(text)
    matches: list[tuple[NodeSpec, str]] = []
    for spec in NODE_SPECS:
        term = next((term for term in spec.terms if _normalize(term) in normalized), "")
        if term:
            if spec.node == "risk_warning_removed" and any(
                word in text for word in ("申请撤销", "可能撤销", "尚需", "能否撤销")
            ):
                continue
            matches.append((spec, term))
    return matches


def _event(
    *, symbol: str, available_as_of: str, spec: NodeSpec,
    source_ids: list[str], span: SourceSpan,
    evidence_status: str, source_digest: str,
    llm_status: str = "not_required", llm_model: str = "", llm_prompt_version: str = "",
) -> P8DerivedEvent:
    identity = {
        "registry": REGISTRY_VERSION,
        "symbol": symbol,
        "available_as_of": available_as_of,
        "node": spec.node,
        "source_ids": sorted(source_ids),
        "source_digest": source_digest,
        "evidence_status": evidence_status,
    }
    return P8DerivedEvent(
        event_id=content_id("P8EV", identity),
        symbol=symbol,
        available_as_of=available_as_of,
        event_type=spec.node,
        track=spec.track,  # type: ignore[arg-type]
        node=spec.node,
        process_direction=spec.process_direction,  # type: ignore[arg-type]
        old_equity_effect=spec.old_equity_effect,  # type: ignore[arg-type]
        not_hard_outcome=not spec.hard_outcome,
        precursor_candidates_for=list(spec.possible_successors) if not spec.hard_outcome else [],
        possible_successors=list(spec.possible_successors),
        failure_successors=list(spec.failure_successors),
        prerequisite_nodes=list(spec.prerequisites),
        evidence_status=evidence_status,  # type: ignore[arg-type]
        source_ids=sorted(source_ids),
        source_spans=[span],
        extractor_version=REGISTRY_VERSION,
        llm_status=llm_status,  # type: ignore[arg-type]
        llm_model=llm_model,
        llm_prompt_version=llm_prompt_version,
        source_content_digest=source_digest,
    )


def _load_p6_events(path: Path, *, through: str) -> list[dict[str, Any]]:
    with _connect_ro(path) as connection:
        return [
            json.loads(str(row[0])) for row in connection.execute(
                "select payload_json from valuation_episode_events where information_available_date<=? order by information_available_date,event_id",
                (through,),
            )
        ]


def _latest_p7_facts(path: Path, *, start_date: str, through: str) -> tuple[str, list[dict[str, Any]]]:
    with _connect_ro(path) as connection:
        row = connection.execute(
            "select run_id from announcement_runs where start_date<=? and through>=? order by created_at desc limit 1",
            (start_date, through),
        ).fetchone()
        if row is None:
            row = connection.execute(
                "select run_id from announcement_runs order by created_at desc limit 1"
            ).fetchone()
        if row is None:
            raise ValueError("P7 announcement run unavailable")
        run_id = str(row[0])
        facts = [
            json.loads(str(item[0])) for item in connection.execute(
                "select payload_json from announcement_facts where run_id=? and available_as_of between ? and ? order by available_as_of,announcement_id",
                (run_id, start_date, through),
            )
        ]
    return run_id, facts


def _load_bodies(path: Path, ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    result: dict[str, str] = {}
    with _connect_ro(path) as connection:
        for row in connection.execute(
            "select announcement_id,body_text from company_announcements where body_text is not null and length(trim(body_text))>0"
        ):
            key = str(row[0])
            if key in ids:
                result[key] = str(row[1])
    return result


def _frontiers(events: list[P8DerivedEvent]) -> list[CompanyFrontier]:
    by_symbol: dict[str, list[P8DerivedEvent]] = defaultdict(list)
    for event in events:
        by_symbol[event.symbol].append(event)
    results: list[CompanyFrontier] = []
    for symbol, rows in sorted(by_symbol.items()):
        current: dict[str, P8DerivedEvent] = {}
        for event in sorted(rows, key=lambda item: (item.available_as_of, item.event_id)):
            current[event.track] = event
        nodes = {event.node for event in rows}
        successors = sorted({successor for event in current.values() for successor in event.possible_successors})
        unmet = sorted({
            prerequisite for successor in successors
            for prerequisite in SPEC_BY_NODE.get(successor, NodeSpec("", "", "", "", (), ())).prerequisites
            if prerequisite not in nodes
        })
        failure_flags = sorted({successor for event in current.values() for successor in event.failure_successors})
        evidence = sorted({event.evidence_status for event in current.values()})
        results.append(CompanyFrontier(
            symbol=symbol,
            current_nodes_by_track={track: event.node for track, event in sorted(current.items())},
            frontier_nodes=sorted(event.node for event in current.values()),
            next_possible_successors=successors,
            unmet_prerequisites=unmet,
            failure_branch_risk_flags=failure_flags,
            evidence_status="+".join(evidence),
        ))
    return results


def build_event_graph(
    *, base_database: Path, p7_intelligence_database: Path,
    valuation_episode_database: Path, start_date: str, through: str,
) -> EventGraphResult:
    p7_run_id, facts = _latest_p7_facts(
        p7_intelligence_database, start_date=start_date, through=through,
    )
    p6_events = _load_p6_events(valuation_episode_database, through=through)
    events: list[P8DerivedEvent] = []
    authoritative_keys: set[tuple[str, str, str]] = set()
    source_p6_run = ""
    with _connect_ro(valuation_episode_database) as connection:
        row = connection.execute(
            "select run_id from valuation_episode_runs order by rowid desc limit 1"
        ).fetchone()
        source_p6_run = str(row[0]) if row else ""
    for raw in p6_events:
        node = P6_EVENT_TO_NODE.get(str(raw.get("event_type") or ""))
        spec = SPEC_BY_NODE.get(node or "")
        if spec is None:
            continue
        available = str(raw.get("information_available_date") or raw.get("event_date") or "")[:10]
        if available < start_date or available > through:
            continue
        symbol = str(raw.get("symbol") or "")
        title = str(raw.get("title") or spec.node)
        source_ref = str(raw.get("source_ref") or raw.get("event_id") or "p6_event")
        source_digest = hashlib.sha256(title.encode("utf-8")).hexdigest()
        events.append(_event(
            symbol=symbol, available_as_of=available, spec=spec,
            source_ids=[str(raw.get("event_id") or source_ref)],
            span=_find_span(title, next((term for term in spec.terms if term in title), spec.terms[0]), source_ref),
            evidence_status="deterministic_verified",
            source_digest=source_digest,
        ))
        authoritative_keys.add((symbol, available, spec.node))

    shortlist = [
        item for item in facts
        if str(item.get("llm_route") or "") in {
            "shortlist_body_available", "shortlist_body_missing", "deterministic_hard_fact",
        }
        and str(item.get("category") or "") in {
            "restructuring_and_pre_restructuring", "risk_warning_and_delisting",
        }
    ]
    ids = {str(item.get("announcement_id") or "") for item in shortlist}
    bodies = _load_bodies(base_database, ids)
    body_missing_count = 0
    for fact in shortlist:
        announcement_id = str(fact.get("announcement_id") or "")
        symbol = str(fact.get("symbol") or "")
        available = str(fact.get("available_as_of") or fact.get("announcement_date") or "")[:10]
        title = str(fact.get("title") or "")
        body = bodies.get(announcement_id, "")
        body_matches = _matched_specs(body) if body else []
        title_matches = _matched_specs(title)
        if not body and str(fact.get("llm_route") or "") == "shortlist_body_missing":
            body_missing_count += 1
        matches = body_matches or title_matches
        for spec, term in matches:
            key = (symbol, available, spec.node)
            if key in authoritative_keys:
                continue
            source_text = body if body_matches else title
            source_ref = f"official_announcement:{announcement_id}"
            source_digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
            status = "provisional" if body_matches else "title_derived"
            events.append(_event(
                symbol=symbol, available_as_of=available, spec=spec,
                source_ids=[announcement_id],
                span=_find_span(source_text, term, source_ref),
                evidence_status=status,
                source_digest=source_digest,
                llm_status="not_run" if body_matches else "not_required",
            ))

    unique: dict[tuple[str, str, str, str], P8DerivedEvent] = {}
    priority = {"deterministic_verified": 4, "body_verified": 3, "provisional": 2, "title_derived": 1}
    for event in events:
        key = (event.symbol, event.available_as_of, event.node, event.source_content_digest)
        existing = unique.get(key)
        if existing is None or priority.get(event.evidence_status, 0) > priority.get(existing.evidence_status, 0):
            unique[key] = event
    ordered = sorted(unique.values(), key=lambda item: (item.available_as_of, item.symbol, item.node, item.event_id))
    return EventGraphResult(
        start_date=start_date,
        through=through,
        source_run_ids=[item for item in (source_p6_run, p7_run_id) if item],
        event_count=len(ordered),
        evidence_status_counts=dict(sorted(Counter(item.evidence_status for item in ordered).items())),
        node_counts=dict(sorted(Counter(item.node for item in ordered).items())),
        company_count=len({item.symbol for item in ordered}),
        body_shortlist_count=sum(bool(bodies.get(str(item.get("announcement_id") or ""))) for item in shortlist),
        body_missing_count=body_missing_count,
        llm_completed_count=sum(item.llm_status == "completed" for item in ordered),
        frontiers=_frontiers(ordered),
        events=ordered,
    )


def persist_event_graph(result: EventGraphResult, repository: P8ResearchRepository):
    payloads = [item.model_dump(mode="json") for item in result.events]
    records = {"derived_event": payloads}
    run = build_run(
        run_kind="event_graph", contract_version=CONTRACT_VERSION,
        start_date=result.start_date, through=result.through,
        source_run_ids=result.source_run_ids,
        source_digests={"event_graph_result": hashlib.sha256(canonical_json(result.model_dump(mode="json", exclude={"events"})).encode("utf-8")).hexdigest()},
        record_payloads=records,
    )
    repository.persist(run=run, records=records)
    return run


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--through", required=True)
    parser.add_argument("--base-database", type=Path, default=DEFAULT_BASE_DB)
    parser.add_argument("--p7-intelligence-database", type=Path, default=P7_INTELLIGENCE_DB)
    parser.add_argument("--valuation-episode-database", type=Path, default=VALUATION_EPISODE_DB)
    parser.add_argument("--repository", type=Path, default=P8_RESEARCH_DB)
    parser.add_argument("--output-json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = build_event_graph(
        base_database=args.base_database,
        p7_intelligence_database=args.p7_intelligence_database,
        valuation_episode_database=args.valuation_episode_database,
        start_date=args.start_date,
        through=args.through,
    )
    run = persist_event_graph(result, P8ResearchRepository(args.repository))
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "run_id": run.run_id,
        "event_count": result.event_count,
        "body_missing_count": result.body_missing_count,
        "llm_completed_count": result.llm_completed_count,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
