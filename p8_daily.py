"""One-command P8 materialization; publish current only after every stage succeeds."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from p8_backtest import build_report, persist_report
from p8_chip_proxies import _load_env_file, materialize_chip_proxies
from p8_event_graph import build_event_graph, persist_event_graph
from p8_funnel import materialize_funnel
from p8_llm_extraction import (
    DEFAULT_CACHE_DIR as LLM_CACHE_DIR,
    persist_reconciled,
    reconcile_event_graph,
    run_extraction,
)
from p8_materialize_activity import materialize_activity
from p8_portfolio import materialize_portfolio, persist as persist_portfolio
from p8_publish import build_status
from p8_references import materialize_references
from p8_research import P8ResearchRepository, publish_manifest
from p8_returns import materialize_return_paths
from p8_review_panel import _names, build_queue, render_html
from llm.config import resolve_model
from settings import (
    DATA_ROOT, MARKET_ACTIVITY_DB, MARKET_CONTEXT_DB, MARKET_FACTOR_DB,
    P7_INTELLIGENCE_DB, P8_RESEARCH_DB, P8_RESEARCH_MANIFEST_PATH,
    VALUATION_EPISODE_DB,
)


DEFAULT_BASE_DB = DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"
DEFAULT_OUTPUT_DIR = DATA_ROOT / "local_data/v8_copilot"


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")  # type: ignore[union-attr]
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--event-start", default="2021-03-17")
    parser.add_argument("--activity-start", default="2025-02-26")
    parser.add_argument("--portfolio-start", default="2026-09-03")
    parser.add_argument("--dry-plan-json", type=Path, required=True)
    parser.add_argument("--base-database", type=Path, default=DEFAULT_BASE_DB)
    parser.add_argument("--market-context-database", type=Path, default=MARKET_CONTEXT_DB)
    parser.add_argument("--market-factor-database", type=Path, default=MARKET_FACTOR_DB)
    parser.add_argument("--market-activity-database", type=Path, default=MARKET_ACTIVITY_DB)
    parser.add_argument("--p7-intelligence-database", type=Path, default=P7_INTELLIGENCE_DB)
    parser.add_argument("--valuation-episode-database", type=Path, default=VALUATION_EPISODE_DB)
    parser.add_argument("--repository", type=Path, default=P8_RESEARCH_DB)
    parser.add_argument("--manifest", type=Path, default=P8_RESEARCH_MANIFEST_PATH)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--provider-env-file", type=Path)
    parser.add_argument("--chip-cache-dir", type=Path, default=DEFAULT_OUTPUT_DIR / "p8_chip_proxy_cache")
    parser.add_argument("--llm-cache-dir", type=Path, default=LLM_CACHE_DIR)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--allow-provider", action="store_true")
    parser.add_argument("--allow-llm", action="store_true")
    args = parser.parse_args()
    repository = P8ResearchRepository(args.repository)
    output = args.output_directory

    graph = build_event_graph(
        base_database=args.base_database,
        p7_intelligence_database=args.p7_intelligence_database,
        valuation_episode_database=args.valuation_episode_database,
        start_date=args.event_start, through=args.as_of,
    )
    if args.allow_llm:
        model = resolve_model()
        extraction = run_extraction(
            base_database=args.base_database,
            p7_database=args.p7_intelligence_database,
            start_date=args.event_start, through=args.as_of,
            model=model, cache_dir=args.llm_cache_dir, workers=args.workers,
        )
        graph = reconcile_event_graph(
            baseline=graph, extraction=extraction, base_database=args.base_database,
        )
        event_run = persist_reconciled(
            graph=graph, extraction=extraction, repository=repository,
        )
        _write(output / "p8_llm_extraction_v1.json", extraction)
    else:
        event_run = persist_event_graph(graph, repository)
    _write(output / "p8_event_graph_v1.json", graph)

    activity = materialize_activity(
        base_database=args.base_database,
        market_context_database=args.market_context_database,
        market_activity_database=args.market_activity_database,
        p7_intelligence_database=args.p7_intelligence_database,
        repository=repository, dry_plan_json=args.dry_plan_json,
        start_date=args.activity_start, through=args.as_of,
    )
    _write(output / "p8_activity_features_v1.json", activity)

    if args.allow_provider:
        _load_env_file(args.provider_env_file)
        chip = materialize_chip_proxies(
            market_context_database=args.market_context_database,
            repository=repository, as_of=args.as_of,
            cache_dir=args.chip_cache_dir, workers=args.workers,
        )
        _write(output / f"p8_chip_proxies_{args.as_of}.json", chip)
    else:
        chip_run = repository.latest_run("chip_proxies")
        if chip_run is None or chip_run.through != args.as_of:
            raise ValueError("当日 chip proxy 不存在；请显式传 --allow-provider")
        chip_records = repository.records(run_id=chip_run.run_id, record_type="chip_proxy")
        chip = {
            "run_id": chip_run.run_id, "as_of": args.as_of,
            "member_count": len(chip_records), "record_count": len(chip_records),
            "holder_observed_count": sum(item.get("holder_status") == "observed" for item in chip_records),
        }

    returns = materialize_return_paths(
        base_database=args.base_database,
        market_context_database=args.market_context_database,
        market_factor_database=args.market_factor_database,
        market_activity_database=args.market_activity_database,
        valuation_episode_database=args.valuation_episode_database,
        repository=repository, start_date=args.event_start, through=args.as_of,
    )
    _write(output / "p8_return_paths_v1.json", returns)
    references = materialize_references(
        repository=repository, base_database=args.base_database,
        market_factor_database=args.market_factor_database, through=args.as_of,
    )
    _write(output / "p8_scenario_references_v1.json", references)
    funnel = materialize_funnel(repository=repository, as_of=args.as_of)
    _write(output / f"p8_funnel_{args.as_of}.json", funnel)
    portfolio = materialize_portfolio(
        repository=repository, base_database=args.base_database,
        market_context_database=args.market_context_database,
        market_activity_database=args.market_activity_database,
        start_date=args.portfolio_start, through=args.as_of,
    )
    portfolio_run = persist_portfolio(portfolio, repository)
    _write(output / "p8_portfolio_v1.json", {"run_id": portfolio_run.run_id, **portfolio.model_dump(mode="json")})
    report = build_report(
        repository=repository, base_database=args.base_database,
        market_context_database=args.market_context_database,
        valuation_episode_database=args.valuation_episode_database,
        start_date=args.activity_start, through=args.as_of,
    )
    backtest_run = persist_report(report, repository)
    backtest = {"run_id": backtest_run.run_id, **report.model_dump(mode="json")}
    _write(output / "p8_backtest_v1.json", backtest)

    dry_plan = json.loads(args.dry_plan_json.read_text(encoding="utf-8"))
    funnel_payload = funnel.model_dump(mode="json")
    chip_payload = chip.model_dump(mode="json") if hasattr(chip, "model_dump") else chip
    queue = build_queue(
        funnel=funnel_payload, backtest=backtest, dry_plan=dry_plan,
        names=_names(args.base_database),
    )
    review_dir = output / "p8_review/latest"
    _write(review_dir / "review_queue.json", queue)
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / "index.html").write_text(render_html(
        queue=queue, funnel=funnel_payload, backtest=backtest,
        dry_plan=dry_plan, chip=chip_payload,
    ), encoding="utf-8")

    status, runs = build_status(repository, as_of=args.as_of)
    manifest = publish_manifest(args.manifest, runs=runs, through=args.as_of)
    status.update({"manifest_id": manifest.manifest_id, "manifest_digest": manifest.content_digest})
    _write(output / "p8_status_v1.json", status)
    print(json.dumps({
        "as_of": args.as_of, "manifest_id": manifest.manifest_id,
        "event_run_id": event_run.run_id, "funnel_items": funnel.item_count,
        "body_verified_events": status["capabilities"]["body_verified_events"],
        "human_actions_required": 0,
        "review_html": str(review_dir / "index.html"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
