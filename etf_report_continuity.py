"""Reconcile adjacent reported whole-fund totals, without converting them into current flows."""
from __future__ import annotations

from datetime import date, datetime, timedelta
import hashlib
from pathlib import Path

from canonical_json import digest
from etf_issuer_nav import NAV_DEFINITIONS
from etf_quarterly import (VERSION as QUARTERLY_VERSION, amount, compact, decimal_text,
                           load_report_capture, parse_midyear_report, read_bound_report)

VERSION = "etf_report_continuity_v1"


def parser_digest():
    root = Path(__file__).parent
    return digest({name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                   for name in (Path(__file__).name, "etf_quarterly.py")})


PARSER_DIGEST = parser_digest()


def compare_adjacent_reports(previous, following):
    result = {"availability": "missing", "total_relation": "not_compared", "total_difference_shares": None,
              "off_exchange_relation": "not_disclosed_in_both", "off_exchange_difference_shares": None}
    if previous.get("availability") != "observed" or following.get("availability") != "observed": return result
    if (previous["code"] != following["code"] or previous.get("share_scope") != "reported_whole_fund_total"
        or following.get("share_scope") != previous["share_scope"] or previous.get("share_unit") != "fund_share"
        or following.get("share_unit") != previous["share_unit"]
        or date.fromisoformat(previous["period_end"]) + timedelta(days=1) != date.fromisoformat(following["period_start"])):
        return {**result, "availability": "incompatible"}
    difference = amount(following["opening_shares"]) - amount(previous["closing_shares"])
    result.update(availability="observed", total_relation="equal" if difference == 0 else "different",
                  total_difference_shares=decimal_text(difference))
    left, right = previous["off_exchange_closing_shares"], following["off_exchange_opening_shares"]
    if left is not None and right is not None:
        off = amount(right) - amount(left)
        result.update(off_exchange_relation="equal" if off == 0 else "different",
                      off_exchange_difference_shares=decimal_text(off))
    return result


def report_continuity_status(directory: Path, announcements: dict, quarterly: dict, now: datetime) -> dict:
    base = {"version": VERSION, "availability": "missing", "reports": [], "declared_etfs": len(NAV_DEFINITIONS),
            "observed_midyear_reports": 0, "compared_etfs": 0, "matched_etfs": 0, "mismatched_etfs": 0,
            "corporate_actions_checked": False, "comparison_basis": "reported_whole_fund_totals",
            "note": "中期报告反映上半年，不代表近两个月的申赎。这里只核对中报期末与三季报期初的已披露基金总份额；相等不证明期间没有份额事件，也不识别资金身份。场外份额未明确披露时保留未知。"}
    if parser_digest() != PARSER_DIGEST: return {**base, "availability": "reload_required"}
    if not quarterly.get("period_start") or not quarterly.get("period_end"): return base
    if quarterly.get("period_start", "")[4:] != "-07-01" or quarterly.get("period_end", "")[4:] != "-09-30":
        return {**base, "availability": "not_applicable"}
    try:
        year = date.fromisoformat(quarterly["period_start"]).year
        if quarterly["period_end"] != f"{year}-09-30": raise ValueError("unmatched quarterly year")
        base.update(period_start=f"{year}-01-01", period_end=f"{year}-06-30",
                    following_period_start=f"{year}-07-01", following_period_end=f"{year}-09-30")
        if (announcements.get("availability") != "observed"
            or announcements.get("fulltext", {}).get("availability") != "observed"
            or quarterly.get("availability") != "observed"): return base
        capture, content_digest = load_report_capture(directory, announcements, now)
        if (quarterly.get("version") != QUARTERLY_VERSION or quarterly.get("catalog_digest") != announcements["content_digest"]
            or quarterly.get("capture_digest") != content_digest): raise ValueError("unbound following reports")
        following = {row["code"]: row for row in quarterly["reports"]}
        if len(following) != len(quarterly["reports"]): raise ValueError("duplicate following report")
        catalogs = {row["code"]: row for row in announcements["catalogs"]}
        if len(catalogs) != len(announcements["catalogs"]): raise ValueError("duplicate report catalog")
    except (OSError, ValueError, KeyError, TypeError): return {**base, "availability": "invalid"}
    reports = []
    for code in NAV_DEFINITIONS:
        candidates = [row for row in catalogs.get(code, {}).get("required_documents", [])
                      if f"{year}年中期报告" in compact(row["title"])]
        previous = {"code": code, "availability": "missing" if not candidates else "invalid"}
        if len(candidates) == 1:
            try:
                previous = read_bound_report(directory, capture, candidates[0], base["period_end"], announcements["through"],
                                             lambda pages: parse_midyear_report(pages, code, year))
            except (OSError, ValueError, TypeError, KeyError, StopIteration): pass
        next_report = following.get(code, {"code": code, "availability": "missing"})
        reports.append({"code": code, "midyear_report": previous, "quarterly_report": next_report,
                        "comparison": compare_adjacent_reports(previous, next_report)})
    compared = [row["comparison"] for row in reports if row["comparison"]["availability"] == "observed"]
    count = sum(row["midyear_report"]["availability"] == "observed" for row in reports)
    return {**base, "availability": "observed" if count == len(NAV_DEFINITIONS) and len(compared) == len(NAV_DEFINITIONS) else "partial",
            "reports": reports, "observed_midyear_reports": count, "compared_etfs": len(compared),
            "matched_etfs": sum(row["total_relation"] == "equal" for row in compared),
            "mismatched_etfs": sum(row["total_relation"] == "different" for row in compared),
            "catalog_digest": announcements["content_digest"], "capture_digest": content_digest,
            "parser_digest": PARSER_DIGEST, "capture_completed_at": capture["completed_at"]}
