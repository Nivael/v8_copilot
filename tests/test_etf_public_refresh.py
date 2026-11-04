from datetime import date, datetime, timezone
import json

import pytest

from canonical_json import digest
from etf_public_refresh import PUBLIC_CODES, parse_share_pages, refresh_public_etfs
from market_calendar import sessions_2026
from market_risk import ETF_BASKET, build_market_risk_status

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)


def payload(rows, page=1, pages=1, total=None):
    return {"result": rows, "pageHelp": {"pageNo": page, "pageCount": pages,
                                         "total": len(rows) if total is None else total}}


def row(code="510300", day="2026-11-04", shares="123.45"):
    return {"SEC_CODE": code, "STAT_DATE": day, "TOT_VOL": shares}


def test_exchange_unit_and_complete_pagination_are_verified():
    pages = [payload([row()], page=1, pages=2, total=2),
             payload([row("510310")], page=2, pages=2, total=2)]
    selected, total = parse_share_pages(pages, "2026-11-04")
    assert total == 2
    assert selected[0] == {"ts_code": "510300.SH", "trade_date": "2026-11-04", "fd_share": 123.45}


@pytest.mark.parametrize("pages", [
    [payload([row()], total=2)],
    [payload([row()], page=2)],
    [payload([row(), row()])],
    [payload([row(day="2026-11-03")])],
    [payload([row(shares="nan")])],
    [payload([row(shares=True)])],
    [payload([])],
])
def test_bad_exchange_responses_are_not_observations(pages):
    with pytest.raises(ValueError):
        parse_share_pages(pages, "2026-11-04")


class Client:
    def __init__(self, missing_day=None, failed=False):
        self.missing_day, self.failed = missing_day, failed
        self.calls = []

    def get_day(self, day):
        self.calls.append(day)
        if self.failed or day == self.missing_day:
            raise TimeoutError("upstream response must not enter result")
        value = 100 + date.fromisoformat(day).toordinal() % 100
        return ([{"ts_code": code, "trade_date": day, "fd_share": value} for code in PUBLIC_CODES], [])


def read(tmp_path):
    return build_market_risk_status(snapshot_dir=tmp_path, database=tmp_path / "missing.db",
                                    manifest_path=tmp_path / "missing.json", now=NOW)


def test_public_shares_do_not_make_the_missing_market_current_or_invent_NAV(tmp_path):
    destination = tmp_path / "public_etf"
    report = refresh_public_etfs(Client(), through="2026-11-04", output=destination, now=NOW)
    before = (destination / "current.json").read_bytes()
    result = read(tmp_path)
    assert report["observed_etfs_at_target"] == 5
    assert result["status"] == "unavailable"
    assert result["snapshot_digest"] is None
    assert result["public_etf_snapshot"]["availability"] == "observed"
    assert result["etf_aggregate"]["20"]["observed_etfs"] == 5
    assert result["etf_aggregate"]["20"]["nav_observed_etfs"] == 0
    assert result["etf_aggregate"]["20"]["declared_etfs"] == 8
    assert result["etf_aggregate"]["20"]["estimated_net_subscription_yuan"] is None
    metric = result["etfs"][0]["windows"]["20"]
    assert metric["status"] == "shares_only"
    assert metric["window_start"] == "2026-09-30"
    assert metric["window_end"] == "2026-11-04"
    assert metric["share_change_notional_yuan"] is None
    assert before == (destination / "current.json").read_bytes()


def test_failed_or_missing_dates_remain_gaps_and_failed_refresh_preserves_current(tmp_path):
    destination = tmp_path / "public_etf"
    refresh_public_etfs(Client(missing_day="2026-10-30"), through="2026-11-04", output=destination, now=NOW)
    result = read(tmp_path)
    assert result["etf_aggregate"]["1"]["observed_etfs"] == 5
    assert result["etf_aggregate"]["5"]["observed_etfs"] == 0
    assert result["etf_aggregate"]["20"]["observed_etfs"] == 0
    assert any(point["shares"] is None for point in result["etfs"][0]["path"])
    before = (destination / "current.json").read_bytes()
    failed = refresh_public_etfs(Client(failed=True), through="2026-11-04", output=destination, now=NOW)
    assert failed["status"] == "failed"
    assert failed["current_snapshot_preserved"] is True
    assert (destination / "current.json").read_bytes() == before
    assert "upstream" not in (destination / "last_attempt.json").read_text()


