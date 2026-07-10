"""Optional structured LLM layer; deterministic Core remains authoritative."""
from __future__ import annotations

import json
import os
import re
from importlib.util import find_spec
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from api_contract import (
    ClaimBacking,
    QuestionInterpretation,
    ResearchObject,
    ResearchRequest,
    ResearchResponse,
    VerifiedClaim,
)
from answer_engine import FORBIDDEN_WORDING
from orchestrator import orchestrate


class ProviderUnavailable(RuntimeError):
    pass


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuestionInterpretationDraft(StrictModel):
    object_kind: str = "unknown"
    object_ref: str | None = None
    intent: str
    dimensions: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    candidate_topics: list[str] = Field(default_factory=list)


class ClaimDraft(StrictModel):
    text: str = Field(min_length=1, max_length=4000)
    claim_type: str
    backing_kind: str
    backing_ref: str = Field(min_length=1, max_length=1000)


class ClaimBatch(StrictModel):
    claims: list[ClaimDraft] = Field(default_factory=list, max_length=100)


T = TypeVar("T", bound=BaseModel)


class StructuredProvider(Protocol):
    provider_name: str

    def parse(self, *, response_model: type[T], instructions: str, payload: dict[str, Any]) -> T:
        ...


class FakeLLMProvider:
    provider_name = "fake"

    def __init__(self, failure: str | None = None) -> None:
        self.failure = failure

    def parse(self, *, response_model: type[T], instructions: str, payload: dict[str, Any]) -> T:
        if self.failure:
            raise ProviderUnavailable(self.failure)
        if response_model is QuestionInterpretationDraft:
            question = str(payload.get("question", ""))
            context = payload.get("context") or {}
            symbol_match = re.search(r"(?<!\d)(\d{6})(?!\d)", question)
            symbol = context.get("symbol") or (symbol_match.group(1) if symbol_match else None)
            topics = [term for term in ("重整", "公告", "股价", "控制权", "股东", "ST") if term.lower() in question.lower()]
            return QuestionInterpretationDraft(
                object_kind="stock" if symbol else "unknown",
                object_ref=symbol,
                intent="research_question",
                dimensions=topics,
                ambiguities=[] if symbol or topics else ["未识别明确对象或主题"],
                candidate_topics=topics,
            )  # type: ignore[return-value]
        if response_model is ClaimBatch:
            existing = payload.get("existing_claims") or []
            if existing:
                return ClaimBatch.model_validate({"claims": [
                    {
                        "text": claim["text"],
                        "claim_type": claim["claim_type"],
                        "backing_kind": claim["backing"]["kind"],
                        "backing_ref": claim["backing"]["ref"],
                    }
                    for claim in existing
                ]})  # type: ignore[return-value]
            catalog = payload.get("backing_catalog") or []
            if not catalog:
                return ClaimBatch(claims=[])  # type: ignore[return-value]
            first = catalog[0]
            return ClaimBatch(claims=[ClaimDraft(
                text="本回答保留结构化证据菜单；分析边界以对应证据项为准。",
                claim_type="caveat",
                backing_kind=first["kind"],
                backing_ref=first["ref"],
            )])  # type: ignore[return-value]
        raise TypeError(f"fake provider 不支持 {response_model.__name__}")


