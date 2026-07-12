"""P2.3 product gate for non-demo questions and readable, focus-aligned answers."""
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api import orchestrate_deterministic
from api_contract import ResearchRequest


SET_PATH = Path(__file__).with_name("real_question_answerability_set_v1.jsonl")


def load_cases() -> list[dict]:
    return [
        json.loads(line)
        for line in SET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def evaluate() -> tuple[int, int]:
    failures: list[str] = []
    cases = load_cases()
    for case in cases:
        response = orchestrate_deterministic(ResearchRequest(
            request_id=f"eval-{case['id'].lower()}",
            question=case["question"],
            llm_mode="off",
        ))
        if response.route.route != case["expected_route"]:
            failures.append(
                f"{case['id']}: route={response.route.route}, expected={case['expected_route']}"
            )
        expected_symbol = case.get("expected_symbol")
        if expected_symbol and response.interpretation.object.ref != expected_symbol:
            failures.append(
                f"{case['id']}: symbol={response.interpretation.object.ref}, expected={expected_symbol}"
            )
        card = response.answer_card
        if bool(card) != bool(case["require_card"]):
            failures.append(f"{case['id']}: card presence={bool(card)}")
            continue
        rows = (card or {}).get("body_rows", [])
        row_ids = [str(row.get("row_id") or "") for row in rows]
        for prefix in case["required_rows"]:
            if not any(row_id.startswith(prefix) for row_id in row_ids):
                failures.append(f"{case['id']}: missing row {prefix}")
        narrative_text = ""
        if response.narrative:
            narrative_text = "\n".join([
                response.narrative.direct_answer.text,
                *(step.title + "\n" + step.text for step in response.narrative.reasoning_steps),
                *(item.text for item in response.narrative.uncertainties),
                *(item.text for item in response.narrative.watch_items),
            ])
        for text in case["required_narrative"]:
            if text not in narrative_text:
                failures.append(f"{case['id']}: narrative missing {text!r}")
        for text in case["forbidden_narrative"]:
            if text in narrative_text:
                failures.append(f"{case['id']}: narrative contains forbidden {text!r}")
    if failures:
        raise AssertionError("\n".join(failures))
    return len(cases), len(cases)


if __name__ == "__main__":
    passed, total = evaluate()
    print(f"[OK] real-question answerability {passed}/{total}")
