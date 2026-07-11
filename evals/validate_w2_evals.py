from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"

QUESTION_SET = EVALS / "question_routing_set_v0.jsonl"
SEED_SET = EVALS / "question_card_seeds_v0.jsonl"
GOLDEN = EVALS / "golden_fact_assertions_v0.json"
REWRITE_SET = EVALS / "rewrite_routing_set_v0.jsonl"

LEGAL_ROUTES = {
    "answer_query",
    "answer_evidence",
    "answer_checklist",
    "answer_methodology",
    "data_debt",
    "lens_gap",
    "needs_review",
    "clarify",
    "refuse_or_rewrite",
}
LEGAL_STATUSES = {"answerable", "needs_data", "needs_review", "clarify", "boundary"}
LEGAL_VIEWS = {
    "query",
    "evidence",
    "checklist",
    "methodology",
    "data_debt",
    "lens_gap",
    "clarify",
    "boundary",
}
LEGAL_LENS_BEHAVIOR = {
    "lens_invocation_required",
    "lens_invocations_or_gap",
    "lens_gap_required",
    "not_applicable",
}
REQUIRED_ROUTE_COVERAGE = {
    "answer_query",
    "answer_evidence",
    "answer_checklist",
    "answer_methodology",
    "data_debt",
    "lens_gap",
    "needs_review",
    "clarify",
    "refuse_or_rewrite",
}
EXPECTED_SEED_STATUS_COUNTS = Counter({"answerable": 7, "needs_data": 7, "needs_review": 1})
KNOWN_SEED_DEBT_ASSIGNMENT_GAPS = {
    "QC-20260710-003",
    "QC-20260710-005",
}
LOCAL_PATH_RE = re.compile(r"/Users/|/home/|/private/var/")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise AssertionError(f"{path.name}:{lineno} is not valid JSON: {exc}") from exc
    return rows


def at_path(value: Any, path: list[Any]) -> Any:
    cur = value
    for part in path:
        cur = cur[part]
    return cur


def assert_no_local_paths(name: str, value: Any) -> None:
    blob = json.dumps(value, ensure_ascii=False)
    if LOCAL_PATH_RE.search(blob):
        raise AssertionError(f"{name} contains a machine-local absolute path")


