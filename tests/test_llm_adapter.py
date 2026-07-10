import pytest

from api_contract import ResearchRequest
from llm_adapter import (
    ClaimBatch,
    FakeLLMProvider,
    OpenAIResponsesProvider,
    ProviderUnavailable,
    orchestrate_with_provider,
)


def request() -> ResearchRequest:
    return ResearchRequest(
        question="重整投资人公开招募后，下一个公告节点通常多久？",
        object={"kind": "episode_type", "ref": "restructuring_investor_recruitment"},
        llm_mode="auto",
    )


def test_fake_provider_runs_full_validated_path() -> None:
    response = orchestrate_with_provider(request(), FakeLLMProvider())

    assert response.route.route == "answer_query"
    assert response.answer_card is not None
    assert response.llm_used is True
    assert response.degraded is False
    assert response.claims


def test_unbacked_claim_is_rejected() -> None:
    class BadProvider(FakeLLMProvider):
        def parse(self, *, response_model, instructions, payload):
            if response_model is ClaimBatch:
                return ClaimBatch.model_validate({"claims": [{
                    "text": "无来源结论",
                    "claim_type": "fact",
                    "backing_kind": "query_row",
                    "backing_ref": "missing",
                }]})
            return super().parse(response_model=response_model, instructions=instructions, payload=payload)

    with pytest.raises(ValueError, match="backing 无对应对象"):
        orchestrate_with_provider(request(), BadProvider())


def test_parser_payload_does_not_receive_answer_card() -> None:
    seen = []

    class InspectingProvider(FakeLLMProvider):
        def parse(self, *, response_model, instructions, payload):
            seen.append((response_model.__name__, set(payload)))
            return super().parse(response_model=response_model, instructions=instructions, payload=payload)

    orchestrate_with_provider(request(), InspectingProvider())
    assert seen[0] == ("QuestionInterpretationDraft", {"question", "context"})
    assert "source_freshness" not in seen[1][1]


def test_openai_provider_requires_explicit_configuration(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("V8_OPENAI_MODEL", raising=False)
    with pytest.raises(ProviderUnavailable, match="OPENAI_API_KEY"):
        OpenAIResponsesProvider()
    with pytest.raises(ProviderUnavailable, match="V8_OPENAI_MODEL"):
        OpenAIResponsesProvider(api_key="test")
