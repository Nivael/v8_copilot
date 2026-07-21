from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime

from data_refresh import (
    AnnouncementRefreshService,
    CninfoHttpClient,
    MaintenanceStateRepository,
    PriceRefreshService,
    TushareHttpClient,
    TusharePriceBatch,
)


def _price_db(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            create table daily_prices (
                symbol text not null, trade_date text not null, adjust text not null,
                open real, high real, low real, close real, volume real, amount real,
                amplitude real, pct_change real, change_amount real, turnover_rate real,
                source text not null, fetched_at text default current_timestamp,
                primary key(symbol,trade_date,adjust)
            );
            create table company_announcements (
                announcement_id text primary key, symbol text not null,
                announcement_date text not null, title text not null
            );
            insert into daily_prices(symbol,trade_date,adjust,open,high,low,close,source)
            values ('603398','2026-07-01','qfq',10,11,9,10,'tushare:daily+adj_factor:qfq'),
                   ('603398','2026-07-02','qfq',10,11,9,10,'tushare:daily+adj_factor:qfq');
            insert into company_announcements values ('OLD-DB','603398','2026-07-01','旧公告');
        """)


def _price_row(trade_date: str, close: float) -> dict:
    return {
        "symbol": "603398", "trade_date": trade_date, "adjust": "qfq",
        "open": close, "high": close, "low": close, "close": close,
        "volume": 1.0, "amount": 1.0, "amplitude": None, "pct_change": 0.0,
        "change_amount": 0.0, "turnover_rate": None,
        "source": "tushare:daily+adj_factor:qfq",
    }


class FakePriceProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.factor = 1.0
        self.overlap_close = 10.0

    def fetch_qfq(self, *, symbol: str, start_date: str, end_date: str) -> TusharePriceBatch:
        self.calls.append((start_date, end_date))
        return TusharePriceBatch(
            rows=[_price_row("2026-07-02", self.overlap_close), _price_row("2026-07-03", 11)],
            latest_adj_factor=self.factor,
        )


def test_price_refresh_resumes_dedupes_and_skips_completed_target(tmp_path) -> None:
    database = tmp_path / "prices.sqlite3"
    _price_db(database)
    state = MaintenanceStateRepository(tmp_path / "maintenance.sqlite3")
    provider = FakePriceProvider()
    service = PriceRefreshService(database=database, state=state, provider=provider)

    first = service.refresh(symbol="603398", through="2026-07-03", overlap_days=1)
    second = service.refresh(symbol="603398", through="2026-07-03", overlap_days=1)

    assert first.fetch_start == "2026-07-01"
    assert first.rows_written == 2  # overlap row changed because full canonical columns were completed
    assert second.status == "skipped"
    assert len(provider.calls) == 1
    checkpoint = state.get("tushare_daily_qfq", "603398")
    assert checkpoint is not None
    assert checkpoint.checked_through == "2026-07-03"
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "select count(*) from daily_prices where symbol='603398' and adjust='qfq'"
        ).fetchone()[0] == 3


def test_price_refresh_rebuilds_full_history_when_adjustment_factor_changes(tmp_path) -> None:
    database = tmp_path / "prices.sqlite3"
    _price_db(database)
    state = MaintenanceStateRepository(tmp_path / "maintenance.sqlite3")
    provider = FakePriceProvider()
    service = PriceRefreshService(database=database, state=state, provider=provider)
    service.refresh(symbol="603398", through="2026-07-03", overlap_days=1)
    provider.factor = 2.0

    result = service.refresh(symbol="603398", through="2026-07-04", overlap_days=1)

    assert result.full_rebase is True
    assert provider.calls[-1][0] == "2026-07-01"


def test_first_checkpoint_rebuilds_when_overlap_reveals_different_qfq_basis(tmp_path) -> None:
    database = tmp_path / "prices.sqlite3"
    _price_db(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "insert into daily_prices(symbol,trade_date,adjust,open,high,low,close,source) "
            "values ('603398','2026-06-30','qfq',10,11,9,10,'tushare:daily+adj_factor:qfq')"
        )
    state = MaintenanceStateRepository(tmp_path / "maintenance.sqlite3")
    provider = FakePriceProvider()
    provider.overlap_close = 5.0
    service = PriceRefreshService(database=database, state=state, provider=provider)

    result = service.refresh(symbol="603398", through="2026-07-03", overlap_days=1)

    assert result.full_rebase is True
    assert provider.calls == [
        ("2026-07-01", "2026-07-03"),
        ("2026-06-30", "2026-07-03"),
    ]


def test_tushare_client_computes_qfq_from_daily_and_adjustment_factor(monkeypatch) -> None:
    client = TushareHttpClient(token="not-a-real-token")

    def query(api_name, *, params, fields):
        if api_name == "daily":
            return [
                {"trade_date": "20260701", "open": 10, "high": 12, "low": 9,
                 "close": 11, "vol": 1, "amount": 2, "pct_chg": 10, "change": 1},
                {"trade_date": "20260702", "open": 20, "high": 22, "low": 19,
                 "close": 21, "vol": 1, "amount": 2, "pct_chg": 5, "change": 1},
            ]
        return [
            {"trade_date": "20260701", "adj_factor": 1},
            {"trade_date": "20260702", "adj_factor": 2},
        ]

    monkeypatch.setattr(client, "_query", query)
    batch = client.fetch_qfq(symbol="603398", start_date="2026-07-01", end_date="2026-07-02")

    assert batch.latest_adj_factor == 2
    assert batch.rows[0]["close"] == 5.5
    assert batch.rows[1]["close"] == 21


def test_tushare_client_exposes_st_universe_and_index_boundaries(monkeypatch) -> None:
    client = TushareHttpClient(token="not-a-real-token")
    calls = []

    def query(api_name, *, params, fields):
        calls.append((api_name, params, fields))
        return []

    monkeypatch.setattr(client, "_query", query)
    client.fetch_st_universe(as_of="2026-07-20")
    client.fetch_index_daily(
        ts_code="000985.CSI", start_date="2026-07-01", end_date="2026-07-20"
    )

    assert calls[0][0:2] == ("stock_st", {"trade_date": "20260720"})
    assert calls[1][0] == "index_daily"
    assert calls[1][1] == {
        "ts_code": "000985.CSI", "start_date": "20260701", "end_date": "20260720"
    }


def test_cninfo_timestamp_is_interpreted_in_exchange_timezone() -> None:
    timestamp = datetime.fromisoformat("2026-07-14T00:30:00+08:00").timestamp() * 1000

    row = CninfoHttpClient._normalize({
        "announcementId": "A-1",
        "announcementTime": timestamp,
        "announcementTitle": "测试公告",
        "secCode": "603398",
    }, "603398")

    assert row is not None
    assert row["announcement_date"] == "2026-07-14"
    assert row["published_at"].endswith("+08:00")


class FakeAnnouncementProvider:
    def __init__(self) -> None:
        self.calls = 0

    def fetch(self, *, symbol: str, start_date: str, end_date: str) -> list[dict]:
        self.calls += 1
        return [
            {"announcement_id": "OLD", "symbol": symbol,
             "announcement_date": "2026-07-02", "title": "已有公告"},
            {"announcement_id": "NEW", "symbol": symbol,
             "announcement_date": "2026-07-03", "title": "新增公告"},
        ]


def test_cninfo_refresh_merges_by_id_and_persists_checked_through(tmp_path) -> None:
    database = tmp_path / "prices.sqlite3"
    _price_db(database)
    refresh = tmp_path / "announcement_refresh"
    refresh.mkdir()
    overlay = refresh / "603398.json"
    overlay.write_text(json.dumps({
        "symbol": "603398", "source": "cninfo", "records": [{
            "announcement_id": "OLD", "symbol": "603398",
            "announcement_date": "2026-07-02", "title": "已有公告", "body_text": "已材料化正文",
        }],
    }), encoding="utf-8")
    os.utime(overlay, (datetime(2026, 7, 2).timestamp(), datetime(2026, 7, 2).timestamp()))
    state = MaintenanceStateRepository(tmp_path / "maintenance.sqlite3")
    provider = FakeAnnouncementProvider()
    service = AnnouncementRefreshService(
        refresh_dir=refresh, base_database=database, state=state, provider=provider,
    )

    first = service.refresh(symbol="603398", through="2026-07-03", overlap_days=1)
    second = service.refresh(symbol="603398", through="2026-07-03", overlap_days=1)

    payload = json.loads(overlay.read_text(encoding="utf-8"))
    assert first.rows_written == 1
    assert first.rows_unchanged == 1
    assert second.status == "skipped"
    assert provider.calls == 1
    assert payload["checked_through"] == "2026-07-03"
    assert {row["announcement_id"] for row in payload["records"]} == {"OLD", "NEW"}
    assert next(row for row in payload["records"] if row["announcement_id"] == "OLD")["body_text"] == "已材料化正文"
