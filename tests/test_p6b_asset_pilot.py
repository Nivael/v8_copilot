import json
import sqlite3

import pytest

from p6b_asset_pilot import (
    PilotManifest,
    ValuationFactRepository,
    _normalize_statement,
    compute_asset_map,
    run_pilot,
)


class FakeProvider:
    def fetch_balance_sheets(self, *, symbol, start_date, end_date):
        return [
            {
                "ts_code": f"{symbol}.SZ",
                "ann_date": "20260430",
                "f_ann_date": "20260430",
                "end_date": "20260331",
                "report_type": "1",
                "total_assets": 1_000,
                "total_liab": 800,
                "total_hldr_eqy_inc_min_int": 200,
                "total_hldr_eqy_exc_min_int": 180,
                "update_flag": "1",
            }
        ]

    def fetch_audit_opinions(self, *, symbol, start_date, end_date):
        return [
            {
                "ts_code": f"{symbol}.SZ",
                "ann_date": "20260420",
                "end_date": "20251231",
                "audit_result": "保留意见",
                "audit_agency": "示例所",
            }
        ]

    def fetch_financial_indicators(self, *, symbol, start_date, end_date):
        return [
            {
                "ts_code": f"{symbol}.SZ",
                "ann_date": "20260430",
                "end_date": "20260331",
                "current_ratio": 0.5,
                "quick_ratio": 0.4,
                "debt_to_assets": 80,
                "ocf_to_shortdebt": -0.1,
                "update_flag": "1",
            }
        ]


def _base_database(path):
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            create table company_announcements (
                announcement_id text, symbol text, announcement_date text,
                announcement_type text, title text, url text, body_text text
            )
            """
        )
        for symbol in ("000001", "000002", "000003", "000004", "000005"):
            connection.execute(
                "insert into company_announcements values (?,?,?,?,?,?,?)",
                (
                    f"A-{symbol}",
                    symbol,
                    "2026-05-10",
                    "风险提示",
                    "关于诉讼及担保事项的公告",
                    f"https://example.invalid/{symbol}",
                    None,
                ),
            )


def _market_database(path):
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            create table market_factor_snapshots (
                snapshot_id text primary key, trade_date text, created_at text
            );
            create table market_cap_daily (
                snapshot_id text, symbol text, trade_date text, total_shares real,
                source text
            );
            """
        )
        connection.execute(
            "insert into market_factor_snapshots values ('S0','2026-05-01','2026-05-01')"
        )
        connection.execute(
            "insert into market_factor_snapshots values ('S1','2026-07-17','2026-07-17')"
        )
        for symbol in ("000001", "000002", "000003", "000004", "000005"):
            connection.execute(
                "insert into market_cap_daily values ('S0',?,'2026-05-01',100,'test')",
                (symbol,),
            )
            end_shares = 150 if symbol == "000001" else 100
            connection.execute(
                "insert into market_cap_daily values ('S1',?,'2026-07-17',?,'test')",
                (symbol, end_shares),
            )


def _manifest():
    return PilotManifest.model_validate(
        {
            "contract_version": "v8_p6b2_asset_equity_pilot_v1",
            "pilot_id": "test",
            "as_of": "2026-07-20",
            "financial_statement_start": "2025-01-01",
            "missing_liability_shock_pct_total_assets": [0, 0.05, 0.1, 0.2],
            "selection_rule": "fixed fixture",
            "symbols": [
                {
                    "symbol": symbol,
                    "episode_start_date": "2026-05-01",
                    "selection_tags": ["fixture"],
                }
                for symbol in ("000001", "000002", "000003", "000004", "000005")
            ],
        }
    )


@pytest.mark.parametrize(
    ("assets", "obligations", "expected", "residual"),
    [
        ((120, 140), (70, 80), "positive", "calculable"),
        ((50, 60), (80, 90), "negative", "calculable"),
        ((50, 100), (70, 90), "unknown", "not_calculable"),
    ],
)
def test_asset_interval_state_and_residual_fail_closed(
    assets, obligations, expected, residual
):
    result = compute_asset_map(
        recoverable_assets_min=assets[0],
        recoverable_assets_max=assets[1],
        known_obligations_min=obligations[0],
        known_obligations_max=obligations[1],
        evidence_refs=["verified:test"],
        independently_verified=True,
    )
    assert result.status == expected
    assert result.market_residual_status == residual


def test_reported_balance_sheet_never_promotes_to_verified_asset_state():
    result = compute_asset_map(
        recoverable_assets_min=1_000,
        recoverable_assets_max=1_000,
        known_obligations_min=800,
        known_obligations_max=800,
        evidence_refs=["tushare:balancesheet"],
        independently_verified=False,
    )
    assert result.status == "unknown"
    assert result.market_residual_status == "not_calculable"
    assert result.adjusted_net_assets_min is None


def test_future_restatement_is_excluded_from_point_in_time_input():
    raw = {
        "ts_code": "000001.SZ",
        "ann_date": "20260730",
        "f_ann_date": "20260730",
        "end_date": "20260331",
        "report_type": "1",
        "update_flag": "1",
    }
    assert _normalize_statement(raw, symbol="000001", as_of="2026-07-20") is None


def test_pilot_freezes_range_output_and_append_only_store(tmp_path):
    base = tmp_path / "base.sqlite3"
    market = tmp_path / "market.sqlite3"
    facts = tmp_path / "facts.sqlite3"
    _base_database(base)
    _market_database(market)
    repository = ValuationFactRepository(facts)
    first = run_pilot(
        manifest=_manifest(),
        provider=FakeProvider(),
        base_database=base,
        market_factor_database=market,
        fact_repository=repository,
    )
    second = run_pilot(
        manifest=_manifest(),
        provider=FakeProvider(),
        base_database=base,
        market_factor_database=market,
        fact_repository=repository,
    )
    assert first.run_id == second.run_id
    assert first.full_scale_equity_output == "range_primary"
    assert all(case.asset_map.status == "unknown" for case in first.cases)
    assert first.cases[0].old_shareholder_ledger.status == "range_only"
    assert first.cases[0].missing_liability_sensitivity[-1].additional_liability == 200
    with sqlite3.connect(facts) as connection:
        assert connection.execute(
            "select count(*) from pilot_runs"
        ).fetchone()[0] == 1
        payload = json.loads(
            connection.execute("select payload_json from pilot_runs").fetchone()[0]
        )
    assert payload["full_scale_equity_output"] == "range_primary"
