from copy import deepcopy
from datetime import datetime, timezone
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from canonical_json import digest
from etf_announcements import SOURCES, SSE_SQL, announcement_status, load_announcement_catalog, required_documents
from etf_announcement_refresh import AnnouncementClient, parse_china_page, parse_js_page, parse_sse_page, record, refresh_announcements
from market_risk import build_market_risk_status, market_update_status

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)


def sse_payload(count=2, page=1):
    rows = [{"SSEDATE": "2026-10-27", "SECURITY_CODE": "510300", "TITLE": f"测试公告 {i}",
             "URL": f"/disclosure/fund/announcement/c/2026-10-27/510300_{i}.pdf"}
            for i in range((page - 1) * 100, min(page * 100, count))]
    return {"sqlId": SSE_SQL, "pageHelp": {"total": count, "pageNo": page, "pageSize": 100, "pageCount": (count + 99) // 100}, "result": rows}


def test_source_specific_pagination_and_instrument_bindings():
    payload = sse_payload()
    rows, pages, count = parse_sse_page(payload, "510300.SH", 1)
    assert len(rows) == count == 2 and pages == 1
    with pytest.raises(ValueError): parse_sse_page(payload, "512100.SH", 1)
    payload["pageHelp"]["total"] = 3
    with pytest.raises(ValueError): parse_sse_page(payload, "510300.SH", 1)
    js = {"error_no": "0", "results": [{"currentPage": 1, "numPerPage": 100, "totalRows": 1, "totalPages": 1,
          "startIndex": 0, "lastIndex": 1, "data": [{"product_id": "371", "pub_date": "2026-10-28", "title": "公告",
          "attachment_url": "", "ad_id": "518516"}]}]}
    parsed = parse_js_page(js, "159919.SZ", "371", 1)[0]
    assert parsed[0]["url"] == "https://www.jsfund.cn/main/fund/noticedetails.shtml?adId=518516"
    with pytest.raises(ValueError): parse_js_page(js, "159922.SZ", "263", 1)


def test_ChinaAMC_publication_cell_is_independent_of_dates_in_the_title():
    html = '''<html><input name="fundcode" value="159845"><div class="li middle-box"><div class="item">
    <a href="../c/2026-05-29/941475.shtml">基金资料概要(2026-05-29)</a></div><div class="item">2026-05-30</div></div>
    <a onclick="thisPage(1)" class="cur">1</a></html>'''
    rows, pages = parse_china_page(html, "159845.SZ", 1)
    assert rows[0]["published_on"] == "2026-05-30" and pages == 1
    with pytest.raises(ValueError): parse_china_page(html, "510330.SH", 1)
    with pytest.raises(ValueError): parse_china_page(html[:-7], "159845.SZ", 1)
    with pytest.raises(ValueError): parse_china_page(html.replace('</html>', '<a onclick="thisPage(2)">2</a></html>'), "159845.SZ", 1)


def make_catalog(code):
    provider = SOURCES[code]["provider"]
    host = "https://www.sse.com.cn" if provider == "sse" else "https://www.jsfund.cn" if provider == "jsfund" else "https://www.chinaamc.com"
    rows = [record(code, "2022-07-30", "取消本次基金份额拆分", host + f"/a/{code[:6]}-cancel.pdf"),
            record(code, "2026-10-27", "季度报告", host + f"/a/{code[:6]}-report.pdf")]
    return {"source": SOURCES[code], "source_declared_pages": 1, "source_declared_count": None if provider == "chinaamc" else 2,
            "record_count": 2, "records": rows}


class Client:
    def get_catalog(self, code, cutoff): return make_catalog(code), []


def refresh(tmp_path, client=None):
    return refresh_announcements(client or Client(), start="2026-08-04", end="2026-11-04", cutoff="2026-11-05", output=tmp_path, now=NOW)


def test_cancellation_plans_results_and_lot_size_changes_all_remain_review_inputs():
    code = "512100.SH"
    titles = ["实施基金份额拆分的公告", "取消基金份额拆分的公告", "基金份额合并结果的公告", "调整最小申购、赎回单位的公告"]
    rows = [record(code, "2022-07-30", title, f"https://www.sse.com.cn/a/{i}.pdf") for i, title in enumerate(titles)]
    rows += [record(code, "2026-11-05", "观察窗结束后的披露", "https://www.sse.com.cn/a/after.pdf"),
             record(code, "2026-11-06", "未来公告", "https://www.sse.com.cn/a/future.pdf"),
             record(code, "2020-01-01", "历史季度报告", "https://www.sse.com.cn/a/old.pdf")]
    selected = required_documents({"records": rows}, "2026-08-04", "2026-11-04", "2026-11-05")
    assert len(selected) == 5 and {r["title"] for r in selected} == set(titles + ["观察窗结束后的披露"])
    assert selected[-1]["review_reason"] == "window_or_later_publication"


def test_complete_catalog_is_not_an_event_finding_and_readers_do_not_mutate_it(tmp_path):
    assert refresh(tmp_path)["records"] == 16
    before = (tmp_path / "current.json").read_bytes()
    status = announcement_status(tmp_path, NOW)
    assert status["availability"] == "observed" and status["catalog_etfs"] == 8
    assert status["record_count"] == 16 and status["review_required_count"] == 16
    assert status["corporate_actions_checked"] is False and status["review_status"] == "not_reconciled"
    assert all(row["review_status"] == "not_reconciled" for row in status["catalogs"])
    assert before == (tmp_path / "current.json").read_bytes()


@pytest.mark.parametrize("alter", ["code", "duplicate", "foreign_url", "declared_count", "pages", "future", "window", "source"])
def test_reader_refuses_rebound_or_incomplete_catalogs_even_after_digest_recalculation(tmp_path, alter):
    refresh(tmp_path)
    path = tmp_path / "current.json"
    raw = json.loads(path.read_text())
    catalog = raw["catalogs"]["510300.SH"]
    if alter == "code": catalog["records"][0]["code"] = "512100.SH"
    elif alter == "duplicate": catalog["records"][1] = deepcopy(catalog["records"][0])
    elif alter == "foreign_url":
        catalog["records"][0] = record("510300.SH", "2022-07-30", "取消本次基金份额拆分", "https://example.com/a.pdf")
    elif alter == "declared_count": catalog["source_declared_count"] = 3
    elif alter == "pages": catalog["source_declared_pages"] = 2
    elif alter == "future": catalog["records"][0] = record("510300.SH", "2026-11-06", "未来", "https://www.sse.com.cn/a.pdf")
    elif alter == "window": raw["window_end"] = "2026-11-05"
    else: raw["sources"]["510300.SH"]["provider"] = "different"
    raw.pop("content_digest")
    raw["content_digest"] = digest(raw)
    path.write_text(json.dumps(raw))
    assert load_announcement_catalog(tmp_path, NOW) == ({"availability": "invalid"}, {})


def test_failed_catalog_preserves_the_prior_snapshot(tmp_path):
    refresh(tmp_path)
    before = (tmp_path / "current.json").read_bytes()
    class Bad(Client):
        def get_catalog(self, code, cutoff):
            if code == "159845.SZ": raise TimeoutError("private upstream detail")
            return super().get_catalog(code, cutoff)
    result = refresh(tmp_path, Bad())
    assert result["status"] == "failed" and result["catalog_etfs"] == 7 and result["current_snapshot_preserved"]
    assert before == (tmp_path / "current.json").read_bytes()
    assert "private" not in (tmp_path / "last_attempt.json").read_text()


def test_catalog_integration_does_not_unlock_net_subscription_or_claim_same_day_publication(tmp_path):
    folder = tmp_path / "etf_announcements"
    refresh(folder)
    result = build_market_risk_status(snapshot_dir=tmp_path, database=tmp_path / "none", manifest_path=tmp_path / "none", now=NOW)
    assert result["etf_announcements"]["corporate_actions_checked"] is False
    assert result["etf_aggregate"]["recent"]["estimated_net_subscription_yuan"] is None
    update = next(row for row in market_update_status(snapshot_dir=tmp_path, now=NOW) if row['source_id']=='etf_announcements')
    assert update["date_basis"] == "catalog_search_cutoff" and update["observed_through_min"] == "2026-11-05"
    assert result["etf_announcements"]["catalogs"][0]["newest_publication"] == "2026-10-27"


def test_repair_refreshes_head_and_changes_cache_scope_when_catalog_grows(tmp_path, monkeypatch):
    calls, size = [], [101]
    class Response:
        def __init__(self, raw): self.raw, self.headers = raw, {"Content-Length": str(len(raw))}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return self.raw
    def open_request(request, **kwargs):
        page = int(parse_qs(urlsplit(request.full_url).query)["pageHelp.pageNo"][0])
        calls.append(page)
        return Response(json.dumps(sse_payload(size[0], page)).encode())
    monkeypatch.setattr("etf_announcement_refresh.urlopen", open_request)
    monkeypatch.setattr("etf_announcement_refresh.time.sleep", lambda _: None)
    client = AnnouncementClient(tmp_path, repair=True)
    assert client.get_catalog("510300.SH", "2026-11-05")[0]["record_count"] == 101
    size[0] = 102
    assert client.get_catalog("510300.SH", "2026-11-05")[0]["record_count"] == 102
    assert calls == [1, 2, 1, 2]
    client.get_catalog("510300.SH", "2026-11-05")
    assert calls == [1, 2, 1, 2, 1]  # Refresh head, reuse only unchanged second-page content.
