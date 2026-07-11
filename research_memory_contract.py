"""D-053 Research Memory contract and deterministic identity construction.

This module defines serialization contracts only. It has no persistence or research-source
write capability.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator


RESEARCH_MEMORY_CONTRACT_VERSION = "v8_research_memory_contract_v0"
REVIEW_ACTIVE_LIMIT = 20

MemoryStatus = Literal["candidate", "accepted", "ignored", "merged", "blocked", "closed"]
ResearchStatus = Literal["answerable", "needs_data", "needs_review"]
QuestionView = Literal["evidence", "query", "checklist", "methodology", "data_debt"]
DebtRefStatus = Literal["assigned", "needs_assignment", "not_required"]
ObjectKind = Literal[
    "stock",
    "stock_event",
    "stock_to_universe",
    "stock_or_episode",
    "episode_type",
    "cluster",
    "lens_cluster",
    "lens",
    "cohort",
    "universe",
    "unknown",
]
SourceType = Literal[
    "user_question",
    "research_run",
    "answer_card",
    "research_response",
    "human_review",
    "post_v7_backlog",
    "seed_fixture",
    "query_template_registry",
    "feedback_event",
    "system_gap",
]
ProvenanceType = Literal[
    "contract_fixture",
    "seed_fixture",
    "research_response",
    "answer_card",
    "review_decision",
    "query_template_registry",
    "user_feedback",
    "research_source",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value


def normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).strip().split())


def normalize_symbol(value: str) -> str:
    normalized = normalize_text(value).upper()
    match = re.fullmatch(r"(?:(?:SH|SZ)[.:-]?)?(\d{6})(?:[.:-]?(?:SH|SZ))?", normalized)
    return match.group(1) if match else normalized.casefold()


def normalize_token(value: str) -> str:
    return normalize_text(value).casefold()


def normalize_many(values: list[str], *, symbols: bool = False) -> list[str]:
    normalizer = normalize_symbol if symbols else normalize_token
    return sorted({normalizer(value) for value in values if normalize_text(value)})


def canonical_scope(kind: ObjectKind, refs: list[str]) -> str:
    normalized = normalize_many(refs, symbols=kind in {"stock", "stock_event"})
    if not normalized:
        raise ValueError("scope requires at least one non-empty ref")
    return f"{kind}:{','.join(normalized)}"


def dedupe_for(canonical_key: str) -> str:
    return sha256(canonical_key.encode("utf-8")).hexdigest()


def stable_id(prefix: str, dedupe_key: str) -> str:
    return f"{prefix}-{dedupe_key[:20].upper()}"


class ObjectScope(StrictModel):
    kind: ObjectKind
    refs: list[str] = Field(min_length=1, max_length=20)

    @field_validator("refs")
    @classmethod
    def normalize_refs(cls, value: list[str], info: Any) -> list[str]:
        kind = info.data.get("kind", "unknown")
        return normalize_many(value, symbols=kind in {"stock", "stock_event"})

    @model_validator(mode="after")
    def require_ref(self) -> "ObjectScope":
        if not self.refs:
            raise ValueError("scope requires at least one non-empty ref")
        return self

    @property
    def canonical(self) -> str:
        return canonical_scope(self.kind, self.refs)


class TimeScope(StrictModel):
    semantics: Literal[
        "not_applicable",
        "as_of",
        "event_window",
        "calendar_range",
        "trading_day_window",
    ] = "not_applicable"
    start: str | None = None
    end: str | None = None
    before: int | None = Field(default=None, ge=0)
    after: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_shape(self) -> "TimeScope":
        has_dates = self.start is not None or self.end is not None
        has_window = self.before is not None or self.after is not None
        if self.semantics == "not_applicable" and (has_dates or has_window):
            raise ValueError("not_applicable time scope cannot carry bounds")
        if self.semantics in {"as_of", "calendar_range"} and not (self.start or self.end):
            raise ValueError(f"{self.semantics} requires start or end")
        if self.semantics in {"as_of", "calendar_range"} and has_window:
            raise ValueError(f"{self.semantics} cannot carry event-window bounds")
        if self.semantics in {"event_window", "trading_day_window"} and (
            self.before is None or self.after is None
        ):
            raise ValueError(f"{self.semantics} requires before and after")
        if self.semantics in {"event_window", "trading_day_window"} and has_dates:
            raise ValueError(f"{self.semantics} cannot carry calendar bounds")
        return self

    @property
    def canonical(self) -> str:
        parts = [self.semantics]
        if self.start is not None:
            parts.append(f"start={normalize_token(self.start)}")
        if self.end is not None:
            parts.append(f"end={normalize_token(self.end)}")
        if self.before is not None:
            parts.append(f"before={self.before}")
        if self.after is not None:
            parts.append(f"after={self.after}")
        return ";".join(parts)


class SourceRef(StrictModel):
    source_type: SourceType
    source_ref: str = Field(min_length=1, max_length=1000)
    source_alias: str | None = Field(default=None, max_length=4000)


class ProvenanceRef(StrictModel):
    provenance_type: ProvenanceType
    provenance_ref: str = Field(min_length=1, max_length=1000)


class AuditFields(StrictModel):
    contract_version: Literal[RESEARCH_MEMORY_CONTRACT_VERSION] = RESEARCH_MEMORY_CONTRACT_VERSION
    status: MemoryStatus
    created_at: datetime
    updated_at: datetime
    source_refs: list[SourceRef] = Field(min_length=1, max_length=100)
    provenance_refs: list[ProvenanceRef] = Field(min_length=1, max_length=100)

    _created_at_aware = field_validator("created_at")(_aware)
    _updated_at_aware = field_validator("updated_at")(_aware)

    @model_validator(mode="after")
    def validate_audit_order(self) -> "AuditFields":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        return self


def _identity_payload(kind: str, parts: dict[str, Any]) -> str:
    rendered: list[str] = [kind]
    for key in sorted(parts):
        value = parts[key]
        if isinstance(value, list):
            normalized = normalize_many([str(item) for item in value])
            rendered.append(f"{key}=[{','.join(normalized)}]")
        else:
            rendered.append(f"{key}={normalize_token(str(value))}")
    return "|".join(rendered)


class MemoryEntity(AuditFields):
    memory_id: str = Field(min_length=1, max_length=128)
    canonical_key: str = Field(min_length=1, max_length=4000)
    dedupe_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    not_evidence: Literal[True] = True


class ResearchRunRef(StrictModel):
    """Non-knowledge source identity. It is never used in target entity dedupe."""

    contract_version: Literal[RESEARCH_MEMORY_CONTRACT_VERSION] = RESEARCH_MEMORY_CONTRACT_VERSION
    run_id: str = Field(min_length=1, max_length=256)
    request_id: str = Field(min_length=1, max_length=256)
    answer_card_id: str | None = Field(default=None, max_length=256)
    research_response_id: str | None = Field(default=None, max_length=256)
    recorded_at: datetime

    _recorded_at_aware = field_validator("recorded_at")(_aware)


class QuestionCard(MemoryEntity):
    external_qc_id: str | None = Field(default=None, pattern=r"^QC-(?:[0-9]{8}-[0-9]{3}|CAND-[a-f0-9]{12})$")
    canonical_question: str = Field(min_length=1, max_length=4000)
    aliases: list[str] = Field(default_factory=list, max_length=100)
    scope: ObjectScope
    semantic_intent: str = Field(min_length=1, max_length=256)
    time_scope: TimeScope = Field(default_factory=TimeScope)
    needs_data: list[str] = Field(default_factory=list, max_length=50)
    research_status: ResearchStatus
    view: QuestionView
    original_source: Literal["user", "human_review", "slice", "system_gap"]
    external_debt_ref: str | None = Field(default=None, max_length=128)
    debt_ref_status: DebtRefStatus

    @field_validator("aliases")
    @classmethod
    def normalize_aliases(cls, value: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for item in value:
            normalized = normalize_text(item)
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result

    @field_validator("needs_data")
    @classmethod
    def normalize_needs_data(cls, value: list[str]) -> list[str]:
        return normalize_many(value)

    @model_validator(mode="after")
    def validate_identity_and_debt(self) -> "QuestionCard":
        expected = question_card_key(
            external_qc_id=self.external_qc_id,
            scope=self.scope,
            semantic_intent=self.semantic_intent,
            view=self.view,
            needs_data=self.needs_data,
            time_scope=self.time_scope,
        )
        _validate_identity(self, expected, "MEM-QC")
        if self.external_qc_id and not self.external_qc_id.startswith("QC-CAND-"):
            if not any(ref.source_type == "seed_fixture" for ref in self.source_refs):
                raise ValueError("fixed QC identity requires a seed_fixture source")
            if not any(
                ref.provenance_type == "seed_fixture" for ref in self.provenance_refs
            ):
                raise ValueError("fixed QC identity requires seed_fixture provenance")
        if self.external_debt_ref and self.debt_ref_status != "assigned":
            raise ValueError("external_debt_ref requires debt_ref_status=assigned")
        if self.debt_ref_status == "assigned" and not self.external_debt_ref:
            raise ValueError("assigned debt_ref_status requires external_debt_ref")
        if self.research_status != "needs_data" and self.debt_ref_status != "not_required":
            raise ValueError("only needs_data questions may require debt assignment")
        return self


class DataDebtCard(MemoryEntity):
    gap_id: str = Field(min_length=1, max_length=256)
    gap_summary: str = Field(min_length=1, max_length=4000)
    scope: ObjectScope
    time_scope: TimeScope = Field(default_factory=TimeScope)
    required_fields: list[str] = Field(min_length=1, max_length=100)
    external_debt_ref: str | None = Field(default=None, max_length=128)
    debt_ref_status: Literal["assigned", "needs_assignment"]

    @field_validator("required_fields")
    @classmethod
    def normalize_required_fields(cls, value: list[str]) -> list[str]:
        return normalize_many(value)

    @model_validator(mode="after")
    def validate_identity_and_ref(self) -> "DataDebtCard":
        expected = data_debt_key(self.gap_id, self.scope, self.required_fields, self.time_scope)
        _validate_identity(self, expected, "MEM-DD")
        if self.debt_ref_status == "assigned" and not self.external_debt_ref:
            raise ValueError("assigned data debt requires external_debt_ref")
        if self.debt_ref_status == "needs_assignment" and self.external_debt_ref:
            raise ValueError("unassigned data debt cannot have external_debt_ref")
        return self


class ExecutorRef(StrictModel):
    registry_contract_version: str = Field(pattern=r"^v8_query_template_contract_v[0-9]+$")
    template_id: str = Field(pattern=r"^QT-[0-9]{3}$")
    executor_key: str = Field(min_length=1, max_length=128)


class QueryTemplateRecord(MemoryEntity):
    template_id: str = Field(pattern=r"^QT-[0-9]{3}$")
    definition_version: str = Field(min_length=1, max_length=128)
    question_pattern: str = Field(min_length=1, max_length=1000)
    parameter_semantics: list[str] = Field(min_length=1, max_length=50)
    outcome_semantics: list[str] = Field(min_length=1, max_length=50)
    caveats: list[str] = Field(min_length=1, max_length=50)
    executor_ref: ExecutorRef | None = None
    executable: bool = False

    @field_validator("parameter_semantics", "outcome_semantics", "caveats")
    @classmethod
    def normalize_semantics(cls, value: list[str]) -> list[str]:
        return normalize_many(value)

    @model_validator(mode="after")
    def validate_template_boundary(self) -> "QueryTemplateRecord":
        expected = query_template_key(self.template_id, self.definition_version)
        _validate_identity(self, expected, "MEM-QT")
        if self.executable and self.executor_ref is None:
            raise ValueError("executable template requires a versioned executor_ref")
        if self.executor_ref and self.executor_ref.template_id != self.template_id:
            raise ValueError("executor_ref template_id must match the record")
        if self.status == "candidate" and self.executable:
            raise ValueError("draft candidate templates cannot be executable")
        return self


class ReviewItem(MemoryEntity):
    review_kind: Literal[
        "question_acceptance", "data_debt_assignment", "dedupe_resolution", "template_review"
    ]
    target_type: Literal["question_card", "data_debt", "query_template"]
    target_memory_id: str = Field(min_length=1, max_length=128)
    priority: int = Field(default=0, ge=0, le=100)
    active: bool = True

    @model_validator(mode="after")
    def validate_review_identity(self) -> "ReviewItem":
        expected = review_item_key(self.review_kind, self.target_type, self.target_memory_id)
        _validate_identity(self, expected, "MEM-RV")
        if self.status in {"ignored", "merged", "closed"} and self.active:
            raise ValueError("terminal review items cannot remain active")
        return self


class FeedbackEvent(MemoryEntity):
    feedback_kind: Literal["useful", "inaccurate", "missing_data", "missing_context", "other"]
    target_type: Literal["answer_card", "research_response", "question_card"]
    target_ref: str = Field(min_length=1, max_length=256)
    feedback_text: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_feedback_identity(self) -> "FeedbackEvent":
        expected = feedback_event_key(
            self.feedback_kind, self.target_type, self.target_ref, self.created_at
        )
        _validate_identity(self, expected, "MEM-FB")
        return self


class MemoryLink(AuditFields):
    link_id: str = Field(pattern=r"^MEM-LK-[A-F0-9]{20}$")
    canonical_key: str = Field(min_length=1, max_length=4000)
    dedupe_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    relation: Literal[
        "derived_from",
        "alias_of",
        "review_of",
        "feedback_on",
        "merged_into",
        "sedimented_from",
    ]
    source_type: SourceType
    source_ref: str = Field(min_length=1, max_length=1000)
    target_type: Literal[
        "question_card", "data_debt", "query_template", "review_item", "feedback_event"
    ]
    target_memory_id: str = Field(min_length=1, max_length=128)
    not_evidence: Literal[True] = True

    @model_validator(mode="after")
    def validate_link_identity(self) -> "MemoryLink":
        expected = memory_link_key(
            self.relation,
            self.source_type,
            self.source_ref,
            self.target_type,
            self.target_memory_id,
        )
        expected_dedupe = dedupe_for(expected)
        if self.canonical_key != expected or self.dedupe_key != expected_dedupe:
            raise ValueError("MemoryLink identity does not match its endpoints")
        if self.link_id != stable_id("MEM-LK", expected_dedupe):
            raise ValueError("MemoryLink link_id is not server-derived")
        return self


class StatusTransition(StrictModel):
    object_type: Literal[
        "question_card", "data_debt", "query_template", "review_item", "feedback_event"
    ]
    from_status: MemoryStatus
    to_status: MemoryStatus
    actor_type: Literal["system", "human"]
    reason: str = Field(min_length=1, max_length=2000)
    merge_target_id: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def validate_transition(self) -> "StatusTransition":
        allowed = STATUS_TRANSITIONS[self.from_status]
        if self.to_status not in allowed:
            raise ValueError(f"illegal transition: {self.from_status} -> {self.to_status}")
        if self.to_status == "merged":
            if self.actor_type != "human" or not self.merge_target_id:
                raise ValueError("merge requires a human actor and explicit merge target")
        elif self.merge_target_id:
            raise ValueError("merge_target_id is only valid for merged transitions")
        return self


STATUS_TRANSITIONS: dict[MemoryStatus, tuple[MemoryStatus, ...]] = {
    "candidate": ("accepted", "ignored", "blocked", "closed"),
    "accepted": ("blocked", "merged", "closed"),
    "blocked": ("candidate", "accepted", "closed"),
    "ignored": ("candidate", "closed"),
    "merged": (),
    "closed": (),
}


class SedimentationResult(StrictModel):
    """Non-persistent result of a future repository operation."""

    contract_version: Literal[RESEARCH_MEMORY_CONTRACT_VERSION] = RESEARCH_MEMORY_CONTRACT_VERSION
    operation_id: str = Field(min_length=1, max_length=256)
    created_ids: list[str] = Field(default_factory=list, max_length=1000)
    existing_ids: list[str] = Field(default_factory=list, max_length=1000)
    created_links: list[MemoryLink] = Field(default_factory=list, max_length=5000)
    completed_at: datetime

    _completed_at_aware = field_validator("completed_at")(_aware)

    @model_validator(mode="after")
    def validate_partition(self) -> "SedimentationResult":
        if set(self.created_ids) & set(self.existing_ids):
            raise ValueError("created_ids and existing_ids must be disjoint")
        return self


def _validate_identity(entity: MemoryEntity, canonical_key: str, prefix: str) -> None:
    expected_dedupe = dedupe_for(canonical_key)
    if entity.canonical_key != canonical_key:
        raise ValueError("canonical_key does not match semantic identity")
    if entity.dedupe_key != expected_dedupe:
        raise ValueError("dedupe_key is not derived from canonical_key")
    if entity.memory_id != stable_id(prefix, expected_dedupe):
        raise ValueError("memory_id is not server-derived from dedupe_key")


def question_card_key(
    *,
    external_qc_id: str | None,
    scope: ObjectScope,
    semantic_intent: str,
    view: QuestionView,
    needs_data: list[str],
    time_scope: TimeScope,
) -> str:
    if external_qc_id and not external_qc_id.startswith("QC-CAND-"):
        return _identity_payload("question_card", {"seed_id": external_qc_id})
    return _identity_payload(
        "question_card",
        {
            "intent": semantic_intent,
            "scope": scope.canonical,
            "view": view,
            "needs_data": needs_data,
            "time": time_scope.canonical,
        },
    )


def data_debt_key(
    gap_id: str, scope: ObjectScope, required_fields: list[str], time_scope: TimeScope
) -> str:
    return _identity_payload(
        "data_debt",
        {
            "gap_id": gap_id,
            "scope": scope.canonical,
            "required_fields": required_fields,
            "time": time_scope.canonical,
        },
    )


def query_template_key(template_id: str, definition_version: str) -> str:
    return _identity_payload(
        "query_template", {"template_id": template_id, "definition_version": definition_version}
    )


def review_item_key(review_kind: str, target_type: str, target_memory_id: str) -> str:
    return _identity_payload(
        "review_item",
        {"review_kind": review_kind, "target_type": target_type, "target": target_memory_id},
    )


def feedback_event_key(
    feedback_kind: str, target_type: str, target_ref: str, created_at: datetime
) -> str:
    return _identity_payload(
        "feedback_event",
        {
            "feedback_kind": feedback_kind,
            "target_type": target_type,
            "target": target_ref,
            "occurred_at": created_at.isoformat(),
        },
    )


def memory_link_key(
    relation: str,
    source_type: str,
    source_ref: str,
    target_type: str,
    target_memory_id: str,
) -> str:
    return _identity_payload(
        "memory_link",
        {
            "relation": relation,
            "source_type": source_type,
            "source_ref": source_ref,
            "target_type": target_type,
            "target": target_memory_id,
        },
    )


def _identity_values(prefix: str, canonical_key: str) -> dict[str, str]:
    dedupe_key = dedupe_for(canonical_key)
    return {
        "memory_id": stable_id(prefix, dedupe_key),
        "canonical_key": canonical_key,
        "dedupe_key": dedupe_key,
    }


def build_question_card(
    *,
    canonical_question: str,
    scope: ObjectScope,
    semantic_intent: str,
    research_status: ResearchStatus,
    view: QuestionView,
    original_source: Literal["user", "human_review", "slice", "system_gap"],
    status: MemoryStatus,
    created_at: datetime,
    updated_at: datetime,
    source_refs: list[SourceRef],
    provenance_refs: list[ProvenanceRef],
    external_qc_id: str | None = None,
    aliases: list[str] | None = None,
    needs_data: list[str] | None = None,
    time_scope: TimeScope | None = None,
    external_debt_ref: str | None = None,
    debt_ref_status: DebtRefStatus = "not_required",
) -> QuestionCard:
    actual_needs = normalize_many(needs_data or [])
    actual_time = time_scope or TimeScope()
    key = question_card_key(
        external_qc_id=external_qc_id,
        scope=scope,
        semantic_intent=semantic_intent,
        view=view,
        needs_data=actual_needs,
        time_scope=actual_time,
    )
    return QuestionCard(
        **_identity_values("MEM-QC", key),
        external_qc_id=external_qc_id,
        canonical_question=canonical_question,
        aliases=aliases or [],
        scope=scope,
        semantic_intent=semantic_intent,
        time_scope=actual_time,
        needs_data=actual_needs,
        research_status=research_status,
        view=view,
        original_source=original_source,
        external_debt_ref=external_debt_ref,
        debt_ref_status=debt_ref_status,
        status=status,
        created_at=created_at,
        updated_at=updated_at,
        source_refs=source_refs,
        provenance_refs=provenance_refs,
    )


def build_data_debt_card(
    *,
    gap_id: str,
    gap_summary: str,
    scope: ObjectScope,
    required_fields: list[str],
    debt_ref_status: Literal["assigned", "needs_assignment"],
    status: MemoryStatus,
    created_at: datetime,
    updated_at: datetime,
    source_refs: list[SourceRef],
    provenance_refs: list[ProvenanceRef],
    external_debt_ref: str | None = None,
    time_scope: TimeScope | None = None,
) -> DataDebtCard:
    actual_fields = normalize_many(required_fields)
    actual_time = time_scope or TimeScope()
    key = data_debt_key(gap_id, scope, actual_fields, actual_time)
    return DataDebtCard(
        **_identity_values("MEM-DD", key),
        gap_id=gap_id,
        gap_summary=gap_summary,
        scope=scope,
        time_scope=actual_time,
        required_fields=actual_fields,
        external_debt_ref=external_debt_ref,
        debt_ref_status=debt_ref_status,
        status=status,
        created_at=created_at,
        updated_at=updated_at,
        source_refs=source_refs,
        provenance_refs=provenance_refs,
    )


def build_query_template_record(
    *,
    template_id: str,
    definition_version: str,
    question_pattern: str,
    parameter_semantics: list[str],
    outcome_semantics: list[str],
    caveats: list[str],
    status: MemoryStatus,
    created_at: datetime,
    updated_at: datetime,
    source_refs: list[SourceRef],
    provenance_refs: list[ProvenanceRef],
    executor_ref: ExecutorRef | None = None,
    executable: bool = False,
) -> QueryTemplateRecord:
    key = query_template_key(template_id, definition_version)
    return QueryTemplateRecord(
        **_identity_values("MEM-QT", key),
        template_id=template_id,
        definition_version=definition_version,
        question_pattern=question_pattern,
        parameter_semantics=parameter_semantics,
        outcome_semantics=outcome_semantics,
        caveats=caveats,
        executor_ref=executor_ref,
        executable=executable,
        status=status,
        created_at=created_at,
        updated_at=updated_at,
        source_refs=source_refs,
        provenance_refs=provenance_refs,
    )


def build_review_item(
    *,
    review_kind: Literal[
        "question_acceptance", "data_debt_assignment", "dedupe_resolution", "template_review"
    ],
    target_type: Literal["question_card", "data_debt", "query_template"],
    target_memory_id: str,
    status: MemoryStatus,
    created_at: datetime,
    updated_at: datetime,
    source_refs: list[SourceRef],
    provenance_refs: list[ProvenanceRef],
    priority: int = 0,
    active: bool = True,
) -> ReviewItem:
    key = review_item_key(review_kind, target_type, target_memory_id)
    return ReviewItem(
        **_identity_values("MEM-RV", key),
        review_kind=review_kind,
        target_type=target_type,
        target_memory_id=target_memory_id,
        priority=priority,
        active=active,
        status=status,
        created_at=created_at,
        updated_at=updated_at,
        source_refs=source_refs,
        provenance_refs=provenance_refs,
    )


def build_feedback_event(
    *,
    feedback_kind: Literal["useful", "inaccurate", "missing_data", "missing_context", "other"],
    target_type: Literal["answer_card", "research_response", "question_card"],
    target_ref: str,
    status: MemoryStatus,
    created_at: datetime,
    updated_at: datetime,
    source_refs: list[SourceRef],
    provenance_refs: list[ProvenanceRef],
    feedback_text: str | None = None,
) -> FeedbackEvent:
    key = feedback_event_key(feedback_kind, target_type, target_ref, created_at)
    return FeedbackEvent(
        **_identity_values("MEM-FB", key),
        feedback_kind=feedback_kind,
        target_type=target_type,
        target_ref=target_ref,
        feedback_text=feedback_text,
        status=status,
        created_at=created_at,
        updated_at=updated_at,
        source_refs=source_refs,
        provenance_refs=provenance_refs,
    )


def build_memory_link(
    *,
    relation: Literal[
        "derived_from", "alias_of", "review_of", "feedback_on", "merged_into", "sedimented_from"
    ],
    source_type: SourceType,
    source_ref: str,
    target_type: Literal[
        "question_card", "data_debt", "query_template", "review_item", "feedback_event"
    ],
    target_memory_id: str,
    status: MemoryStatus,
    created_at: datetime,
    updated_at: datetime,
    source_refs: list[SourceRef],
    provenance_refs: list[ProvenanceRef],
) -> MemoryLink:
    key = memory_link_key(relation, source_type, source_ref, target_type, target_memory_id)
    dedupe_key = dedupe_for(key)
    return MemoryLink(
        link_id=stable_id("MEM-LK", dedupe_key),
        canonical_key=key,
        dedupe_key=dedupe_key,
        relation=relation,
        source_type=source_type,
        source_ref=source_ref,
        target_type=target_type,
        target_memory_id=target_memory_id,
        status=status,
        created_at=created_at,
        updated_at=updated_at,
        source_refs=source_refs,
        provenance_refs=provenance_refs,
    )


def public_contract_schema() -> dict[str, Any]:
    models = {
        "ResearchRunRef": ResearchRunRef,
        "QuestionCard": QuestionCard,
        "DataDebtCard": DataDebtCard,
        "QueryTemplateRecord": QueryTemplateRecord,
        "ReviewItem": ReviewItem,
        "FeedbackEvent": FeedbackEvent,
        "MemoryLink": MemoryLink,
        "StatusTransition": StatusTransition,
        "SedimentationResult": SedimentationResult,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": RESEARCH_MEMORY_CONTRACT_VERSION,
        "title": "v8 Research Memory Contract v0",
        "type": "object",
        "$defs": {name: TypeAdapter(model).json_schema() for name, model in models.items()},
    }


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
