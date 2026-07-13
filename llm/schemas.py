from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


RouteName = Literal[
    "answer_query",
    "answer_evidence",
    "answer_checklist",
    "answer_methodology",
    "data_debt",
    "clarify",
    "lens_gap",
    "needs_review",
    "refuse_or_rewrite",
]
ClaimType = Literal["fact", "inference", "caveat", "question", "data_gap"]
ComposerBackingKind = Literal[
    "query_row", "lens_invocation", "provenance_ref", "data_debt", "lens_gap",
]
ObjectKind = Literal[
    "stock",
    "stock_event",
    "episode_type",
    "cluster",
    "lens_cluster",
    "lens",
    "cohort",
    "universe",
    "unknown",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ParsedDateRange(StrictModel):
    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def valid_iso_date_or_empty(cls, value: str) -> str:
        if value:
            date.fromisoformat(value)
        return value


class ParsedQuestion(StrictModel):
    """Structured proposal from the LLM. The deterministic router is final."""

    normalized_question: str = Field(min_length=1)
    object_kind: ObjectKind
    object_ref: str = Field(min_length=1, max_length=256)
    intent: str = Field(min_length=1, max_length=128)
    time_range: ParsedDateRange
    dimensions: list[str] = Field(max_length=20)
    ambiguities: list[str] = Field(max_length=20)
    candidate_topics: list[str] = Field(max_length=20)
    proposed_route: RouteName
    compliant_rewrite: str

    @model_validator(mode="after")
    def date_range_is_consistent(self) -> "ParsedQuestion":
        if bool(self.time_range.start) != bool(self.time_range.end):
            raise ValueError("time_range.start/end 必须同时为空或同时有值")
        if self.time_range.start and self.time_range.start > self.time_range.end:
            raise ValueError("time_range.start 不得晚于 end")
        return self


class ClaimBacking(StrictModel):
    kind: ComposerBackingKind
    ref: str = Field(min_length=1, max_length=1000)


class NarrativeClaim(StrictModel):
    text: str = Field(min_length=1, max_length=800)
    claim_type: ClaimType
    backing: ClaimBacking


class NarrativeDraft(StrictModel):
    """The composer has no unvalidated free-text output channel."""

    claims: list[NarrativeClaim] = Field(max_length=24)
    narrative: "StructuredNarrativeDraft | None" = None


class StructuredNarrativeStatement(StrictModel):
    text: str = Field(min_length=1, max_length=4000)
    backing: list[ClaimBacking] = Field(min_length=1, max_length=10)


class StructuredNarrativeStep(StructuredNarrativeStatement):
    title: str = Field(min_length=1, max_length=200)


class StructuredNarrativeDraft(StrictModel):
    direct_answer: StructuredNarrativeStatement
    reasoning_steps: list[StructuredNarrativeStep] = Field(default_factory=list, max_length=12)
    uncertainties: list[StructuredNarrativeStatement] = Field(default_factory=list, max_length=12)
    watch_items: list[StructuredNarrativeStatement] = Field(default_factory=list, max_length=12)


class BackingEntry(StrictModel):
    kind: ComposerBackingKind
    ref: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=4000)


class FilteredAnswerCard(StrictModel):
    question: str
    object_ref: str
    view: str
    as_of: str
    sample_scope: str
    evidence_grade: str
    body_rows: list[dict[str, object]]
    caveats: list[str]
    data_debt_summary: list[str]
    lens_gap_summary: list[str]
