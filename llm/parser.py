from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import re
from typing import Any, Callable, Mapping

from pydantic import BaseModel, ValidationError

from evals.deterministic_router_v0 import RoutePrediction, route_question
from llm.boundaries import LLM_FORBIDDEN_WORDING
from llm.config import LLMConfigurationError, resolve_model
from llm.providers import LLMProviderError, StructuredLLMProvider
from llm.schemas import ParsedQuestion


API_CONTRACT_VERSION = "v8_copilot_api_contract_v0"
CONTEXT_FIELDS = {
    "symbol",
    "date_range",
    "selected_event",
    "selected_episode",
    "selected_lenses",
    "active_question",
    "answer_card_id",
}

PARSER_SYSTEM_PROMPT = """你是 ST Research Copilot 的问题解析器。
只做问题规范化、对象候选、意图、时间范围、分析维度、歧义、候选主题和路由建议。
不得回答研究问题，不得生成事实、数字或证据结论。
proposed_route 只是建议，最终由确定性 router 裁决。
若原问题请求交易建议，可给一个不含交易建议的研究问题改写；否则 compliant_rewrite 为空。
time_range 不明确时 start/end 都输出空字符串。输出必须符合给定结构。
"""


def _jsonable(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _context_payload(context: BaseModel | Mapping[str, Any] | None) -> dict[str, Any]:
    if context is None:
        return {}
    if isinstance(context, BaseModel):
        raw = context.model_dump(mode="json")
    elif isinstance(context, Mapping):
        raw = dict(context)
    else:
        raise TypeError("ResearchContext 必须是 W1 Pydantic 对象、mapping 或 None")
    unknown = set(raw) - CONTEXT_FIELDS
    if unknown:
        raise ValueError(f"ResearchContext 含 W1 契约外字段: {sorted(unknown)}")
    return _jsonable(raw)  # type: ignore[return-value]


def _object_payload(value: Mapping[str, Any] | BaseModel | None) -> dict[str, str] | None:
    if value is None:
        return None
    if isinstance(value, BaseModel):
        raw = value.model_dump(mode="json")
    else:
        raw = dict(value)
    kind = str(raw.get("kind", "unknown"))
    ref = str(raw.get("ref", "unknown"))
    return {"kind": kind, "ref": ref}


def _resolved_object(
    parsed: ParsedQuestion | None,
    context: dict[str, Any],
    authoritative_object: Mapping[str, Any] | BaseModel | None,
) -> dict[str, str]:
    explicit = _object_payload(authoritative_object)
    if explicit and explicit["kind"] != "unknown":
        return explicit
    symbol = context.get("symbol")
    if isinstance(symbol, str) and symbol:
        return {"kind": "stock", "ref": symbol}
    if (
        parsed is not None
        and parsed.object_kind == "stock"
        and re.fullmatch(r"[0-9]{6}", parsed.object_ref)
    ):
        return {"kind": parsed.object_kind, "ref": parsed.object_ref}
    return explicit or {"kind": "unknown", "ref": "unknown"}


def _route_payload(route: RoutePrediction) -> dict[str, Any]:
    return {
        "contract_version": API_CONTRACT_VERSION,
        "route": route.predicted_route,
        "status": route.expected_status,
        "view": route.expected_view,
        "reason": route.route_note or "确定性路由已裁决。",
        "matched_rules": route.matched_rules,
        "data_debt_refs": route.required_data_debt_refs,
        "question_card_refs": route.required_question_card_refs,
        "required_lens_behavior": route.required_lens_behavior,
    }


def _interpretation_payload(
    parsed: ParsedQuestion,
    resolved_object: dict[str, str],
    context: dict[str, Any],
) -> dict[str, Any]:
    if parsed.time_range.start:
        time_range: dict[str, Any] | None = {
            "start": parsed.time_range.start,
            "end": parsed.time_range.end,
        }
    else:
        time_range = context.get("date_range")
    return {
        "contract_version": API_CONTRACT_VERSION,
        "object": resolved_object,
        "intent": parsed.intent,
        "time_range": time_range,
        "dimensions": parsed.dimensions,
        "ambiguities": parsed.ambiguities,
        "candidate_topics": parsed.candidate_topics,
    }


def _safe_rewrite(
    candidate: str,
    route: RoutePrediction,
    resolved_object: dict[str, str],
) -> str:
    if route.predicted_route != "refuse_or_rewrite":
        return ""
    candidate = candidate.strip()
    if candidate:
        rerouted = route_question({"user_question": candidate, "object": resolved_object})
        if rerouted.predicted_route != "refuse_or_rewrite" and not any(
            term in candidate for term in LLM_FORBIDDEN_WORDING
        ):
            return candidate
    subject = resolved_object["ref"] if resolved_object["kind"] == "stock" else "该研究对象"
    return f"{subject} 当前有哪些公开事件节点、历史证据和待核查窗口？"


@dataclass(frozen=True)
class ParsedQuestionResult:
    parsed: ParsedQuestion | None
    interpretation: dict[str, Any] | None
    adjudicated_route: RoutePrediction
    route_payload: dict[str, Any]
    compliant_rewrite: str
    llm_used: bool
    llm_route_overruled: bool
    degraded_reasons: list[str]


class QuestionParser:
    def __init__(
        self,
        provider: StructuredLLMProvider,
        *,
        model: str | None = None,
        router: Callable[[dict], RoutePrediction] = route_question,
    ) -> None:
        self._provider = provider
        self._model = model
        self._router = router

    def parse(
        self,
        question: str,
        context: BaseModel | Mapping[str, Any] | None,
        *,
        authoritative_object: Mapping[str, Any] | BaseModel | None = None,
    ) -> ParsedQuestionResult:
        if not question.strip():
            raise ValueError("question 不得为空")
        context_payload = _context_payload(context)
        payload = {"question": question, "research_context": context_payload}
        parsed = self._provider.generate(
            response_model=ParsedQuestion,
            system_prompt=PARSER_SYSTEM_PROMPT,
            payload=payload,
            model=resolve_model(self._model),
        )
        resolved_object = _resolved_object(parsed, context_payload, authoritative_object)
        adjudicated = self._router({"user_question": question, "object": resolved_object})
        return ParsedQuestionResult(
            parsed=parsed,
            interpretation=_interpretation_payload(parsed, resolved_object, context_payload),
            adjudicated_route=adjudicated,
            route_payload=_route_payload(adjudicated),
            compliant_rewrite=_safe_rewrite(
                parsed.compliant_rewrite, adjudicated, resolved_object
            ),
            llm_used=True,
            llm_route_overruled=parsed.proposed_route != adjudicated.predicted_route,
            degraded_reasons=[],
        )

    def parse_or_fallback(
        self,
        question: str,
        context: BaseModel | Mapping[str, Any] | None,
        *,
        authoritative_object: Mapping[str, Any] | BaseModel | None = None,
    ) -> ParsedQuestionResult:
        try:
            return self.parse(
                question,
                context,
                authoritative_object=authoritative_object,
            )
        except (LLMProviderError, LLMConfigurationError, ValidationError) as exc:
            context_payload = _context_payload(context)
            resolved_object = _resolved_object(None, context_payload, authoritative_object)
            adjudicated = self._router({"user_question": question, "object": resolved_object})
            return ParsedQuestionResult(
                parsed=None,
                interpretation=None,
                adjudicated_route=adjudicated,
                route_payload=_route_payload(adjudicated),
                compliant_rewrite=_safe_rewrite("", adjudicated, resolved_object),
                llm_used=False,
                llm_route_overruled=False,
                degraded_reasons=[f"LLM 问题解析降级: {type(exc).__name__}"],
            )
