from __future__ import annotations

import json
import os
import re
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from .models import ClaimBatch, QuestionInterpretation

T = TypeVar("T", bound=BaseModel)


class ProviderUnavailable(RuntimeError):
    """The optional narrative provider cannot be used; deterministic flow may continue."""


class StructuredLLMProvider(Protocol):
    provider_name: str

    def parse(self, *, response_model: type[T], instructions: str, payload: dict[str, Any]) -> T:
        ...


class FakeLLMProvider:
    """Deterministic provider used by tests and no-key local development."""

    provider_name = "fake"

    def __init__(self, failure: str | None = None) -> None:
        self.failure = failure

    def parse(self, *, response_model: type[T], instructions: str, payload: dict[str, Any]) -> T:
        if self.failure:
            raise ProviderUnavailable(f"fake provider failure: {self.failure}")
        if response_model is QuestionInterpretation:
            question = str(payload.get("question", ""))
            context = payload.get("research_context") or {}
            symbol_match = re.search(r"(?<!\d)(\d{6})(?!\d)", question)
            symbol = context.get("symbol") or (symbol_match.group(1) if symbol_match else None)
            topics = [
                topic for topic in ("重整", "公告", "股价", "控制权", "股东", "ST", "退市")
                if topic.lower() in question.lower()
            ]
            value = QuestionInterpretation(
                object_kind="stock" if symbol else "unknown",
                object_ref=symbol,
                intent="research_question",
                time_scope=(
                    f"{context.get('time_start') or ''}/{context.get('time_end') or ''}"
                    if context.get("time_start") or context.get("time_end") else None
                ),
                requested_dimensions=topics,
                ambiguities=[] if symbol or topics else ["未识别明确研究对象或主题"],
                candidate_topics=topics,
            )
            return value  # type: ignore[return-value]
        if response_model is ClaimBatch:
            existing = payload.get("existing_claims") or []
            if existing:
                return ClaimBatch.model_validate({"claims": existing})  # type: ignore[return-value]
            catalog = payload.get("backing_catalog") or []
            if not catalog:
                return ClaimBatch(claims=[])  # type: ignore[return-value]
            first = catalog[0]
            return ClaimBatch.model_validate({
                "claims": [{
                    "text": "本回答保留结构化证据菜单；结论边界以对应证据项为准。",
                    "claim_type": "caveat",
                    "backing": first,
                }]
            })  # type: ignore[return-value]
        raise TypeError(f"FakeLLMProvider 不支持模型: {response_model.__name__}")


class OpenAIResponsesProvider:
    """OpenAI Responses API Structured Outputs adapter.

    The adapter deliberately exposes no tools and never forwards raw token deltas.
    """

    provider_name = "openai"

    def __init__(self, *, api_key: str | None = None, model: str | None = None, client: Any = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("V8_OPENAI_MODEL")
        if not self.api_key:
            raise ProviderUnavailable("缺 OPENAI_API_KEY；确定性回答仍可运行")
        if not self.model:
            raise ProviderUnavailable("缺 V8_OPENAI_MODEL；不硬编码模型默认值")
        if client is not None:
            self.client = client
            return
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderUnavailable("未安装 openai SDK；请运行 uv sync --group dev") from exc
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
        if isinstance(parsed, response_model):
            return parsed
        return response_model.model_validate(parsed)
