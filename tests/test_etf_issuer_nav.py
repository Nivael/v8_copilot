from copy import deepcopy
from datetime import date, datetime, timezone
import json

import pytest

from canonical_json import digest
from etf_issuer_nav import NAV_DEFINITIONS, load_issuer_navs
from etf_nav_refresh import IssuerNAVClient, parse_chinaamc, parse_efunds, parse_huatai, parse_jsfund, parse_nffund, refresh_issuer_navs
from market_calendar import sessions_2026
from market_risk import ETF_BASKET, _with_issuer_navs, build_market_risk_status, etf_metrics, market_update_status

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)
CALENDAR = sessions_2026(date(2026, 8, 4), date(2026, 11, 4))


def test_html_parsers_choose_unit_NAV_not_accumulated_or_assets():
    js = '''<html><input name="FundCode" value="159919"><option value="159919" selected>ETF</option>
    <table class="mm_r_table7"><tr><td>日期</td><td>份额净值</td><td>累计净值</td></tr>
    <tr><td>2026-11-04</td><td>4.3628</td><td>2.0246</td></tr></table></html>'''
    assert parse_jsfund(js, "159919.SZ", CALENDAR)[0]["unit_nav"] == 4.3628
    with pytest.raises(ValueError): parse_jsfund(js, "159922.SZ", CALENDAR)
    with pytest.raises(ValueError): parse_jsfund(js[:-7], "159919.SZ", CALENDAR)
    china = '''<html><input name="fundcode" value="510330"><input name="beginDate" value="2026-08-04">
    <input name="endDate" value="2026-11-04"><table id="hoverBox1"><tr><th>净值日期</th><th>单位净值</th><th>累计净值</th><th>资产净值</th></tr></table>
    <table id="hoverBox1_1"><tr><td>2026-11-04</td><td><span>4.3583</span></td><td>2.1279</td><td>9999999</td></tr></table>
    <script>let currentPage = '1'; let totalPage = '4';</script></html>'''
    rows, pages = parse_chinaamc(china, "510330.SH", CALENDAR, 1)
    assert rows[0]["unit_nav"] == 4.3583 and pages == 4
    with pytest.raises(ValueError): parse_chinaamc(china, "510330.SH", CALENDAR, 2)
    with pytest.raises(ValueError): parse_chinaamc(china.replace("单位净值", "资产净值"), "510330.SH", CALENDAR, 1)


def test_json_and_literal_primary_fields_are_not_IOPV_or_accumulated_NAV():
    huatai = {"currentPage": 1, "totalPage": 7, "dataList": [{"date": "2026-11-04", "fundcode": "510300", "netvalue": "4.1785", "totalnetvalue": "1.8764"}]}
    assert parse_huatai(huatai, "510300.SH", CALENDAR, 1)[0][0]["unit_nav"] == 4.1785
    with pytest.raises(ValueError): parse_huatai(huatai, "510310.SH", CALENDAR, 1)
    text = 'mk_510310_1y="0_1_2_3_4;20261104_1.16038400_4.0609_2.1602_2.31;";'
    assert parse_efunds(text, "510310.SH", CALENDAR)[0]["unit_nav"] == 4.0609
    for invalid in (text.replace("0_1_2_3_4", "0_1_3_2_4"), text + "alert(1)", text.replace("510310", "510300"), text.replace("4.0609", "--")):
        with pytest.raises(ValueError): parse_efunds(invalid, "510310.SH", CALENDAR)


def test_ChinaAMC_query_flag_only_resets_first_page(tmp_path):
    calendar = CALENDAR[-21:]
    client = IssuerNAVClient(tmp_path)
    calls = []
    def request(url, params=None, **kwargs):
        calls.append(params)
        # The official form's isQuery=true resets pageIndex to page one.
        page = 1 if params["isQuery"] == "true" else params["pageIndex"]
        days = calendar[::-1][(page - 1) * 20:page * 20]
        rows = ''.join(f'<tr><td>{day}</td><td>4.3583</td><td>2.1279</td><td></td></tr>' for day in days)
        return f'''<html><input name="fundcode" value="510330"><input name="beginDate" value="{calendar[0]}">
        <input name="endDate" value="{calendar[-1]}"><table id="hoverBox1"><tr><th>净值日期</th><th>单位净值</th><th>累计净值</th><th>资产净值</th></tr></table>
        <table id="hoverBox1_1">{rows}</table><script>let currentPage = '{page}'; let totalPage = '2';</script></html>'''.encode()
    client.request = request
    rows, _ = client.get_navs("510330.SH", calendar)
    assert len(rows) == 21
    assert [(call["isQuery"], call["pageIndex"]) for call in calls] == [("true", 1), ("", 2)]


