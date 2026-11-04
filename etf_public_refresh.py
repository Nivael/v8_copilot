"""Explicit SSE daily-share collection, independent of the private market provider."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from market_calendar import CALENDAR_SOURCE, CALENDAR_VERSION, sessions_2026
from market_risk import ETF_BASKET, ETF_SHARE_SOURCE as SHARE_SOURCE, ETF_SHARE_SQL as SHARE_SQL, MARKET_RISK_DIR, _public_etfs

PUBLIC_CODES = tuple(code for code in ETF_BASKET if code.endswith(".SH"))


def parse_share_pages(pages: list[dict], day: str) -> tuple[list[dict], int]:
    """Reject incomplete pages, wrong dates, duplicates, and ambiguous numeric fields."""
    total = None
    rows = []
    for page_no, payload in enumerate(pages, 1):
        if payload.get("actionErrors") or payload.get("fieldErrors"):
            raise ValueError("exchange query error")
        meta = payload["pageHelp"]
        count = int(meta["total"])
        if total is None:
            total = count
        if count != total or int(meta["pageNo"]) != page_no or int(meta["pageCount"]) != len(pages):
            raise ValueError("inconsistent pagination")
        rows.extend(payload["result"])
    if not rows or total != len(rows):
        raise ValueError("empty or truncated exchange response")
    seen = set()
    selected = []
    for row in rows:
        code = row["SEC_CODE"]
        if row["STAT_DATE"] != day or code in seen:
            raise ValueError("wrong date or duplicate ETF")
        seen.add(code)
        full_code = f"{code}.SH"
        if full_code not in PUBLIC_CODES:
            continue
        value = row["TOT_VOL"]
        shares = float(value)
        if isinstance(value, bool) or not math.isfinite(shares) or shares <= 0:
            raise ValueError("invalid ETF shares")
        selected.append({"ts_code": full_code, "trade_date": day, "fd_share": shares})
    return selected, len(rows)


class SSEShareClient:
    def __init__(self, response_dir: Path):
        self.response_dir = response_dir

    def get_day(self, day: str) -> tuple[list[dict], list[dict]]:
        pages, provenance = [], []
        page_count = 1
        page_no = 1
        while page_no <= page_count:
            params = {"sqlId": SHARE_SQL, "isPagination": "true", "STAT_DATE": day,
                      "pageHelp.pageSize": 1000, "pageHelp.pageNo": page_no,
                      "pageHelp.beginPage": page_no, "pageHelp.endPage": page_no, "pageHelp.cacheSize": 1}
            url = "https://query.sse.com.cn/commonQuery.do?" + urlencode(params)
            request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": SHARE_SOURCE})
            with urlopen(request, timeout=20) as response:
                raw = response.read(4_000_001)
            if len(raw) > 4_000_000:
                raise ValueError("exchange response too large")
            payload = json.loads(raw)
            page_count = int(payload["pageHelp"]["pageCount"])
            if not 1 <= page_count <= 10:
                raise ValueError("unexpected exchange page count")
            payload_digest = hashlib.sha256(raw).hexdigest()
            self.response_dir.mkdir(parents=True, exist_ok=True)
            (self.response_dir / f"{payload_digest}.json").write_bytes(raw)
            pages.append(payload)
            provenance.append({"query_date": day, "page": page_no, "url": url,
                               "response_sha256": payload_digest,
                               "observed_at": datetime.now(timezone.utc).isoformat()})
            page_no += 1
        selected, count = parse_share_pages(pages, day)
        for item in provenance:
            item["complete_daily_rows"] = count
        return selected, provenance


def refresh_public_etfs(client, *, through: str, output: Path, sessions: int = 21,
                        now: datetime | None = None, repair_missing: bool = False) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    end = date.fromisoformat(through)
    if end >= now.astimezone(ZoneInfo("Asia/Shanghai")).date() or not 21 <= sessions <= 61:
        raise ValueError("Only completed dates and 21–61 sessions are supported")
    calendar = sessions_2026(date(end.year, 1, 1), end)[-sessions:]
    if len(calendar) != sessions or calendar[-1] != through:
        raise ValueError("Target must be a verified 2026 session with sufficient history")
    reusable = {}
    reused_digest = None
    if repair_missing:
        state, _ = _public_etfs(output, now)
        if state["availability"] != "observed":
            raise ValueError("No verified public snapshot is available to repair")
        prior = json.loads((output / "current.json").read_text())
        expected = prior.pop("content_digest")
        if digest(prior) != expected or expected != state["content_digest"] or prior["calendar"] != calendar:
            raise ValueError("Repair input changed or has a different window")
        reused_digest = expected
        for day in calendar:
            rows = [row for values in prior["etf_shares"].values() for row in values if row["trade_date"] == day]
            if {row["ts_code"] for row in rows} == set(PUBLIC_CODES) and len(rows) == len(PUBLIC_CODES):
                reusable[day] = (rows, [ref for ref in prior["responses"] if ref["query_date"] == day])
    started = now.isoformat()
    raw = {"contract_version": "public_etf_shares_raw_v1", "provider": "sse_public",
           "source_url": SHARE_SOURCE, "source_sql": SHARE_SQL, "share_unit": "ten_thousand_shares",
           "requested_through": through, "fetched_at": started,
           "availability_basis": "first_observed_at_fetch_not_historical_PIT",
           "calendar_version": CALENDAR_VERSION, "calendar_source": CALENDAR_SOURCE,
           "calendar": calendar, "declared_codes": list(PUBLIC_CODES),
           "collection_mode": "repair_missing_dates" if repair_missing else "fresh",
           "reused_from_digest": reused_digest,
           "etf_shares": {code: [] for code in PUBLIC_CODES}, "responses": [], "gaps": []}
    for day in calendar:
        try:
            rows, provenance = reusable[day] if day in reusable else client.get_day(day)
            codes = [row["ts_code"] for row in rows]
            if len(codes) != len(set(codes)) or any(code not in PUBLIC_CODES for code in codes):
                raise ValueError("unexpected ETF codes")
            if any(row["trade_date"] != day or isinstance(row["fd_share"], bool)
                   or not math.isfinite(float(row["fd_share"])) or float(row["fd_share"]) <= 0 for row in rows):
                raise ValueError("invalid ETF date/value")
            for row in rows:
                raw["etf_shares"][row["ts_code"]].append(row)
            raw["responses"].extend(provenance)
            for code in set(PUBLIC_CODES) - set(codes):
                raw["gaps"].append(f"{code}:{day}:missing")
        except Exception as exc:
            raw["gaps"].append(f"{day}:{type(exc).__name__}")
    has_target = any(any(row["trade_date"] == through for row in rows) for rows in raw["etf_shares"].values())
    result = {"status": "partial" if has_target else "failed", "started_at": started,
              "completed_at": datetime.now(timezone.utc).isoformat(), "requested_through": through,
              "gap_count": len(raw["gaps"]), "source": "sse_public"}
    result["reused_complete_dates"] = len(reusable)
    if has_target:
        raw["content_digest"] = digest(raw)
        atomic_write_json(output / "snapshots" / f"{raw['content_digest']}.json", raw)
        atomic_write_json(output / "current.json", raw)
        result["snapshot_digest"] = raw["content_digest"]
        result["observed_etfs_at_target"] = sum(any(row["trade_date"] == through for row in rows) for rows in raw["etf_shares"].values())
    else:
        result.update(reason="no_target_share_observations", current_snapshot_preserved=True)
    atomic_write_json(output / "last_attempt.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through", required=True)
    parser.add_argument("--sessions", type=int, default=21)
    parser.add_argument("--repair", action="store_true", help="Reuse verified complete dates; request only missing dates")
    parser.add_argument("--output", type=Path, default=MARKET_RISK_DIR / "public_etf")
    args = parser.parse_args()
    report = refresh_public_etfs(SSEShareClient(args.output / "responses"), through=args.through,
                                 output=args.output, sessions=args.sessions, repair_missing=args.repair)
    print(json.dumps(report, ensure_ascii=False))
    return 2 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
