"""Validate a coherent P8 run set and explicitly publish its current manifest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from p8_research import P8ResearchRepository, publish_manifest
from settings import P8_RESEARCH_DB, P8_RESEARCH_MANIFEST_PATH


REQUIRED_KINDS = (
    "event_graph", "activity_features", "return_paths", "scenario_references",
    "chip_proxies", "funnel", "portfolio", "backtest",
)


def build_status(repository: P8ResearchRepository, *, as_of: str) -> tuple[dict, list]:
    runs = [repository.latest_run(kind) for kind in REQUIRED_KINDS]
    missing = [kind for kind, run in zip(REQUIRED_KINDS, runs, strict=True) if run is None]
    if missing:
        raise ValueError(f"缺少 P8 materialization: {missing}")
    complete = [run for run in runs if run is not None]
    stale = {run.run_kind: run.through for run in complete if run.through != as_of}
    if stale:
        raise ValueError(f"P8 run 未对齐 as_of={as_of}: {stale}")

    event_run = next(run for run in complete if run.run_kind == "event_graph")
    return_run = next(run for run in complete if run.run_kind == "return_paths")
    reference_run = next(run for run in complete if run.run_kind == "scenario_references")
    funnel_run = next(run for run in complete if run.run_kind == "funnel")
    portfolio_run = next(run for run in complete if run.run_kind == "portfolio")
    events = repository.records(run_id=event_run.run_id, record_type="derived_event")
    frontiers = repository.records(run_id=event_run.run_id, record_type="company_frontier")
    extractions = repository.records(run_id=event_run.run_id, record_type="llm_announcement_extraction")
    returns = repository.records(run_id=return_run.run_id, record_type="return_path")
    references = repository.records(run_id=reference_run.run_id, record_type="scenario_reference")
    current_maps = repository.records(run_id=reference_run.run_id, record_type="current_scenario_map")
    funnel = repository.records(run_id=funnel_run.run_id, record_type="funnel_item")
    portfolios = repository.records(run_id=portfolio_run.run_id, record_type="portfolio_summary")
    forward_shadow_days = (
        len(set(portfolios[-1].get("source_funnel_run_ids") or [])) if portfolios else 0
    )
    body_verified = sum(item.get("evidence_status") == "body_verified" for item in events)
    exact_equity = sum(item.get("value_status") == "exact_old_equity" for item in references)
    p_star_count = sum(item.get("scenario_implied_weight") is not None for item in current_maps)
    frontier_symbols = {str(item.get("symbol") or "") for item in frontiers}
    map_symbols = {str(item.get("symbol") or "") for item in current_maps}
    families_by_symbol = {
        symbol: {
            str(item.get("reference_family") or "")
            for item in current_maps if item.get("symbol") == symbol
        }
        for symbol in map_symbols
    }
    map_counts_by_symbol = {
        symbol: sum(str(item.get("symbol") or "") == symbol for item in current_maps)
        for symbol in map_symbols
    }
    incomplete_maps = [
        symbol for symbol, families in families_by_symbol.items()
        if len(families) != 3 or map_counts_by_symbol[symbol] != 3
    ]
    duplicate_frontiers = len(frontiers) != len(frontier_symbols)
    wrong_dates = [
        str(item.get("record_id") or "")
        for item in [*frontiers, *current_maps]
        if str(item.get("available_as_of") or "") != as_of
    ]
    if (
        not frontier_symbols or frontier_symbols != map_symbols or incomplete_maps
        or duplicate_frontiers or wrong_dates
    ):
        raise ValueError(
            "P8 current cohort 不闭合："
            f"frontier={len(frontier_symbols)}, map={len(map_symbols)}, "
            f"incomplete_three_family={len(incomplete_maps)}, "
            f"duplicate_frontiers={duplicate_frontiers}, wrong_dates={len(wrong_dates)}"
        )
    status = {
        "as_of": as_of,
        "run_ids_by_kind": {run.run_kind: run.run_id for run in complete},
        "capabilities": {
            "event_graph": "available",
            "body_llm_extraction": "available" if extractions else "authorization_pending",
            "body_verified_events": body_verified,
            "current_member_frontiers": len(frontier_symbols),
            "current_scenario_map_records": len(current_maps),
            "current_scenario_map_complete": True,
            "observable_return_paths": len(returns),
            "exact_old_equity_references": exact_equity,
            "p_star": "available" if p_star_count else "unavailable_company_specific_inputs",
            "p_star_calculable_records": p_star_count,
            "daily_funnel_items": len(funnel),
            "concurrent_portfolio": (
                portfolios[-1].get("evidence_status") if portfolios else "unavailable"
            ),
            "forward_shadow_days": forward_shadow_days,
            "operational_10_day_gate": (
                "passed" if forward_shadow_days >= 10 else "accumulating"
            ),
            "validation_60_day_gate": (
                "eligible_for_evaluation" if forward_shadow_days >= 60 else "accumulating"
            ),
        },
        "human_actions_required": 0,
        "publishable": True,
        "limitations": [
            "正文 LLM 未运行时，title/provisional 事件不升级为 body_verified。",
            "公司自身同口径成功/失败情景未闭合时，p* 保持 unavailable；跨公司中位数只作敏感性。",
            "组合只有真实 forward shadow 日，不回填伪历史漏斗。",
        ],
    }
    return status, complete


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--repository", type=Path, default=P8_RESEARCH_DB)
    parser.add_argument("--manifest", type=Path, default=P8_RESEARCH_MANIFEST_PATH)
    parser.add_argument("--status-json", type=Path)
    parser.add_argument("--publish-current", action="store_true")
    args = parser.parse_args()
    if not args.publish_current:
        parser.error("移动 current manifest 必须显式传 --publish-current")
    repository = P8ResearchRepository(args.repository)
    status, runs = build_status(repository, as_of=args.as_of)
    manifest = publish_manifest(args.manifest, runs=runs, through=args.as_of)
    status["manifest_id"] = manifest.manifest_id
    status["manifest_digest"] = manifest.content_digest
    if args.status_json:
        args.status_json.parent.mkdir(parents=True, exist_ok=True)
        args.status_json.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
