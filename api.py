"""Local-only FastAPI surface for ST Research Copilot v8."""
from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path as FilePath
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from api_contract import (
    API_CONTRACT_VERSION,
    ResearchRequest,
    RouteDecision,
    StockDossierPayload,
)
from api_contract_v1 import (
    API_CONTRACT_VERSION_V1,
    ResearchResponseV1,
    ResearchStreamEventV1,
)
from answer_engine import CONTRACT_VERSION as ANSWER_CONTRACT_VERSION
from dossier_service import DossierNotFoundError, build_stock_dossier
from llm_adapter import openai_configured, orchestrate_optional_llm
from orchestrator import route_only
from orchestrator_v1 import enrich_response_v1, stream_events_v1


logger = logging.getLogger(__name__)


class SPAStaticFiles(StaticFiles):
    """Serve index.html for client routes while preserving real 404s."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            leaf = path.rsplit("/", 1)[-1]
            if (
                exc.status_code != 404
                or path.startswith("api/")
                or "." in leaf
            ):
                raise
            return await super().get_response("index.html", scope)


def orchestrate(request: ResearchRequest) -> ResearchResponseV1:
    """Patchable API boundary used by JSON and NDJSON endpoints."""
    return enrich_response_v1(request, orchestrate_optional_llm(request))

app = FastAPI(
    title="ST Research Copilot API",
    version="0.1.0",
    description="Local-only, evidence-grounded ST research API.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/v1/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "api_contract_version": API_CONTRACT_VERSION_V1,
        "request_contract_version": API_CONTRACT_VERSION,
        "response_contract_version": API_CONTRACT_VERSION_V1,
        "answer_contract_version": ANSWER_CONTRACT_VERSION,
        "llm_available": openai_configured(),
        "database_mode": "read_only",
    }


@app.post("/api/v1/route", response_model=RouteDecision)
def route(request: ResearchRequest) -> RouteDecision:
    return route_only(request)


@app.post("/api/v1/answers", response_model=ResearchResponseV1)
def answers(request: ResearchRequest) -> ResearchResponseV1:
    try:
        return orchestrate(request)
    except (FileNotFoundError, ValueError) as exc:
        logger.exception("deterministic answer execution failed")
        raise HTTPException(
            status_code=500,
            detail={"code": "deterministic_execution_failed", "message": "研究内核执行失败。"},
        ) from exc


def _ndjson_stream(request: ResearchRequest) -> Iterator[str]:
    request_with_id = request
    if request.request_id is None:
        request_with_id = request.model_copy(update={"request_id": f"req-{uuid4().hex}"})
    try:
        response = orchestrate(request_with_id)
        for event in stream_events_v1(request_with_id, response):
            yield event.model_dump_json() + "\n"
    except Exception:
        logger.exception("deterministic answer stream failed")
        event = ResearchStreamEventV1(
            request_id=request_with_id.request_id or "req-error",
            sequence=1,
            event="error",
            payload={"code": "stream_failed", "message": "研究内核执行失败。"},
        )
        yield event.model_dump_json() + "\n"


@app.post("/api/v1/answers/stream")
def answer_stream(request: ResearchRequest) -> StreamingResponse:
    return StreamingResponse(
        _ndjson_stream(request),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@app.get("/api/v1/stocks/{symbol}/dossier", response_model=StockDossierPayload)
def stock_dossier(
    symbol: str = Path(pattern=r"^[0-9]{6}$"),
    announcement_focus: str | None = Query(default=None, max_length=256),
) -> StockDossierPayload:
    try:
        return build_stock_dossier(symbol, announcement_focus=announcement_focus)
    except DossierNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "dossier_not_found", "message": "当前快照没有该股票的个股材料。"},
        ) from exc
    except ValueError as exc:
        logger.exception("dossier data validation failed")
        raise HTTPException(
            status_code=500,
            detail={"code": "dossier_invalid", "message": "个股材料校验失败。"},
        ) from exc


_WEB_DIST = FilePath(__file__).resolve().parent / "web/dist"
if _WEB_DIST.exists():
    app.mount("/", SPAStaticFiles(directory=_WEB_DIST, html=True), name="web")
