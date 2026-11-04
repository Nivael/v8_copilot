"""Historical exchange report cross-sections; a single venue never becomes whole-market history."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from market_breadth import SOURCES, cross_section, st_name, validate_venue
from market_breadth_export import EXPORT_KIND, EXPORT_URL, export_params, parse_export
from market_calendar import CALENDAR_VERSION
from market_periods import recent_calendar_window
from settings import DATA_ROOT

VERSION = "exchange_breadth_history_raw_v1"
DAY_VERSION = "exchange_breadth_history_day_v1"
SCOPE = "SZSE_A_shares_daily_reports"
REQUIRED_VENUES = ["SSE", "SZSE"]
SUPPORTED_VENUES = ["SZSE"]
DEFAULT_OUTPUT = DATA_ROOT / "local_data/v8_copilot/market_risk/public_breadth_history"


def processor_digest():
    root = Path(__file__).parent
    return digest({name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                   for name in (Path(__file__).name, "market_breadth.py", "market_breadth_refresh.py", "market_breadth_export.py", "market_calendar.py", "market_periods.py", "canonical_json.py")})


PROCESSOR_DIGEST = processor_digest()


def _source_store(directory):
    return directory.parent / "public_breadth"


def _read_day(directory, key, day, now, *, check_raw=False):
    if not isinstance(key, str) or not re.fullmatch(r"[a-f0-9]{64}", key): raise ValueError("invalid daily key")
    raw = json.loads((directory / "days" / f"{key}.json").read_text())
    expected = raw.pop("content_digest")
    observed = datetime.fromisoformat(raw["fetched_at"])
    materialized = datetime.fromisoformat(raw["materialized_at"])
    if (digest(raw) != expected or expected != key or raw["contract_version"] != DAY_VERSION
        or raw["processor_digest"] != PROCESSOR_DIGEST or raw["venue"] != "SZSE" or raw["date"] != day
        or raw["source"] != SOURCES["SZSE"] or observed.tzinfo is None or materialized.tzinfo is None
        or not observed <= materialized <= now
        or observed.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat() < day):
        raise ValueError("daily binding mismatch")
    validate_venue("SZSE", raw["block"], day)
    refs = raw["responses"]
    pages = math.ceil(raw["block"]["reported_total"] / 10)
    exported = len(refs) == 3 and refs[-1].get("kind") == EXPORT_KIND
    if not exported and len(refs) != pages: raise ValueError("incomplete daily source pages")
    bodies = []
    for index, ref in enumerate(refs):
        page = (1 if index == 0 else pages) if exported else index + 1
        params = {"SHOWTYPE": "JSON", "CATALOGID": SOURCES["SZSE"]["catalog"], "TABKEY": "tab1",
                  "txtBeginDate": day, "txtEndDate": day, "PAGENO": page}
        is_export = exported and index == 2
        if is_export: params = export_params(day)
        stamp = datetime.fromisoformat(ref["observed_at"])
        if (ref["venue"] != "SZSE" or ref["url"] != (EXPORT_URL if is_export else SOURCES["SZSE"]["api_url"]) or ref["params"] != params
            or (ref.get("kind") is not None and not is_export)
            or stamp.tzinfo is None or stamp > observed or stamp.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat() < day
            or not re.fullmatch(r"[a-f0-9]{64}", ref["response_sha256"])):
            raise ValueError("daily source query does not match complete unfiltered report")
        if check_raw:
            body = (_source_store(directory) / "responses" / f"{ref['response_sha256']}.{'xlsx' if is_export else 'json'}").read_bytes()
            if hashlib.sha256(body).hexdigest() != ref["response_sha256"]: raise ValueError("source bytes changed")
            bodies.append(body)
    if check_raw and exported and parse_export(bodies[2], json.loads(bodies[0]), json.loads(bodies[1]), day) != raw["block"]:
        raise ValueError("normalized day disagrees with archived source export")
    if max(datetime.fromisoformat(ref["observed_at"]) for ref in refs) != observed:
        raise ValueError("source observation time changed during reprocessing")
    return raw


def load_breadth_history(directory: Path, now: datetime) -> dict:
    try:
        raw = json.loads((directory / "current.json").read_text())
        expected = raw.pop("content_digest")
        observed = datetime.fromisoformat(raw["fetched_at"])
        materialized = datetime.fromisoformat(raw["materialized_at"])
        window = recent_calendar_window(raw["through"])
        if (raw["contract_version"] != VERSION or digest(raw) != expected or raw["processor_digest"] != PROCESSOR_DIGEST
            or processor_digest() != PROCESSOR_DIGEST or raw["calendar_version"] != CALENDAR_VERSION
            or raw["scope"] != SCOPE or raw["venues"] != SUPPORTED_VENUES or raw["required_venues"] != REQUIRED_VENUES
            or raw["availability_basis"] != "first_observed_at_fetch_not_historical_PIT"
            or observed.tzinfo is None or materialized.tzinfo is None or not observed <= materialized <= now
            or raw["through"] >= now.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
            or window["availability"] != "defined" or raw["calendar"] != window["calendar"]
            or set(raw["daily_snapshots"]) != set(raw["calendar"])):
            raise ValueError("invalid historical source/window binding")
        points, source_times = [], []
        for day in raw["calendar"]:
            daily = _read_day(directory, raw["daily_snapshots"][day], day, materialized)
            source_times.append(datetime.fromisoformat(daily["fetched_at"]))
            block = daily["block"]
            points.append({"date": day, "source_rows": block["reported_total"], "excluded_b_shares": block["excluded_b_shares"],
                           "excluded_preferred_shares": len(block["excluded_preferred_codes"]), **cross_section(block["rows"]),
                           "st_name_group": cross_section([row for row in block["rows"] if st_name(row["security_name"])])})
        if max(source_times) != observed: raise ValueError("window source observation time mismatch")
        return {"availability": "observed", "scope": SCOPE, "venue": "SZSE", "label": "深交所历史收盘日表",
                "source_url": SOURCES["SZSE"]["url"], "start": raw["calendar"][0], "through": raw["through"],
                "fetched_at": raw["fetched_at"], "materialized_at": raw["materialized_at"], "content_digest": expected, "processor_digest": PROCESSOR_DIGEST,
                "observed_days": len(points), "expected_days": len(raw["calendar"]), "points": points,
                "complete_market_history": False, "covered_venues": SUPPORTED_VENUES, "missing_venues": ["SSE"],
                "observation_count": sum(point["listed_source_stocks"] for point in points),
                "note": "仅深市历史日表中的普通A股；不含沪市、北交所、B股和优先股。ST名称组按各日简称分组，不是历史法定名单或固定组合指数。停牌/无成交单列，首次抓取不冒充历史当时可见。"}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
        return {"availability": "missing" if not (directory / "current.json").exists() else "invalid", "points": [],
                "complete_market_history": False, "covered_venues": [], "missing_venues": REQUIRED_VENUES}


def refresh_breadth_history(client, *, through, output: Path, repair=False, now=None, progress=None):
    def clock(): return now or datetime.now(timezone.utc)
    start = clock()
    window = recent_calendar_window(through)
    if (window["availability"] != "defined" or date.fromisoformat(through) >= start.astimezone(ZoneInfo("Asia/Shanghai")).date()
        or processor_digest() != PROCESSOR_DIGEST):
        raise ValueError("verified completed calendar window and loaded processor required")
    old = load_breadth_history(output, start)
    if old.get("through", "") > through: raise ValueError("older history window cannot replace current")
    expected = window["calendar"]
    raw = {"contract_version": VERSION, "processor_digest": PROCESSOR_DIGEST, "calendar_version": CALENDAR_VERSION,
           "scope": SCOPE, "venues": SUPPORTED_VENUES, "required_venues": REQUIRED_VENUES,
           "availability_basis": "first_observed_at_fetch_not_historical_PIT", "through": through, "fetched_at": start.isoformat(),
           "calendar": expected, "daily_snapshots": {}}
    report = {"status": "collecting", "process_id": os.getpid(), "started_at": start.isoformat(), "requested_through": through,
              "start": expected[0], "expected_days": len(expected), "completed_days": 0, "reused_days": 0,
              "scope": SCOPE, "complete_market_history": False}
    source_times = []
    for day in expected:
        report.update(current_date=day, recorded_at=clock().isoformat())
        atomic_write_json(output / "last_attempt.json", report)
        if progress: progress(dict(report))
        try:
            reused = False
            if repair:
                try:
                    key = json.loads((output / "staging" / f"{day}.json").read_text())["content_digest"]
                    daily = _read_day(output, key, day, clock(), check_raw=True)
                    reused = True
                except (OSError, ValueError, KeyError, TypeError, AttributeError): pass
            if not reused:
                block, refs = client.get_venue("SZSE", day)
                validate_venue("SZSE", block, day)
                observed_at = max(datetime.fromisoformat(ref["observed_at"]) for ref in refs).isoformat()
                daily = {"contract_version": DAY_VERSION, "processor_digest": PROCESSOR_DIGEST, "venue": "SZSE",
                         "source": SOURCES["SZSE"], "date": day, "fetched_at": observed_at, "materialized_at": clock().isoformat(),
                         "block": block, "responses": refs}
                key = digest(daily)
                atomic_write_json(output / "days" / f"{key}.json", {**daily, "content_digest": key})
                _read_day(output, key, day, clock(), check_raw=True)
                atomic_write_json(output / "staging" / f"{day}.json", {"content_digest": key})
            raw["daily_snapshots"][day] = key
            source_times.append(datetime.fromisoformat(daily["fetched_at"]))
            report.update(completed_days=len(raw["daily_snapshots"]), reused_days=report["reused_days"] + int(reused))
        except Exception as exc:
            report.update(status="failed", error_type=type(exc).__name__, current_snapshot_preserved=True,
                          completed_at=clock().isoformat(), recorded_at=clock().isoformat())
            atomic_write_json(output / "last_attempt.json", report)
            return report
    if processor_digest() != PROCESSOR_DIGEST:
        report.update(status="failed", error_type="ProcessorChanged", current_snapshot_preserved=True)
    else:
        raw["fetched_at"] = max(source_times).isoformat()
        raw["materialized_at"] = clock().isoformat()
        raw["content_digest"] = digest(raw)
        atomic_write_json(output / "snapshots" / f"{raw['content_digest']}.json", raw)
        atomic_write_json(output / "current.json", raw)
        report.update(status="complete", snapshot_digest=raw["content_digest"])
    report.update(completed_at=clock().isoformat(), recorded_at=clock().isoformat())
    atomic_write_json(output / "last_attempt.json", report)
    return report


def main():
    from market_breadth_export import HistoricalExportClient
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--repair", action="store_true")
    args = parser.parse_args()
    log = lambda row: print(json.dumps(row, ensure_ascii=False), flush=True)
    client = HistoricalExportClient(_source_store(args.output), repair=args.repair, progress=log)
    report = refresh_breadth_history(client, through=args.through, output=args.output, repair=args.repair, progress=log)
    log(report)
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__": raise SystemExit(main())
