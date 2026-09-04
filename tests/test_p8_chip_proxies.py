from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from p8_chip_proxies import materialize_chip_proxies
from p8_research import P8ResearchRepository


class FakeProvider:
    def fetch_holder_numbers(self, *, symbol: str, start_date: str, end_date: str):
        if symbol == "000001":
            return [
                {"ts_code": "000001.SZ", "ann_date": "20260801", "end_date": "20260630", "holder_num": 90},
                {"ts_code": "000001.SZ", "ann_date": "20260401", "end_date": "20260331", "holder_num": 100},
            ]
        return []

    def fetch_top_list(self, *, trade_date: str):
        return [{"ts_code": "000001.SZ", "trade_date": "20260903", "net_amount": 12}]

    def fetch_top_institutions(self, *, trade_date: str):
        return []

    def fetch_block_trades(self, *, trade_date: str):
        return [{"ts_code": "000002.SZ", "trade_date": "20260903", "price": 2, "vol": 5, "amount": 10}]

    def fetch_margin_details(self, *, trade_date: str):
        return []


def _context(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("create table st_membership_daily (trade_date text,symbol text)")
        connection.executemany(
            "insert into st_membership_daily values (?,?)",
            [("2026-09-03", "000001"), ("2026-09-03", "000002")],
        )


def test_chip_proxies_preserve_missing_semantics_and_never_claim_flow(tmp_path: Path) -> None:
    context = tmp_path / "context.sqlite3"
    _context(context)
    fake = FakeProvider()
    result = materialize_chip_proxies(
        market_context_database=context,
        repository=P8ResearchRepository(tmp_path / "p8.sqlite3"),
        as_of="2026-09-03", cache_dir=tmp_path / "cache", workers=2,
        client_factory=lambda: fake,
    )
    assert result.failed_request_count == 0
    by_symbol = {item.symbol: item for item in result.records}
    assert by_symbol["000001"].holder_change_pct == pytest.approx(-0.1)
    assert by_symbol["000001"].top_list_status == "triggered"
    assert by_symbol["000002"].holder_status == "unknown"
    assert by_symbol["000002"].block_trade_status == "reported"
    assert by_symbol["000002"].margin_status == "not_covered_or_missing"
    assert all(item.not_fund_flow for item in result.records)
