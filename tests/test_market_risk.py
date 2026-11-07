from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from market_risk import breadth_metrics, build_market_risk_status, etf_metrics, index_metrics
from market_risk_refresh import refresh_market_risk


def dates(size=61):
    return [(date(2026, 1, 1) + timedelta(days=index)).isoformat() for index in range(size)]


def test_share_price_fall_does_not_become_fund_outflow():
    calendar = dates(6)
    shares = [{"trade_date": day, "fd_share": 100} for day in calendar]
    navs = [{"nav_date": day, "unit_nav": 2 - index * .1} for index, day in enumerate(calendar)]
    result = etf_metrics(shares, navs, calendar, corporate_actions_checked=True, whole_fund_daily_scope_verified=True,
                         share_precision_verified=True, final_revision_verified=True)["windows"]["5"]
    assert result["share_change_pct"] == 0
    assert result["estimated_net_subscription_yuan"] == 0


def test_fd_share_is_ten_thousand_units_and_unchecked_corporate_action_blocks_flow():
    calendar = dates(2)
    shares = [{"trade_date": calendar[0], "fd_share": 100}, {"trade_date": calendar[1], "fd_share": 90}]
    navs = [{"nav_date": calendar[1], "unit_nav": 2}]
    result = etf_metrics(shares, navs, calendar)["windows"]["1"]
    assert result["share_change_notional_yuan"] == -200_000
    assert result["share_change_pct"] == -10
    assert result["estimated_net_subscription_yuan"] is None
    assert result["status"] == "corporate_actions_unchecked"


@pytest.mark.parametrize('mask',range(16))
def test_all_four_independent_flow_conditions_are_required(mask):
    calendar=dates(2);shares=[{'trade_date':calendar[0],'fd_share':100},{'trade_date':calendar[1],'fd_share':110}];navs=[{'nav_date':calendar[1],'unit_nav':2}]
    gates={name:bool(mask&(1<<index)) for index,name in enumerate(('corporate_actions_checked','whole_fund_daily_scope_verified','share_precision_verified','final_revision_verified'))}
    data=etf_metrics(shares,navs,calendar,**gates);window=data['windows']['1']
    assert window['share_change_notional_yuan']==200000 and window['share_change_pct']==10
    assert window['estimated_net_subscription_yuan']==(200000 if mask==15 else None)
    assert window['flow_estimate_ready'] is (mask==15)
    assert window['cash_estimation_gaps']==[name for name,value in gates.items() if not value]
    assert data['flow_verification_gates_passed'] is (mask==15)


def test_exchange_register_transfer_cannot_become_net_subscription_with_only_event_clearance():
    # Illustrative book transfer: exchange +10, off-exchange -10, whole-fund total unchanged.
    calendar=dates(2);listed=[100,110];off_exchange=[20,10]
    assert listed[0]+off_exchange[0]==listed[1]+off_exchange[1]
    data=etf_metrics([{'trade_date':d,'fd_share':v} for d,v in zip(calendar,listed)],[{'nav_date':calendar[-1],'unit_nav':2}],calendar,
                     corporate_actions_checked=True,share_precision_verified=True,final_revision_verified=True)
    result=data['windows']['1']
    assert result['share_change_notional_yuan']==200000 and result['estimated_net_subscription_yuan'] is None
    assert result['status']=='share_scope_unverified' and result['cash_estimation_gaps']==['whole_fund_daily_scope_verified']


def test_truthy_labels_and_complete_verification_without_complete_inputs_cannot_release_a_flow():
    calendar=dates(2);rows=[{'trade_date':d,'fd_share':100} for d in calendar];nav=[{'nav_date':calendar[-1],'unit_nav':2}]
    labels=dict(corporate_actions_checked='true',whole_fund_daily_scope_verified=1,share_precision_verified='yes',final_revision_verified=['verified'])
    data=etf_metrics(rows,nav,calendar,**labels)
    assert data['flow_verification_gates_passed'] is False and data['windows']['1']['estimated_net_subscription_yuan'] is None
    verified={name:True for name in labels};empty=etf_metrics(rows,[],calendar,**verified)['windows']['1']
    assert empty['estimated_net_subscription_yuan'] is None and empty['flow_estimate_ready'] is False and empty['cash_estimation_gaps']==['NAV_window_incomplete']


