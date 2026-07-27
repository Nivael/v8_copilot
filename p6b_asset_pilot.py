"""P6B-2 point-in-time asset facts and old-shareholder equity pilot.

Reported accounting data is stored as evidence, never promoted to recoverable
asset value.  The valuation state remains unknown until independently verified
recoverable assets and obligations are supplied on the same as-of basis.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from data_refresh import TushareHttpClient


CONTRACT_VERSION = "v8_p6b2_asset_equity_pilot_v1"
FACT_STORE_VERSION = "valuation_facts_v1"
RISK_CATEGORIES = (
    "restatement",
    "guarantee",
    "litigation",
    "fund_occupation",
    "asset_disposal",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PilotSymbol(StrictModel):
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    episode_start_date: str
    selection_tags: list[str]


class PilotManifest(StrictModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    pilot_id: str
    as_of: str
    financial_statement_start: str
    missing_liability_shock_pct_total_assets: list[float]
    selection_rule: str
    symbols: list[PilotSymbol] = Field(min_length=5, max_length=10)

    @model_validator(mode="after")
    def validate_frozen_scope(self) -> "PilotManifest":
        if len({item.symbol for item in self.symbols}) != len(self.symbols):
            raise ValueError("pilot symbols 不得重复")
        if self.missing_liability_shock_pct_total_assets != [0.0, 0.05, 0.1, 0.2]:
            raise ValueError("missing-liability shock grid 已冻结为 0/5/10/20%")
        _iso_date(self.as_of, field="as_of")
        _iso_date(self.financial_statement_start, field="financial_statement_start")
        for item in self.symbols:
            if _iso_date(item.episode_start_date, field="episode_start_date") > self.as_of:
                raise ValueError(f"{item.symbol} episode 起点晚于 pilot as_of")
        return self


class FinancialStatementFact(StrictModel):
    fact_id: str
    symbol: str
    available_date: str
    announcement_date: str
    period_end: str
    report_type: str
    update_flag: str
    total_assets: float | None = None
    total_liabilities: float | None = None
    total_equity_including_minority: float | None = None
    equity_excluding_minority: float | None = None
    cash: float | None = None
    receivables: float | None = None
    inventory: float | None = None
    fixed_assets: float | None = None
    intangible_assets: float | None = None
    goodwill: float | None = None
    current_liabilities: float | None = None
    noncurrent_liabilities: float | None = None
    source_ref: str
    raw_digest: str


class AuditOpinionFact(StrictModel):
    fact_id: str
    symbol: str
    available_date: str
    period_end: str
    result: str
    agency: str
    source_ref: str
    raw_digest: str


class FinancialIndicatorFact(StrictModel):
    fact_id: str
    symbol: str
    available_date: str
    period_end: str
    current_ratio: float | None = None
    quick_ratio: float | None = None
    debt_to_assets: float | None = None
    operating_cashflow_to_short_debt: float | None = None
    update_flag: str
    source_ref: str
    raw_digest: str


class RiskDisclosureFact(StrictModel):
    fact_id: str
    symbol: str
    available_date: str
    category: Literal[
        "restatement", "guarantee", "litigation", "fund_occupation", "asset_disposal"
    ]
    title: str
    announcement_id: str
    body_available: bool
    amount_status: Literal["unknown"] = "unknown"
    source_ref: str


class ReportedAccountingBaseline(StrictModel):
    status: Literal["available", "unavailable"]
    period_end: str = ""
    available_date: str = ""
    total_assets: float | None = None
    total_liabilities: float | None = None
    reported_net_assets: float | None = None
    accounting_identity_status: Literal["passes", "mismatch", "not_testable"]
    audit_result: str = ""
    audit_available_date: str = ""
    basis: Literal["reported_accounting_only"] = "reported_accounting_only"
    warning: str = (
        "账面数仅作事实语境；未经独立回收率/处置证据核证，不是可回收资产底座。"
    )


class LiabilitySensitivity(StrictModel):
    shock_pct_total_assets: float
    additional_liability: float
    reported_net_assets_after_shock: float
    reported_solvency_gap_after_shock: float
    basis: Literal["reported_accounting_only"] = "reported_accounting_only"


class AssetMap(StrictModel):
    status: Literal["positive", "negative", "unknown"]
    recoverable_assets_min: float | None = None
    recoverable_assets_max: float | None = None
    known_obligations_min: float | None = None
    known_obligations_max: float | None = None
    adjusted_net_assets_min: float | None = None
    adjusted_net_assets_max: float | None = None
    equity_asset_backing_min: float | None = None
    equity_asset_backing_max: float | None = None
    solvency_gap_min: float | None = None
    solvency_gap_max: float | None = None
    market_residual_status: Literal["calculable", "not_calculable"]
    calibration_status: Literal["uncalibrated", "independently_verified"]
    evidence_refs: list[str]
    reason: str


class SharePoint(StrictModel):
    trade_date: str
    total_shares: float
    snapshot_id: str
    source_ref: str


class OldShareholderLedger(StrictModel):
    status: Literal[
        "unknown", "no_detected_share_change", "range_only", "exact"
    ]
    start: SharePoint | None = None
    end: SharePoint | None = None
    total_share_change: float | None = None
    gross_share_count_ratio: float | None = None
    per_share_dilution_factor: float | None = None
    allocation_status: Literal["unknown", "verified"]
    consideration_status: Literal["unknown", "verified"]
    exact_closure: bool
    reason: str


class PilotCaseResult(StrictModel):
    symbol: str
    episode_start_date: str
    as_of: str
    selection_tags: list[str]
    statement_fact_count: int
    audit_fact_count: int
    indicator_fact_count: int
    risk_fact_count_by_category: dict[str, int]
    risk_amounts_unknown: int
    baseline: ReportedAccountingBaseline
    missing_liability_sensitivity: list[LiabilitySensitivity]
    asset_map: AssetMap
    old_shareholder_ledger: OldShareholderLedger
    decision_clusters: list[str]


class PilotResult(StrictModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    run_id: str
    pilot_id: str
    as_of: str
    generated_at: str
    fact_store_version: Literal[FACT_STORE_VERSION] = FACT_STORE_VERSION
    source_manifest_digest: str
    cases: list[PilotCaseResult]
    exact_ledger_count: int
    non_exact_ledger_count: int
    full_scale_equity_output: Literal["exact", "range_primary"]
    decision_cluster_count: int
    review_budget_status: Literal["within_budget", "exceeded"]
    conclusions: list[str]


def _iso_date(value: object, *, field: str) -> str:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是 YYYY-MM-DD: {value!r}") from exc


def _provider_date(value: object) -> str:
    raw = str(value or "")
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return _iso_date(raw, field="provider_date") if raw else ""


def _number(value: object) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _canonical(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _fact_id(prefix: str, value: Any) -> str:
    return f"{prefix}-{_digest(value)[:20].upper()}"


def compute_asset_map(
    *,
    recoverable_assets_min: float | None,
    recoverable_assets_max: float | None,
    known_obligations_min: float | None,
    known_obligations_max: float | None,
    evidence_refs: list[str],
    independently_verified: bool,
) -> AssetMap:
    values = (
        recoverable_assets_min,
        recoverable_assets_max,
        known_obligations_min,
        known_obligations_max,
    )
    if not independently_verified or any(value is None for value in values):
        return AssetMap(
            status="unknown",
            market_residual_status="not_calculable",
            calibration_status="uncalibrated",
            evidence_refs=evidence_refs,
            reason="缺少同一时点、独立核证的可回收资产和已知义务区间。",
        )
    assert recoverable_assets_min is not None
    assert recoverable_assets_max is not None
    assert known_obligations_min is not None
    assert known_obligations_max is not None
    if recoverable_assets_min > recoverable_assets_max:
        raise ValueError("recoverable asset interval 非法")
    if known_obligations_min > known_obligations_max:
        raise ValueError("known obligation interval 非法")
    adjusted_min = recoverable_assets_min - known_obligations_max
    adjusted_max = recoverable_assets_max - known_obligations_min
    if adjusted_min > 0:
        status: Literal["positive", "negative", "unknown"] = "positive"
    elif adjusted_max < 0:
        status = "negative"
    else:
        status = "unknown"
    return AssetMap(
        status=status,
        recoverable_assets_min=recoverable_assets_min,
        recoverable_assets_max=recoverable_assets_max,
        known_obligations_min=known_obligations_min,
        known_obligations_max=known_obligations_max,
        adjusted_net_assets_min=adjusted_min,
        adjusted_net_assets_max=adjusted_max,
        equity_asset_backing_min=max(adjusted_min, 0),
        equity_asset_backing_max=max(adjusted_max, 0),
        solvency_gap_min=max(-adjusted_max, 0),
        solvency_gap_max=max(-adjusted_min, 0),
        market_residual_status=(
            "calculable" if status in {"positive", "negative"} else "not_calculable"
        ),
        calibration_status="independently_verified",
        evidence_refs=evidence_refs,
        reason=(
            "独立证据区间整体为正。"
            if status == "positive"
            else "独立证据区间整体为负。"
            if status == "negative"
            else "独立证据区间跨越零，保持 unknown。"
        ),
    )


def _normalize_statement(raw: dict[str, Any], *, symbol: str, as_of: str) -> FinancialStatementFact | None:
    available = _provider_date(raw.get("f_ann_date") or raw.get("ann_date"))
    if not available or available > as_of:
        return None
    payload = dict(raw)
    return FinancialStatementFact(
        fact_id=_fact_id("VF-BS", payload),
        symbol=symbol,
        available_date=available,
        announcement_date=_provider_date(raw.get("ann_date")) or available,
        period_end=_provider_date(raw.get("end_date")),
        report_type=str(raw.get("report_type") or ""),
        update_flag=str(raw.get("update_flag") or ""),
        total_assets=_number(raw.get("total_assets")),
        total_liabilities=_number(raw.get("total_liab")),
        total_equity_including_minority=_number(raw.get("total_hldr_eqy_inc_min_int")),
        equity_excluding_minority=_number(raw.get("total_hldr_eqy_exc_min_int")),
        cash=_number(raw.get("money_cap")),
        receivables=_number(raw.get("accounts_receiv")),
        inventory=_number(raw.get("inventories")),
        fixed_assets=_number(raw.get("fix_assets")),
        intangible_assets=_number(raw.get("intan_assets")),
        goodwill=_number(raw.get("goodwill")),
        current_liabilities=_number(raw.get("total_cur_liab")),
        noncurrent_liabilities=_number(raw.get("total_ncl")),
        source_ref=f"tushare:balancesheet:{raw.get('ts_code')}:{raw.get('end_date')}",
        raw_digest=_digest(payload),
    )


def _normalize_audit(raw: dict[str, Any], *, symbol: str, as_of: str) -> AuditOpinionFact | None:
    available = _provider_date(raw.get("ann_date"))
    if not available or available > as_of:
        return None
    payload = dict(raw)
    return AuditOpinionFact(
        fact_id=_fact_id("VF-AUDIT", payload),
        symbol=symbol,
        available_date=available,
        period_end=_provider_date(raw.get("end_date")),
        result=str(raw.get("audit_result") or ""),
        agency=str(raw.get("audit_agency") or ""),
        source_ref=f"tushare:fina_audit:{raw.get('ts_code')}:{raw.get('end_date')}",
        raw_digest=_digest(payload),
    )


def _normalize_indicator(
    raw: dict[str, Any], *, symbol: str, as_of: str
) -> FinancialIndicatorFact | None:
    available = _provider_date(raw.get("ann_date"))
    if not available or available > as_of:
        return None
    payload = dict(raw)
    return FinancialIndicatorFact(
        fact_id=_fact_id("VF-FI", payload),
        symbol=symbol,
        available_date=available,
        period_end=_provider_date(raw.get("end_date")),
        current_ratio=_number(raw.get("current_ratio")),
        quick_ratio=_number(raw.get("quick_ratio")),
        debt_to_assets=_number(raw.get("debt_to_assets")),
        operating_cashflow_to_short_debt=_number(raw.get("ocf_to_shortdebt")),
        update_flag=str(raw.get("update_flag") or ""),
        source_ref=f"tushare:fina_indicator:{raw.get('ts_code')}:{raw.get('end_date')}",
        raw_digest=_digest(payload),
    )


def _risk_categories(title: str, announcement_type: str) -> list[str]:
    text = f"{title} {announcement_type}"
    patterns = {
        "restatement": r"前期差错|会计差错|追溯调整|更正公告|更正后",
        "guarantee": r"担保|被担保",
        "litigation": r"诉讼|仲裁",
        "fund_occupation": r"资金占用|非经营性占用",
        "asset_disposal": r"资产处置|司法拍卖|拍卖公告|变卖|资产转让",
    }
    return [name for name, pattern in patterns.items() if re.search(pattern, text)]


def _load_risk_facts(
    database: Path, *, symbol: str, start_date: str, as_of: str
) -> list[RiskDisclosureFact]:
    if not database.is_file():
        raise FileNotFoundError(database)
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "select announcement_id,announcement_date,announcement_type,title,url,body_text "
            "from company_announcements where symbol=? and announcement_date>=? "
            "and announcement_date<=? order by announcement_date,announcement_id",
            (symbol, start_date, as_of),
        ).fetchall()
    facts: list[RiskDisclosureFact] = []
    for row in rows:
        for category in _risk_categories(
            str(row["title"] or ""), str(row["announcement_type"] or "")
        ):
            payload = {
                "announcement_id": str(row["announcement_id"]),
                "category": category,
            }
            facts.append(
                RiskDisclosureFact(
                    fact_id=_fact_id("VF-RISK", payload),
                    symbol=symbol,
                    available_date=_iso_date(
                        row["announcement_date"], field="announcement_date"
                    ),
                    category=category,
                    title=str(row["title"] or ""),
                    announcement_id=str(row["announcement_id"]),
                    body_available=bool(str(row["body_text"] or "").strip()),
                    source_ref=str(row["url"] or f"announcement:{row['announcement_id']}"),
                )
            )
    return facts


def _latest_share_point(
    database: Path, *, symbol: str, through: str, exact_date: bool
) -> SharePoint | None:
    if not database.is_file():
        raise FileNotFoundError(database)
    comparison = "=" if exact_date else "<="
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "select d.trade_date,d.total_shares,d.snapshot_id,d.source "
            "from market_cap_daily d join market_factor_snapshots s "
            "on s.snapshot_id=d.snapshot_id where d.symbol=? "
            f"and d.trade_date{comparison}? and d.total_shares is not null "
            "order by d.trade_date desc,s.created_at desc limit 1",
            (symbol, through),
        ).fetchone()
    if row is None:
        return None
    return SharePoint(
        trade_date=str(row["trade_date"]),
        total_shares=float(row["total_shares"]),
        snapshot_id=str(row["snapshot_id"]),
        source_ref=str(row["source"]),
    )


def _old_shareholder_ledger(
    database: Path, *, symbol: str, episode_start: str, as_of: str
) -> OldShareholderLedger:
    start = _latest_share_point(
        database, symbol=symbol, through=episode_start, exact_date=True
    )
    end = _latest_share_point(database, symbol=symbol, through=as_of, exact_date=False)
    if start is None or end is None:
        return OldShareholderLedger(
            status="unknown",
            start=start,
            end=end,
            allocation_status="unknown",
            consideration_status="unknown",
            exact_closure=False,
            reason="episode 起点或截止日股本快照缺失。",
        )
    change = end.total_shares - start.total_shares
    ratio = start.total_shares / end.total_shares if end.total_shares else None
    unchanged = abs(change) <= max(1.0, start.total_shares * 1e-8)
    return OldShareholderLedger(
        status="no_detected_share_change" if unchanged else "range_only",
        start=start,
        end=end,
        total_share_change=change,
        gross_share_count_ratio=ratio,
        per_share_dilution_factor=ratio if change > 0 else None,
        allocation_status="unknown",
        consideration_status="unknown",
        exact_closure=False,
        reason=(
            "期间未检出总股本变化，但股份归属和受让对价未核证，不能宣称精确闭环。"
            if unchanged
            else "检出总股本变化；缺股份归属和受让对价，只允许范围输出。"
        ),
    )


def _baseline(
    statements: list[FinancialStatementFact],
    audits: list[AuditOpinionFact],
) -> ReportedAccountingBaseline:
    if not statements:
        return ReportedAccountingBaseline(
            status="unavailable",
            accounting_identity_status="not_testable",
        )
    latest = max(
        statements,
        key=lambda item: (item.period_end, item.available_date, item.update_flag),
    )
    audit_candidates = [item for item in audits if item.period_end <= latest.period_end]
    audit = max(
        audit_candidates, key=lambda item: (item.period_end, item.available_date)
    ) if audit_candidates else None
    assets = latest.total_assets
    liabilities = latest.total_liabilities
    net_assets = (
        assets - liabilities
        if assets is not None and liabilities is not None
        else None
    )
    if net_assets is None or latest.total_equity_including_minority is None:
        identity = "not_testable"
    else:
        tolerance = max(1.0, abs(assets or 0) * 0.005)
        identity = (
            "passes"
            if abs(net_assets - latest.total_equity_including_minority) <= tolerance
            else "mismatch"
        )
    return ReportedAccountingBaseline(
        status="available",
        period_end=latest.period_end,
        available_date=latest.available_date,
        total_assets=assets,
        total_liabilities=liabilities,
        reported_net_assets=net_assets,
        accounting_identity_status=identity,
        audit_result=audit.result if audit else "",
        audit_available_date=audit.available_date if audit else "",
    )


def _sensitivity(
    baseline: ReportedAccountingBaseline, shocks: list[float]
) -> list[LiabilitySensitivity]:
    if (
        baseline.status != "available"
        or baseline.total_assets is None
        or baseline.reported_net_assets is None
    ):
        return []
    rows = []
    for shock in shocks:
        additional = baseline.total_assets * shock
        net_assets = baseline.reported_net_assets - additional
        rows.append(
            LiabilitySensitivity(
                shock_pct_total_assets=shock,
                additional_liability=additional,
                reported_net_assets_after_shock=net_assets,
                reported_solvency_gap_after_shock=max(-net_assets, 0),
            )
        )
    return rows


class ValuationFactRepository:
    """Append-only facts and immutable pilot runs."""

    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.executescript(
            """
            create table if not exists financial_statement_facts (
                fact_id text primary key, symbol text not null, available_date text not null,
                period_end text not null, payload_json text not null
            );
            create table if not exists audit_opinion_facts (
                fact_id text primary key, symbol text not null, available_date text not null,
                period_end text not null, payload_json text not null
            );
            create table if not exists financial_indicator_facts (
                fact_id text primary key, symbol text not null, available_date text not null,
                period_end text not null, payload_json text not null
            );
            create table if not exists risk_disclosure_facts (
                fact_id text primary key, symbol text not null, available_date text not null,
                category text not null, payload_json text not null
            );
            create table if not exists pilot_runs (
                run_id text primary key, pilot_id text not null, as_of text not null,
                payload_json text not null, created_at text not null
            );
            """
        )
        return connection

    def write_facts(
        self,
        *,
        statements: list[FinancialStatementFact],
        audits: list[AuditOpinionFact],
        indicators: list[FinancialIndicatorFact],
        risks: list[RiskDisclosureFact],
    ) -> None:
        with self._connect() as connection:
            connection.executemany(
                "insert or ignore into financial_statement_facts values (?,?,?,?,?)",
                [
                    (
                        item.fact_id,
                        item.symbol,
                        item.available_date,
                        item.period_end,
                        _canonical(item.model_dump(mode="json")),
                    )
                    for item in statements
                ],
            )
            connection.executemany(
                "insert or ignore into audit_opinion_facts values (?,?,?,?,?)",
                [
                    (
                        item.fact_id,
                        item.symbol,
                        item.available_date,
                        item.period_end,
                        _canonical(item.model_dump(mode="json")),
                    )
                    for item in audits
                ],
            )
            connection.executemany(
                "insert or ignore into financial_indicator_facts values (?,?,?,?,?)",
                [
                    (
                        item.fact_id,
                        item.symbol,
                        item.available_date,
                        item.period_end,
                        _canonical(item.model_dump(mode="json")),
                    )
                    for item in indicators
                ],
            )
            connection.executemany(
                "insert or ignore into risk_disclosure_facts values (?,?,?,?,?)",
                [
                    (
                        item.fact_id,
                        item.symbol,
                        item.available_date,
                        item.category,
                        _canonical(item.model_dump(mode="json")),
                    )
                    for item in risks
                ],
            )

    def write_run(self, result: PilotResult) -> None:
        payload = _canonical(result.model_dump(mode="json"))
        with self._connect() as connection:
            existing = connection.execute(
                "select payload_json from pilot_runs where run_id=?", (result.run_id,)
            ).fetchone()
            if existing is not None:
                old = json.loads(str(existing[0]))
                new = json.loads(payload)
                old.pop("generated_at", None)
                new.pop("generated_at", None)
                if old != new:
                    raise ValueError(f"pilot run_id 冲突: {result.run_id}")
                return
            connection.execute(
                "insert or ignore into pilot_runs values (?,?,?,?,?)",
                (
                    result.run_id,
                    result.pilot_id,
                    result.as_of,
                    payload,
                    result.generated_at,
                ),
            )


def run_pilot(
    *,
    manifest: PilotManifest,
    provider: TushareHttpClient,
    base_database: Path,
    market_factor_database: Path,
    fact_repository: ValuationFactRepository,
) -> PilotResult:
    cases: list[PilotCaseResult] = []
    all_statements: list[FinancialStatementFact] = []
    all_audits: list[AuditOpinionFact] = []
    all_indicators: list[FinancialIndicatorFact] = []
    all_risks: list[RiskDisclosureFact] = []
    for item in manifest.symbols:
        raw_statements = provider.fetch_balance_sheets(
            symbol=item.symbol,
            start_date=manifest.financial_statement_start,
            end_date=manifest.as_of,
        )
        raw_audits = provider.fetch_audit_opinions(
            symbol=item.symbol,
            start_date=manifest.financial_statement_start,
            end_date=manifest.as_of,
        )
        raw_indicators = provider.fetch_financial_indicators(
            symbol=item.symbol,
            start_date=manifest.financial_statement_start,
            end_date=manifest.as_of,
        )
        statements = [
            fact
            for raw in raw_statements
            if (fact := _normalize_statement(raw, symbol=item.symbol, as_of=manifest.as_of))
        ]
        audits = [
            fact
            for raw in raw_audits
            if (fact := _normalize_audit(raw, symbol=item.symbol, as_of=manifest.as_of))
        ]
        indicators = [
            fact
            for raw in raw_indicators
            if (fact := _normalize_indicator(raw, symbol=item.symbol, as_of=manifest.as_of))
        ]
        risks = _load_risk_facts(
            base_database,
            symbol=item.symbol,
            start_date=item.episode_start_date,
            as_of=manifest.as_of,
        )
        baseline = _baseline(statements, audits)
        asset_map = compute_asset_map(
            recoverable_assets_min=None,
            recoverable_assets_max=None,
            known_obligations_min=None,
            known_obligations_max=None,
            evidence_refs=[],
            independently_verified=False,
        )
        ledger = _old_shareholder_ledger(
            market_factor_database,
            symbol=item.symbol,
            episode_start=item.episode_start_date,
            as_of=manifest.as_of,
        )
        risk_counts = {
            category: sum(fact.category == category for fact in risks)
            for category in RISK_CATEGORIES
        }
        decisions = []
        if baseline.accounting_identity_status == "mismatch":
            decisions.append("accounting_identity_mismatch")
        if ledger.status == "range_only":
            decisions.append("share_change_requires_plan_terms")
        cases.append(
            PilotCaseResult(
                symbol=item.symbol,
                episode_start_date=item.episode_start_date,
                as_of=manifest.as_of,
                selection_tags=item.selection_tags,
                statement_fact_count=len(statements),
                audit_fact_count=len(audits),
                indicator_fact_count=len(indicators),
                risk_fact_count_by_category=risk_counts,
                risk_amounts_unknown=len(risks),
                baseline=baseline,
                missing_liability_sensitivity=_sensitivity(
                    baseline, manifest.missing_liability_shock_pct_total_assets
                ),
                asset_map=asset_map,
                old_shareholder_ledger=ledger,
                decision_clusters=decisions,
            )
        )
        all_statements.extend(statements)
        all_audits.extend(audits)
        all_indicators.extend(indicators)
        all_risks.extend(risks)
    fact_repository.write_facts(
        statements=all_statements,
        audits=all_audits,
        indicators=all_indicators,
        risks=all_risks,
    )
    manifest_digest = _digest(manifest.model_dump(mode="json"))
    result_identity = {
        "contract_version": CONTRACT_VERSION,
        "pilot_id": manifest.pilot_id,
        "as_of": manifest.as_of,
        "source_manifest_digest": manifest_digest,
        "cases": [case.model_dump(mode="json") for case in cases],
    }
    run_id = f"P6B2R-{_digest(result_identity)[:20].upper()}"
    exact_count = sum(case.old_shareholder_ledger.exact_closure for case in cases)
    non_exact = len(cases) - exact_count
    clusters = sorted(
        {cluster for case in cases for cluster in case.decision_clusters}
    )
    result = PilotResult(
        run_id=run_id,
        pilot_id=manifest.pilot_id,
        as_of=manifest.as_of,
        generated_at=datetime.now(timezone.utc).isoformat(),
        source_manifest_digest=manifest_digest,
        cases=cases,
        exact_ledger_count=exact_count,
        non_exact_ledger_count=non_exact,
        full_scale_equity_output=(
            "range_primary" if non_exact > len(cases) / 2 else "exact"
        ),
        decision_cluster_count=len(clusters),
        review_budget_status="within_budget" if len(clusters) <= 10 else "exceeded",
        conclusions=[
            "财报事实可自动 point-in-time 材料化，但不得冒充可回收资产底座。",
            "没有独立处置/评估证据的公司资产状态保持 unknown，市场残差不可计算。",
            (
                "超过一半 pilot 的老股东权益账无法精确闭环；"
                "全量阶段冻结为范围输出主口径。"
                if non_exact > len(cases) / 2
                else "半数以上 pilot 精确闭环；全量仍逐案保持 fail closed。"
            ),
        ],
    )
    fact_repository.write_run(result)
    return result


def render_markdown(result: PilotResult) -> str:
    lines = [
        "# P6B-2 资产与老股东权益 pilot 结果",
        "",
        f"- run：`{result.run_id}`",
        f"- 截止：{result.as_of}",
        f"- 样本：{len(result.cases)} 家",
        f"- 资产三态：unknown {sum(c.asset_map.status == 'unknown' for c in result.cases)} 家",
        f"- 精确老股东权益账：{result.exact_ledger_count}/{len(result.cases)}",
        f"- 全量主口径：`{result.full_scale_equity_output}`",
        f"- 人审 decision cluster：{result.decision_cluster_count}（{result.review_budget_status}）",
        "",
        "## 逐家公司",
        "",
        "| 股票 | episode 起点 | 最新财报 | 账面净资产(亿元) | 审计意见 | 风险事实数 | 资产状态 | 股本账 |",
        "| --- | --- | --- | ---: | --- | ---: | --- | --- |",
    ]
    for case in result.cases:
        baseline = case.baseline
        net_assets = (
            f"{baseline.reported_net_assets / 100_000_000:.2f}"
            if baseline.reported_net_assets is not None
            else "不可用"
        )
        risk_count = sum(case.risk_fact_count_by_category.values())
        lines.append(
            f"| {case.symbol} | {case.episode_start_date} | "
            f"{baseline.period_end or '不可用'} | {net_assets} | "
            f"{baseline.audit_result or '未匹配'} | {risk_count} | "
            f"`{case.asset_map.status}` | `{case.old_shareholder_ledger.status}` |"
        )
    lines.extend(
        [
            "",
            "## 冻结结论",
            "",
            *[f"- {item}" for item in result.conclusions],
            "",
            "缺失负债敏感度只作用于账面偿债语境，固定为总资产的 0/5/10/20%；"
            "它不是概率、折价率或估值区间。公告标题只能证明风险披露存在，"
            "正文金额未核证时统一记录为 unknown。",
        ]
    )
    return "\n".join(lines) + "\n"


def _load_provider_env(path: Path | None) -> None:
    if path is None:
        return
    if not path.is_file():
        raise FileNotFoundError(path)
    allowed = {"TUSHARE_TOKEN", "TUSHARE_HTTP_URL"}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in allowed and key.strip() not in os.environ:
            os.environ[key.strip()] = value.strip().strip("\"'")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--base-database", type=Path, required=True)
    parser.add_argument("--market-factor-database", type=Path, required=True)
    parser.add_argument("--fact-database", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args(argv)
    manifest = PilotManifest.model_validate_json(
        args.manifest.read_text(encoding="utf-8")
    )
    _load_provider_env(args.env_file)
    result = run_pilot(
        manifest=manifest,
        provider=TushareHttpClient(),
        base_database=args.base_database,
        market_factor_database=args.market_factor_database,
        fact_repository=ValuationFactRepository(args.fact_database),
    )
    _write(
        args.output_json,
        json.dumps(
            result.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
    )
    _write(args.output_markdown, render_markdown(result))
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "cases": len(result.cases),
                "full_scale_equity_output": result.full_scale_equity_output,
                "decision_clusters": result.decision_cluster_count,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
