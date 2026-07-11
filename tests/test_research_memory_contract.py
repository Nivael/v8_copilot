import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_memory_contract import (
    STATUS_TRANSITIONS,
    DataDebtCard,
    ObjectScope,
    ProvenanceRef,
    QuestionCard,
    SourceRef,
    StatusTransition,
    TimeScope,
    build_data_debt_card,
    build_question_card,
    normalize_symbol,
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
        source_refs=[
            SourceRef(
                source_type="answer_card",
                source_ref="card-z",
                source_alias="603398 有哪些公开观察窗口？",
            )
        ],
        **base,
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


def test_fixed_seed_identity_uses_qc_id_not_question_wording() -> None:
    common = {
        "external_qc_id": "QC-20260710-015",
        "scope": ObjectScope(kind="stock", refs=["603398"]),
        "semantic_intent": "seed:QC-20260710-015",
        "needs_data": ["daily_prices", "episode_index"],
        "research_status": "answerable",
        "view": "checklist",
        "original_source": "slice",
        "status": "accepted",
        "created_at": STAMP,
        "updated_at": STAMP,
        "source_refs": [SourceRef(source_type="seed_fixture", source_ref="seed")],
        "provenance_refs": [
            ProvenanceRef(provenance_type="seed_fixture", provenance_ref="seed")
        ],
    }
    first = build_question_card(canonical_question="seed canonical question", **common)
    second = build_question_card(
        canonical_question="seed canonical question",
        aliases=["user wording must remain an alias"],
        **common,
    )

    assert first.dedupe_key == second.dedupe_key
    assert first.canonical_key == "question_card|seed_id=qc-20260710-015"


def test_fixed_seed_id_rejects_non_seed_source() -> None:
    with pytest.raises(ValidationError, match="seed_fixture source"):
        build_question_card(
            external_qc_id="QC-20260710-015",
            canonical_question="forged fixed card",
            scope=ObjectScope(kind="stock", refs=["603398"]),
            semantic_intent="seed:QC-20260710-015",
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
        "required_fields": ["trade_date", "close"],
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
            object_type="question_card",
            from_status="accepted",
            to_status="merged",
            actor_type="system",
            reason="automatic merge",
            merge_target_id="MEM-QC-TARGET",
        )


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
