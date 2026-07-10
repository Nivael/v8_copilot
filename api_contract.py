"""Versioned public contract shared by W1 Core/API, W2 LLM, and W3 Web UI."""
from __future__ import annotations

from datetime import date as Date, datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator


API_CONTRACT_VERSION = "v8_copilot_api_contract_v0"

ObjectKind = Literal[
    "stock", "stock_event", "episode_type", "cluster", "lens_cluster",
    "lens", "cohort", "universe", "unknown",
]
LlmMode = Literal["off", "auto", "required"]
RouteName = Literal[
    "answer_query", "answer_evidence", "answer_checklist", "answer_methodology",
    "data_debt", "lens_gap", "needs_review", "clarify", "refuse_or_rewrite",
]
RouteStatus = Literal["answerable", "needs_data", "needs_review", "clarify", "boundary"]
RouteView = Literal[
    "query", "evidence", "checklist", "methodology", "data_debt",
    "lens_gap", "clarify", "boundary",
]
ClaimType = Literal["fact", "inference", "caveat", "question", "data_gap"]
BackingKind = Literal[
    "lens_invocation", "query_row", "provenance_ref", "data_debt", "lens_gap",
]
StreamEventName = Literal[
    "accepted", "interpreted", "routed", "answer_card", "claim_block",
    "degraded", "completed", "error",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResearchObject(StrictModel):
    kind: ObjectKind
    ref: str = Field(min_length=1, max_length=256)


class DateRange(StrictModel):
    start: Date | None = None
    end: Date | None = None

    @model_validator(mode="after")
    def validate_order(self) -> "DateRange":
        if self.start and self.end and self.start > self.end:
            raise ValueError("date_range.start 不得晚于 end")
        return self


class EventRef(StrictModel):
    event_id: str = Field(min_length=1, max_length=256)
    date: Date | None = None
    title: str | None = Field(default=None, max_length=500)


class ResearchContext(StrictModel):
    symbol: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
    date_range: DateRange | None = None
    selected_event: EventRef | None = None
    selected_episode: str | None = Field(default=None, max_length=256)
    selected_lenses: list[str] = Field(default_factory=list, max_length=20)
    active_question: str | None = Field(default=None, max_length=4000)
    answer_card_id: str | None = Field(default=None, max_length=256)


class ResearchRequest(StrictModel):
    contract_version: Literal[API_CONTRACT_VERSION] = API_CONTRACT_VERSION
    request_id: str | None = Field(default=None, min_length=1, max_length=128)
    question: str = Field(min_length=1, max_length=4000)
    object: ResearchObject | None = None
    context: ResearchContext | None = None
    llm_mode: LlmMode = "auto"


class QuestionInterpretation(StrictModel):
    contract_version: Literal[API_CONTRACT_VERSION] = API_CONTRACT_VERSION
    object: ResearchObject
    intent: str = Field(min_length=1, max_length=128)
    time_range: DateRange | None = None
    dimensions: list[str] = Field(default_factory=list, max_length=20)
    ambiguities: list[str] = Field(default_factory=list, max_length=20)
    candidate_topics: list[str] = Field(default_factory=list, max_length=20)


class RouteDecision(StrictModel):
    contract_version: Literal[API_CONTRACT_VERSION] = API_CONTRACT_VERSION
    route: RouteName
    status: RouteStatus
    view: RouteView
    reason: str = Field(min_length=1, max_length=1000)
    matched_rules: list[str] = Field(default_factory=list, max_length=30)
    data_debt_refs: list[str] = Field(default_factory=list, max_length=20)
    question_card_refs: list[str] = Field(default_factory=list, max_length=20)
    required_lens_behavior: Literal[
        "lens_invocation_required", "lens_invocations_or_gap",
        "lens_gap_required", "not_applicable",
    ]


class ClaimBacking(StrictModel):
    kind: BackingKind
    ref: str = Field(min_length=1, max_length=1000)


class VerifiedClaim(StrictModel):
    text: str = Field(min_length=1, max_length=4000)
    claim_type: ClaimType
    backing: ClaimBacking


class GapDescriptor(StrictModel):
    kind: Literal["lens_gap", "data_debt", "execution_gap"]
    gap_id: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=2000)
    refs: list[str] = Field(default_factory=list, max_length=20)


