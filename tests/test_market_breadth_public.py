from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

import pytest

from canonical_json import digest
from market_breadth import SOURCES, load_public_breadth, st_name
from market_breadth_refresh import PublicBreadthClient, parse_sse, parse_szse, refresh_public_breadth
from market_risk import build_market_risk_status, market_update_status

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)
DAY = "2026-11-04"


def sse_pages():
    rows = [
        ["600000", "普通股票", 9, 10, -10, 100, 100000, "E110", "ASH", ""],
        ["600001", "*ST样本", 10, 10, 0, 20, 10, "E110", "ASH", ""],
        ["688001", "ST停牌", 0, 5, 0, 0, 0, "P010", "KSH", ""],
        ["900901", "B股", .5, 1, -50, 200, 200, "E110", "BSH", ""],
    ]
    return [{"date": 20261104, "time": 162904, "total": 4, "begin": i, "end": i + 2, "list": rows[i:i + 2]} for i in (0, 2)]


def szse_pages():
    rows = [
        {"jyrq": DAY, "zqdm": "000001", "zqjc": "深市&nbsp;样本", "ss": "8.00", "qss": "10.00", "sdf": "-20.00", "cjgs": "1.50", "cjje": "9.50"},
        {"jyrq": DAY, "zqdm": "300001", "zqjc": "ST无成交", "ss": "--", "qss": "4.00", "sdf": "0.00", "cjgs": "0.00", "cjje": "0.00"},
        {"jyrq": DAY, "zqdm": "200001", "zqjc": "深B", "ss": "1.00", "qss": "2.00", "sdf": "-50.00", "cjgs": "2.00", "cjje": "5.00"},
    ]
    cols = {"jyrq": "交易日期", "zqdm": "证券代码", "zqjc": "证券简称", "qss": "前收", "ss": "今收",
            "sdf": "涨跌幅<br>（%）", "cjgs": "成交量<br>(万股)", "cjje": "成交金额<br>(万元)"}
    return [[{"metadata": {"catalogid": "1815_stock_snapshot", "tabkey": "tab1", "recordcount": 3, "pagesize": 2,
             "pageno": i + 1, "pagecount": 2, "cols": cols}, "data": rows[i * 2:i * 2 + 2]}] for i in range(2)]


class Client:
    def get_venue(self, venue, through):
        block = parse_sse(sse_pages(), through, 2) if venue == "SSE" else parse_szse(szse_pages(), through)
        return block, []


def test_real_source_units_B_shares_and_no_trading_do_not_distort_breadth(tmp_path):
    report = refresh_public_breadth(Client(), through=DAY, output=tmp_path, now=NOW)
    assert report["status"] == "complete" and report["source_rows"] == 7 and report["a_share_rows"] == 5
    before = (tmp_path / "current.json").read_bytes()
    meta, result = load_public_breadth(tmp_path, NOW)
    assert meta["through"] == DAY
    assert result["listed_source_stocks"] == 5 and result["observed_trading_stocks"] == 3
    assert result["advancing"] == 0 and result["declining"] == 2 and result["flat"] == 1
    assert result["nontrading_stocks"] == 2
    assert result["median_return_pct"] == -10 and result["declining_share_pct"] == 66.666667
    assert result["declining_5pct_or_more"] == 2
    assert result["amount_yuan"] == 195010  # CNY SSE amounts + SZSE's 9.50 ten-thousand CNY.
    assert result["st_name_group"]["listed_source_stocks"] == 3
    assert result["st_name_group"]["observed_trading_stocks"] == 1
    assert result["st_name_group"]["median_return_pct"] == 0
    assert result["st_name_group"]["flat"] == 1
    assert result["historical_path_available"] is False
    assert sum(row["excluded_b_shares"] for row in result["venues"]) == 2
    assert "北交所" in result["scope"]
    assert before == (tmp_path / "current.json").read_bytes()


def test_rounded_percentages_do_not_invent_flat_stocks_or_cross_the_5pct_boundary():
    pages = sse_pages()
    pages[0]["list"][0][2:5] = [500.01, 500, 0]
    pages[0]["list"][1][2:5] = [19.01, 20.01, -5]
    from market_breadth import cross_section
    block = parse_sse(pages, DAY, 2)
    result = cross_section(block["rows"])
    assert result["advancing"] == 1 and result["declining"] == 1 and result["flat"] == 0
    assert result["declining_5pct_or_more"] == 0
    assert block["rows"][0]["reported_pct_chg"] == 0
    assert block["rows"][0]["pct_chg"] > 0


