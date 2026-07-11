from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from query_templates import TEMPLATES  # noqa: E402
from research_memory_contract import (  # noqa: E402
    RESEARCH_MEMORY_CONTRACT_VERSION,
    REVIEW_ACTIVE_LIMIT,
    STATUS_TRANSITIONS,
    DataDebtCard,
    ExecutorRef,
    ObjectScope,
    ProvenanceRef,
    QuestionCard,
    ResearchRunRef,
    SedimentationResult,
    SourceRef,
    StatusTransition,
    TimeScope,
    build_data_debt_card,
    build_feedback_event,
    build_memory_link,
    build_query_template_record,
    build_question_card,
    build_review_item,
    public_contract_schema,
)


HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
VALID = FIXTURES / "valid"
INVALID = FIXTURES / "invalid"
MIGRATION = FIXTURES / "seed_migration"
STAMP = datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc)
SEED_PATH = ROOT / "evals/question_card_seeds_v0.jsonl"
SEED_SHA256 = "d98583e8d651ce8cf4cae41e87cfca342142b814f675833e43c174f4964fd559"

PROTECTED_CONTRACT_CHECKSUMS = {
    "contracts/v8_answer_contract_v0/schema.json": "985acc1697bd28ded3a0f5d598fa6c3db4389f4fe9509555c727da9ab81e3ed3",
    "contracts/v8_copilot_api_contract_v0/manifest.json": "570796a69ddc13636d76ff297e2144b1f5189f2b17bf9426e5fcac4bdfd4ff49",
    "contracts/v8_copilot_api_contract_v0/schema.json": "6857ef8e486ef1cadfb3deedc13c1a27ec866ae7eb18b36e6108d5b2111ec8f8",
    "contracts/v8_copilot_api_contract_v1/manifest.json": "2d40a181718fe2934ecb243a7d4890cd86c53f0af6ebceb1d3771f37e730af76",
    "contracts/v8_copilot_api_contract_v1/schema.json": "8ec5b6a048e900a23ca745bf9e54a286ede62462349117f140e01c56ced82ca6",
    "contracts/v8_query_template_contract_v0/registry.json": "a93d0e8b223339d40d917bbf97e24508a634425cfbee8fc993da55bc814b0f9d",
    "contracts/v8_query_template_contract_v0/schema.json": "6b8914ebd650bf768d6543352492f03ed9145e9278015b3f3e6ce45df2396d59",
    "contracts/v8_question_card_contract_v0/fixture.json": "5268fe8e042edd35219fd1d8e201377b6a5d23804589122e9c74faff9bef3281",
    "contracts/v8_question_card_contract_v0/schema.json": "52e7de211b4e74cc18a5a744423ed177642c9028559d2cdf405f67e67e6cadaf",
}


def dump(path: Path, value: Any) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source(source_type: str, source_ref: str, alias: str | None = None) -> SourceRef:
    return SourceRef(source_type=source_type, source_ref=source_ref, source_alias=alias)


def provenance(kind: str, ref: str) -> ProvenanceRef:
    return ProvenanceRef(provenance_type=kind, provenance_ref=ref)


def seed_rows() -> list[dict[str, Any]]:
    seed_bytes = SEED_PATH.read_bytes()
    if sha256(seed_bytes).hexdigest() != SEED_SHA256:
        raise RuntimeError("question-card seed checksum drifted")
    return [json.loads(line) for line in seed_bytes.decode("utf-8").splitlines()]


def migrate_seed(row: dict[str, Any]) -> QuestionCard:
    debt_ref = row["debt_ref"] or None
    return build_question_card(
        external_qc_id=row["id"],
        canonical_question=row["question"],
        scope=ObjectScope(kind=row["object"]["kind"], refs=[row["object"]["ref"]]),
        semantic_intent=f"seed:{row['id']}",
        aliases=[],
        needs_data=row["needs_data"],
        research_status=row["status"],
        view=row["view"],
        original_source=row["source"],
        external_debt_ref=debt_ref,
        debt_ref_status=row["debt_ref_status"],
        status="accepted",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[
            source("seed_fixture", "evals/question_card_seeds_v0.jsonl", row["question"])
        ],
        provenance_refs=[
            provenance("seed_fixture", "evals/question_card_seeds_v0.jsonl")
        ],
    )


