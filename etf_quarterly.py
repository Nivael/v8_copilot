"""Read quarter-specific share accounting from bound primary reports, without inferring current cash flows."""
from __future__ import annotations

import calendar
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from zoneinfo import ZoneInfo

from canonical_json import digest
from etf_document_capture import valid_ready
from etf_issuer_nav import NAV_DEFINITIONS

VERSION = "etf_quarterly_share_accounting_v1"
PARSER_SOURCE_DIGEST = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
NUMBER = r"(?:0|[1-9]\d{0,2}(?:,\d{3})+|[1-9]\d*)(?:\.\d{1,2})?"
PERIOD = re.compile(r"本报告期自(\d{4})年(\d{1,2})月(\d{1,2})日起至(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日止")


def compact(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def amount(text):
    value = Decimal(text.replace(",", ""))
    if not value.is_finite(): raise ValueError("nonfinite report amount")
    return value


def decimal_text(value):
    return format(value, "f")


def completed_quarter(through: str):
    target = date.fromisoformat(through)
    year, quarter = target.year, (target.month - 1) // 3 + 1
    end_month = quarter * 3
    end = date(year, end_month, calendar.monthrange(year, end_month)[1])
    if end > target:
        quarter -= 1
        if quarter == 0: year, quarter = year - 1, 4
        end_month = quarter * 3
        end = date(year, end_month, calendar.monthrange(year, end_month)[1])
    return year, quarter, date(year, (quarter - 1) * 3 + 1, 1).isoformat(), end.isoformat()


def _one(pattern, text):
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1: raise ValueError("missing or ambiguous report field")
    return matches[0]


def parse_report(pages: list[str], code: str, year: int, quarter: int) -> dict:
    """Accept a single-fund §6 table; multi-column or changed layouts remain unparsed."""
    if code not in NAV_DEFINITIONS or not pages or any(not isinstance(page, str) for page in pages):
        raise ValueError("unknown report identity")
    normalized = [compact(page) for page in pages]
    text = "\n".join(normalized)
    if f"{year}年第{quarter}季度报告" not in text or _one(r"基金主代码(\d{6})(?!\d)", text)[1] != code[:6]:
        raise ValueError("wrong report fund or quarter")
    match = _one(PERIOD.pattern, text)
    begin = date(int(match[1]), int(match[2]), int(match[3])).isoformat()
    end = date(int(match[4] or match[1]), int(match[5]), int(match[6])).isoformat()
    _, _, expected_begin, expected_end = completed_quarter(f"{year}-{quarter * 3:02d}-{calendar.monthrange(year, quarter * 3)[1]}")
    if (begin, end) != (expected_begin, expected_end): raise ValueError("report period is not the requested quarter")
    table_start = _one(r"§6开放式基金份额变动", text).end()
    following = _one(r"§7", text[table_start:]).start() + table_start
    block = text[table_start:following]
    if not block.startswith("单位:份"): raise ValueError("share table has wrong or missing unit")
    labels = [r"(?:本)?报告期期初基金份额总额", r"(?:本)?报告期期间基金总申购份额",
              r"减:(?:本)?报告期期间基金总赎回份额", r"(?:本)?报告期期间基金拆分变动份额(?:\([^)]{0,30}\))?",
              r"(?:本)?报告期期末基金份额总额"]
    fields = [_one(label + f"(?P<value>-?{NUMBER}|[-—–])(?=" + (labels[i + 1] if i < 4 else r"(?:注:|§|$)") + ")", block)
              for i, label in enumerate(labels)]
    # Numeric values are required for the accounting totals. A dash in the split row is preserved, never silently turned into zero.
    raw_values = [field["value"] for field in fields]
    if any(not re.fullmatch(NUMBER, raw_values[i]) for i in (0, 1, 2, 4)):
        raise ValueError("missing report accounting totals")
    opening, subscribed, redeemed, closing = [amount(raw_values[i]) for i in (0, 1, 2, 4)]
    split = None if raw_values[3] in ("-", "—", "–") else amount(raw_values[3])
    product_total = amount(_one(r"报告期末基金份额总额(" + NUMBER + r")份", text[:table_start])[1])
    if product_total != closing or min(opening, closing) <= 0: raise ValueError("product summary disagrees with the share table")
    residual = closing - opening - subscribed + redeemed
    if split is not None and residual != split: raise ValueError("share accounting does not balance")
    if split is None and residual != 0: raise ValueError("unexplained share accounting residual")
    off_begin = off_end = None
    if "场外" in block:
        off = _one(r"期初基金总份额包含场外份额(" + NUMBER + r")份;期末基金总份额包含场外份额(" + NUMBER + r")份", block)
        off_begin, off_end = amount(off[1]), amount(off[2])
        if off_begin > opening or off_end > closing: raise ValueError("off-exchange amount exceeds report total")
    table_page = next(i for i, page in enumerate(normalized, 1) if "§6开放式基金份额变动" in page)
    return {"code": code, "period_start": begin, "period_end": end, "table_page": table_page,
            "opening_shares": decimal_text(opening), "subscription_shares": decimal_text(subscribed),
            "redemption_shares": decimal_text(redeemed), "net_subscription_shares": decimal_text(subscribed - redeemed),
            "closing_shares": decimal_text(closing), "split_entry": raw_values[3],
            "reported_split_shares": decimal_text(split) if split is not None else None,
            "non_subscription_share_change": decimal_text(residual),
            "accounting_residual_shares": decimal_text(residual - split if split is not None else residual),
            "off_exchange_opening_shares": decimal_text(off_begin) if off_begin is not None else None,
            "off_exchange_closing_shares": decimal_text(off_end) if off_end is not None else None,
            "audit_status": "report_states_unaudited" if "本报告中财务资料未经审计" in text else "not_confirmed"}


def compare_daily(report: dict, etf: dict | None) -> dict:
    result = {"availability": "missing", "date": report["period_end"], "reported_shares": None,
              "difference_from_report_total": None, "difference_after_explicit_off_exchange": None,
              "source": etf.get("source") if etf else None, "source_url": etf.get("source_url") if etf else None, "display_reference_shares": "100",
              "source_rounding_rule": "not_confirmed"}
    if not etf or etf.get("source") not in ("sse_public", "szse_public"): return result
    matches = [point for point in etf.get("path", []) if point["date"] == report["period_end"]]
    if len(matches) != 1 or isinstance(matches[0]["shares"], bool) or matches[0]["shares"] is None: return result
    daily = Decimal(str(matches[0]["shares"])) * 10000
    if not daily.is_finite() or daily <= 0: return result
    closing = amount(report["closing_shares"])
    difference = daily - closing
    off = report["off_exchange_closing_shares"]
    after = difference + amount(off) if off is not None else None
    return {**result, "availability": "observed", "reported_shares": decimal_text(daily),
            "difference_from_report_total": decimal_text(difference),
            "difference_after_explicit_off_exchange": decimal_text(after) if after is not None else None,
            "within_display_reference": abs(difference) < 100,
            "within_reference_after_off_exchange": abs(after) < 100 if after is not None else None}


def quarterly_status(directory: Path, announcements: dict, etfs: list[dict], through: str | None, now: datetime) -> dict:
    base = {"version": VERSION, "availability": "missing", "reports": [], "observed_reports": 0, "declared_etfs": len(NAV_DEFINITIONS),
            "corporate_actions_checked": False, "note": "季报申赎为整个季度的份额披露，不是近两个月的资金金额；拆分栏横线保留原样，不能证明期间没有份额事件。报告期、披露日和本次取得时点分开，不作为季内当时已知信号。"}
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != PARSER_SOURCE_DIGEST:
        return {**base, "availability": "reload_required"}
    if through is None: return base
    year, quarter, begin, end = completed_quarter(through)
    base.update(period_start=begin, period_end=end, period_label=f"{year}Q{quarter}")
    if announcements.get("availability") != "observed" or announcements.get("fulltext", {}).get("availability") != "observed": return base
    try:
        capture = json.loads((directory / "document_capture.json").read_text())
        content_digest = capture.pop("content_digest")
        if (digest(capture) != content_digest or content_digest != announcements["fulltext"]["content_digest"]
            or capture["catalog_digest"] != announcements["content_digest"]
            or datetime.fromisoformat(capture["completed_at"]) > now):
            raise ValueError("quarterly capture binding mismatch")
    except (OSError, ValueError, TypeError, KeyError): return {**base, "availability": "invalid"}
    reports = []
    by_code = {row["code"]: row for row in etfs}
    for catalog in announcements["catalogs"]:
        code = catalog["code"]
        candidates = [row for row in catalog["required_documents"] if f"{year}年第{quarter}季度报告" in compact(row["title"])]
        pending = {"code": code, "availability": "missing" if not candidates else "invalid"}
        if len(candidates) != 1:
            reports.append(pending)
            continue
        doc = candidates[0]
        try:
            result = capture["documents"][doc["document_id"]]
            if (not valid_ready(result, directory, doc, capture["catalog_digest"])
                or not end < doc["published_on"] <= announcements["through"]):
                raise ValueError("unverified or incorrectly dated report document")
            observed = datetime.fromisoformat(result["responses"][-1]["observed_at"])
            if (observed.tzinfo is None or observed > datetime.fromisoformat(capture["completed_at"])
                or observed.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat() < doc["published_on"]):
                raise ValueError("invalid document availability time")
            body = (directory / "document_text" / f"{result['text_sha256']}.json").read_bytes()
            if hashlib.sha256(body).hexdigest() != result["text_sha256"]: raise ValueError("report text changed")
            report = parse_report(json.loads(body)["pages"], code, year, quarter)
            report.update(availability="observed", document_id=doc["document_id"], publication_date=doc["published_on"],
                          source_url=doc["url"], pdf_url=result["responses"][-1]["url"] if result["format"] == "pdf" else None,
                          document_observed_at=result["responses"][-1]["observed_at"], text_sha256=result["text_sha256"])
            report["daily_comparison"] = compare_daily(report, by_code.get(code))
            reports.append(report)
        except (OSError, ValueError, TypeError, KeyError, StopIteration): reports.append(pending)
    return {**base, "availability": "observed", "observed_reports": sum(row["availability"] == "observed" for row in reports),
            "reports": reports, "catalog_digest": announcements["content_digest"], "capture_digest": content_digest,
            "parser_digest": PARSER_SOURCE_DIGEST, "capture_completed_at": capture["completed_at"]}
