from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    from evals.deterministic_router_v0 import RoutePrediction, route_question
    from evals.validate_w2_evals import QUESTION_SET, load_jsonl, validate_question_routes
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from evals.deterministic_router_v0 import RoutePrediction, route_question
    from evals.validate_w2_evals import QUESTION_SET, load_jsonl, validate_question_routes


@dataclass(frozen=True)
class RouteEvalFailure:
    id: str
    user_question: str
    field: str
    expected: Any
    actual: Any
    prediction: dict[str, Any]


@dataclass(frozen=True)
class RouteEvalResult:
    total: int
    passed: int
    failures: list[RouteEvalFailure]
    route_counts: dict[str, int]

    @property
    def ok(self) -> bool:
        return not self.failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "failures": [asdict(f) for f in self.failures],
            "route_counts": self.route_counts,
        }


def _expected_subset(expected: list[str], actual: list[str]) -> bool:
    return set(expected).issubset(set(actual))


def _compare(row: dict[str, Any], prediction: RoutePrediction) -> list[RouteEvalFailure]:
    pred = prediction.to_dict()
    checks: list[tuple[str, Any, Any, str]] = [
        ("expected_route", row["expected_route"], prediction.predicted_route, "exact"),
        ("expected_status", row["expected_status"], prediction.expected_status, "exact"),
        ("expected_view", row["expected_view"], prediction.expected_view, "exact"),
        (
            "required_lens_behavior",
            row["required_lens_behavior"],
            prediction.required_lens_behavior,
            "exact",
        ),
        (
            "required_data_debt_refs",
            sorted(row["required_data_debt_refs"]),
            sorted(prediction.required_data_debt_refs),
            "exact",
        ),
        (
            "required_question_card_refs",
            row["required_question_card_refs"],
            prediction.required_question_card_refs,
            "subset",
        ),
    ]
    failures = []
    for field, expected, actual, mode in checks:
        if mode == "exact":
            passed = expected == actual
        elif mode == "subset":
            passed = _expected_subset(expected, actual)
        else:
            raise ValueError(f"unknown compare mode: {mode}")
        if not passed:
            failures.append(RouteEvalFailure(
                id=row["id"],
                user_question=row["user_question"],
                field=field,
                expected=expected,
                actual=actual,
                prediction=pred,
            ))
    return failures


def evaluate_routes(rows: list[dict[str, Any]]) -> RouteEvalResult:
    validate_question_routes(rows)
    failures: list[RouteEvalFailure] = []
    route_counts: Counter[str] = Counter()
    for row in rows:
        prediction = route_question(row)
        route_counts[prediction.predicted_route] += 1
        failures.extend(_compare(row, prediction))

    failed_ids = {f.id for f in failures}
    return RouteEvalResult(
        total=len(rows),
        passed=len(rows) - len(failed_ids),
        failures=failures,
        route_counts=dict(sorted(route_counts.items())),
    )


def main() -> int:
    rows = load_jsonl(QUESTION_SET)
    result = evaluate_routes(rows)
    if result.ok:
        print(f"[OK] deterministic router matched {result.passed}/{result.total} questions")
        print("[OK] predicted route coverage:", result.route_counts)
        return 0

    print(
        f"[FAIL] deterministic router matched {result.passed}/{result.total} questions",
        file=sys.stderr,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
