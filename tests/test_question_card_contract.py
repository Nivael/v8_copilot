import pytest
from pydantic import ValidationError

from question_cards import QuestionCard, candidate_id


def card_payload(**updates):
    payload = {
        "id": "QC-20260710-011",
        "question": "同一问题按省份分层如何？",
        "object": {"kind": "cohort", "ref": "restructuring"},
        "needs_data": ["symbol_to_province"],
        "status": "needs_data",
        "view": "data_debt",
        "source": "system_gap",
        "debt_ref": "D-051A",
        "created_from": [{"kind": "data_debt", "ref": "D-051A"}],
    }
    payload.update(updates)
    return payload


def test_question_card_lifecycle_accepts_registered_data_debt() -> None:
    card = QuestionCard.model_validate(card_payload())

    assert card.debt_ref == "D-051A"


@pytest.mark.parametrize(
    "updates",
    [
        {"debt_ref": None},
        {"needs_data": []},
        {"status": "answerable", "view": "data_debt", "debt_ref": None},
        {"status": "needs_review", "debt_ref": "D-051A"},
    ],
)
def test_question_card_rejects_invalid_lifecycle(updates) -> None:
    with pytest.raises(ValidationError):
        QuestionCard.model_validate(card_payload(**updates))


def test_candidate_id_is_stable_and_scope_sensitive() -> None:
    first = candidate_id("未知问题", "stock", "603398")

    assert first == candidate_id("未知问题", "stock", "603398")
    assert first != candidate_id("未知问题", "stock", "000001")
    assert first.startswith("QC-CAND-")
