"""Versioned QuestionCard contract and deterministic candidate construction."""
from __future__ import annotations

from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


QUESTION_CARD_CONTRACT_VERSION = "v8_question_card_contract_v0"

QuestionStatus = Literal["answerable", "needs_data", "needs_review"]
QuestionView = Literal[
    "evidence", "query", "checklist", "methodology", "data_debt"
]
QuestionSource = Literal["user", "human_review", "slice", "system_gap"]
QuestionObjectKind = Literal[
    "stock", "stock_event", "episode_type", "cluster", "lens_cluster",
    "lens", "cohort", "universe", "unknown",
]
OriginKind = Literal[
    "user_question", "answer_card", "lens_gap", "data_debt", "review_item"
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class QuestionObject(StrictModel):
    kind: QuestionObjectKind
    ref: str = Field(min_length=1, max_length=256)


class QuestionOrigin(StrictModel):
    kind: OriginKind
    ref: str = Field(min_length=1, max_length=1000)


class QuestionCard(StrictModel):
    contract_version: Literal[QUESTION_CARD_CONTRACT_VERSION] = (
        QUESTION_CARD_CONTRACT_VERSION
    )
    id: str = Field(pattern=r"^QC-(?:[0-9]{8}-[0-9]{3}|CAND-[a-f0-9]{12})$")
    question: str = Field(min_length=1, max_length=4000)
    object: QuestionObject
    needs_data: list[str] = Field(default_factory=list, max_length=30)
    status: QuestionStatus
    view: QuestionView
    source: QuestionSource
    debt_ref: str | None = Field(default=None, max_length=128)
    created_from: list[QuestionOrigin] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "QuestionCard":
        if self.status == "needs_data":
            if not self.needs_data:
                raise ValueError("needs_data QuestionCard 必须列出缺失数据")
            if not self.debt_ref:
                raise ValueError("needs_data QuestionCard 必须绑定 debt_ref")
        elif self.debt_ref:
            raise ValueError("只有 needs_data QuestionCard 可以绑定 debt_ref")
        if self.status == "answerable" and self.view == "data_debt":
            raise ValueError("answerable QuestionCard 不得使用 data_debt 视图")
        return self


class DataDebtCandidate(StrictModel):
    debt_ref: str = Field(min_length=1, max_length=128)
    gap: str = Field(min_length=1, max_length=2000)
    affects: str = Field(min_length=1, max_length=2000)
    created_from: list[QuestionOrigin] = Field(min_length=1, max_length=20)


def candidate_id(question: str, object_kind: str, object_ref: str) -> str:
    digest = sha256(
        f"{question.strip()}\x1f{object_kind}\x1f{object_ref}".encode("utf-8")
    ).hexdigest()[:12]
    return f"QC-CAND-{digest}"
