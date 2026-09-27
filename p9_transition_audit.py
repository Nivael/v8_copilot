"""P9D transition-queue audit.

Declared-edge conditioned, deduplicated, fixed-horizon, right-censored audit of
observed stage transitions in the P8 event graph.

Why this module exists
----------------------
``possible_successors`` is an *allowed graph edge*, not an observed transition.
Node event counts (``node_counts``) are neither. Three quantities that are easy
to conflate must stay separate:

    node event count  >=  events carrying a declared edge  >=  observed transitions

The P9 panel must only show a successor *frequency* when a specific
``start node -> successor node`` cell clears the frozen sample gate on the
observable denominator. This module computes that, and is the regression
baseline for it: if a future change alters dedupe keys, edge conditioning,
horizon handling or right-censoring, these numbers move and the tests fail.

Read-only
---------
Every research database is opened with ``mode=ro``. The only write target is the
path passed to ``--output`` / ``--json``.

Contract version: ``p9_transition_audit_v1``
"""
from __future__ import annotations

import argparse
import bisect
import json
import sqlite3
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import settings

AUDIT_VERSION = "p9_transition_audit_v1"

#: Evidence tiers. Never merge these into one frequency table.
TIERS: tuple[str, ...] = ("deterministic_verified", "provisional", "title_derived")

#: Cell verdicts.
VERDICT_FREQUENCY = "frequency"
VERDICT_RAW_ONLY = "raw_points_only"
VERDICT_INSUFFICIENT = "sample_insufficient"
VERDICT_TERMINAL = "terminal_node_no_declared_successor"

#: Frozen sample gate (P8 PRD 3.3 / P9 PRD 6.1).
MIN_CELL_OBSERVATIONS = 8
MIN_CELL_COMPANIES = 5
MIN_RAW_OBSERVATIONS = 2

DEFAULT_HORIZON = 60
SENSITIVITY_HORIZON = 120

MAX_TEXT_CELLS = 400

#: How to treat an event whose ``available_as_of`` is not a trading day
#: (weekend / public holiday). Both policies are exposed because the choice is
#: not neutral: ``exclude`` drops the event from the risk set entirely, while
#: ``next_trading_day`` rolls it forward, which is the convention frozen in
#: P8 PRD 3.3 ("只有日期时统一使用下一交易日").
NONTRADING_EXCLUDE = "exclude"
NONTRADING_NEXT_TRADING_DAY = "next_trading_day"
NONTRADING_POLICIES = (NONTRADING_EXCLUDE, NONTRADING_NEXT_TRADING_DAY)


# --------------------------------------------------------------------------
# data loading
# --------------------------------------------------------------------------


@dataclass
class Event:
    """One deduplicated graph event."""

    symbol: str
    node: str
    available_as_of: str
    evidence_status: str
    declared: tuple[str, ...]
    trading_index: int | None = None


@dataclass
class Prepared:
    """Events deduplicated and pinned to a trading-day calendar."""

    events: list[Event]
    by_symbol: dict[str, list[Event]]
    calendar: list[str]
    duplicate_rows_removed: int
    total_rows: int
    off_calendar_events: int
    unresolved_events: int
    nontrading_policy: str

    @property
    def max_index(self) -> int:
        return len(self.calendar) - 1


def load_calendar(connection: sqlite3.Connection) -> list[str]:
    """Trading-day calendar, ascending, from the market activity store."""
    rows = connection.execute(
        "select distinct trade_date from market_activity_daily order by trade_date"
    ).fetchall()
    return [str(r[0]) for r in rows if r[0]]


