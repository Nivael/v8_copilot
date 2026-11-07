"""Read historical activity with separately bound corrections; never write SQLite.

Original snapshot IDs continue to describe original bytes. Effective facts belong
to a new reading manifest, so a correction cannot masquerade as the old source.
"""
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from math import isfinite
from pathlib import Path
import re
import sqlite3
import unicodedata

from canonical_json import digest
from historical_code_gap_review import verified_code_identity, _archive_after_switch
from market_activity import MarketActivityFact
from p8_grid_price_coverage import full_day, sha as suspension_digest

REGISTRY_VERSION = "activity_reading_corrections_v1"
READING_VERSION = "corrected_activity_reading_v1"
NOTICE_URL = "https://www.bse.cn/disclosure/2025/2025-09-12/a998a306557c4ad48d542b59d71cd0f0.pdf"
SHA = re.compile(r"[a-f0-9]{64}")


def registry_path(database):
    return Path(database).parent / "activity_reading_corrections/current.json"


def _clock(value):
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None or stamp > datetime.now(timezone.utc):
        raise ValueError("invalid correction observation clock")
    return stamp


def _asset(root, ref):
    name = ref.get("asset", "")
    if not re.fullmatch(r"assets/[a-f0-9]{64}\.(html|pdf)", name):
        raise ValueError("unregistered correction asset")
    path = root / name
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("correction asset cannot be a mutable link")
    raw = path.read_bytes()
    if not 0 < len(raw) <= 2_000_000 or len(raw) != ref["bytes"] or sha256(raw).hexdigest() != ref["sha256"]:
        raise ValueError("correction asset bytes changed")
    if Path(name).stem != ref["sha256"]:
        raise ValueError("correction asset name changed")
    _clock(ref["fetched_at"])
    return raw


def _notice_text(raw):
    from pypdf import PdfReader
    return "".join(page.extract_text() or "" for page in PdfReader(BytesIO(raw)).pages)


def verified_basis(value, root):
    sources = value["sources"]
    if set(sources) != {"mapping", "switch", "notice"}:
        raise ValueError("incomplete correction sources")
    mapping = verified_code_identity(old_codes=["839680"],
        mapping_html=_asset(root, sources["mapping"]), mapping_ref=sources["mapping"],
        switch_html=_asset(root, sources["switch"]), switch_ref=sources["switch"])["839680"]
    ref = sources["notice"]
    if ref["url"] != NOTICE_URL or ref["response_url"] != NOTICE_URL or ref["published_on"] != "2025-09-12":
        raise ValueError("suspension notice identity changed")
    raw = _asset(root, ref)
    text = re.sub(r"\s+", "", unicodedata.normalize("NFKC", _notice_text(raw)))
    if sha256(text.encode()).hexdigest() != ref["normalized_text_sha256"] or not all(
            part in text for part in ("839680", "深圳市广道数字技术股份有限公司", "2025年9月12日", "2025年9月15日", "起停牌")):
        raise ValueError("suspension notice content changed")
    days = {}
    for item in value["provider_days"]:
        day = item["trade_date"]
        if day in days or not "2025-09-15" <= day <= "2025-09-30":
            raise ValueError("duplicate or out-of-profile suspension day")
        if date.fromisoformat(day).isoformat() != day or item["source"] != "tushare:suspend_d" or suspension_digest(item["rows"]) != item["rows_digest"]:
            raise ValueError("suspension source changed")
        _archive_after_switch(item["fetched_at"])
        _clock(item["fetched_at"])
        if any(r.get("trade_date") != day.replace("-", "") for r in item["rows"]):
            raise ValueError("suspension raw date changed")
        matched = [r for r in item["rows"] if r.get("ts_code") == mapping["provider_code"] + ".BJ"]
        if not matched or not all(full_day(r.get("suspend_type"), r.get("suspend_timing")) for r in matched):
            raise ValueError("no uncontradicted full-day suspension evidence")
        days[day] = item
    return mapping, days


