"""Run the fixed v0 fault matrix against snapshot and answer contracts."""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from answer_engine import (
    AnalysisClaim,
    AnswerCard,
    BackingRef,
    DataDebtRow,
    FIXED_CAVEATS,
)
from lens_binding import LensGap, LensRegistry
from snapshot_metadata import load_episode_snapshot, load_price_snapshot


MATRIX_PATH = Path(__file__).with_name("fault_injection_set_v0.json")


def _base_card() -> AnswerCard:
    return AnswerCard(
        question="故障注入测试",
        object_ref="stock:000001",
        view="query",
        as_of="2026-07-10",
        sample_scope="fixture N=1",
        evidence_grade="descriptive_query",
        data_snapshot_as_of="2026-07-10",
        source_freshness={"fixture_as_of": "2026-07-10"},
        lens_gap=[LensGap(
            gap_id="fixture_gap",
            missing_for="fixture",
            sediment_as="question_card:QC-FI-001",
        )],
        body_rows=[{"row_id": "fixture_row", "value": 1}],
        caveats=list(FIXED_CAVEATS),
        provenance=["fixture:source"],
    )


def _manifest(path: Path, payload: dict | None = None) -> Path:
    path.write_text(json.dumps(payload or {
        "builder_version": "fixture_v1", "as_of": "2026-07-10"
    }), encoding="utf-8")
    return path


def _price_db(path: Path, *, with_table: bool = True) -> Path:
    with sqlite3.connect(path) as connection:
        if with_table:
            connection.execute(
                "create table daily_prices "
                "(symbol text,trade_date text,close real,adjust text)"
            )
            connection.executemany(
                "insert into daily_prices values (?,?,?,?)",
                [("000001", f"2026-01-{day:02d}", float(day), "qfq") for day in range(1, 13)],
            )
        else:
            connection.execute("create table unrelated (value text)")
    return path


def _library(path: Path, *, provenance: bool = True) -> Path:
    record = {
        "release_id": "RL-FI-001",
        "release_role": "methodology_frame",
        "logic_chain_summary": "fixture: logic",
        "provenance_refs": ["fixture:source"] if provenance else [],
    }
    path.write_text(json.dumps({
        "library_version": "fixture_v1",
        "frozen_at": "2026-07-10T00:00:00Z",
        "records": [record],
    }), encoding="utf-8")
    return path


def _cases(root: Path) -> dict[str, Callable[[], object]]:
    valid_manifest = _manifest(root / "episode_manifest.json")
    valid_index = root / "episode.jsonl"
    valid_index.write_text('{"symbol":"000001"}\n', encoding="utf-8")
    return {
        "FI-001": lambda: load_price_snapshot(root / "missing.sqlite3"),
        "FI-002": lambda: load_price_snapshot(_price_db(root / "missing_table.sqlite3", with_table=False)),
        "FI-003": lambda: load_price_snapshot(
            _price_db(root / "mismatch.sqlite3"), expected_as_of="2026-02-01"
        ),
        "FI-004": lambda: load_episode_snapshot(root / "missing.jsonl", valid_manifest),
        "FI-005": lambda: load_episode_snapshot(
            (root / "broken.jsonl"), valid_manifest
        ),
        "FI-006": lambda: load_episode_snapshot(
            valid_index,
            _manifest(root / "incomplete_manifest.json", {"builder_version": ""}),
        ),
        "FI-007": lambda: LensRegistry(root / "missing_library.json"),
        "FI-008": lambda: LensRegistry(_library(root / "bad_library.json", provenance=False)),
        "FI-009": _hanging_backing,
        "FI-010": _missing_debt_id,
    }


def _hanging_backing() -> None:
    card = _base_card()
    card.analysis_claims = [AnalysisClaim(
        text="fixture claim",
        claim_type="fact",
        backing=BackingRef(kind="query_row", ref="missing_row"),
    )]
    card.validate()


def _missing_debt_id() -> None:
    card = _base_card()
    card.view = "data_debt"
    card.evidence_grade = "insufficient_data"
    card.data_debt = [DataDebtRow(gap="fixture", affects="fixture", debt_ref="")]
    card.validate()


def run_fault_injections() -> list[dict[str, str]]:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    if len(matrix) != 10 or len({case["case_id"] for case in matrix}) != 10:
        raise AssertionError("fault injection matrix 必须恰好包含 10 个唯一案例")
    results: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="v8-faults-") as directory:
        root = Path(directory)
        broken = root / "broken.jsonl"
        broken.write_text("{broken\n", encoding="utf-8")
        cases = _cases(root)
        for specification in matrix:
            case_id = specification["case_id"]
            try:
                cases[case_id]()
            except Exception as exc:  # the matrix checks exact public failure behavior
                if type(exc).__name__ != specification["expected_error"]:
                    raise AssertionError(
                        f"{case_id} error type: {type(exc).__name__}"
                    ) from exc
                if specification["message_contains"] not in str(exc):
                    raise AssertionError(f"{case_id} error message: {exc}") from exc
                results.append({"case_id": case_id, "status": "passed"})
            else:
                raise AssertionError(f"{case_id} 未按预期失败")
    return results


def main() -> None:
    results = run_fault_injections()
    print(f"fault injection eval passed {len(results)}/10")


if __name__ == "__main__":
    main()