def validate_question_routes(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 30:
        raise AssertionError(f"question routing set must contain 30 rows, got {len(rows)}")

    ids = [r.get("id") for r in rows]
    if len(ids) != len(set(ids)):
        raise AssertionError("question routing set has duplicate ids")

    route_counts = Counter()
    object_kinds = Counter()
    for row in rows:
        rid = row["id"]
        missing = {
            "id",
            "user_question",
            "source",
            "object",
            "expected_route",
            "expected_status",
            "expected_view",
            "required_backing",
            "required_provenance",
            "required_lens_behavior",
            "required_data_debt_refs",
            "required_question_card_refs",
            "forbidden_claims",
            "notes",
        } - set(row)
        if missing:
            raise AssertionError(f"{rid} missing fields: {sorted(missing)}")
        if "expected_answer" in row or "standard_answer" in row:
            raise AssertionError(f"{rid} must not handwrite a standard answer")
        if row["expected_route"] not in LEGAL_ROUTES:
            raise AssertionError(f"{rid} illegal route: {row['expected_route']}")
        if row["expected_status"] not in LEGAL_STATUSES:
            raise AssertionError(f"{rid} illegal status: {row['expected_status']}")
        if row["expected_view"] not in LEGAL_VIEWS:
            raise AssertionError(f"{rid} illegal view: {row['expected_view']}")
        if row["required_lens_behavior"] not in LEGAL_LENS_BEHAVIOR:
            raise AssertionError(f"{rid} illegal lens behavior: {row['required_lens_behavior']}")
        if not isinstance(row["required_backing"], list) or not row["required_backing"]:
            raise AssertionError(f"{rid} must state required backing")
        if not isinstance(row["forbidden_claims"], list) or len(row["forbidden_claims"]) < 2:
            raise AssertionError(f"{rid} must include at least two forbidden claims")
        if row["expected_route"] == "data_debt":
            has_debt_ref = bool(row["required_data_debt_refs"])
            has_known_gap = bool(row.get("known_seed_gap"))
            if not has_debt_ref and not has_known_gap:
                raise AssertionError(f"{rid} data_debt route needs debt refs or explicit known_seed_gap")
        if row["expected_route"] == "lens_gap" and not row["required_question_card_refs"]:
            raise AssertionError(f"{rid} lens_gap route must sediment into a QuestionCard ref")
        if row["expected_route"] == "refuse_or_rewrite":
            if row["expected_view"] != "boundary" or row["required_lens_behavior"] != "not_applicable":
                raise AssertionError(f"{rid} boundary route must use boundary/not_applicable")
        if row["expected_route"] == "clarify":
            if row["expected_view"] != "clarify" or row["required_lens_behavior"] != "not_applicable":
                raise AssertionError(f"{rid} clarify route must use clarify/not_applicable")
        route_counts[row["expected_route"]] += 1
        object_kinds[row["object"].get("kind", "?")] += 1

    missing_routes = REQUIRED_ROUTE_COVERAGE - set(route_counts)
    if missing_routes:
        raise AssertionError(f"question set is missing route coverage: {sorted(missing_routes)}")
    if object_kinds["stock"] < 5:
        raise AssertionError("question set should include at least five stock-scoped questions")


def validate_rewrite_routes(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 20:
        raise AssertionError(f"rewrite routing set must contain 20 rows, got {len(rows)}")
    ids = [row.get("rewrite_id") for row in rows]
    if any(not rewrite_id for rewrite_id in ids):
        raise AssertionError("rewrite routing set has empty rewrite_id")
    if len(ids) != len(set(ids)):
        raise AssertionError("rewrite routing set has duplicate rewrite_id")
    for row in rows:
        rewrite_id = row["rewrite_id"]
        missing = {"rewrite_id", "user_question", "object", "expected_route"} - set(row)
        if missing:
            raise AssertionError(f"{rewrite_id} missing fields: {sorted(missing)}")
        if row["expected_route"] != "refuse_or_rewrite":
            raise AssertionError(f"{rewrite_id} must route to refuse_or_rewrite")
        if not row["user_question"]:
            raise AssertionError(f"{rewrite_id} has empty user_question")
        if not row["object"].get("kind") or not row["object"].get("ref"):
            raise AssertionError(f"{rewrite_id} has invalid object")


def validate_question_seeds(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 15:
        raise AssertionError(f"QuestionCard seed set must contain 15 rows, got {len(rows)}")

    ids = [r.get("id") for r in rows]
    if len(ids) != len(set(ids)):
        raise AssertionError("QuestionCard seed set has duplicate ids")
    if Counter(r["status"] for r in rows) != EXPECTED_SEED_STATUS_COUNTS:
        got = Counter(r["status"] for r in rows)
        raise AssertionError(f"QuestionCard seed status drift: expected {EXPECTED_SEED_STATUS_COUNTS}, got {got}")

    gaps = set()
    for row in rows:
        rid = row["id"]
        if row["status"] not in {"answerable", "needs_data", "needs_review"}:
            raise AssertionError(f"{rid} illegal seed status: {row['status']}")
        if row["status"] == "needs_data":
            if row["debt_ref_status"] == "assigned" and not row["debt_ref"]:
                raise AssertionError(f"{rid} says debt assigned but debt_ref is empty")
            if row["debt_ref_status"] == "needs_assignment":
                gaps.add(rid)
        else:
            if row["debt_ref"]:
                raise AssertionError(f"{rid} unexpectedly has debt_ref despite status={row['status']}")

    if gaps != KNOWN_SEED_DEBT_ASSIGNMENT_GAPS:
        raise AssertionError(
            "QuestionCard debt assignment gap drift: "
            f"expected {sorted(KNOWN_SEED_DEBT_ASSIGNMENT_GAPS)}, got {sorted(gaps)}"
        )


def validate_golden_assertions(spec: dict[str, Any]) -> None:
    cards_path = ROOT / spec["answer_cards_path"]
    cards = json.loads(cards_path.read_text(encoding="utf-8"))
    for assertion in spec["assertions"]:
        aid = f"{assertion['card']}:{assertion['path']}"
        value = at_path(cards[assertion["card"]], assertion["path"])
        if "equals" in assertion and value != assertion["equals"]:
            raise AssertionError(f"{aid} expected {assertion['equals']!r}, got {value!r}")
        if "contains" in assertion and assertion["contains"] not in value:
            raise AssertionError(f"{aid} expected to contain {assertion['contains']!r}, got {value!r}")
        if "len" in assertion and len(value) != assertion["len"]:
            raise AssertionError(f"{aid} expected len {assertion['len']}, got {len(value)}")
        if "min_len" in assertion and len(value) < assertion["min_len"]:
            raise AssertionError(f"{aid} expected len >= {assertion['min_len']}, got {len(value)}")

    for card_id, card in cards.items():
        if not (card.get("lens_invocations") or card.get("lens_gap")):
            raise AssertionError(f"{card_id} has neither lens_invocations nor lens_gap")
        if not card.get("provenance"):
            raise AssertionError(f"{card_id} has no provenance")
        if not card.get("source_freshness"):
            raise AssertionError(f"{card_id} has no source_freshness")


def main() -> int:
    question_rows = load_jsonl(QUESTION_SET)
    rewrite_rows = load_jsonl(REWRITE_SET)
    seed_rows = load_jsonl(SEED_SET)
    golden_spec = json.loads(GOLDEN.read_text(encoding="utf-8"))

    assert_no_local_paths(QUESTION_SET.name, question_rows)
    assert_no_local_paths(REWRITE_SET.name, rewrite_rows)
    assert_no_local_paths(SEED_SET.name, seed_rows)
    assert_no_local_paths(GOLDEN.name, golden_spec)

    validate_question_routes(question_rows)
    validate_rewrite_routes(rewrite_rows)
    validate_question_seeds(seed_rows)
    validate_golden_assertions(golden_spec)

    route_counts = Counter(r["expected_route"] for r in question_rows)
    seed_counts = Counter(r["status"] for r in seed_rows)
    print("[OK] W2 question routing set: 30 rows")
    print("[OK] W2 rewrite routing set: 20 rows")
    print("[OK] route coverage:", dict(sorted(route_counts.items())))
    print("[OK] QuestionCard seed counts:", dict(sorted(seed_counts.items())))
    print("[OK] golden fact assertions:", len(golden_spec["assertions"]))
    print("[NOTE] known seed debt assignment gaps:", sorted(KNOWN_SEED_DEBT_ASSIGNMENT_GAPS))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        raise SystemExit(1)
