"""Walk-forward P8A scenario-reference layer stability test."""
from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from data_refresh import atomic_write_json
from p8_references import ScenarioReference, build_distribution
from p8_research import P8ResearchRepository, build_run, content_id
from settings import P8_RESEARCH_DB


CONTRACT_VERSION = "v8_p8_reference_backtest_v2"
TEST_YEARS = (2023, 2024, 2025)
MIN_OBSERVATIONS = 100
MIN_COMPANIES = 40
VERIFIED = {"verified", "body_verified", "deterministic_verified"}
FAMILY_VALUE = {
    "strategic_entry_reference": "old_equity_value",
    "failure_exit_reference": "total_market_value",
    "public_node_reference": "total_market_value",
}


def _months_before(day: str, months: int) -> str:
    value = date.fromisoformat(day)
    index = value.year * 12 + value.month - 1 - months
    year, month_zero = divmod(index, 12)
    candidate = value.day
    while candidate:
        try:
            return date(year, month_zero + 1, candidate).isoformat()
        except ValueError:
            candidate -= 1
    raise AssertionError("unreachable")


def _interval(values: list[float]) -> tuple[float, float, float] | None:
    if len(values) < 8:
        return None
    ordered = sorted(values)
    return (
        ordered[int((len(ordered) - 1) * .25)],
        statistics.median(ordered),
        ordered[int((len(ordered) - 1) * .75)],
    )


def _interval_score(value: float, lower: float, upper: float) -> float:
    score = upper - lower
    if value < lower:
        score += 4 * (lower - value)
    elif value > upper:
        score += 4 * (value - upper)
    return score


def _as_value_reference(item: dict[str, Any]) -> ScenarioReference | None:
    family = str(item.get("family") or "")
    field = FAMILY_VALUE.get(family)
    value = item.get(field or "")
    if field is None or value is None or item.get("evidence_status") not in VERIFIED:
        return None
    reference = ScenarioReference.model_validate({
        key: value for key, value in item.items()
        if key in ScenarioReference.model_fields
    })
    return reference.model_copy(update={"old_equity_value": float(value)})


