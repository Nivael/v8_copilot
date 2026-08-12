"""Compressed, human-readable review queue for reusable research experience."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from experience_contract import ExperienceRecord, ExperienceStatus
from research_repository import ExperienceRepository, ResearchRunLedger


REVIEW_VERSION = "v8_experience_batch_review_v1"
Decision = Literal["accept_suggested", "need_more_evidence", "reject", "defer"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ReviewOption(StrictModel):
    value: Decision
    label: str
    description: str


class ReviewExample(StrictModel):
    run_id: str
    question: str
    intent: str
    answer_excerpt: str
    source_pointer: str


class ExperienceReviewCard(StrictModel):
    card_id: str
    experience_id: str
    experience_version: int
    title: str
    affected_area: str
    target_field: Literal["experience_status"] = "experience_status"
    scope: Literal["experience_cluster"] = "experience_cluster"
    decision_requested: str
    why_surfaced: str
    recommendation: Decision
    recommendation_label: str
    recommendation_reason: str
    impact: str
    affected_count: int = Field(ge=0)
    options: list[ReviewOption]
    evidence_examples: list[ReviewExample]
    counterexamples: list[ReviewExample] = Field(default_factory=list)
    prior_decisions: list[str] = Field(default_factory=list)
    experience: ExperienceRecord


class ExperienceReviewQueue(StrictModel):
    review_session_id: str
    review_version: Literal[REVIEW_VERSION] = REVIEW_VERSION
    title: str
    source_packet: str
    created_at: str
    max_pending: int = Field(ge=1, le=20)
    cards: list[ExperienceReviewCard] = Field(max_length=20)


class ExperienceReviewDecision(StrictModel):
    card_id: str
    decision: Decision
    note: str = Field(default="", max_length=2000)
    target_field: Literal["experience_status"] = "experience_status"
    affected_area: str
    scope: Literal["experience_cluster"] = "experience_cluster"
    recommended_decision: Decision
    question: str


class ExperienceReviewDecisionExport(StrictModel):
    review_session_id: str
    review_version: Literal[REVIEW_VERSION] = REVIEW_VERSION
    exported_at: str
    source_packet: str
    decisions: list[ExperienceReviewDecision] = Field(min_length=1, max_length=20)


OPTIONS = [
    ReviewOption(value="accept_suggested", label="接受推荐", description="升级为 accepted；后续仍重新查证事实。"),
    ReviewOption(value="need_more_evidence", label="需要更多证据", description="转为 blocked，补足来源或回归后再审。"),
    ReviewOption(value="reject", label="不沉淀", description="转为 ignored，不进入经验库。"),
    ReviewOption(value="defer", label="稍后再看", description="保留 candidate，不产生可复用规则。"),
]


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def build_review_queue(
    repository: ExperienceRepository,
    ledger: ResearchRunLedger,
    *,
    limit: int = 10,
) -> ExperienceReviewQueue:
    limit = min(max(limit, 1), 20)
    candidates = repository.list(status=ExperienceStatus.CANDIDATE, limit=limit)
    cards: list[ExperienceReviewCard] = []
    for candidate in candidates:
        examples: list[ReviewExample] = []
        for run_id in candidate.source_run_refs:
            if not run_id.startswith("RUN-"):
                continue
            try:
                run = ledger.get(run_id)
            except KeyError:
                continue
            examples.append(ReviewExample(
                run_id=run.run_id,
                question=run.question_text,
                intent=run.normalized_intent,
                answer_excerpt=run.final_answer[:240],
                source_pointer=f"research_run:{run.run_id}",
            ))
            if len(examples) == 5:
                break
        regression_ready = all(not ref.startswith("review:") for ref in candidate.validation_refs)
        recommendation: Decision = (
            "accept_suggested" if examples and regression_ready else "need_more_evidence"
        )
        reason = (
            f"已有 {len(examples)} 条真实运行来源，并绑定可执行回归。"
            if recommendation == "accept_suggested"
            else "真实运行来源或可执行回归尚不足，先不要让它进入研究提示。"
        )
        cards.append(ExperienceReviewCard(
            card_id=candidate.experience_id,
            experience_id=candidate.experience_id,
            experience_version=candidate.experience_version,
            title=candidate.title,
            affected_area=candidate.experience_type.value,
            decision_requested=f"是否把“{candidate.title}”作为以后同类研究的方法提示？",
            why_surfaced=f"该方法由 {len(candidate.source_run_refs)} 个来源运行归并成一个候选簇。",
            recommendation=recommendation,
            recommendation_label="建议接受" if recommendation == "accept_suggested" else "建议补证",
            recommendation_reason=reason,
            impact=f"决定 1 个方法簇；当前关联 {len(candidate.source_run_refs)} 个来源运行。",
            affected_count=len(candidate.source_run_refs),
            options=OPTIONS,
            evidence_examples=examples,
            experience=candidate,
        ))
    identity = [card.experience.model_dump(mode="json") for card in cards]
    source_packet = f"sha256:{_digest(identity)}"
    return ExperienceReviewQueue(
        review_session_id=f"XRV-{_digest({'source_packet': source_packet})[:20].upper()}",
        title="可复用研究经验批量审阅",
        source_packet=source_packet,
        created_at=(
            max(candidate.created_at for candidate in candidates).isoformat()
            if candidates else datetime.now(timezone.utc).date().isoformat()
        ),
        max_pending=limit,
        cards=cards,
    )


def validate_decision_export(
    queue: ExperienceReviewQueue,
    export: ExperienceReviewDecisionExport,
) -> None:
    if export.review_session_id != queue.review_session_id:
        raise ValueError("review_session_id 与审阅队列不一致")
    if export.source_packet != queue.source_packet:
        raise ValueError("source_packet 与审阅队列不一致")
    cards = {card.card_id: card for card in queue.cards}
    seen: set[str] = set()
    for decision in export.decisions:
        if decision.card_id in seen:
            raise ValueError("同一审阅卡不能提交两次")
        seen.add(decision.card_id)
        card = cards.get(decision.card_id)
        if card is None:
            raise ValueError("决策包含不属于该队列的 card_id")
        if (
            decision.target_field != card.target_field
            or decision.affected_area != card.affected_area
            or decision.scope != card.scope
            or decision.recommended_decision != card.recommendation
            or decision.question != card.decision_requested
        ):
            raise ValueError("决策元数据与原审阅卡不一致")
