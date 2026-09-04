"""Materialize P8 cumulative activity features without reading future outcomes."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from market_activity import MarketActivityRepository
from p8_activity import (
    CONTRACT_VERSION,
    FROZEN_SHAPE_PROFILES,
    build_activity_features,
    classify_shape,
)
from p8_research import P8ResearchRepository, build_run
from p8_prices import qfq_close
from settings import (
    DATA_ROOT, MARKET_ACTIVITY_DB, MARKET_CONTEXT_DB, P7_INTELLIGENCE_DB,
    P8_QFQ_DB, P8_RESEARCH_DB,
)


DEFAULT_BASE_DB = DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"


class ActivityMaterializationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    run_id: str
    start_date: str
    through: str
    source_activity_fact_count: int
    feature_count: int
    calculable_count: int
    shape_profile: str
    shape_counts: dict[str, int]
    deviation_bin_counts: dict[str, int]
    point_in_time_market_value_count: int
    strict_single_day_input_count: int
    outcome_inputs_consumed: bool = False


def _connect_ro(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _qfq(
    path: Path, *, overlay_database: Path, symbols: set[str], start_date: str, through: str,
) -> dict[tuple[str, str], float]:
    return {
        key: value for key, value in qfq_close(
            path, overlay_database=overlay_database, start=start_date, through=through,
        ).items() if key[0] in symbols
    }


def _benchmarks(path: Path, *, start_date: str, through: str) -> dict[tuple[str, str], float]:
    with _connect_ro(path) as connection:
        return {
            (str(row[0]), str(row[1])): float(row[2])
            for row in connection.execute(
                "select benchmark_id,trade_date,close from benchmark_daily "
                "where benchmark_id in ('st_equal_weight_v1','csi_2000') "
                "and trade_date between ? and ? and close>0",
                (start_date, through),
            )
        }


def _deviation_bin(payload: dict[str, object]) -> str:
    if not bool(payload.get("calculable")):
        return "unknown"
    percentile = payload.get("turnover_percentile_120")
    robust_z = payload.get("turnover_robust_z_120")
    if percentile is None or robust_z is None:
        return "unknown"
    value, z_value = float(percentile), float(robust_z)
    for label, percentile_gate, z_gate in (
        ("D4", 99.0, 5.0),
        ("D3_only", 97.5, 4.0),
        ("D2_only", 95.0, 3.0),
        ("D1_only", 90.0, 2.0),
    ):
        if value >= percentile_gate and z_value >= z_gate:
            return label
    return "D0"


def _p7_anomaly_context(
    path: Path, *, through: str,
) -> tuple[
    str, set[tuple[str, str]], dict[tuple[str, str], str],
    dict[tuple[str, str], dict[str, object]],
]:
    with _connect_ro(path) as connection:
        row = connection.execute(
            "select run_id from p7_runs where run_kind='anomaly' and through<=? "
            "order by through desc,created_at desc limit 1",
            (through,),
        ).fetchone()
        if row is None:
            return "", set(), {}, {}
        run_id = str(row[0])
        rows = [
            (str(item[0]), str(item[1]), json.loads(str(item[2])))
            for item in connection.execute(
                "select symbol,trade_date,payload_json from activity_anomalies where run_id=?",
                (run_id,),
            )
        ]
    strict = {(symbol, day) for symbol, day, payload in rows if bool(payload.get("strict"))}
    bins = {(symbol, day): _deviation_bin(payload) for symbol, day, payload in rows}
    payloads = {(symbol, day): payload for symbol, day, payload in rows}
    return run_id, strict, bins, payloads


def materialize_activity(
    *, base_database: Path, market_context_database: Path,
    market_activity_database: Path, p7_intelligence_database: Path,
    qfq_database: Path,
    repository: P8ResearchRepository, dry_plan_json: Path,
    start_date: str, through: str,
) -> ActivityMaterializationResult:
    dry_plan = json.loads(dry_plan_json.read_text(encoding="utf-8"))
    profile_name = str(dry_plan.get("frozen_shape_profile") or "")
    profile = next((item for item in FROZEN_SHAPE_PROFILES if item.profile == profile_name), None)
    if profile is None:
        raise ValueError("P8-0 未冻结可用 shape profile")
    if bool(dry_plan.get("activity_feature_capacity", {}).get("threshold_selection_uses_outcomes")):
        raise ValueError("拒绝使用读取 outcome 后选择的 shape profile")

    facts = MarketActivityRepository(market_activity_database).latest_facts(
        start_date=start_date, through=through,
    )
    symbols = {item.symbol for item in facts}
    qfq = _qfq(
        base_database, overlay_database=qfq_database, symbols=symbols,
        start_date=start_date, through=through,
    )
    benchmarks = _benchmarks(market_context_database, start_date=start_date, through=through)
    features = build_activity_features(
        facts, qfq_close_by_symbol_date=qfq,
        benchmark_close_by_id_date=benchmarks,
    )
    p7_run_id, strict_dates, deviation_bins, anomaly_payloads = _p7_anomaly_context(
        p7_intelligence_database, through=through,
    )
    records = []
    shape_counts: Counter[str] = Counter()
    deviation_bin_counts: Counter[str] = Counter()
    for feature in features:
        label = classify_shape(
            feature, profile,
            single_day_strict=(feature.symbol, feature.trade_date) in strict_dates,
        )
        shape_counts[label.label] += 1
        deviation_bin = deviation_bins.get((feature.symbol, feature.trade_date), "unknown")
        anomaly = anomaly_payloads.get((feature.symbol, feature.trade_date), {})
        deviation_bin_counts[deviation_bin] += 1
        payload = feature.model_dump(mode="json")
        payload.update({
            "record_id": feature.feature_id,
            "available_as_of": feature.trade_date,
            "evidence_status": "derived_point_in_time" if feature.calculable else "unknown",
            "shape_profile": profile_name,
            "shape_label": label.label,
            "shape_reasons": label.reasons,
            "single_day_strict_input": (feature.symbol, feature.trade_date) in strict_dates,
            "single_day_deviation_bin": deviation_bin,
            "point_in_time_total_mv_10k_cny": anomaly.get("total_mv_10k_cny"),
            "risk_type": anomaly.get("risk_type", ""),
            "p7_anomaly_id": anomaly.get("anomaly_id", ""),
            "not_a_trading_signal": True,
        })
        records.append(payload)
    record_payloads = {"activity_feature": records}
    run = build_run(
        run_kind="activity_features", contract_version=CONTRACT_VERSION,
        start_date=start_date, through=through,
        source_run_ids=[item for item in (p7_run_id, dry_plan.get("plan_id", "")) if item],
        source_digests={
            "market_activity_v1": _file_digest(market_activity_database),
            "market_context_v1": _file_digest(market_context_database),
            "p8_qfq_overlay": _file_digest(qfq_database) if qfq_database.is_file() else "",
            "p8_dry_plan": str(dry_plan.get("content_digest") or ""),
        },
        record_payloads=record_payloads,
    )
    repository.persist(run=run, records=record_payloads)
    return ActivityMaterializationResult(
        run_id=run.run_id,
        start_date=start_date,
        through=through,
        source_activity_fact_count=len(facts),
        feature_count=len(features),
        calculable_count=sum(item.calculable for item in features),
        shape_profile=profile_name,
        shape_counts=dict(sorted(shape_counts.items())),
        deviation_bin_counts=dict(sorted(deviation_bin_counts.items())),
        point_in_time_market_value_count=sum(
            item.get("point_in_time_total_mv_10k_cny") is not None for item in records
        ),
        strict_single_day_input_count=len(strict_dates),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--through", required=True)
    parser.add_argument("--base-database", type=Path, default=DEFAULT_BASE_DB)
    parser.add_argument("--market-context-database", type=Path, default=MARKET_CONTEXT_DB)
    parser.add_argument("--market-activity-database", type=Path, default=MARKET_ACTIVITY_DB)
    parser.add_argument("--p7-intelligence-database", type=Path, default=P7_INTELLIGENCE_DB)
    parser.add_argument("--qfq-database", type=Path, default=P8_QFQ_DB)
    parser.add_argument("--repository", type=Path, default=P8_RESEARCH_DB)
    parser.add_argument("--dry-plan-json", type=Path, required=True)
    parser.add_argument("--output-json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = materialize_activity(
        base_database=args.base_database,
        market_context_database=args.market_context_database,
        market_activity_database=args.market_activity_database,
        p7_intelligence_database=args.p7_intelligence_database,
        qfq_database=args.qfq_database,
        repository=P8ResearchRepository(args.repository),
        dry_plan_json=args.dry_plan_json,
        start_date=args.start_date,
        through=args.through,
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