def valid_objects() -> dict[str, Any]:
    common_source = [source("research_response", "response-fixture-001")]
    common_provenance = [provenance("research_response", "response-fixture-001")]
    question = build_question_card(
        canonical_question="603398 某节点前后有哪些可回链变化？",
        scope=ObjectScope(kind="stock_event", refs=["SH.603398", "603398.SH"]),
        semantic_intent="stock_event_window",
        needs_data=["daily_prices", "episode_index", "daily_prices"],
        research_status="answerable",
        view="query",
        original_source="user",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=common_source,
        provenance_refs=common_provenance,
        time_scope=TimeScope(semantics="event_window", before=10, after=10),
    )
    debt = build_data_debt_card(
        gap_id="market_index_daily_series",
        gap_summary="缺少可按交易日对齐的大盘指数日线。",
        scope=ObjectScope(kind="universe", refs=["ST panel"]),
        required_fields=["trade_date", "index_close", "trade_date"],
        external_debt_ref="D-051C",
        debt_ref_status="assigned",
        status="accepted",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("system_gap", "gap:market_index_daily_series")],
        provenance_refs=[provenance("contract_fixture", "D-053")],
    )
    debt_unassigned = build_data_debt_card(
        gap_id="release_lens_boundary_catalog",
        gap_summary="缺少可查询的 lens standing/rejected 边界目录。",
        scope=ObjectScope(kind="lens", refs=["任意"]),
        required_fields=["standing", "rejection_reason"],
        debt_ref_status="needs_assignment",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("system_gap", "QC-20260710-003")],
        provenance_refs=[provenance("seed_fixture", "evals/question_card_seeds_v0.jsonl")],
    )
    template = build_query_template_record(
        template_id="QT-001",
        definition_version="v8_query_template_contract_v0",
        question_pattern="某事件后下一个节点多久",
        parameter_semantics=["episode_type"],
        outcome_semantics=["event_next_node_timing"],
        caveats=["不同节点定义必须并列展示"],
        executor_ref=ExecutorRef(
            registry_contract_version="v8_query_template_contract_v0",
            template_id="QT-001",
            executor_key="next_node_timing",
        ),
        executable=True,
        status="accepted",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("query_template_registry", "QT-001")],
        provenance_refs=[
            provenance("query_template_registry", "contracts/v8_query_template_contract_v0/registry.json")
        ],
    )
    review = build_review_item(
        review_kind="question_acceptance",
        target_type="question_card",
        target_memory_id=question.memory_id,
        priority=10,
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=common_source,
        provenance_refs=common_provenance,
    )
    feedback = build_feedback_event(
        feedback_kind="missing_context",
        target_type="research_response",
        target_ref="response-fixture-001",
        feedback_text="需要补充事件日期。",
        status="accepted",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("user_question", "feedback-fixture-001")],
        provenance_refs=[provenance("user_feedback", "feedback-fixture-001")],
    )
    link = build_memory_link(
        relation="derived_from",
        source_type="research_response",
        source_ref="response-fixture-001",
        target_type="question_card",
        target_memory_id=question.memory_id,
        status="accepted",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=common_source,
        provenance_refs=common_provenance,
    )
    run = ResearchRunRef(
        run_id="run-fixture-001",
        request_id="request-fixture-001",
        answer_card_id="answer-card-fixture-001",
        research_response_id="response-fixture-001",
        recorded_at=STAMP,
    )
    transition = StatusTransition(
        object_type="question_card",
        from_status="candidate",
        to_status="accepted",
        actor_type="human",
        reason="review accepted",
    )
    result = SedimentationResult(
        operation_id="sedimentation-fixture-001",
        created_ids=[question.memory_id],
        existing_ids=[],
        created_links=[link],
        completed_at=STAMP,
    )
    return {
        "question_card": question,
        "data_debt_assigned": debt,
        "data_debt_unassigned": debt_unassigned,
        "query_template_record": template,
        "review_item": review,
        "feedback_event": feedback,
        "memory_link": link,
        "research_run_ref": run,
        "status_transition": transition,
        "sedimentation_result": result,
    }


