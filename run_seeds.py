"""通过统一引擎生成 P1 种子答案卡，并写出 JSON/Markdown。"""
import json
from pathlib import Path
from typing import Callable

from answer_engine import (
    AnswerCard,
    card_calendar_regime_evidence,
    card_consolidation_checklist,
    card_next_node_gap,
    card_province_mapping_debt,
    card_st_status_timeline,
    card_two_week_move,
)

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)


def seed_builders() -> list[tuple[str, Callable[[], AnswerCard]]]:
    return [
        ("slice01_next_node_gap", card_next_node_gap),
        ("slice02_two_week_move", card_two_week_move),
        ("slice03_consolidation_checklist", lambda: card_consolidation_checklist("603398")),
        ("slice04_calendar_evidence_a001", lambda: card_calendar_regime_evidence("RL-A-001")),
        ("slice05_calendar_evidence_a002", lambda: card_calendar_regime_evidence("RL-A-002")),
        ("slice06_province_data_debt", card_province_mapping_debt),
        ("slice07_st_status_timeline", lambda: card_st_status_timeline("603398")),
    ]


def write_seed_cards(out_dir: Path = OUT) -> dict[str, dict]:
    out_dir.mkdir(exist_ok=True, parents=True)
    cards_json = {}
    md_parts = ["# v8 Answer Engine — P1 种子答案卡（引擎生成）\n"]
    for name, fn in seed_builders():
        card = fn()
        card.validate()
        cards_json[name] = card.to_dict()
        md_parts.append(card.to_markdown())
        md_parts.append("\n---\n")
        print(f"[OK] {name}: 契约通过 · view={card.view} · grade={card.evidence_grade}")
    (out_dir / "answer_cards.json").write_text(
        json.dumps(cards_json, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "answer_cards.md").write_text("\n".join(md_parts), encoding="utf-8")
    return cards_json


def main() -> None:
    write_seed_cards(OUT)
    print(f"\n写出：{OUT/'answer_cards.json'}\n      {OUT/'answer_cards.md'}")


if __name__ == "__main__":
    main()
