"""Additive response contract for readable, evidence-backed narratives."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from api_contract import (
    ClaimBacking,
    GapDescriptor,
    QuestionInterpretation,
    RouteDecision,
    SedimentationCandidate,
    VerifiedClaim,
)
from api_contract_v1 import NavigationRef
from question_cards import DataDebtCandidate, QuestionCard


API_CONTRACT_VERSION_V2 = "v8_copilot_api_contract_v2"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NarrativeStatement(StrictModel):
    text: str = Field(min_length=1, max_length=4000)
    backing: list[ClaimBacking] = Field(min_length=1, max_length=10)


class NarrativeStep(NarrativeStatement):
    title: str = Field(min_length=1, max_length=200)


class ResearchNarrative(StrictModel):
    direct_answer: NarrativeStatement
    reasoning_steps: list[NarrativeStep] = Field(default_factory=list, max_length=12)
    uncertainties: list[NarrativeStatement] = Field(default_factory=list, max_length=12)
    watch_items: list[NarrativeStatement] = Field(default_factory=list, max_length=12)
    basis_note: str = Field(min_length=1, max_length=1000)


class BoundaryRewrite(StrictModel):
    message: str = Field(min_length=1, max_length=1000)
    rewritten_question: str = Field(min_length=1, max_length=1000)
    why: str = Field(min_length=1, max_length=1000)


class ResearchResponseV2(StrictModel):
    contract_version: Literal[API_CONTRACT_VERSION_V2] = API_CONTRACT_VERSION_V2
    request_id: str = Field(min_length=1, max_length=128)
    interpretation: QuestionInterpretation
    route: RouteDecision
    answer_card: dict[str, Any] | None = Field(
        default=None,
        json_schema_extra={"x-contract-ref": "../v8_answer_contract_v0/schema.json"},
    )
    claims: list[VerifiedClaim] = Field(default_factory=list, max_length=100)
    narrative: ResearchNarrative | None = None
    boundary_rewrite: BoundaryRewrite | None = None
    gaps: list[GapDescriptor] = Field(default_factory=list, max_length=50)
    sedimentation_candidates: list[SedimentationCandidate] = Field(
        default_factory=list, max_length=50
    )
    question_cards: list[QuestionCard] = Field(default_factory=list, max_length=20)
    data_debt_candidates: list[DataDebtCandidate] = Field(
        default_factory=list, max_length=20
    )
    navigation_refs: list[NavigationRef] = Field(default_factory=list, max_length=200)
    query_template_id: str | None = Field(default=None, pattern=r"^QT-[0-9]{3}$")
    degraded: bool = False
    degraded_reasons: list[str] = Field(default_factory=list, max_length=20)
    llm_used: bool = False

    @model_validator(mode="after")
    def narrative_backing_exists(self) -> "ResearchResponseV2":
        if self.answer_card is None:
            if self.narrative is not None:
                raise ValueError("无 AnswerCard 时不得输出 research narrative")
        elif self.narrative is None:
            raise ValueError("有 AnswerCard 时必须输出 research narrative")

        if self.route.route == "refuse_or_rewrite":
            if self.boundary_rewrite is None:
                raise ValueError("交易边界必须输出 boundary rewrite")
        elif self.boundary_rewrite is not None:
            raise ValueError("非交易边界不得输出 boundary rewrite")

        if self.narrative is None or self.answer_card is None:
            return self
        card = self.answer_card
        valid = {
            "query_row": {
                str(row.get("row_id")) for row in card.get("body_rows", [])
                if row.get("row_id")
            },
            "lens_invocation": {
                str(row.get("release_id")) for row in card.get("lens_invocations", [])
                if row.get("release_id")
            },
            "provenance_ref": {str(ref) for ref in card.get("provenance", [])},
            "data_debt": {str(ref) for ref in card.get("data_debt_refs", [])},
            "lens_gap": {
                str(row.get("gap_id")) for row in card.get("lens_gap", [])
                if row.get("gap_id")
            },
        }
        statements: list[NarrativeStatement] = [self.narrative.direct_answer]
        statements.extend(self.narrative.reasoning_steps)
        statements.extend(self.narrative.uncertainties)
        statements.extend(self.narrative.watch_items)
        for statement in statements:
            for backing in statement.backing:
                if backing.ref not in valid.get(backing.kind, set()):
                    raise ValueError(
                        f"narrative backing 无对应对象: {backing.kind}:{backing.ref}"
                    )
        return self


class ResearchStreamEventV2(StrictModel):
    contract_version: Literal[API_CONTRACT_VERSION_V2] = API_CONTRACT_VERSION_V2
    request_id: str = Field(min_length=1, max_length=128)
    sequence: int = Field(ge=1)
    event: Literal[
        "accepted", "interpreted", "routed", "answer_card", "claim_block",
        "degraded", "completed", "error",
    ]
    emitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)


PublicContractObjectV2 = Annotated[
    ResearchResponseV2 | ResearchStreamEventV2 | ResearchNarrative | BoundaryRewrite,
    Field(union_mode="left_to_right"),
]


def public_contract_schema_v2() -> dict[str, Any]:
    schema = TypeAdapter(PublicContractObjectV2).json_schema()
    response_schema = schema["$defs"]["ResearchResponseV2"]
    response_schema["properties"]["answer_card"] = {
        "anyOf": [
            {"$ref": "../v8_answer_contract_v0/schema.json"},
            {"type": "null"},
        ],
        "default": None,
        "x-contract-ref": "../v8_answer_contract_v0/schema.json",
    }
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = API_CONTRACT_VERSION_V2
    schema["title"] = "ST Research Copilot API Contract v2"
    schema["x-contract-version"] = API_CONTRACT_VERSION_V2
    return schema
