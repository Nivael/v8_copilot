from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import pytest

from canonical_json import digest
from historical_code_gap_review import MAPPING_URL, SWITCH_URL, review_code_gaps
from historical_price_gap_review import classify_gaps, QUOTE_SOURCE
from p8_grid_price_coverage import sha

OLD, NEW, DAY = "839680", "920680", "2025-09-15"
NOTICE = ("关于北交所存量上市公司代码切换上线的通知 2025-09-12 "
          "自2025年10月9日起 新旧代码对应关系").encode()
TABLE = b"<table><tr><td>174</td><td>Test issuer</td><td>2021/11/15</td><td>839680</td><td>920680</td></tr></table>"


def ref(raw, url):
    return {"url": url, "response_url": url, "sha256": sha256(raw).hexdigest(), "bytes": len(raw),
            "fetched_at": datetime.now(timezone.utc).isoformat()}


def base(gap=None):
    return classify_gaps([gap or {"symbol": OLD, "trade_date": DAY, "name": "Test issuer"}],
                         quotes=[], snapshots=[], suspension_days=[])


def quote(close=3):
    return {"symbol": NEW, "trade_date": DAY, "adjust": "qfq", "close": close, "source": QUOTE_SOURCE,
            "fetched_at": "2026-06-29 05:38:03"}


def suspension(kind="S", timing=None):
    rows = [{"ts_code": NEW + ".BJ", "trade_date": DAY.replace("-", ""), "suspend_type": kind, "suspend_timing": timing}]
    return {"trade_date": DAY, "rows": rows, "rows_digest": sha(rows), "source": "tushare:suspend_d",
            "fetched_at": "2026-09-06T16:11:29+00:00"}


def run(prior=None, *, quotes=(), days=(), **changes):
    kwargs = {"old_codes": [OLD], "mapping_html": TABLE, "mapping_ref": ref(TABLE, MAPPING_URL),
              "switch_html": NOTICE, "switch_ref": ref(NOTICE, SWITCH_URL),
              "quotes": list(quotes), "suspension_days": list(days), **changes}
    return review_code_gaps(prior or base(), **kwargs)


def test_exact_mapping_preserves_old_trade_identity_and_separate_clocks():
    prior = base(); saved = deepcopy(prior); out = run(prior, quotes=[quote()])
    assert prior == saved and out["counts"] == {"mapped_archive_quote": 1}
    row = out["patches"][0]
    assert row["symbol"] == OLD and row["evidence"][0]["source_row"]["symbol"] == NEW
    assert row["code_identity"]["listing_date"] == "2021-11-15"
    assert row["code_identity"]["exchange_code_effective_on"] == "2025-10-09"
    assert row["evidence"][0]["source_row"]["fetched_at"] == "2026-06-29 05:38:03"
    assert all(v is False for v in out["boundaries"].values())
    assert out["content_digest"] == digest({k: v for k, v in out.items() if k != "content_digest"})


def test_mapped_full_day_suspension_and_conflicting_quote():
    assert run(days=[suspension()])["counts"] == {"mapped_provider_full_day_suspension": 1}
    assert run(quotes=[quote()], days=[suspension()])["counts"] == {"conflicting_source_states": 1}


@pytest.mark.parametrize("kind,timing", [("R", None), ("S", "09:30-10:00")])
def test_resume_intraday_and_absence_remain_unknown(kind, timing):
    assert run(days=[suspension(kind, timing)])["patches"] == []
    assert run()["counts"] == {"unresolved": 1}


def test_contradictory_old_state_is_not_overwritten_by_new_code():
    prior = base(); prior["rows"][0]["evidence"] = [{"full_day_suspension": True}]
    prior["rows"][0]["classification"] = "provider_full_day_suspension"
    prior["counts"] = {"provider_full_day_suspension": 1}
    prior["content_digest"] = digest({k: v for k, v in prior.items() if k != "content_digest"})
    assert run(prior, quotes=[quote()])["counts"] == {"conflicting_source_states": 1}


def test_unrelated_prior_rows_are_untouched_and_same_provider_is_not_independent():
    prior = classify_gaps([{"symbol": OLD, "trade_date": DAY}, {"symbol": "002514", "trade_date": DAY}], quotes=[], snapshots=[], suspension_days=[])
    out = run(prior, quotes=[quote()])
    assert len(out["patches"]) == 1 and out["counts"] == {"unresolved": 1, "mapped_archive_quote": 1}
    assert out["base_review_digest"] == prior["content_digest"]


@pytest.mark.parametrize("field,value", [("url", "https://mirror.test/map"), ("response_url", "https://mirror.test/map"),
                                          ("sha256", "0" * 64), ("bytes", 1), ("fetched_at", "2026-11-07")])
def test_official_source_identity_and_aware_clock_required(field, value):
    changed = {**ref(TABLE, MAPPING_URL), field: value}
    with pytest.raises(ValueError): run(mapping_ref=changed)


@pytest.mark.parametrize("change", ["missing", "duplicate", "date", "newcode"])
def test_table_identity_cannot_be_guessed(change):
    raw = TABLE
    if change == "missing": raw = raw.replace(b"839680", b"839681")
    if change == "duplicate": raw += TABLE
    if change == "date": raw = raw.replace(b"2021/11/15", b"not a date")
    if change == "newcode": raw = raw.replace(b"920680", b"002514")
    with pytest.raises(ValueError): run(mapping_html=raw, mapping_ref=ref(raw, MAPPING_URL))


def test_changed_notice_and_out_of_scope_issuer_are_rejected():
    raw = NOTICE.replace("10月9日".encode(), "5月6日".encode())
    with pytest.raises(ValueError): run(switch_html=raw, switch_ref=ref(raw, SWITCH_URL))
    with pytest.raises(ValueError): run(old_codes=["873305"])


@pytest.mark.parametrize("day", ["2021-11-14", "2025-10-09", "2025-12-31"])
def test_listing_trade_and_code_effective_dates_not_conflated(day):
    with pytest.raises(ValueError): run(base({"symbol": OLD, "trade_date": day}))


@pytest.mark.parametrize("stamp", ["2025-10-08 09:00:00", "2025-10-09 23:59:59", "2099-01-01 00:00:00"])
def test_later_normalized_archive_cannot_be_dated_before_code_change(stamp):
    with pytest.raises(ValueError): run(quotes=[{**quote(), "fetched_at": stamp}])


def test_tampered_base_and_unrelated_quotes_rejected():
    prior = base(); prior["rows"][0]["name"] = "changed"
    with pytest.raises(ValueError): run(prior)
    with pytest.raises(ValueError): run(quotes=[{**quote(), "symbol": "920681"}])
