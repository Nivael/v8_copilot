"""Verified exchange closing cross-sections, separate from historical style indices."""
from __future__ import annotations

from datetime import date, datetime
import json
import math
from pathlib import Path
import re
from statistics import mean, median
import unicodedata
from zoneinfo import ZoneInfo

from canonical_json import digest
from market_calendar import CALENDAR_VERSION, sessions_2026

VERSION = "exchange_breadth_raw_v1"
SSE_SELECT = "code,name,last,prev_close,chg_rate,volume,amount,tradephase,cpxxsubtype,cpxxprodusta"
SOURCES = {
    "SSE": {"label": "上交所股票行情", "url": "https://www.sse.com.cn/market/price/report/",
            "api_url": "https://yunhq.sse.com.cn:32042/v1/sh1/list/exchange/equity",
            "select": SSE_SELECT, "amount_unit": "CNY", "volume_unit": "shares"},
    "SZSE": {"label": "深交所股票收盘报表", "url": "https://www.szse.cn/market/trend/index.html",
             "api_url": "https://fund.szse.cn/api/report/ShowReport/data", "catalog": "1815_stock_snapshot",
             "tabkey": "tab1", "amount_unit": "CNY_10000", "volume_unit": "shares_10000",
             "preferred_share_exclusions": {
                 "140001": {"name": "宁行优01", "url": "https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-04-25/18358089-2830-4737-8f0d-041166aaf36e.PDF"},
                 "140008": {"name": "铁汉优01", "url": "https://static.cninfo.com.cn/finalpage/2020-01-15/1207249430.PDF"}}},
}
SCOPE = "沪深交易所普通A股，含科创板和创业板；不含B股、优先股与北交所。停牌或无成交股票单列，不计作平盘。"


def st_name(name: str) -> bool:
    return bool(re.match(r"^(?:S)?\*?ST", unicodedata.normalize("NFKC", name).strip(), re.I))


