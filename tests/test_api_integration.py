import json

from fastapi.testclient import TestClient

from answer_engine import BASE_DB, EPISODE_INDEX
from api.app import create_app
from contracts.v8_copilot_api_contract_v0.models import (
    ClaimBacking,
    ResearchRequest,
    ValidatedClaim,
)
from lens_binding import RELEASE_LIBRARY
from service.orchestrator import ResearchOrchestrator


def request_payload(question: str, *, llm_mode: str = "disabled") -> dict:
    return {
        "contract_version": "v8_copilot_api_contract_v0",
        "request_id": "test-request-001",
        "question": question,
        "object": None,
        "context": None,
        "llm_mode": llm_mode,
    }


def ndjson_events(response) -> list[dict]:
    assert response.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in response.text.splitlines() if line]


def test_health_and_route_endpoints() -> None:
    client = TestClient(create_app())

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "contract_version": "v8_copilot_api_contract_v0",
        "read_only": True,
        "llm_available": False,
        "sources": {
            "research_db": True,
            "episode_index": True,
            "release_library": True,
        },
    }

    route = client.post(
        "/api/v1/route",
        json=request_payload("重整投资人招募后，下一个公告节点平均多久？"),
    )
    assert route.status_code == 200
    assert route.json()["route"] == "answer_query"
    assert route.json()["matched_rules"] == ["restructuring_next_node_query"]


def test_known_question_executes_real_answer_card() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/answers",
        json=request_payload("重整投资人招募后，下一个公告节点平均多久？"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "complete"
    assert payload["fallback"] is None
    assert payload["answer_card"]["contract_version"] == "v8_answer_contract_v0"
    assert [row["中位(天)"] for row in payload["answer_card"]["body_rows"]] == [4, 10, 14]


def test_unknown_question_returns_stable_lens_gap_without_facts() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/answers",
        json=request_payload("请分析一个当前规则尚未定义的新型风险模式。"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"]["route"] == "lens_gap"
    assert payload["answer_card"] is None
    assert payload["fallback"]["kind"] == "lens_gap"
    assert payload["claims"] == []


def test_boundary_request_is_rewritten_without_echoing_forbidden_terms() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/answers",
        json=request_payload("603398能买吗，目标价多少？"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"]["route"] == "refuse_or_rewrite"
    assert payload["fallback"]["kind"] == "refuse"
    public_guidance = json.dumps(
        {"note": payload["route"]["note"], "fallback": payload["fallback"]},
        ensure_ascii=False,
    )
    assert "目标价" not in public_guidance
    assert "仓位" not in public_guidance


def test_missing_llm_degrades_but_keeps_deterministic_card() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/answers",
        json=request_payload(
            "重整投资人招募后，下一个公告节点平均多久？",
            llm_mode="auto",
        ),
    )

    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["answer_card"] is not None
    assert payload["claims"] == []
    assert payload["degradations"] == [{
        "code": "llm_unavailable",
        "message": "LLM 叙述层不可用，已返回确定性 AnswerCard。",
    }]


def test_ndjson_event_order_and_allowed_names() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/answers/stream",
        json=request_payload(
            "重整投资人招募后，下一个公告节点平均多久？",
            llm_mode="auto",
        ),
    )
    events = ndjson_events(response)
    names = [event["event"] for event in events]

    assert names == [
        "accepted", "interpreted", "routed", "answer_card", "degraded", "completed"
    ]
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert set(names) <= {
        "accepted", "interpreted", "routed", "answer_card", "claim_block",
        "degraded", "completed", "error",
    }
    assert events[-1]["payload"]["response"]["status"] == "degraded"


def test_dossier_603398_uses_real_read_only_data_and_display_labels() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/stocks/603398/dossier")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "603398"
    assert payload["as_of"] == "2026-06-26"
    assert len(payload["price_series"]) == 1982
    assert len(payload["event_nodes"]) >= 150
    assert payload["lens_invocations"]
    assert any(node["episode_label"] == "重整路径" for node in payload["event_nodes"])
    assert any(
        node["source_material_label"].startswith("公告编号 ")
        for node in payload["event_nodes"]
    )
    display_blob = json.dumps({
        "nodes": [
            {
                "lane_label": node["lane_label"],
                "episode_label": node["episode_label"],
                "subtype_label": node["subtype_label"],
                "source_material_label": node["source_material_label"],
            }
            for node in payload["event_nodes"]
        ],
        "lenses": payload["lens_invocations"],
    }, ensure_ascii=False)
    for raw_value in (
        "aggregate_weak",
        "C17:stock_price_behavior_episode",
        "restructuring_path",
        "investor_or_control_change",
        "announcement:",
    ):
        assert raw_value not in display_blob


def test_api_calls_do_not_modify_research_sources() -> None:
    sources = [BASE_DB, EPISODE_INDEX, RELEASE_LIBRARY]
    before = {source: source.stat().st_mtime_ns for source in sources}
    client = TestClient(create_app())

    assert client.post(
        "/api/v1/answers",
        json=request_payload("沐邦平台整理期该看哪些窗口？"),
    ).status_code == 200
    assert client.get("/api/v1/stocks/603398/dossier").status_code == 200

    after = {source: source.stat().st_mtime_ns for source in sources}
    assert after == before


class InvalidClaimProvider:
    available = True

    def compose(self, *, request, answer_card, backing_catalog):
        return [ValidatedClaim(
            claim_id="claim-invalid",
            text="这条说明没有对应依据。",
            claim_type="inference",
            backing=ClaimBacking(kind="query_row", ref="missing-row"),
        )]


def test_unbacked_injected_claim_is_rejected_before_response() -> None:
    orchestrator = ResearchOrchestrator(claim_provider=InvalidClaimProvider())
    response = orchestrator.answer(ResearchRequest.model_validate(request_payload(
        "重整投资人招募后，下一个公告节点平均多久？",
        llm_mode="auto",
    )))

    assert response.answer_card is not None
    assert response.claims == []
    assert response.status == "degraded"
    assert response.degradations[0].code == "llm_output_rejected"
