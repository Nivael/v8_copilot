import json
from urllib.parse import parse_qs

import pytest

import data_refresh
from data_refresh import AnnouncementRefreshService, CninfoHttpClient, MaintenanceStateRepository, CNINFO_SOURCE_ID


def item(identity, day="2026-07-02", symbol="603398"):
    return {"announcementId": identity, "secCode": symbol, "orgId": "9900024444",
            "announcementTime": day, "announcementTitle": f"正式公告{identity}",
            "adjunctUrl": f"finalpage/{day}/{identity}.PDF"}


def page(items, total, more):
    return {"announcements": items, "totalAnnouncement": total, "totalRecordNum": total,
            "hasMore": more, "totalpages": 1}


def network(monkeypatch, pages, stocks=None):
    calls = []
    index = {"stockList": stocks if stocks is not None else [
        {"code": "603398", "orgId": "9900024444"},
        {"code": "002124", "orgId": "9900002441"},
    ]}

    class Response:
        def __init__(self, payload):
            self.raw = json.dumps(payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, *_):
            return self.raw

    def open_request(request, **_):
        form = parse_qs(request.data.decode()) if request.data else {}
        calls.append((request.full_url, form))
        if request.full_url.endswith("/new/data/szse_stock.json"):
            return Response(index)
        number = int(form["pageNum"][0])
        return Response(pages(number) if callable(pages) else pages[number - 1])

    monkeypatch.setattr(data_refresh, "urlopen", open_request)
    return calls


def fetch(client=None):
    return (client or CninfoHttpClient()).fetch(
        symbol="603398", start_date="2026-01-01", end_date="2026-07-03")


def test_short_page_with_more_flag_continues_and_binds_the_exact_issuer(monkeypatch):
    calls = network(monkeypatch, [page([item("A")], 3, True),
                                  page([item("B"), item("C")], 3, False)])
    client = CninfoHttpClient(page_size=100)
    rows = fetch(client)

    assert {row["announcement_id"] for row in rows} == {"A", "B", "C"}
    forms = [form for _, form in calls if form]
    assert [form["pageNum"] for form in forms] == [["1"], ["2"]]
    assert all(form["pageSize"] == ["30"] for form in forms)
    assert all(form["stock"] == ["603398,9900024444"] and form["column"] == ["sse"] for form in forms)
    assert all(not form.get("searchkey") for form in forms)
    coverage = client.coverage_for(symbol="603398", start_date="2026-01-01", end_date="2026-07-03")
    assert coverage["record_count"] == coverage["reported_total"] == 3
    assert coverage["page_count"] == 2 and coverage["terminal_has_more"] is False
    assert coverage["records_digest"] == data_refresh.hashlib.sha256(data_refresh._canonical(rows).encode()).hexdigest()


@pytest.mark.parametrize("payloads", [
    [page([item("A")], 3, True), page([item("A")], 3, True)],
    [page([item("A"), item("A")], 2, False)],
    [page([item("A")], 3, True), page([item("A"), item("B")], 3, False)],
])
def test_repeated_or_overlapping_records_do_not_claim_complete_coverage(monkeypatch, payloads):
    calls = network(monkeypatch, payloads)
    with pytest.raises(RuntimeError, match="重复"):
        fetch()
    assert len([form for _, form in calls if form]) <= 2


@pytest.mark.parametrize("payload", [
    page([item("A")], 3, False),
    page([], 3, True),
    page([item("A")], 0, False),
    {"error": "temporary upstream failure"},
    {**page([item("A")], 1, False), "hasMore": "false"},
    {**page([item("A")], 1, False), "totalAnnouncement": True},
    {**page([item("A")], 1, False), "totalRecordNum": 2},
])
def test_incomplete_or_malformed_pages_are_not_empty_successes(monkeypatch, payload):
    network(monkeypatch, [payload])
    with pytest.raises((RuntimeError, ValueError)):
        fetch()


def test_reported_total_cannot_change_between_pages(monkeypatch):
    network(monkeypatch, [page([item("A")], 3, True), page([item("B")], 2, False)])
    with pytest.raises(RuntimeError, match="总数"):
        fetch()


@pytest.mark.parametrize("bad_item", [
    item("A", symbol="002124"), item("A", day="2025-12-31"),
    {**item("A"), "announcementTitle": ""}, {**item("A"), "announcementId": ""},
])
def test_foreign_out_of_range_or_invalid_rows_cannot_be_silently_dropped(monkeypatch, bad_item):
    network(monkeypatch, [page([bad_item], 1, False)])
    with pytest.raises((RuntimeError, ValueError)):
        fetch()


def test_empty_confirmed_inventory_is_valid_and_has_a_bound_receipt(monkeypatch):
    network(monkeypatch, [page([], 0, False)])
    client = CninfoHttpClient()
    assert fetch(client) == []
    coverage = client.coverage_for(symbol="603398", start_date="2026-01-01", end_date="2026-07-03")
    assert coverage["record_count"] == 0 and coverage["terminal_has_more"] is False
    assert client.coverage_for(symbol="002124", start_date="2026-01-01", end_date="2026-07-03") is None


def test_unresolved_or_ambiguous_issuer_never_falls_back_to_keyword_search(monkeypatch):
    network(monkeypatch, [], stocks=[])
    with pytest.raises((RuntimeError, ValueError), match="主体"):
        fetch()
    network(monkeypatch, [], stocks=[{"code": "603398", "orgId": "A"}, {"code": "603398", "orgId": "B"}])
    with pytest.raises((RuntimeError, ValueError), match="主体"):
        fetch()


