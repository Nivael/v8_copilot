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
    QUESTION_SEMANTIC_REGISTRY_VERSION,
    PROVISIONAL_QUESTION_IDENTITY_VERSION,
    PROVISIONAL_QUESTION_NORMALIZATION_VERSION,
    QUESTION_DIMENSION_ALIASES,
    QUESTION_INTENT_ALIASES,
    REVIEW_ACTIVE_LIMIT,
    STATUS_TRANSITIONS,
    DataDebtCard,
    ExecutorRef,
    MemoryObjectRef,
    ObjectScope,
    ProvenanceRef,
    QueryParameterSpec,
    QuestionDimension,
    QuestionCard,
    QuestionIntent,
    ResearchRouteRef,
    ResearchRunRef,
    ReviewSubjectRef,
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
    canonical_json,
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

SEED_SEMANTICS: dict[str, dict[str, Any]] = {
    "QC-20260710-001": {
        "object": {"kind": "stock", "ref": "任意"},
        "intent": "st_status_reason_and_key_nodes",
        "dimensions": ["st_status", "announcement", "episode"],
    },
    "QC-20260710-002": {
        "object": {"kind": "stock_to_universe", "ref": "任意"},
        "intent": "historical_case_similarity",
        "dimensions": ["episode_sequence", "event_type", "price_path"],
    },
    "QC-20260710-003": {
        "object": {"kind": "stock", "ref": "任意"},
        "intent": "lens_applicability_and_standing",
        "dimensions": ["lens_kind", "validation_status", "rejected_boundary"],
    },
    "QC-20260710-004": {
        "object": {"kind": "stock_event", "ref": "任意"},
        "intent": "stock_event_multi_dimension_window",
        "dimensions": [
            "announcement", "price", "share_capital", "shareholder_count",
            "regulatory_action",
        ],
    },
    "QC-20260710-005": {
        "object": {"kind": "lens", "ref": "任意"},
        "intent": "lens_evidence_audit",
        "dimensions": ["evidence_grade", "sample_n", "counterexample", "data_gap"],
    },
    "QC-20260710-006": {
        "object": {"kind": "stock_or_episode", "ref": "任意"},
        "intent": "st_shareholder_count_change",
        "dimensions": ["shareholder_count"],
    },
    "QC-20260710-007": {
        "object": {"kind": "stock_or_episode", "ref": "任意"},
        "intent": "st_announcement_density",
        "dimensions": ["announcement_density"],
    },
    "QC-20260710-008": {
        "object": {"kind": "stock_event", "ref": "任意"},
        "intent": "stock_event_data_summary",
        "dimensions": ["multi_table_summary"],
    },
    "QC-20260710-009": {
        "object": {"kind": "episode_type", "ref": "restructuring"},
        "intent": "restructuring_stage_timing",
        "dimensions": ["episode_transition", "elapsed_days"],
    },
    "QC-20260710-010": {
        "object": {"kind": "cohort", "ref": "重整招募"},
        "intent": "restructuring_recruitment_next_node_timing",
        "dimensions": ["next_announcement", "stage"],
    },
    "QC-20260710-011": {
        "object": {"kind": "cohort", "ref": "重整招募"},
        "intent": "restructuring_recruitment_next_node_timing",
        "dimensions": ["next_announcement", "province", "stage"],
    },
    "QC-20260710-012": {
        "object": {"kind": "cohort", "ref": "重整"},
        "intent": "restructuring_path_isolation",
        "dimensions": ["out_of_court", "in_court", "elapsed_days"],
    },
    "QC-20260710-013": {
        "object": {"kind": "universe", "ref": "ST panel"},
        "intent": "st_microcap_two_week_distribution",
        "dimensions": ["market_cap_cohort", "two_week_return"],
    },
    "QC-20260710-014": {
        "object": {"kind": "universe", "ref": "ST panel"},
        "intent": "st_market_relative_two_week_distribution",
        "dimensions": ["market_index", "two_week_excess_return"],
    },
    "QC-20260710-015": {
        "object": {"kind": "stock", "ref": "603398"},
        "intent": "stock_observation_windows",
        "dimensions": ["price", "episode"],
    },
}

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


