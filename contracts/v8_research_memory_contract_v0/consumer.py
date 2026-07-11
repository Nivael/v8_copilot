"""Read-only validation helpers for W0/W2/W3 contract consumers."""
from __future__ import annotations

import json
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import BaseModel, ValidationError


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from research_memory_contract import (
    QUESTION_DIMENSION_ALIASES,
    QUESTION_INTENT_ALIASES,
    QUESTION_SEMANTIC_REGISTRY_VERSION,
    PROVISIONAL_QUESTION_IDENTITY_VERSION,
    PROVISIONAL_QUESTION_NORMALIZATION_VERSION,
    REVIEW_ACTIVE_LIMIT,
    DataDebtCard,
    FeedbackEvent,
    MemoryLink,
    PUBLIC_MEMORY_ADAPTER,
    QueryTemplateRecord,
    QuestionDimension,
    QuestionCard,
    QuestionIntent,
    ResearchRunRef,
    ReviewItem,
    SedimentationResult,
    StatusTransition,
    SourceRef,
    ProvenanceRef,
    build_question_card,
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
    "question_card_post_v7_backlog.json": QuestionCard,
    "question_card_provisional_unknown.json": QuestionCard,
    "question_card_provisional_ignored.json": QuestionCard,
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
DEFINITION_BY_FIXTURE = {
    "question_card.json": "QuestionCard",
    "question_card_post_v7_backlog.json": "QuestionCard",
    "question_card_provisional_unknown.json": "QuestionCard",
    "question_card_provisional_ignored.json": "QuestionCard",
    "data_debt_assigned.json": "DataDebtCard",
    "data_debt_unassigned.json": "DataDebtCard",
    "query_template_record.json": "QueryTemplateRecord",
    "review_item.json": "ReviewItem",
    "feedback_event.json": "FeedbackEvent",
    "memory_link.json": "MemoryLink",
    "research_run_ref.json": "ResearchRunRef",
    "status_transition.json": "StatusTransition",
    "sedimentation_result.json": "SedimentationResult",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def validate_public_payload(payload: dict[str, Any]) -> None:
    schema = read_json(HERE / "schema.json")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
    PUBLIC_MEMORY_ADAPTER.validate_python(payload)


def validate_schema() -> None:
    committed = read_json(HERE / "schema.json")
    assert committed == public_contract_schema(), "committed schema differs from Python types"
    Draft202012Validator.check_schema(committed)
    validator = Draft202012Validator(committed, format_checker=FormatChecker())
    try:
        validator.validate({})
    except JsonSchemaValidationError:
        pass
    else:
        raise AssertionError("public root schema unexpectedly accepted an empty object")
    question = read_json(HERE / "fixtures/valid/question_card.json")
    for required_field in ("record_type", "contract_version", "not_evidence"):
        missing = dict(question)
        missing.pop(required_field)
        try:
            validator.validate(missing)
        except JsonSchemaValidationError:
            continue
        raise AssertionError(f"public root schema allowed missing {required_field}")


def validate_valid_fixtures() -> None:
    fixture_dir = HERE / "fixtures/valid"
    validator = Draft202012Validator(
        read_json(HERE / "schema.json"), format_checker=FormatChecker()
    )
    for filename, model in VALID_FIXTURES.items():
        payload = read_json(fixture_dir / filename)
        validator.validate(payload)
        definition_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$defs": read_json(HERE / "schema.json")["$defs"],
            "$ref": f"#/$defs/{DEFINITION_BY_FIXTURE[filename]}",
        }
        Draft202012Validator(
            definition_schema, format_checker=FormatChecker()
        ).validate(payload)
        PUBLIC_MEMORY_ADAPTER.validate_python(payload)
        model.model_validate(payload)


def validate_invalid_fixtures() -> None:
    validator = Draft202012Validator(
        read_json(HERE / "schema.json"), format_checker=FormatChecker()
    )
    for path in sorted((HERE / "fixtures/invalid").glob("*.json")):
        case = read_json(path)
        model = MODEL_BY_NAME[case["model"]]
        schema_rejected = False
        try:
            validator.validate(case["payload"])
        except JsonSchemaValidationError:
            schema_rejected = True
        pydantic_rejected = False
        try:
            model.model_validate(case["payload"])
        except ValidationError:
            pydantic_rejected = True
        assert pydantic_rejected, f"invalid fixture passed Pydantic: {path.name}"
        if case.get("schema_must_reject"):
            assert schema_rejected, f"invalid fixture passed JSON Schema: {path.name}"


def validate_key_cases() -> None:
    cases = read_json(HERE / "fixtures/key_cases.json")
    model_for_case = {
        "synonym_different_runs": QuestionCard,
        "seed_and_online_semantic_equivalence": QuestionCard,
        "registered_semantic_alias_equivalence": QuestionCard,
        "provisional_unknown_retry_stability": QuestionCard,
        "provisional_unknown_question_separation": QuestionCard,
        "same_gap_different_scope": DataDebtCard,
        "assigned_debt_same_ref_changed_description": DataDebtCard,
        "assigned_debt_different_ref": DataDebtCard,
        "normalized_arrays_and_symbols": QuestionCard,
        "different_time_semantics": QuestionCard,
        "different_dimensions": QuestionCard,
        "query_template_semantic_collision_guard": QueryTemplateRecord,
        "review_same_decision_unit_changed_package": ReviewItem,
        "review_different_decision_unit": ReviewItem,
        "feedback_same_target_changed_wording": FeedbackEvent,
        "feedback_different_research_run": FeedbackEvent,
    }
    for name, model in model_for_case.items():
        case = cases[name]
        first = model.model_validate(case["first"])
        second = model.model_validate(case["second"])
        validate_public_payload(case["first"])
        validate_public_payload(case["second"])
        actual_same = first.dedupe_key == second.dedupe_key
        assert actual_same is case["expect_same_dedupe_key"], name
        if case.get("expect_different_source_refs"):
            assert first.source_refs != second.source_refs, name

    title_case = cases["llm_title_changes"]
    card = QuestionCard.model_validate(title_case["semantic_record"])
    validate_public_payload(title_case["semantic_record"])
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
    record_payloads = read_json(fixture_dir / "expected_records.json")
    records = [QuestionCard.model_validate(row) for row in record_payloads]
    for row in record_payloads:
        validate_public_payload(row)
    assert len(source_rows) == len(records) == manifest["seed_count"] == 15
    by_external_id = {record.external_qc_id: record for record in records}
    semantics = read_json(fixture_dir / "semantic_mapping.json")
    assert set(semantics) == set(by_external_id)
    assert len({record.dedupe_key for record in records}) == len(records)
    for row in source_rows:
        record = by_external_id[row["id"]]
        semantic = semantics[row["id"]]
        assert record.canonical_question == row["question"]
        assert record.scope.kind == row["object"]["kind"]
        assert record.research_status == row["status"]
        assert record.view == row["view"]
        assert record.external_debt_ref == (row["debt_ref"] or None)
        assert record.debt_ref_status == row["debt_ref_status"]
        assert record.original_source == row["source"]
        assert record.semantic_intent.value == semantic["intent"]
        assert [item.value for item in record.dimensions] == sorted(
            semantic["dimensions"]
        )
        online_equivalent = build_question_card(
            canonical_question="equivalent online wording",
            scope=record.scope,
            semantic_intent=record.semantic_intent,
            dimensions=record.dimensions,
            time_scope=record.time_scope,
            needs_data=["runtime_availability_may_differ"],
            research_status=record.research_status,
            view="query",
            original_source="user",
            debt_ref_status="not_required",
            status="candidate",
            created_at=record.created_at,
            updated_at=record.updated_at,
            source_refs=[
                SourceRef(source_type="research_run", source_ref=f"online:{row['id']}")
            ],
            provenance_refs=[
                ProvenanceRef(
                    provenance_type="research_response",
                    provenance_ref=f"online:{row['id']}",
                )
            ],
        )
        assert online_equivalent.dedupe_key == record.dedupe_key
        assert row["id"].casefold() not in record.canonical_key

    first = SedimentationResult.model_validate(read_json(fixture_dir / "first_import_result.json"))
    second = SedimentationResult.model_validate(read_json(fixture_dir / "second_import_result.json"))
    validate_public_payload(first.model_dump(mode="json"))
    validate_public_payload(second.model_dump(mode="json"))
    assert len(first.created) == 15 and not first.existing
    assert not first.merged and not first.ignored
    assert not second.created and len(second.existing) == 15
    assert not second.merged and not second.ignored
    assert first.created == second.existing


def validate_query_template_registry() -> None:
    registry = {
        row["template_id"]: row
        for row in read_json(ROOT / "contracts/v8_query_template_contract_v0/registry.json")
    }
    record_payloads = read_json(HERE / "fixtures/query_template_records.json")
    records = [
        QueryTemplateRecord.model_validate(row)
        for row in record_payloads
    ]
    for row in record_payloads:
        validate_public_payload(row)
    assert {record.template_id for record in records} == set(registry) == {
        f"QT-{index:03d}" for index in range(1, 9)
    }
    for record in records:
        assert record.not_evidence is True
        assert record.executor_ref is not None
        assert record.executor_ref.executor_key == registry[record.template_id]["executor_key"]


def validate_question_semantic_registry() -> None:
    registry = read_json(HERE / "question_semantic_registry.json")
    assert registry["registry_version"] == QUESTION_SEMANTIC_REGISTRY_VERSION
    assert set(registry["intents"]) == {item.value for item in QuestionIntent}
    assert set(registry["dimensions"]) == {item.value for item in QuestionDimension}
    assert registry["intent_aliases"] == {
        alias: target.value for alias, target in QUESTION_INTENT_ALIASES.items()
    }
    assert registry["dimension_aliases"] == {
        alias: target.value for alias, target in QUESTION_DIMENSION_ALIASES.items()
    }
    assert registry["unknown_value_policy"] == "reject"
    assert registry["unknown_question_intake"] == {
        "intent": "unknown_research_question",
        "identity_kind": "provisional_unknown",
        "identity_version": PROVISIONAL_QUESTION_IDENTITY_VERSION,
        "normalization_version": PROVISIONAL_QUESTION_NORMALIZATION_VERSION,
        "builder_status": "candidate",
        "human_terminal_statuses": ["ignored", "merged"],
        "required_research_status": "needs_review",
    }
    assert registry["mapping_authority"] == "deterministic_sedimenter"


def validate_post_v7_backlog_fixture() -> None:
    payload = read_json(HERE / "fixtures/valid/question_card_post_v7_backlog.json")
    card = QuestionCard.model_validate(payload)
    validate_public_payload(payload)
    assert card.original_source == "post_v7_backlog"
    assert any(ref.source_type == "post_v7_backlog" for ref in card.source_refs)


def validate_provisional_unknown_fixture() -> None:
    payload = read_json(
        HERE / "fixtures/valid/question_card_provisional_unknown.json"
    )
    card = QuestionCard.model_validate(payload)
    validate_public_payload(payload)
    assert card.identity_kind == "provisional_unknown"
    assert card.provisional_identity is not None
    assert card.status == "candidate"
    assert card.research_status == "needs_review"
    canonical = json.loads(card.canonical_key)
    assert canonical["kind"] == "provisional_question"
    assert "normalized_question" not in canonical
    ignored_payload = read_json(
        HERE / "fixtures/valid/question_card_provisional_ignored.json"
    )
    ignored = QuestionCard.model_validate(ignored_payload)
    validate_public_payload(ignored_payload)
    transition = StatusTransition.model_validate(
        read_json(HERE / "fixtures/status_transitions.json")[
            "valid_human_candidate_ignore"
        ]
    )
    assert ignored.status == transition.to_status == "ignored"
    assert transition.actor_type == "human"


def validate_feedback_taxonomy() -> None:
    payloads = read_json(HERE / "fixtures/feedback_taxonomy.json")
    events = [FeedbackEvent.model_validate(payload) for payload in payloads]
    for payload in payloads:
        validate_public_payload(payload)
    assert {event.feedback_kind for event in events} == {
        "useful",
        "not_useful",
        "scope_error",
        "missing_evidence",
        "wording_issue",
        "other",
    }
    assert {"research_run", "answer_card"} <= {
        event.target_type for event in events
    }


def validate_review_capacity_fixture() -> None:
    fixture = read_json(HERE / "fixtures/review_capacity.json")
    assert fixture["max_active_items"] == REVIEW_ACTIVE_LIMIT == 20
    items = [ReviewItem.model_validate(item) for item in fixture["active_items"]]
    for item in fixture["active_items"]:
        validate_public_payload(item)
    assert len(items) == REVIEW_ACTIVE_LIMIT
    assert all(item.active for item in items)
    assert len({item.memory_id for item in items}) == REVIEW_ACTIVE_LIMIT


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


def validate_transition_fixtures() -> None:
    fixture = read_json(HERE / "fixtures/status_transitions.json")
    for name in (
        "valid_human_merge",
        "valid_human_candidate_merge",
        "valid_human_candidate_ignore",
        "valid_seed_migration_acceptance",
    ):
        payload = fixture[name]
        validate_public_payload(payload)
        StatusTransition.model_validate(payload)


def validate_all() -> None:
    validate_schema()
    validate_valid_fixtures()
    validate_invalid_fixtures()
    validate_key_cases()
    validate_seed_migration()
    validate_query_template_registry()
    validate_question_semantic_registry()
    validate_post_v7_backlog_fixture()
    validate_provisional_unknown_fixture()
    validate_feedback_taxonomy()
    validate_review_capacity_fixture()
    validate_transition_fixtures()
    validate_protected_contract_checksums()
    validate_route_seed_coverage()


if __name__ == "__main__":
    validate_all()