def key_fixtures() -> dict[str, Any]:
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
        "provenance_refs": [provenance("research_response", "response-001")],
    }
    synonym_a = build_question_card(
        canonical_question="沐邦接下来该看哪些窗口？",
        source_refs=[source("research_run", "run-001", "沐邦接下来该看哪些窗口？")],
        **base,
    )
    synonym_b = build_question_card(
        canonical_question="沐邦接下来该看哪些窗口？",
        source_refs=[
            source("answer_card", "answer-999", "603398 后续有哪些公开节点值得观察？")
        ],
        **base,
    )
    array_a = build_question_card(
        canonical_question="节点窗口",
        scope=ObjectScope(kind="stock", refs=["SH.603398", "603398.SH"]),
        semantic_intent="stock_event_window",
        needs_data=["episode_index", "daily_prices", "episode_index"],
        research_status="answerable",
        view="query",
        original_source="user",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("research_run", "run-array-a")],
        provenance_refs=[provenance("research_response", "response-array")],
    )
    array_b = build_question_card(
        canonical_question="节点窗口",
        scope=ObjectScope(kind="stock", refs=["603398"]),
        semantic_intent="stock_event_window",
        needs_data=["daily_prices", "episode_index"],
        research_status="answerable",
        view="query",
        original_source="user",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("research_run", "run-array-b")],
        provenance_refs=[provenance("research_response", "response-array")],
    )
    debt_stock = build_data_debt_card(
        gap_id="same-gap",
        gap_summary="same gap",
        scope=ObjectScope(kind="stock", refs=["603398"]),
        required_fields=["field_a"],
        debt_ref_status="needs_assignment",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("system_gap", "gap-stock")],
        provenance_refs=[provenance("contract_fixture", "key-fixtures")],
    )
    debt_universe = build_data_debt_card(
        gap_id="same-gap",
        gap_summary="same gap",
        scope=ObjectScope(kind="universe", refs=["ST panel"]),
        required_fields=["field_a"],
        debt_ref_status="needs_assignment",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("system_gap", "gap-universe")],
        provenance_refs=[provenance("contract_fixture", "key-fixtures")],
    )
    time_a = build_question_card(
        canonical_question="十日窗口",
        time_scope=TimeScope(semantics="trading_day_window", before=0, after=10),
        source_refs=[source("research_run", "run-time-a")],
        **base,
    )
    time_b = build_question_card(
        canonical_question="十四日窗口",
        time_scope=TimeScope(semantics="trading_day_window", before=0, after=14),
        source_refs=[source("research_run", "run-time-b")],
        **base,
    )
    return {
        "synonym_different_runs": {
            "first": synonym_a.model_dump(mode="json"),
            "second": synonym_b.model_dump(mode="json"),
            "expect_same_dedupe_key": True,
            "expect_different_source_refs": True,
        },
        "same_gap_different_scope": {
            "first": debt_stock.model_dump(mode="json"),
            "second": debt_universe.model_dump(mode="json"),
            "expect_same_dedupe_key": False,
        },
        "normalized_arrays_and_symbols": {
            "first": array_a.model_dump(mode="json"),
            "second": array_b.model_dump(mode="json"),
            "expect_same_dedupe_key": True,
        },
        "different_time_semantics": {
            "first": time_a.model_dump(mode="json"),
            "second": time_b.model_dump(mode="json"),
            "expect_same_dedupe_key": False,
        },
        "llm_title_changes": {
            "semantic_record": synonym_a.model_dump(mode="json"),
            "llm_titles": ["可能爆发", "后续观察窗口", "完全不同的展示标题"],
            "expected_dedupe_key": synonym_a.dedupe_key,
            "title_is_not_contract_input": True,
        },
    }


