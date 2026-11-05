"""Market context parameters, separate from company events and uncalibrated signals."""
from __future__ import annotations

import json
import math
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from canonical_json import digest
from etf_issuer_nav import NAV_DEFINITIONS, load_issuer_navs
from etf_announcements import announcement_status
from etf_quarterly import quarterly_status
from etf_report_continuity import report_continuity_status
from etf_notice_review import notice_review_status
from etf_prospectus_rules import prospectus_rule_status
from etf_review_scope import scope_status as etf_scope_status
from etf_szse_history import SOURCE_URL as SZSE_ETF_SOURCE, API_URL as SZSE_ETF_API, HTTP_API_URL as SZSE_HTTP_API
from etf_szse_recheck import recheck_status
from etf_issuer_history import history_status
from node_market_audit import audit_status as node_market_audit_status
from exchange_risk_membership import list_status as risk_membership_status
from szse_st_reference import reference_status as szse_st_reference_status
from sse_history_archive import archive_status as sse_history_archive_status
from sse_gap_review import review_status as sse_gap_review_status
from market_breadth_combined import history_status as combined_breadth_status
from combined_st_reference import reference_status as st_reconstruction_status
from sse_st_notice_review import review_status as sse_st_notice_status
from etf_share_events import share_event_status
from market_breadth import SOURCES as BREADTH_SOURCES, load_public_breadth
from market_breadth_history import load_breadth_history
from market_calendar import CALENDAR_VERSION, sessions_2026
from market_periods import price_period_summary, recent_calendar_window
from settings import DATA_ROOT, MARKET_CONTEXT_DB, MARKET_CONTEXT_MANIFEST_PATH


PARAMETER_VERSION = "market_risk_parameters_v5"
MARKET_RISK_DIR = DATA_ROOT / "local_data/v8_copilot/market_risk"
ETF_BASKET = {
    "510300.SH": "沪深300", "510310.SH": "沪深300", "510330.SH": "沪深300", "159919.SZ": "沪深300",
    "510500.SH": "中证500", "159922.SZ": "中证500", "512100.SH": "中证1000", "159845.SZ": "中证1000",
}
INDEX_BASKET = {"000985.CSI": "中证全指", "000300.SH": "沪深300", "932000.CSI": "中证2000"}
HORIZONS = (5, 20, 60)
ETF_SHARE_SOURCE = "https://www.sse.com.cn/market/funddata/volumn/etfvolumn/"
ETF_SHARE_SQL = "COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L"
CSI_PERF_URL = "https://www.csindex.com.cn/csindex-home/perf/index-perf"
CSI_SOURCE_URL = "https://www.csindex.com.cn/#/indices/family/detail?indexCode=000985"


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def _date(value: str) -> str:
    text = str(value)
    return date.fromisoformat(f"{text[:4]}-{text[4:6]}-{text[6:8]}" if len(text) == 8 else text).isoformat()


def index_metrics(rows: list[dict[str, Any]], calendar: list[str]) -> dict[str, Any]:
    points = {_date(row["trade_date"]): row for row in rows}
    if len(points) != len(rows):
        raise ValueError("duplicate index dates")
    # Calendar supplies the evaluation end date. Missing tail data cannot move it backwards.
    days = sorted(set(calendar))
    end = days[-1] if days else None
    results: dict[str, Any] = {}
    for horizon in HORIZONS:
        window = days[-horizon - 1:]
        closes = [_number(points.get(day, {}).get("close")) for day in window]
        valid = len(window) == horizon + 1 and all(value is not None and value > 0 for value in closes)
        summary = price_period_summary(closes) if valid else price_period_summary([])
        results[f"return_{horizon}d_pct"] = summary["return_pct"]
        if horizon == 60:
            results["max_drawdown_60d_pct"] = summary["max_drawdown_pct"]
            results["from_60d_peak_pct"] = summary["from_peak_pct"]
    amounts = [_number(points.get(day, {}).get("amount")) for day in days[-20:]]
    valid_amount = len(amounts) == 20 and all(value is not None and value >= 0 for value in amounts) and sum(amounts) > 0
    results["amount_5d_to_20d_ratio"] = round((sum(amounts[-5:]) / 5) / (sum(amounts) / 20), 6) if valid_amount else None
    observed_days = [day for day in days if _number(points.get(day, {}).get("close")) is not None]
    recent = recent_calendar_window(end)
    recent_metrics = None
    if recent["availability"] == "defined":
        recent_metrics = {"start": recent["start"], "end": recent["end"], "sessions": recent["sessions"],
                          **price_period_summary([_number(points.get(day, {}).get("close")) for day in recent["calendar"]])}
    return {"through": observed_days[-1] if observed_days else None,
            "evaluation_through": end, "observation_count": len(observed_days), "recent": recent_metrics, **results,
            "path": [{"date": day, "close": _number(points[day].get("close"))} for day in days if day in points]}


