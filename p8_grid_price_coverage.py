"""Outcome-blind, bounded suspension evidence for P8C price windows; no DB writes."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from data_refresh import TushareHttpClient, atomic_write_json
from p8_research import canonical_json


def sha(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def full_day(kind, timing):
    # Legacy MarketActivityFact serialized provider None as the string "None".
    return kind == "S" and timing in (None, "", "None")


def verified_suspensions(facts, evidence=None):
    fm = {(f.symbol, f.trade_date): f for f in facts}
    result = {key for key, f in fm.items() if full_day(getattr(f, "suspend_type", ""),
              getattr(f, "suspend_timing", "")) and getattr(f, "close", None) is None}
    for item in (evidence or {}).get("days", []):
        if item.get("source") != "tushare:suspend_d":
            raise ValueError("unsupported suspension source")
        raw = item["rows"]
        if sha(raw) != item["rows_digest"]:
            raise ValueError("suspension evidence digest mismatch")
        day = item["trade_date"]
        grouped = defaultdict(list)
        for r in raw:
            if r.get("trade_date") != day.replace("-", ""):
                raise ValueError("suspension evidence date mismatch")
            grouped[str(r["ts_code"]).split(".")[0]].append(r)
        for symbol, rows in grouped.items():
            key = (symbol, day)
            if all(full_day(r.get("suspend_type"), r.get("suspend_timing")) for r in rows):
                if key not in fm or getattr(fm[key], "close", None) is None:
                    result.add(key)
            else:
                result.discard(key)  # Conflicting resume/intraday rows never excuse a gap.
    return result


def gap_plan(prices, calendar, memberships, facts, window):
    """Include warm-up grid dates too: preceding states affect first-entry detection."""
    known = verified_suspensions(facts)
    membership_indices = defaultdict(list)
    for i, d in enumerate(calendar):
        for s in memberships.get(d, set()):
            membership_indices[s].append(i)
    targets = defaultdict(set)
    for s, indices in membership_indices.items():
        p = dict(prices.get(s, []))
        needed = set()
        for i in indices:
            if i >= window-1:
                needed.update(range(i-window+1, i+1))
        for j in needed:
            d = calendar[j]
            if d not in p and (s, d) not in known:
                targets[d].add(s)
    body = dict(version="p8c_suspension_plan_v1", outcomes_read=False,
                targets={d: sorted(v) for d, v in sorted(targets.items())},
                input_digest=sha(dict(prices=prices, membership={d: sorted(v) for d, v in memberships.items()},
                                      local_suspensions=sorted(known), calendar=calendar, window=window)))
    return dict(body, plan_digest=sha(body), request_upper_bound=len(targets),
                missing_pairs=sum(map(len, targets.values())))


def acquire(plan, directory, client, delay=1.3):
    """One request per frozen date, resumable cache; never infer S from absence."""
    directory.mkdir(parents=True, exist_ok=True)
    days, failures = [], {}
    def fetch(day):
        path = directory / f"{day}.json"
        if path.exists():
            item = json.loads(path.read_text())
        else:
            try:
                rows = client.fetch_suspend_daily(trade_date=day)
                if len(rows) >= 5000:
                    raise ValueError("possibly truncated suspension response")
                if any(r.get("trade_date") != day.replace("-", "") for r in rows):
                    raise ValueError("provider response date mismatch")
                # Keep the full date response so future scoped replays share the same evidence.
                item = dict(trade_date=day, rows=rows, rows_digest=sha(rows),
                            source="tushare:suspend_d", fetched_at=datetime.now(timezone.utc).isoformat())
                atomic_write_json(path, item)
                time.sleep(delay)
            except Exception as exc:
                time.sleep(delay)
                message = str(exc).lower()
                reason = ("provider_rate_limit" if any(x in message for x in ("频", "每分钟", "rate limit"))
                          else "provider_permission" if any(x in message for x in ("权限", "积分", "permission"))
                          else type(exc).__name__)
                return day, None, reason  # Never expose token-bearing errors.
        if item["trade_date"] != day or sha(item["rows"]) != item["rows_digest"]:
            raise ValueError("cached evidence mismatch")
        return day, item, None
    with ThreadPoolExecutor(max_workers=2) as pool:
        for n, (day, item, error) in enumerate(pool.map(fetch, plan["targets"]), 1):
            if error:
                failures[day] = error
            else:
                days.append(item)
            if n % 50 == 0:
                print(json.dumps(dict(completed=n, total=len(plan["targets"]), failures=len(failures))), flush=True)
    return dict(version="p8c_suspension_evidence_v1", plan_digest=plan["plan_digest"],
                outcomes_read=False, days=days, failures=failures,
                status="complete" if not failures else "partial")


def main():
    from market_activity import MarketActivityRepository
    from p8_backtest_v2 import _calendar_membership
    from p8_prices import qfq_series
    from p8_qfq_backfill import _load_env
    from settings import DATA_ROOT, MARKET_ACTIVITY_DB, MARKET_CONTEXT_DB, P8_QFQ_DB
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--allow-provider", action="store_true")
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    cfg = json.loads(Path(__file__).with_name("p8_grid_config.json").read_text())
    cal, members = _calendar_membership(MARKET_CONTEXT_DB, "2021-03-17", cfg["signal_through"])
    prices = qfq_series(DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3",
                        overlay_database=P8_QFQ_DB, start=cal[0], through=cal[-1])
    facts = MarketActivityRepository(MARKET_ACTIVITY_DB).latest_facts(start_date=cal[0], through=cal[-1])
    plan = gap_plan(prices, cal, members, facts, cfg["windows"]["position"])
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.allow_provider:
        atomic_write_json(args.output / "plan.json", plan)
        print(json.dumps({k: v for k, v in plan.items() if k != "targets"}))
        return
    if not args.plan or json.loads(args.plan.read_text()) != plan:
        raise ValueError("need unchanged outcome-blind plan before provider requests")
    _load_env(args.env_file)
    evidence = acquire(plan, args.output / "dates", TushareHttpClient())
    atomic_write_json(args.output / "evidence.json", evidence)
    known = verified_suspensions(facts, evidence)
    unresolved = {d: [s for s in syms if (s, d) not in known] for d, syms in plan["targets"].items()}
    atomic_write_json(args.output / "unresolved.json", {d: v for d, v in unresolved.items() if v})
    print(json.dumps(dict(status=evidence["status"], dates=len(evidence["days"]),
                          unresolved_pairs=sum(map(len, unresolved.values())))))


if __name__ == "__main__":
    main()