class SedimentationCandidate(StrictModel):
    kind: Literal["question_card", "data_debt"]
    ref: str | None = Field(default=None, max_length=256)
    reason: str = Field(min_length=1, max_length=2000)


class ResearchResponse(StrictModel):
    contract_version: Literal[API_CONTRACT_VERSION] = API_CONTRACT_VERSION
    request_id: str = Field(min_length=1, max_length=128)
    interpretation: QuestionInterpretation
    route: RouteDecision
    answer_card: dict[str, Any] | None = Field(
        default=None,
        json_schema_extra={"x-contract-ref": "../v8_answer_contract_v0/schema.json"},
    )
    claims: list[VerifiedClaim] = Field(default_factory=list, max_length=100)
    gaps: list[GapDescriptor] = Field(default_factory=list, max_length=50)
    sedimentation_candidates: list[SedimentationCandidate] = Field(
        default_factory=list, max_length=50
    )
    degraded: bool = False
    degraded_reasons: list[str] = Field(default_factory=list, max_length=20)
    llm_used: bool = False


class PricePoint(StrictModel):
    date: Date
    close: float


class StatusInterval(StrictModel):
    start_date: Date
    end_date: Date | None = None
    status_name: str
    status_type: str
    source: str


class DossierEvent(StrictModel):
    event_id: str
    date: Date
    title: str
    episode_type: str
    episode_label: str
    subtype: str | None = None
    subtype_label: str
    timeline_lane: str
    timeline_label: str
    provenance_refs: list[str] = Field(default_factory=list)
    related_lens_ids: list[str] = Field(default_factory=list)


class TimelineLane(StrictModel):
    lane_id: str
    label: str
    event_ids: list[str] = Field(default_factory=list)


class DossierLensSummary(StrictModel):
    release_id: str
    lens_kind: str
    display_label: str
    evidence_grade: str
    contributed_section: str
    provenance_refs: list[str] = Field(default_factory=list)


class DossierDataGap(StrictModel):
    gap_id: str
    display_label: str
    debt_ref: str | None = None


class StockDossierPayload(StrictModel):
    contract_version: Literal[API_CONTRACT_VERSION] = API_CONTRACT_VERSION
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    display_name: str
    as_of: Date
    status_intervals: list[StatusInterval] = Field(default_factory=list)
    price_series: list[PricePoint] = Field(default_factory=list)
    events: list[DossierEvent] = Field(default_factory=list)
    timeline_lanes: list[TimelineLane] = Field(default_factory=list)
    lens_summaries: list[DossierLensSummary] = Field(default_factory=list)
    data_gaps: list[DossierDataGap] = Field(default_factory=list)
    display_labels: dict[str, str] = Field(default_factory=dict)
    research_context: ResearchContext
    provenance: list[str] = Field(default_factory=list)


class ResearchStreamEvent(StrictModel):
    contract_version: Literal[API_CONTRACT_VERSION] = API_CONTRACT_VERSION
    request_id: str = Field(min_length=1, max_length=128)
    sequence: int = Field(ge=1)
    event: StreamEventName
    emitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)


PublicContractObject = Annotated[
    ResearchRequest
    | QuestionInterpretation
    | RouteDecision
    | ResearchResponse
    | StockDossierPayload
    | ResearchStreamEvent,
    Field(union_mode="left_to_right"),
]


def public_contract_schema() -> dict[str, Any]:
    schema = TypeAdapter(PublicContractObject).json_schema()
    response_schema = schema["$defs"]["ResearchResponse"]
    response_schema["properties"]["answer_card"] = {
        "anyOf": [
            {"$ref": "../v8_answer_contract_v0/schema.json"},
            {"type": "null"},
        ],
        "default": None,
        "x-contract-ref": "../v8_answer_contract_v0/schema.json",
    }
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = API_CONTRACT_VERSION
    schema["title"] = "ST Research Copilot API Contract v0"
    schema["x-contract-version"] = API_CONTRACT_VERSION
    return schema
