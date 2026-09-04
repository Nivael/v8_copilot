import sqlite3

from data_refresh import TusharePriceBatch
from p8_prices import qfq_close
from p8_qfq_backfill import backfill, missing_prefix_symbols


def _price_db(path, *, start="2022-01-04"):
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            create table daily_prices(
                symbol text,trade_date text,adjust text,open real,high real,low real,
                close real,volume real,amount real,amplitude real,pct_change real,
                change_amount real,turnover_rate real,source text,
                primary key(symbol,trade_date,adjust)
            );
        """)
        connection.execute(
            "insert into daily_prices values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("000001", start, "qfq", 10, 10, 10, 10, 1, 1, None, 0, 0, None, "base"),
        )


def _context(path):
    with sqlite3.connect(path) as connection:
        connection.execute("create table st_membership_daily(trade_date text,symbol text)")
        connection.execute("insert into st_membership_daily values('2021-03-17','000001')")


class FakeProvider:
    def fetch_qfq(self, *, symbol, start_date, end_date):
        assert symbol == "000001"
        assert start_date == "2021-03-17"
        assert end_date == "2026-09-03"
        row = {
            "symbol": symbol, "trade_date": "2021-03-17", "adjust": "qfq",
            "open": 5.0, "high": 5.0, "low": 5.0, "close": 5.0,
            "volume": 1.0, "amount": 1.0, "amplitude": None,
            "pct_change": 0.0, "change_amount": 0.0,
            "turnover_rate": None, "source": "fake",
        }
        later = dict(row, trade_date="2022-01-04", open=9.0, high=9.0, low=9.0, close=9.0)
        return TusharePriceBatch(rows=[row, later], latest_adj_factor=2.0)


def test_scoped_qfq_backfill_and_overlay_priority(tmp_path):
    base, context, overlay = tmp_path / "base.sqlite3", tmp_path / "context.sqlite3", tmp_path / "overlay.sqlite3"
    _price_db(base)
    _context(context)
    assert missing_prefix_symbols(
        base_database=base, market_context_database=context,
    ) == [("000001", "2021-03-17")]
    result = backfill(
        base_database=base, market_context_database=context,
        overlay_database=overlay, allow_provider=True, workers=1,
        client_factory=FakeProvider,
    )
    assert result["status"] == "complete"
    prices = qfq_close(
        base, overlay_database=overlay, start="2021-01-01", through="2023-01-01",
    )
    assert prices[("000001", "2021-03-17")] == 5.0
    assert prices[("000001", "2022-01-04")] == 9.0
