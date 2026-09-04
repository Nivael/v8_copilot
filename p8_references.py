"""P8A three-family scenario references; deliberately independent from activity/funnel."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import statistics
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from p8_regimes import REGISTRY_VERSION, regime_for_date
from p8_research import P8ResearchRepository, build_run, content_id
from settings import DATA_ROOT, MARKET_FACTOR_DB, P8_RESEARCH_DB


CONTRACT_VERSION = "p8_scenario_references_v1"
MIN_OBSERVATIONS = 8
MIN_COMPANIES = 5
WINDOWS = (12, 18, 24)
DEFAULT_BASE_DB = DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ScenarioReference(StrictModel):
    reference_id: str = Field(pattern=r"^P8REF-[A-F0-9]{20}$")
    family: Literal[
        "strategic_entry_reference", "failure_exit_reference", "public_node_reference"
    ]
    symbol: str = Field(pattern=r"^\d{6}$")
    available_as_of: str
    stage: str
    stage_source: str
    delisting_risk_type: Literal[
        "financial", "trading", "normative", "major_violation",
        "none_identified", "unknown",
    ]
    board: Literal["主板", "创业板", "科创板", "北交所"]
    regime_version: str
    total_market_value: float | None = None
    old_equity_value: float | None = None
    transaction_price_per_share: float | None = None
    transferred_shares: float | None = None
    old_shareholder_retained_shares: float | None = None
    value_status: Literal[
        "exact_old_equity", "range_old_equity", "total_mv_fact_only", "raw_terms_only", "unknown"
    ]
    contamination_flags: list[str]
    source_ids: list[str]
    evidence_status: str
    not_a_fair_value_claim: bool = True


class ReferenceDistribution(StrictModel):
    family: str
    as_of: str
    layer_key: str
    relaxation_path: list[str]
    window_months: int
    n: int
    company_n: int
    median: float | None = None
    p25: float | None = None
    p75: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    status: Literal["distribution", "raw_points_only", "empty"]
    value_field: Literal["old_equity_value"] = "old_equity_value"


class ReferenceMaterializationResult(StrictModel):
    run_id: str
    through: str
    reference_count: int
    family_counts: dict[str, int]
    value_status_counts: dict[str, int]
    exact_old_equity_count: int
    total_mv_fact_count: int
    distribution_count: int
    p_star_calculable_count: int
    regime_registry_version: str


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


def _board(symbol: str) -> str:
    if symbol.startswith("300"):
        return "创业板"
    if symbol.startswith("688"):
        return "科创板"
    if symbol.startswith(("8", "9")):
        return "北交所"
    return "主板"


def _risk_text_type(text: str, *, status_type: str = "") -> str:
    normalized = text or ""
    if any(term in normalized for term in ("重大违法", "欺诈发行", "虚假记载")):
        return "major_violation"
    if any(term in normalized for term in ("低于1元", "低于一元", "市值低于", "股东人数", "成交量")):
        return "trading"
    if any(term in normalized for term in ("资金占用", "规范运作", "内部控制", "控股股东")):
        return "normative"
    if any(term in normalized for term in ("净资产", "营业收入", "利润", "审计意见", "无法表示", "否定意见")):
        return "financial"
    if status_type == "other_risk_warning":
        return "none_identified"
    return "unknown"


def _risk_type(path: Path, *, symbol: str, day: str) -> str:
    with _connect_ro(path) as connection:
        rows = connection.execute(
            "select status_name,status_type,coalesce(notes,'') notes from st_status_history "
            "where symbol=? and start_date<=? and (end_date is null or end_date>=?) "
            "order by start_date desc",
            (symbol, day, day),
        ).fetchall()
    if not rows:
        return "unknown"
    values = [_risk_text_type(f"{row['status_name']} {row['notes']}", status_type=str(row["status_type"])) for row in rows]
    known = [value for value in values if value not in {"unknown", "none_identified"}]
    return known[0] if known else ("none_identified" if "none_identified" in values else "unknown")


def _market_values(path: Path) -> dict[tuple[str, str], float]:
    result: dict[tuple[str, str], float] = {}
    with _connect_ro(path) as connection:
        for row in connection.execute(
            "select d.symbol,d.trade_date,d.total_market_value from market_cap_daily d "
            "join market_factor_snapshots s on s.snapshot_id=d.snapshot_id "
            "where d.total_market_value is not null order by d.symbol,d.trade_date,s.created_at"
        ):
            result[(str(row[0]), str(row[1]))] = float(row[2])
    return result


def _stage_for_node(node: str) -> str:
    return {
        "restructuring_application_disclosed": "restructuring_application_disclosed",
        "pre_restructuring_started": "pre_restructuring_started",
        "investor_recruitment": "investor_recruitment",
        "investor_selected": "investor_recruitment",
        "investor_agreement_signed": "investor_agreement_signed",
        "formal_restructuring_accepted": "formal_restructuring_accepted",
        "creditor_claims": "formal_restructuring_accepted",
        "creditor_meeting": "formal_restructuring_accepted",
        "plan_key_terms_disclosed": "plan_key_terms_disclosed",
        "plan_approved": "plan_approved",
        "plan_executed": "plan_executed",
        "risk_warning_removed": "risk_warning_removed",
    }.get(node, "unknown")


def _reference(
    *, family: str, symbol: str, available_as_of: str, stage: str,
    stage_source: str, base_database: Path, total_mv: float | None,
    source_ids: list[str], evidence_status: str, contamination: list[str],
    value_status: str,
) -> ScenarioReference:
    identity = {
        "contract": CONTRACT_VERSION, "family": family, "symbol": symbol,
        "available_as_of": available_as_of, "stage": stage,
        "source_ids": sorted(source_ids), "total_mv": total_mv,
    }
    return ScenarioReference(
        reference_id=content_id("P8REF", identity),
        family=family,  # type: ignore[arg-type]
        symbol=symbol,
        available_as_of=available_as_of,
        stage=stage,
        stage_source=stage_source,
        delisting_risk_type=_risk_type(
            base_database, symbol=symbol, day=available_as_of,
        ),  # type: ignore[arg-type]
        board=_board(symbol),  # type: ignore[arg-type]
        regime_version=regime_for_date(available_as_of).regime_version,
        total_market_value=total_mv,
        value_status=value_status,  # type: ignore[arg-type]
        contamination_flags=sorted(set(contamination)),
        source_ids=sorted(source_ids),
        evidence_status=evidence_status,
    )


def build_reference_points(
    *, repository: P8ResearchRepository, base_database: Path,
    market_factor_database: Path,
) -> list[ScenarioReference]:
    event_run = repository.latest_run("event_graph")
    return_run = repository.latest_run("return_paths")
    if event_run is None or return_run is None:
        raise ValueError("P8A 需要 event_graph 与 return_paths")
    events = repository.records(run_id=event_run.run_id, record_type="derived_event")
    paths = repository.records(run_id=return_run.run_id, record_type="return_path")
    path_by_anchor = {str(item["anchor_id"]): item for item in paths}
    market_values = _market_values(market_factor_database)
    references: list[ScenarioReference] = []
    for event in events:
        node = str(event.get("node") or "")
        symbol = str(event.get("symbol") or "")
        path = path_by_anchor.get(str(event.get("event_id") or ""), {})
        entry_date = str(path.get("entry_date") or "")
        total_mv = market_values.get((symbol, entry_date)) if entry_date else None
        source_ids = list(event.get("source_ids") or [])
        evidence_status = str(event.get("evidence_status") or "unknown")
        if node == "investor_agreement_signed":
            references.append(_reference(
                family="strategic_entry_reference", symbol=symbol,
                available_as_of=str(event["available_as_of"]),
                stage="investor_agreement_signed", stage_source=evidence_status,
                base_database=base_database, total_mv=None, source_ids=source_ids,
                evidence_status=evidence_status,
                contamination=["transaction_terms_not_structured", "package_conditions_not_separated"],
                value_status="raw_terms_only",
            ))
        if node in {"formal_restructuring_accepted", "plan_approved", "plan_executed", "risk_warning_removed"}:
            flags = [] if total_mv is not None else ["point_in_time_market_value_missing"]
            if path and any(
                horizon.get("capital_structure_status") == "changed"
                for horizon in path.get("horizons", [])
            ):
                flags.append("capital_structure_changed_in_observation_window")
            references.append(_reference(
                family="public_node_reference", symbol=symbol,
                available_as_of=entry_date or str(event["available_as_of"]),
                stage=_stage_for_node(node), stage_source=evidence_status,
                base_database=base_database, total_mv=total_mv, source_ids=source_ids,
                evidence_status=evidence_status, contamination=flags,
                value_status="total_mv_fact_only" if total_mv is not None else "unknown",
            ))
    for path in paths:
        if (
            str(path.get("anchor_kind") or "") != "episode_start"
            or not bool(path.get("delisted_known"))
            or not str(path.get("last_exchange_date") or "")
        ):
            continue
        symbol = str(path["symbol"])
        last_date = str(path["last_exchange_date"])
        total_mv = market_values.get((symbol, last_date))
        references.append(_reference(
            family="failure_exit_reference", symbol=symbol,
            available_as_of=last_date,
            stage=str(path.get("anchor_node") or "unknown"),
            stage_source=str(path.get("evidence_status") or "unknown"),
            base_database=base_database, total_mv=total_mv,
            source_ids=[str(path.get("path_id") or "")],
            evidence_status=str(path.get("evidence_status") or "unknown"),
            contamination=[] if total_mv is not None else ["last_exchange_market_value_missing"],
            value_status="total_mv_fact_only" if total_mv is not None else "unknown",
        ))
    unique = {item.reference_id: item for item in references}
    return sorted(unique.values(), key=lambda item: (item.available_as_of, item.symbol, item.family))


def _months_before(day: str, months: int) -> str:
    value = date.fromisoformat(day)
    index = value.year * 12 + value.month - 1 - months
    year, month_zero = divmod(index, 12)
    month = month_zero + 1
    candidate_day = value.day
    while candidate_day:
        try:
            return date(year, month, candidate_day).isoformat()
        except ValueError:
            candidate_day -= 1
    raise AssertionError("unreachable")


def build_distribution(
    references: list[ScenarioReference], *, family: str, as_of: str,
    stage: str, risk_type: str, board: str, regime_version: str,
) -> ReferenceDistribution:
    paths = [
        ("exact", lambda item: item.stage == stage and item.delisting_risk_type == risk_type and item.board == board),
        ("drop_board", lambda item: item.stage == stage and item.delisting_risk_type == risk_type),
    ]
    adjacent = {
        "distress_entry": {"st_distress_only", "restructuring_application_disclosed"},
        "pre_judicial": {"pre_restructuring_started", "investor_recruitment"},
        "formal_process": {"formal_restructuring_accepted", "investor_agreement_signed"},
        "plan_resolution": {"plan_key_terms_disclosed", "plan_approved"},
        "execution_exit": {"plan_executed", "risk_warning_removed"},
    }
    group = next((members for members in adjacent.values() if stage in members), {stage})
    paths.append(("adjacent_stage_group", lambda item: item.stage in group and item.delisting_risk_type == risk_type))
    last_points: list[ScenarioReference] = []
    last_path: list[str] = []
    last_window = 24
    for window in WINDOWS:
        start = _months_before(as_of, window)
        for label, predicate in paths:
            selected = [
                item for item in references
                if item.family == family and item.regime_version == regime_version
                and start <= item.available_as_of <= as_of and predicate(item)
                and item.old_equity_value is not None
            ]
            last_points, last_path, last_window = selected, [label], window
            companies = {item.symbol for item in selected}
            if len(selected) >= MIN_OBSERVATIONS and len(companies) >= MIN_COMPANIES:
                values = sorted(float(item.old_equity_value) for item in selected if item.old_equity_value is not None)
                return ReferenceDistribution(
                    family=family, as_of=as_of,
                    layer_key=f"{stage}|{risk_type}|{board}|{regime_version}",
                    relaxation_path=[label] + ([f"window_{window}m"] if window != 12 else []),
                    window_months=window, n=len(values), company_n=len(companies),
                    median=statistics.median(values),
                    p25=values[int((len(values) - 1) * .25)],
                    p75=values[int((len(values) - 1) * .75)],
                    minimum=min(values), maximum=max(values), status="distribution",
                )
    return ReferenceDistribution(
        family=family, as_of=as_of,
        layer_key=f"{stage}|{risk_type}|{board}|{regime_version}",
        relaxation_path=last_path + ["raw_points_only"],
        window_months=last_window,
        n=len(last_points), company_n=len({item.symbol for item in last_points}),
        status="raw_points_only" if last_points else "empty",
    )


def scenario_weight(*, current: float | None, failure: float | None, success: float | None) -> tuple[float | None, str]:
    if current is None or failure is None or success is None:
        return None, "input_unknown"
    denominator = success - failure
    if denominator <= 0:
        return None, "non_positive_scenario_spread"
    value = (current - failure) / denominator
    return value, "outside_scenario_range" if value < 0 or value > 1 else "within_scenario_range"


def materialize_references(
    *, repository: P8ResearchRepository, base_database: Path,
    market_factor_database: Path, through: str,
) -> ReferenceMaterializationResult:
    references = build_reference_points(
        repository=repository, base_database=base_database,
        market_factor_database=market_factor_database,
    )
    records = {"scenario_reference": [
        {**item.model_dump(mode="json"), "record_id": item.reference_id}
        for item in references
    ]}
    event_run = repository.latest_run("event_graph")
    return_run = repository.latest_run("return_paths")
    run = build_run(
        run_kind="scenario_references", contract_version=CONTRACT_VERSION,
        start_date=min((item.available_as_of for item in references), default=through),
        through=through,
        source_run_ids=[item.run_id for item in (event_run, return_run) if item],
        source_digests={
            "market_factors_v1": _file_digest(market_factor_database),
            "regime_registry": hashlib.sha256(REGISTRY_VERSION.encode()).hexdigest(),
        },
        record_payloads=records,
    )
    repository.persist(run=run, records=records)
    return ReferenceMaterializationResult(
        run_id=run.run_id, through=through,
        reference_count=len(references),
        family_counts=dict(sorted(Counter(item.family for item in references).items())),
        value_status_counts=dict(sorted(Counter(item.value_status for item in references).items())),
        exact_old_equity_count=sum(item.value_status == "exact_old_equity" for item in references),
        total_mv_fact_count=sum(item.total_market_value is not None for item in references),
        distribution_count=0,
        p_star_calculable_count=0,
        regime_registry_version=REGISTRY_VERSION,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through", required=True)
    parser.add_argument("--base-database", type=Path, default=DEFAULT_BASE_DB)
    parser.add_argument("--market-factor-database", type=Path, default=MARKET_FACTOR_DB)
    parser.add_argument("--repository", type=Path, default=P8_RESEARCH_DB)
    parser.add_argument("--output-json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = materialize_references(
        repository=P8ResearchRepository(args.repository),
        base_database=args.base_database,
        market_factor_database=args.market_factor_database,
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
