"""LLM boundary for the v8 ST Research Copilot.

The public objects are loaded lazily so importing a leaf module such as
``llm.providers`` does not initialize the answer engine or require its frozen
release assets.  This matters for standalone maintenance and extraction jobs.
"""

from importlib import import_module
from typing import Any

__all__ = [
    "CompositionResult",
    "FakeLLMProvider",
    "NarrativeComposer",
    "OpenAIResponsesProvider",
    "ParsedQuestionResult",
    "QuestionParser",
]


_PUBLIC_IMPORTS = {
    "CompositionResult": ("llm.composer", "CompositionResult"),
    "NarrativeComposer": ("llm.composer", "NarrativeComposer"),
    "ParsedQuestionResult": ("llm.parser", "ParsedQuestionResult"),
    "QuestionParser": ("llm.parser", "QuestionParser"),
    "FakeLLMProvider": ("llm.providers", "FakeLLMProvider"),
    "OpenAIResponsesProvider": ("llm.providers", "OpenAIResponsesProvider"),
}


def __getattr__(name: str) -> Any:
    target = _PUBLIC_IMPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value
