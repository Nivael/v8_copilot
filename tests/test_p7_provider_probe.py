from __future__ import annotations

from p7_provider_probe import build_provider_probe
from data_refresh import TushareHttpClient


FIELDS = {
    "ts_code": "000001.SZ", "trade_date": "20260817", "open": 1, "high": 1,
    "low": 1, "close": 1, "pre_close": 1, "change": 0, "pct_chg": 0,
    "vol": 1, "amount": 1,
}


class FakeProvider:
    def fetch_daily(self, *, trade_date):
        return [{**FIELDS, "trade_date": trade_date.replace("-", "")}]

    def fetch_daily_basic(self, *, trade_date):
        return [{
            "ts_code": "000001.SZ", "trade_date": trade_date.replace("-", ""),
            "close": 1, "turnover_rate": 1, "turnover_rate_f": 2,
            "volume_ratio": 1, "total_share": 1, "float_share": 1,
            "free_share": 1, "total_mv": 1, "circ_mv": 1, "limit_status": 0,
        }]

    def fetch_suspend_daily(self, *, trade_date):
        return []

    def fetch_stock_limits(self, *, trade_date):
        return [{"ts_code": "000001.SZ", "trade_date": trade_date.replace("-", ""), "pre_close": 1, "up_limit": 1.05, "down_limit": .95}]

    def fetch_exchange_reference(self, *, api_name, trade_date):
        raise RuntimeError("您暂时无法使用该接口")


def test_provider_probe_validates_schema_and_keeps_exchange_reference_nonblocking():
    result = build_provider_probe(
        provider=FakeProvider(),
        source_dry_plan={"plan_id": "P7DP-TEST", "content_digest": "abc"},
        latest_trade_date="2026-08-17",
    )
    assert result.hard_blockers == []
    assert result.provider_permission_matrix["daily_basic"]["status"] == "success"
    assert result.provider_permission_matrix["stk_alert"]["status"] == "permission_denied"
    assert result.production_writes == 0


def test_daily_basic_explicitly_requests_frozen_fields():
    captured = {}
    client = object.__new__(TushareHttpClient)
    client._query = lambda api_name, *, params, fields: captured.update({  # type: ignore[method-assign]
        "api_name": api_name, "params": params, "fields": fields,
    }) or []
    assert client.fetch_daily_basic(trade_date="2026-08-17") == []
    assert captured["api_name"] == "daily_basic"
    assert "turnover_rate_f" in captured["fields"]
    assert "limit_status" in captured["fields"]
