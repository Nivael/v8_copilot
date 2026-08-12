import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path

import api as api_module
import dossier_service
import httpx
from api import SPAStaticFiles
from answer_engine import BASE_DB, EPISODE_INDEX
from fastapi import FastAPI
from jsonschema import Draft202012Validator
from lens_binding import RELEASE_LIBRARY
from research_repository import ExperienceRepository, ResearchRunLedger


def api_request(method: str, url: str, **kwargs) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=api_module.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, url, **kwargs)

    return asyncio.run(send())


def payload(question: str, *, kind: str = "stock", ref: str = "603398") -> dict:
    return {
        "request_id": "req-api-test",
        "question": question,
        "object": {"kind": kind, "ref": ref},
        "llm_mode": "off",
    }


def experience_candidate_payload() -> dict:
    return {
        "experience_type": "presentation_rule",
        "title": "主回答先给判断",
        "value_summary": "把精度下沉到依据与证据层。",
        "trigger_conditions": ["比较问题"],
        "scope": ["comparison"],
        "required_inputs": ["evidence_pack"],
        "query_plan": ["识别实质差异"],
        "definitions": ["主回答可独立读懂"],
        "answer_rubric": ["首段直接回答"],
        "anti_patterns": ["字段清单开头"],
        "coverage_boundaries": ["不改变证据等级"],
        "validation_refs": ["regression:readability"],
        "source_run_refs": ["migration:test"],
        "supersedes": [],
    }


def test_health_exposes_contracts_and_read_only_mode(monkeypatch) -> None:
    monkeypatch.setattr(api_module, "openai_configured", lambda: False)
    response = api_request("GET", "/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "api_contract_version": "v8_copilot_api_contract_v2",
        "request_contract_version": "v8_copilot_api_contract_v0",
        "response_contract_version": "v8_copilot_api_contract_v2",
        "answer_contract_version": "v8_answer_contract_v0",
        "llm_available": False,
        "database_mode": "read_only",
    }


def test_route_endpoint_returns_deterministic_decision() -> None:
    response = api_request(
        "POST",
        "/api/v1/route",
        json=payload("沐邦接下来可能的爆发点在哪里？"),
    )

    assert response.status_code == 200
    assert response.json()["route"] == "answer_checklist"
    assert response.json()["view"] == "checklist"


