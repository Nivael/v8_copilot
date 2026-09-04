"""Run real structured LLM extraction on every body-available P8 shortlist item.

The LLM is deliberately not an oracle.  It may propose frozen event nodes and
quote source text.  This module validates the quote against the point-in-time
announcement body and reconciles the proposal with deterministic extraction.
Only agreement between both extractors can become ``body_verified``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from llm.config import resolve_model
from llm.providers import LLMProviderError, OpenAIResponsesProvider, StructuredLLMProvider
from p8_event_graph import (
    CONTRACT_VERSION,
    NODE_SPECS,
    REGISTRY_VERSION,
    EventGraphResult,
    _event,
    _find_span,
    _frontiers,
    _latest_p7_facts,
    _load_bodies,
    _matched_specs,
    build_event_graph,
)
from p8_research import P8DerivedEvent, P8ResearchRepository, build_run, canonical_json, content_id
from settings import DATA_ROOT, P7_INTELLIGENCE_DB, P8_RESEARCH_DB, VALUATION_EPISODE_DB


PROMPT_VERSION = "p8_body_extraction_v1"
EXTRACTION_CONTRACT_VERSION = "p8_body_extraction_contract_v1"
DEFAULT_BASE_DB = DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"
DEFAULT_CACHE_DIR = DATA_ROOT / "local_data/v8_copilot/p8_llm_extraction_cache"
MAX_CHUNK_CHARS = 48_000
CHUNK_OVERLAP_CHARS = 1_000

EventNode = Literal[
    "restructuring_application_disclosed",
    "pre_restructuring_started",
    "formal_restructuring_accepted",
    "restructuring_rejected",
    "restructuring_terminated",
    "investor_recruitment",
    "investor_selected",
    "investor_agreement_signed",
    "investor_agreement_terminated",
    "creditor_claims",
    "creditor_meeting",
    "plan_key_terms_disclosed",
    "plan_approved",
    "plan_rejected",
    "plan_executed",
    "risk_warning_removed",
    "delisting_decision",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProposedNode(StrictModel):
    node: EventNode
    evidence_quote: str = Field(min_length=2, max_length=300)
    confidence: Literal["high", "medium", "low"]
    issuer_scope: Literal["listed_company", "controlled_subsidiary", "shareholder", "other"]


class ExtractedKeyFact(StrictModel):
    fact_type: Literal[
        "strategic_entry_price", "share_conversion_ratio", "share_transfer_ratio",
        "investor", "court", "audit_opinion", "other",
    ]
    value: str = Field(min_length=1, max_length=300)
    unit: str = Field(default="", max_length=40)
    evidence_quote: str = Field(min_length=2, max_length=300)


class BodyChunkExtraction(StrictModel):
    document_relevant: bool
    nodes: list[ProposedNode] = Field(default_factory=list, max_length=10)
    key_facts: list[ExtractedKeyFact] = Field(default_factory=list, max_length=16)
    no_event_reason: str = Field(default="", max_length=240)

    @model_validator(mode="after")
    def relevance_is_consistent(self) -> "BodyChunkExtraction":
        if not self.document_relevant and (self.nodes or self.key_facts):
            raise ValueError("document_relevant=false 时不得输出节点或关键事实")
        return self


class ValidatedNode(StrictModel):
    node: EventNode
    confidence: Literal["high", "medium", "low"]
    issuer_scope: Literal["listed_company", "controlled_subsidiary", "shareholder", "other"]
    evidence_quote: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    quote_valid: bool = True


class ValidatedKeyFact(StrictModel):
    fact_type: str
    value: str
    unit: str
    evidence_quote: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)


class AnnouncementExtractionRecord(StrictModel):
    record_id: str = Field(pattern=r"^P8LX-[A-F0-9]{20}$")
    announcement_id: str
    symbol: str = Field(pattern=r"^\d{6}$")
    available_as_of: str
    title: str
    source_content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    prompt_version: str = PROMPT_VERSION
    requested_model: str
    response_models: list[str]
    chunk_count: int = Field(ge=1)
    completed_chunk_count: int = Field(ge=0)
    cache_hit_count: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    deterministic_nodes: list[str]
    llm_nodes: list[ValidatedNode]
    key_facts: list[ValidatedKeyFact]
    invalid_proposal_count: int = Field(ge=0)
    reconciliation: Literal["agreement", "partial_agreement", "no_event", "conflict", "failed"]
    evidence_status: Literal["body_verified", "provisional", "conflicted", "failed"]
    conflict_reasons: list[str]
    errors: list[str]


class ExtractionBatchResult(StrictModel):
    contract_version: str = EXTRACTION_CONTRACT_VERSION
    prompt_version: str = PROMPT_VERSION
    model: str
    start_date: str
    through: str
    p7_run_id: str
    body_shortlist_count: int
    attempted_count: int
    completed_count: int
    failed_count: int
    cache_hit_count: int
    input_tokens: int
    output_tokens: int
    reconciliation_counts: dict[str, int]
    validated_node_count: int
    key_fact_count: int
    conflict_cluster_counts: dict[str, int]
    records: list[AnnouncementExtractionRecord]


SYSTEM_PROMPT = """你是上市公司公告的结构化事实抽取器，不是投资顾问。
只读取用户提供的这一份公告正文片段，禁止使用外部知识、标题推断或事后结果。
任务：找出正文明确陈述、且属于允许词表的程序节点；同时抽取受让价、转增/让渡比例、
投资人、法院、审计意见等关键事实。每项必须给出正文中逐字可定位的短引用。
不要把申请、拟议、可能、风险提示误写成已经完成；不要把股东、债权人或无关子公司的
事项当成上市公司自身事项。程序推进方向与老股东权益影响是不同维度，本任务不作投资判断。
若片段没有相关事实，document_relevant=false，并用 no_event_reason 简述原因。
允许节点及含义：
restructuring_application_disclosed=披露重整/预重整申请；
pre_restructuring_started=法院或有权机关明确启动预重整；
formal_restructuring_accepted=法院裁定正式受理重整；
restructuring_rejected=法院不予受理或驳回；
restructuring_terminated=预重整/重整程序明确终止或终结；
investor_recruitment=公开招募重整投资人；investor_selected=已确定/选定投资人；
investor_agreement_signed=重整投资协议已经签署；
investor_agreement_terminated=重整投资协议已经解除或终止；
creditor_claims=债权申报安排；creditor_meeting=债权人会议安排或召开；
plan_key_terms_disclosed=重整计划草案或出资人权益调整关键条款已披露；
plan_approved=法院裁定批准重整计划；plan_rejected=法院不批准/驳回计划；
plan_executed=重整计划已经执行完毕；
risk_warning_removed=交易所/公司明确撤销风险警示，不含仅申请撤销；
delisting_decision=交易所作出终止上市决定。
"""


_thread_local = threading.local()


def _provider() -> OpenAIResponsesProvider:
    provider = getattr(_thread_local, "provider", None)
    if provider is None:
        provider = OpenAIResponsesProvider(timeout_seconds=90.0)
        _thread_local.provider = provider
    return provider


def _body_chunks(body: str) -> list[tuple[int, str]]:
    if len(body) <= MAX_CHUNK_CHARS:
        return [(0, body)]
    chunks: list[tuple[int, str]] = []
    start = 0
    while start < len(body):
        hard_end = min(len(body), start + MAX_CHUNK_CHARS)
        end = hard_end
        if hard_end < len(body):
            split = max(body.rfind("\n", start + MAX_CHUNK_CHARS // 2, hard_end), body.rfind("。", start + MAX_CHUNK_CHARS // 2, hard_end))
            if split > start:
                end = split + 1
        chunks.append((start, body[start:end]))
        if end >= len(body):
            break
        start = max(start + 1, end - CHUNK_OVERLAP_CHARS)
    return chunks


def _normalized_positions(text: str) -> tuple[str, list[int]]:
    normalized: list[str] = []
    positions: list[int] = []
    for index, char in enumerate(text):
        if char.isspace():
            continue
        normalized.append(char)
        positions.append(index)
    return "".join(normalized), positions


def locate_quote(body: str, quote: str) -> tuple[int, int] | None:
    start = body.find(quote)
    if start >= 0:
        return start, start + len(quote)
    normalized_body, positions = _normalized_positions(body)
    normalized_quote, _ = _normalized_positions(quote)
    if not normalized_quote:
        return None
    normalized_start = normalized_body.find(normalized_quote)
    if normalized_start < 0:
        return None
    normalized_end = normalized_start + len(normalized_quote) - 1
    return positions[normalized_start], positions[normalized_end] + 1


def _cache_path(cache_dir: Path, *, digest: str, model: str, chunk_index: int) -> Path:
    model_key = re.sub(r"[^A-Za-z0-9_.-]+", "_", model)
    return cache_dir / PROMPT_VERSION / model_key / digest[:2] / f"{digest}.{chunk_index}.json"


def _call_chunk(
    *, announcement_id: str, symbol: str, title: str, body_digest: str,
    chunk_index: int, chunk_start: int, chunk: str, model: str,
    cache_dir: Path, provider_factory: Any = _provider,
) -> tuple[BodyChunkExtraction | None, dict[str, Any]]:
    path = _cache_path(cache_dir, digest=body_digest, model=model, chunk_index=chunk_index)
    if path.is_file():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            parsed = BodyChunkExtraction.model_validate(cached["response"])
            return parsed, {**cached.get("metadata", {}), "cache_hit": True, "error": ""}
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            pass
    payload = {
        "announcement_id": announcement_id,
        "symbol": symbol,
        "title_for_identity_only": title,
        "chunk_index": chunk_index,
        "chunk_start_offset": chunk_start,
        "body_text": chunk,
    }
    error = ""
    for attempt in range(3):
        try:
            provider: StructuredLLMProvider = provider_factory()
            response = provider.generate(
                response_model=BodyChunkExtraction,
                system_prompt=SYSTEM_PROMPT,
                payload=payload,
                model=model,
            )
            generation = getattr(provider, "last_generation", None)
            metadata = {
                "cache_hit": False,
                "requested_model": model,
                "response_model": str(getattr(generation, "response_model", model)),
                "response_id": str(getattr(generation, "response_id", "")),
                "input_tokens": int(getattr(generation, "input_tokens", 0) or 0),
                "output_tokens": int(getattr(generation, "output_tokens", 0) or 0),
                "error": "",
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"response": response.model_dump(mode="json"), "metadata": metadata}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return response, metadata
        except (LLMProviderError, ValueError, OSError) as exc:
            error = f"{type(exc).__name__}:{exc}"
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    return None, {"cache_hit": False, "requested_model": model, "response_model": "", "response_id": "", "input_tokens": 0, "output_tokens": 0, "error": error}


def extract_announcement(
    fact: dict[str, Any], body: str, *, model: str, cache_dir: Path,
    provider_factory: Any = _provider,
) -> AnnouncementExtractionRecord:
    announcement_id = str(fact.get("announcement_id") or "")
    symbol = str(fact.get("symbol") or "")
    available = str(fact.get("available_as_of") or fact.get("announcement_date") or "")[:10]
    title = str(fact.get("title") or "")
    body_digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    chunks = _body_chunks(body)
    responses: list[tuple[int, BodyChunkExtraction]] = []
    metadata: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, (chunk_start, chunk) in enumerate(chunks):
        response, meta = _call_chunk(
            announcement_id=announcement_id, symbol=symbol, title=title,
            body_digest=body_digest, chunk_index=index, chunk_start=chunk_start,
            chunk=chunk, model=model, cache_dir=cache_dir,
            provider_factory=provider_factory,
        )
        metadata.append(meta)
        if response is None:
            errors.append(f"chunk_{index}:{meta.get('error') or 'unknown_error'}")
        else:
            responses.append((chunk_start, response))

    valid_nodes: dict[tuple[str, int, int], ValidatedNode] = {}
    valid_facts: dict[tuple[str, str, int, int], ValidatedKeyFact] = {}
    invalid_count = 0
    for _, response in responses:
        for proposal in response.nodes:
            location = locate_quote(body, proposal.evidence_quote)
            if location is None:
                invalid_count += 1
                continue
            start, end = location
            item = ValidatedNode(
                node=proposal.node, confidence=proposal.confidence,
                issuer_scope=proposal.issuer_scope,
                evidence_quote=body[start:end], start_offset=start, end_offset=end,
            )
            valid_nodes[(item.node, start, end)] = item
        for proposal in response.key_facts:
            location = locate_quote(body, proposal.evidence_quote)
            if location is None:
                invalid_count += 1
                continue
            start, end = location
            item = ValidatedKeyFact(
                fact_type=proposal.fact_type, value=proposal.value, unit=proposal.unit,
                evidence_quote=body[start:end], start_offset=start, end_offset=end,
            )
            valid_facts[(item.fact_type, item.value, start, end)] = item

    deterministic_nodes = sorted({spec.node for spec, _ in _matched_specs(body)})
    usable_llm_nodes = {
        item.node for item in valid_nodes.values()
        if item.issuer_scope == "listed_company"
        and item.confidence in {"high", "medium"}
    }
    agreement = set(deterministic_nodes) & usable_llm_nodes
    conflicts: list[str] = []
    if invalid_count:
        conflicts.append("source_quote_not_found")
    if set(deterministic_nodes) - usable_llm_nodes:
        conflicts.append("deterministic_only_node")
    if usable_llm_nodes - set(deterministic_nodes):
        conflicts.append("llm_only_node")
    if any(item.confidence == "low" for item in valid_nodes.values()):
        conflicts.append("low_confidence_node")
    if any(item.issuer_scope != "listed_company" for item in valid_nodes.values()):
        conflicts.append("non_issuer_scope")
    if not responses:
        reconciliation = "failed"
        evidence_status = "failed"
    elif not deterministic_nodes and not usable_llm_nodes:
        reconciliation = "no_event"
        evidence_status = "provisional"
    elif agreement and agreement == set(deterministic_nodes) == usable_llm_nodes and not conflicts:
        reconciliation = "agreement"
        evidence_status = "body_verified"
    elif agreement:
        reconciliation = "partial_agreement"
        evidence_status = "provisional"
    else:
        reconciliation = "conflict"
        evidence_status = "conflicted"
    identity = {
        "announcement_id": announcement_id,
        "body_digest": body_digest,
        "prompt_version": PROMPT_VERSION,
        "model": model,
    }
    return AnnouncementExtractionRecord(
        record_id=content_id("P8LX", identity),
        announcement_id=announcement_id, symbol=symbol, available_as_of=available,
        title=title, source_content_digest=body_digest, requested_model=model,
        response_models=sorted({str(item.get("response_model") or model) for item in metadata if not item.get("error")}),
        chunk_count=len(chunks), completed_chunk_count=len(responses),
        cache_hit_count=sum(bool(item.get("cache_hit")) for item in metadata),
        input_tokens=sum(int(item.get("input_tokens") or 0) for item in metadata),
        output_tokens=sum(int(item.get("output_tokens") or 0) for item in metadata),
        deterministic_nodes=deterministic_nodes,
        llm_nodes=sorted(valid_nodes.values(), key=lambda item: (item.node, item.start_offset)),
        key_facts=sorted(valid_facts.values(), key=lambda item: (item.fact_type, item.start_offset)),
        invalid_proposal_count=invalid_count, reconciliation=reconciliation,
        evidence_status=evidence_status, conflict_reasons=sorted(set(conflicts)),
        errors=errors,
    )


def run_extraction(
    *, base_database: Path, p7_database: Path, start_date: str, through: str,
    model: str, cache_dir: Path, workers: int = 4,
    provider_factory: Any = _provider, limit: int | None = None,
) -> ExtractionBatchResult:
    p7_run_id, facts = _latest_p7_facts(p7_database, start_date=start_date, through=through)
    shortlist = [item for item in facts if str(item.get("llm_route") or "") == "shortlist_body_available"]
    shortlist.sort(key=lambda item: (str(item.get("available_as_of") or ""), str(item.get("announcement_id") or "")))
    if limit is not None:
        shortlist = shortlist[:limit]
    bodies = _load_bodies(base_database, {str(item.get("announcement_id") or "") for item in shortlist})
    missing = [item for item in shortlist if str(item.get("announcement_id") or "") not in bodies]
    if missing:
        raise ValueError(f"标为 body-available 的公告实际缺正文: {len(missing)}")
    records: list[AnnouncementExtractionRecord] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(
                extract_announcement, item, bodies[str(item.get("announcement_id") or "")],
                model=model, cache_dir=cache_dir, provider_factory=provider_factory,
            ): item for item in shortlist
        }
        for future in as_completed(futures):
            records.append(future.result())
    records.sort(key=lambda item: (item.available_as_of, item.announcement_id))
    cluster_counts = Counter(reason for item in records for reason in item.conflict_reasons)
    return ExtractionBatchResult(
        model=model, start_date=start_date, through=through, p7_run_id=p7_run_id,
        body_shortlist_count=len(shortlist), attempted_count=len(records),
        completed_count=sum(item.completed_chunk_count == item.chunk_count for item in records),
        failed_count=sum(item.reconciliation == "failed" for item in records),
        cache_hit_count=sum(item.cache_hit_count for item in records),
        input_tokens=sum(item.input_tokens for item in records),
        output_tokens=sum(item.output_tokens for item in records),
        reconciliation_counts=dict(sorted(Counter(item.reconciliation for item in records).items())),
        validated_node_count=sum(len(item.llm_nodes) for item in records),
        key_fact_count=sum(len(item.key_facts) for item in records),
        conflict_cluster_counts=dict(sorted(cluster_counts.items())), records=records,
    )


def reconcile_event_graph(
    *, baseline: EventGraphResult, extraction: ExtractionBatchResult,
    base_database: Path,
) -> EventGraphResult:
    by_announcement = {item.announcement_id: item for item in extraction.records}
    body_map = _load_bodies(base_database, set(by_announcement))
    events = [
        event for event in baseline.events
        if not any(source_id in by_announcement for source_id in event.source_ids)
    ]
    for announcement_id, record in sorted(by_announcement.items()):
        body = body_map[announcement_id]
        deterministic_matches = {spec.node: (spec, term) for spec, term in _matched_specs(body)}
        llm_by_node: dict[str, list[ValidatedNode]] = defaultdict(list)
        for proposal in record.llm_nodes:
            if proposal.issuer_scope == "listed_company":
                llm_by_node[proposal.node].append(proposal)
        nodes = sorted(set(deterministic_matches) | set(llm_by_node))
        for node in nodes:
            spec = next(item for item in NODE_SPECS if item.node == node)
            proposals = llm_by_node.get(node, [])
            strong = [item for item in proposals if item.confidence in {"high", "medium"}]
            agreed = node in deterministic_matches and bool(strong)
            if strong:
                proposal = strong[0]
                span = _find_span(body, proposal.evidence_quote, f"official_announcement:{announcement_id}")
            elif node in deterministic_matches:
                span = _find_span(body, deterministic_matches[node][1], f"official_announcement:{announcement_id}")
            else:
                proposal = proposals[0]
                span = _find_span(body, proposal.evidence_quote, f"official_announcement:{announcement_id}")
            if agreed:
                evidence_status = "body_verified"
                reasons: list[str] = []
            elif node in deterministic_matches and record.reconciliation == "failed":
                evidence_status = "provisional"
                reasons = ["llm_failed"]
            elif node in deterministic_matches:
                evidence_status = "conflicted"
                reasons = ["deterministic_only_node"]
            else:
                evidence_status = "provisional"
                reasons = ["llm_only_or_low_confidence"]
            event = _event(
                symbol=record.symbol, available_as_of=record.available_as_of,
                spec=spec, source_ids=[announcement_id], span=span,
                evidence_status=evidence_status,
                source_digest=record.source_content_digest,
                llm_status="failed" if record.reconciliation == "failed" else "completed",
                llm_model=record.requested_model,
                llm_prompt_version=record.prompt_version,
            ).model_copy(update={"conflict_reasons": reasons})
            events.append(event)
    unique: dict[tuple[str, str, str, str], P8DerivedEvent] = {}
    priority = {"deterministic_verified": 6, "body_verified": 5, "provisional": 3, "conflicted": 2, "title_derived": 1}
    for event in events:
        key = (event.symbol, event.available_as_of, event.node, event.source_content_digest)
        existing = unique.get(key)
        if existing is None or priority.get(event.evidence_status, 0) > priority.get(existing.evidence_status, 0):
            unique[key] = event
    ordered = sorted(unique.values(), key=lambda item: (item.available_as_of, item.symbol, item.node, item.event_id))
    return baseline.model_copy(update={
        "source_run_ids": sorted(set(baseline.source_run_ids + [extraction.p7_run_id])),
        "event_count": len(ordered),
        "evidence_status_counts": dict(sorted(Counter(item.evidence_status for item in ordered).items())),
        "node_counts": dict(sorted(Counter(item.node for item in ordered).items())),
        "company_count": len({item.symbol for item in ordered}),
        "llm_completed_count": sum(item.llm_status == "completed" for item in ordered),
        "frontiers": _frontiers(ordered),
        "events": ordered,
    })


def persist_reconciled(
    *, graph: EventGraphResult, extraction: ExtractionBatchResult,
    repository: P8ResearchRepository,
):
    records = {
        "derived_event": [item.model_dump(mode="json") for item in graph.events],
        "llm_announcement_extraction": [item.model_dump(mode="json") for item in extraction.records],
    }
    summary = extraction.model_dump(mode="json", exclude={"records"})
    run = build_run(
        run_kind="event_graph", contract_version=f"{CONTRACT_VERSION}+{EXTRACTION_CONTRACT_VERSION}",
        start_date=graph.start_date, through=graph.through,
        source_run_ids=graph.source_run_ids,
        source_digests={
            "extraction_batch": hashlib.sha256(canonical_json(summary).encode("utf-8")).hexdigest(),
            "event_graph": hashlib.sha256(canonical_json(graph.model_dump(mode="json", exclude={"events"})).encode("utf-8")).hexdigest(),
        }, record_payloads=records,
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
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--model")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--allow-llm", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.allow_llm:
        raise SystemExit("拒绝隐式调用 LLM；真实运行必须显式传入 --allow-llm")
    model = resolve_model(args.model)
    baseline = build_event_graph(
        base_database=args.base_database,
        p7_intelligence_database=args.p7_intelligence_database,
        valuation_episode_database=args.valuation_episode_database,
        start_date=args.start_date, through=args.through,
    )
    extraction = run_extraction(
        base_database=args.base_database, p7_database=args.p7_intelligence_database,
        start_date=args.start_date, through=args.through, model=model,
        cache_dir=args.cache_dir, workers=args.workers, limit=args.limit,
    )
    graph = reconcile_event_graph(baseline=baseline, extraction=extraction, base_database=args.base_database)
    run = persist_reconciled(graph=graph, extraction=extraction, repository=P8ResearchRepository(args.repository))
    output = {
        "run_id": run.run_id,
        "event_graph": graph.model_dump(mode="json", exclude={"events", "frontiers"}),
        "extraction": extraction.model_dump(mode="json", exclude={"records"}),
    }
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
