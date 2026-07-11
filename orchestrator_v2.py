"""API v2 enrichment for readable narratives and explicit boundary rewrites."""
from __future__ import annotations

from api_contract import ResearchRequest
from api_contract_v1 import ResearchResponseV1
from api_contract_v2 import ResearchResponseV2, ResearchStreamEventV2
from narrative_builder import build_boundary_rewrite, build_narrative


def enrich_response_v2(
    request: ResearchRequest,
    response: ResearchResponseV1,
) -> ResearchResponseV2:
    return ResearchResponseV2(
        request_id=response.request_id,
        interpretation=response.interpretation,
        route=response.route,
        answer_card=response.answer_card,
        claims=response.claims,
        narrative=build_narrative(response),
        boundary_rewrite=build_boundary_rewrite(request, response),
        gaps=response.gaps,
        sedimentation_candidates=response.sedimentation_candidates,
        question_cards=response.question_cards,
        data_debt_candidates=response.data_debt_candidates,
        navigation_refs=response.navigation_refs,
        query_template_id=response.query_template_id,
        degraded=response.degraded,
        degraded_reasons=response.degraded_reasons,
        llm_used=response.llm_used,
    )


def stream_events_v2(
    request: ResearchRequest,
    response: ResearchResponseV2,
) -> list[ResearchStreamEventV2]:
    events: list[ResearchStreamEventV2] = []

    def append(event: str, payload: dict) -> None:
        events.append(ResearchStreamEventV2(
            request_id=response.request_id,
            sequence=len(events) + 1,
            event=event,  # type: ignore[arg-type]
            payload=payload,
        ))

    append("accepted", {"llm_mode": request.llm_mode})
    append("interpreted", response.interpretation.model_dump(mode="json"))
    append("routed", {
        **response.route.model_dump(mode="json"),
        "query_template_id": response.query_template_id,
    })
    if response.answer_card is not None:
        append("answer_card", response.answer_card)
    if response.claims:
        append("claim_block", {
            "claims": [claim.model_dump(mode="json") for claim in response.claims],
            "narrative": response.narrative.model_dump(mode="json") if response.narrative else None,
        })
    if response.degraded:
        append("degraded", {"reasons": response.degraded_reasons})
    append("completed", {
        "route": response.route.route,
        "has_answer_card": response.answer_card is not None,
        "claim_count": len(response.claims),
        "response": response.model_dump(mode="json"),
    })
    return events
