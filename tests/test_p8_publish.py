from pathlib import Path

import pytest

from p8_publish import REQUIRED_KINDS, build_status
from p8_research import P8ResearchRepository, build_run


def _persist_run(
    repository: P8ResearchRepository, kind: str, through: str,
    records: dict[str, list[dict]] | None = None,
) -> None:
    records = records or {}
    run = build_run(
        run_kind=kind,
        contract_version="test",
        start_date=through,
        through=through,
        source_run_ids=[],
        source_digests={"empty": kind},
        record_payloads=records,
    )
    repository.persist(run=run, records=records)


def test_publish_status_fails_closed_when_a_materialization_is_missing(tmp_path: Path) -> None:
    repository = P8ResearchRepository(tmp_path / "p8.sqlite3")
    for kind in REQUIRED_KINDS[:-1]:
        _persist_run(repository, kind, "2026-09-03")

    with pytest.raises(ValueError, match="backtest"):
        build_status(repository, as_of="2026-09-03")


def test_publish_status_fails_closed_when_run_dates_do_not_align(tmp_path: Path) -> None:
    repository = P8ResearchRepository(tmp_path / "p8.sqlite3")
    for kind in REQUIRED_KINDS:
        through = "2026-09-02" if kind == "activity_features" else "2026-09-03"
        _persist_run(repository, kind, through)

    with pytest.raises(ValueError, match="activity_features"):
        build_status(repository, as_of="2026-09-03")


def test_publish_status_requires_and_reports_complete_current_cohort(tmp_path: Path) -> None:
    repository = P8ResearchRepository(tmp_path / "p8.sqlite3")
    through = "2026-09-03"
    for kind in REQUIRED_KINDS:
        records: dict[str, list[dict]] = {}
        if kind == "event_graph":
            records = {"company_frontier": [{
                "record_id": "frontier-1", "symbol": "000001",
                "available_as_of": through, "evidence_status": "no_event_observed",
            }]}
        elif kind == "scenario_references":
            records = {"current_scenario_map": [{
                "record_id": f"map-{family}", "symbol": "000001",
                "available_as_of": through, "evidence_status": "partial",
                "reference_family": family,
            } for family in (
                "strategic_entry_reference", "failure_exit_reference", "public_node_reference",
            )]}
        elif kind == "portfolio":
            records = {"portfolio_summary": [{
                "record_id": "portfolio-1", "symbol": "",
                "available_as_of": through, "evidence_status": "unavailable",
                "source_funnel_run_ids": ["funnel-day-1"],
            }]}
        _persist_run(repository, kind, through, records)

    status, _runs = build_status(repository, as_of=through)
    assert status["capabilities"]["current_scenario_map_complete"] is True
    assert status["capabilities"]["current_member_frontiers"] == 1
    assert status["capabilities"]["forward_shadow_days"] == 1
    assert status["capabilities"]["operational_10_day_gate"] == "accumulating"