def nf_payload(days, *, page=1, total=61):
    return {"code": "ETS-5BP00000", "data": {"jjjzList": {"pageNum": page, "pageSize": 10, "size": len(days),
            "total": total, "pages": (total + 9) // 10, "list": [{"fdate": day.replace("-", ""), "fdate_ex": day,
            "fundCode": None, "fundNav": "6.6614", "ljfundNav": "2.2638"} for day in days]}}}


def test_NFFund_walks_unfiltered_history_to_lower_boundary_and_checks_every_page(tmp_path):
    client = IssuerNAVClient(tmp_path)
    calls = []
    def request(url, params=None, **kwargs):
        calls.append(params)
        page = params["curPage"]
        days = CALENDAR[::-1][(page - 1) * 10:page * 10]
        # Different totals outside the requested window do not replace the exact calendar check.
        return json.dumps(nf_payload(days, page=page, total=61 if page % 2 else 62)).encode()
    client.request = request
    rows, _ = client.get_navs("510500.SH", CALENDAR)
    assert len(rows) == 61 and rows[0]["nav_date"] == "2026-08-04"
    assert [call["curPage"] for call in calls] == list(range(1, 8))
    assert all("startDate" not in call for call in calls)
    payload = nf_payload(CALENDAR[-10:][::-1])
    assert parse_nffund(payload, "510500.SH", CALENDAR, 1)[0][-1]["unit_nav"] == 6.6614
    payload["data"]["jjjzList"]["total"] = 62
    payload["data"]["jjjzList"]["pageNum"] = 2
    with pytest.raises(ValueError): parse_nffund(payload, "510500.SH", CALENDAR, 1)


class Complete:
    def get_navs(self, code, calendar):
        return [{"ts_code": code, "nav_date": day, "unit_nav": 2} for day in calendar], []


def test_complete_snapshot_is_readonly_and_one_failed_fund_preserves_it(tmp_path):
    assert set(NAV_DEFINITIONS) == set(ETF_BASKET)
    report = refresh_issuer_navs(Complete(), through="2026-11-04", output=tmp_path, now=NOW)
    assert report["status"] == "complete" and report["nav_observations"] == 488
    before = (tmp_path / "current.json").read_bytes()
    meta, rows = load_issuer_navs(tmp_path, NOW)
    assert meta["through"] == "2026-11-04" and len(rows) == 8
    class Missing(Complete):
        def get_navs(self, code, calendar):
            if code == "159845.SZ": raise TimeoutError("private upstream details")
            return super().get_navs(code, calendar)
    report = refresh_issuer_navs(Missing(), through="2026-11-04", output=tmp_path, now=NOW)
    assert report["status"] == "failed" and report["complete_series"] == 7
    assert report["current_snapshot_preserved"]
    assert before == (tmp_path / "current.json").read_bytes()


def test_repair_reuses_only_verified_complete_series_for_exact_window(tmp_path):
    class Missing(Complete):
        def get_navs(self, code, calendar):
            if code == "159919.SZ": raise TimeoutError()
            return super().get_navs(code, calendar)
    first = refresh_issuer_navs(Missing(), through="2026-11-04", output=tmp_path, now=NOW)
    assert first["status"] == "failed" and first["complete_series"] == 7
    path = tmp_path / "staging/2026-11-04-61/510300.SH.json"
    path.write_text(path.read_text().replace('"unit_nav": 2', '"unit_nav": 3', 1))
    calls = []
    class Repair(Complete):
        def get_navs(self, code, calendar):
            calls.append(code)
            return super().get_navs(code, calendar)
    final = refresh_issuer_navs(Repair(), through="2026-11-04", output=tmp_path, now=NOW, repair=True)
    assert final["status"] == "complete" and final["reused_series"] == 6
    assert set(calls) == {"510300.SH", "159919.SZ"}
    assert "private" not in (tmp_path / "last_attempt.json").read_text()
    before = (tmp_path / "current.json").read_bytes()
    shorter = refresh_issuer_navs(Complete(), through="2026-11-04", sessions=21, output=tmp_path, now=NOW)
    assert shorter["reason"] == "would_regress_existing_window"
    assert before == (tmp_path / "current.json").read_bytes()


