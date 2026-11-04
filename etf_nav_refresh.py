"""Explicit, bounded collection of the eight declared ETFs' primary issuer NAVs."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
from http.client import IncompleteRead
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from etf_issuer_nav import NAV_DEFINITIONS, NAV_VERSION, load_issuer_navs, validate_nav_rows
from market_calendar import CALENDAR_SOURCE, CALENDAR_VERSION, sessions_2026
from settings import DATA_ROOT

DEFAULT_OUTPUT = DATA_ROOT / "local_data/v8_copilot/market_risk/issuer_nav"
HUATAI_API = "https://www.huatai-pb.com/common-web/chart/fundnettable/getFundNetTableJson"
HUATAI_SITE = "9496d23c648f4a72a79150c3f2ac669b"
NF_API = "https://www.nffund.com/nfwebApi/fund/newValueList"
CHINAAMC_API = "https://www.chinaamc.com/product/fundLishijingzhi.do"
EFUNDS_SCHEMA = "https://www.efunds.com.cn/js/fund_details/product-detail-overview.js?7905e4a6"


class NAVTable(HTMLParser):
    def __init__(self, text: str):
        super().__init__()
        self.tables, self.inputs, self.selected = [], {}, []
        self.table = self.row = self.cell = None
        if not re.search(r"</html>\s*$", text, re.I):
            raise ValueError("incomplete HTML document")
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name"):
            self.inputs[attrs["name"]] = attrs.get("value")
        elif tag == "option" and "selected" in attrs:
            self.selected.append(attrs.get("value"))
        elif tag == "table":
            if self.table is not None:
                raise ValueError("nested NAV tables are unsupported")
            self.table = {"attrs": attrs, "rows": []}
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("th", "td") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table["rows"].append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None

    def table_rows(self, *, identifier=None, css_class=None):
        matches = [table["rows"] for table in self.tables
                   if (identifier is None or table["attrs"].get("id") == identifier)
                   and (css_class is None or css_class in table["attrs"].get("class", "").split())]
        if len(matches) != 1:
            raise ValueError("missing or ambiguous NAV table")
        return matches[0]


def normalized(rows: list[tuple[str, object]], code: str, calendar: list[str], *, bounded: bool) -> list[dict]:
    result, seen = [], set()
    for day, value in rows:
        if re.fullmatch(r"\d{8}", day):
            day = f"{day[:4]}-{day[4:6]}-{day[6:]}"
        day = date.fromisoformat(day).isoformat()
        number = float(str(value).replace(",", ""))
        if day in seen or isinstance(value, bool) or not math.isfinite(number) or number <= 0:
            raise ValueError("duplicate date or invalid NAV")
        seen.add(day)
        if day not in calendar:
            if bounded or calendar[0] <= day <= calendar[-1]:
                raise ValueError("NAV date outside requested trading calendar")
            continue
        result.append({"ts_code": code, "nav_date": day, "unit_nav": number})
    return sorted(result, key=lambda row: row["nav_date"])


def parse_chinaamc(text: str, code: str, calendar: list[str], page: int) -> tuple[list[dict], int]:
    parsed = NAVTable(text)
    if (parsed.inputs.get("fundcode") != code[:6] or parsed.inputs.get("beginDate") != calendar[0]
        or parsed.inputs.get("endDate") != calendar[-1]
        or parsed.table_rows(identifier="hoverBox1") != [["净值日期", "单位净值", "累计净值", "资产净值"]]):
        raise ValueError("wrong ChinaAMC code, dates or NAV columns")
    current = re.findall(r"let\s+currentPage\s*=\s*'(\d+)'", text)
    total = re.findall(r"let\s+totalPage\s*=\s*'(\d+)'", text)
    if set(current) != {str(page)} or len(set(total)) != 1:
        raise ValueError("wrong ChinaAMC page")
    rows = parsed.table_rows(identifier="hoverBox1_1")
    if not rows or any(len(row) != 4 for row in rows):
        raise ValueError("invalid ChinaAMC NAV rows")
    return normalized([(row[0], row[1]) for row in rows], code, calendar, bounded=True), int(total[0])


def parse_jsfund(text: str, code: str, calendar: list[str]) -> list[dict]:
    parsed = NAVTable(text)
    if parsed.inputs.get("FundCode") != code[:6] or code[:6] not in parsed.selected:
        raise ValueError("wrong JSFund instrument")
    rows = parsed.table_rows(css_class="mm_r_table7")
    if not rows or rows[0] != ["日期", "份额净值", "累计净值"] or any(len(row) != 3 for row in rows[1:]):
        raise ValueError("wrong JSFund NAV columns")
    return normalized([(row[0], row[1]) for row in rows[1:]], code, calendar, bounded=False)


def parse_huatai(payload: dict, code: str, calendar: list[str], page: int) -> tuple[list[dict], int]:
    rows = payload["dataList"]
    if int(payload["currentPage"]) != page or not rows or any(row["fundcode"] != code[:6] for row in rows):
        raise ValueError("wrong Huatai instrument/page")
    return normalized([(row["date"], row["netvalue"]) for row in rows], code, calendar, bounded=True), int(payload["totalPage"])


def parse_nffund(payload: dict, code: str, calendar: list[str], page: int) -> tuple[list[dict], int, str]:
    if payload["code"] != "ETS-5BP00000":
        raise ValueError("NFFund request failed")
    block = payload["data"]["jjjzList"]
    rows = block["list"]
    # This endpoint ignores date ranges. Walk its dated pages until the lower boundary.
    if (block["pageNum"] != page or block["pageSize"] != 10 or len(rows) != block["size"] or not rows
        or block["pages"] != math.ceil(block["total"] / 10)
        or len(rows) != min(10, block["total"] - (page - 1) * 10)
        or any(row.get("fundCode") not in (None, code[:6]) for row in rows)):
        raise ValueError("invalid NFFund pagination/instrument")
    dates = [date.fromisoformat(row["fdate_ex"]).isoformat() for row in rows]
    if dates != sorted(set(dates), reverse=True) or any(row["fdate"] != day.replace("-", "") for row, day in zip(rows, dates)):
        raise ValueError("invalid NFFund dates/order")
    return normalized([(row["fdate_ex"], row["fundNav"]) for row in rows], code, calendar, bounded=False), block["total"], dates[-1]


def parse_efunds(text: str, code: str, calendar: list[str]) -> list[dict]:
    # Parse the official literal as data; never evaluate downloaded JavaScript.
    match = re.fullmatch(r'\s*mk_' + code[:6] + r'_1y="([\d_;.\-]+)";\s*', text)
    if not match:
        raise ValueError("invalid EFunds literal/instrument")
    records = match[1].split(";")
    if records[0] != "0_1_2_3_4" or records[-1] != "":
        raise ValueError("unexpected EFunds column schema")
    rows = [record.split("_") for record in records[1:-1]]
    if any(len(row) != 5 for row in rows):
        raise ValueError("truncated EFunds records")
    return normalized([(row[0], row[2]) for row in rows], code, calendar, bounded=False)


class IssuerNAVClient:
    def __init__(self, response_dir: Path):
        self.response_dir = response_dir

    def request(self, url: str, params: dict | None = None, *, post=False, code: str, refs: list) -> bytes:
        params = params or {}
        address = url + ("?" + urlencode(params) if params and not post else "")
        request = Request(address, data=urlencode(params).encode() if post else None,
                          headers={"User-Agent": "Mozilla/5.0", "Referer": NAV_DEFINITIONS[code]["url"]})
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
        provider = NAV_DEFINITIONS[code]["provider"]
        refs, result = [], []
        if provider == "jsfund":
            text = self.request(NAV_DEFINITIONS[code]["url"], code=code, refs=refs).decode("utf-8")
            result = parse_jsfund(text, code, calendar)
        elif provider == "efunds":
            page = self.request(NAV_DEFINITIONS[code]["url"], code=code, refs=refs).decode("utf-8")
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
        validate_nav_rows(result, code, calendar)
        return result, refs


def _staged_navs(path: Path, code: str, calendar: list[str], now: datetime, response_dir: Path):
    try:
        staged = json.loads(path.read_text())
        expected = staged.pop("content_digest")
        fetched = datetime.fromisoformat(staged["fetched_at"])
        if (digest(staged) != expected or staged["definition"] != NAV_DEFINITIONS[code]
            or staged["calendar"] != calendar or staged["nav_unit"] != "CNY_per_share"
            or fetched.tzinfo is None or fetched > now or fetched.date().isoformat() < calendar[-1]):
            raise ValueError("staged NAV binding mismatch")
        validate_nav_rows(staged["rows"], code, calendar)
        for ref in staged["responses"]:
            key = ref["response_sha256"]
            if not re.fullmatch(r"[a-f0-9]{64}", key) or hashlib.sha256((response_dir / f"{key}.raw").read_bytes()).hexdigest() != key:
                raise ValueError("staged response missing or changed")
        return staged["rows"], staged["responses"]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def refresh_issuer_navs(client, *, through: str, output: Path, sessions=61, now: datetime | None = None, repair=False) -> dict:
    now = now or datetime.now(timezone.utc)
    end = date.fromisoformat(through)
    if end >= now.astimezone(ZoneInfo("Asia/Shanghai")).date() or not 21 <= sessions <= 61:
        raise ValueError("only completed dates and 21–61 sessions are supported")
    calendar = sessions_2026(date(end.year, 1, 1), end)[-sessions:]
    if len(calendar) != sessions or calendar[-1] != through:
        raise ValueError("verified window ending at target required")
    raw = {"contract_version": NAV_VERSION, "definitions": NAV_DEFINITIONS, "nav_unit": "CNY_per_share",
           "requested_through": through, "fetched_at": now.isoformat(), "calendar": calendar,
           "calendar_source": CALENDAR_SOURCE, "calendar_version": CALENDAR_VERSION,
           "availability_basis": "first_observed_at_fetch_not_historical_PIT", "etf_navs": {}, "responses": []}
    failures, reused = [], 0
    for code in NAV_DEFINITIONS:
        try:
            stage_path = output / "staging" / f"{through}-{sessions}" / f"{code}.json"
            staged = _staged_navs(stage_path, code, calendar, now, output / "responses") if repair else None
            reusing = staged is not None
            if staged is not None:
                rows, refs = staged
                reused += 1
            else:
                rows, refs = client.get_navs(code, calendar)
            validate_nav_rows(rows, code, calendar)
            staged = {"definition": NAV_DEFINITIONS[code], "calendar": calendar, "nav_unit": "CNY_per_share",
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
              "complete_series": len(raw["etf_navs"]), "declared_series": len(NAV_DEFINITIONS)}
    previous, previous_rows = load_issuer_navs(output, now)
    if previous_rows and (previous["through"] > through or previous["through"] == through and len(previous["calendar"]) > sessions):
        report.update(status="failed", reason="would_regress_existing_window")
    if report["status"] == "complete":
        raw["content_digest"] = digest(raw)
        atomic_write_json(output / "snapshots" / f"{raw['content_digest']}.json", raw)
        atomic_write_json(output / "current.json", raw)
        report.update(snapshot_digest=raw["content_digest"], nav_observations=sum(map(len, raw["etf_navs"].values())))
    else:
        report["current_snapshot_preserved"] = True
    atomic_write_json(output / "last_attempt.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through", required=True)
    parser.add_argument("--sessions", type=int, default=61)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--repair", action="store_true", help="reuse integrity-checked complete series for this exact window")
    args = parser.parse_args()
    report = refresh_issuer_navs(IssuerNAVClient(args.output / "responses"), through=args.through, output=args.output, sessions=args.sessions, repair=args.repair)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
