import asyncio
import json
from pathlib import Path

import api as api_module
import httpx
from api import SPAStaticFiles
from answer_engine import BASE_DB, EPISODE_INDEX
from fastapi import FastAPI
from jsonschema import Draft202012Validator
from lens_binding import RELEASE_LIBRARY


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


def test_health_exposes_contracts_and_read_only_mode(monkeypatch) -> None:
    monkeypatch.setattr(api_module, "openai_configured", lambda: False)
    response = api_request("GET", "/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "api_contract_version": "v8_copilot_api_contract_v1",
        "request_contract_version": "v8_copilot_api_contract_v0",
        "response_contract_version": "v8_copilot_api_contract_v1",
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
    assert body["contract_version"] == "v8_copilot_api_contract_v1"
    assert body["answer_card"]["contract_version"] == "v8_answer_contract_v0"
    assert [row["中位(天)"] for row in body["answer_card"]["body_rows"]] == [4, 10, 14]
    schema = json.loads((
        Path(__file__).resolve().parents[1]
        / "contracts/v8_answer_contract_v0/schema.json"
    ).read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(body["answer_card"])


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


def test_stream_failure_returns_safe_error_event(monkeypatch) -> None:
    def fail(_request):
        raise RuntimeError("sensitive local detail")

    monkeypatch.setattr(api_module, "orchestrate", fail)
    response = api_request(
        "POST",
        "/api/v1/answers/stream",
        json=payload("测试流错误"),
    )

    rows = [json.loads(line) for line in response.text.splitlines()]
    assert rows == [
        {
            "contract_version": "v8_copilot_api_contract_v1",
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
    assert body["as_of"] == "2026-06-26"
    assert len(body["price_series"]) == 1982
    assert len(body["events"]) >= 150
    assert len({event["event_id"] for event in body["events"]}) == len(body["events"])
    assert len(body["lens_summaries"]) == 3
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
    assert event["episode_label"] == "公开公告（未纳入事件段）"
    assert all(item["event_id"] != "announcement:FAKE" for item in fake.json()["events"])
    assert sum(
        item["event_id"] == "announcement:1221766612"
        for item in bare.json()["events"]
    ) == 1


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