def validate_venue(venue: str, block: dict, through: str) -> None:
    if venue not in SOURCES:
        raise ValueError("undeclared exchange")
    rows = block["rows"]
    excluded = block["excluded_b_shares"]
    preferred = block["excluded_preferred_codes"]
    total = block["reported_total"]
    if (not rows or isinstance(total, bool) or not isinstance(total, int) or not 0 < total < 10_000
        or isinstance(excluded, bool) or not isinstance(excluded, int) or excluded < 0
        or not isinstance(preferred, list) or len(preferred) != len(set(preferred))
        or not set(preferred) <= set(SOURCES[venue].get("preferred_share_exclusions", {}))
        or len(rows) + excluded + len(preferred) != total or block["received_total"] != total
        or block["amount_unit"] != "CNY" or block["volume_unit"] != "shares"):
        raise ValueError("incomplete exchange scope or wrong normalized units")
    if venue == "SSE":
        quote_time = block["quote_time"]
        if isinstance(quote_time, bool) or not isinstance(quote_time, int) or quote_time < 150000:
            raise ValueError("SSE snapshot is not after the close")
        datetime.strptime(str(quote_time).zfill(6), "%H%M%S")
    codes = set()
    for row in rows:
        code = row["ts_code"]
        expected = r"(?:60|68)\d{4}\.SH" if venue == "SSE" else r"[03]\d{5}\.SZ"
        if (not re.fullmatch(expected, code) or code in codes or row["trade_date"] != through
            or not isinstance(row["security_name"], str) or not row["security_name"].strip()
            or not isinstance(row["is_trading"], bool)):
            raise ValueError("wrong, duplicate or undated security")
        codes.add(code)
        for key in ("volume", "amount"):
            value = row[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError("invalid volume/amount")
        for key in ("last", "prev_close"):
            value = row[key]
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
                raise ValueError("invalid reference price")
        if row["is_trading"]:
            for key in ("last", "prev_close", "pct_chg", "reported_pct_chg"):
                value = row[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError("invalid trading quote")
            if min(row["last"], row["prev_close"], row["volume"], row["amount"]) <= 0:
                raise ValueError("trading row lacks a valid price or turnover")
            calculated = (row["last"] / row["prev_close"] - 1) * 100
            if abs(calculated - row["pct_chg"]) > 1e-8 or abs(calculated - row["reported_pct_chg"]) > .015:
                raise ValueError("return disagrees with official previous-close reference")
        elif row["pct_chg"] is not None or row["volume"] != 0 or row["amount"] != 0:
            raise ValueError("inactive stock must not become a flat return")


def cross_section(rows: list[dict]) -> dict:
    active = [row for row in rows if row["is_trading"]]
    values = [row["pct_chg"] for row in active]
    return {"observed_trading_stocks": len(active), "listed_source_stocks": len(rows),
            "nontrading_stocks": len(rows) - len(active),
            "advancing": sum(value > 0 for value in values), "declining": sum(value < 0 for value in values),
            "flat": sum(value == 0 for value in values), "declining_5pct_or_more": sum(value <= -5 for value in values),
            "median_return_pct": round(median(values), 6) if values else None,
            "mean_return_pct": round(mean(values), 6) if values else None,
            "declining_share_pct": round(sum(value < 0 for value in values) / len(values) * 100, 6) if values else None,
            "amount_yuan": round(sum(row["amount"] for row in active), 2) if values else None}


def load_public_breadth(directory: Path, now: datetime) -> tuple[dict, dict]:
    try:
        raw = json.loads((directory / "current.json").read_text())
        expected = raw.pop("content_digest")
        if (raw["contract_version"] != VERSION or digest(raw) != expected or raw["sources"] != SOURCES
            or raw["scope"] != "SSE_SZSE_A_shares" or raw["calendar_version"] != CALENDAR_VERSION
            or raw["availability_basis"] != "first_observed_at_fetch_not_historical_PIT"):
            raise ValueError("invalid breadth definition/digest")
        through = date.fromisoformat(raw["requested_through"])
        fetched = datetime.fromisoformat(raw["fetched_at"])
        if (fetched.tzinfo is None or fetched > now or fetched.date() < through
            or through >= now.astimezone(ZoneInfo("Asia/Shanghai")).date()
            or sessions_2026(through, through) != [through.isoformat()] or set(raw["venues"]) != set(SOURCES)):
            raise ValueError("invalid breadth dates/venues")
        rows, venues = [], []
        for venue, block in raw["venues"].items():
            validate_venue(venue, block, through.isoformat())
            rows.extend(block["rows"])
            venues.append({"venue": venue, "label": SOURCES[venue]["label"], "url": SOURCES[venue]["url"],
                           "source_rows": block["reported_total"], "excluded_b_shares": block["excluded_b_shares"],
                           "excluded_preferred_shares": len(block["excluded_preferred_codes"]),
                           "through": through.isoformat(), **cross_section(block["rows"])})
        result = {"status": "observed", "source": "exchange_public", "through": through.isoformat(),
                  "scope": SCOPE, "historical_path_available": False, "venues": venues,
                  "return_basis": "当日收盘价/官方前收参考价−1；保留源端已取整涨跌幅作交叉校验，不用四舍五入值划分平盘或5%跌幅边界。",
                  "source_rows": sum(block["reported_total"] for block in raw["venues"].values()), **cross_section(rows),
                  "st_name_group": {"definition": "当日证券简称以ST、*ST、SST或S*ST开头的沪深A股；仅为当日名称分组，不重建历史成员。",
                                    **cross_section([row for row in rows if st_name(row["security_name"])])}}
        if not result["observed_trading_stocks"]:
            raise ValueError("no valid trading observations")
        return {"availability": "observed", "through": through.isoformat(), "fetched_at": raw["fetched_at"],
                "content_digest": expected, "scope": raw["scope"], "availability_basis": raw["availability_basis"]}, result
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, OverflowError):
        return {"availability": "missing" if not (directory / "current.json").exists() else "invalid"}, {"status": "missing"}