def load_graph_events(connection: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    """Raw ``derived_event`` payloads for one event-graph run."""
    return [
        json.loads(row[0])
        for row in connection.execute(
            "select payload_json from p8_records "
            "where record_type = 'derived_event' and run_id = ?",
            (run_id,),
        )
    ]


def event_graph_run_id(manifest: Mapping[str, Any]) -> str:
    runs = manifest.get("run_ids_by_kind") or {}
    run_id = runs.get("event_graph")
    if not run_id:
        raise ValueError("manifest has no event_graph run id")
    return str(run_id)


def resolve_trading_index(
    day: str, calendar: Sequence[str], index: Mapping[str, int], policy: str
) -> int | None:
    """Map an event date to a trading-day index under the given policy.

    ``exclude`` returns ``None`` for a non-trading date (the event leaves the
    risk set). ``next_trading_day`` rolls forward to the first trading day on or
    after the date, per P8 PRD 3.3.
    """
    direct = index.get(day)
    if direct is not None:
        return direct
    if policy == NONTRADING_NEXT_TRADING_DAY:
        position = bisect.bisect_left(calendar, day)
        if position < len(calendar):
            return position
    return None


def prepare(
    raw_events: Iterable[Mapping[str, Any]],
    calendar: Sequence[str],
    nontrading_policy: str = NONTRADING_EXCLUDE,
) -> Prepared:
    """Deduplicate events and pin each to a trading-day index.

    Dedupe key is ``(symbol, node, available_as_of)``: repeated announcements for
    the same node on the same day are one observation, not several.
    """
    if nontrading_policy not in NONTRADING_POLICIES:
        raise ValueError(f"unknown non-trading policy: {nontrading_policy}")
    index = {day: i for i, day in enumerate(calendar)}
    seen: set[tuple[str, str, str]] = set()
    events: list[Event] = []
    total = 0
    removed = 0
    off_calendar = 0
    unresolved = 0
    for raw in raw_events:
        total += 1
        symbol = str(raw.get("symbol") or "")
        node = str(raw.get("node") or "")
        day = str(raw.get("available_as_of") or "")
        key = (symbol, node, day)
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        declared = tuple(sorted(str(s) for s in (raw.get("possible_successors") or [])))
        resolved = resolve_trading_index(day, calendar, index, nontrading_policy)
        if index.get(day) is None:
            off_calendar += 1
            if resolved is None:
                unresolved += 1
        event = Event(
            symbol=symbol,
            node=node,
            available_as_of=day,
            evidence_status=str(raw.get("evidence_status") or ""),
            declared=declared,
            trading_index=resolved,
        )
        events.append(event)
    by_symbol: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        if event.trading_index is not None:
            by_symbol[event.symbol].append(event)
    for bucket in by_symbol.values():
        bucket.sort(key=lambda e: e.trading_index or 0)
    return Prepared(
        events=events,
        by_symbol=dict(by_symbol),
        calendar=list(calendar),
        duplicate_rows_removed=removed,
        total_rows=total,
        off_calendar_events=off_calendar,
        unresolved_events=unresolved,
        nontrading_policy=nontrading_policy,
    )


# --------------------------------------------------------------------------
# audit
# --------------------------------------------------------------------------


@dataclass
class CellRow:
    """One ``start node -> successor node`` cell on the observable denominator."""

    start_node: str
    successor_node: str
    tier: str
    horizon: int
    # node-level risk set, repeated on every cell so a cell is self-describing
    risk_set_n: int
    censored_n: int
    observable_n: int
    observed_n: int
    companies: int
    median_gap: float | None
    p25_gap: float | None
    p75_gap: float | None
    frequency: float | None
    verdict: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "start_node": self.start_node,
            "successor_node": self.successor_node,
            "tier": self.tier,
            "horizon": self.horizon,
            "risk_set_n": self.risk_set_n,
            "censored_n": self.censored_n,
            "observable_n": self.observable_n,
            "observed_n": self.observed_n,
            "companies": self.companies,
            "median_gap": self.median_gap,
            "p25_gap": self.p25_gap,
            "p75_gap": self.p75_gap,
            #: Only ever set when verdict == frequency. N alone is never a frequency.
            "frequency": self.frequency,
            "verdict": self.verdict,
        }


