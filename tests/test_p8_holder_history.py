import sqlite3
from pathlib import Path

import pytest

from p8_holder_history import _records_for_symbol, backfill_holder_history
from p8_research import P8ResearchRepository


class FakeProvider:
    def fetch_holder_numbers(self, *, symbol: str, start_date: str, end_date: str):
        assert start_date == "2020-01-01"
        assert end_date == "2025-12-31"
        return [
            {"ts_code": f"{symbol}.SZ", "ann_date": "20221231", "end_date": "20220930", "holder_num": 100},
            {"ts_code": f"{symbol}.SZ", "ann_date": "20230103", "end_date": "20221231", "holder_num": 80},
        ]


def _context(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("create table st_membership_daily(trade_date text,symbol text)")
        connection.executemany(
            "insert into st_membership_daily values (?,?)",
            [(day, "000001") for day in ("2023-01-03", "2023-01-04", "2023-01-05")],
        )


def test_holder_record_uses_prior_disclosure_and_next_trade_day() -> None:
    rows = FakeProvider().fetch_holder_numbers(
        symbol="000001", start_date="2020-01-01", end_date="2025-12-31",
    )
    result = _records_for_symbol(
        symbol="000001", rows=rows,
        calendar=["2023-01-03", "2023-01-04", "2023-01-05"],
        memberships={day: {"000001"} for day in ("2023-01-03", "2023-01-04", "2023-01-05")},
    )
    assert len(result) == 1
    assert result[0]["available_as_of"] == "2023-01-03"
    assert result[0]["trade_date"] == "2023-01-04"
    assert result[0]["holder_change_pct"] == pytest.approx(-0.2)


def test_holder_history_run_is_point_in_time_and_outcome_blind(tmp_path: Path) -> None:
    context = tmp_path / "context.sqlite3"
    _context(context)
    result = backfill_holder_history(
        market_context_database=context,
        repository=P8ResearchRepository(tmp_path / "p8.sqlite3"),
        cache_dir=tmp_path / "cache", allow_provider=True, workers=1,
        client_factory=FakeProvider,
    )
    assert result["status"] == "complete"
    assert result["record_count"] == 1
    assert result["outcomes_read"] is False
    assert result["returns_computed"] is False