def test_missing_share_or_index_day_is_not_forward_filled_or_shortened():
    calendar = dates(21)
    prices = [{"trade_date": day, "close": 100 + index} for index, day in enumerate(calendar)]
    assert index_metrics(prices, calendar)["return_20d_pct"] == 20
    assert index_metrics(prices[:-1], calendar)["return_5d_pct"] is None
    assert index_metrics(prices[:-1], calendar)["through"] == calendar[-2]
    assert index_metrics([], calendar)["through"] is None
    assert index_metrics(prices[:10] + prices[11:], calendar)["return_20d_pct"] is None
    shares = [{"trade_date": day, "fd_share": 100} for day in calendar]
    navs = [{"nav_date": day, "unit_nav": 2} for day in calendar]
    assert etf_metrics(shares[:-1], navs, calendar)["windows"]["5"]["share_change_pct"] is None


def test_drawdown_is_peak_to_trough_in_same_window():
    calendar = dates()
    closes = [100] * 61
    closes[30], closes[31], closes[-1] = 200, 80, 160
    result = index_metrics([{"trade_date": day, "close": close} for day, close in zip(calendar, closes)], calendar)
    assert result["max_drawdown_60d_pct"] == -60
    assert result["from_60d_peak_pct"] == -20
    assert result["return_60d_pct"] == 60


def test_duplicate_observations_cannot_inflate_breadth_or_overwrite_prices():
    row = {"trade_date": "20260101", "ts_code": "600000.SH", "pct_chg": -5, "amount": 100}
    assert breadth_metrics([row, row])["status"] == "invalid"
    with pytest.raises(ValueError, match="duplicate"):
        index_metrics([{"trade_date": "20260101", "close": 100}] * 2, ["2026-01-01"])
    result = breadth_metrics([row, {**row, "ts_code": "000001.SZ", "pct_chg": 1}])
    assert result["observed_trading_stocks"] == 2
    assert result["declining_5pct_or_more"] == 1
    assert result["amount_yuan"] == 200_000


def test_expired_provider_preserves_prior_snapshot_and_sanitizes_failure(tmp_path):
    class Expired:
        def _query(self, *args, **kwargs):
            raise RuntimeError("token已过期 secret-value")
    current = tmp_path / "current.json"
    current.write_text("prior good snapshot")
    result = refresh_market_risk(Expired(), through="2026-01-01", output=tmp_path)
    assert result["status"] == "failed"
    assert result["reason"] == "provider_token_expired"
    assert current.read_text() == "prior good snapshot"
    assert "secret-value" not in (tmp_path / "last_attempt.json").read_text()


def test_missing_market_inputs_do_not_produce_a_low_risk_score(tmp_path):
    result = build_market_risk_status(snapshot_dir=tmp_path, database=tmp_path / "missing.db", manifest_path=tmp_path / "missing.json")
    assert result["status"] == "unavailable"
    assert result["current_risk_assessment"] == "not_calibrated"
    assert result["parameters"]["risk_weights"] is None
    assert result["etf_aggregate"]["5"]["estimated_net_subscription_yuan"] is None
    assert list(tmp_path.iterdir()) == []


def test_tampered_snapshot_is_not_consumed(tmp_path):
    (tmp_path / "current.json").write_text(json.dumps({"contract_version": "market_risk_raw_v1", "content_digest": "bad", "calendar": []}))
    result = build_market_risk_status(snapshot_dir=tmp_path, database=tmp_path / "missing.db", manifest_path=tmp_path / "missing.json")
    assert result["snapshot_digest"] is None
    assert result["indices"] == []


def test_materializer_and_reader_share_a_verifiable_snapshot(tmp_path):
    calendar = dates(100)
    class Provider:
        def _query(self, name, *, params, fields):
            code = params.get("ts_code", "")
            if name == "trade_cal":
                return [{"cal_date": day.replace("-", ""), "is_open": 1} for day in calendar]
            if name == "index_daily":
                return [{"ts_code": code, "trade_date": day, "close": 100 + index, "amount": 1000} for index, day in enumerate(calendar)]
            if name == "fund_share":
                return [{"ts_code": code, "trade_date": day, "fd_share": 100} for day in calendar]
            if name == "fund_nav":
                return [{"ts_code": code, "nav_date": day, "ann_date": day.replace("-", ""), "unit_nav": 2} for day in calendar]
            return [{"ts_code": "600000.SH", "trade_date": calendar[-1], "pct_chg": -6, "amount": 1000}]
    report = refresh_market_risk(Provider(), through=calendar[-1], output=tmp_path)
    assert report["status"] == "partial"
    before = (tmp_path / "current.json").read_bytes()
    result = build_market_risk_status(snapshot_dir=tmp_path)
    assert result["status"] == "observed_snapshot"
    assert result["snapshot_digest"] == report["snapshot_digest"]
    assert result["etf_aggregate"]["5"]["observed_etfs"] == 8
    assert result["etfs"][0]["windows"]["5"]["estimated_net_subscription_yuan"] is None
    assert result["breadth"]["declining_5pct_or_more"] == 1
    assert (tmp_path / "current.json").read_bytes() == before
