"""Source-bound retrospective BSE code identity; never rewrite trading history."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import re

from canonical_json import digest
from historical_price_gap_review import classify_gaps

VERSION = "historical_bse_code_gap_review_v1"
MAPPING_URL = "https://www.bse.cn/service/code_mapping.html"
SWITCH_URL = "https://www.bse.cn/important_news/200026735.html"
EFFECTIVE_ON = "2025-10-09"
PROFILE_OLD_CODES = {"835305", "839680"}


class _Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.text = [], []
        self.row = self.cell = None
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"): self.skip += 1
        if tag == "tr": self.row = []
        if tag in ("td", "th") and self.row is not None: self.cell = []

    def handle_data(self, value):
        if self.cell is not None: self.cell.append(value)
        if not self.skip: self.text.append(value)

    def handle_endtag(self, tag):
        if tag in ("script", "style"): self.skip = max(0, self.skip - 1)
        if tag in ("td", "th") and self.cell is not None:
            self.row.append("".join(self.cell).strip()); self.cell = None
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row); self.row = None


def _document(raw, ref, expected_url):
    if (not isinstance(raw, bytes) or not 0 < len(raw) <= 1_000_000 or
            ref.get("url") != expected_url or ref.get("response_url") != expected_url or
            ref.get("bytes") != len(raw) or ref.get("sha256") != sha256(raw).hexdigest()):
        raise ValueError("official document identity changed")
    stamp = datetime.fromisoformat(ref["fetched_at"])
    if stamp.tzinfo is None or stamp > datetime.now(timezone.utc):
        raise ValueError("invalid official observation clock")
    result = _Document(); result.feed(raw.decode("utf-8", errors="strict"))
    return result


def _archive_after_switch(value):
    day = datetime.fromisoformat(value).date().isoformat()
    if not EFFECTIVE_ON < day <= datetime.now(timezone.utc).date().isoformat():
        raise ValueError("archive observation date outside retrospective profile")


def verified_code_identity(*, old_codes, mapping_html, mapping_ref, switch_html, switch_ref):
    """Verify official identities independently of a particular price-gap audit."""
    if not old_codes or len(set(old_codes)) != len(old_codes): raise ValueError("invalid mapping scope")
    if not set(old_codes) <= PROFILE_OLD_CODES:
        raise ValueError("issuer code-effective history not verified in this profile")
    table = _document(mapping_html, mapping_ref, MAPPING_URL)
    notice = _document(switch_html, switch_ref, SWITCH_URL)
    text = re.sub(r"\s+", "", "".join(notice.text))
    if not all(part in text for part in ("关于北交所存量上市公司代码切换上线的通知", "2025-09-12", "自2025年10月9日起", "新旧代码对应关系")):
        raise ValueError("code-change notice profile mismatch")
    mapping = {}
    for old in old_codes:
        if not isinstance(old, str) or not re.fullmatch(r"[48]\d{5}", old): raise ValueError("unsupported old BSE code")
        rows = [r for r in table.rows if len(r) == 5 and r[3] == old]
        if len(rows) != 1: raise ValueError("missing or ambiguous official mapping")
        row = rows[0]
        if not row[1] or not re.fullmatch(r"920\d{3}", row[4]): raise ValueError("invalid mapped identity")
        listing = datetime.strptime(row[2], "%Y/%m/%d").date().isoformat()
        mapping[old] = {"old_code": old, "provider_code": row[4], "official_name": row[1],
                        "listing_date": listing, "exchange_code_effective_on": EFFECTIVE_ON,
                        "official_table_row": row}
    if len({r["provider_code"] for r in mapping.values()}) != len(mapping):
        raise ValueError("many-to-one code identity")
    return mapping


def review_code_gaps(base, *, old_codes, mapping_html, mapping_ref, switch_html,
                     switch_ref, quotes, suspension_days):
    """Apply exact official mappings to a fixed prior audit, returning patches only.

    Listing date, exchange code-effective date, historic trade date and later
    provider observation date remain separate. This is retrospective archive
    interpretation, not certification of point-in-time availability or returns.
    """
    if (base.get("version") != "historical_price_gap_review_v1" or
            digest({k: v for k, v in base.items() if k != "content_digest"}) != base.get("content_digest") or
            Counter(r["classification"] for r in base["rows"]) != base["counts"]):
        raise ValueError("base gap audit changed")
    keys = {(r["symbol"], r["trade_date"]) for r in base["rows"]}
    if len(keys) != len(base["rows"]): raise ValueError("duplicate base member day")
    mapping = verified_code_identity(old_codes=old_codes, mapping_html=mapping_html,
                                     mapping_ref=mapping_ref, switch_html=switch_html,
                                     switch_ref=switch_ref)
    selected = [r for r in base["rows"] if r["symbol"] in mapping]
    normalized = []
    for row in selected:
        identity = mapping[row["symbol"]]
        if not identity["listing_date"] <= row["trade_date"] < EFFECTIVE_ON:
            raise ValueError("old-code member day outside identity profile")
        normalized.append({"symbol": identity["provider_code"], "trade_date": row["trade_date"],
                           "name": row.get("name", ""), "original_symbol": row["symbol"]})
    if not normalized: raise ValueError("no matching historic member days")
    allowed = {r["provider_code"] for r in mapping.values()}
    for quote in quotes:
        if quote["symbol"] not in allowed: raise ValueError("unrelated quote in code review")
        # Preserve naive legacy timestamps; compare calendar dates, not invented UTC instants.
        _archive_after_switch(quote["fetched_at"])
    for day in suspension_days:
        _archive_after_switch(day["fetched_at"])
    candidate = classify_gaps(normalized, quotes=quotes, snapshots=[], suspension_days=suspension_days)
    by = {(r["original_symbol"], r["trade_date"]): r for r in candidate["rows"]}
    patches = []
    counts = Counter(base["counts"])
    names = {"alternate_archive_quote": "mapped_archive_quote",
             "provider_full_day_suspension": "mapped_provider_full_day_suspension"}
    for before in selected:
        after = by[(before["symbol"], before["trade_date"])]
        new = after["classification"]
        old = before["classification"]
        old_suspended = any(e.get("full_day_suspension") for e in before["evidence"])
        old_positive = any(e.get("positive_close") for e in before["evidence"])
        old_contrary = any(e.get("contrary_to_full_day") for e in before["evidence"])
        conflict = new == "conflicting_source_states" or (new == "alternate_archive_quote" and old_suspended) or (new == "provider_full_day_suspension" and (old_positive or old_contrary))
        status = "conflicting_source_states" if conflict else names.get(new) if old == "unresolved" else None
        if status is None: continue
        row = deepcopy(before)
        row.update(classification=status, previous_classification=old,
                   code_identity=mapping[before["symbol"]],
                   evidence=[*row["evidence"], *after["evidence"]])
        patches.append(row); counts[old] -= 1; counts[status] += 1
    body = {"version": VERSION, "base_review_digest": base["content_digest"], "patches": patches,
            "counts": {k: v for k, v in counts.items() if v}, "mapping": mapping,
            "source_bindings": {"mapping": mapping_ref, "switch_notice": switch_ref,
                                "notice_publication_on": "2025-09-12", "exchange_code_effective_on": EFFECTIVE_ON,
                                "classified_candidate_digest": candidate["content_digest"],
                                "quotes_digest": digest(quotes), "suspension_days_digest": digest(suspension_days)},
            "boundaries": {"suffix_guess_used": False, "historic_trade_codes_rewritten": False,
                           "prices_spliced": False, "zero_returns_inferred": False,
                           "adjustment_consistency_verified": False, "independent_quote_source": False,
                           "point_in_time_availability_verified": False, "full_population_certified": False,
                           "causal_or_strategy_estimates": False}}
    return {**body, "content_digest": digest(body)}
