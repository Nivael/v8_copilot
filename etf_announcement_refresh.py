"""Explicit complete official/issuer announcement catalog collection for the fixed ETF basket."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import time
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from etf_announcements import CHINA_API, JS_API, SELECTION_VERSION, SOURCES, SSE_API, SSE_SQL, SSE_URL, VERSION, document_id, load_announcement_catalog, validate_catalog
from settings import DATA_ROOT

DEFAULT_OUTPUT = DATA_ROOT / "local_data/v8_copilot/market_risk/etf_announcements"


def record(code, published, title, url):
    published = date.fromisoformat(published).isoformat()
    title = unescape(title).strip()
    return {"code": code, "published_on": published, "title": title, "url": url,
            "document_id": document_id(code, published, title, url)}


class ChinaAnnouncements(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.inputs, self.pages, self.current, self.records = {}, set(), [], []
        self.depth, self.item_depth, self.item, self.anchor = 0, None, None, None
        if not re.search(r"</html>\s*$", text, re.I):
            raise ValueError("incomplete announcement HTML")
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name"):
            self.inputs[attrs["name"]] = attrs.get("value")
        if tag == "div":
            self.depth += 1
            if "li" in attrs.get("class", "").split():
                if self.item is not None:
                    raise ValueError("nested announcement item")
                self.item_depth, self.item = self.depth, {"urls": [], "date_parts": [], "title": []}
        if tag == "a":
            page = re.fullmatch(r"thisPage\((\d+)\)", attrs.get("onclick", ""))
            if page:
                self.pages.add(int(page[1]))
                if "cur" in attrs.get("class", "").split(): self.current.append(int(page[1]))
            if self.item is not None and attrs.get("href"):
                self.item["urls"].append(attrs["href"])
                self.anchor = True

    def handle_data(self, data):
        if self.item is not None:
            if self.anchor: self.item["title"].append(data)
            else: self.item["date_parts"].append(data)

    def handle_endtag(self, tag):
        if tag == "a": self.anchor = None
        if tag == "div":
            if self.item is not None and self.depth == self.item_depth:
                dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", " ".join(self.item["date_parts"]))
                if len(dates) != 1 or len(self.item["urls"]) != 1:
                    raise ValueError("ambiguous announcement row")
                self.records.append((dates[0], "".join(self.item["title"]).strip(), self.item["urls"][0]))
                self.item = self.item_depth = None
            self.depth -= 1


def parse_china_page(text: str, code: str, page: int) -> tuple[list[dict], int]:
    parsed = ChinaAnnouncements(text)
    if (parsed.inputs.get("fundcode") != code[:6] or parsed.current != [page] or not parsed.pages
        or not parsed.records or len(parsed.records) > 20 or page < max(parsed.pages) and len(parsed.records) != 20):
        raise ValueError("wrong ChinaAMC instrument/page")
    return [record(code, day, title, urljoin(CHINA_API, url)) for day, title, url in parsed.records], max(parsed.pages)


def parse_sse_page(payload: dict, code: str, page: int) -> tuple[list[dict], int, int]:
    meta = payload["pageHelp"]
    count = meta["total"]
    if (payload["sqlId"] != SSE_SQL or meta["pageNo"] != page or meta["pageSize"] != 100
        or meta["pageCount"] != math.ceil(count / 100) or count <= 0
        or len(payload["result"]) != min(100, count - (page - 1) * 100)
        or any(row["SECURITY_CODE"] != code[:6] for row in payload["result"])):
        raise ValueError("wrong SSE instrument/pagination")
    return [record(code, row["SSEDATE"], row["TITLE"], urljoin(SSE_URL, row["URL"])) for row in payload["result"]], meta["pageCount"], count


def parse_js_page(payload: dict, code: str, product_id: str, page: int) -> tuple[list[dict], int, int]:
    if str(payload["error_no"]) != "0" or len(payload["results"]) != 1:
        raise ValueError("JSFund announcement request failed")
    meta = payload["results"][0]
    count = meta["totalRows"]
    if (meta["currentPage"] != page or meta["numPerPage"] != 100 or count <= 0
        or meta["totalPages"] != math.ceil(count / 100) or meta["startIndex"] != (page - 1) * 100
        or meta["lastIndex"] != min(page * 100, count)
        or len(meta["data"]) != meta["lastIndex"] - meta["startIndex"]
        or any(row["product_id"] != product_id for row in meta["data"])):
        raise ValueError("wrong JSFund product/pagination")
    return [record(code, row["pub_date"], row["title"], urljoin(JS_API, row["attachment_url"] or f"/main/fund/noticedetails.shtml?adId={row['ad_id']}"))
            for row in meta["data"]], meta["totalPages"], count


class AnnouncementClient:
    def __init__(self, output: Path, *, repair=False):
        self.output, self.repair, self.next_request = output, repair, 0.0
        self.cutoff, self.head_digest = None, None

    def request(self, url, params=None, *, post=False, refs, use_cache=False):
        params = params or {}
        method = "POST" if post else "GET"
        binding = {"url": url, "params": params, "method": method, "publication_cutoff": self.cutoff, "head_digest": self.head_digest}
        key = digest(binding)
        path = self.output / "cache" / f"{key}.json"
        if self.repair and use_cache:
            try:
                ref = json.loads(path.read_text())
                observed = datetime.fromisoformat(ref["observed_at"])
                if any(ref[k] != v for k, v in binding.items()) or observed.tzinfo is None or observed > datetime.now(timezone.utc):
                    raise ValueError("cached request mismatch")
                content_hash = ref["response_sha256"]
                if not re.fullmatch(r"[a-f0-9]{64}", content_hash): raise ValueError("invalid response key")
                raw = (self.output / "responses" / f"{content_hash}.raw").read_bytes()
                if hashlib.sha256(raw).hexdigest() != content_hash: raise ValueError("cached response changed")
                refs.append(ref)
                return raw
            except (OSError, ValueError, KeyError, TypeError):
                pass
        address = url + ("?" + urlencode(params) if params and not post else "")
        referer = "https://www.sse.com.cn/" if url == SSE_API else "https://www.jsfund.cn/" if url.startswith("https://www.jsfund.cn/") else "https://www.chinaamc.com/"
        request = Request(address, data=urlencode(params).encode() if post else None, headers={"User-Agent": "Mozilla/5.0", "Referer": referer})
        for attempt in range(3):
            try:
                delay = self.next_request - time.monotonic()
                if delay > 0: time.sleep(delay)
                self.next_request = time.monotonic() + .4
                with urlopen(request, timeout=20) as response:
                    raw = response.read(4_000_001)
                    length = response.headers.get("Content-Length")
                if len(raw) > 4_000_000 or length is not None and len(raw) != int(length):
                    raise ValueError("oversized or incomplete response")
                break
            except (OSError, TimeoutError):
                if attempt == 2: raise
                time.sleep(2 * (attempt + 1))
        content_hash = hashlib.sha256(raw).hexdigest()
        folder = self.output / "responses"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{content_hash}.raw").write_bytes(raw)
        ref = {**binding, "response_sha256": content_hash, "observed_at": datetime.now(timezone.utc).isoformat(), "bytes": len(raw)}
        atomic_write_json(path, ref)
        refs.append(ref)
        return raw

    def get_catalog(self, code, cutoff):
        self.cutoff, self.head_digest = cutoff, None
        source = SOURCES[code]
        refs, rows, product_id = [], [], None
        if source["provider"] == "jsfund":
            html = self.request(source["url"], refs=refs).decode("utf-8")
            matches = re.findall(r'<input\s+id="product_id"\s+value="(\d+)"', html)
            if len(matches) != 1: raise ValueError("JSFund product identity missing")
            product_id = matches[0]
            identity = json.loads(self.request(JS_API, {"funcNo": "741011", "product_id": product_id}, post=True, refs=refs))
            if (str(identity["error_no"]) != "0" or len(identity["results"]) != 1
                or identity["results"][0]["product_code"] != code[:6] or identity["results"][0]["product_id"] != product_id):
                raise ValueError("JSFund identity disagrees with requested ETF")
        page, total_pages, total_count = 1, 1, None
        while page <= total_pages:
            if source["provider"] == "sse":
                params = {"sqlId": SSE_SQL, "isPagination": "true", "pageHelp.pageSize": 100, "pageHelp.pageNo": page,
                          "pageHelp.beginPage": page, "pageHelp.endPage": page, "pageHelp.cacheSize": 1,
                          "type": "inParams", "SECURITY_CODE": code[:6], "END_DATE": cutoff, "DATE_DESC": 1}
                payload = json.loads(self.request(SSE_API, params, refs=refs, use_cache=page > 1))
                records, pages, count = parse_sse_page(payload, code, page)
            elif source["provider"] == "jsfund":
                params = {"funcNo": "741015", "product_id": product_id, "curtpage": page, "numperpage": 100,
                          "keyword": "", "start_date": "", "end_date": cutoff.replace("-", ""), "select_time": "", "type": ""}
                payload = json.loads(self.request(JS_API, params, post=True, refs=refs, use_cache=page > 1))
                records, pages, count = parse_js_page(payload, code, product_id, page)
            else:
                params = {"fundcode": code[:6], "pageIndex": page, "title": "", "beginDate": "", "endDate": "", "isQuery": "true" if page == 1 else ""}
                text = self.request(CHINA_API, params, post=True, refs=refs, use_cache=page > 1).decode("utf-8")
                records, pages = parse_china_page(text, code, page)
                count = None
            if not 1 <= pages <= 50 or page > 1 and (pages != total_pages or count != total_count):
                raise ValueError("changing/excessive catalog pagination")
            total_pages, total_count = pages, count
            if page == 1:
                self.head_digest = digest({"code": code, "records": records, "pages": pages, "count": count})
            rows.extend(records)
            page += 1
        if total_count is not None and len(rows) != total_count:
            raise ValueError("incomplete catalog")
        result = {"source": source, "record_count": len(rows), "records": sorted(rows, key=lambda row: (row["published_on"], row["document_id"])),
                  "source_declared_count": total_count, "source_declared_pages": total_pages}
        validate_catalog(code, result)
        return result, refs


def refresh_announcements(client, *, start: str, end: str, cutoff: str, output: Path, now=None):
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(ZoneInfo("Asia/Shanghai")).date()
    begin, through, published = map(date.fromisoformat, (start, end, cutoff))
    if begin > through or through >= today or through > published or published > today:
        raise ValueError("completed observation window and nonfuture publication cutoff required")
    raw = {"contract_version": VERSION, "sources": SOURCES, "selection_version": SELECTION_VERSION,
           "window_start": start, "window_end": end, "publication_cutoff": cutoff, "fetched_at": now.isoformat(),
           "availability_basis": "first_observed_at_fetch_not_historical_PIT", "catalogs": {}, "responses": []}
    failures = []
    for code in SOURCES:
        try:
            catalog, refs = client.get_catalog(code, cutoff)
            validate_catalog(code, catalog)
            if any(row["published_on"] > cutoff for row in catalog["records"]):
                raise ValueError("source ignored publication cutoff")
            raw["catalogs"][code] = catalog
            raw["responses"].extend(refs)
        except Exception as exc:
            failures.append({"code": code, "error_type": type(exc).__name__})
    report = {"status": "failed" if failures else "complete", "failures": failures, "catalog_etfs": len(raw["catalogs"]),
              "declared_etfs": len(SOURCES), "publication_cutoff": cutoff, "completed_at": datetime.now(timezone.utc).isoformat()}
    previous, _ = load_announcement_catalog(output, now)
    if previous.get("through", "") > cutoff:
        report.update(status="failed", reason="would_regress_publication_cutoff")
    if report["status"] == "complete":
        raw["content_digest"] = digest(raw)
        atomic_write_json(output / "snapshots" / f"{raw['content_digest']}.json", raw)
        atomic_write_json(output / "current.json", raw)
        report.update(snapshot_digest=raw["content_digest"], records=sum(c["record_count"] for c in raw["catalogs"].values()))
    else:
        report["current_snapshot_preserved"] = True
    atomic_write_json(output / "last_attempt.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--publication-cutoff", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--repair", action="store_true")
    args = parser.parse_args()
    report = refresh_announcements(AnnouncementClient(args.output, repair=args.repair), start=args.start, end=args.end,
                                   cutoff=args.publication_cutoff, output=args.output)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__": raise SystemExit(main())