def test_verified_preferred_shares_are_separate_from_ordinary_A_shares():
    pages = szse_pages()
    preferred = {**pages[0][0]["data"][0], "zqdm": "140001", "zqjc": "宁行优01", "cjgs": "0.00", "cjje": "0.00", "sdf": "0.00"}
    pages[1][0]["data"].append(preferred)
    for page in pages: page[0]["metadata"]["recordcount"] = 4
    block = parse_szse(pages, DAY)
    assert len(block["rows"]) == 2 and block["excluded_b_shares"] == 1
    assert block["excluded_preferred_codes"] == ["140001"]
    preferred["zqjc"] = "unverified identity"
    with pytest.raises(ValueError, match="preferred-share identity"): parse_szse(pages, DAY)


@pytest.mark.parametrize('previous,close,expected',[(32.4,30.78,1),(10.4,9.88,1),(20.01,19.01,0),(100,94.99,1)])
def test_exact_five_percent_boundary_uses_decimal_prices_without_an_epsilon(previous,close,expected):
    from market_breadth import cross_section
    from market_breadth_refresh import quote
    row=quote('300001','边界样本',DAY,close,previous,-5,100,1000,venue='SZSE')
    assert cross_section([row])['declining_5pct_or_more']==expected


@pytest.mark.parametrize("alter", ["date", "intraday", "different_time", "missing", "duplicate", "type", "return", "boundaries", "columns"])
def test_SSE_incomplete_or_inconsistent_snapshot_is_rejected(alter):
    pages = sse_pages()
    if alter == "date": pages[0]["date"] = 20261103
    elif alter == "intraday": pages[0]["time"] = 145959
    elif alter == "different_time": pages[1]["time"] = 162905
    elif alter == "missing": pages.pop()
    elif alter == "duplicate": pages[1]["list"][0] = pages[0]["list"][0]
    elif alter == "type": pages[0]["list"][0][8] = "FUND"
    elif alter == "return": pages[0]["list"][0][4] = 10
    elif alter == "boundaries": pages[1]["end"] = 5
    else: pages[0]["list"][0].pop()
    with pytest.raises(ValueError): parse_sse(pages, DAY, 2)


@pytest.mark.parametrize("alter", ["date", "missing", "duplicate", "unit", "catalog", "tab", "count", "format", "fund_code"])
def test_SZSE_wrong_scope_pagination_dates_or_units_are_rejected(alter):
    pages = szse_pages()
    if alter == "date": pages[0][0]["data"][0]["jyrq"] = "2026-11-03"
    elif alter == "missing": pages.pop()
    elif alter == "duplicate": pages[1][0]["data"][0] = pages[0][0]["data"][0]
    elif alter == "unit": pages[1][0]["metadata"]["cols"]["cjje"] = "成交金额<br>(亿元)"
    elif alter == "catalog": pages[1][0]["metadata"]["catalogid"] = "another-report"
    elif alter == "tab": pages[1][0]["metadata"]["tabkey"] = "tab2"
    elif alter == "count": pages[1][0]["metadata"]["recordcount"] = 4
    elif alter == "format": pages[0][0]["data"][0]["cjgs"] = "1,2"
    else: pages[0][0]["data"][0]["zqdm"] = "159919"
    with pytest.raises(ValueError): parse_szse(pages, DAY)


@pytest.mark.parametrize("name,expected", [("ST金花", True), ("*ST清越", True), ("ＳＴ公司", True), ("S*ST样本", True), ("SST样本", True), ("普通ST字样", False), ("浦发银行", False)])
def test_ST_group_is_only_a_current_name_prefix(name, expected):
    assert st_name(name) is expected


def test_one_failed_exchange_preserves_current_and_does_not_leak_upstream_details(tmp_path):
    refresh_public_breadth(Client(), through=DAY, output=tmp_path, now=NOW)
    before = (tmp_path / "current.json").read_bytes()
    class Failed(Client):
        def get_venue(self, venue, through):
            if venue == "SZSE": raise RuntimeError("private upstream detail")
            return super().get_venue(venue, through)
    report = refresh_public_breadth(Failed(), through=DAY, output=tmp_path, now=NOW)
    assert report["status"] == "failed" and report["complete_venues"] == 1
    assert report["current_snapshot_preserved"]
    assert (tmp_path / "current.json").read_bytes() == before
    assert "private" not in (tmp_path / "last_attempt.json").read_text()


