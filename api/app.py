from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from answer_engine import BASE_DB, EPISODE_INDEX
from contracts.v8_copilot_api_contract_v0.models import (
    ResearchRequest,
    ResearchResponse,
    RouteDecision,
    StockDossierPayload,
)
from lens_binding import RELEASE_LIBRARY
from service.dossier import DossierNotFound, load_stock_dossier
from service.orchestrator import ResearchOrchestrator


def _configured_orchestrator() -> ResearchOrchestrator:
    if not (os.getenv("OPENAI_API_KEY") and os.getenv("V8_OPENAI_MODEL")):
        return ResearchOrchestrator()
    try:
        from llm.integration import OpenAIInterpretationProvider, OpenAINarrativeProvider
        from llm.providers import OpenAIResponsesProvider

        provider = OpenAIResponsesProvider()
        return ResearchOrchestrator(
            claim_provider=OpenAINarrativeProvider(provider),
            interpretation_provider=OpenAIInterpretationProvider(provider),
        )
    except Exception:
        return ResearchOrchestrator()


def create_app(orchestrator: ResearchOrchestrator | None = None) -> FastAPI:
    application = FastAPI(
        title="ST Research Copilot",
        version="0.2.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    research = orchestrator or _configured_orchestrator()

    @application.get("/api/v1/health")
    def health() -> dict:
        return {
            "status": "ok",
            "contract_version": "v8_copilot_api_contract_v0",
            "read_only": True,
            "llm_available": bool(research.claim_provider and research.claim_provider.available),
            "sources": {
                "research_db": BASE_DB.exists(),
                "episode_index": EPISODE_INDEX.exists(),
                "release_library": RELEASE_LIBRARY.exists(),
            },
        }

    @application.post("/api/v1/route", response_model=RouteDecision)
    def route(request: ResearchRequest) -> RouteDecision:
        return research.route(request).route

    @application.post("/api/v1/answers", response_model=ResearchResponse)
    def answer(request: ResearchRequest) -> ResearchResponse:
        return research.answer(request)

    @application.post("/api/v1/answers/stream")
    def answer_stream(request: ResearchRequest) -> StreamingResponse:
        def lines():
            for event in research.events(request):
                yield json.dumps(event.model_dump(mode="json"), ensure_ascii=False) + "\n"

        return StreamingResponse(lines(), media_type="application/x-ndjson")

    @application.get("/api/v1/stocks/{symbol}/dossier", response_model=StockDossierPayload)
    def dossier(symbol: str) -> StockDossierPayload:
        try:
            return load_stock_dossier(symbol)
        except DossierNotFound as exc:
            status = 422 if "invalid symbol" in str(exc) else 404
            raise HTTPException(status_code=status, detail=str(exc)) from exc

    web_dist = Path(__file__).resolve().parents[1] / "web/dist"
    if web_dist.exists():
        application.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
    return application


app = create_app()
