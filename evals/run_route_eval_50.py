from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.deterministic_router_v0 import route_question
from evals.run_route_eval import evaluate_routes
from evals.validate_w2_evals import QUESTION_SET, load_jsonl


PARAPHRASE_SET = Path(__file__).with_name("question_routing_paraphrases_v0.jsonl")


def main() -> int:
    canonical = load_jsonl(QUESTION_SET)
    canonical_result = evaluate_routes(canonical)
    paraphrases = load_jsonl(PARAPHRASE_SET)
    failures = [
        {
            "id": row["id"],
            "expected": row["expected_route"],
            "actual": route_question(row).predicted_route,
        }
        for row in paraphrases
        if route_question(row).predicted_route != row["expected_route"]
    ]
    passed = canonical_result.passed + len(paraphrases) - len(failures)
    if canonical_result.ok and not failures:
        print(f"[OK] final lawful route matched {passed}/50 questions")
        return 0
    print(json.dumps({
        "canonical": canonical_result.to_dict(),
        "paraphrase_failures": failures,
    }, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
