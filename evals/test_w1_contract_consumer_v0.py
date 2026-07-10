from __future__ import annotations

from answer_engine import card_calendar_regime_evidence
from evals.w1_contract_consumer_v0 import (
    load_fixture,
    load_schema,
    validate_definition,
)
from llm.composer import NarrativeComposer
from llm.parser import QuestionParser
from llm.providers import FakeLLMProvider
from llm.schemas import ParsedQuestion


def _parser_factory(response_model: type, payload: dict) -> dict:
    assert response_model is ParsedQuestion
    return {
        "normalized_question": payload["question"],
        "object_kind": "unknown",
        "object_ref": "pronoun",
        "intent": "clarify_object",
        "time_range": {"start": "", "end": ""},
        "dimensions": [],
        "ambiguities": ["缺少可绑定的股票或事件对象"],
        "candidate_topics": [],
        "proposed_route": "clarify",
        "compliant_rewrite": "",
    }


def test_frozen_w1_schema_and_request_fixture_are_consumable() -> None:
    schema = load_schema()
    request = load_fixture("research_request.json")

    assert schema["x-contract-version"] == "v8_copilot_api_contract_v0"
    validate_definition("ResearchRequest", request)


def test_parser_outputs_match_w1_interpretation_and_route_contracts() -> None:
    request = load_fixture("research_request.json")
    result = QuestionParser(
        FakeLLMProvider(response_factory=_parser_factory), model="fake"
    ).parse(
        request["question"],
        request["context"],
        authoritative_object=request["object"],
    )

    validate_definition("QuestionInterpretation", result.interpretation)
    validate_definition("RouteDecision", result.route_payload)
    assert result.adjudicated_route.predicted_route == "clarify"


def test_composer_claims_match_w1_verified_claim_contract() -> None:
    card = card_calendar_regime_evidence()
    row_id = card.body_rows[0]["row_id"]
    composer = NarrativeComposer(FakeLLMProvider(responses=[{
        "claims": [{
            "text": "该记录展示了历史证据等级和样本边界。",
            "claim_type": "fact",
            "backing": {"kind": "query_row", "ref": row_id},
        }]
    }]), model="fake")

    result = composer.compose(card)

    for claim in result.verified_claims_payload():
        validate_definition("VerifiedClaim", claim)
