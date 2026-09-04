"""Typed append-only storage and claim boundary for P8 research derivatives."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


STORE_VERSION = "p8_research_v1"
FORBIDDEN_CLAIM_TERMS = (
    "资金流入", "主力埋伏", "内幕", "买入信号", "卖出信号",
    "胜率", "目标价", "低估", "底部",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceSpan(StrictModel):
    source_ref: str
    excerpt: str = Field(min_length=1, max_length=500)
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def offsets_are_ordered(self) -> "SourceSpan":
        if self.start_offset is not None and self.end_offset is not None:
            if self.end_offset < self.start_offset:
                raise ValueError("source span end_offset 不能小于 start_offset")
        return self


class P8DerivedEvent(StrictModel):
    event_id: str = Field(pattern=r"^P8EV-[A-F0-9]{20}$")
    symbol: str = Field(pattern=r"^\d{6}$")
    available_as_of: str
    event_type: str
    track: Literal["judicial", "investor", "plan", "execution", "risk_warning"]
    node: str
    process_direction: Literal["advance", "rollback", "unchanged", "unknown"]
    old_equity_effect: Literal["supportive", "adverse", "mixed", "unknown"]
    not_hard_outcome: bool
    precursor_candidates_for: list[str] = Field(default_factory=list)
    possible_successors: list[str] = Field(default_factory=list)
    failure_successors: list[str] = Field(default_factory=list)
    prerequisite_nodes: list[str] = Field(default_factory=list)
    evidence_status: Literal[
        "body_verified", "deterministic_verified", "title_derived",
        "provisional", "conflicted", "body_missing",
    ]
    source_ids: list[str]
    source_spans: list[SourceSpan] = Field(default_factory=list)
    extractor_version: str
    llm_status: Literal["not_required", "completed", "failed", "not_run"]
    llm_model: str = ""
    llm_prompt_version: str = ""
    source_content_digest: str = Field(pattern=r"^(|[a-f0-9]{64})$")
    conflict_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def verified_body_has_span(self) -> "P8DerivedEvent":
        if self.evidence_status == "body_verified" and not self.source_spans:
            raise ValueError("body_verified event 必须带 source span")
        if self.llm_status == "completed" and (not self.llm_model or not self.llm_prompt_version):
            raise ValueError("完成的 LLM 抽取必须登记 model 与 prompt version")
        return self


class P8ClaimEvent(StrictModel):
    event_id: str
    symbol: str
    available_as_of: str
    event_type: str
    track: str
    node: str
    process_direction: str
    old_equity_effect: str
    evidence_status: Literal["body_verified", "deterministic_verified"]
    source_ids: list[str]
    source_spans: list[SourceSpan]
    notice: Literal["程序方向与老股东影响是两条独立研究轴，不构成交易建议"] = (
        "程序方向与老股东影响是两条独立研究轴，不构成交易建议"
    )


class P8Run(StrictModel):
    run_id: str = Field(pattern=r"^P8R-[A-F0-9]{20}$")
    store_version: Literal[STORE_VERSION] = STORE_VERSION
    run_kind: Literal[
        "dry_plan", "event_graph", "activity_features", "return_paths",
        "scenario_references", "chip_proxies", "funnel", "portfolio", "backtest",
        "p8_backtest_v2_dry_plan", "p8_signal_rank_v2",
        "p8_historical_funnel_v2", "p8_walk_forward_basket_v2",
        "p8_backtest_v2_report", "p8_holder_history_v2",
    ]
    contract_version: str
    start_date: str
    through: str
    source_run_ids: list[str]
    source_digests: dict[str, str]
    record_counts: dict[str, int]
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    generated_at: str
    status: Literal["complete"] = "complete"


class P8Manifest(StrictModel):
    manifest_version: Literal[STORE_VERSION] = STORE_VERSION
    manifest_id: str = Field(pattern=r"^P8M-[A-F0-9]{20}$")
    through: str
    run_ids_by_kind: dict[str, str]
    run_digests_by_kind: dict[str, str]
    generated_at: str
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def content_id(prefix: str, value: Any) -> str:
    return f"{prefix}-{digest(value)[:20].upper()}"


def build_run(
    *, run_kind: str, contract_version: str, start_date: str, through: str,
    source_run_ids: list[str], source_digests: dict[str, str],
    record_payloads: dict[str, list[dict[str, Any]]],
) -> P8Run:
    identity = {
        "store_version": STORE_VERSION,
        "run_kind": run_kind,
        "contract_version": contract_version,
        "start_date": start_date,
        "through": through,
        "source_run_ids": sorted(source_run_ids),
        "source_digests": dict(sorted(source_digests.items())),
        "record_payloads": {
            key: sorted(values, key=canonical_json) for key, values in sorted(record_payloads.items())
        },
    }
    run_digest = digest(identity)
    return P8Run(
        run_id=f"P8R-{run_digest[:20].upper()}",
        run_kind=run_kind,
        contract_version=contract_version,
        start_date=start_date,
        through=through,
        source_run_ids=sorted(source_run_ids),
        source_digests=dict(sorted(source_digests.items())),
        record_counts={key: len(values) for key, values in sorted(record_payloads.items())},
        content_digest=run_digest,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def to_claim_event(event: P8DerivedEvent) -> P8ClaimEvent | None:
    if event.evidence_status not in {"body_verified", "deterministic_verified"}:
        return None
    payload = event.model_dump(mode="json")
    text = canonical_json(payload)
    forbidden = [term for term in FORBIDDEN_CLAIM_TERMS if term in text]
    if forbidden:
        raise ValueError(f"宣称层包含禁词: {forbidden}")
    return P8ClaimEvent(
        event_id=event.event_id,
        symbol=event.symbol,
        available_as_of=event.available_as_of,
        event_type=event.event_type,
        track=event.track,
        node=event.node,
        process_direction=event.process_direction,
        old_equity_effect=event.old_equity_effect,
        evidence_status=event.evidence_status,
        source_ids=event.source_ids,
        source_spans=event.source_spans,
    )


class P8ResearchRepository:
    """Append-only P8 store. Source planes remain immutable."""

    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.executescript("""
            pragma foreign_keys=on;
            create table if not exists p8_runs (
                run_id text primary key, run_kind text not null,
                contract_version text not null, start_date text not null,
                through text not null, content_digest text not null,
                payload_json text not null, created_at text not null
            );
            create table if not exists p8_records (
                run_id text not null, record_type text not null,
                record_id text not null, symbol text not null,
                available_as_of text not null, evidence_status text not null,
                content_digest text not null, payload_json text not null,
                primary key(run_id,record_type,record_id),
                foreign key(run_id) references p8_runs(run_id)
            );
            create index if not exists idx_p8_records_symbol_date
                on p8_records(record_type,symbol,available_as_of);
            create table if not exists p8_record_versions (
                record_type text not null, record_id text not null,
                content_digest text not null, payload_json text not null,
                first_run_id text not null,
                primary key(record_type,record_id,content_digest)
            );
        """)
        return connection

    def persist(
        self, *, run: P8Run,
        records: dict[str, list[dict[str, Any]]],
    ) -> None:
        observed_counts = {key: len(value) for key, value in sorted(records.items())}
        if observed_counts != run.record_counts:
            raise ValueError("run record_counts 与待写记录不一致")
        with self._connect() as connection:
            existing = connection.execute(
                "select content_digest,payload_json from p8_runs where run_id=?", (run.run_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["content_digest"]) != run.content_digest:
                    raise ValueError("run_id digest 冲突")
                return
            connection.execute(
                "insert into p8_runs values (?,?,?,?,?,?,?,?)",
                (
                    run.run_id, run.run_kind, run.contract_version,
                    run.start_date, run.through, run.content_digest,
                    canonical_json(run.model_dump(mode="json")), run.generated_at,
                ),
            )
            for record_type, items in sorted(records.items()):
                for item in items:
                    record_id = str(item.get("record_id") or item.get("event_id") or item.get("feature_id") or item.get("path_id") or item.get("reference_id") or item.get("item_id") or "")
                    if not record_id:
                        raise ValueError(f"{record_type} 缺稳定 record ID")
                    payload = canonical_json(item)
                    content_digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                    symbol = str(item.get("symbol") or "")
                    available = str(item.get("available_as_of") or item.get("trade_date") or item.get("start_date") or run.through)
                    evidence = str(item.get("evidence_status") or item.get("status") or "derived")
                    connection.execute(
                        "insert into p8_records values (?,?,?,?,?,?,?,?)",
                        (
                            run.run_id, record_type, record_id, symbol, available,
                            evidence, content_digest, payload,
                        ),
                    )
                    connection.execute(
                        "insert or ignore into p8_record_versions values (?,?,?,?,?)",
                        (record_type, record_id, content_digest, payload, run.run_id),
                    )

    def latest_run(self, run_kind: str) -> P8Run | None:
        if not self.path.is_file():
            return None
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            row = connection.execute(
                "select payload_json from p8_runs where run_kind=? order by created_at desc,run_id desc limit 1",
                (run_kind,),
            ).fetchone()
        return P8Run.model_validate_json(str(row[0])) if row else None

    def records(self, *, run_id: str, record_type: str) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            rows = connection.execute(
                "select payload_json from p8_records where run_id=? and record_type=? order by available_as_of,record_id",
                (run_id, record_type),
            ).fetchall()
        return [json.loads(str(row[0])) for row in rows]


def publish_manifest(
    path: Path, *, runs: list[P8Run], through: str,
) -> P8Manifest:
    if not runs:
        raise ValueError("manifest 至少需要一个完整 run")
    by_kind = {item.run_kind: item.run_id for item in runs}
    digests = {item.run_kind: item.content_digest for item in runs}
    identity = {
        "manifest_version": STORE_VERSION,
        "through": through,
        "run_ids_by_kind": dict(sorted(by_kind.items())),
        "run_digests_by_kind": dict(sorted(digests.items())),
    }
    content_digest = digest(identity)
    manifest = P8Manifest(
        manifest_id=f"P8M-{content_digest[:20].upper()}",
        through=through,
        run_ids_by_kind=dict(sorted(by_kind.items())),
        run_digests_by_kind=dict(sorted(digests.items())),
        generated_at=datetime.now(timezone.utc).isoformat(),
        content_digest=content_digest,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(manifest.model_dump(mode="json"), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return manifest
