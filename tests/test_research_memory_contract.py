import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError

from research_memory_contract import (
    QUESTION_SEMANTIC_REGISTRY_VERSION,
    STATUS_TRANSITIONS,
    DataDebtCard,
    ExecutorRef,
    FeedbackEvent,
    ObjectScope,
    ProvenanceRef,
    QueryParameterSpec,
    ResearchRunRef,
    ReviewItem,
    SedimentationResult,
    QuestionCard,
    SourceRef,
    StatusTransition,
    TimeScope,
    build_data_debt_card,
    build_feedback_event,
    build_query_template_record,
    build_question_card,
    normalize_symbol,
    public_contract_schema,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts/v8_research_memory_contract_v0"
STAMP = datetime(2026, 7, 11, tzinfo=timezone.utc)


def load_consumer():
    spec = importlib.util.spec_from_file_location("memory_contract_consumer", CONTRACT / "consumer.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source(ref: str) -> list[SourceRef]:
    return [SourceRef(source_type="research_response", source_ref=ref)]


def provenance(ref: str) -> list[ProvenanceRef]:
    return [ProvenanceRef(provenance_type="research_response", provenance_ref=ref)]


def test_all_committed_contract_artifacts_validate() -> None:
    load_consumer().validate_all()


def test_export_is_deterministic_and_revalidates() -> None:
    before = {
        path.relative_to(CONTRACT): path.read_bytes()
        for path in CONTRACT.rglob("*")
        if path.is_file() and path.name not in {"export_contract.py", "consumer.py", "README.md"}
    }

    subprocess.run(
        [sys.executable, str(CONTRACT / "export_contract.py")],
        cwd=ROOT,
        check=True,
    )

    after = {
        path.relative_to(CONTRACT): path.read_bytes()
        for path in CONTRACT.rglob("*")
        if path.is_file() and path.name not in {"export_contract.py", "consumer.py", "README.md"}
    }
    assert after == before
    load_consumer().validate_all()


@pytest.mark.parametrize("value", ["603398", "SH.603398", "603398.SH", "sh-603398"])
def test_symbol_normalization_is_stable(value: str) -> None:
    assert normalize_symbol(value) == "603398"


def test_natural_language_and_run_identity_do_not_enter_question_dedupe() -> None:
    base = {
        "scope": ObjectScope(kind="stock", refs=["603398.SH"]),
        "semantic_intent": "stock_observation_windows",
        "dimensions": ["price", "episode"],
        "needs_data": ["episode_index", "daily_prices"],
        "research_status": "answerable",
        "view": "checklist",
        "original_source": "user",
        "status": "candidate",
        "created_at": STAMP,
        "updated_at": STAMP,
        "provenance_refs": provenance("response-shared"),
    }
    first = build_question_card(
        canonical_question="沐邦后面看什么？",
        source_refs=[SourceRef(source_type="research_run", source_ref="run-a")],
        **base,
    )
    second = build_question_card(
        canonical_question="沐邦后面看什么？",
        needs_data=["changed_availability_note"],
        view="query",
        source_refs=[
            SourceRef(
                source_type="answer_card",
                source_ref="card-z",
                source_alias="603398 有哪些公开观察窗口？",
            )
        ],
        **{key: value for key, value in base.items() if key not in {"needs_data", "view"}},
    )

    assert first.memory_id == second.memory_id
    assert first.dedupe_key == second.dedupe_key
    assert first.source_refs != second.source_refs
    assert "run-a" not in first.canonical_key
    assert "card-z" not in second.canonical_key
    assert first.canonical_question not in first.canonical_key
    assert second.source_refs[0].source_alias not in second.canonical_key


def test_qc_candidate_is_source_only_not_memory_identity() -> None:
    card = build_question_card(
        external_qc_id="QC-CAND-0123456789ab",
        canonical_question="未知问题",
        scope=ObjectScope(kind="unknown", refs=["unknown"]),
        semantic_intent="unknown_research_question",
        research_status="needs_review",
        view="query",
        original_source="system_gap",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[SourceRef(source_type="system_gap", source_ref="QC-CAND-0123456789ab")],
        provenance_refs=[ProvenanceRef(provenance_type="research_response", provenance_ref="response-x")],
    )

    assert card.memory_id.startswith("MEM-QC-")
    assert "QC-CAND" not in card.canonical_key


def test_fixed_seed_and_online_question_share_semantic_identity() -> None:
    common = {
        "scope": ObjectScope(kind="stock", refs=["603398"]),
        "semantic_intent": "stock_observation_windows",
        "dimensions": ["price", "episode"],
        "needs_data": ["daily_prices", "episode_index"],
        "research_status": "answerable",
        "view": "checklist",
        "original_source": "slice",
        "status": "accepted",
        "created_at": STAMP,
        "updated_at": STAMP,
    }
    seed = build_question_card(
        external_qc_id="QC-20260710-015",
        canonical_question="沐邦(603398)平台整理两个月该看哪些窗口？",
        source_refs=[SourceRef(source_type="seed_fixture", source_ref="seed")],
        provenance_refs=[
            ProvenanceRef(provenance_type="seed_fixture", provenance_ref="seed")
        ],
        **common,
    )
    online = build_question_card(
        canonical_question="603398 后面应该观察什么？",
        original_source="user",
        status="candidate",
        source_refs=[SourceRef(source_type="research_run", source_ref="run-online")],
        provenance_refs=provenance("response-online"),
        **{key: value for key, value in common.items() if key not in {"original_source", "status"}},
    )

    assert seed.dedupe_key == online.dedupe_key
    assert seed.memory_id == online.memory_id
    assert "qc-20260710-015" not in seed.canonical_key
    assert json.loads(seed.canonical_key)["intent"] == "stock_observation_windows"


def test_registered_question_semantic_aliases_collapse_to_same_key() -> None:
    common = {
        "canonical_question": "观察窗口",
        "scope": ObjectScope(kind="stock", refs=["603398"]),
        "research_status": "answerable",
        "view": "checklist",
        "original_source": "user",
        "status": "candidate",
        "created_at": STAMP,
        "updated_at": STAMP,
        "source_refs": source("semantic-alias"),
        "provenance_refs": provenance("semantic-alias"),
    }
    canonical = build_question_card(
        semantic_intent="stock_observation_windows",
        dimensions=["price", "episode"],
        **common,
    )
    aliases = build_question_card(
        semantic_intent="stock_monitoring_windows",
        dimensions=["daily_prices", "episode_index"],
        **common,
    )

    assert canonical.dedupe_key == aliases.dedupe_key
    assert aliases.semantic_intent.value == "stock_observation_windows"
    assert [item.value for item in aliases.dimensions] == ["episode", "price"]
    assert aliases.semantic_registry_version == QUESTION_SEMANTIC_REGISTRY_VERSION


@pytest.mark.parametrize(
    ("intent", "dimensions", "message"),
    [
        ("llm_freeform_intent", ["price"], "unknown question intent"),
        ("stock_observation_windows", ["llm_freeform_dimension"], "unknown question dimension"),
    ],
)
def test_question_builder_rejects_unknown_semantics(
    intent: str, dimensions: list[str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        build_question_card(
            canonical_question="unknown semantic input",
            scope=ObjectScope(kind="stock", refs=["603398"]),
            semantic_intent=intent,
            dimensions=dimensions,
            research_status="needs_review",
            view="query",
            original_source="user",
            status="candidate",
            created_at=STAMP,
            updated_at=STAMP,
            source_refs=source("unknown-semantic"),
            provenance_refs=provenance("unknown-semantic"),
        )


def test_post_v7_backlog_question_source_is_lossless() -> None:
    payload = json.loads(
        (CONTRACT / "fixtures/valid/question_card_post_v7_backlog.json").read_text()
    )
    card = QuestionCard.model_validate(payload)

    assert card.original_source == "post_v7_backlog"
    assert card.source_refs[0].source_type == "post_v7_backlog"


def test_fixed_seed_id_rejects_non_seed_source() -> None:
    with pytest.raises(ValidationError, match="seed_fixture source"):
        build_question_card(
            external_qc_id="QC-20260710-015",
            canonical_question="forged fixed card",
            scope=ObjectScope(kind="stock", refs=["603398"]),
            semantic_intent="stock_observation_windows",
            dimensions=["price", "episode"],
            research_status="answerable",
            view="checklist",
            original_source="user",
            status="accepted",
            created_at=STAMP,
            updated_at=STAMP,
            source_refs=source("not-seed"),
            provenance_refs=provenance("not-seed"),
        )


def test_same_gap_with_different_scope_does_not_merge() -> None:
    common = {
        "gap_id": "missing-market-series",
        "gap_summary": "missing data",
        "missing_assets": ["market_index_daily_series"],
        "missing_fields": ["trade_date", "close"],
        "blocked_question_card_refs": ["QC-20260710-014"],
        "owner": "unassigned",
        "debt_ref_status": "needs_assignment",
        "status": "candidate",
        "created_at": STAMP,
        "updated_at": STAMP,
        "source_refs": [SourceRef(source_type="system_gap", source_ref="gap")],
        "provenance_refs": [ProvenanceRef(provenance_type="contract_fixture", provenance_ref="test")],
    }
    stock = build_data_debt_card(scope=ObjectScope(kind="stock", refs=["603398"]), **common)
    universe = build_data_debt_card(scope=ObjectScope(kind="universe", refs=["ST panel"]), **common)

    assert stock.dedupe_key != universe.dedupe_key


def test_assigned_data_debt_key_is_anchored_only_by_debt_ref() -> None:
    common = {
        "debt_ref_status": "assigned",
        "status": "accepted",
        "created_at": STAMP,
        "updated_at": STAMP,
        "source_refs": [SourceRef(source_type="system_gap", source_ref="gap")],
        "provenance_refs": [
            ProvenanceRef(provenance_type="contract_fixture", provenance_ref="test")
        ],
    }
    first = build_data_debt_card(
        gap_id="gap-a",
        gap_summary="first description",
        scope=ObjectScope(kind="universe", refs=["ST panel"]),
        missing_assets=["market_index_daily_series"],
        missing_fields=["trade_date", "close"],
        blocked_question_card_refs=["QC-20260710-014"],
        owner="owner-a",
        external_debt_ref="D-051C",
        **common,
    )
    changed = build_data_debt_card(
        gap_id="gap-b",
        gap_summary="changed description",
        scope=ObjectScope(kind="stock", refs=["603398"]),
        missing_assets=["different_asset"],
        missing_fields=["different_field"],
        blocked_question_card_refs=["QC-20260710-001"],
        owner="owner-b",
        external_debt_ref="d-051c",
        **common,
    )
    other_ref = build_data_debt_card(
        gap_id="gap-a",
        gap_summary="first description",
        scope=ObjectScope(kind="universe", refs=["ST panel"]),
        missing_assets=["market_index_daily_series"],
        missing_fields=["trade_date", "close"],
        blocked_question_card_refs=["QC-20260710-014"],
        owner="owner-a",
        external_debt_ref="D-051D",
        **common,
    )

    assert first.dedupe_key == changed.dedupe_key
    assert first.memory_id == changed.memory_id
    assert first.dedupe_key != other_ref.dedupe_key


def test_query_template_key_uses_executor_parameters_and_outcomes() -> None:
    common = {
        "template_id": "QT-999",
        "definition_version": "draft-v1",
        "question_pattern": "display text does not define identity",
        "caveats": ["not evidence"],
        "proposed_executor_ref": "proposal:window-query",
        "status": "candidate",
        "created_at": STAMP,
        "updated_at": STAMP,
        "source_refs": [SourceRef(source_type="human_review", source_ref="template")],
        "provenance_refs": [
            ProvenanceRef(provenance_type="contract_fixture", provenance_ref="test")
        ],
    }
    first = build_query_template_record(
        parameter_schema=[QueryParameterSpec(name="symbol", value_type="string")],
        outcome_semantics=["event_timing"],
        **common,
    )
    changed_parameters = build_query_template_record(
        parameter_schema=[QueryParameterSpec(name="cohort", value_type="string")],
        outcome_semantics=["event_timing"],
        **common,
    )
    changed_outcome = build_query_template_record(
        parameter_schema=[QueryParameterSpec(name="symbol", value_type="string")],
        outcome_semantics=["distribution"],
        **common,
    )

    assert len({first.dedupe_key, changed_parameters.dedupe_key, changed_outcome.dedupe_key}) == 3


def test_time_scope_semantics_are_identity_bearing() -> None:
    base = {
        "canonical_question": "窗口",
        "scope": ObjectScope(kind="stock", refs=["603398"]),
        "semantic_intent": "event_window",
        "research_status": "answerable",
        "view": "query",
        "original_source": "user",
        "status": "candidate",
        "created_at": STAMP,
        "updated_at": STAMP,
        "source_refs": source("time"),
        "provenance_refs": provenance("time"),
    }
    ten_days = build_question_card(
        time_scope=TimeScope(semantics="trading_day_window", before=0, after=10), **base
    )
    fourteen_days = build_question_card(
        time_scope=TimeScope(semantics="trading_day_window", before=0, after=14), **base
    )

    assert ten_days.dedupe_key != fourteen_days.dedupe_key


def test_time_scope_rejects_mixed_semantics() -> None:
    with pytest.raises(ValidationError, match="calendar bounds"):
        TimeScope(
            semantics="trading_day_window",
            start="2026-07-01",
            before=0,
            after=10,
        )


def test_data_debt_internal_id_is_separate_from_optional_external_ref() -> None:
    assigned = DataDebtCard.model_validate(json.loads(
        (CONTRACT / "fixtures/valid/data_debt_assigned.json").read_text()
    ))
    unassigned = DataDebtCard.model_validate(json.loads(
        (CONTRACT / "fixtures/valid/data_debt_unassigned.json").read_text()
    ))

    assert assigned.memory_id.startswith("MEM-DD-")
    assert assigned.external_debt_ref == "D-051C"
    assert unassigned.memory_id.startswith("MEM-DD-")
    assert unassigned.external_debt_ref is None
    assert unassigned.debt_ref_status == "needs_assignment"


def test_feedback_taxonomy_and_research_run_target_are_public() -> None:
    payloads = json.loads((CONTRACT / "fixtures/feedback_taxonomy.json").read_text())
    events = [FeedbackEvent.model_validate(payload) for payload in payloads]

    assert {event.feedback_kind for event in events} == {
        "useful",
        "not_useful",
        "scope_error",
        "missing_evidence",
        "wording_issue",
        "other",
    }
    assert any(event.target_type == "research_run" for event in events)


def test_feedback_wording_and_source_do_not_change_event_key() -> None:
    common = {
        "feedback_kind": "wording_issue",
        "target_type": "research_run",
        "target_ref": "run-001",
        "status": "accepted",
        "created_at": STAMP,
        "updated_at": STAMP,
        "provenance_refs": [
            ProvenanceRef(provenance_type="user_feedback", provenance_ref="feedback")
        ],
    }
    first = build_feedback_event(
        feedback_text="措辞过强",
        source_refs=[SourceRef(source_type="user_question", source_ref="feedback-a")],
        **common,
    )
    second = build_feedback_event(
        feedback_text="应该降级表达",
        source_refs=[SourceRef(source_type="user_question", source_ref="feedback-b")],
        **common,
    )
    other_target = build_feedback_event(
        feedback_text="措辞过强",
        source_refs=[SourceRef(source_type="user_question", source_ref="feedback-c")],
        **{**common, "target_ref": "run-002"},
    )

    assert first.dedupe_key == second.dedupe_key
    assert first.dedupe_key != other_target.dedupe_key


def test_combo_object_kinds_survive_seed_migration() -> None:
    rows = json.loads((CONTRACT / "fixtures/seed_migration/expected_records.json").read_text())
    records = {row["external_qc_id"]: QuestionCard.model_validate(row) for row in rows}

    assert records["QC-20260710-002"].scope.kind == "stock_to_universe"
    assert records["QC-20260710-006"].scope.kind == "stock_or_episode"
    assert records["QC-20260710-007"].scope.kind == "stock_or_episode"
    assert records["QC-20260710-003"].debt_ref_status == "needs_assignment"
    assert records["QC-20260710-005"].external_debt_ref is None


def test_transition_table_covers_all_states_and_blocks_automatic_merge() -> None:
    assert set(STATUS_TRANSITIONS) == {
        "candidate", "accepted", "ignored", "merged", "blocked", "closed"
    }
    with pytest.raises(ValidationError, match="human actor"):
        StatusTransition(
            record_type="status_transition",
            object_type="question_card",
            from_status="accepted",
            to_status="merged",
            actor_type="system",
            context="online",
            reason="automatic merge",
            merge_target_id="MEM-QC-TARGET",
        )


def test_human_can_merge_candidate_directly() -> None:
    transition = StatusTransition(
        record_type="status_transition",
        object_type="question_card",
        from_status="candidate",
        to_status="merged",
        actor_type="human",
        context="online",
        reason="human matched existing question",
        merge_target_id="MEM-QC-TARGET",
    )

    assert transition.to_status == "merged"


@pytest.mark.parametrize(
    ("to_status", "actor_type", "message"),
    [
        ("accepted", "system", "acceptance requires"),
        ("ignored", "system", "ignore requires"),
        ("blocked", "llm", "LLM cannot"),
    ],
)
def test_online_candidate_status_decisions_require_human(
    to_status: str, actor_type: str, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        StatusTransition(
            record_type="status_transition",
            object_type="question_card",
            from_status="candidate",
            to_status=to_status,
            actor_type=actor_type,
            context="online",
            reason="forbidden automated decision",
        )


def test_seed_acceptance_has_explicit_migration_path() -> None:
    transition = StatusTransition(
        record_type="status_transition",
        object_type="question_card",
        from_status="candidate",
        to_status="accepted",
        actor_type="migration",
        context="seed_bootstrap",
        reason="controlled frozen seed import",
    )

    assert transition.actor_type == "migration"
    assert transition.context == "seed_bootstrap"


def test_public_root_schema_rejects_empty_and_resolves_all_public_fixtures() -> None:
    validator = Draft202012Validator(public_contract_schema())
    with pytest.raises(JsonSchemaValidationError):
        validator.validate({})

    for path in sorted((CONTRACT / "fixtures/valid").glob("*.json")):
        validator.validate(json.loads(path.read_text()))


def test_source_and_review_objects_expose_frozen_context_fields() -> None:
    valid = CONTRACT / "fixtures/valid"
    run = ResearchRunRef.model_validate(json.loads((valid / "research_run_ref.json").read_text()))
    review = ReviewItem.model_validate(json.loads((valid / "review_item.json").read_text()))
    result = SedimentationResult.model_validate(
        json.loads((valid / "sedimentation_result.json").read_text())
    )

    assert run.route.route == "answer_query"
    assert run.snapshot_refs and run.content_digest
    assert run.content_digest_algorithm == "sha256-canonical-json-v1"
    assert run.request_contract_version and run.response_contract_version
    assert review.uncertainty_type and review.decision_unit
    assert review.evidence_package_refs and review.recommended_action
    assert len(result.created) == 1
    assert result.existing == result.merged == result.ignored == []


def test_contract_models_reject_evidence_identity_and_naive_timestamps() -> None:
    payload = json.loads((CONTRACT / "fixtures/valid/question_card.json").read_text())
    payload["evidence_grade"] = "supported"
    with pytest.raises(ValidationError):
        QuestionCard.model_validate(payload)

    payload.pop("evidence_grade")
    payload["created_at"] = "2026-07-11T00:00:00"
    with pytest.raises(ValidationError, match="timezone"):
        QuestionCard.model_validate(payload)


def test_contract_tree_has_no_persistence_or_write_api_artifact() -> None:
    paths = [str(path.relative_to(ROOT)) for path in CONTRACT.rglob("*") if path.is_file()]
    assert not any(path.endswith((".sqlite", ".sqlite3", ".db")) for path in paths)
    assert not any("local_state" in path for path in paths)
    assert not any("repository.py" in path or "api.py" in path for path in paths)