def invalid_payloads(valid: dict[str, Any]) -> dict[str, dict[str, Any]]:
    question = valid["question_card"].model_dump(mode="json")
    no_source = {**question, "source_refs": []}
    no_provenance = {**question, "provenance_refs": []}
    evidence_identity = {**question, "evidence_grade": "supported"}
    bad_identity = {**question, "dedupe_key": "0" * 64}
    naive_time = {**question, "created_at": "2026-07-11T00:00:00"}
    draft = valid["query_template_record"].model_dump(mode="json")
    draft.update({"status": "candidate", "executable": True})
    unassigned = valid["data_debt_unassigned"].model_dump(mode="json")
    unassigned["external_debt_ref"] = "D-FAKE"
    return {
        "missing_source_refs": {"model": "QuestionCard", "payload": no_source},
        "missing_provenance_refs": {"model": "QuestionCard", "payload": no_provenance},
        "evidence_identity_forbidden": {"model": "QuestionCard", "payload": evidence_identity},
        "tampered_dedupe_key": {"model": "QuestionCard", "payload": bad_identity},
        "timezone_naive": {"model": "QuestionCard", "payload": naive_time},
        "draft_template_executable": {"model": "QueryTemplateRecord", "payload": draft},
        "unassigned_debt_with_ref": {"model": "DataDebtCard", "payload": unassigned},
        "illegal_transition": {
            "model": "StatusTransition",
            "payload": {
                "object_type": "question_card",
                "from_status": "closed",
                "to_status": "accepted",
                "actor_type": "human",
                "reason": "illegal reopen",
            },
        },
        "automatic_merge": {
            "model": "StatusTransition",
            "payload": {
                "object_type": "question_card",
                "from_status": "accepted",
                "to_status": "merged",
                "actor_type": "system",
                "reason": "automatic similarity merge",
                "merge_target_id": "MEM-QC-TARGET",
            },
        },
    }


def query_template_records() -> list[dict[str, Any]]:
    records = []
    for template in TEMPLATES:
        record = build_query_template_record(
            template_id=template.template_id,
            definition_version=template.contract_version,
            question_pattern=template.question_pattern,
            parameter_semantics=template.required_inputs,
            outcome_semantics=[template.query_intent, *template.definition_variants],
            caveats=template.default_caveats,
            executor_ref=ExecutorRef(
                registry_contract_version=template.contract_version,
                template_id=template.template_id,
                executor_key=template.executor_key,
            ),
            executable=True,
            status="accepted",
            created_at=STAMP,
            updated_at=STAMP,
            source_refs=[source("query_template_registry", template.template_id)],
            provenance_refs=[
                provenance("query_template_registry", "contracts/v8_query_template_contract_v0/registry.json")
            ],
        )
        records.append(record.model_dump(mode="json"))
    return records


