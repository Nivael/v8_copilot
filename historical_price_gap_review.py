"""Classify fixed historical quote gaps without filling prices or estimating returns.

Inputs are already retained provider archives. A provider suspension is a source
claim, not independent exchange verification. Codes are joined exactly; aliases,
absent rows and intraday pauses never manufacture a daily close or zero return.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from math import isfinite
import re

from canonical_json import digest
from p8_grid_price_coverage import full_day, sha as suspension_digest

VERSION = "historical_price_gap_review_v1"
ACTIVITY_SOURCE = "tushare:daily+daily_basic+suspend_d+stk_limit"
QUOTE_SOURCE = "tushare:daily+adj_factor:qfq"


def _key(symbol, day):
    if not isinstance(symbol, str) or not re.fullmatch(r"\d{6}", symbol):
        raise ValueError("expected exact six-digit symbol")
    if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
        raise ValueError("expected ISO trade date")
    return symbol, day


def _clock(value):
    # Legacy quote timestamps are naive. Preserve them without inventing a zone.
    if not isinstance(value, str) or not value.strip():
        raise ValueError("missing original source observation clock")
    datetime.fromisoformat(value)
    return value


def _positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value > 0


def classify_gaps(gaps, *, quotes, snapshots, suspension_days):
    """Validate archives, then conservatively classify each exact symbol/day.

    Each snapshot is ``{metadata: SQLite snapshot row, facts: full payloads}``.
    Full content hashes are re-derived before facts are used. Revisions with
    contrary trading/paused states are retained as conflicts, never last-write wins.
    """
    targets = {}
    for gap in gaps:
        key = _key(gap["symbol"], gap["trade_date"])
        if key in targets:
            raise ValueError("duplicate target member day")
        targets[key] = gap
    evidence = defaultdict(list)
    quote_refs, snapshot_refs, day_refs = [], [], []
    quote_keys = set()
    for quote in quotes:
        key = _key(quote["symbol"], quote["trade_date"])
        if quote.get("adjust") != "qfq" or quote.get("source") != QUOTE_SOURCE:
            raise ValueError("unsupported alternate quote source or adjustment")
        if key in quote_keys:
            raise ValueError("duplicate alternate quote identity")
        quote_keys.add(key)
        _clock(quote["fetched_at"])
        quote_refs.append(quote)
        if key in targets:
            evidence[key].append({"kind": "alternate_qfq_quote", "positive_close": _positive(quote.get("close")),
                                  "source_row": quote, "source_row_digest": digest(quote)})
    snapshot_ids = set()
    for snapshot in snapshots:
        meta, facts = snapshot["metadata"], snapshot["facts"]
        day = meta["trade_date"]
        _clock(meta["fetched_at"])
        if meta["contract_version"] != "market_activity_v1":
            raise ValueError("unsupported activity archive version")
        if meta["snapshot_id"] in snapshot_ids:
            raise ValueError("duplicate activity snapshot")
        snapshot_ids.add(meta["snapshot_id"])
        ordered = sorted(facts, key=lambda fact: fact["symbol"])
        actual = digest({"contract_version": meta["contract_version"], "trade_date": day, "facts": ordered})
        if meta["content_digest"] != actual or meta["snapshot_id"] != "MAS-" + actual[:20].upper():
            raise ValueError("activity snapshot content mismatch")
        if len(facts) != meta["row_count"] or len(facts) != meta["membership_count"]:
            raise ValueError("activity snapshot row count mismatch")
        keys = set()
        for fact in ordered:
            key = _key(fact["symbol"], fact["trade_date"])
            if key in keys or key[1] != day:
                raise ValueError("activity identity/date mismatch")
            keys.add(key)
            if fact.get("source") != ACTIVITY_SOURCE or str(fact.get("ts_code", "")).split(".")[0] != key[0]:
                raise ValueError("activity source/code mismatch")
            if key not in targets:
                continue
            is_full = full_day(fact.get("suspend_type"), fact.get("suspend_timing")) and fact.get("close") is None and fact.get("suspension_status") == "suspended"
            contrary = (fact.get("suspend_type") == "R" or
                        (fact.get("suspend_type") == "S" and not full_day(fact.get("suspend_type"), fact.get("suspend_timing"))) or
                        fact.get("suspension_status") == "trading" or _positive(fact.get("close")))
            evidence[key].append({"kind": "activity_fact", "full_day_suspension": is_full,
                                  "contrary_to_full_day": contrary, "snapshot_id": meta["snapshot_id"],
                                  "source_state_conflict": full_day(fact.get("suspend_type"), fact.get("suspend_timing")) and contrary,
                                  "snapshot_digest": actual, "fetched_at": meta["fetched_at"],
                                  "source_fact": fact, "source_fact_digest": digest(fact)})
        snapshot_refs.append({**meta, "metadata_digest": digest(meta)})
    dates = set()
    for day in suspension_days:
        trading_day, rows = day["trade_date"], day["rows"]
        if trading_day in dates:
            raise ValueError("duplicate suspension day")
        dates.add(trading_day)
        _clock(day["fetched_at"])
        if day.get("source") != "tushare:suspend_d" or suspension_digest(rows) != day["rows_digest"]:
            raise ValueError("suspension source/content mismatch")
        grouped = defaultdict(list)
        for row in rows:
            if row.get("trade_date") != trading_day.replace("-", ""):
                raise ValueError("suspension raw date mismatch")
            code = row.get("ts_code", "")
            if not re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", code):
                raise ValueError("invalid suspension provider code")
            grouped[_key(code.split(".")[0], trading_day)].append(row)
        for key, group in grouped.items():
            if key in targets:
                evidence[key].append({"kind": "raw_suspend_d", "full_day_suspension": all(full_day(r.get("suspend_type"), r.get("suspend_timing")) for r in group),
                                      "contrary_to_full_day": any(not full_day(r.get("suspend_type"), r.get("suspend_timing")) for r in group),
                                      "source_state_conflict": any(full_day(r.get("suspend_type"), r.get("suspend_timing")) for r in group) and any(not full_day(r.get("suspend_type"), r.get("suspend_timing")) for r in group),
                                      "rows_digest": day["rows_digest"], "source_rows": group, "fetched_at": day["fetched_at"]})
        day_refs.append({k: v for k, v in day.items() if k != "rows"})
    result = []
    for key, target in sorted(targets.items()):
        refs = evidence[key]
        positive = any(r.get("positive_close") for r in refs)
        suspended = any(r.get("full_day_suspension") for r in refs)
        contrary = any(r.get("contrary_to_full_day") for r in refs)
        status = ("conflicting_source_states" if any(r.get("source_state_conflict") for r in refs) or suspended and (positive or contrary) else
                  "alternate_archive_quote" if positive else
                  "provider_full_day_suspension" if suspended else "unresolved")
        result.append({**target, "classification": status, "evidence": refs})
    counts = Counter(row["classification"] for row in result)
    years = {}
    for year in sorted({key[1][:4] for key in targets}):
        years[year] = dict(Counter(row["classification"] for row in result if row["trade_date"].startswith(year)))
    body = {"version": VERSION, "rows": result, "counts": dict(counts), "years": years,
            "source_bindings": {"target_rows_digest": digest(gaps), "alternate_quote_rows_digest": digest(quote_refs),
                                "alternate_quote_rows": len(quote_refs), "activity_snapshots": snapshot_refs,
                                "suspension_days": day_refs},
            "boundaries": {"exact_code_join_only": True, "independent_exchange_suspension_verification": False,
                           "alternate_provider_not_independent": True, "prices_filled_or_spliced": False,
                           "zero_returns_inferred": False, "full_population_certified": False,
                           "historical_information_availability_verified": False,
                           "corporate_actions_or_adjustment_vintages_verified": False,
                           "causal_or_strategy_estimates": False}}
    return {**body, "content_digest": digest(body)}
