from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone

from experience_contract import ExperienceCandidateInput, ExperienceReviewRequest
from experience_governance import ExperienceGovernanceRepository, RegressionReport
from learning_status import build_learning_status
from research_repository import ExperienceRepository, ResearchRunCreate, ResearchRunLedger


NOW = datetime(2026, 11, 5, 1, tzinfo=timezone.utc)


def setup_sources(tmp_path):
    repo = ExperienceRepository(tmp_path / "experience.sqlite3")
    ledger = ResearchRunLedger(tmp_path / "runs.sqlite3")
    governance = ExperienceGovernanceRepository(tmp_path / "governance.sqlite3")
    run = ledger.record(ResearchRunCreate(
        request_id="real-run", question_text="怎样统一比较范围？", normalized_intent="comparison",
        evidence_pack_ids=["EP-AAAAAAAAAAAAAAAAAAAA"], final_answer="统一主体和截止日。",
        validation_report={"valid": True}, source_freshness={}, agent_surface="test",
    ))
    candidate = repo.propose(ExperienceCandidateInput(
        experience_type="query_plan", title="统一比较范围", value_summary="先统一主体和截止日。",
        trigger_conditions=["比较"], scope=["comparison"], required_inputs=["scope"],
        answer_rubric=["说明范围"], anti_patterns=["混淆主体"], coverage_boundaries=["只比较同一口径"],
        validation_refs=["regression:entity_scope_boundary"],
        source_run_refs=[run.run_id, "migration:legacy"],
    ))
    record = repo.review(candidate.experience_id, ExperienceReviewRequest(
        action="accept", actor_type="human", reviewed_by="owner",
    ))
    # A real, successful empty batch is deliberately NOT evidence for this method.
    governance.record(RegressionReport(
        run_id="XRG-AAAAAAAAAAAAAAAAAAAA", started_at="2026-10-01T00:00:00Z",
        completed_at="2026-10-01T00:01:00Z", cadence_days=30, due_only=True,
        accepted_examined=0, passed=0, failed=0, unverified=0, results=[],
    ))
    manifest = tmp_path / "freshness.json"
    manifest.write_text(json.dumps({
        "contract_version": "v8_freshness_manifest_v1", "manifest_id": "FM-AAAAAAAAAAAAAAAAAAAA",
        "generated_at": "2026-09-08T00:00:00Z", "overall_status": "ready",
        "research_symbols": ["603398"], "sources": [{
            "source_id": "daily_prices", "label": "日线", "source_ref": "daily_prices",
            "status": "current", "as_of": "2026-09-07", "expected_through": "2026-09-07",
        }],
    }))
    return record, dict(experience_db=repo.path, ledger_db=ledger.path,
                        governance_db=governance.path, freshness_path=manifest, now=NOW)


def test_empty_batch_is_not_a_verified_inventory_and_reads_do_not_write(tmp_path):
    record, args = setup_sources(tmp_path)
    paths = [value for value in args.values() if hasattr(value, "read_bytes")]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}

    result = build_learning_status(**args)

    assert result["counts"]["accepted"] == 1
    assert result["regression_counts"]["current"] == 0
    assert result["regression_counts"]["never_checked"] == 1
    assert result["latest_regression"]["accepted_examined"] == 0
    method = result["methods"][0]
    assert method["experience_id"] == record.experience_id
    assert method["source_ref_count"] == 2
    assert method["validator_passed_source_runs"] == 1
    assert method["unresolved_source_refs"] == ["migration:legacy"]
    assert result["quality_evaluation"]["accuracy"] is None
    assert result["freshness"]["sources"][0]["age_calendar_days"] == 59
    assert result["freshness"]["sources"][0]["declared_status"] == "current"
    assert before == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def test_missing_sources_remain_missing_and_unknown_instead_of_zero(tmp_path):
    args = {name: tmp_path / name for name in ("experience_db", "ledger_db", "governance_db", "freshness_path")}
    result = build_learning_status(**args, now=NOW)
    assert result["counts"] is None
    assert result["runs"] is None
    assert result["regression_counts"] is None
    assert result["availability"]["experiences"] == "missing"
    assert result["freshness"]["availability"] == "missing"
    assert list(tmp_path.iterdir()) == []


def test_reaccepted_expired_failed_and_future_checks_are_not_current(tmp_path):
    record, args = setup_sources(tmp_path)
    with sqlite3.connect(args["experience_db"]) as connection:
        connection.execute("update experiences set reviewed_at='2026-10-01T00:00:00+00:00'")
    for checked, due, status, expected in [
        ("2026-11-01T00:00:00Z", "2026-12-01T00:00:00Z", "passed", "current"),
        ("2026-10-01T00:00:00Z", "2026-11-01T00:00:00Z", "passed", "due"),
        ("2026-09-01T00:00:00Z", "2026-12-01T00:00:00Z", "passed", "needs_recheck"),
        ("2026-11-01T00:00:00Z", "2026-12-01T00:00:00Z", "failed", "failed"),
        ("2026-11-06T00:00:00Z", "2026-12-01T00:00:00Z", "passed", "unverified"),
    ]:
        with sqlite3.connect(args["governance_db"]) as connection:
            connection.execute("insert or replace into experience_regression_status values (?,?,?,?,?)",
                               (record.experience_id, "XRG-AAAAAAAAAAAAAAAAAAAA", status, checked, due))
        result = build_learning_status(**args)
        assert result["regression_counts"][expected] == 1
        assert result["regression_counts"]["current"] == (expected == "current")


def test_corrupt_source_degrades_independently_and_does_not_hide_methods(tmp_path):
    _, args = setup_sources(tmp_path)
    args["freshness_path"].write_text("not json")
    args["ledger_db"] = tmp_path / "broken.sqlite3"
    args["ledger_db"].write_text("not sqlite")
    result = build_learning_status(**args)
    assert result["counts"]["accepted"] == 1
    assert result["methods"][0]["validator_passed_source_runs"] is None
    assert result["runs"] is None
    assert result["availability"]["runs"] == "invalid"
    assert result["freshness"]["availability"] == "invalid"


def test_observation_date_is_beijing_date_not_utc_date(tmp_path):
    _, args = setup_sources(tmp_path)
    args["now"] = datetime(2026, 11, 4, 19, tzinfo=timezone.utc)
    assert build_learning_status(**args)["observation_date"] == "2026-11-05"


def test_read_only_http_endpoint_uses_configured_sources(tmp_path, monkeypatch):
    import asyncio
    import httpx
    import api
    _, args = setup_sources(tmp_path)
    monkeypatch.setattr(api, "experience_repository", ExperienceRepository(args["experience_db"]))
    monkeypatch.setattr(api, "research_run_ledger", ResearchRunLedger(args["ledger_db"]))
    monkeypatch.setattr(api, "experience_governance_repository", ExperienceGovernanceRepository(args["governance_db"]))
    monkeypatch.setattr(api, "FRESHNESS_MANIFEST_PATH", args["freshness_path"])
    async def request():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://test") as client:
            return await client.get("/api/v1/learning/status")
    response = asyncio.run(request())
    assert response.status_code == 200
    assert response.json()["counts"]["accepted"] == 1
    assert response.json()["regression_counts"]["current"] == 0
    assert response.json()["read_only"] is True