def main() -> None:
    rows = seed_rows()
    migrated = [migrate_seed(row) for row in rows]
    valid = valid_objects()

    dump(HERE / "schema.json", public_contract_schema())
    for name, value in valid.items():
        dump(VALID / f"{name}.json", value)
    dump(FIXTURES / "key_cases.json", key_fixtures())
    dump(FIXTURES / "query_template_records.json", query_template_records())
    dump(
        FIXTURES / "status_transitions.json",
        {
            "transition_table": {key: list(value) for key, value in STATUS_TRANSITIONS.items()},
            "valid_human_merge": StatusTransition(
                object_type="question_card",
                from_status="accepted",
                to_status="merged",
                actor_type="human",
                reason="review confirmed duplicate",
                merge_target_id=migrated[0].memory_id,
            ).model_dump(mode="json"),
        },
    )
    review_ids = []
    for index in range(REVIEW_ACTIVE_LIMIT):
        item = build_review_item(
            review_kind="question_acceptance",
            target_type="question_card",
            target_memory_id=f"MEM-QC-CAPACITY-{index:02d}",
            priority=index,
            status="candidate",
            created_at=STAMP,
            updated_at=STAMP,
            source_refs=[source("human_review", f"review-capacity-{index:02d}")],
            provenance_refs=[provenance("contract_fixture", "review-capacity")],
        )
        review_ids.append(item.memory_id)
    dump(
        FIXTURES / "review_capacity.json",
        {
            "max_active_items": REVIEW_ACTIVE_LIMIT,
            "active_item_ids": review_ids,
            "repository_must_reject_active_count_above": REVIEW_ACTIVE_LIMIT,
        },
    )

    for name, value in invalid_payloads(valid).items():
        dump(INVALID / f"{name}.json", value)

    MIGRATION.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SEED_PATH, MIGRATION / "question_card_seeds_v0.jsonl")
    dump(MIGRATION / "expected_records.json", [item.model_dump(mode="json") for item in migrated])
    first_links = [
        build_memory_link(
            relation="sedimented_from",
            source_type="seed_fixture",
            source_ref=f"evals/question_card_seeds_v0.jsonl#{index + 1}",
            target_type="question_card",
            target_memory_id=item.memory_id,
            status="accepted",
            created_at=STAMP,
            updated_at=STAMP,
            source_refs=item.source_refs,
            provenance_refs=item.provenance_refs,
        )
        for index, item in enumerate(migrated)
    ]
    dump(
        MIGRATION / "first_import_result.json",
        SedimentationResult(
            operation_id="seed-import-first",
            created_ids=[item.memory_id for item in migrated],
            existing_ids=[],
            created_links=first_links,
            completed_at=STAMP,
        ),
    )
    dump(
        MIGRATION / "second_import_result.json",
        SedimentationResult(
            operation_id="seed-import-second",
            created_ids=[],
            existing_ids=[item.memory_id for item in migrated],
            created_links=[],
            completed_at=STAMP,
        ),
    )
    dump(
        MIGRATION / "seed_summary.json",
        {
            "sha256": SEED_SHA256,
            "count": len(rows),
            "research_status": dict(Counter(row["status"] for row in rows)),
            "debt_ref_status": dict(Counter(row["debt_ref_status"] for row in rows)),
            "external_qc_ids": [row["id"] for row in rows],
        },
    )

    artifact_paths = sorted(
        str(path.relative_to(HERE))
        for path in HERE.rglob("*.json")
        if path.name != "manifest.json"
    )
    artifact_paths.append("fixtures/seed_migration/question_card_seeds_v0.jsonl")
    dump(
        HERE / "manifest.json",
        {
            "contract_version": RESEARCH_MEMORY_CONTRACT_VERSION,
            "decision": "D-053",
            "schema": "schema.json",
            "python_types": "research_memory_contract.py",
            "seed_sha256": SEED_SHA256,
            "seed_count": 15,
            "persistent_entities": [
                "QuestionCard",
                "DataDebtCard",
                "QueryTemplateRecord",
                "ReviewItem",
                "FeedbackEvent",
                "MemoryLink",
            ],
            "transport_objects": ["ResearchRunRef", "SedimentationResult"],
            "review_active_limit": REVIEW_ACTIVE_LIMIT,
            "artifacts": artifact_paths,
            "protected_contract_checksums": PROTECTED_CONTRACT_CHECKSUMS,
            "prohibited_capabilities": [
                "sqlite_repository",
                "write_api",
                "research_source_write",
                "evidence_or_lens_promotion",
            ],
        },
    )


if __name__ == "__main__":
    main()