def question_semantic_registry_payload() -> dict[str, Any]:
    return {
        "registry_version": QUESTION_SEMANTIC_REGISTRY_VERSION,
        "intents": sorted(item.value for item in QuestionIntent),
        "dimensions": sorted(item.value for item in QuestionDimension),
        "intent_aliases": {
            alias: target.value for alias, target in sorted(QUESTION_INTENT_ALIASES.items())
        },
        "dimension_aliases": {
            alias: target.value
            for alias, target in sorted(QUESTION_DIMENSION_ALIASES.items())
        },
        "unknown_value_policy": "reject",
        "unknown_question_intake": {
            "intent": "unknown_research_question",
            "identity_kind": "provisional_unknown",
            "identity_version": PROVISIONAL_QUESTION_IDENTITY_VERSION,
            "normalization_version": PROVISIONAL_QUESTION_NORMALIZATION_VERSION,
            "builder_status": "candidate",
            "human_merge_terminal_status": "merged",
            "required_research_status": "needs_review",
        },
        "mapping_authority": "deterministic_sedimenter",
    }


def source(source_type: str, source_ref: str, alias: str | None = None) -> SourceRef:
    return SourceRef(source_type=source_type, source_ref=source_ref, source_alias=alias)


def provenance(kind: str, ref: str) -> ProvenanceRef:
    return ProvenanceRef(provenance_type=kind, provenance_ref=ref)


def object_ref(object_type: str, item: Any) -> MemoryObjectRef:
    return MemoryObjectRef(
        object_type=object_type,
        memory_id=item.memory_id,
        dedupe_key=item.dedupe_key,
    )


def seed_rows() -> list[dict[str, Any]]:
    seed_bytes = SEED_PATH.read_bytes()
    if sha256(seed_bytes).hexdigest() != SEED_SHA256:
        raise RuntimeError("question-card seed checksum drifted")
    rows = [json.loads(line) for line in seed_bytes.decode("utf-8").splitlines()]
    if {row["id"] for row in rows} != set(SEED_SEMANTICS):
        raise RuntimeError("seed semantic mapping does not cover the frozen seed exactly")
    return rows


