from __future__ import annotations

from contracts.v8_copilot_api_contract_v0.models import (
    QuestionInterpretation,
    ResearchObject,
    ResearchRequest,
    ValidatedClaim,
)

from .composer import NarrativeComposer
from .parser import QuestionParser
from .providers import StructuredLLMProvider


class OpenAIInterpretationProvider:
    """Adapts structured question parsing to the public contract."""

    available = True

    def __init__(self, provider: StructuredLLMProvider) -> None:
        self.parser = QuestionParser(provider)

    def interpret(
        self,
        *,
        request: ResearchRequest,
        deterministic: QuestionInterpretation,
    ) -> QuestionInterpretation:
        parsed = self.parser.parse(
            request.question,
            request.context.model_dump(mode="json") if request.context else {},
        ).interpretation
        research_object = deterministic.object
        if research_object.kind == "unknown" and parsed.object_ref:
            research_object = ResearchObject(kind="stock", ref=parsed.object_ref)
        return QuestionInterpretation(
            request_id=request.request_id,
            object=research_object,
            intent=parsed.intent,
            time_scope=deterministic.time_scope,
            requested_dimensions=parsed.requested_dimensions,
            ambiguities=parsed.ambiguities,
            candidate_topics=parsed.candidate_topics,
            generated_by="llm_validated",
        )


class OpenAINarrativeProvider:
    """Adapts validated structured claims to the public API claim type."""

    available = True

    def __init__(self, provider: StructuredLLMProvider) -> None:
        self.composer = NarrativeComposer(provider)

    def compose(self, *, request, answer_card, backing_catalog) -> list[ValidatedClaim]:
        claims = self.composer.compose(answer_card)
        return [
            ValidatedClaim(
                claim_id=f"claim-{index:03d}",
                **claim,
            )
            for index, claim in enumerate(claims, 1)
        ]
