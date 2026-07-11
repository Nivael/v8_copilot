import json
from pathlib import Path

from jsonschema import Draft202012Validator

from answer_engine import BASE_DB, EPISODE_INDEX, card_next_node_gap
from lens_binding import RELEASE_LIBRARY
from run_seeds import write_seed_cards


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "contracts/v8_answer_contract_v0/schema.json"
)


def test_real_seed_cards_validate_and_preserve_read_only_sources(tmp_path: Path) -> None:
    sources = [BASE_DB, EPISODE_INDEX, RELEASE_LIBRARY]
    before = {path: path.stat().st_mtime_ns for path in sources}

    cards = write_seed_cards(tmp_path)

    after = {path: path.stat().st_mtime_ns for path in sources}
    assert before == after
    assert len(cards) == 7

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for card in cards.values():
        validator.validate(card)

    written = json.loads((tmp_path / "answer_cards.json").read_text(encoding="utf-8"))
    assert written == cards
    assert (tmp_path / "answer_cards.md").read_text(encoding="utf-8").startswith(
        "# v8 Answer Engine"
    )


def test_seed_cards_keep_known_baseline_values(tmp_path: Path) -> None:
    cards = write_seed_cards(tmp_path)

    timing = cards["slice01_next_node_gap"]["body_rows"]
    assert [row["中位(天)"] for row in timing] == [4, 10, 14]

    two_week = cards["slice02_two_week_move"]["body_rows"][0]
    assert two_week["p05"] == "-15.5%"
    assert two_week["p50"] == "-0.5%"
    assert two_week["p95"] == "17.6%"

    evidence = cards["slice04_calendar_evidence_a001"]
    assert evidence["view"] == "evidence"
    assert evidence["lens_invocations"][0]["release_id"] == "RL-A-001"
    assert evidence["body_rows"][0]["触发样本N"] == 16215
    assert evidence["body_rows"][0]["对照样本N"] == 20462

    debt = cards["slice06_province_data_debt"]
    assert debt["view"] == "data_debt"
    assert debt["data_debt_refs"] == ["D-051A"]

    status = cards["slice07_st_status_timeline"]
    assert status["view"] == "query"
    status_rows = [
        row for row in status["body_rows"]
        if row["row_id"].startswith("st_interval_")
    ]
    assert {row["状态"] for row in status_rows} == {"*ST沐邦:*ST", "*ST沐邦"}
    assert any(
        row["row_id"].startswith("st_trigger_announcement_")
        for row in status["body_rows"]
    )


def test_unknown_episode_subtype_returns_stable_empty_distribution() -> None:
    card = card_next_node_gap("subtype_that_does_not_exist")

    card.validate()
    assert card.sample_scope.endswith("0 只股票 / 0 触发事件")
    assert [row["N"] for row in card.body_rows] == [0, 0, 0]
    assert [row["中位(天)"] for row in card.body_rows] == [None, None, None]
