import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from answer_engine import (
    AnalysisClaim,
    AnswerCard,
    BackingRef,
    DataDebtRow,
    FIXED_CAVEATS,
    _pd,
)
from lens_binding import LensGap


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "contracts/v8_answer_contract_v0/schema.json"
)


def valid_card() -> AnswerCard:
    return AnswerCard(
        question="测试问题",
        object_ref="stock:000001",
        view="query",
        as_of="2026-07-10",
        sample_scope="测试样本 N=1",
        evidence_grade="descriptive_query",
        lens_gap=[LensGap(
            gap_id="test_gap",
            missing_for="测试证据",
            sediment_as="question_card:QC-TEST-001",
        )],
        body_rows=[{"row_id": "result_1", "value": 1}],
        caveats=list(FIXED_CAVEATS),
        provenance=["fixture:test"],
    )


def test_valid_card_passes_python_and_json_schema() -> None:
    card = valid_card()
    card.validate()

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(card.to_dict())


def test_card_requires_lens_spine() -> None:
    card = valid_card()
    card.lens_gap = []

    with pytest.raises(ValueError, match="缺脊梁"):
        card.validate()


def test_body_rows_require_unique_row_ids() -> None:
    card = valid_card()
    card.body_rows = [{"value": 1}, {"row_id": "same"}, {"row_id": "same"}]

    with pytest.raises(ValueError) as exc_info:
        card.validate()

    message = str(exc_info.value)
    assert "每行必须带 row_id" in message
    assert "row_id 重复" in message


def test_data_debt_rows_must_be_covered_by_refs() -> None:
    card = valid_card()
    card.data_debt = [DataDebtRow(gap="字段缺失", affects="分层", debt_ref="D-TEST")]

    with pytest.raises(ValueError, match="data_debt_refs 未覆盖"):
        card.validate()


def test_forbidden_wording_is_rejected() -> None:
    card = valid_card()
    card.question = "请给目标价"

    with pytest.raises(ValueError, match="命中禁用交易措辞"):
        card.validate()


def test_analysis_claim_requires_existing_backing() -> None:
    card = valid_card()
    card.analysis_claims = [AnalysisClaim(
        text="该数字来自不存在的结果行。",
        claim_type="fact",
        backing=BackingRef(kind="query_row", ref="missing_row"),
    )]

    with pytest.raises(ValueError, match="backing 无对应对象"):
        card.validate()


def test_analysis_claim_accepts_existing_backing() -> None:
    card = valid_card()
    card.analysis_claims = [AnalysisClaim(
        text="测试结果值为 1。",
        claim_type="fact",
        backing=BackingRef(kind="query_row", ref="result_1"),
    )]

    card.validate()


def test_analysis_claim_rejects_missing_backing_object() -> None:
    card = valid_card()
    card.analysis_claims = [AnalysisClaim(
        text="缺少 backing。",
        claim_type="fact",
        backing=None,  # type: ignore[arg-type]
    )]

    with pytest.raises(ValueError, match="缺合法 backing"):
        card.validate()


def test_data_debt_view_requires_debt_row() -> None:
    card = valid_card()
    card.view = "data_debt"
    card.evidence_grade = "insufficient_data"

    with pytest.raises(ValueError, match="data_debt 视图缺 data_debt 行"):
        card.validate()


def test_invalid_date_fails_loudly() -> None:
    with pytest.raises(ValueError, match="日期字段非法"):
        _pd("2026-99-99")