def validate_registry(value, root):
    if (set(value) != {"version", "created_at", "basis_study", "sources", "provider_days", "entries", "content_digest"}
            or value["version"] != REGISTRY_VERSION or digest({k: v for k, v in value.items() if k != "content_digest"}) != value["content_digest"]):
        raise ValueError("activity correction registry changed")
    clock = _clock(value["created_at"])
    if not re.fullmatch(r"RUN-[A-F0-9]{24}", value["basis_study"]):
        raise ValueError("invalid source-study reference")
    mapping, days = verified_basis(value, root)
    if any(_clock(ref["fetched_at"]) > clock for ref in value["sources"].values()):
        raise ValueError("correction predates its evidence")
    if any(_clock(item["fetched_at"]) > clock for item in value["provider_days"]):
        raise ValueError("correction predates its daily suspension observations")
    seen = set()
    fields = {"symbol", "trade_date", "snapshot_id", "snapshot_digest", "snapshot_metadata_digest", "old_fact_digest", "provider_day_digest", "entry_id"}
    for entry in value["entries"]:
        if set(entry) != fields or entry["symbol"] != "839680" or entry["trade_date"] not in days:
            raise ValueError("correction subject or date not evidenced")
        key = entry["symbol"], entry["trade_date"]
        if key in seen: raise ValueError("duplicate activity correction")
        seen.add(key)
        if not mapping["listing_date"] <= entry["trade_date"] < mapping["exchange_code_effective_on"]:
            raise ValueError("historic trading identity changed")
        if any(not isinstance(entry[k], str) or not SHA.fullmatch(entry[k]) for k in ("snapshot_digest", "snapshot_metadata_digest", "old_fact_digest", "provider_day_digest")):
            raise ValueError("invalid correction source digest")
        if (entry["snapshot_id"] != "MAS-" + entry["snapshot_digest"][:20].upper()
                or entry["provider_day_digest"] != digest(days[entry["trade_date"]])
                or entry["entry_id"] != "ASC-" + digest({k: v for k, v in entry.items() if k != "entry_id"})[:24].upper()):
            raise ValueError("correction entry binding changed")
    if not seen: raise ValueError("empty correction registry")
    return value


def _window(start, through):
    left, right = date.fromisoformat(start), date.fromisoformat(through)
    if left.isoformat() != start or right.isoformat() != through or not 0 <= (right - left).days <= 366:
        raise ValueError("activity reading requires a bounded ISO date window")


def snapshot_inputs(database, start, through):
    """Return latest valid complete snapshots and full facts using read-only handles."""
    _window(start, through)
    database = Path(database).resolve()
    if not database.is_file(): raise FileNotFoundError("activity database is unavailable")
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        db.execute("pragma query_only=on"); db.row_factory = sqlite3.Row
        metas = [dict(r) for r in db.execute("with ranked as (select *,row_number() over (partition by trade_date order by fetched_at desc,snapshot_id desc) rn from activity_snapshots where trade_date between ? and ? and daily_row_count>0 and daily_basic_row_count>0 and limit_row_count>0) select * from ranked where rn=1 order by trade_date", (start, through))]
        result = []
        for meta in metas:
            meta.pop("rn")
            values = [dict(r) for r in db.execute("select symbol,trade_date,payload_json from market_activity_daily where snapshot_id=? order by symbol", (meta["snapshot_id"],))]
            facts = [json.loads(r["payload_json"]) for r in values]
            if any((r["symbol"], r["trade_date"]) != (f["symbol"], f["trade_date"]) for r, f in zip(values, facts)):
                raise ValueError("stored activity fact identity changed")
            code = digest({"contract_version": meta["contract_version"], "trade_date": meta["trade_date"], "facts": facts})
            if (meta["contract_version"] != "market_activity_v1" or code != meta["content_digest"] or meta["snapshot_id"] != "MAS-" + code[:20].upper()
                    or len(facts) != meta["row_count"] or len(facts) != meta["membership_count"] or len({f["symbol"] for f in facts}) != len(facts)
                    or any(f["trade_date"] != meta["trade_date"] for f in facts)):
                raise ValueError("stored activity snapshot changed")
            for fact in facts: MarketActivityFact.model_validate(fact)
            result.append({"metadata": meta, "facts": facts})
    return result


def _positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value > 0


