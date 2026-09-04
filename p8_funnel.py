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


CONTRACT_VERSION = "p8_research_funnel_v2"
LANE_QUOTAS = {
    "event_frontier": 6,
    "scenario_tension": 5,
    # P8-BT2 killed this lane under both terminal conventions. Keep its
    # feature/overflow ledger, but do not promote it into the post-result funnel.
    "persistent_activity": 0,
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
    lane_status: dict[str, str]
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


def _current_episode_events(
    events: list[dict[str, Any]], frontiers: list[dict[str, Any]], *,
    current_symbols: set[str], as_of: str,
) -> list[dict[str, Any]]:
    membership_starts = {
        str(item.get("symbol") or ""): str(item.get("membership_start_date") or "")
        for item in frontiers
    }
    missing = sorted(current_symbols - set(membership_starts))
    if missing:
        raise ValueError(f"P8D current membership 缺 frontier: {missing[:5]}")
    return [
        item for item in events
        if str(item.get("symbol") or "") in current_symbols
        and membership_starts.get(str(item.get("symbol") or ""), "")
        <= str(item.get("available_as_of") or "") <= as_of
    ]


def _scenario_lane(current_maps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Only same-claim distributions with a pre-registered tail position can enter this lane.
    candidates = [
        item for item in current_maps
        if item.get("reference_status") == "distribution"
        and item.get("position_pct_in_layer") is not None
        and (
            float(item["position_pct_in_layer"]) <= 0.10
            or float(item["position_pct_in_layer"]) >= 0.90
        )
        and item.get("current_old_equity_value") is not None
    ]
    ranked = sorted(candidates, key=lambda item: (
        min(float(item["position_pct_in_layer"]), 1 - float(item["position_pct_in_layer"])),
        str(item.get("symbol") or ""), str(item.get("reference_family") or ""),
    ))
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in ranked:
        symbol = str(item.get("symbol") or "")
        if symbol not in seen:
            result.append(item)
            seen.add(symbol)
    return result


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


def _persistent_activity_lane(
    daily_candidates: list[dict[str, Any]], *, same_day_event_symbols: set[str],
) -> list[dict[str, Any]]:
    persistent_labels = {
        "persistent_activity_price_stable", "persistent_activity_price_down",
    }
    return [
        item for item in daily_candidates
        if str(item.get("shape_label") or "") in persistent_labels
        and not bool(item.get("single_day_strict_input"))
        and str(item.get("symbol") or "") not in same_day_event_symbols
    ]


def _verified_event_lane(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Only promote nodes whose meaning is verified beyond the announcement title."""
    allowed = {"body_verified", "deterministic_verified"}
    return [
        item for item in rows
        if str(item.get("evidence_status") or "") in allowed
    ]


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
    symbols = ({*event_by_symbol} & {*activity_by_symbol}) | set(notable_chip)
    rows = [{
        "symbol": symbol,
        "event": event_by_symbol.get(symbol),
        "activity": activity_by_symbol.get(symbol),
        "chip": notable_chip.get(symbol),
    } for symbol in symbols]
    return sorted(rows, key=_exploration_priority)


def _exploration_priority(item: dict[str, Any]) -> tuple[Any, ...]:
    """Frozen, outcome-blind ordering for the exploration quota."""

    chip = item.get("chip") or {}
    channel_count = sum(bool(item.get(key)) for key in ("event", "activity", "chip"))
    discrete_public_fact_count = sum((
        chip.get("top_list_status") == "triggered",
        chip.get("top_institution_status") == "reported",
        chip.get("block_trade_status") == "reported",
    ))
    disclosure_date = str(chip.get("holder_latest_announcement_date") or "").replace("-", "")
    disclosure_rank = -int(disclosure_date) if disclosure_date.isdigit() else 0
    holder_change = chip.get("holder_change_pct")
    holder_change_rank = float(holder_change) if holder_change is not None else 0.0
    return (
        -channel_count,
        -discrete_public_fact_count,
        disclosure_rank,
        holder_change_rank,
        str(item.get("symbol") or ""),
    )


def _checks(
    *, symbol: str, event: dict[str, Any] | None,
    activity: dict[str, Any] | None, scenario_maps: list[dict[str, Any]],
    chip: dict[str, Any] | None,
) -> tuple[list[ResearchCheck], list[str], list[str]]:
    gaps: list[str] = []
    risks: list[str] = []
    event_status = str((event or {}).get("evidence_status") or "")
    if event is None:
        official = ResearchCheck(check_id="official_evidence", status="not_applicable", detail="本条不由公告前沿触发。")
    elif event_status in {"body_verified", "deterministic_verified"}:
        excerpt = str(((event.get("source_spans") or [{}])[0]).get("excerpt") or "")[:80]
        official = ResearchCheck(
            check_id="official_evidence", status="ready",
            detail=f"{event.get('available_as_of')} 已核证 {event.get('node')}：{excerpt or '来源可回链'}",
        )
    else:
        official = ResearchCheck(
            check_id="official_evidence", status="gap",
            detail=(
                f"{event.get('available_as_of')} 的 {event.get('node')} 仍为 "
                f"{event_status or 'unknown'}，正文摘要不进入正式结论。"
            ),
        )
        gaps.append("event_body_or_verification_gap")
    primary_map = next(
        (item for item in scenario_maps if item.get("reference_family") == "public_node_reference"),
        scenario_maps[0] if scenario_maps else None,
    )
    current_stage = str((primary_map or {}).get("stage") or "unknown")
    stage_source = str((primary_map or {}).get("stage_source") or "unknown")
    successors = list((event or {}).get("possible_successors") or (primary_map or {}).get("next_possible_successors") or [])
    gap_days = (primary_map or {}).get("days_since_last_verified_node")
    frontier = ResearchCheck(
        check_id="stage_frontier",
        status="ready" if current_stage != "unknown" and successors else "gap",
        detail=(
            f"当前阶段 {current_stage}（{stage_source}）；下一可能节点："
            + ("、".join(successors) if successors else "unknown")
            + (f"；距最近核证节点 {gap_days} 天" if gap_days is not None else "")
        ),
    )
    if frontier.status == "gap":
        gaps.append("stage_frontier_gap")
    distributions = [item for item in scenario_maps if item.get("reference_status") == "distribution"]
    if distributions:
        scenario = ResearchCheck(
            check_id="scenario_reference", status="ready",
            detail="；".join(
                f"{item.get('reference_family')} n={item.get('reference_n')} "
                f"位置={item.get('position_pct_in_layer')}"
                for item in distributions
            ),
        )
    elif scenario_maps:
        scenario = ResearchCheck(
            check_id="scenario_reference", status="gap",
            detail="三类参考均因同口径样本不足只保留原始点或空结果。",
        )
        gaps.append("old_equity_reference_gap")
    else:
        scenario = ResearchCheck(check_id="scenario_reference", status="unavailable", detail="当前 ST 全量情景地图缺失。")
        gaps.append("scenario_reference_unavailable")
    map_gaps = sorted({gap for item in scenario_maps for gap in (item.get("data_gaps") or [])})
    risks.extend(gap for gap in map_gaps if "capital" in gap or "risk" in gap)
    p_star = next((item.get("scenario_implied_weight") for item in scenario_maps if item.get("scenario_implied_weight") is not None), None)
    cross_sensitivity = next((
        item.get("cross_company_sensitivity_weight") for item in scenario_maps
        if item.get("cross_company_sensitivity_weight") is not None
    ), None)
    par_distance = (primary_map or {}).get("distance_to_par_delisting_pct")
    mv_distance = (primary_map or {}).get("distance_to_mv_delisting_pct")
    capital = ResearchCheck(
        check_id="capital_structure_and_risk",
        status="ready" if p_star is not None and mv_distance is not None else "gap",
        detail=(
            f"p*={p_star if p_star is not None else 'unknown'}；"
            f"跨公司情景敏感性={cross_sensitivity if cross_sensitivity is not None else 'unknown'}；"
            f"距一元参考={f'{float(par_distance):.1%}' if par_distance is not None else 'unknown'}；"
            f"距市值退市参考={f'{float(mv_distance):.1%}' if mv_distance is not None else 'unknown'}。"
        ),
    )
    if capital.status == "gap":
        gaps.extend(map_gaps or ["capital_structure_or_risk_gap"])
    if activity or chip:
        details = []
        if activity:
            details.append(str(activity.get("shape_label") or "可观察活动特征已计算"))
        if chip:
            holder_change = chip.get("holder_change_pct")
            holder_detail = (
                f"股东户数较前次 {float(holder_change):+.1%}"
                f"（披露 {chip.get('holder_latest_announcement_date') or '日期未知'}）"
                if holder_change is not None else "股东户数变化 unknown"
            )
            details.append(
                "公开筹码旁证："
                + "/".join(str(chip.get(key) or "unknown") for key in (
                    "holder_status", "top_list_status", "block_trade_status", "margin_status",
                ))
                + f"；{holder_detail}"
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
    frontiers = repository.records(run_id=event_run.run_id, record_type="company_frontier")
    features = repository.records(run_id=activity_run.run_id, record_type="activity_feature")
    current_maps = (
        repository.records(run_id=reference_run.run_id, record_type="current_scenario_map")
        if reference_run else []
    )
    chip_proxies = (
        repository.records(run_id=chip_run.run_id, record_type="chip_proxy")
        if chip_run else []
    )
    current_symbols = {str(item.get("symbol") or "") for item in current_maps}
    if not current_symbols:
        raise ValueError("P8D 缺少 current_scenario_map；拒绝在未限定当日 ST 成员时生成漏斗")
    current_events = _current_episode_events(
        events, frontiers, current_symbols=current_symbols, as_of=as_of,
    )
    recent_event_candidates = _event_lane(current_events, as_of=as_of)
    event_candidates = _verified_event_lane(recent_event_candidates)
    scenario_candidates = _scenario_lane(current_maps)
    daily_activity_candidates = [
        item for item in _activity_lane(features, as_of=as_of)
        if str(item.get("symbol") or "") in current_symbols
    ]
    same_day_event_symbols = {
        str(item.get("symbol") or "") for item in current_events
        if str(item.get("available_as_of") or "") == as_of
    }
    activity_candidates = _persistent_activity_lane(
        daily_activity_candidates, same_day_event_symbols=same_day_event_symbols,
    )
    exploration_candidates = _exploration_lane(
        recent_event_candidates, daily_activity_candidates, chip_proxies,
    )

    event_by_symbol = _latest_by_symbol(current_events, "available_as_of")
    activity_by_symbol = {str(item["symbol"]): item for item in daily_activity_candidates}
    maps_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in current_maps:
        maps_by_symbol[str(item.get("symbol") or "")].append(item)
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
        symbol_maps = maps_by_symbol.get(symbol, [])
        chip = chip_by_symbol.get(symbol)
        checks, gaps, risks = _checks(
            symbol=symbol, event=event, activity=activity, scenario_maps=symbol_maps,
            chip=chip,
        )
        reasons = []
        if lane == "event_frontier" and event:
            reasons.append(f"程序前沿为 {event.get('node')}，存在已登记后继或失败分支。")
        elif lane == "scenario_tension" and symbol_maps:
            reasons.append("存在同口径旧股东权益情景参考；只进入研究，不构成便宜/昂贵判断。")
        elif lane == "persistent_activity" and activity:
            reasons.extend(list(activity.get("shape_reasons") or [str(activity.get("shape_label"))]))
        else:
            overlap = [
                label for present, label in (
                    (event, "近 30 日公告待核证节点"),
                    (activity, "当日量价形态"),
                    (chip, "公开筹码旁证"),
                ) if present
            ]
            if len(overlap) >= 2:
                reasons.append("与".join(overlap) + "重合，优先补证；不解释为消息资金。")
            if chip:
                public_facts = []
                if chip.get("top_list_status") == "triggered":
                    public_facts.append("龙虎榜")
                if chip.get("top_institution_status") == "reported":
                    public_facts.append("机构席位")
                if chip.get("block_trade_status") == "reported":
                    public_facts.append("大宗交易")
                holder_change = chip.get("holder_change_pct")
                if holder_change is not None and float(holder_change) <= -0.10:
                    public_facts.append(
                        f"股东户数较前次 {float(holder_change):+.1%}"
                        f"（披露 {chip.get('holder_latest_announcement_date') or '日期未知'}）"
                    )
                if public_facts:
                    reasons.append(
                        "新增公开旁证：" + "、".join(public_facts)
                        + "；仅描述公开筹码变化，不推断资金身份或方向。"
                    )
            if not reasons:
                reasons.append("公告程序前沿与当日持续型活动同时出现，优先补证。")
        source_ids = sorted(set(
            list((event or {}).get("source_ids") or [])
            + [source_id for item in symbol_maps for source_id in (item.get("source_ids") or [])]
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
        lane_status={
            "event_frontier": "unavailable_pending_body_validation",
            "scenario_tension": "unavailable_same_claim_inputs_absent",
            "persistent_activity": "killed_by_p8_backtest_v2",
            "chip_or_exploration": "weak_unweighted_context_only",
        },
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
