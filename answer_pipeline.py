"""One validated answer pipeline for HTTP and local EvidencePack consumers."""
from __future__ import annotations

from api_contract import ResearchRequest
from api_contract_v2 import ResearchResponseV2
from llm_adapter import orchestrate_optional_llm_result
from orchestrator_v1 import enrich_response_v1
from orchestrator_v2 import enrich_response_v2


def answer(request: ResearchRequest) -> ResearchResponseV2:
    result = orchestrate_optional_llm_result(request)
    response = enrich_response_v1(request, result.response)
    return enrich_response_v2(request, response, narrative_override=result.narrative)


def answer_deterministic(request: ResearchRequest) -> ResearchResponseV2:
    return answer(request.model_copy(update={"llm_mode": "off"}))