class OpenAIResponsesProvider:
    provider_name = "openai"

    def __init__(self, *, api_key: str | None = None, model: str | None = None, client: Any = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("V8_OPENAI_MODEL")
        if not self.api_key:
            raise ProviderUnavailable("缺 OPENAI_API_KEY")
        if not self.model:
            raise ProviderUnavailable("缺 V8_OPENAI_MODEL")
        if client is not None:
            self.client = client
            return
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderUnavailable("未安装 openai Python SDK") from exc
        self.client = OpenAI(api_key=self.api_key)

    def parse(self, *, response_model: type[T], instructions: str, payload: dict[str, Any]) -> T:
        try:
            response = self.client.responses.parse(
                model=self.model,
                instructions=instructions,
                input=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                text_format=response_model,
            )
        except Exception as exc:
            raise ProviderUnavailable(f"OpenAI structured response 失败: {type(exc).__name__}") from exc
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise ProviderUnavailable("OpenAI response 缺 output_parsed")
        return parsed if isinstance(parsed, response_model) else response_model.model_validate(parsed)


PARSER_INSTRUCTIONS = """只解释问题对象、意图、维度和歧义。不得补充事实、数字、
证据等级或投资建议。最终路由由确定性引擎裁决。"""
COMPOSER_INSTRUCTIONS = """只重组输入中的证据菜单。每条 claim 必须引用 backing_catalog；
不得引入新数字、新日期、新事实、新证据等级或买卖、仓位、目标价建议。"""


def _parse_question(provider: StructuredProvider, request: ResearchRequest) -> QuestionInterpretationDraft:
    return provider.parse(
        response_model=QuestionInterpretationDraft,
        instructions=PARSER_INSTRUCTIONS,
        payload={
            "question": request.question,
            "context": request.context.model_dump(mode="json") if request.context else None,
        },
    )


def _backing_catalog(card: dict[str, Any]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    refs.extend({"kind": "lens_invocation", "ref": row["release_id"]} for row in card.get("lens_invocations", []))
    refs.extend({"kind": "query_row", "ref": row["row_id"]} for row in card.get("body_rows", []))
    refs.extend({"kind": "provenance_ref", "ref": ref} for ref in card.get("provenance", []))
    refs.extend({"kind": "data_debt", "ref": ref} for ref in card.get("data_debt_refs", []))
    refs.extend({"kind": "lens_gap", "ref": row["gap_id"]} for row in card.get("lens_gap", []))
    return refs


def _composer_payload(card: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "question", "object_ref", "view", "as_of", "sample_scope", "evidence_grade",
        "lens_invocations", "lens_gap", "body_rows", "analysis_claims", "data_debt",
        "data_debt_refs", "caveats", "provenance",
    }
    payload = {key: value for key, value in card.items() if key in allowed}
    payload["existing_claims"] = payload.pop("analysis_claims", [])
    payload["backing_catalog"] = _backing_catalog(card)
    return payload


def _compose_claims(provider: StructuredProvider, card: dict[str, Any]) -> list[VerifiedClaim]:
    batch = provider.parse(
        response_model=ClaimBatch,
        instructions=COMPOSER_INSTRUCTIONS,
        payload=_composer_payload(card),
    )
    catalog = {(item["kind"], item["ref"]) for item in _backing_catalog(card)}
    claims: list[VerifiedClaim] = []
    for draft in batch.claims:
        if (draft.backing_kind, draft.backing_ref) not in catalog:
            raise ValueError(f"claim backing 无对应对象: {draft.backing_kind}:{draft.backing_ref}")
        if draft.claim_type not in {"fact", "inference", "caveat", "question", "data_gap"}:
            raise ValueError(f"claim_type 非法: {draft.claim_type}")
        if any(term in draft.text for term in FORBIDDEN_WORDING):
            raise ValueError("claim 命中禁用交易措辞")
        claims.append(VerifiedClaim(
            text=draft.text,
            claim_type=draft.claim_type,  # type: ignore[arg-type]
            backing=ClaimBacking(
                kind=draft.backing_kind,  # type: ignore[arg-type]
                ref=draft.backing_ref,
            ),
        ))
    return claims


def orchestrate_with_provider(request: ResearchRequest, provider: StructuredProvider) -> ResearchResponse:
    deterministic = orchestrate(request.model_copy(update={"llm_mode": "off"}))
    draft = _parse_question(provider, request)
    research_object = deterministic.interpretation.object
    if research_object.kind == "unknown" and draft.object_ref:
        research_object = ResearchObject(kind="stock", ref=draft.object_ref)
    interpretation = QuestionInterpretation(
        object=research_object,
        intent=draft.intent,
        time_range=deterministic.interpretation.time_range,
        dimensions=draft.dimensions,
        ambiguities=draft.ambiguities,
        candidate_topics=draft.candidate_topics,
    )
    claims = deterministic.claims
    if deterministic.answer_card is not None:
        claims = _compose_claims(provider, deterministic.answer_card)
    return deterministic.model_copy(update={
        "interpretation": interpretation,
        "claims": claims,
        "llm_used": True,
        "degraded": deterministic.answer_card is None,
        "degraded_reasons": (
            deterministic.degraded_reasons if deterministic.answer_card is None else []
        ),
    })


def openai_configured() -> bool:
    return bool(
        os.getenv("OPENAI_API_KEY")
        and os.getenv("V8_OPENAI_MODEL")
        and find_spec("openai") is not None
    )


def orchestrate_optional_llm(request: ResearchRequest) -> ResearchResponse:
    if request.llm_mode == "off":
        return orchestrate(request)
    if not openai_configured():
        return orchestrate(request)
    try:
        return orchestrate_with_provider(request, OpenAIResponsesProvider())
    except (ProviderUnavailable, ValueError):
        response = orchestrate(request)
        reasons = [reason for reason in response.degraded_reasons if "adapter 尚未注入" not in reason]
        reasons.insert(0, "LLM 输出不可用或未通过 backing 校验，已返回确定性结果。")
        return response.model_copy(update={"degraded": True, "degraded_reasons": reasons})
