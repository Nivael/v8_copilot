"""Provider-neutral LLM boundary for v8 Copilot."""

from .composer import NarrativeComposer, validate_claims_against_card
from .models import AnalysisClaimOutput, ClaimBatch, QuestionInterpretation
from .parser import ParsedQuestion, QuestionParser
from .providers import FakeLLMProvider, OpenAIResponsesProvider, ProviderUnavailable

__all__ = [
    "AnalysisClaimOutput",
    "ClaimBatch",
    "FakeLLMProvider",
    "NarrativeComposer",
    "OpenAIResponsesProvider",
    "ParsedQuestion",
    "ProviderUnavailable",
    "QuestionInterpretation",
    "QuestionParser",
    "validate_claims_against_card",
]