@pytest.mark.parametrize("alter", ["count", "inactive", "date", "boolean", "source", "unit", "future"])
def test_local_reader_rechecks_schema_even_with_recomputed_digest(tmp_path, alter):
    refresh_public_breadth(Client(), through=DAY, output=tmp_path, now=NOW)
    path = tmp_path / "current.json"
    raw = json.loads(path.read_text())
    venue = raw["venues"]["SSE"]
    if alter == "count": venue["excluded_b_shares"] += 1
    elif alter == "inactive": venue["rows"][2]["pct_chg"] = 0
    elif alter == "date": venue["rows"][0]["trade_date"] = "2026-11-03"
    elif alter == "boolean": venue["rows"][0]["volume"] = True
    elif alter == "source": raw["sources"]["SSE"]["select"] = "code,name,last"
    elif alter == "unit": venue["amount_unit"] = "CNY_10000"
    else: raw["fetched_at"] = "2026-11-06T00:00:00+00:00"
    raw.pop("content_digest")
    raw["content_digest"] = digest(raw)
    path.write_text(json.dumps(raw))
    assert load_public_breadth(tmp_path, NOW) == ({"availability": "invalid"}, {"status": "missing"})


def test_public_breadth_integrates_without_promoting_a_daily_name_group_to_ST_history(tmp_path):
    folder = tmp_path / "public_breadth"
    refresh_public_breadth(Client(), through=DAY, output=folder, now=NOW)
    before = (folder / "current.json").read_bytes()
    result = build_market_risk_status(snapshot_dir=tmp_path, database=tmp_path / "none", manifest_path=tmp_path / "none", now=NOW)
    assert result["breadth"]["source"] == "exchange_public"
    assert result["breadth"]["through"] == DAY
    assert result["market_coverage"]["st_style_at_target"] is False
    assert result["current_risk_assessment"] == "not_calibrated"
    assert result["parameters"]["breadth_st_group_version"] == "current_quote_name_prefix_v1"
    sources = {row["source_id"]: row for row in market_update_status(snapshot_dir=tmp_path, now=NOW)}
    assert sources["exchange_breadth"]["observation_count"] == 5
    assert sources["exchange_breadth"]["series_at_target"] == 2
    assert (folder / "current.json").read_bytes() == before


def test_repair_checks_actual_response_bytes_before_reusing_a_page(tmp_path, monkeypatch):
    payload = szse_pages()[0]
    raw = json.dumps(payload).encode()
    key = hashlib.sha256(raw).hexdigest()
    params = {"CATALOGID": "1815_stock_snapshot", "PAGENO": 1}
    ref = {"venue": "SZSE", "url": SOURCES["SZSE"]["api_url"], "params": params, "response_sha256": key,
           "observed_at": "2026-11-04T20:00:00+00:00", "bytes": len(raw)}
    request_key = digest({"url": ref["url"], "params": params})
    (tmp_path / "responses").mkdir()
    (tmp_path / "cache").mkdir()
    response_path = tmp_path / "responses" / f"{key}.json"
    response_path.write_bytes(raw)
    (tmp_path / "cache" / f"{request_key}.json").write_text(json.dumps(ref))
    client = PublicBreadthClient(tmp_path, repair=True)
    calls = []
    class Response:
        headers = {"Content-Length": str(len(raw))}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return raw
    def open_request(*args, **kwargs):
        calls.append(args[0].full_url)
        return Response()
    monkeypatch.setattr("market_breadth_refresh.urlopen", open_request)
    assert client.request("SZSE", params, cache=True)[0] == payload
    assert calls == []
    response_path.write_bytes(b"changed")
    assert client.request("SZSE", params, cache=True)[0] == payload
    assert len(calls) == 1 and "PAGENO=1" in calls[0]


def test_client_follows_report_declared_page_count(tmp_path):
    client = PublicBreadthClient(tmp_path)
    pages = szse_pages()
    calls = []
    def request(venue, params, **kwargs):
        calls.append(params)
        return deepcopy(pages[params["PAGENO"] - 1]), {}
    client.request = request
    block, refs = client.get_venue("SZSE", DAY)
    assert len(refs) == 2 and block["received_total"] == 3
    assert sorted(row["PAGENO"] for row in calls) == [1, 2]
    assert all(row["txtBeginDate"] == DAY and row["txtEndDate"] == DAY for row in calls)
