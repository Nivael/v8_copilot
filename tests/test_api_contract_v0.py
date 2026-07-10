import json
from pathlib import Path

from jsonschema import Draft202012Validator

from contracts.v8_copilot_api_contract_v0.models import (
    QuestionInterpretation,
    ResearchContext,
    ResearchRequest,
    ResearchResponse,
    ResearchStreamEvent,
    RouteDecision,
    StockDossierPayload,
    public_contract_schema,
)


CONTRACT_DIR = (
    Path(__file__).resolve().parents[1]
    / "contracts/v8_copilot_api_contract_v0"
)


FIXTURE_MODELS = {
    "research_context.json": ("ResearchContext", ResearchContext),
    "research_request.json": ("ResearchRequest", ResearchRequest),
    "question_interpretation.json": ("QuestionInterpretation", QuestionInterpretation),
    "route_decision.json": ("RouteDecision", RouteDecision),
    "research_response.json": ("ResearchResponse", ResearchResponse),
    "stock_dossier_payload.json": ("StockDossierPayload", StockDossierPayload),
    "research_stream_event.json": ("ResearchStreamEvent", ResearchStreamEvent),
}


def test_checked_in_schema_matches_runtime_models() -> None:
    checked_in = json.loads((CONTRACT_DIR / "schema.json").read_text(encoding="utf-8"))
    generated = public_contract_schema()

    Draft202012Validator.check_schema(checked_in)
    assert checked_in == generated


def test_all_public_fixtures_pass_pydantic_and_json_schema() -> None:
    schema = json.loads((CONTRACT_DIR / "schema.json").read_text(encoding="utf-8"))
    definitions = schema["$defs"]

    for fixture_name, (definition_name, model) in FIXTURE_MODELS.items():
        payload = json.loads(
            (CONTRACT_DIR / "fixtures" / fixture_name).read_text(encoding="utf-8")
        )
        validated = model.model_validate(payload)
        assert validated.model_dump(mode="json", exclude_unset=False)

        fixture_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$ref": f"#/$defs/{definition_name}",
            "$defs": definitions,
        }
        Draft202012Validator(fixture_schema).validate(payload)


def test_response_requires_exactly_one_result_shape() -> None:
    fixture = json.loads(
        (CONTRACT_DIR / "fixtures/research_response.json").read_text(encoding="utf-8")
    )
    fixture["fallback"] = None

    try:
        ResearchResponse.model_validate(fixture)
    except ValueError as exc:
        assert "exactly one" in str(exc)
    else:
        raise AssertionError("ResearchResponse accepted no result")