def read_activity(*, database, symbol, start, through, corrections=None):
    if not isinstance(symbol, str) or not re.fullmatch(r"\d{6}", symbol):
        raise ValueError("activity reading requires an exact six-digit historical member code")
    snapshots = snapshot_inputs(database, start, through)
    path = Path(corrections) if corrections is not None else registry_path(database)
    if corrections is not None and not path.is_file(): raise FileNotFoundError("requested activity corrections are unavailable")
    registry = validate_registry(json.loads(path.read_text()), path.parent) if path.is_file() else None
    identity = None
    if registry and symbol == "839680":
        sources = registry["sources"]
        identity = verified_code_identity(old_codes=[symbol],
            mapping_html=_asset(path.parent, sources["mapping"]), mapping_ref=sources["mapping"],
            switch_html=_asset(path.parent, sources["switch"]), switch_ref=sources["switch"])[symbol]
    entries = {(e["symbol"], e["trade_date"]): e for e in registry["entries"]} if registry else {}
    rows, refs, applied = [], [], set()
    for snapshot in snapshots:
        meta = snapshot["metadata"]
        for fact in snapshot["facts"]:
            if fact["symbol"] != symbol: continue
            before, after = deepcopy(fact), deepcopy(fact)
            key = symbol, fact["trade_date"]
            entry = entries.get(key)
            mode = "stored_state"
            if entry:
                if (meta["snapshot_id"] != entry["snapshot_id"] or meta["content_digest"] != entry["snapshot_digest"]
                        or digest(meta) != entry["snapshot_metadata_digest"] or digest(before) != entry["old_fact_digest"]
                        or before["suspension_status"] != "trading" or before["suspend_type"] or before["close"] is not None or before["volume"] is not None):
                    raise ValueError("activity correction no longer matches the selected original snapshot")
                after.update(suspend_type="S", suspend_timing="", suspension_status="suspended", eligible_for_anomaly=False)
                after["exclusion_reasons"] = list(dict.fromkeys([*after["exclusion_reasons"], "suspended"]))
                mode = "official_suspension_correction"; applied.add(key)
            elif before["suspension_status"] == "trading" and not (_positive(before["close"]) and _positive(before["volume"])):
                after.update(suspension_status="unknown", eligible_for_anomaly=False)
                after["exclusion_reasons"] = list(dict.fromkeys([*after["exclusion_reasons"], "suspension_status_unknown"]))
                mode = "missing_trade_data_state_unknown"
            MarketActivityFact.model_validate(after)
            rows.append({"symbol": symbol, "trade_date": fact["trade_date"], "snapshot_id": meta["snapshot_id"],
                         "stored_fact": before, "effective_fact": after, "stored_fact_digest": digest(before),
                         "effective_fact_digest": digest(after), "reading_mode": mode,
                         "correction_id": entry["entry_id"] if entry else None})
            refs.append(meta)
    needed = {k for k in entries if k[0] == symbol and start <= k[1] <= through}
    if needed != applied: raise ValueError("a registered correction target is missing from the current snapshot selection")
    body = {"version": READING_VERSION, "symbol": symbol, "start": start, "through": through,
            "rows": rows, "reading_modes": dict(Counter(r["reading_mode"] for r in rows)),
            "source_snapshots": refs, "correction_registry_digest": registry["content_digest"] if registry else None,
            "correction_recorded_at": registry["created_at"] if registry else None,
            "correction_sources": registry["sources"] if registry else {},
            "basis_study": registry["basis_study"] if registry else None,
            "verified_member_identity": identity,
            "reader_digest": sha256(Path(__file__).read_bytes()).hexdigest(),
            "availability": "available" if rows else "unavailable",
            "boundaries": {"original_snapshots_rewritten": False, "legacy_jobs_recomputed": False,
                           "prices_filled": False, "zero_returns_inferred": False,
                           "point_in_time_availability_certified": False, "causal_or_strategy_validation": False}}
    return {**body, "content_digest": digest(body)}


def augment_activity_reading(pack, reading):
    """Register an explicit source reading in the existing pack/catalog workflow."""
    from evidence_gateway import EvidencePack
    from canonical_json import canonical_json
    if (reading.get("version") != READING_VERSION or
            digest({k: v for k, v in reading.items() if k != "content_digest"}) != reading.get("content_digest")):
        raise ValueError("activity reading content changed")
    if pack.question_scope.get("route") in {"refuse_or_rewrite", "clarify"}:
        return pack
    scope = pack.question_scope.get("object", {})
    if scope.get("kind") == "stock" and scope.get("ref") != reading["symbol"]:
        identity = reading.get("verified_member_identity") or {}
        if not (reading.get("correction_registry_digest") and identity.get("old_code") == reading["symbol"]
                and identity.get("provider_code") == scope.get("ref")
                and identity.get("listing_date", "9999") <= reading["start"] <= reading["through"] < identity.get("exchange_code_effective_on", "")):
            raise ValueError("activity reading differs from the research subject")
    row = {"row_id": "activity_reading_" + reading["content_digest"][:20],
           "activity_reading": reading, "not_mechanism_lens": True}
    if any(r.get("row_id") == row["row_id"] for r in pack.rows):
        if row not in pack.rows: raise ValueError("activity reading row conflict")
        return pack
    payload = pack.model_dump(mode="json", exclude={"pack_id", "pack_digest"})
    payload["rows"].append(row)
    payload["question_scope"]["activity_reading_scope"] = {"historical_member_code": reading["symbol"],
        "start": reading["start"], "through": reading["through"], "verified_member_identity": reading.get("verified_member_identity")}
    payload["validation_catalog"]["query_row:" + row["row_id"]] = canonical_json({k: v for k, v in row.items() if k != "row_id"})
    payload["provenance"].append("corrected_activity_reading:" + reading["content_digest"])
    payload["source_freshness"]["activity_correction_recorded_at"] = reading["correction_recorded_at"] or "no_registry"
    payload["definitions"].append("活动状态读取同时保留原快照与独立更正；更正记录时间不冒充当时信息可得时间。")
    payload["definitions"].append("已核官方新旧代码可关联同一公司；显式历史窗口不修改原交易代码或已有概览的截止日。")
    payload["forbidden_inferences"].append("活动状态更正不回填价格、不推断零收益、不替旧回测重算，也不认证预测或因果效果。")
    code = digest(payload)
    return EvidencePack.model_validate({**payload, "pack_id": "EP-" + code[:20].upper(), "pack_digest": code})
