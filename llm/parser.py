from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evals.deterministic_router_v0 import RoutePrediction, route_question

from .models import QuestionInterpretation, ResearchContextInput
from .providers import StructuredLLMProvider


PARSER_INSTRUCTIONS = """你只负责把研究问题解释成结构化意图。
不得补充事实、数字、日期结论、证据等级或投资建议。歧义必须显式列出。
candidate_topics 只是检索提示，最终路由由确定性引擎裁决。"""


@dataclass(frozen=True)
class ParsedQuestion:
    interpretation: QuestionInterpretation
    route: RoutePrediction


class QuestionParser:
    def __init__(self, provider: StructuredLLMProvider) -> None:
        self.provider = provider

    def parse(self, question: str, research_context: dict[str, Any] | None = None) -> ParsedQuestion:
        context = ResearchContextInput.model_validate(research_context or {})
        interpretation = self.provider.parse(
            response_model=QuestionInterpretation,
            instructions=PARSER_INSTRUCTIONS,
            payload={
                "question": question,
                "research_context": context.model_dump(mode="json"),
            },
        )
        object_kind = interpretation.object_kind
        object_ref = interpretation.object_ref
        row = {
            "user_question": question,
            "object": {"kind": object_kind, "ref": object_ref or ""},
        }
        route = route_question(row)
        return ParsedQuestion(interpretation=interpretation, route=route)
