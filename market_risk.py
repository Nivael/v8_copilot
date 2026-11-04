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
from settings import DATA_ROOT, MARKET_CONTEXT_DB, MARKET_CONTEXT_MANIFEST_PATH


PARAMETER_VERSION = "market_risk_parameters_v1"
MARKET_RISK_DIR = DATA_ROOT / "local_data/v8_copilot/market_risk"
ETF_BASKET = {
    "510300.SH": "沪深300", "510310.SH": "沪深300", "510330.SH": "沪深300", "159919.SZ": "沪深300",
    "510500.SH": "中证500", "159922.SZ": "中证500", "512100.SH": "中证1000", "159845.SZ": "中证1000",
}
INDEX_BASKET = {"000985.CSI": "中证全指", "000300.SH": "沪深300", "932000.CSI": "中证2000"}
HORIZONS = (5, 20, 60)


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
        results[f"return_{horizon}d_pct"] = round((closes[-1] / closes[0] - 1) * 100, 6) if valid else None
        if horizon == 60:
            peak = closes[0] if valid else None
            drawdowns = []
            if valid:
                for value in closes:
                    peak = max(peak, value)
                    drawdowns.append((value / peak - 1) * 100)
            results["max_drawdown_60d_pct"] = round(min(drawdowns), 6) if valid else None
            results["from_60d_peak_pct"] = round(drawdowns[-1], 6) if valid else None
    amounts = [_number(points.get(day, {}).get("amount")) for day in days[-20:]]
    valid_amount = len(amounts) == 20 and all(value is not None and value >= 0 for value in amounts) and sum(amounts) > 0
    results["amount_5d_to_20d_ratio"] = round((sum(amounts[-5:]) / 5) / (sum(amounts) / 20), 6) if valid_amount else None
    observed_days = [day for day in days if _number(points.get(day, {}).get("close")) is not None]
    return {"through": observed_days[-1] if observed_days else None,
            "evaluation_through": end, "observation_count": len(observed_days), **results,
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
              "evaluation_through": days[-1] if days else None,
              "corporate_actions_checked": corporate_actions_checked, "windows": {}}
    for horizon in (1, 5, 20):
        window = days[-horizon - 1:]
        unit_counts = [share_by_day.get(day) for day in window]
        values = [nav_by_day.get(day) for day in window[1:]]
        share_ready = len(window) == horizon + 1 and all(value is not None and value > 0 for value in unit_counts)
        nav_ready = share_ready and all(value is not None and value > 0 for value in values)
        # fd_share is ten-thousand shares. Price changes/AUM changes are never called flows.
        notional = sum((unit_counts[i] - unit_counts[i - 1]) * 10_000 * values[i - 1]
                       for i in range(1, len(window))) if nav_ready else None
        output["windows"][str(horizon)] = {
            "share_change_pct": round((unit_counts[-1] / unit_counts[0] - 1) * 100, 6) if share_ready else None,
            "share_change_notional_yuan": round(notional, 2) if notional is not None else None,
            "estimated_net_subscription_yuan": round(notional, 2) if notional is not None and corporate_actions_checked else None,
            "status": "missing" if not nav_ready else "estimated" if corporate_actions_checked else "corporate_actions_unchecked",
        }
    return output


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
            etfs.append({"code": code, "group": group, **etf_metrics(
                raw["etf_shares"].get(code, []), raw["etf_navs"].get(code, []), calendar,
            )})
        breadth = breadth_metrics(raw.get("breadth", []))
        gaps += raw.get("gaps", [])
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        snapshot_id = None
        requested_through = None
        indices, etfs, breadth = [], [], {"status": "missing"}
        gaps.append("当前大盘快照缺失或未通过完整性校验")
        try:
            indices = _historical_indices(database, manifest_path)
        except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
            gaps.append("本地历史市场基准也不可读")
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
        "etf_aggregate": {str(horizon): {
            "observed_etfs": sum(row["windows"][str(horizon)]["share_change_notional_yuan"] is not None for row in etfs),
            "declared_etfs": len(ETF_BASKET), "estimated_net_subscription_yuan": None,
            "reason": "份额事件未核验；不发布样本净申赎总金额",
        } for horizon in (1, 5, 20)},
        "parameters": {"trend_windows_sessions": list(HORIZONS), "etf_windows_sessions": [1, 5, 20],
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
            {"title": "上交所ETF申赎说明", "url": "https://etf.sse.com.cn/fund/quertion/"},
            {"title": "Tushare基金份额（万份）", "url": "https://tushare.pro/document/2?doc_id=207"},
            {"title": "Tushare基金净值", "url": "https://tushare.pro/document/2?doc_id=119"},
        ], "read_only": True,
    }
