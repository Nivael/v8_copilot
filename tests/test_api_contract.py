import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api_contract import (
    API_CONTRACT_VERSION,
    QuestionInterpretation,
    ResearchRequest,
    ResearchResponse,
    ResearchStreamEvent,
    RouteDecision,
    StockDossierPayload,
    public_contract_schema,
)


CONTRACT_DIR = (
    Path(__file__).resolve().parents[1] / "contracts/v8_copilot_api_contract_v0"
)


def test_committed_schema_matches_pydantic_models() -> None:
    committed = json.loads((CONTRACT_DIR / "schema.json").read_text(encoding="utf-8"))

    assert committed == public_contract_schema()
    assert committed["x-contract-version"] == API_CONTRACT_VERSION
    for model_name in (
        "ResearchRequest",
        "QuestionInterpretation",
        "RouteDecision",
        "ResearchResponse",
        "StockDossierPayload",
        "ResearchStreamEvent",
    ):
        assert model_name in committed["$defs"]


@pytest.mark.parametrize(
    ("filename", "model"),
    [
        ("research_request.json", ResearchRequest),
        ("question_interpretation.json", QuestionInterpretation),
        ("route_decision.json", RouteDecision),
        ("research_response.json", ResearchResponse),
        ("stock_dossier_payload.json", StockDossierPayload),
    ],
)
def test_fixed_json_fixtures_validate(filename: str, model: type) -> None:
    payload = json.loads(
        (CONTRACT_DIR / "fixtures" / filename).read_text(encoding="utf-8")
    )

    parsed = model.model_validate(payload)
    assert parsed.contract_version == API_CONTRACT_VERSION


def test_fixed_ndjson_events_validate() -> None:
    rows = [
        json.loads(line)
        for line in (
            CONTRACT_DIR / "fixtures/research_stream_events.ndjson"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    events = [ResearchStreamEvent.model_validate(row) for row in rows]
    assert [event.sequence for event in events] == [1, 2, 3, 4]
    assert [event.event for event in events] == [
        "accepted", "interpreted", "routed", "completed"
    ]


def test_request_rejects_extra_fields_and_oversized_question() -> None:
    with pytest.raises(ValidationError):
        ResearchRequest.model_validate({"question": "测试", "unknown": True})
    with pytest.raises(ValidationError):
        ResearchRequest(question="问" * 4001)


def test_date_range_rejects_reversed_dates() -> None:
    with pytest.raises(ValidationError, match="start 不得晚于 end"):
        ResearchRequest.model_validate({
            "question": "测试时间范围",
            "context": {"date_range": {"start": "2026-07-11", "end": "2026-07-10"}},
        })


def test_contract_artifacts_have_no_machine_local_paths() -> None:
    for path in CONTRACT_DIR.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert "/Users/" not in text
            assert "/home/" not in text
