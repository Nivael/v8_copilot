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
                created_at text not null
            );
            create table if not exists run_experience_links (
                run_id text not null references research_runs(run_id),
                experience_id text not null,
                relation text not null,
                created_at text not null,
                primary key (run_id, experience_id, relation)
            );
        """)
        return connection

    def _connect_readonly(self) -> sqlite3.Connection | None:
        if not self.path.is_file():
            return None
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
                "insert into research_runs values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id, value.request_id, value.question_text,
                    value.normalized_intent, _json(value.object_refs),
                    _json(value.evidence_pack_ids), value.final_answer,
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

    def add_feedback(
        self,
        run_id: str,
        *,
        category: str,
        feedback_text: str,
        submitted_by: str,
    ) -> str:
        feedback_id = f"FB-{uuid4().hex[:20].upper()}"
        with self._connect() as connection:
            exists = connection.execute(
                "select 1 from research_runs where run_id=?", (run_id,)
            ).fetchone()
            if exists is None:
                raise KeyError(run_id)
            connection.execute(
                "insert into run_feedback values (?,?,?,?,?,?)",
                (feedback_id, run_id, category, feedback_text, submitted_by, _now()),
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
                "from run_experience_links l where l.run_id=r.run_id), '[]') as candidates "
                "from research_runs r order by created_at desc limit ?",
                (limit,),
            ).fetchall()
        return [self._record(row) for row in rows]

    @staticmethod
    def _record(row: sqlite3.Row) -> ResearchRunRecord:
        return ResearchRunRecord(
            run_id=row["run_id"], request_id=row["request_id"],
            question_text=row["question_text"], normalized_intent=row["normalized_intent"],
            object_refs=_loads(row["object_refs_json"]),
            evidence_pack_ids=_loads(row["evidence_pack_ids_json"]),
            final_answer=row["final_answer"],
            validation_report=_loads(row["validation_report_json"]),
            source_freshness=_loads(row["source_freshness_json"]),
            tool_calls=_loads(row["tool_calls_json"]),
            experience_hits=_loads(row["experience_hits_json"]),
            agent_surface=row["agent_surface"], model=row["model"],
            config_digest=row["config_digest"], thread_id=row["thread_id"],
            turn_id=row["turn_id"], started_at=row["started_at"],
            completed_at=row["completed_at"], created_at=row["created_at"],
            experience_candidate_ids=_loads(row["candidates"]),
        )


class ExperienceRepository:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
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
                if merged_sources != record.source_run_refs:
                    payload = record.model_dump(mode="json")
                    payload["source_run_refs"] = merged_sources
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
        if request.action == "accept" and request.actor_type != "human":
            raise PermissionError("只有 human review 可以接受经验")
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
        tokens = {token for token in question.casefold().replace("？", " ").split() if token}
        records = self.list(status=ExperienceStatus.ACCEPTED, limit=200)
        ranked: list[tuple[int, ExperienceRecord]] = []
        for record in records:
            haystack = " ".join([
                record.title, record.value_summary, *record.trigger_conditions,
                *record.scope,
            ]).casefold()
            score = sum(1 for token in tokens if token in haystack)
            # Chinese questions often have no spaces; trigger phrase containment is stronger.
            normalized_triggers = {
                trigger.removesuffix("问题").removesuffix("查询")
                for trigger in record.trigger_conditions
            }
            score += 3 * sum(
                1 for trigger in normalized_triggers
                if len(trigger) >= 2 and trigger in question
            )
            if score or any(term in question for term in record.scope):
                ranked.append((score, record))
        ranked.sort(key=lambda item: (-item[0], item[1].title))
        return [
            {
                "experience_id": record.experience_id,
                "title": record.title,
                "experience_type": record.experience_type.value,
                "value_summary": record.value_summary,
                "trigger_conditions": record.trigger_conditions,
                "answer_rubric": record.answer_rubric,
                "coverage_boundaries": record.coverage_boundaries,
                "version": record.experience_version,
                "not_evidence": True,
            }
            for _, record in ranked[:limit]
        ]

    @staticmethod
    def _record(row: sqlite3.Row) -> ExperienceRecord:
        return ExperienceRecord.model_validate(_loads(row["payload_json"]))