def etf_metrics(
    shares: list[dict[str, Any]], navs: list[dict[str, Any]], calendar: list[str],
    *, corporate_actions_checked: bool = False,
) -> dict[str, Any]:
    share_by_day = {_date(row["trade_date"]): _number(row.get("fd_share")) for row in shares}
    nav_by_day = {_date(row["nav_date"]): _number(row.get("unit_nav")) for row in navs}
    if len(share_by_day) != len(shares) or len(nav_by_day) != len(navs):
        raise ValueError("duplicate ETF dates")
    days = sorted(set(calendar))
    share_days = [day for day in days if share_by_day.get(day) is not None]
    nav_days = [day for day in days if nav_by_day.get(day) is not None]
    output = {"through": share_days[-1] if share_days else None,
              "nav_through": nav_days[-1] if nav_days else None,
              "share_observation_count": len(share_days), "nav_observation_count": len(nav_days),
              "evaluation_through": days[-1] if days else None,
              "corporate_actions_checked": corporate_actions_checked, "windows": {},
              "nav_path": [{"nav_date": day, "unit_nav": nav_by_day[day]} for day in nav_days],
              "path": [{"date": day, "shares": share_by_day.get(day)} for day in days]}
    recent = recent_calendar_window(days[-1] if days else None)
    windows = [(str(horizon), days[-horizon - 1:], horizon) for horizon in (1, 5, 20)]
    windows.append(("recent", recent.get("calendar", []), recent.get("sessions", 0)))
    for key, window, horizon in windows:
        unit_counts = [share_by_day.get(day) for day in window]
        values = [nav_by_day.get(day) for day in window[1:]]
        share_ready = len(window) == horizon + 1 and all(value is not None and value > 0 for value in unit_counts)
        nav_ready = share_ready and all(value is not None and value > 0 for value in values)
        # fd_share is ten-thousand shares. Price changes/AUM changes are never called flows.
        notional = sum((unit_counts[i] - unit_counts[i - 1]) * 10_000 * values[i - 1]
                       for i in range(1, len(window))) if nav_ready else None
        output["windows"][key] = {
            "window_sessions": horizon if window else None,
            "window_start": window[0] if len(window) == horizon + 1 else None,
            "window_end": days[-1] if days else None,
            "share_change_ten_thousand": round(unit_counts[-1] - unit_counts[0], 6) if share_ready else None,
            "share_change_pct": round((unit_counts[-1] / unit_counts[0] - 1) * 100, 6) if share_ready else None,
            "share_change_notional_yuan": round(notional, 2) if notional is not None else None,
            "estimated_net_subscription_yuan": round(notional, 2) if notional is not None and corporate_actions_checked else None,
            "status": "missing" if not share_ready else "shares_only" if not nav_ready else "estimated" if corporate_actions_checked else "corporate_actions_unchecked",
        }
    return output


def _with_issuer_navs(etfs: list[dict], navs: dict[str, list[dict]], meta: dict) -> list[dict]:
    """Keep share dates/source intact; conflicting or older NAVs cannot overwrite them."""
    output = []
    for row in etfs:
        incoming = navs.get(row["code"], [])
        if not incoming or meta.get("through") != row["evaluation_through"]:
            output.append(row)
            continue
        calendar = [point["date"] for point in row["path"]]
        candidates = [point for point in incoming if point["nav_date"] in calendar]
        by_day = {point["nav_date"]: point["unit_nav"] for point in candidates}
        existing = row.get("nav_path", [])
        overlap = [point for point in existing if point["nav_date"] in by_day]
        conflicts = [point["nav_date"] for point in overlap
                     if abs(point["unit_nav"] - by_day[point["nav_date"]]) > 0.00005]
        if conflicts:
            output.append({**row, "nav_conflict_dates": conflicts})
            continue
        if len(candidates) < row["nav_observation_count"]:
            output.append(row)
            continue
        definition = NAV_DEFINITIONS[row["code"]]
        metrics = etf_metrics([{"trade_date": point["date"], "fd_share": point["shares"]} for point in row["path"]],
                              candidates, calendar)
        output.append({**row, **metrics, "nav_source": definition["label"], "nav_source_url": definition["url"],
                       "nav_unit": "CNY_per_share", "nav_crosscheck_observations": len(overlap), "nav_conflict_dates": []})
    return output


def _public_etfs(directory: Path, now: datetime) -> tuple[dict, list[dict]]:
    try:
        raw = json.loads((directory / "current.json").read_text())
        expected = raw.pop("content_digest")
        if (raw.get("contract_version") != "public_etf_shares_raw_v1" or digest(raw) != expected
            or raw.get("provider") != "sse_public" or raw.get("share_unit") != "ten_thousand_shares"
            or raw.get("source_url") != ETF_SHARE_SOURCE or raw.get("source_sql") != ETF_SHARE_SQL
            or raw.get("calendar_version") != CALENDAR_VERSION):
            raise ValueError("invalid public ETF snapshot")
        calendar = raw["calendar"]
        through = date.fromisoformat(raw["requested_through"])
        fetched = datetime.fromisoformat(raw["fetched_at"])
        today = now.astimezone(ZoneInfo("Asia/Shanghai")).date()
        if (fetched.tzinfo is None or fetched > now or fetched.date() < through or through >= today
            or not 21 <= len(calendar) <= 61 or calendar[-1] != through.isoformat()
            or calendar != sessions_2026(date.fromisoformat(calendar[0]), through)):
            raise ValueError("invalid public ETF calendar/date")
        declared = {code for code in ETF_BASKET if code.endswith(".SH")}
        if set(raw["declared_codes"]) != declared or set(raw["etf_shares"]) != declared:
            raise ValueError("unexpected public ETF scope")
        etfs = []
        for code in sorted(declared):
            rows = raw["etf_shares"][code]
            if any(row.get("ts_code") != code or row.get("trade_date") not in calendar
                   or (_number(row.get("fd_share")) or 0) <= 0 for row in rows):
                raise ValueError("invalid public ETF observations")
            etfs.append({"code": code, "group": ETF_BASKET[code], "source": "sse_public",
                         "source_url": ETF_SHARE_SOURCE, **etf_metrics(rows, [], calendar)})
        if not any(row["through"] == through.isoformat() for row in etfs):
            raise ValueError("public ETF target missing")
        return {"availability": "observed", "through": through.isoformat(), "fetched_at": raw["fetched_at"],
                "content_digest": expected, "provider": "sse_public", "scope": "five_declared_SSE_ETFs",
                "calendar_version": CALENDAR_VERSION, "gap_count": len(raw["gaps"]),
                "availability_basis": raw["availability_basis"]}, etfs
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
        return {"availability": "missing" if not (directory / "current.json").exists() else "invalid"}, []