@dataclass
class NodeRow:
    """Per start-node summary for one tier and horizon."""

    node: str
    tier: str
    horizon: int
    risk_set_n: int
    censored_n: int
    observable_n: int
    companies: int
    declared_edges: tuple[str, ...]
    terminal: bool
    #: Observed follow-on nodes outside the declared edge set. Diagnostics only.
    undeclared_successors: dict[str, int] = field(default_factory=dict)
    cells: list[CellRow] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "node": self.node,
            "tier": self.tier,
            "horizon": self.horizon,
            "risk_set_n": self.risk_set_n,
            "censored_n": self.censored_n,
            "observable_n": self.observable_n,
            "companies": self.companies,
            "declared_edges": list(self.declared_edges),
            "terminal": self.terminal,
            "undeclared_successors": dict(sorted(self.undeclared_successors.items())),
            "cells": [c.as_dict() for c in self.cells],
        }


def verdict_for(observed_n: int, companies: int) -> str:
    """Frozen sample gate. Applied to the *cell*, never to the start node alone."""
    if observed_n >= MIN_CELL_OBSERVATIONS and companies >= MIN_CELL_COMPANIES:
        return VERDICT_FREQUENCY
    if observed_n >= MIN_RAW_OBSERVATIONS:
        return VERDICT_RAW_ONLY
    return VERDICT_INSUFFICIENT