@pytest.mark.parametrize("alter", ["duplicate", "missing", "code", "field", "unit", "future", "value"])
def test_reader_refuses_corruption_even_with_recomputed_digest(tmp_path, alter):
    refresh_issuer_navs(Complete(), through="2026-11-04", output=tmp_path, now=NOW)
    path = tmp_path / "current.json"
    raw = json.loads(path.read_text())
    code = "159919.SZ"
    if alter == "duplicate": raw["etf_navs"][code].append(raw["etf_navs"][code][0])
    elif alter == "missing": raw["etf_navs"][code].pop(20)
    elif alter == "code": raw["etf_navs"][code][0]["ts_code"] = "159922.SZ"
    elif alter == "field": raw["definitions"][code]["field"] = "累计净值"
    elif alter == "unit": raw["nav_unit"] = "IOPV"
    elif alter == "future": raw["fetched_at"] = "2026-11-06T00:00:00+00:00"
    else: raw["etf_navs"][code][0]["unit_nav"] = True
    raw.pop("content_digest")
    raw["content_digest"] = digest(raw)
    path.write_text(json.dumps(raw))
    assert load_issuer_navs(tmp_path, NOW) == ({"availability": "invalid"}, {})


def share_row():
    return {"code": "159919.SZ", "group": "沪深300", "source": "szse_public", "share_revision_unverified": True,
            **etf_metrics([{"trade_date": day, "fd_share": 100 + i} for i, day in enumerate(CALENDAR)],
                          [{"nav_date": day, "unit_nav": 2} for day in CALENDAR[-11:-1]], CALENDAR)}


def test_NAV_enrichment_crosschecks_overlap_but_never_enables_flow_or_changes_share_revision(tmp_path):
    refresh_issuer_navs(Complete(), through="2026-11-04", output=tmp_path, now=NOW)
    meta, navs = load_issuer_navs(tmp_path, NOW)
    row = share_row()
    result = _with_issuer_navs([row], navs, meta)[0]
    assert result["nav_through"] == "2026-11-04" and result["nav_crosscheck_observations"] == 10
    assert result["nav_observation_count"] == 61 and result["nav_source"] == "嘉实"
    assert result["path"] == row["path"] and result["share_revision_unverified"]
    assert result["windows"]["20"]["share_change_notional_yuan"] == 400000
    assert result["windows"]["20"]["estimated_net_subscription_yuan"] is None
    assert result["windows"]["20"]["status"] == "corporate_actions_unchecked"
    assert _with_issuer_navs([row], navs, {**meta, "through": "2026-11-03"}) == [row]
    conflict = deepcopy(navs)
    conflict["159919.SZ"][-2]["unit_nav"] = 3
    result = _with_issuer_navs([row], conflict, meta)[0]
    assert result["nav_conflict_dates"] == ["2026-11-03"]
    assert result["nav_through"] == "2026-11-03" and result["nav_observation_count"] == 10
    assert result["windows"]["1"]["share_change_notional_yuan"] is None


def test_NAV_alone_does_not_create_shares_or_risk_assessment(tmp_path):
    refresh_issuer_navs(Complete(), through="2026-11-04", output=tmp_path / "issuer_nav", now=NOW)
    result = build_market_risk_status(snapshot_dir=tmp_path, database=tmp_path / "none", manifest_path=tmp_path / "none", now=NOW)
    assert result["status"] == "unavailable" and result["etfs"] == []
    assert result["issuer_nav_snapshot"]["availability"] == "observed"
    sources = {row["source_id"]: row for row in market_update_status(snapshot_dir=tmp_path, now=NOW)}
    assert sources["issuer_etf_nav"]["observation_count"] == 488
    assert sources["issuer_etf_nav"]["series_at_target"] == 8
