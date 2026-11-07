"""Explicit, bounded market materialization. Reading the panel never invokes it."""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import dotenv_values

from canonical_json import digest
from data_refresh import TushareHttpClient, atomic_write_json
from market_risk import ETF_BASKET, INDEX_BASKET, MARKET_RISK_DIR
from settings import DATA_ROOT


def refresh_market_risk(client: TushareHttpClient, *, through: str, output: Path) -> dict[str, Any]:
    end = date.fromisoformat(through)
    now = datetime.now(timezone.utc)
    if end >= now.astimezone(ZoneInfo("Asia/Shanghai")).date():
        raise ValueError("v1 只材料化观察日之前的完整收盘日")
    start = end - timedelta(days=200)
    params = {"start_date": start.strftime("%Y%m%d"), "end_date": end.strftime("%Y%m%d")}
    started = now.isoformat()
    try:
        calendar_rows = client._query("trade_cal", params={**params, "exchange": "SSE"}, fields="cal_date,is_open")
        calendar = sorted({f"{row['cal_date'][:4]}-{row['cal_date'][4:6]}-{row['cal_date'][6:8]}"
                           for row in calendar_rows if str(row["is_open"]) == "1"})
        if len(calendar) < 61:
            raise ValueError("交易日历不足61个交易日")
        target = calendar[-1]
        params["end_date"] = target.replace("-", "")
        raw: dict[str, Any] = {"contract_version": "market_risk_raw_v1", "requested_through": target,
                               "fetched_at": started, "availability_basis": "first_observed_at_fetch_not_historical_PIT",
                               "calendar": calendar, "indices": {}, "etf_shares": {}, "etf_navs": {}, "breadth": [], "gaps": []}

        def fetch(api: str, query: dict[str, str], fields: str, label: str) -> list[dict[str, Any]]:
            try:
                rows = client._query(api, params=query, fields=fields)
                if "ts_code" in query and any(row.get("ts_code") != query["ts_code"] for row in rows):
                    raise ValueError("provider returned a different instrument")
                if api == "fund_nav":
                    # One NAV per valuation date; choose only disclosures observed by this fetch date.
                    seen: dict[str, dict[str, Any]] = {}
                    for row in sorted(rows, key=lambda item: str(item.get("ann_date") or "")):
                        announced = str(row.get("ann_date") or "")
                        if len(announced) == 8 and announced <= now.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d"):
                            seen[row["nav_date"]] = row
                    rows = list(seen.values())
                if not rows:
                    raw["gaps"].append(f"{label}:empty_response")
                return rows
            except Exception as exc:
                # Credentials and arbitrary upstream response bodies never enter artifacts.
                raw["gaps"].append(f"{label}:{type(exc).__name__}")
                return []

        for code in INDEX_BASKET:
            raw["indices"][code] = fetch("index_daily", {**params, "ts_code": code},
                                         "ts_code,trade_date,close,pct_chg,amount", f"index:{code}")
        for code in ETF_BASKET:
            raw["etf_shares"][code] = fetch("fund_share", {**params, "ts_code": code},
                                            "ts_code,trade_date,fd_share", f"shares:{code}")
            raw["etf_navs"][code] = fetch("fund_nav", {**params, "ts_code": code, "market": "E"},
                                          "ts_code,ann_date,nav_date,unit_nav", f"nav:{code}")
        raw["breadth"] = fetch("daily", {"trade_date": target.replace("-", "")},
                                "ts_code,trade_date,pct_chg,amount", "market_breadth")
        if not raw["indices"].get("000985.CSI"):
            raise ValueError("缺少全市场基准；不推进current快照")
        raw["gaps"].append("ETF份额折算等公司行动尚未逐日核验；净申赎金额暂不发布")
        snapshot_digest = digest(raw)
        raw["content_digest"] = snapshot_digest
        atomic_write_json(output / "snapshots" / f"{snapshot_digest}.json", raw)
        atomic_write_json(output / "current.json", raw)
        result = {"status": "partial", "started_at": started, "completed_at": datetime.now(timezone.utc).isoformat(),
                  "requested_through": through, "observed_through": target, "snapshot_digest": snapshot_digest,
                  "gap_count": len(raw["gaps"])}
    except Exception as exc:
        message = str(exc)
        result = {"status": "failed", "started_at": started, "completed_at": datetime.now(timezone.utc).isoformat(),
                  "requested_through": through, "reason": "provider_token_expired" if "token" in message.lower() and "过期" in message else type(exc).__name__,
                  "current_snapshot_preserved": True}
    atomic_write_json(output / "last_attempt.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through", required=True, help="YYYY-MM-DD; only completed dates")
    parser.add_argument("--env-file", type=Path, default=DATA_ROOT / "local_secrets/v5_pr35_secrets/tushare_proxy.env")
    parser.add_argument("--output", type=Path, default=MARKET_RISK_DIR)
    args = parser.parse_args()
    config = dotenv_values(args.env_file) if args.env_file.is_file() else {}
    client = TushareHttpClient(token=config.get("TUSHARE_TOKEN"), url=config.get("TUSHARE_HTTP_URL"))
    result = refresh_market_risk(client, through=args.through, output=args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