def _quartiles(values: list[int]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    if len(values) == 1:
        return float(values[0]), float(values[0])
    quartiles = statistics.quantiles(values, n=4)
    return quartiles[0], quartiles[2]


def first_successors(prepared: Prepared, start: Event, horizon: int) -> dict[str, Event]:
    """First event of each *other* node strictly after ``start`` within ``horizon``.

    Same-day multi-node disclosures are not transitions: the index comparison is
    strict. Repeats of the start node are excluded.
    """
    assert start.trading_index is not None
    window_end = start.trading_index + horizon
    found: dict[str, Event] = {}
    for candidate in prepared.by_symbol.get(start.symbol, []):
        index = candidate.trading_index
        if index is None or index <= start.trading_index:
            continue
        if index > window_end:
            break
        if candidate.node == start.node:
            continue
        found.setdefault(candidate.node, candidate)
    return found


def audit_node(
    prepared: Prepared, node: str, tier: str, horizon: int
) -> NodeRow | None:
    """Audit one start node under one evidence tier and horizon."""
    starts = [
        e
        for e in prepared.events
        if e.node == node and e.evidence_status == tier and e.trading_index is not None
    ]
    if not starts:
        return None

    risk_set_n = len(starts)
    censored_n = 0
    observable: list[Event] = []
    for event in starts:
        assert event.trading_index is not None
        if event.trading_index + horizon > prepared.max_index:
            censored_n += 1
        else:
            observable.append(event)

    # Declared edges are node-level constant in the frozen registry; assert it
    # rather than assume it, so a future per-event edge set cannot slip through.
    edge_sets = {e.declared for e in starts}
    declared_edges = next(iter(edge_sets)) if len(edge_sets) == 1 else tuple()
    consistent = len(edge_sets) == 1

    observed_counts: Counter[str] = Counter()
    company_sets: dict[str, set[str]] = defaultdict(set)
    gaps: dict[str, list[int]] = defaultdict(list)
    undeclared: Counter[str] = Counter()

    for event in observable:
        assert event.trading_index is not None
        successors = first_successors(prepared, event, horizon)
        for successor_node, successor in successors.items():
            if successor_node in event.declared:
                observed_counts[successor_node] += 1
                company_sets[successor_node].add(event.symbol)
                assert successor.trading_index is not None
                gaps[successor_node].append(successor.trading_index - event.trading_index)
            else:
                # Diagnostics only: never becomes a frequency cell.
                undeclared[successor_node] += 1

    cells: list[CellRow] = []
    for successor_node in sorted(observed_counts):
        observed_n = observed_counts[successor_node]
        companies = len(company_sets[successor_node])
        verdict = verdict_for(observed_n, companies)
        p25, p75 = _quartiles(gaps[successor_node])
        cells.append(
            CellRow(
                start_node=node,
                successor_node=successor_node,
                tier=tier,
                horizon=horizon,
                risk_set_n=risk_set_n,
                censored_n=censored_n,
                observable_n=len(observable),
                observed_n=observed_n,
                companies=companies,
                median_gap=(
                    float(statistics.median(gaps[successor_node]))
                    if gaps[successor_node]
                    else None
                ),
                p25_gap=p25,
                p75_gap=p75,
                frequency=(
                    observed_n / len(observable)
                    if verdict == VERDICT_FREQUENCY and observable
                    else None
                ),
                verdict=verdict,
            )
        )
    cells.sort(key=lambda c: (-c.observed_n, c.successor_node))

    terminal = not declared_edges and not cells
    if not consistent:
        terminal = False

    return NodeRow(
        node=node,
        tier=tier,
        horizon=horizon,
        risk_set_n=risk_set_n,
        censored_n=censored_n,
        observable_n=len(observable),
        companies=len({e.symbol for e in observable}),
        declared_edges=declared_edges,
        terminal=terminal,
        undeclared_successors=dict(undeclared),
        cells=cells,
    )


def audit(
    prepared: Prepared,
    tier: str,
    horizon: int = DEFAULT_HORIZON,
    nodes: Sequence[str] | None = None,
) -> list[NodeRow]:
    """Audit every start node (or the given subset) for one tier and horizon."""
    if tier not in TIERS:
        raise ValueError(f"unknown evidence tier: {tier}")
    universe = nodes or sorted({e.node for e in prepared.events})
    rows = [audit_node(prepared, node, tier, horizon) for node in universe]
    return [r for r in rows if r is not None]


def terminal_nodes(rows: Sequence[NodeRow]) -> list[str]:
    return sorted(r.node for r in rows if r.terminal)


def frequency_cells(rows: Sequence[NodeRow]) -> list[CellRow]:
    return [c for r in rows for c in r.cells if c.verdict == VERDICT_FREQUENCY]


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------


def render_text(result: Mapping[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"P9D transition audit  version={result['audit_version']}")
    lines.append(
        f"manifest={result['manifest_id']}  event_graph_run={result['event_graph_run']}"
    )
    lines.append(
        f"calendar={result['calendar_start']}..{result['calendar_end']} "
        f"({result['calendar_days']} trading days)"
    )
    lines.append(
        f"derived_event rows={result['total_rows']} "
        f"deduped={result['deduped_rows']} removed={result['duplicate_rows_removed']} "
        f"off_calendar={result['off_calendar_events']} "
        f"unresolved={result['unresolved_events']} "
        f"(non-trading policy={result['nontrading_policy']})"
    )
    lines.append(
        "gate: frequency requires observed_n >= "
        f"{result['gate']['min_observations']} and companies >= "
        f"{result['gate']['min_companies']}; "
        f"{result['gate']['min_raw_observations']}.."
        f"{result['gate']['min_observations'] - 1} -> raw points; "
        "0..1 -> insufficient"
    )

    for section in result["sections"]:
        lines.append("")
        lines.append("=" * 118)
        lines.append(
            f"tier={section['tier']}  horizon={section['horizon']} trading days"
        )
        lines.append("=" * 118)
        lines.append(
            f"{'start node':<38}{'risk':>6}{'cens':>6}{'observable':>11}{'co':>5}  note"
        )
        for row in section["nodes"]:
            note = "TERMINAL (no declared successor)" if row["terminal"] else ""
            lines.append(
                f"{row['node']:<38}{row['risk_set_n']:>6}{row['censored_n']:>6}"
                f"{row['observable_n']:>11}{row['companies']:>5}  {note}"
            )
        lines.append("")
        lines.append(
            f"{'start -> successor':<64}{'obs':>4}{'co':>4}{'denom':>7}"
            f"{'freq':>8}  {'verdict':<20} median gap (P25-P75)"
        )
        shown = 0
        for row in section["nodes"]:
            for cell in row["cells"]:
                if shown >= MAX_TEXT_CELLS:
                    lines.append("  ... truncated")
                    break
                shown += 1
                freq = (
                    f"{cell['frequency'] * 100:.1f}%"
                    if cell["frequency"] is not None
                    else "—"
                )
                gap = (
                    f"{cell['median_gap']:.0f} "
                    f"({cell['p25_gap']:.0f}-{cell['p75_gap']:.0f})"
                    if cell["median_gap"] is not None
                    else ""
                )
                lines.append(
                    f"{(cell['start_node'] + ' -> ' + cell['successor_node']):<64}"
                    f"{cell['observed_n']:>4}{cell['companies']:>4}"
                    f"{cell['observable_n']:>7}{freq:>8}  {cell['verdict']:<20} {gap}"
                )
        undeclared: Counter[str] = Counter()
        for row in section["nodes"]:
            undeclared.update(row["undeclared_successors"])
        if undeclared:
            lines.append("")
            lines.append(
                "  [diagnostics] observed follow-ons OUTSIDE the declared edge set "
                "(never a frequency):"
            )
            lines.append(f"    {dict(undeclared.most_common(12))}")
        terminals = [r["node"] for r in section["nodes"] if r["terminal"]]
        if terminals:
            lines.append("")
            lines.append(
                "  [terminal nodes] declared edge set is empty; must not render "
                f"as 0% successor frequency: {terminals}"
            )
    return "\n".join(lines) + "\n"


def run_audit(
    *,
    research_db: Path,
    activity_db: Path,
    manifest: Mapping[str, Any],
    tiers: Sequence[str] = TIERS,
    horizons: Sequence[int] = (DEFAULT_HORIZON, SENSITIVITY_HORIZON),
    nontrading_policy: str = NONTRADING_EXCLUDE,
) -> dict[str, Any]:
    """Full audit against the databases. Read-only."""
    run_id = event_graph_run_id(manifest)
    with sqlite3.connect(f"file:{research_db}?mode=ro", uri=True) as research:
        raw = load_graph_events(research, run_id)
    with sqlite3.connect(f"file:{activity_db}?mode=ro", uri=True) as activity:
        calendar = load_calendar(activity)
    if not calendar:
        raise ValueError("empty trading calendar")
    prepared = prepare(raw, calendar, nontrading_policy)

    sections = []
    for horizon in horizons:
        for tier in tiers:
            rows = audit(prepared, tier, horizon)
            if not rows:
                continue
            sections.append(
                {
                    "tier": tier,
                    "horizon": horizon,
                    "nodes": [r.as_dict() for r in rows],
                }
            )

    return {
        "audit_version": AUDIT_VERSION,
        "manifest_id": str(manifest.get("manifest_id") or ""),
        "manifest_through": str(manifest.get("through") or ""),
        "event_graph_run": run_id,
        "calendar_start": prepared.calendar[0],
        "calendar_end": prepared.calendar[-1],
        "calendar_days": len(prepared.calendar),
        "total_rows": prepared.total_rows,
        "deduped_rows": len(prepared.events),
        "duplicate_rows_removed": prepared.duplicate_rows_removed,
        "nontrading_policy": prepared.nontrading_policy,
        "off_calendar_events": prepared.off_calendar_events,
        "unresolved_events": prepared.unresolved_events,
        "gate": {
            "min_observations": MIN_CELL_OBSERVATIONS,
            "min_companies": MIN_CELL_COMPANIES,
            "min_raw_observations": MIN_RAW_OBSERVATIONS,
        },
        "sections": sections,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--research-db", type=Path, default=settings.P8_RESEARCH_DB)
    parser.add_argument(
        "--activity-db", type=Path, default=settings.MARKET_ACTIVITY_DB
    )
    parser.add_argument(
        "--manifest", type=Path, default=settings.P8_RESEARCH_MANIFEST_PATH
    )
    parser.add_argument("--horizon", type=int, action="append", default=None)
    parser.add_argument("--tier", action="append", default=None)
    parser.add_argument(
        "--nontrading",
        choices=NONTRADING_POLICIES,
        default=NONTRADING_EXCLUDE,
        help=(
            "how to treat events dated on a non-trading day: "
            "'exclude' drops them from the risk set (baseline), "
            "'next_trading_day' rolls them forward per P8 PRD 3.3"
        ),
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = run_audit(
        research_db=args.research_db,
        activity_db=args.activity_db,
        manifest=manifest,
        tiers=tuple(args.tier) if args.tier else TIERS,
        horizons=tuple(args.horizon) if args.horizon else (DEFAULT_HORIZON,),
        nontrading_policy=args.nontrading,
    )
    text = render_text(result)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    if args.json:
        args.json.write_text(
            json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