def test_answers_endpoint_returns_validated_answer_card() -> None:
    response = api_request(
        "POST",
        "/api/v1/answers",
        json=payload(
            "重整投资人公开招募后，下一个公告节点通常多久？",
            kind="episode_type",
            ref="restructuring_investor_recruitment",
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["contract_version"] == "v8_copilot_api_contract_v2"
    assert body["answer_card"]["contract_version"] == "v8_answer_contract_v0"
    assert [row["中位(天)"] for row in body["answer_card"]["body_rows"]] == [4, 10, 14]
    assert body["narrative"]["direct_answer"]["backing"]
    schema = json.loads((
        Path(__file__).resolve().parents[1]
        / "contracts/v8_answer_contract_v0/schema.json"
    ).read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(body["answer_card"])


def test_research_gateway_and_validator_round_trip() -> None:
    response = api_request(
        "POST",
        "/api/v1/research/evidence",
        json={"question": "沐邦和南都怎么比较？", "llm_mode": "off"},
    )

    assert response.status_code == 200
    pack = response.json()
    assert pack["pack_id"].startswith("EP-")
    assert pack["rows"]
    assert pack["not_evidence"] is False

    validated = api_request(
        "POST",
        "/api/v1/research/validate",
        json={
            "evidence_pack": pack,
            "draft": {"narrative": pack["deterministic_response"]["narrative"]},
        },
    )
    assert validated.status_code == 200
    assert validated.json()["valid"] is True


def test_experience_review_requires_human_and_filters_status(monkeypatch, tmp_path) -> None:
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    monkeypatch.setattr(api_module, "experience_repository", repository)
    created = api_request(
        "POST", "/api/v1/experiences/candidates", json=experience_candidate_payload()
    )

    assert created.status_code == 201
    experience_id = created.json()["experience_id"]
    rejected = api_request(
        "POST",
        f"/api/v1/experiences/{experience_id}/review",
        json={"action": "accept", "actor_type": "codex", "reviewed_by": "codex"},
    )
    assert rejected.status_code == 403

    accepted = api_request(
        "POST",
        f"/api/v1/experiences/{experience_id}/review",
        json={"action": "accept", "actor_type": "human", "reviewed_by": "owner"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    listed = api_request("GET", "/api/v1/experiences?status=accepted")
    assert [row["experience_id"] for row in listed.json()] == [experience_id]


def test_run_feedback_creates_generic_candidate_not_question_memory(monkeypatch, tmp_path) -> None:
    ledger = ResearchRunLedger(tmp_path / "runs.sqlite3")
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    monkeypatch.setattr(api_module, "research_run_ledger", ledger)
    monkeypatch.setattr(api_module, "experience_repository", repository)
    run = api_request("POST", "/api/v1/research/runs", json={
        "request_id": "req-api-run",
        "question_text": "两只股票怎么比较？",
        "normalized_intent": "stock_comparison",
        "object_refs": ["comparison"],
        "evidence_pack_ids": ["EP-AAAAAAAAAAAAAAAAAAAA"],
        "final_answer": "先给实质差异。",
        "validation_report": {"valid": True},
        "source_freshness": {"announcement": "2026-07-08"},
        "agent_surface": "codex_desktop",
    })
    assert run.status_code == 201

    feedback = api_request(
        "POST",
        f"/api/v1/research/runs/{run.json()['run_id']}/feedback",
        json={
            "feedback_text": "总览先说实质差异，不要从系统口径开始。",
            "category": "presentation",
            "submitted_by": "owner",
        },
    )
    candidate = feedback.json()["experience_candidate"]
    assert candidate["experience_type"] == "presentation_rule"
    assert candidate["not_evidence"] is True
    assert "两只股票怎么比较" not in candidate["value_summary"]

    replay = api_request(
        "POST", f"/api/v1/research/runs/{run.json()['run_id']}/feedback",
        json={
            "feedback_text": "总览先说实质差异，不要从系统口径开始。",
            "category": "presentation", "submitted_by": "owner",
        },
    )
    assert replay.json()["feedback_id"] == feedback.json()["feedback_id"]
    assert api_request("GET", f"/api/v1/research/runs/{run.json()['run_id']}").json()["feedback_count"] == 1


def test_batch_review_export_import_is_idempotent(monkeypatch, tmp_path) -> None:
    ledger = ResearchRunLedger(tmp_path / "runs.sqlite3")
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    monkeypatch.setattr(api_module, "research_run_ledger", ledger)
    monkeypatch.setattr(api_module, "experience_repository", repository)
    run = api_request("POST", "/api/v1/research/runs", json={
        "request_id": "req-batch-review", "question_text": "两只股票怎么比较？",
        "normalized_intent": "stock_comparison", "evidence_pack_ids": ["EP-AAAAAAAAAAAAAAAAAAAA"],
        "final_answer": "先给实质差异。", "validation_report": {"valid": True},
        "source_freshness": {"announcement": "2026-08-11"}, "agent_surface": "codex_desktop",
    }).json()
    api_request("POST", f"/api/v1/research/runs/{run['run_id']}/feedback", json={
        "feedback_text": "先给判断", "category": "presentation", "submitted_by": "owner",
    })
    queue = api_request("GET", "/api/v1/experience-review/queue?limit=10").json()
    card = queue["cards"][0]
    export = {
        "review_session_id": queue["review_session_id"], "review_version": queue["review_version"],
        "exported_at": "2026-08-12T00:00:00Z", "source_packet": queue["source_packet"],
        "decisions": [{
            "card_id": card["card_id"], "decision": "accept_suggested", "note": "",
            "target_field": card["target_field"], "affected_area": card["affected_area"],
            "scope": card["scope"], "recommended_decision": card["recommendation"],
            "question": card["decision_requested"],
        }],
    }

    first = api_request("POST", "/api/v1/experience-review/decisions", json=export)
    second = api_request("POST", "/api/v1/experience-review/decisions", json=export)

    assert first.status_code == 200
    assert first.json()["applied"][0] == {"card_id": card["card_id"], "status": "accepted", "replayed": False}
    assert second.json()["applied"][0]["replayed"] is True
    assert repository.get(card["card_id"]).status.value == "accepted"


def test_persisted_evidence_pack_is_available_for_run_audit(monkeypatch, tmp_path) -> None:
    ledger = ResearchRunLedger(tmp_path / "runs.sqlite3")
    monkeypatch.setattr(api_module, "research_run_ledger", ledger)
    content = {
        "rows": [{"row_id": "row-1"}],
        "lens_invocations": [{"release_id": "RL-1"}],
        "coverage_gaps": [],
    }
    digest = hashlib.sha256(json.dumps(
        content, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")).hexdigest()
    pack = ledger.store_evidence_pack({
        **content, "pack_id": f"EP-{digest[:20].upper()}", "pack_digest": digest,
    })

    response = api_request("GET", f"/api/v1/research/evidence/{pack.pack_id}")

    assert response.status_code == 200
    assert response.json()["payload"]["rows"][0]["row_id"] == "row-1"


def test_stream_answers_non_seed_stock_name_with_real_backing(monkeypatch) -> None:
    monkeypatch.setattr(api_module, "openai_configured", lambda: False)
    request_payload = {
        "request_id": "req-huawei-micro",
        "question": "ST华微为什么被ST？最近有哪些关键公告和风险节点？",
        "llm_mode": "off",
    }

    response = api_request("POST", "/api/v1/answers/stream", json=request_payload)

    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[-1]["event"] == "completed"
    result = events[-1]["payload"]["response"]
    assert result["interpretation"]["object"] == {"kind": "stock", "ref": "600360"}
    assert result["answer_card"] is not None
    assert result["claims"]
    assert not any(event["event"] == "error" for event in events)


def test_ndjson_stream_emits_validated_domain_events() -> None:
    response = api_request(
        "POST",
        "/api/v1/answers/stream",
        json=payload("日历月份效应的证据等级和反例是什么？", kind="lens_cluster", ref="C03"),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    rows = [json.loads(line) for line in response.text.splitlines()]
    assert [row["sequence"] for row in rows] == list(range(1, len(rows) + 1))
    assert rows[0]["event"] == "accepted"
    assert rows[-1]["event"] == "completed"
    assert all(row["event"] not in {"token", "delta", "token_delta"} for row in rows)
    answer_event = next(row for row in rows if row["event"] == "answer_card")
    assert answer_event["payload"]["response"]["answer_card"] is not None


def test_auto_stream_exposes_deterministic_card_before_llm_completion(monkeypatch) -> None:
    original_final = api_module.orchestrate
    monkeypatch.setattr(
        api_module,
        "orchestrate",
        lambda request: api_module.orchestrate_deterministic(request),
    )
    request_payload = payload("沐邦为什么 ST？关键节点是什么？")
    request_payload["llm_mode"] = "auto"

    response = api_request("POST", "/api/v1/answers/stream", json=request_payload)

    monkeypatch.setattr(api_module, "orchestrate", original_final)
    rows = [json.loads(line) for line in response.text.splitlines()]
    answer_index = next(index for index, row in enumerate(rows) if row["event"] == "answer_card")
    completed_index = next(index for index, row in enumerate(rows) if row["event"] == "completed")
    assert answer_index < completed_index
    assert rows[answer_index]["payload"]["response"]["answer_card"] is not None
    assert rows[answer_index]["payload"]["response"]["llm_used"] is False


def test_llm_phase_failure_keeps_deterministic_card_and_completes(monkeypatch) -> None:
    def fail(_request):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(api_module, "orchestrate", fail)
    request_payload = payload("沐邦为什么 ST？关键节点是什么？")
    request_payload["llm_mode"] = "auto"

    response = api_request("POST", "/api/v1/answers/stream", json=request_payload)

    rows = [json.loads(line) for line in response.text.splitlines()]
    assert any(row["event"] == "answer_card" for row in rows)
    assert rows[-1]["event"] == "completed"
    assert rows[-1]["payload"]["response"]["answer_card"] is not None
    assert rows[-1]["payload"]["response"]["degraded"] is True
    assert not any(row["event"] == "error" for row in rows)


def test_stream_failure_returns_safe_error_event(monkeypatch) -> None:
    def fail(_request):
        raise RuntimeError("sensitive local detail")

    monkeypatch.setattr(api_module, "orchestrate_deterministic", fail)
    response = api_request(
        "POST",
        "/api/v1/answers/stream",
        json=payload("测试流错误"),
    )

    rows = [json.loads(line) for line in response.text.splitlines()]
    assert rows == [
        {
                "contract_version": "v8_copilot_api_contract_v2",
            "request_id": "req-api-test",
            "sequence": 1,
            "event": "error",
            "emitted_at": rows[0]["emitted_at"],
            "payload": {"code": "stream_failed", "message": "研究内核执行失败。"},
        }
    ]
    assert "sensitive local detail" not in response.text


def test_dossier_endpoint_uses_real_read_only_sources() -> None:
    sources = [BASE_DB, EPISODE_INDEX, RELEASE_LIBRARY]
    before = {path: path.stat().st_mtime_ns for path in sources}

    response = api_request("GET", "/api/v1/stocks/603398/dossier")

    after = {path: path.stat().st_mtime_ns for path in sources}
    assert response.status_code == 200
    assert before == after
    body = response.json()
    assert body["symbol"] == "603398"
    with sqlite3.connect(f"file:{BASE_DB}?mode=ro", uri=True) as connection:
        expected_price_count = connection.execute(
            "select count(*) from daily_prices where symbol=? and adjust='qfq'",
            ("603398",),
        ).fetchone()[0]
    assert body["as_of"] == body["price_series"][-1]["date"]
    assert len(body["price_series"]) == expected_price_count
    assert len(body["events"]) >= 300
    assert len({event["event_id"] for event in body["events"]}) == len(body["events"])
    assert {item["release_id"] for item in body["lens_summaries"]} == {
        "RL-C-002", "RL-C-003",
    }
    assert body["display_labels"]["lens_library_size"] == "冻结库 9 条"
    assert "条正式公告" in body["display_labels"]["event_count"]
    assert "个 M6 已分类节点" in body["display_labels"]["event_count"]
    assert body["display_labels"]["announcement_data_as_of"]
    assert "RL-A-003" not in {item["release_id"] for item in body["lens_summaries"]}
    assert all("episode_label" in event for event in body["events"])


def test_dossier_invalid_or_missing_symbol_fails_cleanly() -> None:
    assert api_request("GET", "/api/v1/stocks/abc/dossier").status_code == 422
    response = api_request("GET", "/api/v1/stocks/999999/dossier")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "dossier_not_found"


def test_dossier_announcement_focus_is_resolved_from_sqlite_not_url_metadata() -> None:
    focused = api_request(
        "GET",
        "/api/v1/stocks/603398/dossier?announcement_focus=announcement%3A1221661091",
    )
    fake = api_request(
        "GET",
        "/api/v1/stocks/603398/dossier?announcement_focus=announcement%3AFAKE",
    )
    bare = api_request(
        "GET",
        "/api/v1/stocks/603398/dossier?announcement_focus=1221766612",
    )

    assert focused.status_code == 200
    event = next(
        item for item in focused.json()["events"]
        if item["event_id"] == "announcement:1221661091"
    )
    assert event["title"] == "江西沐邦高科股份有限公司关于董事会、监事会延期换届选举的提示性公告"
    assert event["episode_label"] == "正式公告（尚未纳入 M6 事件段）"
    assert all(item["event_id"] != "announcement:FAKE" for item in fake.json()["events"])
    assert sum(
        item["event_id"] == "announcement:1221766612"
        for item in bare.json()["events"]
    ) == 1


def test_dossier_merges_cninfo_refresh_without_promoting_title_to_lens(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(dossier_service, "ANNOUNCEMENT_REFRESH_DIR", tmp_path)
    (tmp_path / "300068.json").write_text(json.dumps({
        "symbol": "300068",
        "source": "cninfo",
        "count": 1,
        "records": [{
            "announcement_id": "TEST-CNINFO-1",
            "announcement_date": "2026-07-08",
            "title": "关于重大资产重组事项的提示性公告",
        }],
    }, ensure_ascii=False), encoding="utf-8")

    response = api_request("GET", "/api/v1/stocks/300068/dossier")

    assert response.status_code == 200
    body = response.json()
    event = next(
        item for item in body["events"]
        if item["event_id"] == "announcement:TEST-CNINFO-1"
    )
    assert event["subtype"] == "announcement_unclassified"
    assert event["episode_label"] == "正式公告（尚未纳入 M6 事件段）"
    assert event["timeline_lane"] == "restructuring"
    assert "RL-C-004" not in {
        item["release_id"] for item in body["lens_summaries"]
    }
    assert body["display_labels"]["announcement_data_as_of"] == "2026-07-08"


def test_cors_is_restricted_to_local_vite_origins() -> None:
    allowed = api_request(
        "OPTIONS",
        "/api/v1/health",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = api_request(
        "OPTIONS",
        "/api/v1/health",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert "access-control-allow-origin" not in denied.headers


def test_spa_static_files_support_deep_links_without_hiding_asset_404s(tmp_path) -> None:
    (tmp_path / "index.html").write_text("<main>copilot</main>", encoding="utf-8")
    static_app = SPAStaticFiles(directory=tmp_path, html=True)
    test_app = FastAPI()
    test_app.mount("/", static_app)

    async def fetch(path: str) -> httpx.Response:
        transport = httpx.ASGITransport(app=test_app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(path)

    deep_link = asyncio.run(fetch("/stocks/603398"))
    missing_asset = asyncio.run(fetch("/assets/missing.js"))

    assert deep_link.status_code == 200
    assert deep_link.text == "<main>copilot</main>"
    assert missing_asset.status_code == 404
