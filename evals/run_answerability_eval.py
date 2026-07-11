"""Product gate: lawful routing is insufficient unless answerable questions return evidence."""
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_contract import ResearchRequest
from orchestrator import orchestrate


SET_PATH = Path(__file__).with_name("answerability_set_v0.jsonl")


def load_cases() -> list[dict]:
    return [
        json.loads(line)
        for line in SET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def evaluate() -> tuple[int, int]:
    cases = load_cases()
    failures: list[str] = []
    for case in cases:
        response = orchestrate(ResearchRequest(
            request_id=f"eval-{case['id'].lower()}",
            question=case["question"],
            llm_mode="off",
        ))
        if response.route.route != case["expected_route"]:
            failures.append(
                f"{case['id']}: route={response.route.route}, expected={case['expected_route']}"
            )
            continue
        expected_symbol = case.get("expected_symbol")
        if expected_symbol and response.interpretation.object.ref != expected_symbol:
            failures.append(
                f"{case['id']}: symbol={response.interpretation.object.ref}, expected={expected_symbol}"
            )
        card = response.answer_card
        if case["require_answer_card"] and card is None:
            failures.append(f"{case['id']}: answerable route returned no AnswerCard")
            continue
        if not case["require_answer_card"] and card is not None:
            failures.append(f"{case['id']}: non-answer route unexpectedly returned AnswerCard")
            continue
        if card is None:
            if not response.gaps:
                failures.append(f"{case['id']}: non-answer route returned no explicit gap")
            continue
        if not response.claims or not card.get("body_rows") or not card.get("provenance"):
            failures.append(f"{case['id']}: AnswerCard lacks claims, rows, or provenance")
            continue
        row_ids = [str(row.get("row_id", "")) for row in card["body_rows"]]
        for prefix in case["required_row_prefixes"]:
            if not any(row_id.startswith(prefix) for row_id in row_ids):
                failures.append(f"{case['id']}: missing row prefix {prefix}")
        provenance = "\n".join(str(item) for item in card["provenance"])
        for source in case["required_provenance"]:
            if source not in provenance:
                failures.append(f"{case['id']}: missing provenance {source}")
    if failures:
        raise AssertionError("\n".join(failures))
    return len(cases), len(cases)


if __name__ == "__main__":
    passed, total = evaluate()
    print(f"[OK] evidence answerability {passed}/{total}")
