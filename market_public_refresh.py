"""Explicit collection of official CSI price indices, separate from the legacy manifest."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from market_calendar import CALENDAR_SOURCE, CALENDAR_VERSION, sessions_2026
from market_risk import CSI_PERF_URL, CSI_SOURCE_URL, INDEX_BASKET, MARKET_RISK_DIR, _date, _number


def parse_index_perf(payload: dict, code: str, calendar: list[str]) -> list[dict]:
    if code not in INDEX_BASKET or str(payload.get("code")) != "200" or not isinstance(payload.get("data"), list):
        raise ValueError("invalid CSI response")
    rows = []
    seen = set()
    for record in payload["data"]:
        day = _date(record["tradeDate"])
        if record["indexCode"] != code[:6] or day not in calendar or day in seen:
            raise ValueError("wrong index, non-session, out-of-window or duplicate date")
        seen.add(day)
        close = _number(record.get("close"))
        value = _number(record.get("tradingValue"))
        if close is None or close <= 0 or record.get("tradingValue") is not None and (value is None or value < 0):
            raise ValueError("invalid CSI close/amount")
        rows.append({"ts_code": code, "trade_date": day, "close": close,
                     "amount": value * 100_000_000 if value is not None else None})
    return sorted(rows, key=lambda row: row["trade_date"])


class CSIIndexClient:
    def __init__(self, response_dir: Path):
        self.response_dir = response_dir

    def get_index(self, code: str, calendar: list[str]) -> tuple[list[dict], dict]:
        if code not in INDEX_BASKET:
            raise ValueError("undeclared CSI index")
        url = CSI_PERF_URL + "?" + urlencode({"indexCode": code[:6], "startDate": calendar[0].replace("-", ""),
                                             "endDate": calendar[-1].replace("-", "")})
        request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.csindex.com.cn/"})
        with urlopen(request, timeout=20) as response:
            raw = response.read(4_000_001)
        if len(raw) > 4_000_000:
            raise ValueError("CSI response too large")
        content_hash = hashlib.sha256(raw).hexdigest()
        self.response_dir.mkdir(parents=True, exist_ok=True)
        (self.response_dir / f"{content_hash}.json").write_bytes(raw)
        rows = parse_index_perf(json.loads(raw), code, calendar)
        return rows, {"code": code, "url": url, "response_sha256": content_hash,
                      "observed_at": datetime.now(timezone.utc).isoformat(),
                      "reported_amount_unit": "CNY100M", "normalized_amount_unit": "CNY"}


def refresh_public_indices(client, *, through: str, output: Path, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    end = date.fromisoformat(through)
    if end >= now.astimezone(ZoneInfo("Asia/Shanghai")).date():
        raise ValueError("only completed dates are supported")
    calendar = sessions_2026(date(end.year, 1, 1), end)[-61:]
    if len(calendar) != 61 or calendar[-1] != through:
        raise ValueError("61 verified sessions ending at the target are required")
    raw = {"contract_version": "public_market_indices_raw_v1", "provider": "csindex_official",
           "source_url": CSI_SOURCE_URL, "api_url": CSI_PERF_URL, "amount_unit": "CNY",
           "requested_through": through, "fetched_at": now.isoformat(), "calendar": calendar,
           "calendar_version": CALENDAR_VERSION, "calendar_source": CALENDAR_SOURCE,
           "availability_basis": "first_observed_at_fetch_not_historical_PIT",
           "scope": "three_price_indices_only", "indices": {}, "responses": [], "gaps": []}
    for code in INDEX_BASKET:
        try:
            rows, provenance = client.get_index(code, calendar)
            days = [row["trade_date"] for row in rows]
            if len(days) != len(set(days)) or any(row.get("ts_code") != code or row["trade_date"] not in calendar
                or (_number(row.get("close")) or 0) <= 0
                or row.get("amount") is not None and (_number(row["amount"]) is None or _number(row["amount"]) < 0) for row in rows):
                raise ValueError("invalid normalized CSI observations")
            raw["indices"][code] = rows
            raw["responses"].append(provenance)
            raw["gaps"].extend(f"{code}:{day}:missing" for day in calendar if day not in days)
        except Exception as exc:
            raw["indices"][code] = []
            raw["gaps"].append(f"{code}:{type(exc).__name__}")
    has_target = any(row["trade_date"] == through for row in raw["indices"]["000985.CSI"])
    report = {"status": "complete" if has_target and not raw["gaps"] else "partial" if has_target else "failed",
              "requested_through": through, "completed_at": datetime.now(timezone.utc).isoformat(),
              "scope": raw["scope"], "gap_count": len(raw["gaps"])}
    if has_target:
        raw["content_digest"] = digest(raw)
        atomic_write_json(output / "snapshots" / f"{raw['content_digest']}.json", raw)
        atomic_write_json(output / "current.json", raw)
        report["snapshot_digest"] = raw["content_digest"]
        report["observations"] = sum(len(rows) for rows in raw["indices"].values())
    else:
        report.update(reason="broad_market_target_missing", current_snapshot_preserved=True)
    atomic_write_json(output / "last_attempt.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through", required=True)
    parser.add_argument("--output", type=Path, default=MARKET_RISK_DIR / "public_indices")
    args = parser.parse_args()
    report = refresh_public_indices(CSIIndexClient(args.output / "responses"), through=args.through, output=args.output)
    print(json.dumps(report, ensure_ascii=False))
    return 2 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
