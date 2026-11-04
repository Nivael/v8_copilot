"""Primary issuer NAV definitions and integrity-checked local snapshots."""
from __future__ import annotations

from datetime import date, datetime
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from canonical_json import digest
from market_calendar import CALENDAR_VERSION, sessions_2026


NAV_DEFINITIONS = {
    "510300.SH": {"provider": "huatai_pb", "label": "华泰柏瑞", "field": "netvalue",
                  "url": "https://www.huatai-pb.com/products/zhishu/510300/index.html"},
    "510310.SH": {"provider": "efunds", "label": "易方达", "field": "EnumSourceTypeNetValue",
                  "url": "https://www.efunds.com.cn/fund/510310.shtml"},
    "510330.SH": {"provider": "chinaamc", "label": "华夏", "field": "单位净值",
                  "url": "https://www.chinaamc.com/product/fundLishijingzhi.do?fundcode=510330"},
    "159919.SZ": {"provider": "jsfund", "label": "嘉实", "field": "份额净值",
                  "url": "https://www.jsfund.cn/Services/cn/jsp/product/NavHistory.jsp?SiteID=1&FundCode=159919"},
    "510500.SH": {"provider": "nffund", "label": "南方", "field": "fundNav",
                  "url": "https://www.nffund.com/main/nffund/personal-financing/detail.shtml?fundCode=510500"},
    "159922.SZ": {"provider": "jsfund", "label": "嘉实", "field": "份额净值",
                  "url": "https://www.jsfund.cn/Services/cn/jsp/product/NavHistory.jsp?SiteID=1&FundCode=159922"},
    "512100.SH": {"provider": "nffund", "label": "南方", "field": "fundNav",
                  "url": "https://www.nffund.com/main/nffund/personal-financing/detail.shtml?fundCode=512100"},
    "159845.SZ": {"provider": "chinaamc", "label": "华夏", "field": "单位净值",
                  "url": "https://www.chinaamc.com/product/fundLishijingzhi.do?fundcode=159845"},
}
NAV_VERSION = "issuer_etf_nav_raw_v1"


def validate_nav_rows(rows: list[dict], code: str, calendar: list[str]) -> None:
    if code not in NAV_DEFINITIONS or [row["nav_date"] for row in rows] != calendar:
        raise ValueError("NAV window is incomplete, duplicated or out of order")
    for row in rows:
        value = row["unit_nav"]
        if row["ts_code"] != code or isinstance(value, bool) or not math.isfinite(float(value)) or float(value) <= 0:
            raise ValueError("wrong instrument or invalid unit NAV")


def load_issuer_navs(directory: Path, now: datetime) -> tuple[dict, dict[str, list[dict]]]:
    """Read only; a digest is an integrity check, not historical point-in-time proof."""
    try:
        raw = json.loads((directory / "current.json").read_text())
        expected = raw.pop("content_digest")
        if (raw.get("contract_version") != NAV_VERSION or digest(raw) != expected
            or raw.get("nav_unit") != "CNY_per_share" or raw.get("definitions") != NAV_DEFINITIONS
            or raw.get("availability_basis") != "first_observed_at_fetch_not_historical_PIT"
            or raw.get("calendar_version") != CALENDAR_VERSION):
            raise ValueError("invalid issuer NAV definition/digest")
        through = date.fromisoformat(raw["requested_through"])
        fetched = datetime.fromisoformat(raw["fetched_at"])
        calendar = raw["calendar"]
        if (fetched.tzinfo is None or fetched > now or fetched.date() < through
            or through >= now.astimezone(ZoneInfo("Asia/Shanghai")).date()
            or not 21 <= len(calendar) <= 61 or calendar[-1] != through.isoformat()
            or calendar != sessions_2026(date.fromisoformat(calendar[0]), through)
            or set(raw["etf_navs"]) != set(NAV_DEFINITIONS)):
            raise ValueError("invalid issuer NAV dates/scope")
        for code, rows in raw["etf_navs"].items():
            validate_nav_rows(rows, code, calendar)
        return {"availability": "observed", "through": through.isoformat(), "fetched_at": raw["fetched_at"],
                "content_digest": expected, "nav_unit": "CNY_per_share", "calendar": calendar,
                "availability_basis": raw["availability_basis"]}, raw["etf_navs"]
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, OverflowError):
        return {"availability": "missing" if not (directory / "current.json").exists() else "invalid"}, {}
