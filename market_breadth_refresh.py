"""Explicit official closing breadth collection; GET readers never call this module."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
import hashlib
from html import unescape
import json
import math
from pathlib import Path
import re
from threading import Lock
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from market_breadth import SOURCES, SSE_SELECT, VERSION, load_public_breadth, validate_venue
from market_calendar import CALENDAR_SOURCE, CALENDAR_VERSION, sessions_2026
from settings import DATA_ROOT

DEFAULT_OUTPUT = DATA_ROOT / "local_data/v8_copilot/market_risk/public_breadth"


def number(value) -> float | None:
    if isinstance(value, bool):
        raise ValueError("boolean quote value")
    text = str(value).strip()
    if text in ("--", "", "None"):
        return None
    if not re.fullmatch(r"-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?", text):
        raise ValueError("invalid numeric quote format")
    result = float(text.replace(",", ""))
    if not math.isfinite(result):
        raise ValueError("nonfinite quote")
    return result


def quote(code: str, name: str, through: str, last, previous, change, volume, amount, *, venue: str) -> dict:
    last, previous, change, volume, amount = [number(value) for value in (last, previous, change, volume, amount)]
    if volume is None or amount is None or volume < 0 or amount < 0 or (volume == 0) != (amount == 0):
        raise ValueError("invalid trading activity")
    active = volume > 0
    if active and (last is None or previous is None or min(last, previous) <= 0):
        raise ValueError("trading stock lacks close/reference price")
    # Official percentage columns are rounded; retain them, but classify direction using the prices.
    # Otherwise a small nonzero move can be miscounted as flat, or -4.998% as a 5% fall.
    calculated = (last / previous - 1) * 100 if active else None
    return {"ts_code": code + (".SH" if venue == "SSE" else ".SZ"), "security_name": unescape(name).strip(),
            "trade_date": through, "last": last, "prev_close": previous, "pct_chg": calculated,
            "reported_pct_chg": change,
            "volume": volume, "amount": amount, "is_trading": active}


def parse_sse(pages: list[dict], through: str, page_size=500) -> dict:
    total, stamp, rows, excluded, seen = None, None, [], 0, set()
    for page, payload in enumerate(pages):
        count, time = payload["total"], payload["time"]
        if (str(payload["date"]) != through.replace("-", "") or isinstance(time, bool) or not isinstance(time, int)
            or not 150000 <= time <= 235959 or total is not None and count != total or stamp is not None and time != stamp
            or isinstance(count, bool) or not isinstance(count, int) or not 0 < count < 10_000
            or payload["begin"] != page * page_size or payload["end"] != min((page + 1) * page_size, count)
            or len(payload["list"]) != payload["end"] - payload["begin"]):
            raise ValueError("SSE date, closing time, total or page boundary mismatch")
        total, stamp = count, time
        for values in payload["list"]:
            if len(values) != 10:
                raise ValueError("SSE column count changed")
            code, name, last, previous, change, volume, amount, phase, subtype, _ = values
            if not re.fullmatch(r"\d{6}", code) or code in seen:
                raise ValueError("duplicate or invalid SSE code")
            seen.add(code)
            if subtype == "BSH" and code.startswith("900"):
                excluded += 1
                continue
            if subtype not in ("ASH", "KSH"):
                raise ValueError("unknown SSE equity type")
            row = quote(code, name, through, last, previous, change, volume, amount, venue="SSE")
            if str(phase).strip().startswith("P") and row["is_trading"]:
                raise ValueError("suspended SSE stock reports trades")
            rows.append(row)
    if total is None or len(seen) != total or len(pages) != math.ceil(total / page_size):
        raise ValueError("incomplete SSE pagination")
    block = {"reported_total": total, "received_total": len(seen), "excluded_b_shares": excluded,
             "excluded_preferred_codes": [],
             "amount_unit": "CNY", "volume_unit": "shares", "quote_time": stamp, "rows": rows}
    validate_venue("SSE", block, through)
    return block


def parse_szse(pages: list[list[dict]], through: str) -> dict:
    total, page_size, rows, excluded, seen, preferred = None, None, [], 0, set(), []
    for page, payload in enumerate(pages, 1):
        if not isinstance(payload, list) or len(payload) != 1:
            raise ValueError("unexpected SZSE report blocks")
        block = payload[0]
        meta = block["metadata"]
        count, size = meta["recordcount"], meta["pagesize"]
        if (meta["catalogid"] != SOURCES["SZSE"]["catalog"] or meta["tabkey"] != "tab1"
            or count <= 0 or not 1 <= size <= 500 or meta["pageno"] != page
            or meta["pagecount"] != len(pages) or meta["pagecount"] != math.ceil(count / size)
            or total is not None and count != total or page_size is not None and size != page_size
            or len(block["data"]) != min(size, count - (page - 1) * size)
            or meta["cols"]["sdf"] != "涨跌幅<br>（%）" or meta["cols"]["cjgs"] != "成交量<br>(万股)"
            or meta["cols"]["cjje"] != "成交金额<br>(万元)"
            or any(meta["cols"][key] != label for key, label in {"jyrq": "交易日期", "zqdm": "证券代码", "zqjc": "证券简称", "qss": "前收", "ss": "今收"}.items())):
            raise ValueError("SZSE catalog, unit, schema, total or pagination mismatch")
        total, page_size = count, size
        for values in block["data"]:
            code = values["zqdm"]
            if not re.fullmatch(r"(?:[023]\d{5}|14\d{4})", code) or code in seen or values["jyrq"] != through:
                raise ValueError("wrong, duplicate or undated SZSE security")
            seen.add(code)
            if code.startswith("14"):
                definition = SOURCES["SZSE"]["preferred_share_exclusions"].get(code)
                if not definition or re.sub(r"\s+", "", unescape(values["zqjc"])) != definition["name"]:
                    raise ValueError("unclassified preferred-share identity")
                preferred.append(code)
                continue
            if code.startswith("2"):
                excluded += 1
                continue
            volume, amount = number(values["cjgs"]), number(values["cjje"])
            rows.append(quote(code, values["zqjc"], through, values["ss"], values["qss"], values["sdf"],
                              volume * 10000 if volume is not None else None,
                              amount * 10000 if amount is not None else None, venue="SZSE"))
    if total is None or len(seen) != total:
        raise ValueError("incomplete SZSE pagination")
    block = {"reported_total": total, "received_total": len(seen), "excluded_b_shares": excluded,
             "excluded_preferred_codes": preferred,
             "amount_unit": "CNY", "volume_unit": "shares", "rows": rows}
    validate_venue("SZSE", block, through)
    return block


class PublicBreadthClient:
    def __init__(self, output: Path, *, repair=False, progress=None):
        self.output, self.repair, self.progress = output, repair, progress
        self._request_lock, self._next_request = Lock(), 0.0

    def request(self, venue: str, params: dict, *, cache=False) -> tuple[object, dict]:
        source = SOURCES[venue]
        request_key = digest({"url": source["api_url"], "params": params})
        cache_path = self.output / "cache" / f"{request_key}.json"
        if self.repair and cache:
            try:
                ref = json.loads(cache_path.read_text())
                observed = datetime.fromisoformat(ref["observed_at"])
                if (ref["url"] != source["api_url"] or ref["params"] != params or observed.tzinfo is None
                    or observed > datetime.now(timezone.utc) or not re.fullmatch(r"[a-f0-9]{64}", ref["response_sha256"])):
                    raise ValueError("cached request mismatch")
                raw = (self.output / "responses" / f"{ref['response_sha256']}.json").read_bytes()
                if hashlib.sha256(raw).hexdigest() != ref["response_sha256"]:
                    raise ValueError("cached response changed")
                return json.loads(raw), ref
            except (OSError, ValueError, KeyError, TypeError):
                pass
        url = source["api_url"] + "?" + urlencode(params)
        request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": source["url"]})
        for attempt in range(3):
            try:
                with self._request_lock:
                    scheduled = max(time.monotonic(), self._next_request)
                    self._next_request = scheduled + .4
                delay = scheduled - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                with urlopen(request, timeout=20) as response:
                    raw = response.read(4_000_001)
                    length = response.headers.get("Content-Length")
                if len(raw) > 4_000_000 or length is not None and len(raw) != int(length):
                    raise ValueError("incomplete or oversized response")
                payload = json.loads(raw)
                break
            except (OSError, TimeoutError):
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
        key = hashlib.sha256(raw).hexdigest()
        response_dir = self.output / "responses"
        response_dir.mkdir(parents=True, exist_ok=True)
        (response_dir / f"{key}.json").write_bytes(raw)
        ref = {"venue": venue, "url": source["api_url"], "params": params, "response_sha256": key,
               "observed_at": datetime.now(timezone.utc).isoformat(), "bytes": len(raw)}
        if cache:
            atomic_write_json(cache_path, ref)
        return payload, ref

    def get_venue(self, venue: str, through: str) -> tuple[dict, list[dict]]:
        pages, refs = [], []
        if venue == "SSE":
            page, count = 0, 1
            while page < count:
                payload, ref = self.request("SSE", {"select": SSE_SELECT, "begin": page * 500, "end": (page + 1) * 500})
                count = math.ceil(payload["total"] / 500)
                if not 1 <= count <= 20:
                    raise ValueError("unexpected SSE scope")
                pages.append(payload)
                refs.append(ref)
                page += 1
            return parse_sse(pages, through), refs
        params = {"SHOWTYPE": "JSON", "CATALOGID": SOURCES["SZSE"]["catalog"], "TABKEY": "tab1",
                  "txtBeginDate": through, "txtEndDate": through}
        def fetch(page):
            return self.request("SZSE", {**params, "PAGENO": page}, cache=True)
        payload, ref = fetch(1)
        count = int(payload[0]["metadata"]["pagecount"])
        if not 1 <= count <= 700:
            raise ValueError("unexpected SZSE scope")
        pages.append(payload)
        refs.append(ref)
        with ThreadPoolExecutor(max_workers=2) as executor:
            for start in range(2, count + 1, 2):
                for payload, ref in executor.map(fetch, range(start, min(start + 2, count + 1))):
                    pages.append(payload)
                    refs.append(ref)
                if self.progress and (len(pages) % 40 == 1 or len(pages) == count):
                    self.progress({"venue": "SZSE", "pages_received": len(pages), "declared_pages": count})
        return parse_szse(pages, through), refs


def refresh_public_breadth(client, *, through: str, output: Path, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    end = date.fromisoformat(through)
    if end >= now.astimezone(ZoneInfo("Asia/Shanghai")).date() or sessions_2026(end, end) != [through]:
        raise ValueError("only a verified completed trading date is supported")
    raw = {"contract_version": VERSION, "sources": SOURCES, "requested_through": through, "fetched_at": now.isoformat(),
           "scope": "SSE_SZSE_A_shares", "calendar_source": CALENDAR_SOURCE, "calendar_version": CALENDAR_VERSION,
           "availability_basis": "first_observed_at_fetch_not_historical_PIT", "venues": {}, "responses": []}
    failures = []
    for venue in SOURCES:
        try:
            block, refs = client.get_venue(venue, through)
            validate_venue(venue, block, through)
            raw["venues"][venue] = block
            raw["responses"].extend(refs)
        except Exception as exc:
            failures.append({"venue": venue, "error_type": type(exc).__name__})
    report = {"status": "failed" if failures else "complete", "requested_through": through, "failures": failures,
              "complete_venues": len(raw["venues"]), "declared_venues": 2, "completed_at": datetime.now(timezone.utc).isoformat()}
    previous, _ = load_public_breadth(output, now)
    if previous.get("through", "") > through:
        report.update(status="failed", reason="would_regress_existing_date")
    if report["status"] == "complete":
        raw["content_digest"] = digest(raw)
        atomic_write_json(output / "snapshots" / f"{raw['content_digest']}.json", raw)
        atomic_write_json(output / "current.json", raw)
        report.update(snapshot_digest=raw["content_digest"], source_rows=sum(block["reported_total"] for block in raw["venues"].values()),
                      a_share_rows=sum(len(block["rows"]) for block in raw["venues"].values()))
    else:
        report["current_snapshot_preserved"] = True
    atomic_write_json(output / "last_attempt.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--repair", action="store_true", help="reuse hash-checked SZSE pages for this exact query")
    args = parser.parse_args()
    client = PublicBreadthClient(args.output, repair=args.repair, progress=lambda row: print(json.dumps(row), flush=True))
    report = refresh_public_breadth(client, through=args.through, output=args.output)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
