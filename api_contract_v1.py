"""Additive Batch 2 closeout API contract; v0 remains immutable."""
from __future__ import annotations

from datetime import date as Date, datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from api_contract import (
    GapDescriptor,
    QuestionInterpretation,
    ResearchObject,
    RouteDecision,
    SedimentationCandidate,
    StockDossierPayload,
    VerifiedClaim,
)
from question_cards import DataDebtCandidate, QuestionCard


API_CONTRACT_VERSION_V1 = "v8_copilot_api_contract_v1"
NavigationKind = Literal[
    "stock", "date", "announcement", "episode", "lens", "provenance",
    "data_debt",
]
NavigationSourceKind = Literal[
    "request_context", "answer_card", "answer_row", "lens_invocation",
    "provenance", "data_debt",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResearchContextPatch(StrictModel):
    symbol: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
    date_start: Date | None = None
    date_end: Date | None = None
    event_id: str | None = Field(default=None, max_length=256)
    event_title: str | None = Field(default=None, max_length=500)
    episode_ref: str | None = Field(default=None, max_length=256)
    lens_id: str | None = Field(default=None, max_length=256)
    provenance_ref: str | None = Field(default=None, max_length=1000)
    data_debt_ref: str | None = Field(default=None, max_length=128)


class NavigationRef(StrictModel):
    id: str = Field(min_length=1, max_length=256)
    kind: NavigationKind
    label: str = Field(min_length=1, max_length=1000)
    source_kind: NavigationSourceKind
    source_ref: str = Field(min_length=1, max_length=1000)
    href: str = Field(pattern=r"^/")
    context: ResearchContextPatch


class ResearchResponseV1(StrictModel):
    contract_version: Literal[API_CONTRACT_VERSION_V1] = API_CONTRACT_VERSION_V1
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
    question_cards: list[QuestionCard] = Field(default_factory=list, max_length=20)
    data_debt_candidates: list[DataDebtCandidate] = Field(
        default_factory=list, max_length=20
    )
    navigation_refs: list[NavigationRef] = Field(default_factory=list, max_length=200)
    query_template_id: str | None = Field(
        default=None, pattern=r"^QT-[0-9]{3}$"
    )
    degraded: bool = False
    degraded_reasons: list[str] = Field(default_factory=list, max_length=20)
    llm_used: bool = False


class ResearchStreamEventV1(StrictModel):
    contract_version: Literal[API_CONTRACT_VERSION_V1] = API_CONTRACT_VERSION_V1
    request_id: str = Field(min_length=1, max_length=128)
    sequence: int = Field(ge=1)
    event: Literal[
        "accepted", "interpreted", "routed", "answer_card", "claim_block",
        "degraded", "completed", "error",
    ]
    emitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)


PublicContractObjectV1 = Annotated[
    ResearchResponseV1 | ResearchStreamEventV1 | NavigationRef | QuestionCard,
    Field(union_mode="left_to_right"),
]


def public_contract_schema_v1() -> dict[str, Any]:
    schema = TypeAdapter(PublicContractObjectV1).json_schema()
    response_schema = schema["$defs"]["ResearchResponseV1"]
    response_schema["properties"]["answer_card"] = {
        "anyOf": [
            {"$ref": "../v8_answer_contract_v0/schema.json"},
            {"type": "null"},
        ],
        "default": None,
        "x-contract-ref": "../v8_answer_contract_v0/schema.json",
    }
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = API_CONTRACT_VERSION_V1
    schema["title"] = "ST Research Copilot API Contract v1"
    schema["x-contract-version"] = API_CONTRACT_VERSION_V1
    return schema