def build_reference_observations(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    transformed = [value for item in records if (value := _as_value_reference(item)) is not None]
    observations: list[dict[str, Any]] = []
    for target in transformed:
        year = int(target.available_as_of[:4])
        if year not in TEST_YEARS:
            continue
        training_cutoff = f"{year - 1}-12-31"
        training = [
            item for item in transformed
            if item.family == target.family and item.available_as_of <= training_cutoff
        ]
        distribution = build_distribution(
            training, family=target.family, as_of=target.available_as_of,
            stage=target.stage, risk_type=target.delisting_risk_type,
            board=target.board, regime_version=target.regime_version,
            exclude_symbol=target.symbol,
        )
        if distribution.status != "distribution":
            continue
        global_values = [
            float(item.old_equity_value) for item in training
            if item.symbol != target.symbol
            and item.regime_version == target.regime_version
            and _months_before(target.available_as_of, 24) <= item.available_as_of <= target.available_as_of
            and item.old_equity_value is not None
        ]
        global_companies = {
            item.symbol for item in training
            if item.symbol != target.symbol and item.regime_version == target.regime_version
            and _months_before(target.available_as_of, 24) <= item.available_as_of <= target.available_as_of
            and item.old_equity_value is not None
        }
        global_interval = _interval(global_values) if len(global_companies) >= 5 else None
        if global_interval is None:
            continue
        value = float(target.old_equity_value)
        assert distribution.p25 is not None and distribution.p75 is not None and distribution.median is not None
        global_lower, global_median, global_upper = global_interval
        identity = {
            "contract": CONTRACT_VERSION, "reference_id": target.reference_id,
            "training_cutoff": training_cutoff, "distribution": distribution.model_dump(mode="json"),
        }
        observations.append({
            "record_id": content_id("P8AREFTEST", identity),
            "symbol": target.symbol, "available_as_of": target.available_as_of,
            "test_year": year, "family": target.family,
            "stage": target.stage, "delisting_risk_type": target.delisting_risk_type,
            "board": target.board, "regime_version": target.regime_version,
            "value": value, "value_field": FAMILY_VALUE[target.family],
            "reference_n": distribution.n, "reference_company_n": distribution.company_n,
            "relaxation_path": distribution.relaxation_path,
            "stratified_median": distribution.median,
            "stratified_p25": distribution.p25, "stratified_p75": distribution.p75,
            "stratified_covered": distribution.p25 <= value <= distribution.p75,
            "stratified_interval_score": _interval_score(value, distribution.p25, distribution.p75),
            "unstratified_median": global_median,
            "unstratified_p25": global_lower, "unstratified_p75": global_upper,
            "unstratified_interval_score": _interval_score(value, global_lower, global_upper),
            "interval_score_difference": (
                _interval_score(value, distribution.p25, distribution.p75)
                - _interval_score(value, global_lower, global_upper)
            ),
            "normalized_interval_score_difference": (
                (
                    _interval_score(value, distribution.p25, distribution.p75)
                    - _interval_score(value, global_lower, global_upper)
                ) / abs(value) if value else None
            ),
            "median_absolute_percentage_error": (
                abs(value - distribution.median) / abs(value) if value else None
            ),
            "evidence_status": "walk_forward_point_in_time",
        })
    return observations


def _cluster_interval(rows: list[dict[str, Any]], *, seed: int, repetitions: int = 500) -> list[float] | None:
    grouped: dict[str, list[float]] = defaultdict(list)
    for item in rows:
        if item.get("normalized_interval_score_difference") is not None:
            grouped[str(item["symbol"])].append(float(item["normalized_interval_score_difference"]))
    symbols = sorted(grouped)
    if len(symbols) < 5:
        return None
    generator = random.Random(seed)
    estimates: list[float] = []
    for _ in range(repetitions):
        sample = [generator.choice(symbols) for _ in symbols]
        values = [value for symbol in sample for value in grouped[symbol]]
        estimates.append(statistics.mean(values))
    estimates.sort()
    return [estimates[int((len(estimates) - 1) * .025)], estimates[int((len(estimates) - 1) * .975)]]


def scorecard(observations: list[dict[str, Any]], *, family: str = "all") -> dict[str, Any]:
    companies = {str(item["symbol"]) for item in observations}
    per_year: dict[str, Any] = {}
    for year in TEST_YEARS:
        rows = [item for item in observations if int(item["test_year"]) == year]
        errors = [float(item["median_absolute_percentage_error"]) for item in rows if item.get("median_absolute_percentage_error") is not None]
        differences = [
            float(item["normalized_interval_score_difference"]) for item in rows
            if item.get("normalized_interval_score_difference") is not None
        ]
        per_year[str(year)] = {
            "observation_count": len(rows),
            "company_count": len({str(item["symbol"]) for item in rows}),
            "median_absolute_percentage_error": statistics.median(errors) if errors else None,
            "mean_interval_score_difference_vs_unstratified": statistics.mean(differences) if differences else None,
            "p25_p75_coverage": statistics.mean(bool(item["stratified_covered"]) for item in rows) if rows else None,
        }
    if len(observations) < MIN_OBSERVATIONS or len(companies) < MIN_COMPANIES:
        status, reason = "unavailable", "minimum_100_observations_40_companies_not_met"
    else:
        mdape_bad = sum(
            item["median_absolute_percentage_error"] is not None
            and float(item["median_absolute_percentage_error"]) > .5
            for item in per_year.values()
        )
        interval_bad = sum(
            item["mean_interval_score_difference_vs_unstratified"] is not None
            and float(item["mean_interval_score_difference_vs_unstratified"]) >= 0
            for item in per_year.values()
        )
        ci = _cluster_interval(observations, seed=2026090503)
        favorable_years = sum(
            item["mean_interval_score_difference_vs_unstratified"] is not None
            and float(item["mean_interval_score_difference_vs_unstratified"]) < 0
            for item in per_year.values()
        )
        if mdape_bad >= 2 or interval_bad >= 2:
            status, reason = "killed", "two_test_years_fail_stability_or_unstratified_baseline"
        elif favorable_years >= 2 and ci and ci[1] < 0:
            status, reason = "supported", "stratification_improves_interval_score_in_two_years"
        else:
            status, reason = "weak", "direction_or_uncertainty_not_consistent"
    return {
        "signal_family": f"p8a_reference_layer:{family}", "status": status, "reason": reason,
        "observation_count": len(observations), "company_count": len(companies),
        "company_cluster_ci95_interval_score_difference": _cluster_interval(
            observations, seed=2026090503,
        ),
        "per_year": per_year,
    }


def build_report(repository: P8ResearchRepository) -> dict[str, Any]:
    source = repository.latest_run("scenario_references")
    if source is None:
        raise ValueError("缺 scenario_references")
    records = repository.records(run_id=source.run_id, record_type="scenario_reference")
    observations = build_reference_observations(records)
    family_scorecards = [
        scorecard(
            [item for item in observations if item["family"] == family], family=family,
        ) for family in FAMILY_VALUE
    ]
    return {
        "record_id": content_id("P8AREPORT", {
            "contract": CONTRACT_VERSION, "source_digest": source.content_digest,
            "observations": observations,
        }),
        "contract_version": CONTRACT_VERSION,
        "source_run_id": source.run_id, "source_digest": source.content_digest,
        "observation_count": len(observations), "family_scorecards": family_scorecards,
        "observations": observations, "not_a_fair_value_claim": True,
        "not_a_trading_signal": True,
    }


def persist(repository: P8ResearchRepository, report: dict[str, Any]) -> str:
    record = {key: value for key, value in report.items() if key != "observations"}
    run = build_run(
        run_kind="p8_reference_backtest_v2", contract_version=CONTRACT_VERSION,
        start_date="2023-01-01", through="2025-12-31",
        source_run_ids=[str(report["source_run_id"])],
        source_digests={"scenario_references": str(report["source_digest"])},
        record_payloads={"p8_reference_backtest_v2": [record]},
    )
    repository.persist(run=run, records={"p8_reference_backtest_v2": [record]})
    return run.run_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=P8_RESEARCH_DB)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    repository = P8ResearchRepository(args.repository)
    report = build_report(repository)
    run_id = persist(repository, report)
    report["run_id"] = run_id
    atomic_write_json(args.output_json, report)
    print(json.dumps({
        "run_id": run_id, "observation_count": report["observation_count"],
        "family_scorecards": report["family_scorecards"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
