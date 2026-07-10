from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.v8_copilot_api_contract_v0.models import ResearchContext as ResearchContextInput


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuestionInterpretation(StrictModel):
    object_kind: str = "unknown"
    object_ref: str | None = None
    intent: str
    time_scope: str | None = None
    requested_dimensions: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    candidate_topics: list[str] = Field(default_factory=list)


BackingKind = Literal[
    "lens_invocation",
    "query_row",
    "provenance_ref",
    "data_debt",
    "lens_gap",
]
ClaimType = Literal["fact", "inference", "caveat", "question", "data_gap"]


class ClaimBacking(StrictModel):
    kind: BackingKind
    ref: str = Field(min_length=1)


class AnalysisClaimOutput(StrictModel):
    text: str = Field(min_length=1)
    claim_type: ClaimType
    backing: ClaimBacking


class ClaimBatch(StrictModel):
    claims: list[AnalysisClaimOutput]
