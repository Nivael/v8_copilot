import json
from pathlib import Path

from api_contract_v1 import (
    NavigationRef,
    ResearchResponseV1,
    ResearchStreamEventV1,
    public_contract_schema_v1,
)
from query_templates import QueryTemplate, TEMPLATES
from question_cards import QuestionCard


ROOT = Path(__file__).resolve().parents[1]


def test_committed_closeout_schemas_match_models() -> None:
    api_dir = ROOT / "contracts/v8_copilot_api_contract_v1"
    question_dir = ROOT / "contracts/v8_question_card_contract_v0"
    template_dir = ROOT / "contracts/v8_query_template_contract_v0"

    assert json.loads((api_dir / "schema.json").read_text()) == public_contract_schema_v1()
    QuestionCard.model_validate(json.loads((question_dir / "fixture.json").read_text()))
    for template in json.loads((template_dir / "registry.json").read_text()):
        QueryTemplate.model_validate(template)
    assert len(TEMPLATES) == 9


def test_api_v1_fixtures_validate() -> None:
    fixture_dir = ROOT / "contracts/v8_copilot_api_contract_v1/fixtures"

    ResearchResponseV1.model_validate(
        json.loads((fixture_dir / "research_response.json").read_text())
    )
    NavigationRef.model_validate(
        json.loads((fixture_dir / "navigation_ref.json").read_text())
    )
    QuestionCard.model_validate(
        json.loads((fixture_dir / "question_card.json").read_text())
    )
    ResearchStreamEventV1.model_validate_json(
        (fixture_dir / "stream.ndjson").read_text().strip()
    )


def test_v0_contract_artifacts_remain_unchanged_by_v1_export() -> None:
    manifest = json.loads((
        ROOT / "contracts/v8_copilot_api_contract_v0/manifest.json"
    ).read_text())

    assert manifest["contract_version"] == "v8_copilot_api_contract_v0"
