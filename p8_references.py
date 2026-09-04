"""P8A three-family scenario references; deliberately independent from activity/funnel."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import statistics
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from p8_regimes import REGISTRY_VERSION, regime_for_date
from p8_research import P8ResearchRepository, build_run, content_id
from settings import (
    DATA_ROOT,
    MARKET_ACTIVITY_DB,
    MARKET_FACTOR_DB,
    P8_RESEARCH_DB,
    VALUATION_EPISODE_DB,
)


CONTRACT_VERSION = "p8_scenario_references_v2"
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
    transaction_consideration: float | None = None
    post_restructuring_total_shares: float | None = None
    headline_post_money: float | None = None
    old_shareholder_retained_shares: float | None = None
    old_shareholder_retained_ratio: float | None = None
    creditor_compensation_shares: float | None = None
    cash_investment: float | None = None
    share_conversion_ratio_raw: str = ""
    share_transfer_ratio_raw: str = ""
    lockup_period_raw: str = ""
    industrial_commitment_raw: str = ""
    total_loss_stress: float | None = None
    market_endpoint_status: str = "not_applicable"
    market_endpoint_delay_rows: int | None = Field(default=None, ge=0)
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


class CurrentMarketInput(StrictModel):
    """Narrow P8A input: market value context without any activity feature."""

    symbol: str = Field(pattern=r"^\d{6}$")
    name: str
    trade_date: str
    close: float | None = None
    total_market_value: float | None = None
    source_snapshot_id: str
    source_digest: str


class CurrentScenarioMap(StrictModel):
    map_id: str = Field(pattern=r"^P8MAP-[A-F0-9]{20}$")
    symbol: str = Field(pattern=r"^\d{6}$")
    available_as_of: str
    stage: str
    stage_source: str
    process_direction: str
    old_equity_effect: str
    delisting_risk_type: str
    board: str
    regime_version: str
    current_total_mv: float | None = None
    current_old_equity_value: float | None = None
    reference_family: Literal[
        "strategic_entry_reference", "failure_exit_reference", "public_node_reference"
    ]
    reference_layer: str
    reference_status: Literal["distribution", "raw_points_only", "empty"]
    reference_n: int
    reference_company_n: int
    reference_median: float | None = None
    reference_window_months: int
    relaxation_path: list[str]
    position_pct_in_layer: float | None = None
    scenario_implied_weight: float | None = None
    scenario_consistency_status: str
    cross_company_sensitivity_weight: float | None = None
    cross_company_sensitivity_status: str = "input_unknown"
    distance_to_par_delisting_pct: float | None = None
    distance_to_mv_delisting_pct: float | None = None
    days_since_last_verified_node: int | None = Field(default=None, ge=0)
    next_possible_successors: list[str]
    data_gaps: list[str]
    source_ids: list[str]
    calculation_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_status: Literal["derived_point_in_time", "partial", "unknown"]
    not_a_fair_value_claim: Literal[True] = True


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
    current_member_count: int
    current_map_count: int
    current_market_value_count: int
    current_known_stage_count: int


class StrategicTerms(StrictModel):
    transaction_price_per_share: float | None = None
    transferred_shares: float | None = None
    transaction_consideration: float | None = None
    post_restructuring_total_shares: float | None = None
    headline_post_money: float | None = None
    old_shareholder_retained_shares: float | None = None
    old_shareholder_retained_ratio: float | None = None
    creditor_compensation_shares: float | None = None
    cash_investment: float | None = None
    share_conversion_ratio_raw: str = ""
    share_transfer_ratio_raw: str = ""
    lockup_period_raw: str = ""
    industrial_commitment_raw: str = ""
    arithmetic_closed: bool
    contamination_flags: list[str]


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
    value_status: str, old_equity_value: float | None = None,
    transaction_price_per_share: float | None = None,
    transferred_shares: float | None = None,
    transaction_consideration: float | None = None,
    post_restructuring_total_shares: float | None = None,
    headline_post_money: float | None = None,
    old_shareholder_retained_shares: float | None = None,
    old_shareholder_retained_ratio: float | None = None,
    creditor_compensation_shares: float | None = None,
    cash_investment: float | None = None,
    share_conversion_ratio_raw: str = "",
    share_transfer_ratio_raw: str = "",
    lockup_period_raw: str = "",
    industrial_commitment_raw: str = "",
    total_loss_stress: float | None = None,
    market_endpoint_status: str = "not_applicable",
    market_endpoint_delay_rows: int | None = None,
) -> ScenarioReference:
    identity = {
        "contract": CONTRACT_VERSION, "family": family, "symbol": symbol,
        "available_as_of": available_as_of, "stage": stage,
        "source_ids": sorted(source_ids), "total_mv": total_mv,
        "old_equity_value": old_equity_value,
        "transaction_price_per_share": transaction_price_per_share,
        "transferred_shares": transferred_shares,
        "transaction_consideration": transaction_consideration,
        "post_restructuring_total_shares": post_restructuring_total_shares,
        "headline_post_money": headline_post_money,
        "old_shareholder_retained_shares": old_shareholder_retained_shares,
        "old_shareholder_retained_ratio": old_shareholder_retained_ratio,
        "creditor_compensation_shares": creditor_compensation_shares,
        "cash_investment": cash_investment,
        "share_conversion_ratio_raw": share_conversion_ratio_raw,
        "share_transfer_ratio_raw": share_transfer_ratio_raw,
        "lockup_period_raw": lockup_period_raw,
        "industrial_commitment_raw": industrial_commitment_raw,
        "total_loss_stress": total_loss_stress,
        "market_endpoint_status": market_endpoint_status,
        "market_endpoint_delay_rows": market_endpoint_delay_rows,
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
        old_equity_value=old_equity_value,
        transaction_price_per_share=transaction_price_per_share,
        transferred_shares=transferred_shares,
        transaction_consideration=transaction_consideration,
        post_restructuring_total_shares=post_restructuring_total_shares,
        headline_post_money=headline_post_money,
        old_shareholder_retained_shares=old_shareholder_retained_shares,
        old_shareholder_retained_ratio=old_shareholder_retained_ratio,
        creditor_compensation_shares=creditor_compensation_shares,
        cash_investment=cash_investment,
        share_conversion_ratio_raw=share_conversion_ratio_raw,
        share_transfer_ratio_raw=share_transfer_ratio_raw,
        lockup_period_raw=lockup_period_raw,
        industrial_commitment_raw=industrial_commitment_raw,
        total_loss_stress=total_loss_stress,
        market_endpoint_status=market_endpoint_status,
        market_endpoint_delay_rows=market_endpoint_delay_rows,
        value_status=value_status,  # type: ignore[arg-type]
        contamination_flags=sorted(set(contamination)),
        source_ids=sorted(source_ids),
        evidence_status=evidence_status,
    )


def _scaled_number(value: str, unit: str) -> float | None:
    text = f"{value}{unit}".replace(",", "").replace("，", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if match is None:
        return None
    number = float(match.group(0))
    suffix = text[match.end():]
    if "亿" in suffix:
        number *= 100_000_000
    elif "万" in suffix:
        number *= 10_000
    return number


def _fact_values(extraction: dict[str, Any], fact_type: str) -> list[dict[str, Any]]:
    return [
        item for item in (extraction.get("key_facts") or [])
        if item.get("fact_type") == fact_type and item.get("evidence_quote")
    ]


def _unique_numeric_fact(extraction: dict[str, Any], fact_type: str) -> float | None:
    values = {
        value for item in _fact_values(extraction, fact_type)
        if (value := _scaled_number(str(item.get("value") or ""), str(item.get("unit") or ""))) is not None
    }
    return next(iter(values)) if len(values) == 1 else None


def _unique_raw_fact(extraction: dict[str, Any], fact_type: str) -> str:
    values = {
        f"{item.get('value') or ''}{item.get('unit') or ''}"
        for item in _fact_values(extraction, fact_type)
    }
    return next(iter(values)) if len(values) == 1 else ""


def strategic_terms(
    extraction: dict[str, Any], *, event_evidence_status: str,
) -> StrategicTerms:
    price = _unique_numeric_fact(extraction, "strategic_entry_price")
    transferred = _unique_numeric_fact(extraction, "transferred_share_count")
    post_total = _unique_numeric_fact(extraction, "post_restructuring_total_share_count")
    retained = _unique_numeric_fact(extraction, "old_shareholder_retained_share_count")
    transfer_ratio = _unique_raw_fact(extraction, "share_transfer_ratio")
    conversion_ratio = _unique_raw_fact(extraction, "share_conversion_ratio")
    creditor_shares = _unique_numeric_fact(extraction, "creditor_compensation_share_count")
    cash = _unique_numeric_fact(extraction, "cash_investment")
    lockup = _unique_raw_fact(extraction, "lockup_period")
    industrial = _unique_raw_fact(extraction, "industrial_commitment")
    arithmetic_closed = bool(
        event_evidence_status == "body_verified"
        and extraction.get("evidence_status") == "body_verified"
        and all(value is not None and value > 0 for value in (price, transferred, post_total, retained))
        and bool(transfer_ratio)
        and retained is not None and post_total is not None and retained <= post_total
        and transferred is not None and transferred <= post_total
    )
    contamination = []
    if cash is not None or industrial:
        contamination.append("package_contaminated")
    if not arithmetic_closed:
        contamination.extend([
            "transaction_terms_not_closed",
            "old_shareholder_equity_not_exact",
        ])
    return StrategicTerms(
        transaction_price_per_share=price,
        transferred_shares=transferred,
        transaction_consideration=(
            price * transferred
            if price is not None and price > 0 and transferred is not None and transferred > 0
            else None
        ),
        post_restructuring_total_shares=post_total,
        headline_post_money=(
            price * post_total
            if price is not None and price > 0 and post_total is not None and post_total > 0
            else None
        ),
        old_shareholder_retained_shares=retained,
        old_shareholder_retained_ratio=(
            retained / post_total
            if retained is not None and retained > 0 and post_total is not None and post_total > 0
            else None
        ),
        creditor_compensation_shares=creditor_shares,
        cash_investment=cash,
        share_conversion_ratio_raw=conversion_ratio,
        share_transfer_ratio_raw=transfer_ratio,
        lockup_period_raw=lockup,
        industrial_commitment_raw=industrial,
        arithmetic_closed=arithmetic_closed,
        contamination_flags=contamination,
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
    extractions = repository.records(
        run_id=event_run.run_id, record_type="llm_announcement_extraction"
    )
    extraction_by_announcement = {
        str(item.get("announcement_id") or ""): item for item in extractions
    }
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
            extraction = next((
                extraction_by_announcement[source_id]
                for source_id in source_ids if source_id in extraction_by_announcement
            ), {})
            terms = strategic_terms(
                extraction, event_evidence_status=evidence_status,
            )
            strategic_source_ids = source_ids + (
                [str(extraction.get("record_id"))] if extraction.get("record_id") else []
            )
            references.append(_reference(
                family="strategic_entry_reference", symbol=symbol,
                available_as_of=str(event["available_as_of"]),
                stage="investor_agreement_signed", stage_source=evidence_status,
                base_database=base_database, total_mv=None, source_ids=strategic_source_ids,
                evidence_status=evidence_status,
                contamination=terms.contamination_flags,
                value_status="exact_old_equity" if terms.arithmetic_closed else "raw_terms_only",
                old_equity_value=(
                    terms.transaction_price_per_share * terms.old_shareholder_retained_shares
                    if terms.arithmetic_closed
                    and terms.transaction_price_per_share is not None
                    and terms.old_shareholder_retained_shares is not None else None
                ),
                transaction_price_per_share=terms.transaction_price_per_share,
                transferred_shares=terms.transferred_shares,
                transaction_consideration=terms.transaction_consideration,
                post_restructuring_total_shares=terms.post_restructuring_total_shares,
                headline_post_money=terms.headline_post_money,
                old_shareholder_retained_shares=terms.old_shareholder_retained_shares,
                old_shareholder_retained_ratio=terms.old_shareholder_retained_ratio,
                creditor_compensation_shares=terms.creditor_compensation_shares,
                cash_investment=terms.cash_investment,
                share_conversion_ratio_raw=terms.share_conversion_ratio_raw,
                share_transfer_ratio_raw=terms.share_transfer_ratio_raw,
                lockup_period_raw=terms.lockup_period_raw,
                industrial_commitment_raw=terms.industrial_commitment_raw,
            ))
        if node in {"formal_restructuring_accepted", "plan_approved", "plan_executed", "risk_warning_removed"}:
            flags = ["old_shareholder_ledger_not_closed_at_node"]
            if total_mv is None:
                flags.append("point_in_time_market_value_missing")
            references.append(_reference(
                family="public_node_reference", symbol=symbol,
                available_as_of=entry_date or str(event["available_as_of"]),
                stage=_stage_for_node(node), stage_source=evidence_status,
                base_database=base_database, total_mv=total_mv, source_ids=source_ids,
                evidence_status=evidence_status, contamination=flags,
                value_status="total_mv_fact_only" if total_mv is not None else "unknown",
                market_endpoint_status=str(
                    path.get("entry_tradeability_status") or "unavailable"
                ),
                market_endpoint_delay_rows=int(path.get("entry_delay_price_rows") or 0),
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
        terminal_flags = ["exchange_terminal_date_unverified"]
        if total_mv is None:
            terminal_flags.append("last_exchange_market_value_missing")
        references.append(_reference(
            family="failure_exit_reference", symbol=symbol,
            available_as_of=last_date,
            stage=str(path.get("anchor_node") or "unknown"),
            stage_source=str(path.get("evidence_status") or "unknown"),
            base_database=base_database, total_mv=total_mv,
            source_ids=[str(path.get("path_id") or "")],
            evidence_status=str(path.get("evidence_status") or "unknown"),
            contamination=terminal_flags,
            value_status="total_mv_fact_only" if total_mv is not None else "unknown",
            total_loss_stress=_number(path.get("total_loss_stress")),
            market_endpoint_status=(
                "last_observed_exchange_price_terminal_unverified"
                if last_date else "unavailable"
            ),
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


def _adjacent_stage_group(stage: str) -> set[str]:
    adjacent = {
        "distress_entry": {"st_distress_only", "restructuring_application_disclosed"},
        "pre_judicial": {"pre_restructuring_started", "investor_recruitment"},
        "formal_process": {"formal_restructuring_accepted", "investor_agreement_signed"},
        "plan_resolution": {"plan_key_terms_disclosed", "plan_approved"},
        "execution_exit": {"plan_executed", "risk_warning_removed"},
    }
    return next((members for members in adjacent.values() if stage in members), {stage})


def _reference_points_for_attempt(
    references: list[ScenarioReference], *, family: str, as_of: str,
    stage: str, risk_type: str, board: str, regime_version: str,
    attempt: str, window: int, exclude_symbol: str | None = None,
) -> list[ScenarioReference]:
    start = _months_before(as_of, window)
    group = _adjacent_stage_group(stage)
    selected: list[ScenarioReference] = []
    for item in references:
        if (
            item.family != family
            or (exclude_symbol is not None and item.symbol == exclude_symbol)
            or item.regime_version != regime_version
            or item.delisting_risk_type != risk_type
            or not start <= item.available_as_of <= as_of
            or item.old_equity_value is None
        ):
            continue
        if attempt == "exact" and not (item.stage == stage and item.board == board):
            continue
        if attempt == "drop_board" and item.stage != stage:
            continue
        if attempt == "adjacent_stage_group" and item.stage not in group:
            continue
        selected.append(item)
    return selected


def build_distribution(
    references: list[ScenarioReference], *, family: str, as_of: str,
    stage: str, risk_type: str, board: str, regime_version: str,
    exclude_symbol: str | None = None,
) -> ReferenceDistribution:
    attempts = [
        ("exact", 12, ["exact"]),
        ("drop_board", 12, ["exact", "drop_board"]),
        ("adjacent_stage_group", 12, ["exact", "drop_board", "adjacent_stage_group"]),
        (
            "adjacent_stage_group", 18,
            ["exact", "drop_board", "adjacent_stage_group", "window_18m"],
        ),
        (
            "adjacent_stage_group", 24,
            ["exact", "drop_board", "adjacent_stage_group", "window_18m", "window_24m"],
        ),
    ]
    last_points: list[ScenarioReference] = []
    last_path: list[str] = ["exact", "drop_board", "adjacent_stage_group", "window_18m", "window_24m"]
    last_window = 24
    for attempt, window, path in attempts:
        selected = _reference_points_for_attempt(
            references, family=family, as_of=as_of, stage=stage,
            risk_type=risk_type, board=board, regime_version=regime_version,
            attempt=attempt, window=window, exclude_symbol=exclude_symbol,
        )
        last_points, last_path, last_window = selected, path, window
        companies = {item.symbol for item in selected}
        if len(selected) >= MIN_OBSERVATIONS and len(companies) >= MIN_COMPANIES:
            values = sorted(float(item.old_equity_value) for item in selected if item.old_equity_value is not None)
            return ReferenceDistribution(
                family=family, as_of=as_of,
                layer_key=f"{stage}|{risk_type}|{board}|{regime_version}",
                relaxation_path=path,
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


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _current_market_inputs(
    path: Path, *, through: str,
) -> tuple[str, str, list[CurrentMarketInput]]:
    """Load only the narrow market-value fields P8A is allowed to consume."""

    with _connect_ro(path) as connection:
        snapshot = connection.execute(
            "select snapshot_id,content_digest from activity_snapshots "
            "where trade_date=? order by fetched_at desc,snapshot_id desc limit 1",
            (through,),
        ).fetchone()
        if snapshot is None:
            raise ValueError(f"P8A 缺少 {through} 的 point-in-time market snapshot")
        rows = connection.execute(
            "select payload_json from market_activity_daily where snapshot_id=? order by symbol",
            (str(snapshot["snapshot_id"]),),
        ).fetchall()
    inputs: list[CurrentMarketInput] = []
    for row in rows:
        payload = json.loads(str(row[0]))
        total_mv_10k = _number(payload.get("total_mv_10k_cny"))
        inputs.append(CurrentMarketInput(
            symbol=str(payload.get("symbol") or ""),
            name=str(payload.get("name") or ""),
            trade_date=str(payload.get("trade_date") or ""),
            close=_number(payload.get("close")),
            total_market_value=(total_mv_10k * 10_000 if total_mv_10k is not None else None),
            source_snapshot_id=str(snapshot["snapshot_id"]),
            source_digest=str(snapshot["content_digest"]),
        ))
    return str(snapshot["snapshot_id"]), str(snapshot["content_digest"]), inputs


def current_market_input_digest(inputs: list[CurrentMarketInput]) -> str:
    """Hash only P8A economic inputs, excluding mixed-snapshot provenance metadata."""

    semantic = [
        item.model_dump(mode="json", exclude={"source_snapshot_id", "source_digest"})
        for item in sorted(inputs, key=lambda value: value.symbol)
    ]
    return hashlib.sha256(
        json.dumps(semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _open_episode_states(path: Path) -> tuple[str, str, dict[str, dict[str, Any]]]:
    with _connect_ro(path) as connection:
        run = connection.execute(
            "select run_id,as_of from valuation_episode_runs order by as_of desc,rowid desc limit 1"
        ).fetchone()
        rows = connection.execute(
            "select payload_json from valuation_episodes where evidence_status='verified'"
        ).fetchall()
    states: dict[str, dict[str, Any]] = {}
    for row in rows:
        payload = json.loads(str(row[0]))
        if bool(payload.get("is_open")):
            states[str(payload.get("symbol") or "")] = payload
    return (
        str(run["run_id"]) if run else "",
        str(run["as_of"]) if run else "",
        states,
    )


def _position_percentile(value: float | None, points: list[ScenarioReference]) -> float | None:
    values = sorted(float(item.old_equity_value) for item in points if item.old_equity_value is not None)
    if value is None or not values:
        return None
    below_or_equal = sum(item <= value for item in values)
    return below_or_equal / len(values)


def build_current_scenario_maps(
    *, repository: P8ResearchRepository, base_database: Path,
    market_activity_database: Path, valuation_episode_database: Path,
    references: list[ScenarioReference], through: str,
) -> tuple[str, str, str, str, list[CurrentScenarioMap]]:
    event_run = repository.latest_run("event_graph")
    if event_run is None:
        raise ValueError("P8A current map 需要 event_graph")
    events = repository.records(run_id=event_run.run_id, record_type="derived_event")
    frontiers = repository.records(run_id=event_run.run_id, record_type="company_frontier")
    event_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event.get("evidence_status") in {"body_verified", "deterministic_verified"}:
            event_by_symbol[str(event.get("symbol") or "")].append(event)
    frontier_by_symbol = {str(item.get("symbol") or ""): item for item in frontiers}
    valuation_run_id, valuation_checked_through, episode_states = _open_episode_states(
        valuation_episode_database
    )
    snapshot_id, snapshot_digest, market_inputs = _current_market_inputs(
        market_activity_database, through=through,
    )
    semantic_market_digest = current_market_input_digest(market_inputs)
    families = (
        "strategic_entry_reference", "failure_exit_reference", "public_node_reference",
    )
    maps: list[CurrentScenarioMap] = []
    for market in market_inputs:
        frontier = frontier_by_symbol.get(market.symbol, {})
        membership_start = str(frontier.get("membership_start_date") or through)
        episode = episode_states.get(market.symbol)
        stage = str((episode or {}).get("current_stage") or "unknown")
        stage_source = (
            f"p6b3_verified:{valuation_run_id}@{valuation_checked_through}"
            if episode else "unknown"
        )
        source_ids = [market.source_snapshot_id]
        gaps: list[str] = []
        if episode:
            source_ids.append(str(episode.get("episode_id") or ""))
        else:
            gaps.append("verified_current_episode_missing")
        if valuation_checked_through and valuation_checked_through < through:
            gaps.append(f"valuation_stage_checked_through_{valuation_checked_through}")
        eligible_events = sorted(
            [
                item for item in event_by_symbol.get(market.symbol, [])
                if membership_start <= str(item.get("available_as_of") or "") <= through
            ],
            key=lambda item: (str(item.get("available_as_of") or ""), str(item.get("event_id") or "")),
        )
        last_event = eligible_events[-1] if eligible_events else None
        if last_event and (
            not valuation_checked_through
            or str(last_event.get("available_as_of") or "") > valuation_checked_through
            or stage == "unknown"
        ):
            derived_stage = _stage_for_node(str(last_event.get("node") or ""))
            if derived_stage != "unknown":
                stage = derived_stage
                stage_source = f"p8_{last_event.get('evidence_status')}:{last_event.get('event_id')}"
        if stage == "unknown":
            gaps.append("current_stage_unknown")
        if last_event:
            source_ids.extend(list(last_event.get("source_ids") or []))
        risk_type = _risk_type(base_database, symbol=market.symbol, day=through)
        if risk_type == "unknown":
            gaps.append("delisting_risk_type_unknown")
        if market.total_market_value is None:
            gaps.append("current_total_market_value_missing")
        current_old_equity_value: float | None = None
        gaps.extend([
            "current_old_equity_claim_not_closed",
            "market_value_delisting_threshold_not_registered",
        ])
        distributions = {
            family: build_distribution(
                references, family=family, as_of=through, stage=stage,
                risk_type=risk_type, board=_board(market.symbol),
                regime_version=regime_for_date(through).regime_version,
                exclude_symbol=market.symbol,
            )
            for family in families
        }
        failure_median = distributions["failure_exit_reference"].median
        for family in families:
            distribution = distributions[family]
            attempt = (
                "adjacent_stage_group" if "adjacent_stage_group" in distribution.relaxation_path
                else "drop_board" if "drop_board" in distribution.relaxation_path
                else "exact"
            )
            points = _reference_points_for_attempt(
                references, family=family, as_of=through, stage=stage,
                risk_type=risk_type, board=_board(market.symbol),
                regime_version=regime_for_date(through).regime_version,
                attempt=attempt, window=distribution.window_months,
                exclude_symbol=market.symbol,
            )
            success = distribution.median if family != "failure_exit_reference" else None
            cross_weight, cross_consistency = scenario_weight(
                current=current_old_equity_value,
                failure=failure_median,
                success=success,
            )
            family_gaps = list(gaps)
            if distribution.status != "distribution":
                family_gaps.append(f"{family}_distribution_{distribution.status}")
            identity = {
                "contract": CONTRACT_VERSION,
                "symbol": market.symbol,
                "through": through,
                "family": family,
                "current_total_mv": market.total_market_value,
                "current_close": market.close,
                "stage": stage,
                "distribution": distribution.model_dump(mode="json"),
            }
            calculation_digest = hashlib.sha256(
                json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            maps.append(CurrentScenarioMap(
                map_id=content_id("P8MAP", identity),
                symbol=market.symbol,
                available_as_of=through,
                stage=stage,
                stage_source=stage_source,
                process_direction=str((last_event or {}).get("process_direction") or "unknown"),
                old_equity_effect=str((last_event or {}).get("old_equity_effect") or "unknown"),
                delisting_risk_type=risk_type,
                board=_board(market.symbol),
                regime_version=regime_for_date(through).regime_version,
                current_total_mv=market.total_market_value,
                current_old_equity_value=current_old_equity_value,
                reference_family=family,  # type: ignore[arg-type]
                reference_layer=distribution.layer_key,
                reference_status=distribution.status,
                reference_n=distribution.n,
                reference_company_n=distribution.company_n,
                reference_median=distribution.median,
                reference_window_months=distribution.window_months,
                relaxation_path=distribution.relaxation_path,
                position_pct_in_layer=(
                    _position_percentile(current_old_equity_value, points)
                    if distribution.status == "distribution" else None
                ),
                scenario_implied_weight=None,
                scenario_consistency_status="company_specific_inputs_unavailable",
                cross_company_sensitivity_weight=cross_weight,
                cross_company_sensitivity_status=cross_consistency,
                distance_to_par_delisting_pct=(market.close - 1.0) if market.close is not None else None,
                distance_to_mv_delisting_pct=None,
                days_since_last_verified_node=(
                    (date.fromisoformat(through) - date.fromisoformat(str(last_event["available_as_of"]))).days
                    if last_event else None
                ),
                next_possible_successors=list((last_event or {}).get("possible_successors") or []),
                data_gaps=sorted(set(family_gaps)),
                source_ids=sorted({item for item in source_ids if item}),
                calculation_digest=calculation_digest,
                evidence_status=(
                    "partial" if market.total_market_value is not None else "unknown"
                ),
            ))
    return valuation_run_id, snapshot_id, snapshot_digest, semantic_market_digest, maps


def materialize_references(
    *, repository: P8ResearchRepository, base_database: Path,
    market_factor_database: Path, market_activity_database: Path,
    valuation_episode_database: Path, through: str,
) -> ReferenceMaterializationResult:
    references = build_reference_points(
        repository=repository, base_database=base_database,
        market_factor_database=market_factor_database,
    )
    (
        valuation_run_id,
        market_snapshot_id,
        market_snapshot_digest,
        semantic_market_digest,
        current_maps,
    ) = build_current_scenario_maps(
        repository=repository,
        base_database=base_database,
        market_activity_database=market_activity_database,
        valuation_episode_database=valuation_episode_database,
        references=references,
        through=through,
    )
    records = {
        "scenario_reference": [
            {**item.model_dump(mode="json"), "record_id": item.reference_id}
            for item in references
        ],
        "current_scenario_map": [
            {**item.model_dump(mode="json"), "record_id": item.map_id}
            for item in current_maps
        ],
    }
    event_run = repository.latest_run("event_graph")
    return_run = repository.latest_run("return_paths")
    run = build_run(
        run_kind="scenario_references", contract_version=CONTRACT_VERSION,
        start_date=min((item.available_as_of for item in references), default=through),
        through=through,
        source_run_ids=[
            *[item.run_id for item in (event_run, return_run) if item],
            *([valuation_run_id] if valuation_run_id else []),
            market_snapshot_id,
        ],
        source_digests={
            "base_database": _file_digest(base_database),
            "market_factors_v1": _file_digest(market_factor_database),
            "current_market_economic_input": semantic_market_digest,
            "current_market_snapshot_provenance": market_snapshot_digest,
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
        p_star_calculable_count=sum(
            item.scenario_implied_weight is not None for item in current_maps
        ),
        regime_registry_version=REGISTRY_VERSION,
        current_member_count=len({item.symbol for item in current_maps}),
        current_map_count=len(current_maps),
        current_market_value_count=len({item.symbol for item in current_maps if item.current_total_mv is not None}),
        current_known_stage_count=len({item.symbol for item in current_maps if item.stage != "unknown"}),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through", required=True)
    parser.add_argument("--base-database", type=Path, default=DEFAULT_BASE_DB)
    parser.add_argument("--market-factor-database", type=Path, default=MARKET_FACTOR_DB)
    parser.add_argument("--market-activity-database", type=Path, default=MARKET_ACTIVITY_DB)
    parser.add_argument("--valuation-episode-database", type=Path, default=VALUATION_EPISODE_DB)
    parser.add_argument("--repository", type=Path, default=P8_RESEARCH_DB)
    parser.add_argument("--output-json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = materialize_references(
        repository=P8ResearchRepository(args.repository),
        base_database=args.base_database,
        market_factor_database=args.market_factor_database,
        market_activity_database=args.market_activity_database,
        valuation_episode_database=args.valuation_episode_database,
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
