import json
import sqlite3

from p8_research import P8ResearchRepository
from p8_terminal_history import _records, backfill_terminal_history


class _Provider:
    def fetch_stock_basics(self, *, list_status: str):
        assert list_status == "D"
        return [
            {
                "ts_code": "000001.SZ", "symbol": "000001", "name": "退市样本",
                "market": "主板", "exchange": "SZSE", "list_status": "D",
                "list_date": "19910403", "delist_date": "20240531",
            },
            {
                "ts_code": "000002.SZ", "symbol": "000002", "name": "非样本",
                "market": "主板", "exchange": "SZSE", "list_status": "D",
                "list_date": "19910129", "delist_date": "20240630",
            },
        ]


def test_terminal_records_filter_to_historical_st_members() -> None:
    records = _records(_Provider().fetch_stock_basics(list_status="D"), historical_symbols={"000001"})
    assert len(records) == 1
    assert records[0]["symbol"] == "000001"
    assert records[0]["delist_date"] == "2024-05-31"
    assert records[0]["total_loss_stress"] == -1.0


def test_terminal_backfill_is_cached_and_append_only(tmp_path) -> None:
    market = tmp_path / "market.sqlite3"
    with sqlite3.connect(market) as connection:
        connection.execute("create table st_membership_daily(trade_date text,symbol text)")
        connection.execute("insert into st_membership_daily values('2024-01-02','000001')")
    repository = P8ResearchRepository(tmp_path / "p8.sqlite3")
    cache = tmp_path / "stock_basic_D.json"
    result = backfill_terminal_history(
        market_context_database=market, repository=repository, cache_path=cache,
        allow_provider=True, provider_factory=_Provider,
    )
    assert result["provider_request_count"] == 1
    assert result["terminal_record_count"] == 1
    assert json.loads(cache.read_text())["list_status"] == "D"
    repeated = backfill_terminal_history(
        market_context_database=market, repository=repository, cache_path=cache,
        allow_provider=True, provider_factory=lambda: (_ for _ in ()).throw(AssertionError()),
    )
    assert repeated["cache_hit"] is True
    assert repeated["run_id"] == result["run_id"]
