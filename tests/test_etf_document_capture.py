from datetime import datetime, timezone
import io
import json

import pytest
from pypdf import PdfWriter

from canonical_json import digest
from etf_announcement_refresh import record
from etf_announcements import announcement_status, load_announcement_catalog, required_documents
from etf_document_capture import DocumentClient, capture_documents, capture_status
from test_etf_announcements import refresh

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)
BODY = "这是测试公告正文，包含基金名称、生效日期以及实施情况，材料可读不能代替事件核验。" * 4


@pytest.fixture
def captured(tmp_path, monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None): return NOW
    monkeypatch.setattr("etf_document_capture.datetime", Clock)
    refresh(tmp_path)
    meta, catalogs = load_announcement_catalog(tmp_path, NOW)
    documents = {row["document_id"]: row for catalog in catalogs.values()
                 for row in required_documents(catalog, meta["window_start"], meta["window_end"], meta["through"])}
    # Exercise actual capture/index/archive paths without depending on live issuer responses.
    from etf_document_capture import pdf_text as original_pdf_text
    def text_document(raw):
        if raw == b"%PDF-synthetic-fixture": return {"format": "pdf", "page_count": 1, "pages": [BODY]}
        return original_pdf_text(raw)
    monkeypatch.setattr("etf_document_capture.pdf_text", text_document)
    calls = []
    class Response:
        def __init__(self, url):
            self.url, self.headers = url, {"Content-Length": "22"}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return b"%PDF-synthetic-fixture"
    def open_request(request, **kwargs):
        calls.append(request.full_url)
        response = Response(request.full_url)
        response.headers["Content-Length"] = str(len(b"%PDF-synthetic-fixture"))
        return response
    monkeypatch.setattr("etf_document_capture.urlopen", open_request)
    monkeypatch.setattr("etf_document_capture.time.sleep", lambda _: None)
    result = capture_documents(tmp_path)
    return tmp_path, meta, documents, result, calls


def test_extraction_is_bound_to_catalog_and_does_not_close_event_review(captured, monkeypatch):
    output, meta, documents, result, calls = captured
    assert result["text_available"] == result["required"] == 16
    assert result["semantic_review"] == "not_reconciled"
    before = (output / "document_capture.json").read_bytes()
    status = announcement_status(output, NOW)
    assert status["fulltext"]["text_available"] == 16
    assert status["review_required_count"] == 16 and status["corporate_actions_checked"] is False
    assert before == (output / "document_capture.json").read_bytes()
    monkeypatch.setattr("etf_document_capture.urlopen", lambda *a, **k: pytest.fail("repair must reuse verified archived bytes"))
    assert capture_documents(output, repair=True)["text_available"] == 16
    assert len(calls) == 16


@pytest.mark.parametrize("alter", ["raw", "text", "wrong_code", "wrong_source", "text_count", "catalog", "extractor", "version", "semantic"])
def test_corrupted_bytes_or_rebound_metadata_cannot_keep_a_full_ready_count(captured, alter):
    output, meta, documents, _, _ = captured
    path = output / "document_capture.json"
    raw = json.loads(path.read_text())
    first = next(iter(raw["documents"].values()))
    if alter == "raw":
        (output / "document_raw" / f"{first['responses'][0]['response_sha256']}.raw").write_bytes(b"corrupt")
    elif alter == "text":
        (output / "document_text" / f"{first['text_sha256']}.json").write_text("{}")
    elif alter == "wrong_code": first["code"] = "outside_basket"
    elif alter == "wrong_source": first["responses"][0]["url"] = "https://www.sse.com.cn/different.pdf"
    elif alter == "text_count": first["character_count"] += 1
    elif alter == "catalog": raw["catalog_digest"] = "changed"
    elif alter == "extractor": raw["extractor_digest"] = "changed"
    elif alter == "version": raw["extraction_version"] = "etf_primary_document_text_v1"
    else: raw["semantic_review"] = "approved"
    raw.pop("content_digest")
    raw["content_digest"] = digest(raw)
    path.write_text(json.dumps(raw))
    result = capture_status(output, meta["content_digest"], documents, NOW)
    assert result["text_available"] != 16
    assert result["semantic_review"] == "not_reconciled"


@pytest.mark.parametrize("change", ["catalog", "extractor"])
def test_inputs_changing_during_capture_preserve_the_prior_index(captured, monkeypatch, change):
    output, meta, _, _, _ = captured
    before = (output / "document_capture.json").read_bytes()
    if change == "catalog":
        real = load_announcement_catalog
        def load(directory, now):
            changed, catalogs = real(directory, now)
            return {**changed, "content_digest": "changed"}, catalogs
        # First load is bound; the second detects a changed input.
        calls = iter([False, True])
        monkeypatch.setattr("etf_announcements.load_announcement_catalog", lambda directory, now: load(directory, now) if next(calls) else real(directory, now))
    else:
        from etf_document_capture import extractor_digest
        original = extractor_digest()
        values = iter([original, "changed"])
        monkeypatch.setattr("etf_document_capture.extractor_digest", lambda: next(values))
    with pytest.raises(ValueError, match="changed during capture"):
        capture_documents(output, repair=True)
    assert before == (output / "document_capture.json").read_bytes()


def test_js_detail_identity_and_attachment_are_checked_before_readiness(tmp_path, monkeypatch):
    document = record("159919.SZ", "2026-10-28", "基金公告", "https://www.jsfund.cn/main/fund/noticedetails.shtml?adId=123")
    detail = {"ad_id": "123", "pub_date": "2026-10-28", "title": "基金公告", "content": f"<p>{BODY}</p>", "attachment_url": ""}
    client = DocumentClient(tmp_path, "catalog")
    monkeypatch.setattr(client, "request", lambda *args, **kwargs: json.dumps({"error_no": "0", "results": [detail]}).encode())
    assert client.capture(document)["format"] == "issuer_html"
    detail["ad_id"] = "124"
    assert client.capture(document)["status"] == "missing_or_unreadable"
    detail["ad_id"] = "123"
    detail["content"] = '<a href="/cms/Services/AttachDownLoad.jsp?id=124">文件.pdf</a>'
    # A link label by itself is never treated as the announcement body.
    assert client.capture(document)["status"] == "missing_or_unreadable"


def test_scanned_or_empty_pdf_is_pending_and_keeps_its_source_identity(tmp_path, monkeypatch):
    writer, buf = PdfWriter(), io.BytesIO()
    writer.add_blank_page(width=300, height=300)
    writer.write(buf)
    document = record("512100.SH", "2026-10-27", "基金公告", "https://www.sse.com.cn/a.pdf")
    client = DocumentClient(tmp_path, "catalog")
    monkeypatch.setattr(client, "request", lambda *args, **kwargs: buf.getvalue())
    result = client.capture(document)
    assert result["status"] == "missing_or_unreadable"
    assert result["document_id"] == document["document_id"] and result["code"] == "512100.SH"
