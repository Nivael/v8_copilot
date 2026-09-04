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
    extractions = repository.records(run_id=event_run.run_id, record_type="llm_announcement_extraction")
    returns = repository.records(run_id=return_run.run_id, record_type="return_path")
    references = repository.records(run_id=reference_run.run_id, record_type="scenario_reference")
    funnel = repository.records(run_id=funnel_run.run_id, record_type="funnel_item")
    portfolios = repository.records(run_id=portfolio_run.run_id, record_type="portfolio_summary")
    body_verified = sum(item.get("evidence_status") == "body_verified" for item in events)
    exact_equity = sum(item.get("value_status") == "exact_old_equity" for item in references)
    status = {
        "as_of": as_of,
        "run_ids_by_kind": {run.run_kind: run.run_id for run in complete},
        "capabilities": {
            "event_graph": "available",
            "body_llm_extraction": "available" if extractions else "authorization_pending",
            "body_verified_events": body_verified,
            "observable_return_paths": len(returns),
            "exact_old_equity_references": exact_equity,
            "p_star": "available" if exact_equity else "unavailable_same_claim_inputs",
            "daily_funnel_items": len(funnel),
            "concurrent_portfolio": (
                portfolios[-1].get("evidence_status") if portfolios else "unavailable"
            ),
        },
        "human_actions_required": 0,
        "publishable": True,
        "limitations": [
            "正文 LLM 未运行时，title/provisional 事件不升级为 body_verified。",
            "精确旧股东权益参照为 0 时，p* 保持 unavailable。",
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
