import sqlite3

import pytest

from p8_event_graph import SPEC_BY_NODE, _event, _find_span, _matched_specs
from p8_research import (
    P8ResearchRepository,
    build_run,
    publish_manifest,
    to_claim_event,
)


def _verified_event():
    text = "人民法院裁定受理公司重整。"
    return _event(
        symbol="000001", available_as_of="2026-01-02",
        spec=SPEC_BY_NODE["formal_restructuring_accepted"],
        source_ids=["ann-1"],
        span=_find_span(text, "裁定受理公司重整", "official:ann-1"),
        evidence_status="deterministic_verified",
        source_digest="a" * 64,
    )


def test_precursor_registry_separates_process_and_old_equity_effect():
    matches = _matched_specs("法院裁定受理公司重整，方案条款尚未披露。")
    assert matches[0][0].node == "formal_restructuring_accepted"
    assert matches[0][0].process_direction == "advance"
    assert matches[0][0].old_equity_effect == "unknown"

    plan = _matched_specs("法院裁定批准重整计划。")
    assert plan[0][0].process_direction == "advance"
    assert plan[0][0].old_equity_effect == "mixed"


def test_claim_view_only_accepts_verified_records():
    verified = _verified_event()
    assert to_claim_event(verified) is not None
    provisional = verified.model_copy(update={"evidence_status": "provisional"})
    assert to_claim_event(provisional) is None


def test_repository_is_append_only_and_manifest_moves_only_on_explicit_publish(tmp_path):
    event = _verified_event().model_dump(mode="json")
    records = {"derived_event": [event]}
    run = build_run(
        run_kind="event_graph", contract_version="test",
        start_date="2026-01-01", through="2026-01-02",
        source_run_ids=["source"], source_digests={"source": "b" * 64},
        record_payloads=records,
    )
    repository = P8ResearchRepository(tmp_path / "p8.sqlite3")
    repository.persist(run=run, records=records)
    repository.persist(run=run, records=records)
    with sqlite3.connect(repository.path) as connection:
        assert connection.execute("select count(*) from p8_runs").fetchone()[0] == 1
        assert connection.execute("select count(*) from p8_records").fetchone()[0] == 1

    manifest_path = tmp_path / "manifest.json"
    assert not manifest_path.exists()
    manifest = publish_manifest(manifest_path, runs=[run], through=run.through)
    assert manifest_path.exists()
    assert manifest.run_ids_by_kind["event_graph"] == run.run_id

    bad = run.model_copy(update={"content_digest": "c" * 64})
    with pytest.raises(ValueError, match="digest 冲突"):
        repository.persist(run=bad, records=records)
