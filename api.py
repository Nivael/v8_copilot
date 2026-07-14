"""Local-only FastAPI surface for ST Research Copilot v8."""
from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path as FilePath
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Path, Query, status
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
from api_contract_v2 import (
    API_CONTRACT_VERSION_V2,
    ResearchResponseV2,
    ResearchStreamEventV2,
)
from answer_engine import CONTRACT_VERSION as ANSWER_CONTRACT_VERSION
from dossier_service import DossierNotFoundError, build_stock_dossier
from evidence_gateway import (
    DraftValidationRequest,
    EvidencePack,
    ValidationReport,
    build_evidence_pack,
    validate_research_draft,
)
from experience_contract import (
    ExperienceCandidateInput,
    ExperienceFeedbackRequest,
    ExperienceRecord,
    ExperienceReviewRequest,
    ExperienceStatus,
)
from experience_distiller import distill_feedback
from llm_adapter import (
    openai_configured,
    orchestrate_optional_llm,
    orchestrate_optional_llm_result,
)
from orchestrator import route_only
from orchestrator_v1 import enrich_response_v1
from orchestrator_v2 import enrich_response_v2, stream_events_v2
from research_repository import (
    ExperienceRepository,
    ResearchRunCreate,
    ResearchRunLedger,
    ResearchRunRecord,
)
from settings import EXPERIENCE_REPOSITORY_DB, RESEARCH_RUN_LEDGER_DB


logger = logging.getLogger(__name__)
experience_repository = ExperienceRepository(EXPERIENCE_REPOSITORY_DB)
research_run_ledger = ResearchRunLedger(RESEARCH_RUN_LEDGER_DB)


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


def orchestrate(request: ResearchRequest) -> ResearchResponseV2:
    """Patchable API boundary used by JSON and NDJSON endpoints."""
    llm_result = orchestrate_optional_llm_result(request)
    response_v1 = enrich_response_v1(request, llm_result.response)
    return enrich_response_v2(
        request, response_v1, narrative_override=llm_result.narrative
    )


def orchestrate_deterministic(request: ResearchRequest) -> ResearchResponseV2:
    """Return the validated local answer without waiting for an LLM provider."""
    local_request = request.model_copy(update={"llm_mode": "off"})
    response_v1 = enrich_response_v1(
        local_request,
        orchestrate_optional_llm(local_request),
    )
    return enrich_response_v2(local_request, response_v1)

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
        "api_contract_version": API_CONTRACT_VERSION_V2,
        "request_contract_version": API_CONTRACT_VERSION,
        "response_contract_version": API_CONTRACT_VERSION_V2,
        "answer_contract_version": ANSWER_CONTRACT_VERSION,
        "llm_available": openai_configured(),
        "database_mode": "read_only",
    }


@app.post("/api/v1/route", response_model=RouteDecision)
def route(request: ResearchRequest) -> RouteDecision:
    return route_only(request)