def _public_indices(directory: Path, now: datetime) -> tuple[dict, list[dict]]:
    try:
        raw = json.loads((directory / "current.json").read_text())
        expected = raw.pop("content_digest")
        if (raw.get("contract_version") != "public_market_indices_raw_v1" or digest(raw) != expected
            or raw.get("provider") != "csindex_official" or raw.get("amount_unit") != "CNY"
            or raw.get("api_url") != CSI_PERF_URL or raw.get("source_url") != CSI_SOURCE_URL
            or raw.get("scope") != "three_price_indices_only" or raw.get("calendar_version") != CALENDAR_VERSION):
            raise ValueError("invalid public index snapshot")
        calendar = raw["calendar"]
        through = date.fromisoformat(raw["requested_through"])
        fetched = datetime.fromisoformat(raw["fetched_at"])
        if (fetched.tzinfo is None or fetched > now or fetched.date() < through
            or through >= now.astimezone(ZoneInfo("Asia/Shanghai")).date()
            or len(calendar) != 61 or calendar[-1] != through.isoformat()
            or calendar != sessions_2026(date.fromisoformat(calendar[0]), through)
            or set(raw["indices"]) != set(INDEX_BASKET)):
            raise ValueError("invalid public index calendar/scope")
        indices = []
        for code, name in INDEX_BASKET.items():
            rows = raw["indices"][code]
            if any(row.get("ts_code") != code or row.get("trade_date") not in calendar
                or (_number(row.get("close")) or 0) <= 0
                or row.get("amount") is not None and (_number(row["amount"]) is None or _number(row["amount"]) < 0) for row in rows):
                raise ValueError("invalid public index observations")
            indices.append({"code": code, "name": name, "source": "csindex_official", "source_url": CSI_SOURCE_URL.replace("000985", code[:6]),
                            "historical_only": False, **index_metrics(rows, calendar)})
        if indices[0]["through"] != through.isoformat():
            raise ValueError("broad market target missing")
        return {"availability": "observed", "through": through.isoformat(), "scope": raw["scope"],
                "fetched_at": raw["fetched_at"], "content_digest": expected,
                "gap_count": len(raw["gaps"]), "availability_basis": raw["availability_basis"]}, indices
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
        return {"availability": "missing" if not (directory / "current.json").exists() else "invalid"}, []


def _szse_etfs(directory: Path, now: datetime) -> tuple[dict, list[dict]]:
    try:
        raw = json.loads((directory / "current.json").read_text())
        expected = raw.pop("content_digest")
        if (raw.get("contract_version") != "szse_etf_history_raw_v1" or digest(raw) != expected
            or raw.get("provider") != "szse_public" or raw.get("share_unit") != "ten_thousand_shares"
            or raw.get("nav_unit") != "CNY_per_share" or raw.get("api_url") not in (SZSE_ETF_API, SZSE_HTTP_API)
            or raw.get("source_url") != SZSE_ETF_SOURCE or raw.get("calendar_version") != CALENDAR_VERSION
            or raw.get("share_revision_status") != "final_revision_unverified"):
            raise ValueError("invalid SZSE snapshot")
        calendar = raw["calendar"]
        through = date.fromisoformat(raw["requested_through"])
        fetched = datetime.fromisoformat(raw["fetched_at"])
        if (fetched.tzinfo is None or fetched > now or fetched.date() < through
            or through >= now.astimezone(ZoneInfo("Asia/Shanghai")).date()
            or not 21 <= len(calendar) <= 61 or calendar[-1] != through.isoformat()
            or calendar != sessions_2026(date.fromisoformat(calendar[0]), through)):
            raise ValueError("invalid SZSE calendar/date")
        codes = {code for code in ETF_BASKET if code.endswith(".SZ")}
        if set(raw["etf_shares"]) != codes or set(raw["etf_navs"]) != codes:
            raise ValueError("unexpected SZSE scope")
        etfs = []
        for code in sorted(codes):
            for key, day_key, value_key in (("etf_shares", "trade_date", "fd_share"), ("etf_navs", "nav_date", "unit_nav")):
                if any(row.get("ts_code") != code or row.get(day_key) not in calendar
                       or (_number(row.get(value_key)) or 0) <= 0 for row in raw[key][code]):
                    raise ValueError("invalid SZSE ETF observations")
            etfs.append({"code": code, "group": ETF_BASKET[code], "source": "szse_public",
                         "source_url": SZSE_ETF_SOURCE, "share_revision_unverified": True,
                         **etf_metrics(raw["etf_shares"][code], raw["etf_navs"][code], calendar)})
        if not any(row["through"] == through.isoformat() for row in etfs):
            raise ValueError("SZSE target missing")
        return {"availability": "observed", "through": through.isoformat(), "fetched_at": raw["fetched_at"],
                "content_digest": expected, "gap_count": len(raw["gaps"]),
                "revision_note": raw["revision_note"], "share_revision_status": raw["share_revision_status"]}, etfs
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
        return {"availability": "missing" if not (directory / "current.json").exists() else "invalid"}, []


def breadth_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    # One cross-section, one observation per security. A provider-limit-sized response is not trusted.
    days = {_date(row["trade_date"]) for row in rows}
    codes = [row["ts_code"] for row in rows]
    if len(days) != 1 or len(codes) != len(set(codes)) or len(rows) >= 6000:
        return {"status": "invalid", "reason": "日期不唯一、代码重复或可能达到源端行数上限"}
    returns = sorted(value for row in rows if (value := _number(row.get("pct_chg"))) is not None)
    if not returns:
        return {"status": "missing"}
    size = len(returns)
    middle = size // 2
    amounts = [_number(row.get("amount")) for row in rows]
    return {"status": "observed", "through": next(iter(days)), "observed_trading_stocks": size,
            "source_rows": len(rows),
            "advancing": sum(value > 0 for value in returns), "declining": sum(value < 0 for value in returns),
            "flat": sum(value == 0 for value in returns),
            "declining_5pct_or_more": sum(value <= -5 for value in returns),
            "median_return_pct": returns[middle] if size % 2 else (returns[middle - 1] + returns[middle]) / 2,
            "amount_yuan": sum(amounts) * 1000 if all(value is not None and value >= 0 for value in amounts) else None,
            "scope": "源端返回的当日有成交股票；停牌不填零，尚不宣称全市场覆盖"}


