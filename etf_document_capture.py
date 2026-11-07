"""Archive and extract selected primary documents; extraction is not semantic event review."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html import unescape
from html.parser import HTMLParser
from importlib.metadata import version
import io
import json
from pathlib import Path
import re
import time
from urllib.parse import parse_qs, quote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from canonical_json import digest
from data_refresh import atomic_write_json
from settings import DATA_ROOT

EXTRACTION_VERSION = "etf_primary_document_text_v2"
DEFAULT_OUTPUT = DATA_ROOT / "local_data/v8_copilot/market_risk/etf_announcements"


def extractor_digest():
    return digest({"module_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "pypdf": version("pypdf")})


class DocumentHTML(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links, self.parts, self.anchor, self.ignored = [], [], None, 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style"): self.ignored += 1
        if tag == "a": self.anchor = {"url": attrs.get("href", ""), "text": []}
        for key in (("src",) if tag in ("iframe", "embed") else ("data",) if tag == "object" else ()):
            if attrs.get(key): self.links.append(attrs[key])

    def handle_data(self, data):
        if not self.ignored: self.parts.append(data)
        if self.anchor is not None: self.anchor["text"].append(data)

    def handle_endtag(self, tag):
        if tag in ("script", "style"): self.ignored = max(0, self.ignored - 1)
        if tag == "a" and self.anchor is not None:
            address = self.anchor["url"]
            if ".pdf" in address.lower() or "AttachDownLoad.jsp" in address or "".join(self.anchor["text"]).strip().lower().endswith(".pdf"):
                self.links.append(address)
            self.anchor = None


def allowed_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme not in ("http", "https") or parsed.username or parsed.password or parsed.port not in (None, 80, 443)
        or parsed.hostname not in ("www.sse.com.cn", "www.jsfund.cn", "www.chinaamc.com")):
        raise ValueError("document URL outside declared primary hosts")
    return urlunsplit((parsed.scheme, parsed.netloc, quote(parsed.path, safe="/%"), parsed.query, ""))


def readable(text):
    return len(re.sub(r"\s+", "", text)) >= 80 and len(re.findall(r"[\u3400-\u9fff]", text)) >= 15 and "\ufffd" not in text


def pdf_text(raw):
    from pypdf import PdfReader
    if not raw.lstrip().startswith(b"%PDF-"):
        raise ValueError("primary document is not a PDF")
    reader = PdfReader(io.BytesIO(raw))
    if reader.is_encrypted or not 1 <= len(reader.pages) <= 500:
        raise ValueError("encrypted or excessive PDF")
    pages = [page.extract_text() or "" for page in reader.pages]
    if not readable("\n".join(pages)):
        raise ValueError("PDF requires visual/OCR review")
    return {"format": "pdf", "page_count": len(pages), "pages": pages}


def _sha_file(path, expected):
    return bool(re.fullmatch(r"[a-f0-9]{64}", expected)) and hashlib.sha256(path.read_bytes()).hexdigest() == expected


def document_binding(document):
    return {"document_id": document["document_id"], "code": document["code"], "source_url": document["url"]}


def valid_ready(result, output, document, catalog_digest):
    try:
        if (result["status"] != "text_available" or not result["responses"]
            or any(result.get(key) != value for key, value in document_binding(document).items())):
            return False
        source = allowed_url(document["url"])
        first = result["responses"][0]
        if urlsplit(source).path.endswith("/noticedetails.shtml"):
            ad_ids = parse_qs(urlsplit(source).query).get("adId", [])
            if len(ad_ids) != 1 or first["url"] != "https://www.jsfund.cn/servlet/json" or first["params"] != {"funcNo": "741021", "ad_id": ad_ids[0]}:
                return False
        elif first["url"] != source or first["params"]:
            return False
        for ref in result["responses"]:
            key = ref["response_sha256"]
            if (ref["catalog_digest"] != catalog_digest or allowed_url(ref["url"]) != ref["url"]
                or not re.fullmatch(r"[a-f0-9]{64}", key) or not _sha_file(output / "document_raw" / f"{key}.raw", key)):
                return False
        key = result["text_sha256"]
        if not re.fullmatch(r"[a-f0-9]{64}", key) or not _sha_file(output / "document_text" / f"{key}.json", key): return False
        payload = json.loads((output / "document_text" / f"{key}.json").read_text())
        pages = payload["pages"]
        return (isinstance(pages, list) and all(isinstance(page, str) for page in pages) and readable("\n".join(pages))
                and payload["format"] == result["format"] and payload["page_count"] == result["page_count"]
                and result["character_count"] == sum(map(len, pages))
                and (payload["format"] == "pdf" and type(payload["page_count"]) is int and payload["page_count"] == len(pages)
                     or payload["format"] == "issuer_html" and payload["page_count"] is None and len(pages) == 1))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def capture_status(output, catalog_digest, documents, now):
    try:
        raw = json.loads((output / "document_capture.json").read_text())
        expected = raw.pop("content_digest")
        fetched = datetime.fromisoformat(raw["completed_at"])
        if (digest(raw) != expected or raw["extraction_version"] != EXTRACTION_VERSION or raw["extractor_digest"] != extractor_digest()
            or raw["catalog_digest"] != catalog_digest or raw["required_document_ids"] != sorted(documents)
            or raw["semantic_review"] != "not_reconciled"
            or fetched.tzinfo is None or fetched > now or set(raw["documents"]) != set(documents)):
            raise ValueError("document capture binding mismatch")
        # Explicit validation also checks archived bytes, not only a success counter in the index.
        ready = sum(valid_ready(result, output, documents[key], catalog_digest) for key, result in raw["documents"].items())
        return {"availability": "observed", "required": len(documents), "text_available": ready,
                "missing_or_unreadable": len(documents) - ready, "completed_at": raw["completed_at"],
                "semantic_review": "not_reconciled", "content_digest": expected}
    except (OSError, ValueError, KeyError, TypeError):
        return {"availability": "missing_or_stale", "required": len(documents), "text_available": None,
                "missing_or_unreadable": None, "semantic_review": "not_reconciled"}


class DocumentClient:
    def __init__(self, output, catalog_digest, *, repair=False):
        self.output, self.catalog_digest, self.repair, self.next_request = output, catalog_digest, repair, 0.0

    def request(self, url, refs, *, params=None):
        url = allowed_url(url)
        params = params or {}
        binding = {"url": url, "params": params, "catalog_digest": self.catalog_digest}
        key = digest(binding)
        path = self.output / "document_cache" / f"{key}.json"
        if self.repair:
            try:
                ref = json.loads(path.read_text())
                body = self.output / "document_raw" / f"{ref['response_sha256']}.raw"
                observed = datetime.fromisoformat(ref["observed_at"])
                if (any(ref[k] != v for k, v in binding.items()) or observed.tzinfo is None or observed > datetime.now(timezone.utc)
                    or not _sha_file(body, ref["response_sha256"])):
                    raise ValueError("cached document response changed")
                refs.append(ref)
                return body.read_bytes()
            except (OSError, ValueError, KeyError, TypeError):
                pass
        from urllib.parse import urlencode
        request = Request(url, data=urlencode(params).encode() if params else None, headers={"User-Agent": "Mozilla/5.0"})
        for attempt in range(3):
            try:
                delay = self.next_request - time.monotonic()
                if delay > 0: time.sleep(delay)
                self.next_request = time.monotonic() + .4
                with urlopen(request, timeout=20) as response:
                    allowed_url(response.url)
                    raw = response.read(30_000_001)
                    length = response.headers.get("Content-Length")
                if len(raw) > 30_000_000 or length is not None and len(raw) != int(length):
                    raise ValueError("oversized or incomplete document")
                break
            except (OSError, TimeoutError):
                if attempt == 2: raise
                time.sleep(2 * (attempt + 1))
        key = hashlib.sha256(raw).hexdigest()
        folder = self.output / "document_raw"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{key}.raw").write_bytes(raw)
        ref = {**binding, "response_sha256": key, "observed_at": datetime.now(timezone.utc).isoformat(), "bytes": len(raw)}
        atomic_write_json(path, ref)
        refs.append(ref)
        return raw

    def capture(self, document):
        refs, url, html_content = [], document["url"], None
        try:
            if urlsplit(url).path.endswith("/noticedetails.shtml"):
                ad_id = parse_qs(urlsplit(url).query).get("adId", [])
                if len(ad_id) != 1 or not re.fullmatch(r"\d+", ad_id[0]): raise ValueError("ambiguous JSFund document ID")
                raw = self.request("https://www.jsfund.cn/servlet/json", refs, params={"funcNo": "741021", "ad_id": ad_id[0]})
                payload = json.loads(raw)
                if str(payload["error_no"]) != "0" or len(payload["results"]) != 1: raise ValueError("JSFund detail failed")
                detail = payload["results"][0]
                if (detail["ad_id"] != ad_id[0] or detail["pub_date"] != document["published_on"]
                    or "".join(unescape(detail["title"]).split()) != "".join(document["title"].split())):
                    raise ValueError("JSFund detail identity changed")
                attachment = detail.get("attachment_url", "")
                if attachment:
                    if "," in attachment: raise ValueError("multiple document attachments require review")
                    url = urljoin(url, attachment)
                    raw = self.request(url, refs)
                else:
                    html_content = detail.get("content", "")
            else:
                raw = self.request(url, refs)
            if html_content is not None or not raw.lstrip().startswith(b"%PDF-"):
                html = html_content if html_content is not None else raw.decode("utf-8")
                parsed = DocumentHTML(html)
                links = list(dict.fromkeys(urljoin(url, link) for link in parsed.links))
                if len(links) == 1:
                    raw = self.request(links[0], refs)
                    text = pdf_text(raw)
                elif not links and html_content is not None and readable("\n".join(parsed.parts)):
                    text = {"format": "issuer_html", "page_count": None, "pages": ["\n".join(parsed.parts)]}
                else:
                    raise ValueError("ambiguous attachment or HTML requires review")
            else:
                text = pdf_text(raw)
            body = json.dumps(text, ensure_ascii=False, sort_keys=True).encode()
            key = hashlib.sha256(body).hexdigest()
            folder = self.output / "document_text"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{key}.json").write_bytes(body)
            return {**document_binding(document), "status": "text_available", "format": text["format"], "page_count": text["page_count"],
                    "text_sha256": key, "character_count": sum(map(len, text["pages"])), "responses": refs}
        except Exception as exc:
            return {**document_binding(document), "status": "missing_or_unreadable", "error_type": type(exc).__name__, "responses": refs}


def capture_documents(output, *, repair=False, progress=None):
    from etf_announcements import load_announcement_catalog, required_documents
    code_digest = extractor_digest()
    now = datetime.now(timezone.utc)
    meta, catalogs = load_announcement_catalog(output, now)
    if not catalogs: raise ValueError("verified announcement catalog required")
    documents = {row["document_id"]: row for catalog in catalogs.values()
                 for row in required_documents(catalog, meta["window_start"], meta["window_end"], meta["through"])}
    old = {}
    if repair:
        try:
            raw = json.loads((output / "document_capture.json").read_text())
            expected = raw.pop("content_digest")
            if (digest(raw) == expected and raw["catalog_digest"] == meta["content_digest"]
                and raw["extractor_digest"] == code_digest and raw["extraction_version"] == EXTRACTION_VERSION):
                old = raw["documents"]
        except (OSError, ValueError, KeyError, TypeError): pass
    client, results = DocumentClient(output, meta["content_digest"], repair=repair), {}
    for number, (key, document) in enumerate(documents.items(), 1):
        previous = old.get(key)
        results[key] = previous if previous and valid_ready(previous, output, document, meta["content_digest"]) else client.capture(document)
        if progress and (number % 10 == 0 or number == len(documents)):
            progress({"documents_processed": number, "required": len(documents),
                      "text_available": sum(row["status"] == "text_available" for row in results.values())})
    current, _ = load_announcement_catalog(output, datetime.now(timezone.utc))
    if current.get("content_digest") != meta["content_digest"] or extractor_digest() != code_digest:
        raise ValueError("catalog or extractor changed during capture; current capture index preserved")
    raw = {"extraction_version": EXTRACTION_VERSION, "extractor_digest": code_digest, "catalog_digest": meta["content_digest"],
           "required_document_ids": sorted(documents), "documents": results, "completed_at": datetime.now(timezone.utc).isoformat(),
           "semantic_review": "not_reconciled"}
    raw["content_digest"] = digest(raw)
    atomic_write_json(output / "document_capture_snapshots" / f"{raw['content_digest']}.json", raw)
    atomic_write_json(output / "document_capture.json", raw)
    return capture_status(output, meta["content_digest"], documents, datetime.now(timezone.utc))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--repair", action="store_true")
    args = parser.parse_args()
    result = capture_documents(args.output, repair=args.repair, progress=lambda row: print(json.dumps(row), flush=True))
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("missing_or_unreadable") == 0 else 2


if __name__ == "__main__": raise SystemExit(main())
