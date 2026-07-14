"""Operational contract for reusable research experience; never research evidence."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


EXPERIENCE_CONTRACT_VERSION = "v8_research_experience_contract_v0"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ExperienceType(StrEnum):
    ROUTING_RULE = "routing_rule"
    QUERY_PLAN = "query_plan"
    DEFINITION = "definition"
    COVERAGE_BOUNDARY = "coverage_boundary"
    REASONING_RULE = "reasoning_rule"
    PRESENTATION_RULE = "presentation_rule"
    ANTI_PATTERN = "anti_pattern"
    MATERIALIZATION_RECIPE = "materialization_recipe"
    REGRESSION_CASE = "regression_case"


class ExperienceStatus(StrEnum):
    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    IGNORED = "ignored"
    MERGED = "merged"
    BLOCKED = "blocked"
    CLOSED = "closed"
    SUPERSEDED = "superseded"


class ExperienceCandidateInput(StrictModel):
    experience_type: ExperienceType
    title: str = Field(min_length=3, max_length=160)
    value_summary: str = Field(min_length=3, max_length=1000)
    trigger_conditions: list[str] = Field(min_length=1, max_length=20)
    scope: list[str] = Field(min_length=1, max_length=20)
    required_inputs: list[str] = Field(min_length=1, max_length=20)
    query_plan: list[str] = Field(default_factory=list, max_length=30)
    definitions: list[str] = Field(default_factory=list, max_length=30)
    answer_rubric: list[str] = Field(min_length=1, max_length=30)
    anti_patterns: list[str] = Field(min_length=1, max_length=30)
    coverage_boundaries: list[str] = Field(min_length=1, max_length=30)
    validation_refs: list[str] = Field(min_length=1, max_length=50)
    source_run_refs: list[str] = Field(min_length=1, max_length=50)
    supersedes: list[str] = Field(default_factory=list, max_length=20)


class ExperienceRecord(ExperienceCandidateInput):
    contract_version: Literal[EXPERIENCE_CONTRACT_VERSION] = EXPERIENCE_CONTRACT_VERSION
    experience_id: str = Field(pattern=r"^EXP-[A-F0-9]{20}$")
    experience_version: int = Field(default=1, ge=1)
    status: ExperienceStatus = ExperienceStatus.CANDIDATE
    dedupe_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime
    reviewed_at: datetime | None = None
    reviewed_by: str | None = Field(default=None, max_length=128)
    not_evidence: Literal[True] = True

    @model_validator(mode="after")
    def accepted_is_human_reviewed_and_generic(self) -> "ExperienceRecord":
        if self.status == ExperienceStatus.ACCEPTED:
            if self.reviewed_at is None or not self.reviewed_by:
                raise ValueError("accepted experience 必须有人类审阅记录")
            reusable = " ".join([
                self.title, self.value_summary, *self.trigger_conditions,
                *self.query_plan, *self.answer_rubric,
            ])
            if re.search(r"(?<!\d)\d{6}(?!\d)|20\d{2}-\d{2}-\d{2}", reusable):
                raise ValueError("accepted experience 不得固化单票代码或时点事实")
        return self


class ExperienceReviewRequest(StrictModel):
    action: Literal["accept", "ignore", "block", "merge", "close", "supersede"]
    actor_type: Literal["human", "codex", "system"]
    reviewed_by: str = Field(min_length=1, max_length=128)
    note: str = Field(default="", max_length=2000)
    merge_target: str | None = Field(default=None, pattern=r"^EXP-[A-F0-9]{20}$")

    @model_validator(mode="after")
    def merge_needs_target(self) -> "ExperienceReviewRequest":
        if self.action == "merge" and not self.merge_target:
            raise ValueError("merge 操作必须提供 merge_target")
        return self


class ExperienceFeedbackRequest(StrictModel):
    feedback_text: str = Field(min_length=1, max_length=4000)
    category: Literal[
        "presentation", "routing", "coverage", "query_plan", "anti_pattern",
        "no_experience",
    ]
    submitted_by: str = Field(default="owner", min_length=1, max_length=128)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