def breadth_history_status(directory: Path, now: datetime) -> dict:
    history = load_breadth_history(directory, now)
    attempt = None
    try:
        raw = json.loads((directory / "last_attempt.json").read_text())
        stamp = datetime.fromisoformat(raw["recorded_at"])
        start = datetime.fromisoformat(raw["started_at"])
        window = recent_calendar_window(raw["requested_through"])
        if (raw["status"] in ("collecting", "failed", "complete") and window["availability"] == "defined"
            and raw["requested_through"] < now.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
            and raw["scope"] == "SZSE_A_shares_daily_reports" and raw["start"] == window["start"]
            and raw["expected_days"] == window["points"] and type(raw["completed_days"]) is int
            and 0 <= raw["completed_days"] <= raw["expected_days"] and start.tzinfo is not None
            and (raw["status"] != "complete" or raw["completed_days"] == raw["expected_days"])
            and stamp.tzinfo is not None and start <= stamp <= now):
            attempt = {key: raw[key] for key in ("status", "recorded_at", "start", "requested_through", "completed_days", "expected_days")}
    except (OSError, ValueError, KeyError, TypeError): pass
    return {**history, "last_recorded_attempt": attempt}


def market_update_status(*, snapshot_dir: Path = MARKET_RISK_DIR, now: datetime | None = None) -> list[dict]:
    """The learning page observes verified files; it never invokes a collector."""
    now = now or datetime.now(timezone.utc)
    index_meta, indices = _public_indices(snapshot_dir / "public_indices", now)
    sse_meta, sse = _public_etfs(snapshot_dir / "public_etf", now)
    szse_meta, szse = _szse_etfs(snapshot_dir / "public_etf_szse", now)
    issuer_meta, issuer_navs = load_issuer_navs(snapshot_dir / "issuer_nav", now)
    breadth_meta, breadth = load_public_breadth(snapshot_dir / "public_breadth", now)
    history = breadth_history_status(snapshot_dir / "public_breadth_history", now)
    combined = combined_breadth_status(snapshot_dir / 'combined_breadth_history', root=snapshot_dir, now=now)
    announcements = announcement_status(snapshot_dir / "etf_announcements", now)
    event_review = share_event_status(snapshot_dir / "etf_announcements", announcements, now)
    etf_scopes = etf_scope_status(snapshot_dir / 'etf_review_scope', root=snapshot_dir, now=now)
    membership = risk_membership_status(snapshot_dir / "exchange_risk_membership", now=now)
    st_reference = szse_st_reference_status(snapshot_dir / 'szse_st_reference', root=snapshot_dir, now=now)
    st_reconstruction = st_reconstruction_status(snapshot_dir / 'st_reconstruction', root=snapshot_dir, now=now)
    sse_notices = sse_st_notice_status(snapshot_dir / 'sse_st_notice_review', now=now)
    sse_archive = sse_history_archive_status(snapshot_dir / 'sse_history_archive', endpoint_dir=snapshot_dir/'public_breadth', now=now)
    gaps = sse_gap_review_status(snapshot_dir / 'sse_gap_review', root=snapshot_dir, now=now)
    issuer_rows = [{"nav_through": rows[-1]["nav_date"], "nav_observation_count": len(rows)} for rows in issuer_navs.values()]
    definitions = [
        ("official_indices", "中证指数 · 市场基准", index_meta, indices, "through", "observation_count", 3, CSI_SOURCE_URL,
         "指数可用不代表同期ST风格和市场宽度已覆盖。"),
        ("sse_etf_shares", "上交所 · ETF份额", sse_meta, sse, "through", "share_observation_count", 5, ETF_SHARE_SOURCE,
         "份额折算等事件未核验，不作为已确认净申赎金额。"),
        ("szse_etf_shares", "深交所 · ETF份额", szse_meta, szse, "through", "share_observation_count", 3, SZSE_ETF_SOURCE,
         "最新份额的次日修订状态待核对。"),
        ("szse_etf_nav", "深交所 · ETF净值", szse_meta, szse, "nav_through", "nav_observation_count", 3, SZSE_ETF_SOURCE,
         "只显示实际取得的净值，不以前值补齐未披露日期。"),
        ("issuer_etf_nav", "5家基金公司 · ETF单位净值", issuer_meta, issuer_rows, "nav_through", "nav_observation_count", 8,
         "/market", "各基金原始链接见大盘页；首次取得日期不冒充历史当时可见，净值齐全不代表份额事件已核验。"),
        ("exchange_breadth", "沪深交易所 · A股收盘横截面", breadth_meta, breadth.get("venues", []), "through", "listed_source_stocks", 2,
         "/market", "两所A股范围分别核对；不含北交所，停牌及无成交单列；此项是单日截面，历史窗口另作独立核对。"),
    ]
    sources = []
    for key, label, meta, rows, through_key, count_key, size, url, note in definitions:
        observed = meta["availability"] == "observed"
        actual = [row[through_key] for row in rows if row.get(through_key)]
        sources.append({"source_id": key, "label": label, "availability": meta["availability"],
                        "requested_through": meta.get("through"), "fetched_at": meta.get("fetched_at"),
                        "observed_through_min": min(actual) if actual else None,
                        "observed_through_max": max(actual) if actual else None,
                        "observation_count": sum(row[count_key] for row in rows) if observed else None,
                        "series_at_target": sum(row.get(through_key) == meta.get("through") for row in rows) if observed else None,
                        "declared_series": size, "snapshot_digest": meta.get("content_digest"), "url": url, "note": note})
    sources.append({"source_id": "exchange_breadth_history", "label": "深交所 · 历史收盘日表", "availability": history["availability"],
                    "requested_through": history.get("through"), "fetched_at": history.get("fetched_at"),
                    "observed_through_min": history.get("start"), "observed_through_max": history.get("through"),
                    "observation_count": history.get("observation_count"), "series_at_target": len(history["covered_venues"]),
                    "observation_unit": "股票日", "coverage_unit": "交易所",
                    "declared_series": 2, "snapshot_digest": history.get("content_digest"), "url": "/market",
                    "note": "此行仅深市原日表，逐日股票观测合计不代表不同股票数；沪深合并历史核对另列。"})
    sources.append({'source_id':'combined_breadth_history','label':'沪深交易所 · 完整历史涨跌分布','availability':combined['availability'],
                    'requested_through':combined.get('through'),'fetched_at':combined.get('fetched_at'),
                    'observed_through_min':combined.get('start'),'observed_through_max':combined.get('through'),
                    'observation_count':combined.get('observation_count'),'observation_unit':'股票日','coverage_unit':'交易所',
                    'series_at_target':len(combined['covered_venues']),'declared_series':2,'snapshot_digest':combined.get('content_digest'),
                    'url':'/market','note':'两所同窗挂牌范围、价格及沪市全部缺日停牌依据分别核对；家数合并，不平均两所百分比。不推进历史ST成员、旧个股清单或风险效果。'})
    sources.append({"source_id": "etf_announcements", "label": "ETF公告目录 · 待事件核验", "availability": announcements["availability"],
                    "requested_through": announcements.get("through"), "fetched_at": announcements.get("fetched_at"),
                    "observed_through_min": announcements.get("through"), "observed_through_max": announcements.get("through"),
                    "observation_count": announcements["record_count"], "series_at_target": announcements["catalog_etfs"],
                    "declared_series": announcements["declared_etfs"], "snapshot_digest": announcements.get("content_digest"),
                    "url": "/market", "date_basis": "catalog_search_cutoff",
                    "note": "日期为采集时点的公告检索上界；最近公告日逐基金列出。目录取得不代表份额事件已核验。"
                            + (f"已逐条核对{event_review['reviewed_events']}条历史事项，涉及{event_review['reconciled_documents']}份材料；其余{event_review['pending_documents']}份不在本事项链核对范围，其他指定范围另列。" if event_review['availability']=='partial' else "")})
    sources.append({'source_id':'etf_document_scope','label':'ETF文档 · 指定范围核对','availability':etf_scopes['availability'],
                    'requested_through':etf_scopes.get('window_end'),'fetched_at':etf_scopes.get('capture_completed_at'),
                    'observed_through_min':etf_scopes.get('publication_cutoff'),'observed_through_max':etf_scopes.get('publication_cutoff'),
                    'observation_count':etf_scopes.get('selected_document_items'),'observation_unit':'基金文档项',
                    'series_at_target':None,'observed_source_groups':etf_scopes.get('items_with_scoped_review'),'declared_series':etf_scopes.get('selected_document_items'),
                    'snapshot_digest':etf_scopes.get('content_digest'),'url':'/market','coverage_basis':'ETF_scoped_review','date_basis':'catalog_search_cutoff',
                    'note':'每项仅有已列范围的原文依据；不代表全部正文或全窗份额事件已验收。日份额范围、精度及最新修订仍待核，净申赎金额继续未发布。'})
    observed = membership['availability']=='observed'
    sources.append({'source_id':'exchange_risk_membership','label':'交易所 · 风险警示与退市整理名单','availability':membership['availability'],
                    'requested_through':None,'fetched_at':membership.get('completed_at'),'observed_through_min':None,'observed_through_max':None,
                    'observation_date':membership.get('observed_on'),'observation_count':len(membership['rows']) if observed else None,
                    'series_at_target':None,'observed_source_groups':len(membership['groups']) if observed else None,'declared_series':6,
                    'snapshot_digest':membership.get('content_digest'),'url':'/market','date_basis':'current_list_observation',
                    'note':'此日期为名单读取日，非统一数据截止日；深市表声明数据日，沪市未声明。表内记录含另列B股与退市整理股票，不推进个股或历史成员日期。'})
    sources.append({'source_id':'szse_st_price_reference','label':'深市ST · 有成交样本价格参考','availability':st_reference['availability'],
                    'requested_through':st_reference.get('through'),'fetched_at':st_reference.get('source_fetched_at'),
                    'observed_through_min':st_reference.get('start'),'observed_through_max':st_reference.get('through'),
                    'observation_count':st_reference.get('member_day_observations'),
                    'observation_unit':'成员日','coverage_unit':'交易所',
                    'series_at_target':1 if st_reference['availability']=='observed' else 0,'declared_series':2,
                    'snapshot_digest':st_reference.get('content_digest'),'url':'/market',
                    'note':'记录数为每日成员合计，包含停牌分母；不同成员数与每日成交覆盖见市场页。独立逐日核验仅深市，沪市仍缺此项核验；回溯核对不代表历史当时可见或组合财富。'})
    reconstructed = st_reconstruction['availability']=='reconstructed'
    sources.append({'source_id':'combined_ST_reconstruction','label':'沪深ST · 成员重建价格参考','availability':st_reconstruction['availability'],
                    'requested_through':st_reconstruction.get('through'),'fetched_at':st_reconstruction.get('newest_notice_observed_at'),
                    'observed_through_min':st_reconstruction.get('start'),'observed_through_max':st_reconstruction.get('through'),
                    'observation_count':st_reconstruction.get('metrics',{}).get('all',{}).get('member_day_observations'),
                    'observation_unit':'成员日（重建）','series_at_target':None,'observed_source_groups':2 if reconstructed else None,
                    'verified_membership_venues':1 if reconstructed else None,'declared_series':2,
                    'snapshot_digest':st_reconstruction.get('content_digest'),'url':'/market','coverage_basis':'ST_reconstruction',
                    'note':'价格来源覆盖两所；沪市日期锚点加3处生效公告重建成员，尚缺完整逐日名单/简称的独立核验。此项不提升ST完整核验或风险效果门槛。'})
    sources.append({'source_id':'sse_ST_notice_clauses','label':'沪市ST · 公告身份与成员状态条款','availability':sse_notices['availability'],
                    'requested_through':sse_notices.get('through'),'fetched_at':sse_notices.get('metadata_observed_at'),
                    'observed_through_min':sse_notices.get('through'),'observed_through_max':sse_notices.get('through'),
                    'observation_count':sse_notices.get('reviewed_items'),'observation_unit':'目录项',
                    'series_at_target':None,'observed_source_groups':sse_notices.get('reviewed_items'),'declared_series':sse_notices.get('catalog_items'),
                    'snapshot_digest':sse_notices.get('content_digest'),'url':'/market','coverage_basis':'ST_notice_clause_review','date_basis':'catalog_search_cutoff',
                    'note':'核对固定目录内的原PDF身份及成员状态条款；不代表全文语义、所有公司公告完整或逐日ST名单已核验，不推进旧个股清单日期。'})
    sources.append({'source_id':'sse_historical_price_archive','label':'上交所 · 历史价格来源核对','availability':sse_archive['availability'],
                    'requested_through':sse_archive.get('through'),'fetched_at':sse_archive.get('source_fetched_at'),
                    'observed_through_min':sse_archive.get('start'),'observed_through_max':sse_archive.get('through'),
                    'observation_count':sse_archive.get('observed_trading_days'),'observation_unit':'有成交股票日',
                    'series_at_target':None,'observed_source_groups':sse_archive.get('price_responses'),
                    'declared_series':sse_archive.get('distinct_securities'),'snapshot_digest':sse_archive.get('content_digest'),
                    'url':'/market','coverage_basis':'price_archives','date_basis':'historical_price_archive',
                    'note':'计数是有成交价格记录；原件覆盖按证券归档，不是每只股票在目标日都应有成交。缺日另以停复牌登记核对，本项不单独推进历史分布、ST覆盖或旧个股清单。'})
    sources.append({'source_id':'sse_missing_day_review','label':'沪市历史缺日 · 停复牌公告核对','availability':gaps['availability'],
                    'requested_through':gaps.get('through'),'fetched_at':gaps.get('source_fetched_at'),
                    'observed_through_min':gaps.get('start'),'observed_through_max':gaps.get('through'),
                    'observation_count':gaps.get('confirmed_missing_days'),'observation_unit':'已解释的缺失股票日',
                    'series_at_target':None,'observed_source_groups':gaps.get('closed_episodes'),
                    'declared_series':gaps.get('reviewed_episodes'),'snapshot_digest':gaps.get('content_digest'),
                    'url':'/market','coverage_basis':'missing_day_episodes','date_basis':'historical_notice_review',
                    'note':'完整停复牌区间与持续停牌至实际终止上市的区间分别核对；起点及期末状态不推断中间区间，不填零或提升整体历史覆盖。'})
    return sources


