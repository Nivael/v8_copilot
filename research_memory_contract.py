"""D-053 Research Memory contract and deterministic identity construction.

This module defines serialization contracts only. It has no persistence or research-source
write capability.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from enum import Enum
from hashlib import sha256
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator


RESEARCH_MEMORY_CONTRACT_VERSION = "v8_research_memory_contract_v0"
QUESTION_SEMANTIC_REGISTRY_VERSION = "v8_question_semantic_registry_v0"
PROVISIONAL_QUESTION_IDENTITY_VERSION = "v8_provisional_question_identity_v0"
PROVISIONAL_QUESTION_NORMALIZATION_VERSION = "nfkc-whitespace-casefold-v1"
REVIEW_ACTIVE_LIMIT = 20

MemoryStatus = Literal["candidate", "accepted", "ignored", "merged", "blocked", "closed"]
ResearchStatus = Literal["answerable", "needs_data", "needs_review"]
QuestionView = Literal["evidence", "query", "checklist", "methodology", "data_debt"]
DebtRefStatus = Literal["assigned", "needs_assignment", "not_required"]
QuestionOriginalSource = Literal[
    "user", "human_review", "slice", "system_gap", "post_v7_backlog"
]
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
MemoryObjectType = Literal[
    "question_card", "data_debt", "query_template", "review_item", "feedback_event"
]


class QuestionIntent(str, Enum):
    ST_STATUS_REASON_AND_KEY_NODES = "st_status_reason_and_key_nodes"
    HISTORICAL_CASE_SIMILARITY = "historical_case_similarity"
    LENS_APPLICABILITY_AND_STANDING = "lens_applicability_and_standing"
    STOCK_EVENT_MULTI_DIMENSION_WINDOW = "stock_event_multi_dimension_window"
    LENS_EVIDENCE_AUDIT = "lens_evidence_audit"
    ST_SHAREHOLDER_COUNT_CHANGE = "st_shareholder_count_change"
    ST_ANNOUNCEMENT_DENSITY = "st_announcement_density"
    STOCK_EVENT_DATA_SUMMARY = "stock_event_data_summary"
    RESTRUCTURING_STAGE_TIMING = "restructuring_stage_timing"
    RESTRUCTURING_RECRUITMENT_NEXT_NODE_TIMING = (
        "restructuring_recruitment_next_node_timing"
    )
    RESTRUCTURING_PATH_ISOLATION = "restructuring_path_isolation"
    ST_MICROCAP_TWO_WEEK_DISTRIBUTION = "st_microcap_two_week_distribution"
    ST_MARKET_RELATIVE_TWO_WEEK_DISTRIBUTION = (
        "st_market_relative_two_week_distribution"
    )
    STOCK_OBSERVATION_WINDOWS = "stock_observation_windows"
    STOCK_EVENT_WINDOW = "stock_event_window"
    EVENT_WINDOW = "event_window"
    UNKNOWN_RESEARCH_QUESTION = "unknown_research_question"


class QuestionDimension(str, Enum):
    ST_STATUS = "st_status"
    ANNOUNCEMENT = "announcement"
    EPISODE = "episode"
    EPISODE_SEQUENCE = "episode_sequence"
    EVENT_TYPE = "event_type"
    PRICE_PATH = "price_path"
    LENS_KIND = "lens_kind"
    VALIDATION_STATUS = "validation_status"
    REJECTED_BOUNDARY = "rejected_boundary"
    PRICE = "price"
    SHARE_CAPITAL = "share_capital"
    SHAREHOLDER_COUNT = "shareholder_count"
    REGULATORY_ACTION = "regulatory_action"
    EVIDENCE_GRADE = "evidence_grade"
    SAMPLE_N = "sample_n"
    COUNTEREXAMPLE = "counterexample"
    DATA_GAP = "data_gap"
    ANNOUNCEMENT_DENSITY = "announcement_density"
    MULTI_TABLE_SUMMARY = "multi_table_summary"
    EPISODE_TRANSITION = "episode_transition"
    ELAPSED_DAYS = "elapsed_days"
    NEXT_ANNOUNCEMENT = "next_announcement"
    STAGE = "stage"
    PROVINCE = "province"
    OUT_OF_COURT = "out_of_court"
    IN_COURT = "in_court"
    MARKET_CAP_COHORT = "market_cap_cohort"
    TWO_WEEK_RETURN = "two_week_return"
    MARKET_INDEX = "market_index"
    TWO_WEEK_EXCESS_RETURN = "two_week_excess_return"


QUESTION_INTENT_ALIASES: dict[str, QuestionIntent] = {
    "stock_monitoring_windows": QuestionIntent.STOCK_OBSERVATION_WINDOWS,
    "stock_watch_windows": QuestionIntent.STOCK_OBSERVATION_WINDOWS,
}
QUESTION_DIMENSION_ALIASES: dict[str, QuestionDimension] = {
    "daily_price": QuestionDimension.PRICE,
    "daily_prices": QuestionDimension.PRICE,
    "episode_index": QuestionDimension.EPISODE,
    "announcements": QuestionDimension.ANNOUNCEMENT,
}


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


def canonical_question_intent(value: str | QuestionIntent) -> QuestionIntent:
    token = normalize_token(value.value if isinstance(value, QuestionIntent) else value)
    if token in QUESTION_INTENT_ALIASES:
        return QUESTION_INTENT_ALIASES[token]
    try:
        return QuestionIntent(token)
    except ValueError as exc:
        raise ValueError(
            f"unknown question intent for {QUESTION_SEMANTIC_REGISTRY_VERSION}: {token}"
        ) from exc


def canonical_question_dimensions(
    values: list[str | QuestionDimension],
) -> list[QuestionDimension]:
    canonical: set[QuestionDimension] = set()
    for value in values:
        token = normalize_token(
            value.value if isinstance(value, QuestionDimension) else value
        )
        if token in QUESTION_DIMENSION_ALIASES:
            canonical.add(QUESTION_DIMENSION_ALIASES[token])
            continue
        try:
            canonical.add(QuestionDimension(token))
        except ValueError as exc:
            raise ValueError(
                "unknown question dimension for "
                f"{QUESTION_SEMANTIC_REGISTRY_VERSION}: {token}"
            ) from exc
    return sorted(canonical, key=lambda item: item.value)


def provisional_question_fingerprint(question: str) -> str:
    normalized = normalize_token(question)
    if not normalized:
        raise ValueError("provisional question requires non-empty normalized text")
    payload = canonical_json(
        {
            "identity_version": PROVISIONAL_QUESTION_IDENTITY_VERSION,
            "normalization_version": PROVISIONAL_QUESTION_NORMALIZATION_VERSION,
            "normalized_question": normalized,
        }
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def normalize_many(values: list[str], *, symbols: bool = False) -> list[str]:
    normalizer = normalize_symbol if symbols else normalize_token
    return sorted({normalizer(value) for value in values if normalize_text(value)})


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_scope(kind: ObjectKind, refs: list[str]) -> dict[str, Any]:
    normalized = normalize_many(refs, symbols=kind in {"stock", "stock_event"})
    if not normalized:
        raise ValueError("scope requires at least one non-empty ref")
    return {"kind": kind, "refs": normalized}


def canonical_key(kind: str, **parts: Any) -> str:
    return canonical_json({"kind": normalize_token(kind), **parts})


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
    def canonical(self) -> dict[str, Any]:
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
    def canonical(self) -> dict[str, Any]:
        parts: dict[str, Any] = {"semantics": self.semantics}
        if self.start is not None:
            parts["start"] = normalize_token(self.start)
        if self.end is not None:
            parts["end"] = normalize_token(self.end)
        if self.before is not None:
            parts["before"] = self.before
        if self.after is not None:
            parts["after"] = self.after
        return parts


class ProvisionalQuestionIdentity(StrictModel):
    identity_version: Literal[PROVISIONAL_QUESTION_IDENTITY_VERSION]
    normalization_version: Literal[PROVISIONAL_QUESTION_NORMALIZATION_VERSION]
    question_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


def build_provisional_question_identity(question: str) -> ProvisionalQuestionIdentity:
    return ProvisionalQuestionIdentity(
        identity_version=PROVISIONAL_QUESTION_IDENTITY_VERSION,
        normalization_version=PROVISIONAL_QUESTION_NORMALIZATION_VERSION,
        question_fingerprint=provisional_question_fingerprint(question),
    )


class SourceRef(StrictModel):
    source_type: SourceType
    source_ref: str = Field(min_length=1, max_length=1000)
    source_alias: str | None = Field(default=None, max_length=4000)


class ProvenanceRef(StrictModel):
    provenance_type: ProvenanceType
    provenance_ref: str = Field(min_length=1, max_length=1000)


class AuditFields(StrictModel):
    contract_version: Literal[RESEARCH_MEMORY_CONTRACT_VERSION]
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


class MemoryEntity(AuditFields):
    memory_id: str = Field(min_length=1, max_length=128)
    canonical_key: str = Field(min_length=1, max_length=4000)
    dedupe_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    not_evidence: Literal[True]


class ResearchRouteRef(StrictModel):
    route: str = Field(min_length=1, max_length=128)
    status: str = Field(min_length=1, max_length=128)
    view: str = Field(min_length=1, max_length=128)


class ResearchRunRef(StrictModel):
    """Non-knowledge source identity. It is never used in target entity dedupe."""

    record_type: Literal["research_run_ref"]
    contract_version: Literal[RESEARCH_MEMORY_CONTRACT_VERSION]
    run_id: str = Field(min_length=1, max_length=256)
    request_id: str = Field(min_length=1, max_length=256)
    research_response_id: str = Field(min_length=1, max_length=256)
    answer_card_id: str | None = Field(default=None, max_length=256)
    request_contract_version: str = Field(min_length=1, max_length=128)
    response_contract_version: str = Field(min_length=1, max_length=128)
    answer_contract_version: str | None = Field(default=None, max_length=128)
    route: ResearchRouteRef
    snapshot_as_of: datetime
    snapshot_refs: list[ProvenanceRef] = Field(min_length=1, max_length=100)
    content_digest_algorithm: Literal["sha256-canonical-json-v1"]
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    content_summary: str = Field(min_length=1, max_length=2000)
    created_at: datetime

    _snapshot_as_of_aware = field_validator("snapshot_as_of")(_aware)
    _created_at_aware = field_validator("created_at")(_aware)

    @model_validator(mode="after")
    def validate_answer_identity(self) -> "ResearchRunRef":
        if bool(self.answer_card_id) != bool(self.answer_contract_version):
            raise ValueError(
                "answer_card_id and answer_contract_version must be present together"
            )
        return self


class QuestionCard(MemoryEntity):
    record_type: Literal["question_card"]
    external_qc_id: str | None = Field(default=None, pattern=r"^QC-(?:[0-9]{8}-[0-9]{3}|CAND-[a-f0-9]{12})$")
    canonical_question: str = Field(min_length=1, max_length=4000)
    aliases: list[str] = Field(default_factory=list, max_length=100)
    scope: ObjectScope
    identity_kind: Literal["semantic", "provisional_unknown"]
    provisional_identity: ProvisionalQuestionIdentity | None = None
    semantic_registry_version: Literal[QUESTION_SEMANTIC_REGISTRY_VERSION]
    semantic_intent: QuestionIntent
    dimensions: list[QuestionDimension] = Field(max_length=50)
    time_scope: TimeScope
    needs_data: list[str] = Field(max_length=50)
    research_status: ResearchStatus
    view: QuestionView
    original_source: QuestionOriginalSource
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

    @field_validator("dimensions")
    @classmethod
    def normalize_dimensions(
        cls, value: list[QuestionDimension]
    ) -> list[QuestionDimension]:
        return sorted(set(value), key=lambda item: item.value)

    @field_validator("needs_data")
    @classmethod
    def normalize_needs_data(cls, value: list[str]) -> list[str]:
        return normalize_many(value)

    @field_validator("external_debt_ref")
    @classmethod
    def normalize_external_debt_ref(cls, value: str | None) -> str | None:
        return normalize_text(value).upper() if value else None

    @model_validator(mode="after")
    def validate_identity_and_debt(self) -> "QuestionCard":
        expected = question_card_key(
            scope=self.scope,
            identity_kind=self.identity_kind,
            provisional_identity=self.provisional_identity,
            semantic_registry_version=self.semantic_registry_version,
            semantic_intent=self.semantic_intent,
            dimensions=self.dimensions,
            time_scope=self.time_scope,
        )
        _validate_identity(self, expected, "MEM-QC")
        is_unknown = self.semantic_intent == QuestionIntent.UNKNOWN_RESEARCH_QUESTION
        if is_unknown:
            if self.identity_kind != "provisional_unknown" or not self.provisional_identity:
                raise ValueError("unknown question requires provisional_unknown identity")
            expected_fingerprint = provisional_question_fingerprint(
                self.canonical_question
            )
            if self.provisional_identity.question_fingerprint != expected_fingerprint:
                raise ValueError(
                    "provisional question fingerprint does not match canonical question"
                )
            if self.dimensions:
                raise ValueError("provisional unknown question cannot carry dimensions")
            if self.status not in {"candidate", "merged"} or self.research_status != "needs_review":
                raise ValueError(
                    "provisional unknown question must remain needs_review and may only "
                    "be candidate or human-merged"
                )
            if self.debt_ref_status != "not_required" or self.external_debt_ref:
                raise ValueError("provisional unknown question cannot bind data debt")
        elif self.identity_kind != "semantic" or self.provisional_identity is not None:
            raise ValueError(
                "classified question must use semantic identity without provisional fields"
            )
        if self.external_qc_id and not self.external_qc_id.startswith("QC-CAND-"):
            if not any(ref.source_type == "seed_fixture" for ref in self.source_refs):
                raise ValueError("fixed QC identity requires a seed_fixture source")
            if not any(
                ref.provenance_type == "seed_fixture" for ref in self.provenance_refs
            ):
                raise ValueError("fixed QC identity requires seed_fixture provenance")
        if self.original_source == "post_v7_backlog" and not any(
            ref.source_type == "post_v7_backlog" for ref in self.source_refs
        ):
            raise ValueError(
                "post_v7_backlog original_source requires a matching source ref"
            )
        if self.external_debt_ref and self.debt_ref_status != "assigned":
            raise ValueError("external_debt_ref requires debt_ref_status=assigned")
        if self.debt_ref_status == "assigned" and not self.external_debt_ref:
            raise ValueError("assigned debt_ref_status requires external_debt_ref")
        if self.research_status != "needs_data" and self.debt_ref_status != "not_required":
            raise ValueError("only needs_data questions may require debt assignment")
        return self


class DataDebtCard(MemoryEntity):
    record_type: Literal["data_debt"]
    gap_id: str = Field(min_length=1, max_length=256)
    gap_summary: str = Field(min_length=1, max_length=4000)
    scope: ObjectScope
    time_scope: TimeScope
    missing_assets: list[str] = Field(min_length=1, max_length=100)
    missing_fields: list[str] = Field(min_length=1, max_length=100)
    blocked_question_card_refs: list[str] = Field(max_length=100)
    owner: str = Field(min_length=1, max_length=256)
    external_debt_ref: str | None = Field(default=None, max_length=128)
    debt_ref_status: Literal["assigned", "needs_assignment"]

    @field_validator("missing_assets", "missing_fields", "blocked_question_card_refs")
    @classmethod
    def normalize_semantic_lists(cls, value: list[str]) -> list[str]:
        return normalize_many(value)

    @field_validator("external_debt_ref")
    @classmethod
    def normalize_external_debt_ref(cls, value: str | None) -> str | None:
        return normalize_text(value).upper() if value else None

    @model_validator(mode="after")
    def validate_identity_and_ref(self) -> "DataDebtCard":
        expected = data_debt_key(
            debt_ref_status=self.debt_ref_status,
            external_debt_ref=self.external_debt_ref,
            scope=self.scope,
            missing_assets=self.missing_assets,
            missing_fields=self.missing_fields,
        )
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

    @property
    def canonical(self) -> dict[str, str]:
        return {
            "registry_contract_version": normalize_token(self.registry_contract_version),
            "template_id": normalize_token(self.template_id),
            "executor_key": normalize_token(self.executor_key),
        }


class QueryParameterSpec(StrictModel):
    name: str = Field(min_length=1, max_length=128)
    value_type: Literal["string", "integer", "number", "boolean", "date", "string_list"]
    required: bool = True
    allowed_values: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return normalize_token(value)

    @field_validator("allowed_values")
    @classmethod
    def normalize_allowed_values(cls, value: list[str]) -> list[str]:
        return normalize_many(value)

    @property
    def canonical(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class QueryTemplateRecord(MemoryEntity):
    record_type: Literal["query_template"]
    template_id: str = Field(pattern=r"^QT-[0-9]{3}$")
    definition_version: str = Field(min_length=1, max_length=128)
    question_pattern: str = Field(min_length=1, max_length=1000)
    parameter_schema: list[QueryParameterSpec] = Field(min_length=1, max_length=50)
    outcome_semantics: list[str] = Field(min_length=1, max_length=50)
    caveats: list[str] = Field(min_length=1, max_length=50)
    executor_ref: ExecutorRef | None = None
    proposed_executor_ref: str | None = Field(default=None, max_length=256)
    executable: bool

    @field_validator("outcome_semantics", "caveats")
    @classmethod
    def normalize_semantics(cls, value: list[str]) -> list[str]:
        return normalize_many(value)

    @field_validator("parameter_schema")
    @classmethod
    def normalize_parameter_schema(
        cls, value: list[QueryParameterSpec]
    ) -> list[QueryParameterSpec]:
        by_name: dict[str, QueryParameterSpec] = {}
        for parameter in value:
            if parameter.name in by_name and by_name[parameter.name] != parameter:
                raise ValueError(f"conflicting parameter schema for {parameter.name}")
            by_name[parameter.name] = parameter
        return [by_name[name] for name in sorted(by_name)]

    @model_validator(mode="after")
    def validate_template_boundary(self) -> "QueryTemplateRecord":
        expected = query_template_key(
            executor_ref=self.executor_ref,
            proposed_executor_ref=self.proposed_executor_ref,
            parameter_schema=self.parameter_schema,
            outcome_semantics=self.outcome_semantics,
        )
        _validate_identity(self, expected, "MEM-QT")
        if self.executable and self.executor_ref is None:
            raise ValueError("executable template requires a versioned executor_ref")
        if self.executor_ref and self.executor_ref.template_id != self.template_id:
            raise ValueError("executor_ref template_id must match the record")
        if bool(self.executor_ref) == bool(self.proposed_executor_ref):
            raise ValueError(
                "provide exactly one of executor_ref or proposed_executor_ref"
            )
        if self.status == "candidate" and self.executable:
            raise ValueError("draft candidate templates cannot be executable")
        if self.status == "candidate" and not self.proposed_executor_ref:
            raise ValueError("draft candidate requires proposed_executor_ref")
        if self.status != "candidate" and self.proposed_executor_ref:
            raise ValueError("only candidate templates may use proposed_executor_ref")
        return self


class ReviewSubjectRef(StrictModel):
    subject_type: Literal[
        "question_card", "data_debt", "query_template", "dedupe_pair", "feedback_event"
    ]
    subject_id: str = Field(min_length=1, max_length=256)

    @property
    def canonical(self) -> dict[str, str]:
        return {
            "subject_type": self.subject_type,
            "subject_id": normalize_token(self.subject_id),
        }


class ReviewItem(MemoryEntity):
    record_type: Literal["review_item"]
    uncertainty_type: str = Field(min_length=1, max_length=256)
    subject_ref: ReviewSubjectRef
    decision_unit: str = Field(min_length=1, max_length=256)
    evidence_package_refs: list[ProvenanceRef] = Field(min_length=1, max_length=100)
    recommended_action: Literal[
        "accept_candidate",
        "ignore_candidate",
        "assign_data_debt",
        "merge_after_review",
        "request_more_evidence",
        "review_template",
    ]
    priority: int = Field(default=0, ge=0, le=100)
    active: bool = True

    @model_validator(mode="after")
    def validate_review_identity(self) -> "ReviewItem":
        expected = review_item_key(
            self.uncertainty_type, self.subject_ref, self.decision_unit
        )
        _validate_identity(self, expected, "MEM-RV")
        if self.status in {"ignored", "merged", "closed"} and self.active:
            raise ValueError("terminal review items cannot remain active")
        return self


class FeedbackEvent(MemoryEntity):
    record_type: Literal["feedback_event"]
    feedback_kind: Literal[
        "useful",
        "not_useful",
        "scope_error",
        "missing_evidence",
        "wording_issue",
        "other",
    ]
    target_type: Literal[
        "research_run", "answer_card", "research_response", "question_card"
    ]
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
    record_type: Literal["memory_link"]
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
    not_evidence: Literal[True]

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
    record_type: Literal["status_transition"]
    object_type: MemoryObjectType
    from_status: MemoryStatus
    to_status: MemoryStatus
    actor_type: Literal["system", "human", "migration", "llm"]
    context: Literal["online", "seed_bootstrap", "maintenance"]
    reason: str = Field(min_length=1, max_length=2000)
    merge_target_id: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def validate_transition(self) -> "StatusTransition":
        allowed = STATUS_TRANSITIONS[self.from_status]
        if self.to_status not in allowed:
            raise ValueError(f"illegal transition: {self.from_status} -> {self.to_status}")
        if self.actor_type == "llm":
            raise ValueError("LLM cannot perform lifecycle transitions")
        if self.from_status == "candidate" and self.to_status in {"accepted", "ignored"}:
            if self.to_status == "accepted" and self.actor_type not in {"human", "migration"}:
                raise ValueError("candidate acceptance requires human or migration actor")
            if self.to_status == "ignored" and self.actor_type != "human":
                raise ValueError("candidate ignore requires human actor")
        if self.actor_type == "migration" and not (
            self.context == "seed_bootstrap"
            and self.from_status == "candidate"
            and self.to_status == "accepted"
        ):
            raise ValueError("migration actor is limited to seed bootstrap acceptance")
        if self.context == "seed_bootstrap" and self.actor_type != "migration":
            raise ValueError("seed_bootstrap context requires migration actor")
        if self.to_status == "merged":
            if self.actor_type != "human" or not self.merge_target_id:
                raise ValueError("merge requires a human actor and explicit merge target")
        elif self.merge_target_id:
            raise ValueError("merge_target_id is only valid for merged transitions")
        return self


STATUS_TRANSITIONS: dict[MemoryStatus, tuple[MemoryStatus, ...]] = {
    "candidate": ("accepted", "ignored", "merged", "blocked", "closed"),
    "accepted": ("blocked", "merged", "closed"),
    "blocked": ("candidate", "accepted", "closed"),
    "ignored": ("candidate", "closed"),
    "merged": (),
    "closed": (),
}


class SedimentationResult(StrictModel):
    """Non-persistent result of a future repository operation."""

    record_type: Literal["sedimentation_result"]
    contract_version: Literal[RESEARCH_MEMORY_CONTRACT_VERSION]
    operation_id: str = Field(min_length=1, max_length=256)
    created: list["MemoryObjectRef"] = Field(max_length=1000)
    existing: list["MemoryObjectRef"] = Field(max_length=1000)
    merged: list["MergeDisposition"] = Field(max_length=1000)
    ignored: list["IgnoredDisposition"] = Field(max_length=1000)
    created_links: list[MemoryLink] = Field(max_length=5000)
    completed_at: datetime

    _completed_at_aware = field_validator("completed_at")(_aware)

    @model_validator(mode="after")
    def validate_partition(self) -> "SedimentationResult":
        partition_ids = [
            {item.memory_id for item in self.created},
            {item.memory_id for item in self.existing},
            {item.object_ref.memory_id for item in self.ignored},
            {item.source.memory_id for item in self.merged},
        ]
        seen: set[str] = set()
        for ids in partition_ids:
            if seen & ids:
                raise ValueError("sedimentation result partitions must be disjoint")
            seen.update(ids)
        return self


class MemoryObjectRef(StrictModel):
    object_type: MemoryObjectType
    memory_id: str = Field(min_length=1, max_length=128)
    dedupe_key: str = Field(pattern=r"^[a-f0-9]{64}$")


class MergeDisposition(StrictModel):
    source: MemoryObjectRef
    target: MemoryObjectRef
    review_item_id: str = Field(min_length=1, max_length=128)


class IgnoredDisposition(StrictModel):
    object_ref: MemoryObjectRef
    reason: str = Field(min_length=1, max_length=2000)


SedimentationResult.model_rebuild()


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
    scope: ObjectScope,
    identity_kind: Literal["semantic", "provisional_unknown"],
    provisional_identity: ProvisionalQuestionIdentity | None,
    semantic_registry_version: str,
    semantic_intent: QuestionIntent,
    dimensions: list[QuestionDimension],
    time_scope: TimeScope,
) -> str:
    if identity_kind == "provisional_unknown":
        if provisional_identity is None:
            raise ValueError("provisional unknown key requires provisional identity")
        return canonical_key(
            "provisional_question",
            identity_version=provisional_identity.identity_version,
            normalization_version=provisional_identity.normalization_version,
            object_scope=scope.canonical,
            question_fingerprint=provisional_identity.question_fingerprint,
            time_scope_semantics=time_scope.canonical,
        )
    if provisional_identity is not None:
        raise ValueError("semantic question key cannot carry provisional identity")
    return canonical_key(
        "question_card",
        semantic_registry_version=semantic_registry_version,
        object_scope=scope.canonical,
        intent=semantic_intent.value,
        dimensions=[item.value for item in dimensions],
        time_scope_semantics=time_scope.canonical,
    )


def data_debt_key(
    *,
    debt_ref_status: Literal["assigned", "needs_assignment"],
    external_debt_ref: str | None,
    scope: ObjectScope,
    missing_assets: list[str],
    missing_fields: list[str],
) -> str:
    if debt_ref_status == "assigned":
        if not external_debt_ref:
            raise ValueError("assigned data debt key requires external_debt_ref")
        return canonical_key(
            "data_debt", debt_ref=normalize_text(external_debt_ref).upper()
        )
    return canonical_key(
        "data_debt",
        object_scope=scope.canonical,
        missing_assets=normalize_many(missing_assets),
        missing_fields=normalize_many(missing_fields),
    )


def query_template_key(
    *,
    executor_ref: ExecutorRef | None,
    proposed_executor_ref: str | None,
    parameter_schema: list[QueryParameterSpec],
    outcome_semantics: list[str],
) -> str:
    executor_identity: dict[str, Any]
    if executor_ref:
        executor_identity = {"registry": executor_ref.canonical}
    elif proposed_executor_ref:
        executor_identity = {"proposed": normalize_token(proposed_executor_ref)}
    else:
        raise ValueError("query template key requires executor identity")
    return canonical_key(
        "query_template",
        executor_ref=executor_identity,
        parameter_schema=[
            item.canonical for item in sorted(parameter_schema, key=lambda item: item.name)
        ],
        outcome_semantics=normalize_many(outcome_semantics),
    )


def review_item_key(
    uncertainty_type: str, subject_ref: ReviewSubjectRef, decision_unit: str
) -> str:
    return canonical_key(
        "review",
        uncertainty_type=normalize_token(uncertainty_type),
        subject_ref=subject_ref.canonical,
        decision_unit=normalize_token(decision_unit),
    )


def feedback_event_key(
    feedback_kind: str, target_type: str, target_ref: str, created_at: datetime
) -> str:
    return canonical_key(
        "feedback_event",
        feedback_kind=normalize_token(feedback_kind),
        target_type=normalize_token(target_type),
        target=normalize_token(target_ref),
        occurred_at=created_at.isoformat(),
    )


def memory_link_key(
    relation: str,
    source_type: str,
    source_ref: str,
    target_type: str,
    target_memory_id: str,
) -> str:
    return canonical_key(
        "memory_link",
        relation=normalize_token(relation),
        source_type=normalize_token(source_type),
        source_ref=normalize_token(source_ref),
        target_type=normalize_token(target_type),
        target=normalize_token(target_memory_id),
    )


def _identity_values(prefix: str, canonical_key: str) -> dict[str, Any]:
    dedupe_key = dedupe_for(canonical_key)
    return {
        "memory_id": stable_id(prefix, dedupe_key),
        "canonical_key": canonical_key,
        "dedupe_key": dedupe_key,
        "contract_version": RESEARCH_MEMORY_CONTRACT_VERSION,
        "not_evidence": True,
    }


def build_question_card(
    *,
    canonical_question: str,
    scope: ObjectScope,
    semantic_intent: str | QuestionIntent,
    research_status: ResearchStatus,
    view: QuestionView,
    original_source: QuestionOriginalSource,
    status: MemoryStatus,
    created_at: datetime,
    updated_at: datetime,
    source_refs: list[SourceRef],
    provenance_refs: list[ProvenanceRef],
    external_qc_id: str | None = None,
    aliases: list[str] | None = None,
    semantic_registry_version: str = QUESTION_SEMANTIC_REGISTRY_VERSION,
    dimensions: list[str | QuestionDimension] | None = None,
    needs_data: list[str] | None = None,
    time_scope: TimeScope | None = None,
    external_debt_ref: str | None = None,
    debt_ref_status: DebtRefStatus = "not_required",
) -> QuestionCard:
    if semantic_registry_version != QUESTION_SEMANTIC_REGISTRY_VERSION:
        raise ValueError(
            f"unsupported question semantic registry: {semantic_registry_version}"
        )
    actual_needs = normalize_many(needs_data or [])
    actual_intent = canonical_question_intent(semantic_intent)
    actual_dimensions = canonical_question_dimensions(dimensions or [])
    actual_time = time_scope or TimeScope()
    is_unknown = actual_intent == QuestionIntent.UNKNOWN_RESEARCH_QUESTION
    if is_unknown:
        if actual_dimensions:
            raise ValueError("provisional unknown question cannot carry dimensions")
        if status != "candidate" or research_status != "needs_review":
            raise ValueError(
                "provisional unknown question must remain candidate and needs_review"
            )
        if debt_ref_status != "not_required" or external_debt_ref:
            raise ValueError("provisional unknown question cannot bind data debt")
        identity_kind: Literal["semantic", "provisional_unknown"] = (
            "provisional_unknown"
        )
        provisional_identity = build_provisional_question_identity(canonical_question)
    else:
        identity_kind = "semantic"
        provisional_identity = None
    key = question_card_key(
        scope=scope,
        identity_kind=identity_kind,
        provisional_identity=provisional_identity,
        semantic_registry_version=semantic_registry_version,
        semantic_intent=actual_intent,
        dimensions=actual_dimensions,
        time_scope=actual_time,
    )
    return QuestionCard(
        **_identity_values("MEM-QC", key),
        record_type="question_card",
        external_qc_id=external_qc_id,
        canonical_question=canonical_question,
        aliases=aliases or [],
        scope=scope,
        identity_kind=identity_kind,
        provisional_identity=provisional_identity,
        semantic_registry_version=semantic_registry_version,
        semantic_intent=actual_intent,
        dimensions=actual_dimensions,
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
    missing_assets: list[str],
    missing_fields: list[str],
    blocked_question_card_refs: list[str],
    owner: str,
    debt_ref_status: Literal["assigned", "needs_assignment"],
    status: MemoryStatus,
    created_at: datetime,
    updated_at: datetime,
    source_refs: list[SourceRef],
    provenance_refs: list[ProvenanceRef],
    external_debt_ref: str | None = None,
    time_scope: TimeScope | None = None,
) -> DataDebtCard:
    actual_assets = normalize_many(missing_assets)
    actual_fields = normalize_many(missing_fields)
    actual_time = time_scope or TimeScope()
    key = data_debt_key(
        debt_ref_status=debt_ref_status,
        external_debt_ref=external_debt_ref,
        scope=scope,
        missing_assets=actual_assets,
        missing_fields=actual_fields,
    )
    return DataDebtCard(
        **_identity_values("MEM-DD", key),
        record_type="data_debt",
        gap_id=gap_id,
        gap_summary=gap_summary,
        scope=scope,
        time_scope=actual_time,
        missing_assets=actual_assets,
        missing_fields=actual_fields,
        blocked_question_card_refs=blocked_question_card_refs,
        owner=owner,
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
    parameter_schema: list[QueryParameterSpec],
    outcome_semantics: list[str],
    caveats: list[str],
    status: MemoryStatus,
    created_at: datetime,
    updated_at: datetime,
    source_refs: list[SourceRef],
    provenance_refs: list[ProvenanceRef],
    executor_ref: ExecutorRef | None = None,
    proposed_executor_ref: str | None = None,
    executable: bool = False,
) -> QueryTemplateRecord:
    key = query_template_key(
        executor_ref=executor_ref,
        proposed_executor_ref=proposed_executor_ref,
        parameter_schema=parameter_schema,
        outcome_semantics=outcome_semantics,
    )
    return QueryTemplateRecord(
        **_identity_values("MEM-QT", key),
        record_type="query_template",
        template_id=template_id,
        definition_version=definition_version,
        question_pattern=question_pattern,
        parameter_schema=parameter_schema,
        outcome_semantics=outcome_semantics,
        caveats=caveats,
        executor_ref=executor_ref,
        proposed_executor_ref=proposed_executor_ref,
        executable=executable,
        status=status,
        created_at=created_at,
        updated_at=updated_at,
        source_refs=source_refs,
        provenance_refs=provenance_refs,
    )


def build_review_item(
    *,
    uncertainty_type: str,
    subject_ref: ReviewSubjectRef,
    decision_unit: str,
    evidence_package_refs: list[ProvenanceRef],
    recommended_action: Literal[
        "accept_candidate",
        "ignore_candidate",
        "assign_data_debt",
        "merge_after_review",
        "request_more_evidence",
        "review_template",
    ],
    status: MemoryStatus,
    created_at: datetime,
    updated_at: datetime,
    source_refs: list[SourceRef],
    provenance_refs: list[ProvenanceRef],
    priority: int = 0,
    active: bool = True,
) -> ReviewItem:
    key = review_item_key(uncertainty_type, subject_ref, decision_unit)
    return ReviewItem(
        **_identity_values("MEM-RV", key),
        record_type="review_item",
        uncertainty_type=uncertainty_type,
        subject_ref=subject_ref,
        decision_unit=decision_unit,
        evidence_package_refs=evidence_package_refs,
        recommended_action=recommended_action,
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
    feedback_kind: Literal[
        "useful",
        "not_useful",
        "scope_error",
        "missing_evidence",
        "wording_issue",
        "other",
    ],
    target_type: Literal[
        "research_run", "answer_card", "research_response", "question_card"
    ],
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
        record_type="feedback_event",
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
        record_type="memory_link",
        contract_version=RESEARCH_MEMORY_CONTRACT_VERSION,
        link_id=stable_id("MEM-LK", dedupe_key),
        canonical_key=key,
        dedupe_key=dedupe_key,
        relation=relation,
        source_type=source_type,
        source_ref=source_ref,
        target_type=target_type,
        target_memory_id=target_memory_id,
        not_evidence=True,
        status=status,
        created_at=created_at,
        updated_at=updated_at,
        source_refs=source_refs,
        provenance_refs=provenance_refs,
    )


PublicMemoryObject = Annotated[
    ResearchRunRef
    | QuestionCard
    | DataDebtCard
    | QueryTemplateRecord
    | ReviewItem
    | FeedbackEvent
    | MemoryLink
    | StatusTransition
    | SedimentationResult,
    Field(discriminator="record_type"),
]
PUBLIC_MEMORY_ADAPTER = TypeAdapter(PublicMemoryObject)


def public_contract_schema() -> dict[str, Any]:
    schema = PUBLIC_MEMORY_ADAPTER.json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = RESEARCH_MEMORY_CONTRACT_VERSION
    schema["title"] = "v8 Research Memory Contract v0"
    return schema
