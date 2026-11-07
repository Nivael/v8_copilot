"""Announcement inventories are review inputs, never an absence-of-events finding."""
from __future__ import annotations

from datetime import date, datetime
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from canonical_json import digest
from etf_issuer_nav import NAV_DEFINITIONS
from etf_document_capture import capture_status

VERSION = "etf_announcement_catalog_v1"
SELECTION_VERSION = "current_window_and_historical_share_titles_v1"
SHARE_TITLE = re.compile(r"折算|拆分|份额合并|基金合并|基金转型|终止.*基金|基金.*终止|最小申购|最小赎回|申赎单位")
SSE_URL = "https://www.sse.com.cn/disclosure/fund/announcement/"
SSE_API = "https://query.sse.com.cn/commonQuery.do"
SSE_SQL = "COMMON_PL_JJXX_JJGG_NEW_L"
JS_API = "https://www.jsfund.cn/servlet/json"
CHINA_API = "https://www.chinaamc.com/product/publishGgList.do"
SOURCES = {code: {"provider": "sse" if code.endswith(".SH") else "jsfund" if code in ("159919.SZ", "159922.SZ") else "chinaamc",
                  "url": SSE_URL if code.endswith(".SH") else f"https://www.jsfund.cn/main/fund/{code[:6]}/fundAnn.shtml" if code in ("159919.SZ", "159922.SZ")
                  else f"https://www.chinaamc.com/fund/{code[:6]}/jijingonggao.shtml?source=click"}
           for code in NAV_DEFINITIONS}


def document_id(code: str, published: str, title: str, url: str) -> str:
    return digest({"code": code, "published_on": published, "title": title, "url": url})


def validate_catalog(code: str, catalog: dict) -> None:
    if code not in SOURCES or catalog["source"] != SOURCES[code] or not catalog["records"]:
        raise ValueError("undeclared or empty announcement source")
    pages, count = catalog["source_declared_pages"], catalog["source_declared_count"]
    record_count = catalog["record_count"]
    if (isinstance(pages, bool) or not isinstance(pages, int) or not 1 <= pages <= 50
        or isinstance(record_count, bool) or not isinstance(record_count, int) or record_count <= 0
        or pages != math.ceil(record_count / (20 if SOURCES[code]["provider"] == "chinaamc" else 100))
        or count is None and SOURCES[code]["provider"] != "chinaamc"
        or count is not None and (isinstance(count, bool) or not isinstance(count, int) or count != len(catalog["records"]))):
        raise ValueError("invalid source-declared catalog coverage")
    seen = set()
    allowed = "www.sse.com.cn" if code.endswith(".SH") else "www.jsfund.cn" if SOURCES[code]["provider"] == "jsfund" else "www.chinaamc.com"
    for row in catalog["records"]:
        published = date.fromisoformat(row["published_on"]).isoformat()
        parsed = urlsplit(row["url"])
        expected = document_id(code, published, row["title"], row["url"])
        if (row["code"] != code or row["document_id"] != expected or expected in seen
            or not row["title"].strip() or parsed.scheme not in ("http", "https") or parsed.hostname != allowed
            or parsed.username or parsed.password or parsed.port not in (None, 80, 443)):
            raise ValueError("invalid, duplicate or foreign announcement")
        seen.add(expected)
    if catalog["record_count"] != len(seen):
        raise ValueError("incomplete announcement inventory")


def required_documents(catalog: dict, start: str, end: str, cutoff: str) -> list[dict]:
    # Selection prepares work. Neither no title hits nor successful extraction proves no share events.
    return [{**row, "review_reason": "window_or_later_publication" if start <= row["published_on"] <= cutoff else "historical_share_title"}
            for row in catalog["records"] if row["published_on"] <= cutoff
            and (row["published_on"] >= start or SHARE_TITLE.search(row["title"]))]


def load_announcement_catalog(directory: Path, now: datetime) -> tuple[dict, dict]:
    try:
        raw = json.loads((directory / "current.json").read_text())
        expected = raw.pop("content_digest")
        fetched = datetime.fromisoformat(raw["fetched_at"])
        start, end, cutoff = [date.fromisoformat(raw[key]) for key in ("window_start", "window_end", "publication_cutoff")]
        if (raw["contract_version"] != VERSION or digest(raw) != expected or raw["sources"] != SOURCES
            or raw["selection_version"] != SELECTION_VERSION or set(raw["catalogs"]) != set(SOURCES)
            or raw["availability_basis"] != "first_observed_at_fetch_not_historical_PIT"
            or fetched.tzinfo is None or fetched > now or start > end or end > cutoff
            or cutoff > now.astimezone(ZoneInfo("Asia/Shanghai")).date() or end >= now.astimezone(ZoneInfo("Asia/Shanghai")).date()
            or fetched.astimezone(ZoneInfo("Asia/Shanghai")).date() < cutoff):
            raise ValueError("invalid announcement snapshot binding/dates")
        for code, catalog in raw["catalogs"].items():
            validate_catalog(code, catalog)
            if any(row["published_on"] > cutoff.isoformat() for row in catalog["records"]):
                raise ValueError("catalog exceeds publication cutoff")
        return {"availability": "observed", "through": cutoff.isoformat(), "window_start": start.isoformat(), "window_end": end.isoformat(),
                "fetched_at": raw["fetched_at"], "content_digest": expected, "review_status": "not_reconciled"}, raw["catalogs"]
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
        return {"availability": "missing" if not (directory / "current.json").exists() else "invalid"}, {}


def announcement_status(directory: Path, now: datetime) -> dict:
    meta, catalogs = load_announcement_catalog(directory, now)
    rows = []
    for code, catalog in catalogs.items():
        selected = required_documents(catalog, meta["window_start"], meta["window_end"], meta["through"])
        rows.append({"code": code, "source_url": catalog["source"]["url"], "record_count": catalog["record_count"],
                     "oldest_publication": min(row["published_on"] for row in catalog["records"]),
                     "newest_publication": max(row["published_on"] for row in catalog["records"]),
                     "review_required_count": len(selected), "review_status": "not_reconciled",
                     "required_documents": sorted(selected, key=lambda row: (row["published_on"], row["document_id"]), reverse=True),
                     "historical_share_title_count": sum(bool(SHARE_TITLE.search(row["title"])) for row in catalog["records"])})
    documents = {doc["document_id"]: doc for row in rows for doc in row["required_documents"]}
    fulltext = capture_status(directory, meta["content_digest"], documents, now) if catalogs else {
        "availability": "missing_or_stale", "required": None, "text_available": None,
        "missing_or_unreadable": None, "semantic_review": "not_reconciled"}
    return {**meta, "declared_etfs": len(SOURCES), "catalog_etfs": len(catalogs), "catalogs": rows, "fulltext": fulltext,
            "record_count": sum(row["record_count"] for row in rows) if catalogs else None,
            "review_required_count": sum(row["review_required_count"] for row in rows) if catalogs else None,
            "corporate_actions_checked": False,
            "note": "目录完整性与事件核验分开；历史标题只筛出待审材料，取消、实施日、比例及基金对象需核对全文，不能据无标题命中认定没有份额事件。"}