def _historical_indices(database: Path, manifest_path: Path) -> list[dict[str, Any]]:
    if not database.is_file() or not manifest_path.is_file():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    through = manifest["pool_common_window"]["end"]
    names = {"csi_all_share": "中证全指", "csi_2000": "中证2000", "st_equal_weight_v1": "ST等权研究指数"}
    output = []
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        # Broad-market dates supply a shared window. ST missing dates/low coverage remain gaps.
        calendar = [str(row[0]) for row in connection.execute(
            "select trade_date from benchmark_daily where benchmark_id='csi_all_share' and trade_date<=? order by trade_date desc limit 121", (through,),
        )][::-1]
        for key, name in names.items():
            rows = [dict(row) for row in connection.execute(
                "select trade_date,close,coverage_ratio from benchmark_daily where benchmark_id=? and trade_date<=? order by trade_date desc limit 121", (key, through),
            ) if key != "st_equal_weight_v1" or row["coverage_ratio"] is not None and row["coverage_ratio"] >= .95]
            output.append({"code": key, "name": name, "source_ref": f"{database.name}::benchmark_daily::{key}",
                           "manifest_id": manifest["manifest_id"], "historical_only": True, **index_metrics(rows, calendar)})
    return output


def build_market_risk_status(
    *, snapshot_dir: Path = MARKET_RISK_DIR, database: Path = MARKET_CONTEXT_DB,
    manifest_path: Path = MARKET_CONTEXT_MANIFEST_PATH, now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
    indices, etfs, breadth, gaps = [], [], {"status": "missing"}, []
    snapshot_id = None
    requested_through = None
    try:
        raw = json.loads((snapshot_dir / "current.json").read_text())
        expected_digest = raw.pop("content_digest")
        if raw.get("contract_version") != "market_risk_raw_v1" or digest(raw) != expected_digest:
            raise ValueError("snapshot digest/version mismatch")
        snapshot_id = expected_digest
        requested_through = raw["requested_through"]
        if requested_through > today:
            raise ValueError("snapshot is in the future")
        calendar = sorted({_date(day) for day in raw["calendar"] if _date(day) <= requested_through})
        if not calendar or calendar[-1] != requested_through:
            raise ValueError("calendar does not reach target session")
        for code, name in INDEX_BASKET.items():
            rows = raw["indices"].get(code, [])
            indices.append({"code": code, "name": name, "historical_only": False, **index_metrics(rows, calendar)})
        for code, group in ETF_BASKET.items():
            etfs.append({"code": code, "group": group, "source": "tushare_fund_share", **etf_metrics(
                raw["etf_shares"].get(code, []), raw["etf_navs"].get(code, []), calendar,
            )})
        breadth = breadth_metrics(raw.get("breadth", []))
        gaps += raw.get("gaps", [])
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        snapshot_id = None
        requested_through = None
        indices, etfs, breadth = [], [], {"status": "missing"}
        gaps.append("行情源综合快照缺失或未通过完整性校验；公开来源分别核对")
        try:
            indices = _historical_indices(database, manifest_path)
        except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
            gaps.append("本地历史市场基准也不可读")
    public_snapshot, public_etfs = _public_etfs(snapshot_dir / "public_etf", now)
    szse_snapshot, szse_etfs = _szse_etfs(snapshot_dir / "public_etf_szse", now)
    public_index_snapshot, public_indices = _public_indices(snapshot_dir / "public_indices", now)
    issuer_nav_snapshot, issuer_navs = load_issuer_navs(snapshot_dir / "issuer_nav", now)
    public_breadth_snapshot, public_breadth = load_public_breadth(snapshot_dir / "public_breadth", now)
    breadth_history = breadth_history_status(snapshot_dir / "public_breadth_history", now)
    combined_history = combined_breadth_status(snapshot_dir / 'combined_breadth_history', root=snapshot_dir, now=now)
    st_reference = szse_st_reference_status(snapshot_dir / 'szse_st_reference', root=snapshot_dir, market_db=database, now=now)
    st_reconstruction = st_reconstruction_status(snapshot_dir / 'st_reconstruction', root=snapshot_dir, market_db=database, now=now)
    if public_breadth.get("status") == "observed" and public_breadth["through"] >= breadth.get("through", ""):
        breadth = public_breadth
    if public_indices and (requested_through is None or public_index_snapshot["through"] > requested_through):
        # Keep the older ST background explicitly dated; never splice it onto a new market path.
        indices = public_indices + [row for row in indices if row["code"] == "st_equal_weight_v1"]
        requested_through = public_index_snapshot["through"]
        snapshot_id = public_index_snapshot["content_digest"]
    by_code = {row["code"]: row for row in etfs}
    for row in [*public_etfs, *szse_etfs]:
        previous = by_code.get(row["code"])
        more_complete = previous is not None and sum(
            metric["share_change_pct"] is not None for metric in row["windows"].values()
        ) > sum(metric["share_change_pct"] is not None for metric in previous["windows"].values())
        if (previous is None or row["evaluation_through"] > previous["evaluation_through"]
            or row["evaluation_through"] == previous["evaluation_through"] and more_complete):
            by_code[row["code"]] = row
    etfs = _with_issuer_navs(list(by_code.values()), issuer_navs, issuer_nav_snapshot)
    announcements = announcement_status(snapshot_dir / "etf_announcements", now)
    quarterly = quarterly_status(snapshot_dir / "etf_announcements", announcements, etfs, requested_through, now)
    etf_through = max((row["evaluation_through"] for row in etfs if row["evaluation_through"]), default=None)
    recent_window = recent_calendar_window(requested_through or etf_through)
    recent_indices, recent_shares = [], []
    if recent_window["availability"] == "defined":
        recent_indices = [row["recent"] for row in indices if row.get("recent")
                          and row["recent"]["start"] == recent_window["start"]
                          and row["recent"]["end"] == recent_window["end"]
                          and row["recent"]["return_pct"] is not None]
        recent_shares = [row["windows"]["recent"] for row in etfs
                         if row["windows"]["recent"]["window_start"] == recent_window["start"]
                         and row["windows"]["recent"]["window_end"] == recent_window["end"]
                         and row["windows"]["recent"]["share_change_pct"] is not None]
    attempt = None
    try:
        attempt = json.loads((snapshot_dir / "last_attempt.json").read_text())
    except (OSError, ValueError):
        pass
    return {
        "contract_version": "market_risk_status_v1", "parameter_version": PARAMETER_VERSION,
        "observation_date": today, "generated_at": now.isoformat(), "snapshot_digest": snapshot_id,
        "requested_through": requested_through,
        "status": "observed_snapshot" if snapshot_id else "historical_only" if indices else "unavailable",
        "current_risk_assessment": "not_calibrated", "indices": indices, "etfs": etfs,
        "breadth": breadth, "last_attempt": attempt, "gaps": gaps,
        "breadth_history": {**breadth_history, "matches_market_target": breadth_history.get("through") == requested_through if requested_through else False},
        "combined_breadth_history": {**combined_history, "matches_market_target": combined_history.get('through') == requested_through if requested_through else False},
        "public_etf_snapshot": public_snapshot,
        "szse_etf_snapshot": szse_snapshot,
        "szse_revision_recheck": recheck_status(snapshot_dir / "szse_revision_recheck", snapshot_dir / "public_etf_szse", now, issuer_navs),
        "etf_issuer_history": {**history_status(snapshot_dir / "issuer_action_history", now),
                               "market_target": requested_through},
        "node_market_input_audit": node_market_audit_status(snapshot_dir / "node_market_audit", now=now),
        "exchange_risk_membership": risk_membership_status(snapshot_dir / "exchange_risk_membership", now=now),
        "szse_st_reference": st_reference,
        "st_reconstruction": st_reconstruction,
        "sse_st_notice_review": sse_st_notice_status(snapshot_dir/'sse_st_notice_review', now=now),
        "sse_history_archive": sse_history_archive_status(snapshot_dir/'sse_history_archive', endpoint_dir=snapshot_dir/'public_breadth', now=now),
        "sse_gap_review": sse_gap_review_status(snapshot_dir/'sse_gap_review', root=snapshot_dir, now=now),
        "public_index_snapshot": public_index_snapshot,
        "issuer_nav_snapshot": {key: value for key, value in issuer_nav_snapshot.items() if key != "calendar"},
        "public_breadth_snapshot": public_breadth_snapshot,
        "etf_announcements": announcements,
        "etf_share_events": share_event_status(snapshot_dir / "etf_announcements", announcements, now),
        "etf_quarterly": quarterly,
        "etf_report_continuity": report_continuity_status(snapshot_dir / "etf_announcements", announcements, quarterly, now),
        "etf_notice_review": notice_review_status(snapshot_dir / "etf_announcements", announcements, now),
        "etf_prospectus_rules": prospectus_rule_status(snapshot_dir / "etf_announcements", announcements, now),
        "etf_review_scope": etf_scope_status(snapshot_dir / 'etf_review_scope', root=snapshot_dir, now=now),
        "market_coverage": {
            "indices_observed_at_target": sum(not row["historical_only"] and row["through"] == requested_through for row in indices),
            "declared_indices": len(INDEX_BASKET),
            "breadth_at_target": breadth.get("status") == "observed" and breadth.get("through") == requested_through,
            "st_style_at_target": any(row["code"] == "st_equal_weight_v1" and row["through"] == requested_through for row in indices),
            "historical_breadth_venues_at_target": (2 if requested_through and combined_history['availability']=='observed' and combined_history.get('through')==requested_through
                                                    else len(breadth_history["covered_venues"]) if breadth_history.get("through") == requested_through else 0),
            "st_reference_venues_at_target": int(st_reference['availability']=='observed' and st_reference.get('through')==requested_through),
            "st_reconstruction_source_venues_at_target": 2 if requested_through and st_reconstruction['availability']=='reconstructed' and st_reconstruction.get('through')==requested_through else 0,
        },
        "recent_window": recent_window,
        "recent_observations": {"index_coverage": len(recent_indices),
                                "declining_indices": sum(row["return_pct"] < 0 for row in recent_indices),
                                "etf_share_coverage": len(recent_shares),
                                "increasing_share_records": sum(row["share_change_pct"] > 0 for row in recent_shares),
                                "decreasing_share_records": sum(row["share_change_pct"] < 0 for row in recent_shares),
                                "interpretation": "价格走势与原始份额变化分别描述；净值覆盖另行核对，份额事件与持有人身份尚未核实，不形成资金撤退结论。"},
        "node_market_comparison": {"status": "not_evaluated", "reason": "当前只作同窗描述；个股价格/节点与独立对照未完成，不能据此证明大盘因素优于节点。"},
        "etf_aggregate": {str(horizon): {
            "evaluation_through": etf_through,
            "observed_etfs": sum(row["evaluation_through"] == etf_through and row["windows"][str(horizon)]["share_change_pct"] is not None for row in etfs),
            "nav_observed_etfs": sum(row["evaluation_through"] == etf_through and row["windows"][str(horizon)]["share_change_notional_yuan"] is not None for row in etfs),
            "revision_unconfirmed_etfs": sum(row["evaluation_through"] == etf_through and row.get("share_revision_unverified") is True and row["windows"][str(horizon)]["share_change_pct"] is not None for row in etfs),
            "declared_etfs": len(ETF_BASKET), "estimated_net_subscription_yuan": None,
            "reason": "份额事件未核验；不发布样本净申赎总金额",
        } for horizon in (1, 5, 20, "recent")},
        "parameters": {"trend_windows_sessions": list(HORIZONS), "etf_windows_sessions": [1, 5, 20],
                       "recent_calendar_months": 2,
                       "breadth_scope": "SSE_SZSE_A_shares", "breadth_session_window": 1,
                       "breadth_history_venues": ["SSE", "SZSE"], "breadth_history_calendar_months": 2,
                       "breadth_st_group_version": "current_quote_name_prefix_v1",
                       "etf_basket": ETF_BASKET, "risk_weights": None, "risk_thresholds": None},
        "limitations": [
            "先看市场环境，再看ST风格与个股节点；节点不覆盖系统性风险。",
            "ETF篮子是预先声明的8只宽基样本，不代表全体股票ETF；同指数产品可存在迁移。",
            "份额变化乘当日单位净值是名义额；折算等份额事件未核对前，不当作净申赎金额。",
            "二级市场成交额、价格下跌和基金规模下降均不是资金净流出；ETF申赎也不能识别资金身份。",
            "数据重建只作描述；未形成历史可见时点与独立检验，不证明最近两月大盘因素已优于节点。",
            "没有风险权重或交易阈值；无数据与过期数据不得解释为低风险。",
        ],
        "sources": [
            *[{"title": source["label"], "url": source["url"]} for source in BREADTH_SOURCES.values()],
            *[{"title": f"{definition['label']} {code[:6]} 单位净值", "url": definition["url"]}
              for code, definition in NAV_DEFINITIONS.items()],
            {"title": "深交所ETF份额与净值", "url": SZSE_ETF_SOURCE},
            {"title": "中证指数官方历史行情", "url": CSI_SOURCE_URL},
            {"title": "上交所ETF日终公布份额（万份）", "url": ETF_SHARE_SOURCE},
            {"title": "上交所ETF申赎说明", "url": "https://etf.sse.com.cn/fund/quertion/"},
            {"title": "Tushare基金份额（万份）", "url": "https://tushare.pro/document/2?doc_id=207"},
            {"title": "Tushare基金净值", "url": "https://tushare.pro/document/2?doc_id=119"},
        ], "read_only": True,
    }
