from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal, Union
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator


API_CONTRACT_VERSION = "v8_copilot_api_contract_v0"
AnswerRoute = Literal[
    "answer_query",
    "answer_evidence",
    "answer_checklist",
    "answer_methodology",
    "data_debt",
    "lens_gap",
    "needs_review",
    "clarify",
    "refuse_or_rewrite",
]
RouteStatus = Literal["answerable", "needs_data", "needs_review", "clarify", "boundary"]
RouteView = Literal[
    "query", "evidence", "checklist", "methodology", "data_debt",
    "lens_gap", "clarify", "boundary",
]
StreamEventName = Literal[
    "accepted",
    "interpreted",
    "routed",
    "answer_card",
    "claim_block",
    "degraded",
    "completed",
    "error",
]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResearchObject(ContractModel):
    kind: Literal["stock", "event", "cohort", "lens", "unknown"]
    ref: str | None = None
    display_name: str | None = None


class ResearchContext(ContractModel):
    symbol: str | None = Field(default=None, pattern=r"^\d{6}$")
    event_id: str | None = None
    event_date: date | None = None
    event_title: str | None = None
    time_start: date | None = None
    time_end: date | None = None
    selected_lenses: list[str] = Field(default_factory=list)
    active_question: str | None = None

    @model_validator(mode="after")
    def validate_time_range(self) -> "ResearchContext":
        if self.time_start and self.time_end and self.time_start > self.time_end:
            raise ValueError("time_start must not be after time_end")
        return self


class ResearchRequest(ContractModel):
    contract_version: Literal["v8_copilot_api_contract_v0"] = API_CONTRACT_VERSION
    request_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)
    question: str = Field(min_length=1, max_length=4000)
    object: ResearchObject | None = None
    context: ResearchContext | None = None
    llm_mode: Literal["auto", "disabled"] = "auto"


class QuestionInterpretation(ContractModel):
    contract_version: Literal["v8_copilot_api_contract_v0"] = API_CONTRACT_VERSION
    request_id: str
    object: ResearchObject
    intent: str
    time_scope: ResearchContext | None = None
    requested_dimensions: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    candidate_topics: list[str] = Field(default_factory=list)
    generated_by: Literal["deterministic", "llm_validated"] = "deterministic"


class RouteDecision(ContractModel):
    contract_version: Literal["v8_copilot_api_contract_v0"] = API_CONTRACT_VERSION
    request_id: str
    route: AnswerRoute
    status: RouteStatus
    view: RouteView
    required_lens_behavior: str
    data_debt_refs: list[str] = Field(default_factory=list)
    question_card_refs: list[str] = Field(default_factory=list)
    matched_rules: list[str] = Field(default_factory=list)
    note: str = ""


class ClaimBacking(ContractModel):
    kind: Literal["lens_invocation", "query_row", "provenance_ref", "data_debt", "lens_gap"]
    ref: str


class ValidatedClaim(ContractModel):
    claim_id: str
    text: str
    claim_type: Literal["fact", "inference", "caveat", "question", "data_gap"]
    backing: ClaimBacking


class FallbackResult(ContractModel):
    kind: Literal["lens_gap", "data_debt", "clarify", "needs_review", "refuse"]
    title: str
    message: str
    question_card_refs: list[str] = Field(default_factory=list)
    data_debt_refs: list[str] = Field(default_factory=list)
    suggested_question: str | None = None
    provenance: list[str] = Field(default_factory=lambda: ["evals/deterministic_router_v0.py"])


class Degradation(ContractModel):
    code: Literal["llm_unavailable", "llm_failed", "llm_output_rejected"]
    message: str


class ResearchResponse(ContractModel):
    contract_version: Literal["v8_copilot_api_contract_v0"] = API_CONTRACT_VERSION
    request_id: str
    status: Literal["complete", "degraded"]
    interpretation: QuestionInterpretation
    route: RouteDecision
    answer_card: dict[str, Any] | None = None
    fallback: FallbackResult | None = None
    claims: list[ValidatedClaim] = Field(default_factory=list)
    degradations: list[Degradation] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_exactly_one_result(self) -> "ResearchResponse":
        if (self.answer_card is None) == (self.fallback is None):
            raise ValueError("exactly one of answer_card or fallback is required")
        if self.status == "degraded" and not self.degradations:
            raise ValueError("degraded response requires degradations")
        if self.status == "complete" and self.degradations:
            raise ValueError("complete response cannot contain degradations")
        return self


class PricePoint(ContractModel):
    date: date
    close: float


class StatusInterval(ContractModel):
    start_date: date
    end_date: date | None = None
    display_name: str
    status_type_id: str
    source: str


class EventNode(ContractModel):
    event_id: str
    date: date
    title: str
    lane_id: str
    lane_label: str
    episode_type_id: str
    episode_label: str
    subtype_id: str | None = None
    subtype_label: str
    source_material_ref: str | None = None
    source_material_label: str


class TimelineLane(ContractModel):
    lane_id: str
    display_label: str
    color: str


class DossierLensSummary(ContractModel):
    release_id: str
    lens_label: str
    contributed_section: str
    evidence_grade_label: str
    cohort_label: str


class StockDossierPayload(ContractModel):
    contract_version: Literal["v8_copilot_api_contract_v0"] = API_CONTRACT_VERSION
    symbol: str = Field(pattern=r"^\d{6}$")
    display_name: str
    as_of: date
    price_series: list[PricePoint]
    status_intervals: list[StatusInterval] = Field(default_factory=list)
    event_nodes: list[EventNode] = Field(default_factory=list)
    timeline_lanes: list[TimelineLane]
    lens_invocations: list[DossierLensSummary] = Field(default_factory=list)
    source_freshness: dict[str, str]
    provenance: list[str]


class ResearchStreamEvent(ContractModel):
    contract_version: Literal["v8_copilot_api_contract_v0"] = API_CONTRACT_VERSION
    request_id: str
    sequence: int = Field(ge=1)
    event: StreamEventName
    payload: dict[str, Any]


PublicContract = Annotated[
    Union[
        ResearchRequest,
        ResearchContext,
        QuestionInterpretation,
        RouteDecision,
        ResearchResponse,
        StockDossierPayload,
        ResearchStreamEvent,
    ],
    Field(union_mode="left_to_right"),
]


def public_contract_schema() -> dict[str, Any]:
    schema = TypeAdapter(PublicContract).json_schema()
    schema["$id"] = API_CONTRACT_VERSION
    schema["title"] = "ST Research Copilot API Contract v0"
    return schema