def migrate_seed(row: dict[str, Any]) -> QuestionCard:
    debt_ref = row["debt_ref"] or None
    semantics = SEED_SEMANTICS[row["id"]]
    if semantics["object"] != row["object"]:
        raise RuntimeError(f"seed semantic scope drifted for {row['id']}")
    return build_question_card(
        external_qc_id=row["id"],
        canonical_question=row["question"],
        scope=ObjectScope(kind=row["object"]["kind"], refs=[row["object"]["ref"]]),
        semantic_intent=semantics["intent"],
        dimensions=semantics["dimensions"],
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
        dimensions=["announcement", "price", "episode"],
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
    backlog_question = build_question_card(
        canonical_question="post-v7 backlog 中待复核的 lens 边界问题",
        scope=ObjectScope(kind="stock", refs=["任意"]),
        semantic_intent="lens_applicability_and_standing",
        dimensions=["lens_kind", "validation_status", "rejected_boundary"],
        needs_data=["release_library_v1"],
        research_status="needs_review",
        view="evidence",
        original_source="post_v7_backlog",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("post_v7_backlog", "post-v7:C06-boundary-review")],
        provenance_refs=[provenance("contract_fixture", "D-053")],
    )
    provisional_question = build_question_card(
        canonical_question="这家公司有没有海外诉讼？",
        scope=ObjectScope(kind="stock", refs=["603398"]),
        semantic_intent="unknown_research_question",
        dimensions=[],
        needs_data=[],
        research_status="needs_review",
        view="query",
        original_source="user",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("research_run", "run-provisional-001")],
        provenance_refs=[provenance("research_response", "response-provisional-001")],
    )
    debt = build_data_debt_card(
        gap_id="market_index_daily_series",
        gap_summary="缺少可按交易日对齐的大盘指数日线。",
        scope=ObjectScope(kind="universe", refs=["ST panel"]),
        missing_assets=["market_index_daily_series"],
        missing_fields=["trade_date", "index_close", "trade_date"],
        blocked_question_card_refs=["QC-20260710-014"],
        owner="data-engineering",
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
        missing_assets=["release_lens_boundary_catalog"],
        missing_fields=["standing", "rejection_reason"],
        blocked_question_card_refs=["QC-20260710-003", "QC-20260710-005"],
        owner="unassigned",
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
        parameter_schema=[
            QueryParameterSpec(name="episode_type", value_type="string", required=True)
        ],
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
        uncertainty_type="question_semantic_identity",
        subject_ref=ReviewSubjectRef(
            subject_type="question_card", subject_id=question.memory_id
        ),
        decision_unit="one_question_candidate",
        evidence_package_refs=common_provenance,
        recommended_action="accept_candidate",
        priority=10,
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=common_source,
        provenance_refs=common_provenance,
    )
    feedback = build_feedback_event(
        feedback_kind="scope_error",
        target_type="research_run",
        target_ref="run-fixture-001",
        feedback_text="对象范围应限定到该事件窗口。",
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
        record_type="research_run_ref",
        contract_version=RESEARCH_MEMORY_CONTRACT_VERSION,
        run_id="run-fixture-001",
        request_id="request-fixture-001",
        answer_card_id="answer-card-fixture-001",
        research_response_id="response-fixture-001",
        request_contract_version="v8_copilot_api_contract_v0",
        response_contract_version="v8_copilot_api_contract_v1",
        answer_contract_version="v8_answer_contract_v0",
        route=ResearchRouteRef(route="answer_query", status="answerable", view="query"),
        snapshot_as_of=STAMP,
        snapshot_refs=common_provenance,
        content_digest_algorithm="sha256-canonical-json-v1",
        content_digest=sha256(
            canonical_json(
                {"research_response_id": "response-fixture-001"}
            ).encode("utf-8")
        ).hexdigest(),
        content_summary="Validated fixture response for a stock event window.",
        created_at=STAMP,
    )
    transition = StatusTransition(
        record_type="status_transition",
        object_type="question_card",
        from_status="candidate",
        to_status="accepted",
        actor_type="human",
        context="online",
        reason="review accepted",
    )
    result = SedimentationResult(
        record_type="sedimentation_result",
        contract_version=RESEARCH_MEMORY_CONTRACT_VERSION,
        operation_id="sedimentation-fixture-001",
        created=[
            MemoryObjectRef(
                object_type="question_card",
                memory_id=question.memory_id,
                dedupe_key=question.dedupe_key,
            )
        ],
        existing=[],
        merged=[],
        ignored=[],
        created_links=[link],
        completed_at=STAMP,
    )
    return {
        "question_card": question,
        "question_card_post_v7_backlog": backlog_question,
        "question_card_provisional_unknown": provisional_question,
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


def feedback_taxonomy_fixtures() -> list[dict[str, Any]]:
    cases = [
        ("useful", "research_run", "run-feedback-001"),
        ("not_useful", "answer_card", "answer-feedback-001"),
        ("scope_error", "research_response", "response-feedback-001"),
        ("missing_evidence", "question_card", "MEM-QC-FEEDBACK-001"),
        ("wording_issue", "research_run", "run-feedback-002"),
        ("other", "answer_card", "answer-feedback-002"),
    ]
    return [
        build_feedback_event(
            feedback_kind=feedback_kind,
            target_type=target_type,
            target_ref=target_ref,
            feedback_text=f"fixture:{feedback_kind}",
            status="accepted",
            created_at=STAMP,
            updated_at=STAMP,
            source_refs=[source("user_question", f"feedback:{feedback_kind}")],
            provenance_refs=[provenance("user_feedback", f"feedback:{feedback_kind}")],
        ).model_dump(mode="json")
        for feedback_kind, target_type, target_ref in cases
    ]


def key_fixtures() -> dict[str, Any]:
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
        "provenance_refs": [provenance("research_response", "response-001")],
    }
    synonym_a = build_question_card(
        canonical_question="沐邦接下来该看哪些窗口？",
        source_refs=[source("research_run", "run-001", "沐邦接下来该看哪些窗口？")],
        **base,
    )
    synonym_b = build_question_card(
        canonical_question="沐邦接下来该看哪些窗口？",
        needs_data=["different_availability_note"],
        view="query",
        source_refs=[
            source("answer_card", "answer-999", "603398 后续有哪些公开节点值得观察？")
        ],
        **{key: value for key, value in base.items() if key not in {"needs_data", "view"}},
    )
    seed_equivalent = build_question_card(
        external_qc_id="QC-20260710-015",
        canonical_question="沐邦(603398)平台整理两个月该看哪些窗口？",
        scope=ObjectScope(kind="stock", refs=["603398"]),
        semantic_intent="stock_observation_windows",
        dimensions=["price", "episode"],
        needs_data=["daily_prices", "episode_index"],
        research_status="answerable",
        view="checklist",
        original_source="slice",
        status="accepted",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("seed_fixture", "evals/question_card_seeds_v0.jsonl")],
        provenance_refs=[provenance("seed_fixture", "evals/question_card_seeds_v0.jsonl")],
    )
    online_equivalent = build_question_card(
        canonical_question="603398 后续观察哪些公开窗口？",
        scope=ObjectScope(kind="stock", refs=["SH.603398"]),
        semantic_intent="stock_observation_windows",
        dimensions=["episode", "price"],
        needs_data=["runtime_availability"],
        research_status="answerable",
        view="query",
        original_source="user",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("research_run", "run-seed-equivalent")],
        provenance_refs=[provenance("research_response", "response-seed-equivalent")],
    )
    registry_alias_equivalent = build_question_card(
        canonical_question="603398 后续监控哪些窗口？",
        scope=ObjectScope(kind="stock", refs=["603398"]),
        semantic_intent="stock_monitoring_windows",
        dimensions=["daily_prices", "episode_index"],
        needs_data=["runtime_availability"],
        research_status="answerable",
        view="query",
        original_source="user",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("research_run", "run-registry-alias")],
        provenance_refs=[provenance("research_response", "response-registry-alias")],
    )
    provisional_lawsuit = build_question_card(
        canonical_question="这家公司有没有海外诉讼？",
        scope=ObjectScope(kind="stock", refs=["603398"]),
        semantic_intent="unknown_research_question",
        dimensions=[],
        research_status="needs_review",
        view="query",
        original_source="user",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("research_run", "run-unknown-a")],
        provenance_refs=[provenance("research_response", "response-unknown-a")],
    )
    provisional_lawsuit_retry = build_question_card(
        canonical_question="  这家公司有没有海外诉讼？  ",
        scope=ObjectScope(kind="stock", refs=["SH.603398"]),
        semantic_intent="unknown_research_question",
        dimensions=[],
        research_status="needs_review",
        view="query",
        original_source="user",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("research_run", "run-unknown-a-retry")],
        provenance_refs=[provenance("research_response", "response-unknown-a-retry")],
    )
    provisional_auditor = build_question_card(
        canonical_question="为什么审计师辞职？",
        scope=ObjectScope(kind="stock", refs=["603398"]),
        semantic_intent="unknown_research_question",
        dimensions=[],
        research_status="needs_review",
        view="query",
        original_source="user",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("research_run", "run-unknown-b")],
        provenance_refs=[provenance("research_response", "response-unknown-b")],
    )
    array_a = build_question_card(
        canonical_question="节点窗口",
        scope=ObjectScope(kind="stock", refs=["SH.603398", "603398.SH"]),
        semantic_intent="stock_event_window",
        dimensions=["price", "announcement", "price"],
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
        dimensions=["announcement", "price"],
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
        missing_assets=["asset_a"],
        missing_fields=["field_a"],
        blocked_question_card_refs=["QC-20260710-003"],
        owner="unassigned",
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
        missing_assets=["asset_a"],
        missing_fields=["field_a"],
        blocked_question_card_refs=["QC-20260710-003"],
        owner="unassigned",
        debt_ref_status="needs_assignment",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("system_gap", "gap-universe")],
        provenance_refs=[provenance("contract_fixture", "key-fixtures")],
    )
    assigned_a = build_data_debt_card(
        gap_id="market-index-a",
        gap_summary="first wording",
        scope=ObjectScope(kind="universe", refs=["ST panel"]),
        missing_assets=["market_index_daily_series"],
        missing_fields=["trade_date", "close"],
        blocked_question_card_refs=["QC-20260710-014"],
        owner="data-engineering",
        external_debt_ref="D-051C",
        debt_ref_status="assigned",
        status="accepted",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("system_gap", "assigned-a")],
        provenance_refs=[provenance("contract_fixture", "key-fixtures")],
    )
    assigned_b = build_data_debt_card(
        gap_id="changed-gap-label",
        gap_summary="changed wording and fields",
        scope=ObjectScope(kind="stock", refs=["603398"]),
        missing_assets=["different_asset"],
        missing_fields=["different_field"],
        blocked_question_card_refs=["QC-20260710-001"],
        owner="another-owner",
        external_debt_ref="d-051c",
        debt_ref_status="assigned",
        status="accepted",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("system_gap", "assigned-b")],
        provenance_refs=[provenance("contract_fixture", "key-fixtures")],
    )
    assigned_other = build_data_debt_card(
        gap_id="market-index-a",
        gap_summary="another debt",
        scope=ObjectScope(kind="universe", refs=["ST panel"]),
        missing_assets=["market_index_daily_series"],
        missing_fields=["trade_date", "close"],
        blocked_question_card_refs=["QC-20260710-014"],
        owner="data-engineering",
        external_debt_ref="D-051D",
        debt_ref_status="assigned",
        status="accepted",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("system_gap", "assigned-other")],
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
    dimension_other = build_question_card(
        canonical_question="不同分析维度",
        dimensions=["shareholder_count"],
        source_refs=[source("research_run", "run-dimension")],
        **{key: value for key, value in base.items() if key != "dimensions"},
    )
    template_a = build_query_template_record(
        template_id="QT-999",
        definition_version="draft-v1",
        question_pattern="draft one",
        parameter_schema=[
            QueryParameterSpec(name="symbol", value_type="string", required=True)
        ],
        outcome_semantics=["event_timing"],
        caveats=["not evidence"],
        proposed_executor_ref="proposal:event-timing",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("human_review", "template-a")],
        provenance_refs=[provenance("contract_fixture", "key-fixtures")],
    )
    template_b = build_query_template_record(
        template_id="QT-999",
        definition_version="draft-v1",
        question_pattern="draft two",
        parameter_schema=[
            QueryParameterSpec(name="cohort", value_type="string", required=True)
        ],
        outcome_semantics=["distribution"],
        caveats=["not evidence"],
        proposed_executor_ref="proposal:event-timing",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("human_review", "template-b")],
        provenance_refs=[provenance("contract_fixture", "key-fixtures")],
    )
    review_a = build_review_item(
        uncertainty_type="question_semantic_identity",
        subject_ref=ReviewSubjectRef(
            subject_type="question_card", subject_id=synonym_a.memory_id
        ),
        decision_unit="one_question_candidate",
        evidence_package_refs=[provenance("research_response", "response-a")],
        recommended_action="accept_candidate",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("human_review", "review-a")],
        provenance_refs=[provenance("contract_fixture", "key-fixtures")],
    )
    review_same_identity = build_review_item(
        uncertainty_type="question_semantic_identity",
        subject_ref=ReviewSubjectRef(
            subject_type="question_card", subject_id=synonym_a.memory_id
        ),
        decision_unit="one_question_candidate",
        evidence_package_refs=[provenance("research_response", "response-b")],
        recommended_action="request_more_evidence",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("human_review", "review-b")],
        provenance_refs=[provenance("contract_fixture", "key-fixtures")],
    )
    review_other_unit = build_review_item(
        uncertainty_type="question_semantic_identity",
        subject_ref=ReviewSubjectRef(
            subject_type="question_card", subject_id=synonym_a.memory_id
        ),
        decision_unit="question_and_scope_pair",
        evidence_package_refs=[provenance("research_response", "response-a")],
        recommended_action="accept_candidate",
        status="candidate",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("human_review", "review-c")],
        provenance_refs=[provenance("contract_fixture", "key-fixtures")],
    )
    feedback_a = build_feedback_event(
        feedback_kind="wording_issue",
        target_type="research_run",
        target_ref="run-key-001",
        feedback_text="措辞过强",
        status="accepted",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("user_question", "feedback-key-a")],
        provenance_refs=[provenance("user_feedback", "feedback-key")],
    )
    feedback_same_target = build_feedback_event(
        feedback_kind="wording_issue",
        target_type="research_run",
        target_ref="run-key-001",
        feedback_text="应该降低结论强度",
        status="accepted",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("user_question", "feedback-key-b")],
        provenance_refs=[provenance("user_feedback", "feedback-key")],
    )
    feedback_other_run = build_feedback_event(
        feedback_kind="wording_issue",
        target_type="research_run",
        target_ref="run-key-002",
        feedback_text="措辞过强",
        status="accepted",
        created_at=STAMP,
        updated_at=STAMP,
        source_refs=[source("user_question", "feedback-key-c")],
        provenance_refs=[provenance("user_feedback", "feedback-key")],
    )
    return {
        "synonym_different_runs": {
            "first": synonym_a.model_dump(mode="json"),
            "second": synonym_b.model_dump(mode="json"),
            "expect_same_dedupe_key": True,
            "expect_different_source_refs": True,
        },
        "seed_and_online_semantic_equivalence": {
            "first": seed_equivalent.model_dump(mode="json"),
            "second": online_equivalent.model_dump(mode="json"),
            "expect_same_dedupe_key": True,
            "expect_different_source_refs": True,
        },
        "registered_semantic_alias_equivalence": {
            "first": online_equivalent.model_dump(mode="json"),
            "second": registry_alias_equivalent.model_dump(mode="json"),
            "expect_same_dedupe_key": True,
            "expect_different_source_refs": True,
        },
        "provisional_unknown_retry_stability": {
            "first": provisional_lawsuit.model_dump(mode="json"),
            "second": provisional_lawsuit_retry.model_dump(mode="json"),
            "expect_same_dedupe_key": True,
            "expect_different_source_refs": True,
        },
        "provisional_unknown_question_separation": {
            "first": provisional_lawsuit.model_dump(mode="json"),
            "second": provisional_auditor.model_dump(mode="json"),
            "expect_same_dedupe_key": False,
        },
        "same_gap_different_scope": {
            "first": debt_stock.model_dump(mode="json"),
            "second": debt_universe.model_dump(mode="json"),
            "expect_same_dedupe_key": False,
        },
        "assigned_debt_same_ref_changed_description": {
            "first": assigned_a.model_dump(mode="json"),
            "second": assigned_b.model_dump(mode="json"),
            "expect_same_dedupe_key": True,
        },
        "assigned_debt_different_ref": {
            "first": assigned_a.model_dump(mode="json"),
            "second": assigned_other.model_dump(mode="json"),
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
        "different_dimensions": {
            "first": synonym_a.model_dump(mode="json"),
            "second": dimension_other.model_dump(mode="json"),
            "expect_same_dedupe_key": False,
        },
        "query_template_semantic_collision_guard": {
            "first": template_a.model_dump(mode="json"),
            "second": template_b.model_dump(mode="json"),
            "expect_same_dedupe_key": False,
        },
        "review_same_decision_unit_changed_package": {
            "first": review_a.model_dump(mode="json"),
            "second": review_same_identity.model_dump(mode="json"),
            "expect_same_dedupe_key": True,
        },
        "review_different_decision_unit": {
            "first": review_a.model_dump(mode="json"),
            "second": review_other_unit.model_dump(mode="json"),
            "expect_same_dedupe_key": False,
        },
        "feedback_same_target_changed_wording": {
            "first": feedback_a.model_dump(mode="json"),
            "second": feedback_same_target.model_dump(mode="json"),
            "expect_same_dedupe_key": True,
            "expect_different_source_refs": True,
        },
        "feedback_different_research_run": {
            "first": feedback_a.model_dump(mode="json"),
            "second": feedback_other_run.model_dump(mode="json"),
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
    question_without_dimensions = dict(question)
    question_without_dimensions.pop("dimensions")
    question_unknown_intent = dict(question)
    question_unknown_intent["semantic_intent"] = "llm_freeform_intent"
    question_unknown_dimension = dict(question)
    question_unknown_dimension["dimensions"] = ["llm_freeform_dimension"]
    question_unknown_registry = dict(question)
    question_unknown_registry["semantic_registry_version"] = "unversioned"
    question_backlog_without_source = dict(question)
    question_backlog_without_source["original_source"] = "post_v7_backlog"
    provisional = valid["question_card_provisional_unknown"].model_dump(mode="json")
    provisional_accepted = dict(provisional)
    provisional_accepted["status"] = "accepted"
    provisional_answerable = dict(provisional)
    provisional_answerable["research_status"] = "answerable"
    provisional_missing_identity = dict(provisional)
    provisional_missing_identity["provisional_identity"] = None
    provisional_tampered_fingerprint = json.loads(json.dumps(provisional))
    provisional_tampered_fingerprint["provisional_identity"]["question_fingerprint"] = (
        "0" * 64
    )
    evidence_identity = {**question, "evidence_grade": "supported"}
    bad_identity = {**question, "dedupe_key": "0" * 64}
    naive_time = {**question, "created_at": "2026-07-11T00:00:00"}
    draft = valid["query_template_record"].model_dump(mode="json")
    draft.update({"status": "candidate", "executable": True})
    unassigned = valid["data_debt_unassigned"].model_dump(mode="json")
    unassigned["external_debt_ref"] = "D-FAKE"
    run_without_route = valid["research_run_ref"].model_dump(mode="json")
    run_without_route.pop("route")
    debt_without_assets = valid["data_debt_unassigned"].model_dump(mode="json")
    debt_without_assets["missing_assets"] = []
    debt_without_owner = valid["data_debt_unassigned"].model_dump(mode="json")
    debt_without_owner.pop("owner")
    debt_without_blocked_refs = valid["data_debt_unassigned"].model_dump(mode="json")
    debt_without_blocked_refs.pop("blocked_question_card_refs")
    review_without_evidence = valid["review_item"].model_dump(mode="json")
    review_without_evidence["evidence_package_refs"] = []
    review_without_action = valid["review_item"].model_dump(mode="json")
    review_without_action.pop("recommended_action")
    result_overlap = valid["sedimentation_result"].model_dump(mode="json")
    result_overlap["existing"] = list(result_overlap["created"])
    result_without_merged = valid["sedimentation_result"].model_dump(mode="json")
    result_without_merged.pop("merged")
    legacy_feedback_kind = valid["feedback_event"].model_dump(mode="json")
    legacy_feedback_kind["feedback_kind"] = "missing_context"
    return {
        "missing_source_refs": {
            "model": "QuestionCard", "payload": no_source, "schema_must_reject": True,
        },
        "missing_provenance_refs": {
            "model": "QuestionCard", "payload": no_provenance, "schema_must_reject": True,
        },
        "question_missing_dimensions": {
            "model": "QuestionCard",
            "payload": question_without_dimensions,
            "schema_must_reject": True,
        },
        "question_unknown_intent": {
            "model": "QuestionCard",
            "payload": question_unknown_intent,
            "schema_must_reject": True,
        },
        "question_unknown_dimension": {
            "model": "QuestionCard",
            "payload": question_unknown_dimension,
            "schema_must_reject": True,
        },
        "question_unknown_semantic_registry": {
            "model": "QuestionCard",
            "payload": question_unknown_registry,
            "schema_must_reject": True,
        },
        "question_backlog_without_matching_source": {
            "model": "QuestionCard",
            "payload": question_backlog_without_source,
        },
        "provisional_unknown_accepted": {
            "model": "QuestionCard",
            "payload": provisional_accepted,
        },
        "provisional_unknown_answerable": {
            "model": "QuestionCard",
            "payload": provisional_answerable,
        },
        "provisional_unknown_missing_identity": {
            "model": "QuestionCard",
            "payload": provisional_missing_identity,
        },
        "provisional_unknown_tampered_fingerprint": {
            "model": "QuestionCard",
            "payload": provisional_tampered_fingerprint,
        },
        "evidence_identity_forbidden": {
            "model": "QuestionCard", "payload": evidence_identity, "schema_must_reject": True,
        },
        "tampered_dedupe_key": {"model": "QuestionCard", "payload": bad_identity},
        "timezone_naive": {"model": "QuestionCard", "payload": naive_time},
        "feedback_legacy_kind": {
            "model": "FeedbackEvent",
            "payload": legacy_feedback_kind,
            "schema_must_reject": True,
        },
        "draft_template_executable": {"model": "QueryTemplateRecord", "payload": draft},
        "unassigned_debt_with_ref": {"model": "DataDebtCard", "payload": unassigned},
        "research_run_missing_route": {
            "model": "ResearchRunRef",
            "payload": run_without_route,
            "schema_must_reject": True,
        },
        "data_debt_missing_assets": {
            "model": "DataDebtCard",
            "payload": debt_without_assets,
            "schema_must_reject": True,
        },
        "data_debt_missing_owner": {
            "model": "DataDebtCard",
            "payload": debt_without_owner,
            "schema_must_reject": True,
        },
        "data_debt_missing_blocked_refs": {
            "model": "DataDebtCard",
            "payload": debt_without_blocked_refs,
            "schema_must_reject": True,
        },
        "review_missing_evidence_package": {
            "model": "ReviewItem",
            "payload": review_without_evidence,
            "schema_must_reject": True,
        },
        "review_missing_recommended_action": {
            "model": "ReviewItem",
            "payload": review_without_action,
            "schema_must_reject": True,
        },
        "sedimentation_partition_overlap": {
            "model": "SedimentationResult",
            "payload": result_overlap,
        },
        "sedimentation_missing_merged_partition": {
            "model": "SedimentationResult",
            "payload": result_without_merged,
            "schema_must_reject": True,
        },
        "illegal_transition": {
            "model": "StatusTransition",
            "payload": {
                "record_type": "status_transition",
                "object_type": "question_card",
                "from_status": "closed",
                "to_status": "accepted",
                "actor_type": "human",
                "context": "online",
                "reason": "illegal reopen",
            },
        },
        "automatic_merge": {
            "model": "StatusTransition",
            "payload": {
                "record_type": "status_transition",
                "object_type": "question_card",
                "from_status": "candidate",
                "to_status": "merged",
                "actor_type": "system",
                "context": "online",
                "reason": "automatic similarity merge",
                "merge_target_id": "MEM-QC-TARGET",
            },
        },
        "system_accept_candidate": {
            "model": "StatusTransition",
            "payload": {
                "record_type": "status_transition",
                "object_type": "question_card",
                "from_status": "candidate",
                "to_status": "accepted",
                "actor_type": "system",
                "context": "online",
                "reason": "automatic accept",
            },
        },
        "system_ignore_candidate": {
            "model": "StatusTransition",
            "payload": {
                "record_type": "status_transition",
                "object_type": "question_card",
                "from_status": "candidate",
                "to_status": "ignored",
                "actor_type": "system",
                "context": "online",
                "reason": "automatic ignore",
            },
        },
        "llm_transition": {
            "model": "StatusTransition",
            "payload": {
                "record_type": "status_transition",
                "object_type": "question_card",
                "from_status": "candidate",
                "to_status": "blocked",
                "actor_type": "llm",
                "context": "online",
                "reason": "LLM status decision",
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
            parameter_schema=[
                QueryParameterSpec(name=name, value_type="string", required=True)
                for name in template.required_inputs
            ],
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

    dump(HERE / "question_semantic_registry.json", question_semantic_registry_payload())
    dump(HERE / "schema.json", public_contract_schema())
    for name, value in valid.items():
        dump(VALID / f"{name}.json", value)
    dump(FIXTURES / "key_cases.json", key_fixtures())
    dump(FIXTURES / "feedback_taxonomy.json", feedback_taxonomy_fixtures())
    dump(FIXTURES / "query_template_records.json", query_template_records())
    dump(
        FIXTURES / "status_transitions.json",
        {
            "transition_table": {key: list(value) for key, value in STATUS_TRANSITIONS.items()},
            "valid_human_merge": StatusTransition(
                record_type="status_transition",
                object_type="question_card",
                from_status="accepted",
                to_status="merged",
                actor_type="human",
                context="online",
                reason="review confirmed duplicate",
                merge_target_id=migrated[0].memory_id,
            ).model_dump(mode="json"),
            "valid_human_candidate_merge": StatusTransition(
                record_type="status_transition",
                object_type="question_card",
                from_status="candidate",
                to_status="merged",
                actor_type="human",
                context="online",
                reason="human review matched an existing semantic object",
                merge_target_id=migrated[0].memory_id,
            ).model_dump(mode="json"),
            "valid_seed_migration_acceptance": StatusTransition(
                record_type="status_transition",
                object_type="question_card",
                from_status="candidate",
                to_status="accepted",
                actor_type="migration",
                context="seed_bootstrap",
                reason="controlled import of frozen question-card seed",
            ).model_dump(mode="json"),
        },
    )
    review_items = []
    for index in range(REVIEW_ACTIVE_LIMIT):
        item = build_review_item(
            uncertainty_type="question_semantic_identity",
            subject_ref=ReviewSubjectRef(
                subject_type="question_card",
                subject_id=f"MEM-QC-CAPACITY-{index:02d}",
            ),
            decision_unit=f"question-candidate-{index:02d}",
            evidence_package_refs=[
                provenance("contract_fixture", f"review-capacity-{index:02d}")
            ],
            recommended_action="accept_candidate",
            priority=index,
            status="candidate",
            created_at=STAMP,
            updated_at=STAMP,
            source_refs=[source("human_review", f"review-capacity-{index:02d}")],
            provenance_refs=[provenance("contract_fixture", "review-capacity")],
        )
        review_items.append(item)
    dump(
        FIXTURES / "review_capacity.json",
        {
            "max_active_items": REVIEW_ACTIVE_LIMIT,
            "active_items": [item.model_dump(mode="json") for item in review_items],
            "repository_must_reject_active_count_above": REVIEW_ACTIVE_LIMIT,
        },
    )

    for name, value in invalid_payloads(valid).items():
        dump(INVALID / f"{name}.json", value)

    MIGRATION.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SEED_PATH, MIGRATION / "question_card_seeds_v0.jsonl")
    dump(MIGRATION / "semantic_mapping.json", SEED_SEMANTICS)
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
            record_type="sedimentation_result",
            contract_version=RESEARCH_MEMORY_CONTRACT_VERSION,
            operation_id="seed-import-first",
            created=[object_ref("question_card", item) for item in migrated],
            existing=[],
            merged=[],
            ignored=[],
            created_links=first_links,
            completed_at=STAMP,
        ),
    )
    dump(
        MIGRATION / "second_import_result.json",
        SedimentationResult(
            record_type="sedimentation_result",
            contract_version=RESEARCH_MEMORY_CONTRACT_VERSION,
            operation_id="seed-import-second",
            created=[],
            existing=[object_ref("question_card", item) for item in migrated],
            merged=[],
            ignored=[],
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
            "schema_entrypoint": "record_type_discriminated_union",
            "python_types": "research_memory_contract.py",
            "canonical_key_encoding": "sorted_compact_json_utf8",
            "question_semantic_registry": "question_semantic_registry.json",
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
