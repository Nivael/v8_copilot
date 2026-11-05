"""Explicit SZSE share/NAV history collection with the source's revision caveat."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from market_calendar import CALENDAR_SOURCE, CALENDAR_VERSION, sessions_2026
from settings import DATA_ROOT
from etf_szse_history import API_URL as SZSE_API, SOURCE_URL as SZSE_SOURCE, HTTP_API_URL, SZSE_CODES, archive_response, history_url, parse_history, number as _number

MARKET_RISK_DIR = DATA_ROOT / "local_data/v8_copilot/market_risk"
REVISION_NOTE = "深交所提示T日晚间的T日规模仅供参考，以T+1日早间更新的T日规模为准；本次未取得最终修订标记。"


class SZSEHistoryClient:
    def __init__(self, response_dir: Path, *, api_url: str = SZSE_API):
        if api_url not in (SZSE_API, HTTP_API_URL): raise ValueError("undeclared SZSE transport")
        self.response_dir, self.api_url = response_dir, api_url

    def get_history(self, code: str, calendar: list[str], *, nav: bool = False) -> tuple[list[dict], list[dict]]:
        pages, provenance, count = [], [], 1
        page = 1
        while page <= count:
            url = history_url(self.api_url, code, calendar, nav=nav, page=page)
            with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": SZSE_SOURCE}), timeout=20) as response:
                if response.geturl() != url: raise ValueError("unexpected SZSE redirect")
                raw = response.read(4_000_001)
            if len(raw) > 4_000_000:
                raise ValueError("SZSE history response too large")
            payload = json.loads(raw)
            metadata = payload[0]["metadata"]
            count = max(1, int(metadata["pagecount"]))
            if count > 10:
                raise ValueError("unexpected history page count")
            content_hash = hashlib.sha256(raw).hexdigest()
            archive_response(self.response_dir / f"{content_hash}.json", raw)
            pages.append(payload)
            provenance.append({"code": code, "kind": "NAV" if nav else "shares", "page": page,
                               "url": url, "response_sha256": content_hash,
                               "observed_at": datetime.now(timezone.utc).isoformat()})
            page += 1
        return parse_history(pages, code, calendar, nav=nav), provenance


def refresh_szse_etfs(client, *, through: str, output: Path, now: datetime | None = None, sessions: int = 21) -> dict:
    now = now or datetime.now(timezone.utc)
    end = date.fromisoformat(through)
    if end >= now.astimezone(ZoneInfo("Asia/Shanghai")).date() or not 21 <= sessions <= 61:
        raise ValueError("only completed dates and 21–61 sessions are supported")
    calendar = sessions_2026(date(end.year, 1, 1), end)[-sessions:]
    if len(calendar) != sessions or calendar[-1] != through:
        raise ValueError("verified sessions ending at target required")
    raw = {"contract_version": "szse_etf_history_raw_v1", "provider": "szse_public", "source_url": SZSE_SOURCE,
           "api_url": getattr(client, "api_url", SZSE_API), "share_unit": "ten_thousand_shares", "nav_unit": "CNY_per_share",
           "requested_through": through, "fetched_at": now.isoformat(), "calendar": calendar,
           "calendar_source": CALENDAR_SOURCE, "calendar_version": CALENDAR_VERSION,
           "availability_basis": "first_observed_at_fetch_not_historical_PIT",
           "share_revision_status": "final_revision_unverified", "revision_note": REVISION_NOTE,
           "etf_shares": {}, "etf_navs": {}, "responses": [], "gaps": []}
    for code in SZSE_CODES:
        for nav, key, day_key in ((False, "etf_shares", "trade_date"), (True, "etf_navs", "nav_date")):
            try:
                rows, refs = client.get_history(code, calendar, nav=nav)
                days = [row[day_key] for row in rows]
                value_key = "unit_nav" if nav else "fd_share"
                if len(days) != len(set(days)) or any(row["ts_code"] != code or row[day_key] not in calendar
                    or (_number(row.get(value_key)) or 0) <= 0 for row in rows):
                    raise ValueError("invalid normalized history")
                raw[key][code] = rows
                raw["responses"].extend(refs)
                raw["gaps"].extend(f"{code}:{key}:{day}:missing" for day in calendar if day not in days)
            except Exception as exc:
                raw[key][code] = []
                raw["gaps"].append(f"{code}:{key}:{type(exc).__name__}")
    has_target = any(any(row["trade_date"] == through for row in values) for values in raw["etf_shares"].values())
    report = {"status": "partial" if has_target else "failed", "requested_through": through,
              "completed_at": datetime.now(timezone.utc).isoformat(), "gap_count": len(raw["gaps"]),
              "share_revision_status": raw["share_revision_status"]}
    if has_target:
        raw["content_digest"] = digest(raw)
        atomic_write_json(output / "snapshots" / f"{raw['content_digest']}.json", raw)
        atomic_write_json(output / "current.json", raw)
        report.update(snapshot_digest=raw["content_digest"], share_observations=sum(map(len, raw["etf_shares"].values())),
                      nav_observations=sum(map(len, raw["etf_navs"].values())))
    else:
        report.update(reason="target_shares_missing", current_snapshot_preserved=True)
    atomic_write_json(output / "last_attempt.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through", required=True)
    parser.add_argument("--sessions", type=int, default=21)
    parser.add_argument("--output", type=Path, default=MARKET_RISK_DIR / "public_etf_szse")
    args = parser.parse_args()
    report = refresh_szse_etfs(SZSEHistoryClient(args.output / "responses"), through=args.through, output=args.output, sessions=args.sessions)
    print(json.dumps(report, ensure_ascii=False))
    return 2 if report["status"] == "failed" else 0


if __name__ == "__main__": raise SystemExit(main())
