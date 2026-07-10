from __future__ import annotations

from api_contract import ResearchRequest
from llm.providers import FakeLLMProvider
from llm.schemas import NarrativeDraft, ParsedQuestion
from llm_adapter import orchestrate_with_provider


def request(question: str = "重整投资人公开招募后，下一个公告节点通常多久？") -> ResearchRequest:
    return ResearchRequest(
        question=question,
        object={"kind": "episode_type", "ref": "restructuring_investor_recruitment"},
        llm_mode="auto",
    )


def valid_factory(response_model: type, payload: dict) -> dict:
    if response_model is ParsedQuestion:
        return {
            "normalized_question": payload["question"],
            "object_kind": "episode_type",
            "object_ref": "restructuring_investor_recruitment",
            "intent": "event_timing",
            "time_range": {"start": "", "end": ""},
            "dimensions": ["announcement"],
            "ambiguities": [],
            "candidate_topics": ["restructuring"],
            "proposed_route": "answer_query",
            "compliant_rewrite": "",
        }
    if response_model is NarrativeDraft:
        first = payload["backing_catalog"][0]
        return {"claims": [{
            "text": "该行保留了历史等待期的样本和分布口径。",
            "claim_type": "fact",
            "backing": {"kind": first["kind"], "ref": first["ref"]},
        }]}
    raise AssertionError(response_model)


def test_fake_provider_runs_full_validated_path() -> None:
    response = orchestrate_with_provider(
        request(),
        FakeLLMProvider(response_factory=valid_factory),
    )

    assert response.route.route == "answer_query"
    assert response.answer_card is not None
    assert response.llm_used is True
    assert response.degraded is False
    assert any("历史等待期" in claim.text for claim in response.claims)


def test_llm_route_proposal_cannot_override_w1_router() -> None:
    def disagreeing_factory(response_model: type, payload: dict) -> dict:
        result = valid_factory(response_model, payload)
        if response_model is ParsedQuestion:
            result["proposed_route"] = "answer_evidence"
        return result

    response = orchestrate_with_provider(
        request(),
        FakeLLMProvider(response_factory=disagreeing_factory),
    )

    assert response.route.route == "answer_query"


def test_provider_failure_preserves_deterministic_answer() -> None:
    response = orchestrate_with_provider(request(), FakeLLMProvider())

    assert response.route.route == "answer_query"
    assert response.answer_card is not None
    assert response.llm_used is False
    assert response.degraded is True
    assert response.degraded_reasons == [
        "LLM 问题解释不可用，已使用确定性路由。",
        "LLM 分析叙述不可用，已保留确定性证据菜单。",
    ]


def test_boundary_request_exposes_safe_rewrite_candidate() -> None:
    response = orchestrate_with_provider(
        ResearchRequest(
            question="这票目标价看到多少？",
            object={"kind": "stock", "ref": "603398"},
            llm_mode="auto",
        ),
        FakeLLMProvider(),
    )

    assert response.route.route == "refuse_or_rewrite"
    assert any(
        candidate.reason.startswith("合规改写：603398 当前有哪些公开事件节点")
        for candidate in response.sedimentation_candidates
    )
