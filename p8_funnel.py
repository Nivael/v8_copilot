"""P8D quota-lane research funnel without an additive opportunity score."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from p8_research import P8ResearchRepository, build_run, content_id
from settings import P8_RESEARCH_DB


CONTRACT_VERSION = "p8_research_funnel_v1"
LANE_QUOTAS = {
    "event_frontier": 6,
    "scenario_tension": 5,
    "persistent_activity": 5,
    "chip_or_exploration": 4,
}
MAX_ITEMS = 20


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResearchCheck(StrictModel):
    check_id: Literal[
        "official_evidence", "stage_frontier", "scenario_reference",
        "capital_structure_and_risk", "market_activity_context",
    ]
    status: Literal["ready", "gap", "not_applicable", "unavailable"]
    detail: str


class FunnelItem(StrictModel):
    item_id: str = Field(pattern=r"^P8FI-[A-F0-9]{20}$")
    symbol: str = Field(pattern=r"^\d{6}$")
    as_of: str
    primary_lane: Literal[
        "event_frontier", "scenario_tension", "persistent_activity", "chip_or_exploration"
    ]
    matched_lanes: list[str]
    lane_rank: int = Field(ge=1)
    reasons: list[str]
    checks: list[ResearchCheck]
    source_ids: list[str]
    data_gaps: list[str]
    risk_flags: list[str]
    owner_review_status: Literal["unreviewed"] = "unreviewed"
    available_actions: list[Literal["keep", "drop", "unknown"]] = Field(
        default_factory=lambda: ["keep", "drop", "unknown"]
    )
    not_a_trading_signal: Literal[True] = True


class FunnelResult(StrictModel):
    run_id: str
    as_of: str
    item_count: int
    overflow_count: int
    lane_counts: dict[str, int]
    multi_lane_count: int
    human_actions_required: int
    source_run_ids: list[str]
    items: list[FunnelItem]


def _days_between(left: str, right: str) -> int:
    return (date.fromisoformat(right) - date.fromisoformat(left)).days


def _latest_by_symbol(items: list[dict[str, Any]], date_field: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        symbol = str(item.get("symbol") or "")
        key = (str(item.get(date_field) or ""), str(item.get("event_id") or item.get("feature_id") or ""))
        previous = result.get(symbol)
        previous_key = (
            str(previous.get(date_field) or ""),
            str(previous.get("event_id") or previous.get("feature_id") or ""),
        ) if previous else ("", "")
        if key > previous_key:
            result[symbol] = item
    return result


def _event_lane(events: list[dict[str, Any]], *, as_of: str) -> list[dict[str, Any]]:
    latest = _latest_by_symbol(events, "available_as_of")
    evidence_rank = {
        "body_verified": 0, "deterministic_verified": 1,
        "provisional": 2, "title_derived": 3,
    }
    candidates = [
        item for item in latest.values()
        if 0 <= _days_between(str(item["available_as_of"]), as_of) <= 60
        and (item.get("possible_successors") or item.get("failure_successors"))
    ]
    return sorted(candidates, key=lambda item: (
        evidence_rank.get(str(item.get("evidence_status")), 9),
        _days_between(str(item["available_as_of"]), as_of),
        str(item["symbol"]),
    ))


def _scenario_lane(references: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # v1 only admits same-claim exact old-equity points. Empty is the safe expected result today.
    candidates = [
        item for item in references
        if item.get("value_status") == "exact_old_equity"
        and item.get("old_equity_value") is not None
        and not item.get("contamination_flags")
    ]
    return sorted(candidates, key=lambda item: (
        str(item.get("available_as_of") or ""), str(item.get("symbol") or "")
    ), reverse=True)


def _activity_lane(features: list[dict[str, Any]], *, as_of: str) -> list[dict[str, Any]]:
    current = [item for item in features if str(item.get("trade_date") or "") == as_of]
    label_rank = {
        "persistent_activity_price_stable": 0,
        "persistent_activity_price_down": 1,
        "single_day_activity_price_jump": 2,
    }
    candidates = [item for item in current if str(item.get("shape_label") or "") in label_rank]
    return sorted(candidates, key=lambda item: (
        label_rank[str(item["shape_label"])],
        -float(item.get("cum_turnover_log_excess_20") or 0),
        str(item["symbol"]),
    ))


def _exploration_lane(
    event_candidates: list[dict[str, Any]], activity_candidates: list[dict[str, Any]],
    chip_proxies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    activity_by_symbol = {str(item["symbol"]): item for item in activity_candidates}
    event_by_symbol = {str(item["symbol"]): item for item in event_candidates}
    notable_chip = {
        str(item["symbol"]): item for item in chip_proxies
        if item.get("top_list_status") == "triggered"
        or item.get("top_institution_status") == "reported"
        or item.get("block_trade_status") == "reported"
        or (
            item.get("holder_change_pct") is not None
            and float(item["holder_change_pct"]) <= -0.10
        )
    }
    symbols = sorted(
        ({*event_by_symbol} & {*activity_by_symbol}) | set(notable_chip)
    )
    return [{
        "symbol": symbol,
        "event": event_by_symbol.get(symbol),
        "activity": activity_by_symbol.get(symbol),
        "chip": notable_chip.get(symbol),
    } for symbol in symbols]


def _checks(
    *, symbol: str, event: dict[str, Any] | None,
    activity: dict[str, Any] | None, reference: dict[str, Any] | None,
    chip: dict[str, Any] | None,
) -> tuple[list[ResearchCheck], list[str], list[str]]:
    gaps: list[str] = []
    risks: list[str] = []
    event_status = str((event or {}).get("evidence_status") or "")
    if event is None:
        official = ResearchCheck(check_id="official_evidence", status="not_applicable", detail="本条不由公告前沿触发。")
    elif event_status in {"body_verified", "deterministic_verified"}:
        official = ResearchCheck(check_id="official_evidence", status="ready", detail="已有可回链核证事件。")
    else:
        official = ResearchCheck(check_id="official_evidence", status="gap", detail=f"事件证据仍为 {event_status or 'unknown'}。")
        gaps.append("event_body_or_verification_gap")
    frontier = ResearchCheck(
        check_id="stage_frontier",
        status="ready" if event and event.get("possible_successors") else "gap",
        detail=(
            "下一可能节点：" + "、".join(event.get("possible_successors") or [])
            if event else "未连接到已核证程序前沿。"
        ),
    )
    if frontier.status == "gap":
        gaps.append("stage_frontier_gap")
    if reference and reference.get("value_status") == "exact_old_equity":
        scenario = ResearchCheck(check_id="scenario_reference", status="ready", detail="存在同旧股东权益口径参考。")
    elif reference:
        scenario = ResearchCheck(check_id="scenario_reference", status="gap", detail="只有总市值或原始条款，旧股东权益口径未闭合。")
        gaps.append("old_equity_reference_gap")
    else:
        scenario = ResearchCheck(check_id="scenario_reference", status="unavailable", detail="本公司暂无可用情景参考。")
        gaps.append("scenario_reference_unavailable")
    contamination = list((reference or {}).get("contamination_flags") or [])
    if contamination:
        risks.extend(contamination)
    capital = ResearchCheck(
        check_id="capital_structure_and_risk",
        status="gap" if contamination else "unavailable",
        detail="；".join(contamination) if contamination else "旧股东让渡、转增或未知负债仍需在深挖时核对。",
    )
    if activity or chip:
        details = []
        if activity:
            details.append(str(activity.get("shape_label") or "可观察活动特征已计算"))
        if chip:
            details.append(
                "公开筹码旁证："
                + "/".join(str(chip.get(key) or "unknown") for key in (
                    "holder_status", "top_list_status", "block_trade_status", "margin_status",
                ))
            )
        market = ResearchCheck(
            check_id="market_activity_context", status="ready",
            detail="；".join(details),
        )
    else:
        market = ResearchCheck(check_id="market_activity_context", status="not_applicable", detail="本条没有当日持续型活动命中。")
    return [official, frontier, scenario, capital, market], sorted(set(gaps)), sorted(set(risks))


def build_funnel(
    *, repository: P8ResearchRepository, as_of: str,
) -> tuple[list[FunnelItem], int, list[str]]:
    event_run = repository.latest_run("event_graph")
    activity_run = repository.latest_run("activity_features")
    reference_run = repository.latest_run("scenario_references")
    chip_run = repository.latest_run("chip_proxies")
    if event_run is None or activity_run is None:
        raise ValueError("P8D 需要 event_graph 与 activity_features")
    events = repository.records(run_id=event_run.run_id, record_type="derived_event")
    features = repository.records(run_id=activity_run.run_id, record_type="activity_feature")
    references = (
        repository.records(run_id=reference_run.run_id, record_type="scenario_reference")
        if reference_run else []
    )
    chip_proxies = (
        repository.records(run_id=chip_run.run_id, record_type="chip_proxy")
        if chip_run else []
    )
    event_candidates = _event_lane(events, as_of=as_of)
    scenario_candidates = _scenario_lane(references)
    activity_candidates = _activity_lane(features, as_of=as_of)
    exploration_candidates = _exploration_lane(
        event_candidates, activity_candidates, chip_proxies,
    )

    event_by_symbol = _latest_by_symbol(events, "available_as_of")
    activity_by_symbol = {str(item["symbol"]): item for item in activity_candidates}
    reference_by_symbol = _latest_by_symbol(references, "available_as_of")
    chip_by_symbol = _latest_by_symbol(chip_proxies, "available_as_of")
    lanes: dict[str, list[dict[str, Any]]] = {
        "event_frontier": event_candidates,
        "scenario_tension": scenario_candidates,
        "persistent_activity": activity_candidates,
        "chip_or_exploration": exploration_candidates,
    }
    lane_symbols = {
        lane: [str(item.get("symbol") or "") for item in rows]
        for lane, rows in lanes.items()
    }
    memberships: dict[str, list[str]] = defaultdict(list)
    for lane, symbols in lane_symbols.items():
        for symbol in symbols:
            memberships[symbol].append(lane)

    selected: list[tuple[str, int, str]] = []
    selected_symbols: set[str] = set()
    overflow_symbols: set[str] = set()
    lane_order = list(LANE_QUOTAS)
    for lane in lane_order:
        ranked = lane_symbols[lane]
        ranked = sorted(
            enumerate(ranked, start=1),
            key=lambda pair: (-len(memberships[pair[1]]), pair[0], pair[1]),
        )
        admitted = 0
        for rank, symbol in ranked:
            if symbol in selected_symbols:
                continue
            if admitted >= LANE_QUOTAS[lane] or len(selected) >= MAX_ITEMS:
                overflow_symbols.add(symbol)
                continue
            selected.append((lane, rank, symbol))
            selected_symbols.add(symbol)
            admitted += 1

    items: list[FunnelItem] = []
    for lane, rank, symbol in selected:
        event = event_by_symbol.get(symbol)
        activity = activity_by_symbol.get(symbol)
        reference = reference_by_symbol.get(symbol)
        chip = chip_by_symbol.get(symbol)
        checks, gaps, risks = _checks(
            symbol=symbol, event=event, activity=activity, reference=reference,
            chip=chip,
        )
        reasons = []
        if lane == "event_frontier" and event:
            reasons.append(f"程序前沿为 {event.get('node')}，存在已登记后继或失败分支。")
        elif lane == "scenario_tension" and reference:
            reasons.append("存在同口径旧股东权益情景参考；只进入研究，不构成便宜/昂贵判断。")
        elif lane == "persistent_activity" and activity:
            reasons.extend(list(activity.get("shape_reasons") or [str(activity.get("shape_label"))]))
        else:
            if chip:
                reasons.append("出现公开筹码旁证或与公告/量价通道重合，优先补证；不解释为资金方向。")
            else:
                reasons.append("公告程序前沿与当日持续型活动同时出现，优先补证。")
        source_ids = sorted(set(
            list((event or {}).get("source_ids") or [])
            + list((reference or {}).get("source_ids") or [])
            + ([str((activity or {}).get("feature_id"))] if activity else [])
            + ([str((chip or {}).get("record_id"))] if chip else [])
        ))
        identity = {
            "contract": CONTRACT_VERSION, "as_of": as_of, "symbol": symbol,
            "primary_lane": lane, "matched_lanes": sorted(memberships[symbol]),
            "source_ids": source_ids,
        }
        items.append(FunnelItem(
            item_id=content_id("P8FI", identity),
            symbol=symbol, as_of=as_of, primary_lane=lane,  # type: ignore[arg-type]
            matched_lanes=sorted(memberships[symbol]), lane_rank=rank,
            reasons=reasons, checks=checks, source_ids=source_ids,
            data_gaps=gaps, risk_flags=risks,
        ))
    return items, len(overflow_symbols - selected_symbols), [
        item.run_id for item in (event_run, activity_run, reference_run, chip_run) if item
    ]


def materialize_funnel(
    *, repository: P8ResearchRepository, as_of: str,
) -> FunnelResult:
    items, overflow, source_run_ids = build_funnel(repository=repository, as_of=as_of)
    records = {"funnel_item": [
        {**item.model_dump(mode="json"), "record_id": item.item_id, "available_as_of": item.as_of}
        for item in items
    ]}
    run = build_run(
        run_kind="funnel", contract_version=CONTRACT_VERSION,
        start_date=as_of, through=as_of,
        source_run_ids=source_run_ids,
        source_digests={
            "source_run_set": hashlib.sha256("|".join(source_run_ids).encode()).hexdigest()
        },
        record_payloads=records,
    )
    repository.persist(run=run, records=records)
    return FunnelResult(
        run_id=run.run_id, as_of=as_of,
        item_count=len(items), overflow_count=overflow,
        lane_counts=dict(sorted(Counter(item.primary_lane for item in items).items())),
        multi_lane_count=sum(len(item.matched_lanes) > 1 for item in items),
        human_actions_required=0,
        source_run_ids=source_run_ids,
        items=items,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--repository", type=Path, default=P8_RESEARCH_DB)
    parser.add_argument("--output-json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = materialize_funnel(
        repository=P8ResearchRepository(args.repository), as_of=args.as_of,
    )
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(result.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
