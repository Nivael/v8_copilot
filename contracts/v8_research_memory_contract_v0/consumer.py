"""Read-only validation helpers for W0/W2/W3 contract consumers."""
from __future__ import annotations

import json
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ValidationError


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from research_memory_contract import (
    REVIEW_ACTIVE_LIMIT,
    DataDebtCard,
    FeedbackEvent,
    MemoryLink,
    QueryTemplateRecord,
    QuestionCard,
    ResearchRunRef,
    ReviewItem,
    SedimentationResult,
    StatusTransition,
    public_contract_schema,
)


MODEL_BY_NAME: dict[str, type[BaseModel]] = {
    "QuestionCard": QuestionCard,
    "DataDebtCard": DataDebtCard,
    "QueryTemplateRecord": QueryTemplateRecord,
    "ReviewItem": ReviewItem,
    "FeedbackEvent": FeedbackEvent,
    "MemoryLink": MemoryLink,
    "ResearchRunRef": ResearchRunRef,
    "StatusTransition": StatusTransition,
    "SedimentationResult": SedimentationResult,
}

VALID_FIXTURES = {
    "question_card.json": QuestionCard,
    "data_debt_assigned.json": DataDebtCard,
    "data_debt_unassigned.json": DataDebtCard,
    "query_template_record.json": QueryTemplateRecord,
    "review_item.json": ReviewItem,
    "feedback_event.json": FeedbackEvent,
    "memory_link.json": MemoryLink,
    "research_run_ref.json": ResearchRunRef,
    "status_transition.json": StatusTransition,
    "sedimentation_result.json": SedimentationResult,
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def validate_schema() -> None:
    committed = read_json(HERE / "schema.json")
    assert committed == public_contract_schema(), "committed schema differs from Python types"
    Draft202012Validator.check_schema(committed)


def validate_valid_fixtures() -> None:
    fixture_dir = HERE / "fixtures/valid"
    for filename, model in VALID_FIXTURES.items():
        model.model_validate(read_json(fixture_dir / filename))


def validate_invalid_fixtures() -> None:
    for path in sorted((HERE / "fixtures/invalid").glob("*.json")):
        case = read_json(path)
        model = MODEL_BY_NAME[case["model"]]
        try:
            model.model_validate(case["payload"])
        except ValidationError:
            continue
        raise AssertionError(f"invalid fixture unexpectedly passed: {path.name}")


def validate_key_cases() -> None:
    cases = read_json(HERE / "fixtures/key_cases.json")
    model_for_case = {
        "synonym_different_runs": QuestionCard,
        "same_gap_different_scope": DataDebtCard,
        "normalized_arrays_and_symbols": QuestionCard,
        "different_time_semantics": QuestionCard,
    }
    for name, model in model_for_case.items():
        case = cases[name]
        first = model.model_validate(case["first"])
        second = model.model_validate(case["second"])
        actual_same = first.dedupe_key == second.dedupe_key
        assert actual_same is case["expect_same_dedupe_key"], name
        if case.get("expect_different_source_refs"):
            assert first.source_refs != second.source_refs, name

    title_case = cases["llm_title_changes"]
    card = QuestionCard.model_validate(title_case["semantic_record"])
    assert title_case["title_is_not_contract_input"] is True
    assert card.dedupe_key == title_case["expected_dedupe_key"]


def validate_seed_migration() -> None:
    fixture_dir = HERE / "fixtures/seed_migration"
    manifest = read_json(HERE / "manifest.json")
    source_seed = ROOT / "evals/question_card_seeds_v0.jsonl"
    fixture_seed = fixture_dir / "question_card_seeds_v0.jsonl"
    assert file_sha256(source_seed) == manifest["seed_sha256"]
    assert file_sha256(fixture_seed) == manifest["seed_sha256"]

    source_rows = [json.loads(line) for line in source_seed.read_text(encoding="utf-8").splitlines()]
    records = [QuestionCard.model_validate(row) for row in read_json(fixture_dir / "expected_records.json")]
    assert len(source_rows) == len(records) == manifest["seed_count"] == 15
    by_external_id = {record.external_qc_id: record for record in records}
    for row in source_rows:
        record = by_external_id[row["id"]]
        assert record.canonical_question == row["question"]
        assert record.scope.kind == row["object"]["kind"]
        assert record.research_status == row["status"]
        assert record.view == row["view"]
        assert record.external_debt_ref == (row["debt_ref"] or None)
        assert record.debt_ref_status == row["debt_ref_status"]
        assert record.original_source == row["source"]

    first = SedimentationResult.model_validate(read_json(fixture_dir / "first_import_result.json"))
    second = SedimentationResult.model_validate(read_json(fixture_dir / "second_import_result.json"))
    assert len(first.created_ids) == 15 and not first.existing_ids
    assert not second.created_ids and len(second.existing_ids) == 15
    assert first.created_ids == second.existing_ids


def validate_query_template_registry() -> None:
    registry = {
        row["template_id"]: row
        for row in read_json(ROOT / "contracts/v8_query_template_contract_v0/registry.json")
    }
    records = [
        QueryTemplateRecord.model_validate(row)
        for row in read_json(HERE / "fixtures/query_template_records.json")
    ]
    assert {record.template_id for record in records} == set(registry) == {
        f"QT-{index:03d}" for index in range(1, 9)
    }
    for record in records:
        assert record.not_evidence is True
        assert record.executor_ref is not None
        assert record.executor_ref.executor_key == registry[record.template_id]["executor_key"]


def validate_review_capacity_fixture() -> None:
    fixture = read_json(HERE / "fixtures/review_capacity.json")
    assert fixture["max_active_items"] == REVIEW_ACTIVE_LIMIT == 20
    assert len(fixture["active_item_ids"]) == REVIEW_ACTIVE_LIMIT
    assert len(set(fixture["active_item_ids"])) == REVIEW_ACTIVE_LIMIT


def validate_protected_contract_checksums() -> None:
    checksums = read_json(HERE / "manifest.json")["protected_contract_checksums"]
    for relative_path, expected in checksums.items():
        assert file_sha256(ROOT / relative_path) == expected, relative_path


def validate_route_seed_coverage() -> None:
    seed_ids = set(read_json(HERE / "fixtures/seed_migration/seed_summary.json")["external_qc_ids"])
    route_refs: set[str] = set()
    route_path = ROOT / "evals/question_routing_set_v0.jsonl"
    for line in route_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        route_refs.update(ref for ref in row["required_question_card_refs"] if ref.startswith("QC-20260710-"))
    assert route_refs == seed_ids


def validate_all() -> None:
    validate_schema()
    validate_valid_fixtures()
    validate_invalid_fixtures()
    validate_key_cases()
    validate_seed_migration()
    validate_query_template_registry()
    validate_review_capacity_fixture()
    validate_protected_contract_checksums()
    validate_route_seed_coverage()


if __name__ == "__main__":
    validate_all()
