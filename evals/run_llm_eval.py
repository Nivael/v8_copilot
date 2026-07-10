from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.rewrite_routing_set_v0 import REWRITE_SET
from evals.validate_w2_evals import QUESTION_SET, load_jsonl
from llm.boundaries import LLM_FORBIDDEN_WORDING
from llm.composer import NarrativeComposer
from llm.parser import QuestionParser
from llm.providers import FakeLLMProvider
from llm.schemas import NarrativeDraft, ParsedQuestion
from run_seeds import seed_builders


def _parser_factory(response_model: type, payload: dict) -> dict:
    if response_model is not ParsedQuestion:
        raise ValueError(f"unexpected response model: {response_model}")
    symbol = payload["research_context"].get("symbol")
    return {
        "normalized_question": payload["question"],
        "object_kind": "stock" if symbol else "unknown",
        "object_ref": symbol or "unknown",
        "intent": "research_question",
        "time_range": {"start": "", "end": ""},
        "dimensions": [],
        "ambiguities": [],
        "candidate_topics": [],
        "proposed_route": "lens_gap",
        "compliant_rewrite": "",
    }


def _context(symbol: str | None) -> dict:
    return {
        "symbol": symbol,
        "date_range": None,
        "selected_event": None,
        "selected_episode": None,
        "selected_lenses": [],
        "active_question": None,
        "answer_card_id": None,
    }


def _composer_factory(response_model: type, payload: dict) -> dict:
    if response_model is not NarrativeDraft:
        raise ValueError(f"unexpected response model: {response_model}")
    catalog = payload["backing_catalog"]
    if not catalog:
        return {"claims": []}
    backing = catalog[0]
    return {
        "claims": [{
            "text": "该分析块严格引用当前答案卡中的可核查依据。",
            "claim_type": "fact",
            "backing": {"kind": backing["kind"], "ref": backing["ref"]},
        }]
    }


def main() -> int:
    parser = QuestionParser(
        FakeLLMProvider(response_factory=_parser_factory), model="fake"
    )
    failures: list[dict[str, str]] = []
    for row in load_jsonl(QUESTION_SET):
        obj = row["object"]
        symbol = obj["ref"] if obj["kind"] == "stock" else None
        result = parser.parse(
            row["user_question"],
            _context(symbol),
            authoritative_object=obj,
        )
        actual = result.adjudicated_route.predicted_route
        if actual != row["expected_route"]:
            failures.append({
                "question_id": row["question_id"],
                "expected": row["expected_route"],
                "actual": actual,
            })

    rewrite_failures: list[str] = []
    for row in load_jsonl(REWRITE_SET):
        result = parser.parse(
            row["user_question"],
            _context(row["object"]["ref"] if row["object"]["kind"] == "stock" else None),
            authoritative_object=row["object"],
        )
        if result.adjudicated_route.predicted_route != row["expected_route"]:
            rewrite_failures.append(row["rewrite_id"])
        if not result.compliant_rewrite or any(
            term in result.compliant_rewrite for term in LLM_FORBIDDEN_WORDING
        ):
            rewrite_failures.append(f"{row['rewrite_id']}:unsafe_rewrite")

    card_failures: list[str] = []
    card_count = 0
    for name, builder in seed_builders():
        card_count += 1
        card = builder()
        result = NarrativeComposer(
            FakeLLMProvider(response_factory=_composer_factory), model="fake"
        ).compose(card)
        try:
            result.public_payload()
        except ValueError:
            card_failures.append(name)
        if result.rejected_claims:
            card_failures.append(f"{name}:rejected_claim")

    if failures or rewrite_failures or card_failures:
        print(json.dumps({
            "route_failures": failures,
            "rewrite_failures": rewrite_failures,
            "card_failures": card_failures,
        }, ensure_ascii=False, indent=2))
        return 1

    print("[OK] LLM parser proposals were adjudicated correctly for 30/30 questions")
    print("[OK] trading requests were routed and safely rewritten for 20/20 questions")
    print(f"[OK] composer backing gate passed for {card_count}/7 seed AnswerCards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
