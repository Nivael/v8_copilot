from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from api_contract import (  # noqa: E402
    API_CONTRACT_VERSION,
    DateRange,
    DossierDataGap,
    GapDescriptor,
    PricePoint,
    QuestionInterpretation,
    ResearchContext,
    ResearchObject,
    ResearchRequest,
    ResearchResponse,
    ResearchStreamEvent,
    RouteDecision,
    SedimentationCandidate,
    StockDossierPayload,
    public_contract_schema,
)


HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"


def _dump(path: Path, value: object) -> None:
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")  # type: ignore[attr-defined]
    else:
        payload = value
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_fixtures() -> dict[str, object]:
    request = ResearchRequest(
        request_id="req-fixture-001",
        question="那它呢？",
        object=ResearchObject(kind="unknown", ref="pronoun"),
        context=ResearchContext(),
        llm_mode="off",
    )
    interpretation = QuestionInterpretation(
        object=ResearchObject(kind="unknown", ref="pronoun"),
        intent="clarify_object",
        time_range=DateRange(),
        ambiguities=["缺少可绑定的股票或事件对象"],
        candidate_topics=[],
    )
    route = RouteDecision(
        route="clarify",
        status="clarify",
        view="clarify",
        reason="缺少可绑定的 stock/event/context，先澄清。",
        matched_rules=["missing_object_or_context"],
        required_lens_behavior="not_applicable",
    )
    response = ResearchResponse(
        request_id="req-fixture-001",
        interpretation=interpretation,
        route=route,
        gaps=[GapDescriptor(
            kind="execution_gap",
            gap_id="missing_object_or_context",
            description="需要补充股票或事件对象后再执行研究查询。",
        )],
        sedimentation_candidates=[SedimentationCandidate(
            kind="question_card",
            reason="等待用户补充研究对象，不自动持久化。",
        )],
        degraded=True,
        degraded_reasons=["问题对象不明确"],
    )
    dossier = StockDossierPayload(
        symbol="603398",
        display_name="*ST沐邦",
        as_of=date(2026, 6, 26),
        price_series=[PricePoint(date=date(2026, 6, 26), close=13.42)],
        data_gaps=[DossierDataGap(
            gap_id="shareholder_count_full_coverage",
            display_label="股东人数全量覆盖尚未完成",
            debt_ref="D-021",
        )],
        display_labels={"price_adjustment": "前复权"},
        research_context=ResearchContext(symbol="603398"),
        provenance=["shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3::daily_prices"],
    )
    emitted_at = datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc)
    events = [
        ResearchStreamEvent(
            request_id="req-fixture-001",
            sequence=1,
            event="accepted",
            emitted_at=emitted_at,
            payload={"llm_mode": "off"},
        ),
        ResearchStreamEvent(
            request_id="req-fixture-001",
            sequence=2,
            event="interpreted",
            emitted_at=emitted_at,
            payload=interpretation.model_dump(mode="json"),
        ),
        ResearchStreamEvent(
            request_id="req-fixture-001",
            sequence=3,
            event="routed",
            emitted_at=emitted_at,
            payload=route.model_dump(mode="json"),
        ),
        ResearchStreamEvent(
            request_id="req-fixture-001",
            sequence=4,
            event="completed",
            emitted_at=emitted_at,
            payload={"degraded": True},
        ),
    ]
    return {
        "research_request.json": request,
        "question_interpretation.json": interpretation,
        "route_decision.json": route,
        "research_response.json": response,
        "stock_dossier_payload.json": dossier,
        "research_stream_events.ndjson": events,
    }


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    _dump(HERE / "schema.json", public_contract_schema())
    fixtures = build_fixtures()
    for name, value in fixtures.items():
        path = FIXTURES / name
        if name.endswith(".ndjson"):
            rows = [item.model_dump(mode="json") for item in value]  # type: ignore[union-attr]
            path.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                encoding="utf-8",
            )
        else:
            _dump(path, value)
    _dump(HERE / "manifest.json", {
        "contract_version": API_CONTRACT_VERSION,
        "schema": "schema.json",
        "fixtures": sorted(fixtures),
    })
    print(f"wrote {HERE / 'schema.json'} and {len(fixtures)} fixtures")


if __name__ == "__main__":
    main()
