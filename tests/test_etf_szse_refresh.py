from copy import deepcopy
from datetime import date, datetime, timezone
import json

import pytest

from canonical_json import digest
from etf_szse_refresh import SZSE_CODES, parse_history, refresh_szse_etfs
from etf_public_refresh import PUBLIC_CODES, refresh_public_etfs
from market_calendar import sessions_2026
from market_risk import build_market_risk_status

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)
CALENDAR = sessions_2026(date(2026, 9, 30), date(2026, 11, 4))


def block(rows, *, nav=False, page=1, pages=1, total=None):
    return [{"metadata": {"catalogid": "fund_jjjz" if nav else "fund_jjgm", "pageno": page,
        "pagecount": pages, "pagesize": 20, "recordcount": len(rows) if total is None else total,
        "cols": {"nav_per_share" if nav else "current_size": "单位基金净值<br>(元)" if nav else "基金规模<br>(万份)"}}, "data": rows}]


def rows(code="159919.SZ", *, nav=False):
    return [{"fund_code": code[:6] + "  ", "nav_date" if nav else "size_date": day,
             "nav_per_share" if nav else "current_size": "4.1234" if nav else "1,234.56"} for day in CALENDAR]


def test_history_units_html_and_exact_pagination():
    data = rows()
    pages = [block(data[:20], page=1, pages=2, total=21), block(data[20:], page=2, pages=2, total=21)]
    parsed = parse_history(pages, "159919.SZ", CALENDAR)
    assert len(parsed) == 21
    assert parsed[-1] == {"ts_code": "159919.SZ", "trade_date": "2026-11-04", "fd_share": 1234.56}


@pytest.mark.parametrize("alter", ["truncated", "duplicate", "wrong_code", "wrong_date", "wrong_unit", "missing_value"])
def test_bad_share_history_does_not_become_coverage(alter):
    value = block(rows())
    if alter == "truncated": value[0]["metadata"]["recordcount"] = 22
    elif alter == "duplicate": value[0]["data"][1] = deepcopy(value[0]["data"][0])
    elif alter == "wrong_code": value[0]["data"][0]["fund_code"] = "159922"
    elif alter == "wrong_date": value[0]["data"][0]["size_date"] = "2026-10-01"
    elif alter == "wrong_unit": value[0]["metadata"]["cols"]["current_size"] = "规模(亿元)"
    else: value[0]["data"][0]["current_size"] = "--"
    with pytest.raises(ValueError): parse_history([value], "159919.SZ", CALENDAR)


def test_unpaginated_NAV_is_only_the_observed_overlap_not_full_window():
    value = block(rows(nav=True)[-11:-1], nav=True)
    value[0]["metadata"].update(pagesize=-1, pageno=0, pagecount=0, recordcount=0)
    parsed = parse_history([value], "159919.SZ", CALENDAR, nav=True)
    assert len(parsed) == 10
    assert parsed[-1]["nav_date"] == "2026-11-03"
    assert parsed[-1]["unit_nav"] == 4.1234
    value[0]["metadata"]["cols"]["nav_per_share"] = "单位基金净值(万元)"
    with pytest.raises(ValueError): parse_history([value], "159919.SZ", CALENDAR, nav=True)


class Client:
    def __init__(self, failed=False): self.failed = failed
    def get_history(self, code, calendar, *, nav=False):
        if self.failed: raise TimeoutError("private upstream detail")
        return parse_history([block(rows(code, nav=nav)[:-1] if nav else rows(code), nav=nav)], code, calendar, nav=nav), []


class SSEClient:
    def get_day(self, day):
        return [{"ts_code": code, "trade_date": day, "fd_share": 100} for code in PUBLIC_CODES], []


def read(tmp_path):
    return build_market_risk_status(snapshot_dir=tmp_path, database=tmp_path / "missing.db",
                                    manifest_path=tmp_path / "missing.json", now=NOW)


def test_eight_share_paths_remain_unconfirmed_and_missing_NAV_is_not_filled(tmp_path):
    refresh_public_etfs(SSEClient(), through="2026-11-04", output=tmp_path / "public_etf", now=NOW)
    folder = tmp_path / "public_etf_szse"
    report = refresh_szse_etfs(Client(), through="2026-11-04", output=folder, now=NOW)
    assert report["share_observations"] == 63
    before = (folder / "current.json").read_bytes()
    result = read(tmp_path)
    assert len(result["etfs"]) == 8
    for window in ("1", "5", "20"):
        assert result["etf_aggregate"][window]["observed_etfs"] == 8
        assert result["etf_aggregate"][window]["revision_unconfirmed_etfs"] == 3
        assert result["etf_aggregate"][window]["estimated_net_subscription_yuan"] is None
    szse = next(row for row in result["etfs"] if row["code"] == "159919.SZ")
    assert szse["share_revision_unverified"] is True
    assert szse["nav_through"] == "2026-11-03"
    assert szse["windows"]["1"]["share_change_notional_yuan"] is None
    assert result["status"] == "unavailable"
    assert before == (folder / "current.json").read_bytes()
    report = refresh_szse_etfs(Client(failed=True), through="2026-11-04", output=folder, now=NOW)
    assert report["status"] == "failed"
    assert report["current_snapshot_preserved"] is True
    assert before == (folder / "current.json").read_bytes()
    assert "private" not in (folder / "last_attempt.json").read_text()


@pytest.mark.parametrize("alter", ["revision_status", "nav_unit", "duplicate", "code"])
def test_reader_refuses_relabeling_or_corrupt_source_data(alter, tmp_path):
    folder = tmp_path / "public_etf_szse"
    refresh_szse_etfs(Client(), through="2026-11-04", output=folder, now=NOW)
    path = folder / "current.json"
    raw = json.loads(path.read_text())
    if alter == "revision_status": raw["share_revision_status"] = "final"
    elif alter == "nav_unit": raw["nav_unit"] = "CNY10000_per_share"
    elif alter == "duplicate": raw["etf_shares"][SZSE_CODES[0]].append(raw["etf_shares"][SZSE_CODES[0]][0])
    else: raw["etf_navs"][SZSE_CODES[0]][0]["ts_code"] = "510300.SH"
    raw.pop("content_digest")
    raw["content_digest"] = digest(raw)
    path.write_text(json.dumps(raw))
    assert read(tmp_path)["szse_etf_snapshot"]["availability"] == "invalid"
    assert read(tmp_path)["etfs"] == []
