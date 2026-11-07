"""Regression tests for the P9D transition-queue audit.

Two layers:

1. Hermetic tests over synthetic events. These lock the *method*: dedupe key,
   same-day handling, declared-edge conditioning, terminal nodes, censoring,
   the cell-level sample gate, and the non-trading-date policy.

2. Real-data tests over the pinned P8 manifest. These lock the *numbers* the
   audit document publishes. They skip when the data root is not reachable.

Run the real-data half with the shared data root, e.g.::

    V8_DATA_ROOT=/path/to/st_research uv run pytest tests/test_p9_transition_audit.py
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

import settings
from p9_transition_audit import (
    AUDIT_VERSION,
    NONTRADING_EXCLUDE,
    NONTRADING_NEXT_TRADING_DAY,
    TIERS,
    VERDICT_FREQUENCY,
    VERDICT_INSUFFICIENT,
    VERDICT_RAW_ONLY,
    audit,
    frequency_cells,
    prepare,
    run_audit,
    verdict_for,
)

VERIFIED = "deterministic_verified"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def trading_days(start: str, count: int) -> list[str]:
    """``count`` consecutive calendar dates treated as trading days."""
    first = dt.date.fromisoformat(start)
    return [(first + dt.timedelta(days=i)).isoformat() for i in range(count)]


def event(symbol, node, day, tier=VERIFIED, successors=(), **extra):
    payload = {
        "symbol": symbol,
        "node": node,
        "available_as_of": day,
        "evidence_status": tier,
        "possible_successors": list(successors),
    }
    payload.update(extra)
    return payload


def cells_by_key(rows):
    return {(c.start_node, c.successor_node): c for r in rows for c in r.cells}


# --------------------------------------------------------------------------
# 1. hermetic: method locks
# --------------------------------------------------------------------------


def test_dedupe_collapses_repeated_symbol_node_date():
    calendar = trading_days("2026-01-05", 30)
    raw = [
        event("A", "X", calendar[0], successors=("Y",)),
        event("A", "X", calendar[0], successors=("Y",)),
        event("A", "X", calendar[0], successors=("Y",)),
    ]
    prepared = prepare(raw, calendar)
    assert prepared.total_rows == 3
    assert prepared.duplicate_rows_removed == 2
    assert len(prepared.events) == 1


def test_same_day_follow_on_is_not_a_transition():
    """A node observed on the same day is co-disclosure, not a transition."""
    calendar = trading_days("2026-01-05", 30)
    raw = [
        event("A", "X", calendar[0], successors=("Y",)),
        event("A", "Y", calendar[0]),
    ]
    rows = audit(prepare(raw, calendar), VERIFIED, horizon=10)
    node = next(r for r in rows if r.node == "X")
    assert node.cells == []
    assert node.undeclared_successors == {}


def test_declared_edge_conditioning_keeps_undeclared_out_of_frequency():
    """An observed follow-on outside the declared edge set is diagnostics only."""
    calendar = trading_days("2026-01-05", 30)
    raw = [
        event("A", "X", calendar[0], successors=("Y",)),
        event("A", "Z", calendar[5]),      # observed, but not a declared edge
        event("A", "Y", calendar[10]),     # observed and declared
    ]
    rows = audit(prepare(raw, calendar), VERIFIED, horizon=20)
    node = next(r for r in rows if r.node == "X")
    keys = {(c.start_node, c.successor_node) for c in node.cells}
    assert keys == {("X", "Y")}
    assert node.undeclared_successors == {"Z": 1}
    assert frequency_cells(rows) == [] or all(
        c.successor_node != "Z" for c in frequency_cells(rows)
    )


def test_terminal_node_has_empty_edges_and_no_cells():
    calendar = trading_days("2026-01-05", 30)
    raw = [
        event("A", "TERM", calendar[0]),
        event("A", "Y", calendar[10]),
    ]
    rows = audit(prepare(raw, calendar), VERIFIED, horizon=20)
    node = next(r for r in rows if r.node == "TERM")
    assert node.terminal is True
    assert node.declared_edges == ()
    assert node.cells == []


def test_censoring_removes_events_without_a_full_window():
    calendar = trading_days("2026-01-05", 30)
    raw = [
        event("A", "X", calendar[0], successors=("Y",)),
        event("B", "X", calendar[25], successors=("Y",)),   # only 4 days remain
    ]
    rows = audit(prepare(raw, calendar), VERIFIED, horizon=10)
    node = next(r for r in rows if r.node == "X")
    assert node.risk_set_n == 2
    assert node.censored_n == 1
    assert node.observable_n == 1


def test_start_gate_pass_does_not_imply_cell_gate_pass():
    """The plan_approved shape: start clears the gate, the cell does not."""
    calendar = trading_days("2026-01-05", 40)
    raw = [event(f"S{i}", "START", calendar[0], successors=("NEXT",)) for i in range(8)]
    raw.append(event("S0", "NEXT", calendar[5]))   # exactly one observed transition
    rows = audit(prepare(raw, calendar), VERIFIED, horizon=20)
    node = next(r for r in rows if r.node == "START")
    assert node.risk_set_n == 8 and node.companies == 8   # start gate would pass
    cell = cells_by_key(rows)[("START", "NEXT")]
    assert cell.observed_n == 1
    assert cell.verdict == VERDICT_INSUFFICIENT
    assert cell.frequency is None


def test_cell_gate_downgrades_when_companies_below_minimum():
    calendar = trading_days("2026-01-05", 40)
    raw = []
    for i in range(8):                                  # 8 observations, 3 companies
        raw.append(event(f"S{i % 3}", "START", calendar[i], successors=("NEXT",)))
    for i in range(8):
        raw.append(event(f"S{i % 3}", "NEXT", calendar[i + 1]))
    rows = audit(prepare(raw, calendar), VERIFIED, horizon=20)
    cell = cells_by_key(rows)[("START", "NEXT")]
    assert cell.observed_n >= 8
    assert cell.companies < 5
    assert cell.verdict == VERDICT_RAW_ONLY
    assert cell.frequency is None


def test_frequency_is_none_unless_verdict_is_frequency():
    assert verdict_for(7, 9) == VERDICT_RAW_ONLY
    assert verdict_for(8, 4) == VERDICT_RAW_ONLY
    assert verdict_for(8, 5) == VERDICT_FREQUENCY
    assert verdict_for(1, 1) == VERDICT_INSUFFICIENT
    assert verdict_for(0, 0) == VERDICT_INSUFFICIENT


def test_cell_carries_risk_set_censored_and_observable_denominator():
    calendar = trading_days("2026-01-05", 40)
    raw = [event(f"S{i}", "START", calendar[i], successors=("NEXT",)) for i in range(10)]
    for i in range(10):
        raw.append(event(f"S{i}", "NEXT", calendar[i + 1]))
    rows = audit(prepare(raw, calendar), VERIFIED, horizon=20)
    cell = cells_by_key(rows)[("START", "NEXT")]
    assert cell.risk_set_n == 10
    assert cell.censored_n == 0
    assert cell.observable_n == 10
    assert cell.horizon == 20
    assert cell.observed_n == 10
    assert cell.companies == 10
    assert cell.frequency == pytest.approx(1.0)


def test_tiers_are_never_merged():
    calendar = trading_days("2026-01-05", 40)
    raw = [
        event("A", "X", calendar[0], tier=VERIFIED, successors=("Y",)),
        event("B", "X", calendar[0], tier="provisional", successors=("Y",)),
        event("A", "Y", calendar[3]),
        event("B", "Y", calendar[3]),
    ]
    prepared = prepare(raw, calendar)
    verified = audit(prepared, VERIFIED, horizon=10)
    provisional = audit(prepared, "provisional", horizon=10)

    # X appears once per tier, each counting only its own tier's start event.
    vx = next(r for r in verified if r.node == "X")
    px = next(r for r in provisional if r.node == "X")
    assert vx.risk_set_n == 1
    assert px.risk_set_n == 1
    assert cells_by_key(verified)[("X", "Y")].tier == VERIFIED
    assert cells_by_key(provisional)[("X", "Y")].tier == "provisional"
    # A and B each transition once, so neither tier may report two.
    assert cells_by_key(verified)[("X", "Y")].observed_n == 1
    assert cells_by_key(provisional)[("X", "Y")].observed_n == 1


def test_nontrading_date_policy_exclude_vs_next_trading_day():
    calendar = ["2026-01-05", "2026-01-06", "2026-01-08"]   # 01-07 is not a session
    raw = [event("A", "X", "2026-01-07", successors=("Y",))]

    excluded = prepare(raw, calendar, NONTRADING_EXCLUDE)
    assert excluded.off_calendar_events == 1
    assert excluded.unresolved_events == 1
    assert excluded.events[0].trading_index is None

    rolled = prepare(raw, calendar, NONTRADING_NEXT_TRADING_DAY)
    assert rolled.off_calendar_events == 1
    assert rolled.unresolved_events == 0
    assert rolled.events[0].trading_index == 2     # 2026-01-08


def test_unknown_tier_is_rejected():
    with pytest.raises(ValueError):
        audit(prepare([], trading_days("2026-01-05", 5)), "made_up", horizon=10)


# --------------------------------------------------------------------------
# 2. real data: published-number locks
# --------------------------------------------------------------------------

DATA_ROOT = settings.DATA_ROOT
REAL_DBS = (
    settings.P8_RESEARCH_DB,
    settings.MARKET_ACTIVITY_DB,
    settings.P8_RESEARCH_MANIFEST_PATH,
    DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3",
)
real_data = pytest.mark.skipif(
    not all(p.is_file() for p in REAL_DBS),
    reason=(
        "pinned P8 manifest not reachable; set V8_DATA_ROOT to the st_research "
        f"root (current DATA_ROOT={DATA_ROOT})"
    ),
)

#: Locked baseline: manifest P8M-B3010C21F760B075CC71, non-trading policy=exclude.
LOCKED_MANIFEST_ID = "P8M-B3010C21F760B075CC71"
LOCKED_EVENT_GRAPH_RUN = "P8R-7CC0257555052AE82666"
LOCKED_DEDUPED_ROWS = 1547
LOCKED_DUPLICATES_REMOVED = 226
LOCKED_OFF_CALENDAR = 91

#: (start, successor) -> (observed_n, companies, observable_n)
LOCKED_FREQUENCY_CELLS = {
    ("investor_recruitment", "investor_agreement_signed"): (30, 20, 79),
    ("investor_recruitment", "investor_selected"): (11, 5, 79),
    ("restructuring_application_disclosed", "formal_restructuring_accepted"): (29, 13, 202),
    ("restructuring_application_disclosed", "pre_restructuring_started"): (26, 16, 202),
    ("pre_restructuring_started", "investor_recruitment"): (16, 14, 38),
}

#: Nodes whose declared edge set is empty; must never yield a frequency cell.
LOCKED_TERMINAL_NODES = (
    "risk_warning_removed",
    "delisting_decision",
    "restructuring_terminated",
    "restructuring_rejected",
)


@pytest.fixture(scope="module")
def real_result():
    manifest = json.loads(settings.P8_RESEARCH_MANIFEST_PATH.read_text(encoding="utf-8"))
    return run_audit(
        research_db=settings.P8_RESEARCH_DB,
        activity_db=settings.MARKET_ACTIVITY_DB,
        manifest=manifest,
        tiers=TIERS,
        horizons=(60, 120),
        nontrading_policy=NONTRADING_EXCLUDE,
    )


@real_data
def test_real_manifest_pins_expected_run(real_result):
    assert real_result["audit_version"] == AUDIT_VERSION
    assert real_result["manifest_id"] == LOCKED_MANIFEST_ID
    assert real_result["event_graph_run"] == LOCKED_EVENT_GRAPH_RUN
    assert real_result["deduped_rows"] == LOCKED_DEDUPED_ROWS
    assert real_result["duplicate_rows_removed"] == LOCKED_DUPLICATES_REMOVED
    assert real_result["off_calendar_events"] == LOCKED_OFF_CALENDAR
    assert real_result["calendar_days"] == 1333


@real_data
def test_real_verified_h60_frequency_cells_are_exactly_the_five(real_result):
    section = next(
        s
        for s in real_result["sections"]
        if s["tier"] == VERIFIED and s["horizon"] == 60
    )
    found = {
        (c["start_node"], c["successor_node"]): (c["observed_n"], c["companies"], c["observable_n"])
        for row in section["nodes"]
        for c in row["cells"]
        if c["verdict"] == VERDICT_FREQUENCY
    }
    assert found == LOCKED_FREQUENCY_CELLS


@real_data
def test_real_frequency_cells_only_exist_on_the_observable_denominator(real_result):
    for section in real_result["sections"]:
        for row in section["nodes"]:
            for cell in row["cells"]:
                assert cell["risk_set_n"] == row["risk_set_n"]
                assert cell["observable_n"] == cell["risk_set_n"] - cell["censored_n"]
                if cell["verdict"] != VERDICT_FREQUENCY:
                    assert cell["frequency"] is None
                else:
                    assert cell["observed_n"] <= cell["observable_n"]


@real_data
def test_real_plan_approved_cell_is_n1_and_not_a_frequency(real_result):
    """The regression the owner asked to lock: start gate passes, the cell does not."""
    section = next(
        s
        for s in real_result["sections"]
        if s["tier"] == VERIFIED and s["horizon"] == 60
    )
    start = next(r for r in section["nodes"] if r["node"] == "plan_approved")
    assert start["risk_set_n"] == 8
    assert start["companies"] == 8          # would pass a start-only gate
    assert len(start["cells"]) == 1
    cell = start["cells"][0]
    assert cell["successor_node"] == "plan_executed"
    assert cell["observed_n"] == 1
    assert cell["companies"] == 1
    assert cell["verdict"] == VERDICT_INSUFFICIENT
    assert cell["frequency"] is None


@real_data
def test_real_plan_approved_cell_moves_under_next_trading_day_policy():
    """Documents that the locked N=1 depends on the non-trading-date policy.

    Under the P8 PRD 3.3 convention (roll forward) the same cell is N=2 and
    upgrades to raw_points_only -- still not a frequency, but a different number.
    """
    manifest = json.loads(settings.P8_RESEARCH_MANIFEST_PATH.read_text(encoding="utf-8"))
    rolled = run_audit(
        research_db=settings.P8_RESEARCH_DB,
        activity_db=settings.MARKET_ACTIVITY_DB,
        manifest=manifest,
        tiers=(VERIFIED,),
        horizons=(60,),
        nontrading_policy=NONTRADING_NEXT_TRADING_DAY,
    )
    assert rolled["unresolved_events"] == 0
    section = rolled["sections"][0]
    start = next(r for r in section["nodes"] if r["node"] == "plan_approved")
    cell = start["cells"][0]
    assert cell["observed_n"] == 2
    assert cell["verdict"] == VERDICT_RAW_ONLY
    assert cell["frequency"] is None


@real_data
def test_real_terminal_nodes_never_produce_a_cell(real_result):
    for section in real_result["sections"]:
        for row in section["nodes"]:
            if row["node"] in LOCKED_TERMINAL_NODES:
                assert row["declared_edges"] == []
                assert row["terminal"] is True
                assert row["cells"] == []


@real_data
def test_real_undeclared_successors_stay_in_diagnostics(real_result):
    """Undeclared follow-ons must never appear as a cell anywhere."""
    for section in real_result["sections"]:
        for row in section["nodes"]:
            undeclared = set(row["undeclared_successors"])
            cell_targets = {c["successor_node"] for c in row["cells"]}
            assert not (undeclared & cell_targets)
            declared = set(row["declared_edges"])
            assert cell_targets <= declared
