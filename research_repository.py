"""Dedicated local repositories for run audit and reusable experience."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from experience_contract import (
    EXPERIENCE_CONTRACT_VERSION,
    ExperienceCandidateInput,
    ExperienceRecord,
    ExperienceReviewRequest,
    ExperienceStatus,
)
from experience_topics import detect_topic_tags, retrieval_score


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _loads(value: str) -> Any:
    return json.loads(value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResearchRunCreate(StrictModel):
    request_id: str = Field(min_length=1, max_length=128)
    question_text: str = Field(min_length=1, max_length=4000)
    normalized_intent: str = Field(min_length=1, max_length=128)
    object_refs: list[str] = Field(default_factory=list, max_length=20)
    evidence_pack_ids: list[str] = Field(min_length=1, max_length=20)
    final_answer: str = Field(min_length=1, max_length=20000)
    research_draft: dict[str, Any] = Field(default_factory=dict)
    decision_audit: dict[str, Any] = Field(default_factory=dict)
    validation_report: dict[str, Any]
    source_freshness: dict[str, str]
    tool_calls: list[str] = Field(default_factory=list, max_length=100)
    experience_hits: list[str] = Field(default_factory=list, max_length=50)
    agent_surface: str = Field(min_length=1, max_length=64)
    model: str = Field(default="", max_length=128)
    config_digest: str = Field(default="", max_length=128)
    thread_id: str = Field(default="", max_length=128)
    turn_id: str = Field(default="", max_length=128)
    started_at: str = Field(default="")
    completed_at: str = Field(default="")


class ResearchRunRecord(ResearchRunCreate):
    run_id: str = Field(pattern=r"^RUN-[A-F0-9]{24}$")
    created_at: str
    experience_candidate_ids: list[str] = Field(default_factory=list)
    feedback_count: int = Field(default=0, ge=0)


class EvidencePackAuditRecord(StrictModel):
    pack_id: str = Field(pattern=r"^EP-[A-F0-9]{20}$")
    pack_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    payload: dict[str, Any]
    created_at: str


class ResearchRunLedger:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("pragma foreign_keys=on")
        connection.executescript("""
            create table if not exists research_runs (
                run_id text primary key,
                request_id text not null,
                question_text text not null,
                normalized_intent text not null,
                object_refs_json text not null,
                evidence_pack_ids_json text not null,
                final_answer text not null,
                research_draft_json text not null default '{}',
                decision_audit_json text not null default '{}',
                validation_report_json text not null,
                source_freshness_json text not null,
                tool_calls_json text not null,
                experience_hits_json text not null,
                agent_surface text not null,
                model text not null,
                config_digest text not null,
                thread_id text not null,
                turn_id text not null,
                started_at text not null,
                completed_at text not null,
                created_at text not null
            );
            create table if not exists run_feedback (
                feedback_id text primary key,
                run_id text not null references research_runs(run_id),
                category text not null,
                feedback_text text not null,
                submitted_by text not null,
                created_at text not null,
                dedupe_key text
            );
            create table if not exists run_experience_links (
                run_id text not null references research_runs(run_id),
                experience_id text not null,
                relation text not null,
                created_at text not null,
                primary key (run_id, experience_id, relation)
            );
            create table if not exists evidence_packs (
                pack_id text primary key,
                pack_digest text not null,
                payload_json text not null,
                created_at text not null
            );
        """)
        columns = {
            str(row[1]) for row in connection.execute("pragma table_info(research_runs)")
        }
        if "research_draft_json" not in columns:
            connection.execute(
                "alter table research_runs add column research_draft_json text not null default '{}'"
            )
        if "decision_audit_json" not in columns:
            connection.execute(
                "alter table research_runs add column decision_audit_json text not null default '{}'"
            )
        feedback_columns = {
            str(row[1]) for row in connection.execute("pragma table_info(run_feedback)")
        }
        if "dedupe_key" not in feedback_columns:
            connection.execute("alter table run_feedback add column dedupe_key text")
        seen_feedback_keys = {
            str(row[0]) for row in connection.execute(
                "select dedupe_key from run_feedback where dedupe_key is not null"
            ).fetchall()
        }
        for row in connection.execute(
            "select feedback_id,run_id,category,feedback_text,submitted_by from run_feedback "
            "where dedupe_key is null order by created_at,feedback_id"
        ).fetchall():
            key = self._feedback_dedupe_key(
                str(row["run_id"]), str(row["category"]),
                str(row["feedback_text"]), str(row["submitted_by"]),
            )
            if key in seen_feedback_keys:
                key = hashlib.sha256(
                    f"legacy-duplicate:{key}:{row['feedback_id']}".encode("utf-8")
                ).hexdigest()
            seen_feedback_keys.add(key)
            connection.execute(
                "update run_feedback set dedupe_key=? where feedback_id=?",
                (key, str(row["feedback_id"])),
            )
        connection.execute(
            "create unique index if not exists idx_run_feedback_dedupe "
            "on run_feedback(dedupe_key)"
        )
        return connection

    @staticmethod
    def _feedback_dedupe_key(
        run_id: str, category: str, feedback_text: str, submitted_by: str,
    ) -> str:
        normalized = " ".join(feedback_text.casefold().split())
        return hashlib.sha256(_json({
            "run_id": run_id, "category": category,
            "feedback_text": normalized, "submitted_by": submitted_by.casefold(),
        }).encode("utf-8")).hexdigest()

    def _connect_readonly(self) -> sqlite3.Connection | None:
        if not self.path.is_file():
            return None
        # Existing local ledgers are migrated in place before the read-only handle
        # is opened. Missing ledgers remain missing, so a read never creates one.
        with self._connect():
            pass
        connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def record(self, value: ResearchRunCreate) -> ResearchRunRecord:
        created_at = _now()
        run_id = f"RUN-{uuid4().hex[:24].upper()}"
        started_at = value.started_at or created_at
        completed_at = value.completed_at or created_at
        with self._connect() as connection:
            connection.execute(
                "insert into research_runs ("
                "run_id,request_id,question_text,normalized_intent,object_refs_json,"
                "evidence_pack_ids_json,final_answer,research_draft_json,decision_audit_json,"
                "validation_report_json,source_freshness_json,tool_calls_json,experience_hits_json,"
                "agent_surface,model,config_digest,thread_id,turn_id,started_at,completed_at,created_at"
                ") values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id, value.request_id, value.question_text,
                    value.normalized_intent, _json(value.object_refs),
                    _json(value.evidence_pack_ids), value.final_answer,
                    _json(value.research_draft), _json(value.decision_audit),
                    _json(value.validation_report), _json(value.source_freshness),
                    _json(value.tool_calls), _json(value.experience_hits),
                    value.agent_surface, value.model, value.config_digest,
                    value.thread_id, value.turn_id, started_at, completed_at, created_at,
                ),
            )
        payload = value.model_dump()
        payload.update({
            "run_id": run_id,
            "created_at": created_at,
            "started_at": started_at,
            "completed_at": completed_at,
        })
        return ResearchRunRecord.model_validate(payload)

    def store_evidence_pack(self, payload: dict[str, Any]) -> EvidencePackAuditRecord:
        pack_id = str(payload.get("pack_id") or "")
        pack_digest = str(payload.get("pack_digest") or "")
        if not pack_id.startswith("EP-") or len(pack_id) != 23:
            raise ValueError("EvidencePack pack_id 非法")
        if len(pack_digest) != 64 or any(char not in "0123456789abcdef" for char in pack_digest):
            raise ValueError("EvidencePack pack_digest 非法")
        digest_payload = {key: value for key, value in payload.items() if key not in {"pack_id", "pack_digest"}}
        actual_digest = hashlib.sha256(_json(digest_payload).encode("utf-8")).hexdigest()
        if actual_digest != pack_digest or pack_id != f"EP-{actual_digest[:20].upper()}":
            raise ValueError("EvidencePack digest 或 pack_id 与内容不匹配")
        created_at = _now()
        with self._connect() as connection:
            existing = connection.execute(
                "select pack_digest,payload_json,created_at from evidence_packs where pack_id=?",
                (pack_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["pack_digest"]) != pack_digest or _loads(existing["payload_json"]) != payload:
                    raise ValueError("同 pack_id 的 EvidencePack 内容不一致")
                return EvidencePackAuditRecord(
                    pack_id=pack_id, pack_digest=pack_digest,
                    payload=payload, created_at=str(existing["created_at"]),
                )
            connection.execute(
                "insert into evidence_packs values (?,?,?,?)",
                (pack_id, pack_digest, _json(payload), created_at),
            )
        return EvidencePackAuditRecord(
            pack_id=pack_id, pack_digest=pack_digest, payload=payload, created_at=created_at,
        )

    def get_evidence_pack(self, pack_id: str) -> EvidencePackAuditRecord:
        connection = self._connect_readonly()
        if connection is None:
            raise KeyError(pack_id)
        with connection:
            row = connection.execute(
                "select * from evidence_packs where pack_id=?", (pack_id,)
            ).fetchone()
        if row is None:
            raise KeyError(pack_id)
        return EvidencePackAuditRecord(
            pack_id=str(row["pack_id"]), pack_digest=str(row["pack_digest"]),
            payload=_loads(row["payload_json"]), created_at=str(row["created_at"]),
        )

    def add_feedback(
        self,
        run_id: str,
        *,
        category: str,
        feedback_text: str,
        submitted_by: str,
    ) -> str:
        dedupe_key = self._feedback_dedupe_key(
            run_id, category, feedback_text, submitted_by,
        )
        with self._connect() as connection:
            exists = connection.execute(
                "select 1 from research_runs where run_id=?", (run_id,)
            ).fetchone()
            if exists is None:
                raise KeyError(run_id)
            existing = connection.execute(
                "select feedback_id from run_feedback where dedupe_key=?", (dedupe_key,)
            ).fetchone()
            if existing is not None:
                return str(existing["feedback_id"])
            feedback_id = f"FB-{uuid4().hex[:20].upper()}"
            connection.execute(
                "insert into run_feedback "
                "(feedback_id,run_id,category,feedback_text,submitted_by,created_at,dedupe_key) "
                "values (?,?,?,?,?,?,?)",
                (feedback_id, run_id, category, feedback_text, submitted_by, _now(), dedupe_key),
            )
        return feedback_id

    def link_experience(self, run_id: str, experience_id: str, relation: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "insert or ignore into run_experience_links values (?,?,?,?)",
                (run_id, experience_id, relation, _now()),
            )

    def list(self, *, limit: int = 50) -> list[ResearchRunRecord]:
        connection = self._connect_readonly()
        if connection is None:
            return []
        with connection:
            rows = connection.execute(
                "select r.*, coalesce((select json_group_array(experience_id) "
                "from run_experience_links l where l.run_id=r.run_id), '[]') as candidates, "
                "(select count(*) from run_feedback f where f.run_id=r.run_id) as feedback_count "
                "from research_runs r order by created_at desc limit ?",
                (limit,),
            ).fetchall()
        return [self._record(row) for row in rows]

    def get(self, run_id: str) -> ResearchRunRecord:
        connection = self._connect_readonly()
        if connection is None:
            raise KeyError(run_id)
        with connection:
            row = connection.execute(
                "select r.*, coalesce((select json_group_array(experience_id) "
                "from run_experience_links l where l.run_id=r.run_id), '[]') as candidates, "
                "(select count(*) from run_feedback f where f.run_id=r.run_id) as feedback_count "
                "from research_runs r where run_id=?",
                (run_id,),
            ).fetchone()
        if row is None:
            raise KeyError(run_id)
        return self._record(row)

    @staticmethod
    def _record(row: sqlite3.Row) -> ResearchRunRecord:
        return ResearchRunRecord(
            run_id=row["run_id"], request_id=row["request_id"],
            question_text=row["question_text"], normalized_intent=row["normalized_intent"],
            object_refs=_loads(row["object_refs_json"]),
            evidence_pack_ids=_loads(row["evidence_pack_ids_json"]),
            final_answer=row["final_answer"],
            research_draft=_loads(row["research_draft_json"]),
            decision_audit=_loads(row["decision_audit_json"]),
            validation_report=_loads(row["validation_report_json"]),
            source_freshness=_loads(row["source_freshness_json"]),
            tool_calls=_loads(row["tool_calls_json"]),
            experience_hits=_loads(row["experience_hits_json"]),
            agent_surface=row["agent_surface"], model=row["model"],
            config_digest=row["config_digest"], thread_id=row["thread_id"],
            turn_id=row["turn_id"], started_at=row["started_at"],
            completed_at=row["completed_at"], created_at=row["created_at"],
            experience_candidate_ids=_loads(row["candidates"]),
            feedback_count=int(row["feedback_count"]),
        )


class ExperienceRepository:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("pragma foreign_keys=on")
        connection.executescript("""
            create table if not exists experiences (
                experience_id text primary key,
                contract_version text not null,
                experience_version integer not null,
                status text not null,
                experience_type text not null,
                title text not null,
                value_summary text not null,
                payload_json text not null,
                dedupe_key text not null unique,
                created_at text not null,
                reviewed_at text,
                reviewed_by text,
                not_evidence integer not null check (not_evidence=1)
            );
            create table if not exists experience_transitions (
                transition_id text primary key,
                experience_id text not null references experiences(experience_id),
                from_status text not null,
                to_status text not null,
                actor_type text not null,
                reviewed_by text not null,
                note text not null,
                merge_target text,
                created_at text not null
            );
            create table if not exists experience_review_sessions (
                review_session_id text primary key,
                source_packet text not null,
                queue_json text not null,
                created_at text not null
            );
            create table if not exists experience_review_decisions (
                review_session_id text not null references experience_review_sessions(review_session_id),
                card_id text not null,
                decision_json text not null,
                created_at text not null,
                primary key (review_session_id, card_id)
            );
        """)
        return connection

    def _connect_readonly(self) -> sqlite3.Connection | None:
        if not self.path.is_file():
            return None
        connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def dedupe_key(value: ExperienceCandidateInput) -> str:
        reusable = {
            "experience_type": value.experience_type.value,
            "title": value.title.casefold(),
            "trigger_conditions": sorted(item.casefold() for item in value.trigger_conditions),
            "scope": sorted(item.casefold() for item in value.scope),
        }
        return hashlib.sha256(_json(reusable).encode("utf-8")).hexdigest()

    def propose(self, value: ExperienceCandidateInput) -> ExperienceRecord:
        dedupe_key = self.dedupe_key(value)
        with self._connect() as connection:
            existing = connection.execute(
                "select * from experiences where dedupe_key=?", (dedupe_key,)
            ).fetchone()
            if existing is not None:
                record = self._record(existing)
                merged_sources = sorted(set(record.source_run_refs) | set(value.source_run_refs))
                merged_topics = sorted(set(record.topic_tags) | set(value.topic_tags))
                merged_validation = sorted(set(record.validation_refs) | set(value.validation_refs))
                if (
                    merged_sources != record.source_run_refs
                    or merged_topics != record.topic_tags
                    or merged_validation != record.validation_refs
                ):
                    payload = record.model_dump(mode="json")
                    payload["source_run_refs"] = merged_sources
                    payload["topic_tags"] = merged_topics
                    payload["validation_refs"] = merged_validation
                    connection.execute(
                        "update experiences set payload_json=? where experience_id=?",
                        (_json(payload), record.experience_id),
                    )
                    record = ExperienceRecord.model_validate(payload)
                return record
            experience_id = f"EXP-{dedupe_key[:20].upper()}"
            created_at = _now()
            record = ExperienceRecord(
                **value.model_dump(), experience_id=experience_id,
                dedupe_key=dedupe_key, created_at=created_at,
            )
            connection.execute(
                "insert into experiences values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    record.experience_id, EXPERIENCE_CONTRACT_VERSION,
                    record.experience_version, record.status.value,
                    record.experience_type.value, record.title, record.value_summary,
                    _json(record.model_dump(mode="json")), record.dedupe_key,
                    created_at, None, None, 1,
                ),
            )
            return record

    def get(self, experience_id: str) -> ExperienceRecord:
        connection = self._connect_readonly()
        if connection is None:
            raise KeyError(experience_id)
        with connection:
            row = connection.execute(
                "select * from experiences where experience_id=?", (experience_id,)
            ).fetchone()
        if row is None:
            raise KeyError(experience_id)
        return self._record(row)

    def list(
        self,
        *,
        status: ExperienceStatus | None = None,
        limit: int = 100,
    ) -> list[ExperienceRecord]:
        query = "select * from experiences"
        params: list[Any] = []
        if status is not None:
            query += " where status=?"
            params.append(status.value)
        query += " order by created_at desc limit ?"
        params.append(limit)
        connection = self._connect_readonly()
        if connection is None:
            return []
        with connection:
            rows = connection.execute(query, params).fetchall()
        return [self._record(row) for row in rows]

    def review(
        self,
        experience_id: str,
        request: ExperienceReviewRequest,
    ) -> ExperienceRecord:
        if request.action == "accept" and request.actor_type not in {"human", "owner_policy"}:
            raise PermissionError("只有 human review 或预授权 owner policy 可以接受经验")
        target = {
            "accept": ExperienceStatus.ACCEPTED,
            "ignore": ExperienceStatus.IGNORED,
            "block": ExperienceStatus.BLOCKED,
            "merge": ExperienceStatus.MERGED,
            "close": ExperienceStatus.CLOSED,
            "supersede": ExperienceStatus.SUPERSEDED,
        }[request.action]
        allowed = {
            ExperienceStatus.CANDIDATE: {
                ExperienceStatus.ACCEPTED, ExperienceStatus.IGNORED,
                ExperienceStatus.BLOCKED, ExperienceStatus.MERGED,
                ExperienceStatus.CLOSED,
            },
            ExperienceStatus.ACCEPTED: {
                ExperienceStatus.BLOCKED, ExperienceStatus.MERGED,
                ExperienceStatus.CLOSED, ExperienceStatus.SUPERSEDED,
            },
            ExperienceStatus.BLOCKED: {
                ExperienceStatus.ACCEPTED, ExperienceStatus.CLOSED,
            },
        }
        current = self.get(experience_id)
        if target not in allowed.get(current.status, set()):
            raise ValueError(f"非法经验状态转换: {current.status.value} -> {target.value}")
        reviewed_at = _now()
        payload = current.model_dump(mode="json")
        payload.update({
            "status": target.value,
            "experience_version": current.experience_version + 1,
            "reviewed_at": reviewed_at,
            "reviewed_by": request.reviewed_by,
        })
        updated = ExperienceRecord.model_validate(payload)
        with self._connect() as connection:
            connection.execute(
                "update experiences set status=?,experience_version=?,payload_json=?,"
                "reviewed_at=?,reviewed_by=? where experience_id=?",
                (
                    target.value, updated.experience_version,
                    _json(updated.model_dump(mode="json")), reviewed_at,
                    request.reviewed_by, experience_id,
                ),
            )
            connection.execute(
                "insert into experience_transitions values (?,?,?,?,?,?,?,?,?)",
                (
                    f"TR-{uuid4().hex[:20].upper()}", experience_id,
                    current.status.value, target.value, request.actor_type,
                    request.reviewed_by, request.note, request.merge_target, reviewed_at,
                ),
            )
        return updated

    def retrieve_accepted(self, question: str, *, limit: int = 8) -> list[dict[str, Any]]:
        records = self.list(status=ExperienceStatus.ACCEPTED, limit=200)
        ranked: list[tuple[int, ExperienceRecord]] = []
        for record in records:
            searchable = [
                *record.trigger_conditions, *record.scope,
                record.title, record.value_summary,
            ]
            effective_topics = sorted(set(record.topic_tags) | set(
                detect_topic_tags(" ".join(searchable))
            ))
            score = retrieval_score(
                question,
                topic_tags=effective_topics,
                fields=[*effective_topics, *searchable],
            )
            if score:
                ranked.append((score, record))
        ranked.sort(key=lambda item: (-item[0], item[1].title))
        return [
            {
                "experience_id": record.experience_id,
                "title": record.title,
                "experience_type": record.experience_type.value,
                "value_summary": record.value_summary,
                "trigger_conditions": record.trigger_conditions,
                "topic_tags": record.topic_tags,
                "answer_rubric": record.answer_rubric,
                "coverage_boundaries": record.coverage_boundaries,
                "version": record.experience_version,
                "not_evidence": True,
            }
            for _, record in ranked[:limit]
        ]

    def save_review_queue(self, payload: dict[str, Any]) -> None:
        session_id = str(payload["review_session_id"])
        source_packet = str(payload["source_packet"])
        with self._connect() as connection:
            existing = connection.execute(
                "select queue_json from experience_review_sessions where review_session_id=?",
                (session_id,),
            ).fetchone()
            serialized = _json(payload)
            if existing is not None and str(existing["queue_json"]) != serialized:
                raise ValueError("同 review_session_id 的 queue 内容不一致")
            connection.execute(
                "insert or ignore into experience_review_sessions values (?,?,?,?)",
                (session_id, source_packet, serialized, _now()),
            )

    def get_review_queue(self, review_session_id: str) -> dict[str, Any]:
        connection = self._connect_readonly()
        if connection is None:
            raise KeyError(review_session_id)
        with connection:
            row = connection.execute(
                "select queue_json from experience_review_sessions where review_session_id=?",
                (review_session_id,),
            ).fetchone()
        if row is None:
            raise KeyError(review_session_id)
        return _loads(str(row["queue_json"]))

    def record_review_decision(
        self, review_session_id: str, card_id: str, payload: dict[str, Any],
    ) -> bool:
        """Persist a decision separately; return False for an identical replay."""
        serialized = _json(payload)
        with self._connect() as connection:
            existing = connection.execute(
                "select decision_json from experience_review_decisions "
                "where review_session_id=? and card_id=?",
                (review_session_id, card_id),
            ).fetchone()
            if existing is not None:
                if str(existing["decision_json"]) != serialized:
                    raise ValueError("同一审阅卡已经提交过不同决定")
                return False
            connection.execute(
                "insert into experience_review_decisions values (?,?,?,?)",
                (review_session_id, card_id, serialized, _now()),
            )
        return True

    def get_review_decision(
        self, review_session_id: str, card_id: str,
    ) -> dict[str, Any] | None:
        connection = self._connect_readonly()
        if connection is None:
            return None
        with connection:
            row = connection.execute(
                "select decision_json from experience_review_decisions "
                "where review_session_id=? and card_id=?",
                (review_session_id, card_id),
            ).fetchone()
        return _loads(str(row["decision_json"])) if row is not None else None

    @staticmethod
    def _record(row: sqlite3.Row) -> ExperienceRecord:
        return ExperienceRecord.model_validate(_loads(row["payload_json"]))
