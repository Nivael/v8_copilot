from datetime import date, datetime, timezone
import json

import pytest

from etf_public_refresh import PUBLIC_CODES
from etf_source_fixtures import refresh_public_etfs
from etf_source_fixtures import refresh_szse_etfs
from learning_status import build_learning_status
from market_calendar import sessions_2026
from market_public_refresh import refresh_public_indices
from market_periods import months_before, recent_calendar_window
from market_risk import build_market_risk_status, etf_metrics, index_metrics, market_update_status

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)
CALENDAR = sessions_2026(date(2026, 8, 4), date(2026, 11, 4))


@pytest.mark.parametrize("end,expected", [("2026-11-04", "2026-09-04"), ("2026-08-31", "2026-06-30"), ("2024-04-30", "2024-02-29")])
def test_calendar_months_preserve_day_and_clamp_month_end(end, expected):
    assert months_before(date.fromisoformat(end), 2).isoformat() == expected


def test_two_month_window_is_not_twenty_or_sixty_sessions_and_uses_prior_close():
    window = recent_calendar_window("2026-11-04")
    assert (window["start"], window["end"], window["sessions"], window["points"]) == ("2026-09-04", "2026-11-04", 37, 38)
    assert "2026-09-25" not in window["calendar"] and "2026-10-07" not in window["calendar"]
    weekend_start = recent_calendar_window("2026-11-05")
    assert weekend_start["requested_start"] == "2026-09-05"
    assert weekend_start["start"] == "2026-09-04"
    assert recent_calendar_window("2026-01-20")["availability"] == "unavailable"


def test_price_drawdown_uses_only_the_complete_recent_window():
    rows = [{"trade_date": day, "close": 100} for day in CALENDAR]
    rows[0]["close"] = 1000  # Outside the two-month window.
    rows[40]["close"], rows[41]["close"], rows[-1]["close"] = 200, 80, 150
    result = index_metrics(rows, CALENDAR)["recent"]
    assert result["return_pct"] == 50
    assert result["max_drawdown_pct"] == -60
    assert result["from_peak_pct"] == -25
    missing = index_metrics([row for row in rows if row["trade_date"] != "2026-10-12"], CALENDAR)["recent"]
    assert missing["return_pct"] is None and missing["max_drawdown_pct"] is None


def test_recent_ETF_coverage_requires_every_day_not_only_endpoints():
    rows = [{"trade_date": day, "fd_share": 100} for day in CALENDAR]
    rows[-1]["fd_share"] = 80
    full = etf_metrics(rows, [], CALENDAR)["windows"]["recent"]
    assert (full["window_start"], full["window_end"], full["window_sessions"]) == ("2026-09-04", "2026-11-04", 37)
    assert full["share_change_pct"] == -20
    assert full["estimated_net_subscription_yuan"] is None
    partial = etf_metrics([row for row in rows if row["trade_date"] != "2026-10-12"], [], CALENDAR)
    assert partial["windows"]["recent"]["share_change_pct"] is None
    assert partial["windows"]["5"]["share_change_pct"] == -20


class SSE:
    def __init__(self): self.calls = []
    def get_day(self, day):
        self.calls.append(day)
        return [{"ts_code": code, "trade_date": day, "fd_share": 100} for code in PUBLIC_CODES], []


def test_extension_reuses_only_verified_overlap_without_changing_the_end(tmp_path):
    folder = tmp_path / "public_etf"
    first = refresh_public_etfs(SSE(), through="2026-11-04", output=folder, now=NOW)
    client = SSE()
    report = refresh_public_etfs(client, through="2026-11-04", output=folder, now=NOW, sessions=61, extend_window=True)
    assert len(client.calls) == 40
    assert report["reused_complete_dates"] == 21
    raw = json.loads((folder / "current.json").read_text())
    assert raw["reused_from_digest"] == first["snapshot_digest"]
    assert len(raw["etf_shares"][PUBLIC_CODES[0]]) == 61
    before = (folder / "current.json").read_bytes()
    with pytest.raises(ValueError):
        refresh_public_etfs(client, through="2026-11-03", output=folder, now=NOW, sessions=61, extend_window=True)
    assert before == (folder / "current.json").read_bytes()


class SZSE:
    def get_history(self, code, calendar, *, nav=False):
        days = calendar[-11:-1] if nav else calendar
        return [{"ts_code": code, "nav_date" if nav else "trade_date": day,
                 "unit_nav" if nav else "fd_share": 2 if nav else 100} for day in days], []