def test_official_calendar_has_no_makeup_weekend_or_guessed_future_year():
    days = sessions_2026(date(2026, 9, 18), date(2026, 10, 12))
    assert "2026-09-20" not in days and "2026-10-10" not in days
    assert "2026-09-25" not in days and "2026-10-07" not in days
    assert "2026-09-28" in days and "2026-10-08" in days
    with pytest.raises(ValueError):
        sessions_2026(date(2027, 1, 1), date(2027, 1, 30))


def test_repair_only_fetches_missing_dates_and_keeps_original_source_observations(tmp_path):
    destination = tmp_path / "public_etf"
    prior = refresh_public_etfs(Client(missing_day="2026-10-12"), through="2026-11-04", output=destination, now=NOW)
    client = Client()
    report = refresh_public_etfs(client, through="2026-11-04", output=destination, now=NOW, repair_missing=True)
    assert client.calls == ["2026-10-12"]
    assert report["reused_complete_dates"] == 20
    assert report["gap_count"] == 0
    raw = json.loads((destination / "current.json").read_text())
    assert raw["reused_from_digest"] == prior["snapshot_digest"]
    assert read(tmp_path)["etf_aggregate"]["20"]["observed_etfs"] == 5


@pytest.mark.parametrize("alter", ["future", "unknown_unit", "calendar_gap", "wrong_code"])
def test_reader_rejects_false_metadata_even_with_recomputed_content_digest(tmp_path, alter):
    destination = tmp_path / "public_etf"
    refresh_public_etfs(Client(), through="2026-11-04", output=destination, now=NOW)
    path = destination / "current.json"
    raw = json.loads(path.read_text())
    if alter == "future":
        raw["fetched_at"] = "2026-12-01T00:00:00+00:00"
    elif alter == "unknown_unit":
        raw["share_unit"] = "shares"
    elif alter == "calendar_gap":
        raw["calendar"].pop(-3)
    else:
        raw["etf_shares"][PUBLIC_CODES[0]][0]["ts_code"] = "159919.SZ"
    raw.pop("content_digest")
    raw["content_digest"] = digest(raw)
    path.write_text(json.dumps(raw))
    assert read(tmp_path)["public_etf_snapshot"]["availability"] == "invalid"
    assert read(tmp_path)["etfs"] == []


@pytest.mark.parametrize("private_end", ["2026-11-03", "2026-11-04"])
def test_sources_use_one_target_for_coverage_and_keep_existing_same_date_NAV(tmp_path, private_end):
    refresh_public_etfs(Client(), through="2026-11-04", output=tmp_path / "public_etf", now=NOW)
    calendar = sessions_2026(date(2026, 9, 1), date.fromisoformat(private_end))
    raw = {"contract_version": "market_risk_raw_v1", "requested_through": private_end,
           "calendar": calendar, "indices": {}, "breadth": [], "gaps": [],
           "etf_shares": {code: [{"trade_date": day, "fd_share": 100} for day in calendar] for code in ETF_BASKET},
           "etf_navs": {code: [{"nav_date": day, "unit_nav": 2} for day in calendar] for code in ETF_BASKET}}
    raw["content_digest"] = digest(raw)
    (tmp_path / "current.json").write_text(json.dumps(raw))
    result = read(tmp_path)
    assert result["etf_aggregate"]["5"]["evaluation_through"] == "2026-11-04"
    if private_end == "2026-11-03":
        assert result["etf_aggregate"]["5"]["observed_etfs"] == 5
        assert result["etf_aggregate"]["5"]["nav_observed_etfs"] == 0
    else:
        assert result["etf_aggregate"]["5"]["observed_etfs"] == 8
        assert result["etf_aggregate"]["5"]["nav_observed_etfs"] == 8
        assert result["etfs"][0]["source"] == "tushare_fund_share"
