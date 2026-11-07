"""Explicit primary issuer NAV collection: legacy eight or the declared broad twelve."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
from http.client import IncompleteRead
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from etf_issuer_nav import NAV_VERSION, BROAD_NAV_VERSION, nav_definitions, load_issuer_navs, validate_nav_rows
from etf_nav_parsers import NAVTable, parse_chinaamc, parse_efunds, parse_huatai, parse_jsfund, parse_nffund
from market_calendar import CALENDAR_SOURCE, CALENDAR_VERSION, sessions_2026
from etf_nav_sources import CHINAAMC_API, EFUNDS_SCHEMA, HUATAI_API, HUATAI_SITE, NF_API, reconcile_fund, reconcile_issuer_navs
from settings import DATA_ROOT

DEFAULT_OUTPUT = DATA_ROOT / "local_data/v8_copilot/market_risk/issuer_nav"
BROAD_OUTPUT = DEFAULT_OUTPUT.parent / "trader_observations/broad_fund_evidence/issuer_nav"


class IssuerNAVClient:
    def __init__(self, response_dir: Path, *, version=NAV_VERSION):
        self.response_dir = response_dir
        self.version = version
        self.definitions = nav_definitions(version)

    def request(self, url: str, params: dict | None = None, *, post=False, code: str, refs: list) -> bytes:
        params = params or {}
        address = url + ("?" + urlencode(params) if params and not post else "")
        request = Request(address, data=urlencode(params).encode() if post else None,
                          headers={"User-Agent": "Mozilla/5.0", "Referer": self.definitions[code]["url"]})
        # A retry is bounded and only handles transport failures. Invalid parsed data is never retried into validity.
        for attempt in range(2):
            try:
                with urlopen(request, timeout=20) as response:
                    raw = response.read(4_000_001)
                    length = response.headers.get("Content-Length")
                    content_type = response.headers.get("Content-Type", "")
                if len(raw) > 4_000_000 or length is not None and len(raw) != int(length):
                    raise ValueError("oversized or incomplete response")
                break
            except (OSError, TimeoutError, IncompleteRead):
                if attempt:
                    raise
        content_hash = hashlib.sha256(raw).hexdigest()
        self.response_dir.mkdir(parents=True, exist_ok=True)
        (self.response_dir / f"{content_hash}.raw").write_bytes(raw)
        refs.append({"code": code, "url": url, "method": "POST" if post else "GET", "params": params,
                     "observed_at": datetime.now(timezone.utc).isoformat(), "response_sha256": content_hash,
                     "bytes": len(raw), "content_type": content_type})
        return raw

    def get_navs(self, code: str, calendar: list[str]) -> tuple[list[dict], list[dict]]:
        provider = self.definitions[code]["provider"]
        refs, result = [], []
        if provider == "jsfund":
            text = self.request(self.definitions[code]["url"], code=code, refs=refs).decode("utf-8")
            result = parse_jsfund(text, code, calendar)
        elif provider == "efunds":
            page = self.request(self.definitions[code]["url"], code=code, refs=refs).decode("utf-8")
            url = f"https://cdn.efunds.com.cn/market/2.0/{code[:6]}_1y.js"
            if url not in page or not re.search(r'var\s+fundCode\s*=\s*"' + code[:6] + '"', page) or "单位净值(元)" not in page:
                raise ValueError("EFunds product identity/unit/link changed")
            schema = self.request(EFUNDS_SCHEMA, code=code, refs=refs).decode("utf-8")
            if not re.search(r"2\s+EnumSourceTypeNetValue\s+单位净值", schema):
                raise ValueError("EFunds NAV column definition changed")
            result = parse_efunds(self.request(url, code=code, refs=refs).decode("utf-8"), code, calendar)
        else:
            expected_pages, prior_oldest = None, None
            for page in range(1, 11):
                if provider == "chinaamc":
                    params = {"fundcode": code[:6], "beginDate": calendar[0], "endDate": calendar[-1], "isQuery": "true" if page == 1 else "", "pageIndex": page}
                    text = self.request(CHINAAMC_API, params, post=True, code=code, refs=refs).decode("utf-8")
                    rows, pages = parse_chinaamc(text, code, calendar, page)
                elif provider == "huatai_pb":
                    params = {"fundcode": code[:6], "from": calendar[0], "to": calendar[-1], "pages": f"{page}-10", "siteId": HUATAI_SITE}
                    payload = json.loads(self.request(HUATAI_API, params, code=code, refs=refs))
                    rows, pages = parse_huatai(payload, code, calendar, page)
                else:
                    payload = json.loads(self.request(NF_API, {"fundCode": code[:6], "curPage": page, "pageSize": 10}, post=True, code=code, refs=refs))
                    rows, count, oldest = parse_nffund(payload, code, calendar, page)
                    if prior_oldest is not None and payload["data"]["jjjzList"]["list"][0]["fdate_ex"] >= prior_oldest:
                        raise ValueError("NFFund history changed across pages")
                    # Its all-history total can vary between server responses (outside our date filter).
                    # Completeness is instead proven by the exact independently verified session calendar.
                    # Retain every reported total and the response itself for review.
                    if refs:
                        refs[-1]["reported_history_total"] = count
                        refs[-1]["pagination_basis"] = "exact_requested_trading_calendar"
                    prior_oldest = oldest
                    pages = page if oldest <= calendar[0] else 10
                if provider != "nffund":
                    if not 1 <= pages <= 10 or expected_pages is not None and pages != expected_pages:
                        raise ValueError("changing or excessive page count")
                    expected_pages = pages
                result.extend(rows)
                if page == pages:
                    break
        result.sort(key=lambda row: row["nav_date"])
        validate_nav_rows(result, code, calendar, version=self.version)
        return result, refs


def _staged_navs(path: Path, code: str, calendar: list[str], now: datetime, response_dir: Path, *, version=NAV_VERSION):
    try:
        staged = json.loads(path.read_text())
        expected = staged.pop("content_digest")
        fetched = datetime.fromisoformat(staged["fetched_at"])
        if (digest(staged) != expected or staged["definition"] != nav_definitions(version)[code]
            or staged["calendar"] != calendar or staged["nav_unit"] != "CNY_per_share"
            or fetched.tzinfo is None or fetched > now or fetched.date().isoformat() < calendar[-1]):
            raise ValueError("staged NAV binding mismatch")
        validate_nav_rows(staged["rows"], code, calendar, version=version)
        reconcile_fund(response_dir.parent, code, calendar, staged["rows"], staged["responses"], now, version=version)
        return staged["rows"], staged["responses"]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def refresh_issuer_navs(client, *, through: str, output: Path, sessions=61, now: datetime | None = None, repair=False, version=NAV_VERSION) -> dict:
    fixed_now = now
    now = now or datetime.now(timezone.utc)
    definitions = nav_definitions(version)
    end = date.fromisoformat(through)
    if end >= now.astimezone(ZoneInfo("Asia/Shanghai")).date() or not 21 <= sessions <= 61:
        raise ValueError("only completed dates and 21–61 sessions are supported")
    calendar = sessions_2026(date(end.year, 1, 1), end)[-sessions:]
    if len(calendar) != sessions or calendar[-1] != through:
        raise ValueError("verified window ending at target required")
    raw = {"contract_version": version, "definitions": definitions, "nav_unit": "CNY_per_share",
           "requested_through": through, "fetched_at": now.isoformat(), "calendar": calendar,
           "calendar_source": CALENDAR_SOURCE, "calendar_version": CALENDAR_VERSION,
           "availability_basis": "first_observed_at_fetch_not_historical_PIT", "etf_navs": {}, "responses": []}
    failures, reused = [], 0
    for code in definitions:
        try:
            stage_path = output / "staging" / f"{through}-{sessions}" / f"{code}.json"
            staged = _staged_navs(stage_path, code, calendar, now, output / "responses", version=version) if repair else None
            reusing = staged is not None
            if staged is not None:
                rows, refs = staged
                reused += 1
            else:
                rows, refs = client.get_navs(code, calendar)
            validate_nav_rows(rows, code, calendar, version=version)
            reconcile_fund(output, code, calendar, rows, refs, fixed_now or datetime.now(timezone.utc), version=version)
            staged = {"definition": definitions[code], "calendar": calendar, "nav_unit": "CNY_per_share",
                      "fetched_at": now.isoformat(), "rows": rows, "responses": refs}
            staged["content_digest"] = digest(staged)
            if not reusing:
                atomic_write_json(stage_path, staged)
            raw["etf_navs"][code] = rows
            raw["responses"].extend(refs)
        except Exception as exc:
            failures.append({"code": code, "error_type": type(exc).__name__})
    report = {"status": "failed" if failures else "complete", "requested_through": through,
              "completed_at": datetime.now(timezone.utc).isoformat(), "failures": failures,
              "reused_series": reused,
              "complete_series": len(raw["etf_navs"]), "declared_series": len(definitions)}
    previous, previous_rows = load_issuer_navs(output, fixed_now or datetime.now(timezone.utc))
    if previous_rows and not set(previous_rows).issubset(definitions):
        report.update(status="failed", reason="would_regress_existing_scope")
    if previous_rows and (previous["through"] > through or previous["through"] == through and len(previous["calendar"]) > sessions):
        report.update(status="failed", reason="would_regress_existing_window")
    if report["status"] == "complete":
        raw["content_digest"] = digest(raw)
        try:
            reconcile_issuer_navs(output, raw, fixed_now or datetime.now(timezone.utc))
            atomic_write_json(output / "snapshots" / f"{raw['content_digest']}.json", raw)
            atomic_write_json(output / "current.json", raw)
            report.update(snapshot_digest=raw["content_digest"], nav_observations=sum(map(len, raw["etf_navs"].values())))
        except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError) as exc:
            report.update(status="failed", reason=type(exc).__name__)
    if report["status"] != "complete":
        report["current_snapshot_preserved"] = True
    atomic_write_json(output / "last_attempt.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through", required=True)
    parser.add_argument("--sessions", type=int, default=61)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--profile", choices=['legacy8','broad12'], default='legacy8')
    parser.add_argument("--repair", action="store_true", help="reuse integrity-checked complete series for this exact window")
    args = parser.parse_args()
    version = BROAD_NAV_VERSION if args.profile == 'broad12' else NAV_VERSION
    output = args.output or (BROAD_OUTPUT if args.profile == 'broad12' else DEFAULT_OUTPUT)
    report = refresh_issuer_navs(IssuerNAVClient(output / "responses", version=version), through=args.through, output=output, sessions=args.sessions, repair=args.repair, version=version)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
