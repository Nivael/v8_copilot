"""W0 bridge between the frozen W1 API and W2's validated LLM boundary."""
from __future__ import annotations

import os
from dataclasses import dataclass
from importlib.util import find_spec
from typing import cast

from api_contract import (
    QuestionInterpretation,
    ResearchRequest,
    ResearchResponse,
    SedimentationCandidate,
    VerifiedClaim,
)
from llm.composer import NarrativeComposer
from api_contract_v2 import ResearchNarrative
from llm.config import load_local_secrets
from llm.parser import ParsedQuestionResult, QuestionParser
from llm.providers import (
    FakeLLMProvider,
    OpenAIResponsesProvider,
    StructuredLLMProvider,
)
from orchestrator import orchestrate, orchestrate_with_card


@dataclass(frozen=True)
class LLMOrchestrationResult:
    response: ResearchResponse
    narrative: ResearchNarrative | None


def _model_for(provider: StructuredLLMProvider, model: str | None) -> str | None:
    if model:
        return model
    return "fake" if isinstance(provider, FakeLLMProvider) else None


def _public_degraded_reasons(
    parser_result: ParsedQuestionResult,
    composer_reasons: list[str],
    *,
    composer_has_narrative: bool,
) -> list[str]:
    reasons: list[str] = []
    if parser_result.degraded_reasons:
        reasons.append("LLM 问题解释不可用，已使用确定性路由。")
    if composer_reasons:
        reasons.append(
            "LLM 分析中的部分语句未通过证据校验，已剔除。"
            if composer_has_narrative
            else "LLM 分析叙述不可用，已保留确定性证据菜单。"
        )
    return reasons


def orchestrate_with_provider(
    request: ResearchRequest,
    provider: StructuredLLMProvider,
    *,
    model: str | None = None,
) -> ResearchResponse:
    return orchestrate_with_provider_result(request, provider, model=model).response


def orchestrate_with_provider_result(
    request: ResearchRequest,
    provider: StructuredLLMProvider,
    *,
    model: str | None = None,
) -> LLMOrchestrationResult:
    """Use W2 for interpretation/composition while keeping W1 routing final."""
    deterministic_request = request.model_copy(update={"llm_mode": "off"})
    deterministic, card = orchestrate_with_card(deterministic_request)
    resolved_model = _model_for(provider, model)

    parser_result = QuestionParser(provider, model=resolved_model).parse_or_fallback(
        request.question,
        request.context,
        authoritative_object=deterministic.interpretation.object,
    )
    interpretation = deterministic.interpretation
    if parser_result.interpretation is not None:
        interpretation = QuestionInterpretation.model_validate(
            parser_result.interpretation
        )

    answer_card = deterministic.answer_card
    claims = deterministic.claims
    composer_used = False
    composer_reasons: list[str] = []
    research_narrative: ResearchNarrative | None = None
    if card is not None:
        composition = NarrativeComposer(
            provider,
            model=resolved_model,
        ).compose_or_fallback(card)
        answer_card = composition.answer_card.to_dict()
        claims = [
            VerifiedClaim.model_validate(payload)
            for payload in composition.verified_claims_payload()
        ]
        composer_used = composition.llm_used
        composer_reasons = composition.degraded_reasons or []
        research_narrative = composition.research_narrative

    candidates = list(deterministic.sedimentation_candidates)
    if parser_result.compliant_rewrite:
        candidates.append(SedimentationCandidate(
            kind="question_card",
            reason=f"合规改写：{parser_result.compliant_rewrite}",
        ))

    reasons = [
        *deterministic.degraded_reasons,
        *_public_degraded_reasons(
            parser_result,
            composer_reasons,
            composer_has_narrative=research_narrative is not None,
        ),
    ]
    # Public llm_used describes the narrative visible to the researcher, not
    # an internal parser call that may have been overruled or discarded.
    llm_used = composer_used and research_narrative is not None
    response = deterministic.model_copy(update={
        "interpretation": interpretation,
        "answer_card": answer_card,
        "claims": claims,
        "sedimentation_candidates": candidates,
        "degraded": bool(reasons),
        "degraded_reasons": reasons,
        "llm_used": llm_used,
    })
    return LLMOrchestrationResult(response=response, narrative=research_narrative)


def openai_configured() -> bool:
    load_local_secrets()
    return bool(
        os.getenv("OPENAI_API_KEY")
        and os.getenv("V8_OPENAI_MODEL")
        and find_spec("openai") is not None
    )


def orchestrate_optional_llm(request: ResearchRequest) -> ResearchResponse:
    if request.llm_mode == "off":
        return orchestrate(request)
    return orchestrate_with_provider(
        request,
        cast(StructuredLLMProvider, OpenAIResponsesProvider()),
    )


def orchestrate_optional_llm_result(request: ResearchRequest) -> LLMOrchestrationResult:
    if request.llm_mode == "off":
        return LLMOrchestrationResult(response=orchestrate(request), narrative=None)
    return orchestrate_with_provider_result(
        request,
        cast(StructuredLLMProvider, OpenAIResponsesProvider()),
    )