def test_learning_page_reports_market_sources_without_updating_old_manifests(tmp_path):
    refresh_public_etfs(SSE(), through="2026-11-04", output=tmp_path / "public_etf", now=NOW, sessions=61)
    refresh_szse_etfs(SZSE(), through="2026-11-04", output=tmp_path / "public_etf_szse", now=NOW, sessions=61)
    sources = {row["source_id"]: row for row in market_update_status(snapshot_dir=tmp_path, now=NOW)}
    assert sources["official_indices"]["observation_count"] is None
    assert sources["sse_etf_shares"]["observation_count"] == 305
    assert sources["szse_etf_shares"]["observation_count"] == 183
    assert sources["szse_etf_nav"]["observation_count"] == 30
    assert sources["szse_etf_nav"]["observed_through_min"] == "2026-11-03"
    assert sources["szse_etf_nav"]["series_at_target"] == 0
    before = {str(path): path.read_bytes() for path in tmp_path.rglob("*.json")}
    status = build_learning_status(market_snapshot_dir=tmp_path, experience_db=tmp_path / "missing.db",
        governance_db=tmp_path / "missing-governance", ledger_db=tmp_path / "missing-ledger",
        freshness_path=tmp_path / "missing-manifest", audit_path=tmp_path / "missing-audit", now=NOW)
    assert status["freshness"]["availability"] == "missing"
    assert status["market_updates"][1]["observation_count"] == 305
    assert before == {str(path): path.read_bytes() for path in tmp_path.rglob("*.json")}
    market = build_market_risk_status(snapshot_dir=tmp_path, database=tmp_path / "missing", manifest_path=tmp_path / "none", now=NOW)
    assert market["etf_aggregate"]["recent"]["observed_etfs"] == 8
    assert market["etf_aggregate"]["recent"]["revision_unconfirmed_etfs"] == 3
    assert market["node_market_comparison"]["status"] == "not_evaluated"


def test_recent_observations_count_only_matching_complete_windows(tmp_path, monkeypatch):
    class Indices:
        def get_index(self, code, calendar):
            return [{"ts_code": code, "trade_date": day, "close": 100-i, "amount": 1000}
                    for i, day in enumerate(calendar)], {"code": code}
    class RisingSSE:
        def get_day(self, day):
            return [{"ts_code": code, "trade_date": day, "fd_share": 100 + CALENDAR.index(day)}
                    for code in PUBLIC_CODES], []
    class FallingSZSE:
        def get_history(self, code, calendar, *, nav=False):
            return [{"ts_code": code, "nav_date" if nav else "trade_date": day,
                     "unit_nav" if nav else "fd_share": 2 if nav else 100-i}
                    for i, day in enumerate(calendar)], []
    refresh_public_indices(Indices(), through="2026-11-04", output=tmp_path / "public_indices", now=NOW)
    refresh_public_etfs(RisingSSE(), through="2026-11-04", output=tmp_path / "public_etf", now=NOW, sessions=61)
    refresh_szse_etfs(FallingSZSE(), through="2026-11-04", output=tmp_path / "public_etf_szse", now=NOW, sessions=61)
    monkeypatch.setattr("market_risk._historical_indices", lambda *_args: [{"code": "st_equal_weight_v1", "name": "old ST",
        "historical_only": True, "through": "2026-09-03", "recent": {"start": "2026-07-03", "end": "2026-09-03", "return_pct": -99}}])
    result = build_market_risk_status(snapshot_dir=tmp_path, database=tmp_path / "missing", manifest_path=tmp_path / "none", now=NOW)
    counts = result["recent_observations"]
    assert (counts["index_coverage"], counts["declining_indices"]) == (3, 3)
    assert (counts["etf_share_coverage"], counts["increasing_share_records"], counts["decreasing_share_records"]) == (8, 5, 3)
    # A different end date must not enter the price-window description.
    refresh_szse_etfs(FallingSZSE(), through="2026-11-03", output=tmp_path / "public_etf_szse", now=NOW, sessions=61)
    result = build_market_risk_status(snapshot_dir=tmp_path, database=tmp_path / "missing", manifest_path=tmp_path / "none", now=NOW)
    assert result["recent_observations"]["etf_share_coverage"] == 5
