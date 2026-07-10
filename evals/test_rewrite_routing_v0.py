from __future__ import annotations

from evals.deterministic_router_v0 import route_question
from evals.rewrite_routing_set_v0 import REWRITE_SET
from evals.validate_w2_evals import QUESTION_SET, load_jsonl
from llm.boundaries import LLM_FORBIDDEN_WORDING
from llm.parser import QuestionParser
from llm.providers import FakeLLMProvider
from llm.schemas import ParsedQuestion


def _factory(response_model: type, payload: dict) -> dict:
    assert response_model is ParsedQuestion
    return {
        "normalized_question": payload["question"],
        "object_kind": "unknown",
        "object_ref": "unknown",
        "intent": "trading_request_boundary",
        "time_range": {"start": "", "end": ""},
        "dimensions": [],
        "ambiguities": [],
        "candidate_topics": [],
        "proposed_route": "answer_query",
        "compliant_rewrite": "",
    }


def test_20_rewrite_questions_route_to_boundary_and_get_safe_fallback() -> None:
    rows = load_jsonl(REWRITE_SET)
    parser = QuestionParser(FakeLLMProvider(response_factory=_factory), model="fake")
    failures = []
    for row in rows:
        result = parser.parse(
            row["user_question"],
            {},
            authoritative_object=row["object"],
        )
        rewrite_route = route_question({
            "user_question": result.compliant_rewrite,
            "object": row["object"],
        })
        if result.adjudicated_route.predicted_route != row["expected_route"]:
            failures.append(row["rewrite_id"])
        assert result.compliant_rewrite
        assert rewrite_route.predicted_route != "refuse_or_rewrite"
        assert not any(term in result.compliant_rewrite for term in LLM_FORBIDDEN_WORDING)

    assert len(rows) == 20
    assert failures == []


def test_combined_routing_acceptance_set_is_50_questions() -> None:
    routing_rows = load_jsonl(QUESTION_SET)
    rewrite_rows = load_jsonl(REWRITE_SET)

    assert len(routing_rows) == 30
    assert len(rewrite_rows) == 20
    assert len(routing_rows) + len(rewrite_rows) == 50
