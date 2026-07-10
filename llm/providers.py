from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Protocol, TypeVar

from pydantic import BaseModel

from llm.config import load_local_secrets


TModel = TypeVar("TModel", bound=BaseModel)
ResponseFactory = Callable[[type[BaseModel], dict[str, Any]], BaseModel | dict[str, Any]]


class LLMProviderError(RuntimeError):
    pass


class StructuredLLMProvider(Protocol):
    def generate(
        self,
        *,
        response_model: type[TModel],
        system_prompt: str,
        payload: dict[str, Any],
        model: str,
    ) -> TModel: ...


@dataclass(frozen=True)
class ProviderCall:
    response_model: type[BaseModel]
    system_prompt: str
    payload: dict[str, Any]
    model: str


@dataclass(frozen=True)
class GenerationMetadata:
    provider: str
    requested_model: str
    response_model: str
    response_id: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None


class FakeLLMProvider:
    """Schema-validating offline provider for tests and deterministic evals."""

    def __init__(
        self,
        responses: list[BaseModel | dict[str, Any]] | None = None,
        *,
        response_factory: ResponseFactory | None = None,
    ) -> None:
        if responses is not None and response_factory is not None:
            raise ValueError("responses 与 response_factory 只能提供一个")
        self._responses = list(responses or [])
        self._response_factory = response_factory
        self.calls: list[ProviderCall] = []
        self.last_generation: GenerationMetadata | None = None

    def generate(
        self,
        *,
        response_model: type[TModel],
        system_prompt: str,
        payload: dict[str, Any],
        model: str,
    ) -> TModel:
        self.calls.append(ProviderCall(response_model, system_prompt, payload, model))
        if self._response_factory is not None:
            raw = self._response_factory(response_model, payload)
        elif self._responses:
            raw = self._responses.pop(0)
        else:
            raise LLMProviderError("FakeLLMProvider 没有可用响应")
        parsed = response_model.model_validate(raw)
        self.last_generation = GenerationMetadata(
            provider="fake",
            requested_model=model,
            response_model=model,
        )
        return parsed


class OpenAIResponsesProvider:
    """OpenAI Responses API adapter using native Pydantic Structured Outputs."""

    def __init__(
        self,
        *,
        client: Any | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self.last_generation: GenerationMetadata | None = None

    def _client_instance(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI

                if self._api_key is None:
                    load_local_secrets()
                self._client = OpenAI(
                    api_key=self._api_key,
                    timeout=self._timeout_seconds,
                )
            except Exception as exc:
                raise LLMProviderError(
                    f"OpenAI client 初始化失败: {type(exc).__name__}"
                ) from exc
        return self._client

    def generate(
        self,
        *,
        response_model: type[TModel],
        system_prompt: str,
        payload: dict[str, Any],
        model: str,
    ) -> TModel:
        try:
            user_content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise LLMProviderError(f"Structured Outputs payload 无法序列化: {exc}") from exc

        try:
            response = self._client_instance().responses.parse(
                model=model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                text_format=response_model,
                store=False,
            )
        except Exception as exc:
            raise LLMProviderError(
                f"Responses API 调用失败: {type(exc).__name__}"
            ) from exc
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise LLMProviderError("Responses API 未返回 output_parsed；拒绝解析自由文本 JSON")
        usage = getattr(response, "usage", None)
        self.last_generation = GenerationMetadata(
            provider="openai",
            requested_model=model,
            response_model=str(getattr(response, "model", model)),
            response_id=str(getattr(response, "id", "")),
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )
        return response_model.model_validate(parsed)