def old_refresh(tmp_path):
    root = tmp_path / "announcements"
    root.mkdir()
    overlay = root / "603398.json"
    overlay.write_text(json.dumps({"symbol": "603398", "source": "cninfo", "checked_through": "2026-07-03",
        "records": [{"announcement_id": "OLD", "symbol": "603398", "announcement_date": "2026-07-01",
                     "title": "旧公告", "body_text": "本地已保存的合成测试正文"}]}))
    state = MaintenanceStateRepository(tmp_path / "maintenance.sqlite3")
    state.record_success(run_id="DM-" + "A" * 20, source_id=CNINFO_SOURCE_ID, symbol="603398",
        fetch_start="2026-01-01", checked_through="2026-07-03", observed_as_of="2026-07-01",
        rows_seen=1, rows_written=1, metadata={"provider": "cninfo"}, started_at="2026-07-03T00:00:00+00:00")
    return root, overlay, state


def test_legacy_success_is_rechecked_and_only_verified_receipts_can_skip(tmp_path, monkeypatch):
    root, overlay, state = old_refresh(tmp_path)
    calls = network(monkeypatch, [page([item("OLD", "2026-07-01"), item("RECOVERED", "2026-02-01")], 2, False)])
    client = CninfoHttpClient()
    service = AnnouncementRefreshService(refresh_dir=root, base_database=tmp_path / "absent.sqlite3",
                                          state=state, provider=client)
    result = service.refresh(symbol="603398", through="2026-07-03")

    assert result.status == "success" and result.fetch_start == "2026-01-01"
    payload = json.loads(overlay.read_text())
    assert {row["announcement_id"] for row in payload["records"]} == {"OLD", "RECOVERED"}
    assert next(row for row in payload["records"] if row["announcement_id"] == "OLD")["body_text"] == "本地已保存的合成测试正文"
    assert payload["source_coverage"]["version"] == client.coverage_version
    assert state.get(CNINFO_SOURCE_ID, "603398").metadata["source_coverage"] == payload["source_coverage"]
    count = len(calls)
    assert service.refresh(symbol="603398", through="2026-07-03").status == "skipped"
    assert len(calls) == count


def test_failed_pagination_preserves_saved_bytes_and_last_success_boundary(tmp_path, monkeypatch):
    root, overlay, state = old_refresh(tmp_path)
    saved = overlay.read_bytes()
    before = state.get(CNINFO_SOURCE_ID, "603398")
    network(monkeypatch, [page([item("A")], 3, True), page([item("A")], 3, True)])
    service = AnnouncementRefreshService(refresh_dir=root, base_database=tmp_path / "absent.sqlite3",
                                          state=state, provider=CninfoHttpClient())
    with pytest.raises(RuntimeError, match="重复"):
        service.refresh(symbol="603398", through="2026-07-04")

    after = state.get(CNINFO_SOURCE_ID, "603398")
    assert overlay.read_bytes() == saved
    assert after.status == "failed" and after.checked_through == before.checked_through
    assert after.last_success_at == before.last_success_at


def test_page_limit_never_returns_a_partial_success(monkeypatch):
    network(monkeypatch, [page([item("A")], 3, True)])
    with pytest.raises(RuntimeError, match="安全上限"):
        fetch(CninfoHttpClient(max_pages=1))


@pytest.mark.parametrize("field,value", [
    ("title", "与抓取凭据不一致的标题"), ("raw_item", None), ("raw_item", "损坏的原始元数据"),
])
def test_changed_saved_metadata_invalidates_a_previous_success(tmp_path, monkeypatch, field, value):
    root, overlay, state = old_refresh(tmp_path)
    calls = network(monkeypatch, [page([item("OLD", "2026-07-01")], 1, False)])
    service = AnnouncementRefreshService(refresh_dir=root, base_database=tmp_path / "absent.sqlite3",
                                          state=state, provider=CninfoHttpClient())
    service.refresh(symbol="603398", through="2026-07-03")
    saved = json.loads(overlay.read_text())
    saved["records"][0][field] = value
    overlay.write_text(json.dumps(saved))
    count = len(calls)

    assert service.refresh(symbol="603398", through="2026-07-03").status == "success"
    assert len(calls) > count
    assert json.loads(overlay.read_text())["records"][0]["title"] == "正式公告OLD"


def test_narrow_receipt_cannot_skip_a_wider_explicit_request(tmp_path, monkeypatch):
    root, _, state = old_refresh(tmp_path)
    calls = network(monkeypatch, [page([item("OLD", "2026-07-01")], 1, False)])
    service = AnnouncementRefreshService(refresh_dir=root, base_database=tmp_path / "absent.sqlite3",
                                          state=state, provider=CninfoHttpClient())
    service.refresh(symbol="603398", through="2026-07-03", start_date="2026-06-01")
    count = len(calls)

    result = service.refresh(symbol="603398", through="2026-07-03", start_date="2026-01-01")
    assert result.status == "success" and result.fetch_start == "2026-01-01"
    assert len(calls) > count
    assert [form for _, form in calls if form][-1]["seDate"] == ["2026-01-01~2026-07-03"]


def test_a_failed_retry_cannot_reuse_an_earlier_in_memory_receipt(monkeypatch):
    network(monkeypatch, [page([item("A")], 1, False)])
    client = CninfoHttpClient()
    fetch(client)
    assert client.coverage_for(symbol="603398", start_date="2026-01-01", end_date="2026-07-03")
    network(monkeypatch, [{"error": "temporarily unavailable"}])

    with pytest.raises(ValueError):
        fetch(client)
    assert client.coverage_for(symbol="603398", start_date="2026-01-01", end_date="2026-07-03") is None