@app.post("/api/v1/answers", response_model=ResearchResponseV2)
def answers(request: ResearchRequest) -> ResearchResponseV2:
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
        deterministic = orchestrate_deterministic(request_with_id)
        deterministic_events = stream_events_v2(request_with_id, deterministic)
        sequence = 0

        def emit(event: ResearchStreamEventV2) -> str:
            nonlocal sequence
            sequence += 1
            return event.model_copy(update={"sequence": sequence}).model_dump_json() + "\n"

        if request_with_id.llm_mode == "off" or deterministic.answer_card is None:
            for event in deterministic_events:
                if event.event == "answer_card":
                    event = event.model_copy(update={"payload": {
                        "answer_card": deterministic.answer_card,
                        "response": deterministic.model_dump(mode="json"),
                    }})
                yield emit(event)
            return

        for event in deterministic_events:
            if event.event not in {"accepted", "interpreted", "routed", "answer_card"}:
                continue
            if event.event == "answer_card":
                event = event.model_copy(update={"payload": {
                    "answer_card": deterministic.answer_card,
                    "response": deterministic.model_dump(mode="json"),
                }})
            yield emit(event)

        try:
            enriched = orchestrate(request_with_id)
        except Exception:
            logger.exception("LLM enrichment failed after deterministic answer")
            enriched = deterministic.model_copy(update={
                "degraded": True,
                "degraded_reasons": [
                    *deterministic.degraded_reasons,
                    "LLM 分析叙述不可用，已保留确定性证据菜单。",
                ],
            })
        for event in stream_events_v2(request_with_id, enriched):
            if event.event in {"claim_block", "degraded", "completed"}:
                yield emit(event)
    except Exception:
        logger.exception("deterministic answer stream failed")
        event = ResearchStreamEventV2(
            request_id=request_with_id.request_id or "req-error",
            sequence=locals().get("sequence", 0) + 1,
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


@app.post("/api/v1/research/evidence", response_model=EvidencePack)
def research_evidence(request: ResearchRequest) -> EvidencePack:
    """Build a self-contained EvidencePack without network or research DB writes."""
    try:
        return build_evidence_pack(
            request.model_copy(update={"llm_mode": "off"}),
            experience_repository=experience_repository,
        )
    except (FileNotFoundError, ValueError) as exc:
        logger.exception("evidence gateway execution failed")
        raise HTTPException(
            status_code=500,
            detail={"code": "evidence_gateway_failed", "message": "只读证据网关执行失败。"},
        ) from exc


@app.post("/api/v1/research/validate", response_model=ValidationReport)
def research_validate(request: DraftValidationRequest) -> ValidationReport:
    return validate_research_draft(request.evidence_pack, request.draft)


@app.post(
    "/api/v1/research/runs",
    response_model=ResearchRunRecord,
    status_code=status.HTTP_201_CREATED,
)
def record_research_run(request: ResearchRunCreate) -> ResearchRunRecord:
    return research_run_ledger.record(request)


@app.get("/api/v1/research/runs", response_model=list[ResearchRunRecord])
def list_research_runs(limit: int = Query(default=50, ge=1, le=200)) -> list[ResearchRunRecord]:
    return research_run_ledger.list(limit=limit)


@app.post("/api/v1/research/runs/{run_id}/feedback")
def add_research_feedback(
    request: ExperienceFeedbackRequest,
    run_id: str = Path(pattern=r"^RUN-[A-F0-9]{24}$"),
) -> dict[str, object]:
    try:
        feedback_id = research_run_ledger.add_feedback(
            run_id,
            category=request.category,
            feedback_text=request.feedback_text,
            submitted_by=request.submitted_by,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="research run 不存在") from exc
    candidate_input = distill_feedback(run_id, request)
    candidate = None
    if candidate_input is not None:
        candidate = experience_repository.propose(candidate_input)
        research_run_ledger.link_experience(run_id, candidate.experience_id, "candidate_source")
    return {
        "feedback_id": feedback_id,
        "experience_candidate": candidate.model_dump(mode="json") if candidate else None,
    }


@app.post(
    "/api/v1/experiences/candidates",
    response_model=ExperienceRecord,
    status_code=status.HTTP_201_CREATED,
)
def propose_experience(request: ExperienceCandidateInput) -> ExperienceRecord:
    """Codex and deterministic distillers may only create candidate records."""
    return experience_repository.propose(request)


@app.get("/api/v1/experiences", response_model=list[ExperienceRecord])
def list_experiences(
    experience_status: ExperienceStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=300),
) -> list[ExperienceRecord]:
    return experience_repository.list(status=experience_status, limit=limit)


@app.get("/api/v1/experiences/{experience_id}", response_model=ExperienceRecord)
def get_experience(
    experience_id: str = Path(pattern=r"^EXP-[A-F0-9]{20}$"),
) -> ExperienceRecord:
    try:
        return experience_repository.get(experience_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="experience 不存在") from exc


@app.post("/api/v1/experiences/{experience_id}/review", response_model=ExperienceRecord)
def review_experience(
    request: ExperienceReviewRequest,
    experience_id: str = Path(pattern=r"^EXP-[A-F0-9]{20}$"),
) -> ExperienceRecord:
    try:
        return experience_repository.review(experience_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="experience 不存在") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


_WEB_DIST = FilePath(__file__).resolve().parent / "web/dist"
if _WEB_DIST.exists():
    app.mount("/", SPAStaticFiles(directory=_WEB_DIST, html=True), name="web")
