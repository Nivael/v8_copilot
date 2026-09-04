from pathlib import Path

import pytest

from p8_publish import REQUIRED_KINDS, build_status
from p8_research import P8ResearchRepository, build_run


def _persist_empty_run(repository: P8ResearchRepository, kind: str, through: str) -> None:
    run = build_run(
        run_kind=kind,
        contract_version="test",
        start_date=through,
        through=through,
        source_run_ids=[],
        source_digests={"empty": kind},
        record_payloads={},
    )
    repository.persist(run=run, records={})


def test_publish_status_fails_closed_when_a_materialization_is_missing(tmp_path: Path) -> None:
    repository = P8ResearchRepository(tmp_path / "p8.sqlite3")
    for kind in REQUIRED_KINDS[:-1]:
        _persist_empty_run(repository, kind, "2026-09-03")

    with pytest.raises(ValueError, match="backtest"):
        build_status(repository, as_of="2026-09-03")


def test_publish_status_fails_closed_when_run_dates_do_not_align(tmp_path: Path) -> None:
    repository = P8ResearchRepository(tmp_path / "p8.sqlite3")
    for kind in REQUIRED_KINDS:
        through = "2026-09-02" if kind == "activity_features" else "2026-09-03"
        _persist_empty_run(repository, kind, through)

    with pytest.raises(ValueError, match="activity_features"):
        build_status(repository, as_of="2026-09-03")
