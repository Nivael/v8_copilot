from copy import deepcopy
import pytest

from canonical_json import digest
from historical_price_gap_review import ACTIVITY_SOURCE, QUOTE_SOURCE, classify_gaps
from p8_grid_price_coverage import sha

GAP = {"symbol": "002514", "trade_date": "2025-05-06", "name": "ST宝馨"}
RAW = {"ts_code": "002514.SZ", "trade_date": "20250506", "suspend_type": "S", "suspend_timing": None}
CLOCK = "2026-09-04T18:06:13+00:00"


def day(rows=None):
    rows = deepcopy([RAW] if rows is None else rows)
    return {"trade_date": GAP["trade_date"], "source": "tushare:suspend_d", "fetched_at": CLOCK,
            "rows": rows, "rows_digest": sha(rows)}


def quote(close=3.14):
    return {"symbol": GAP["symbol"], "trade_date": GAP["trade_date"], "adjust": "qfq", "close": close,
            "source": QUOTE_SOURCE, "fetched_at": "2026-09-04 18:06:13"}


def snapshot(**changes):
    fact = {**GAP, "source": ACTIVITY_SOURCE, "ts_code": "002514.SZ", "close": None,
            "suspend_type": "S", "suspend_timing": "", "suspension_status": "suspended", **changes}
    facts = [fact]
    code = digest({"contract_version": "market_activity_v1", "trade_date": GAP["trade_date"], "facts": facts})
    return {"metadata": {"contract_version": "market_activity_v1", "trade_date": GAP["trade_date"],
                         "snapshot_id": "MAS-" + code[:20].upper(), "content_digest": code,
                         "row_count": 1, "membership_count": 1, "fetched_at": CLOCK}, "facts": facts}


def review(*, quotes=(), snapshots=(), days=(), gaps=None):
    return classify_gaps([GAP] if gaps is None else gaps, quotes=list(quotes),
                         snapshots=list(snapshots), suspension_days=list(days))


def status(**kwargs):
    return review(**kwargs)["rows"][0]["classification"]


def test_missing_is_unknown_not_zero_or_suspension():
    result = review()
    assert result["counts"] == {"unresolved": 1}
    assert not result["boundaries"]["zero_returns_inferred"]
    assert not result["boundaries"]["prices_filled_or_spliced"]
    assert not result["boundaries"]["historical_information_availability_verified"]


def test_quote_is_same_provider_archive_not_independent_and_preserves_naive_clock():
    result = review(quotes=[quote()])
    assert result["counts"] == {"alternate_archive_quote": 1}
    assert result["rows"][0]["evidence"][0]["source_row"]["fetched_at"] == "2026-09-04 18:06:13"
    assert result["boundaries"]["alternate_provider_not_independent"]
    assert result["content_digest"] == digest({k: v for k, v in result.items() if k != "content_digest"})


@pytest.mark.parametrize("close", [None, 0, -1, float("inf"), float("nan"), True, "3.14"])
def test_invalid_quotes_do_not_close_gap(close):
    assert status(quotes=[quote(close)]) == "unresolved"


@pytest.mark.parametrize("timing", [None, "", "None"])
def test_explicit_full_day_provider_claim(timing):
    assert status(days=[day([{**RAW, "suspend_timing": timing}])]) == "provider_full_day_suspension"
    assert status(snapshots=[snapshot(suspend_timing=timing)]) == "provider_full_day_suspension"


@pytest.mark.parametrize("row", [{**RAW, "suspend_type": "R"}, {**RAW, "suspend_timing": "09:30-10:00"}])
def test_resume_and_intraday_are_not_full_day(row):
    assert status(days=[day([row])]) == "unresolved"
    assert status(days=[day([RAW, row])]) == "conflicting_source_states"


def test_positive_quote_and_suspension_are_conflict():
    assert status(quotes=[quote()], days=[day()]) == "conflicting_source_states"
    assert status(quotes=[quote()], snapshots=[snapshot()]) == "conflicting_source_states"


def test_conflicting_activity_revision_or_raw_resume_is_retained():
    assert status(snapshots=[snapshot(), snapshot(suspend_type="R", suspension_status="trading")]) == "conflicting_source_states"
    assert status(snapshots=[snapshot()], days=[day([{**RAW, "suspend_type": "R"}])]) == "conflicting_source_states"


def test_never_join_alias_by_shared_suffix_or_spread_to_next_day():
    bj = {**GAP, "symbol": "839680"}
    result = review(gaps=[bj], quotes=[{**quote(), "symbol": "920680"}])
    assert result["counts"] == {"unresolved": 1}
    assert status(days=[{**day(), "trade_date": "2025-05-07", "rows": [{**RAW, "trade_date": "20250507"}],
                         "rows_digest": sha([{**RAW, "trade_date": "20250507"}])}]) == "unresolved"


@pytest.mark.parametrize("mutation", ["fact", "identity", "count", "version", "clock"])
def test_tampered_activity_archive_rejected(mutation):
    item = snapshot()
    if mutation == "fact": item["facts"][0]["close"] = 3
    if mutation == "identity": item["metadata"]["snapshot_id"] = "MAS-" + "0" * 20
    if mutation == "count": item["metadata"]["row_count"] = 2
    if mutation == "version": item["metadata"]["contract_version"] = "unknown"
    if mutation == "clock": item["metadata"]["fetched_at"] = ""
    with pytest.raises(ValueError): review(snapshots=[item])


@pytest.mark.parametrize("field,value", [("source", "mirror"), ("rows_digest", "0" * 64), ("trade_date", "2025-05-07")])
def test_tampered_raw_suspension_rejected(field, value):
    with pytest.raises(ValueError): review(days=[{**day(), field: value}])


@pytest.mark.parametrize("field,value", [("adjust", "raw"), ("source", "mirror"), ("fetched_at", ""), ("symbol", "2514")])
def test_invalid_quote_identity_rejected(field, value):
    with pytest.raises(ValueError): review(quotes=[{**quote(), field: value}])


def test_duplicate_archive_identity_and_member_day_rejected():
    for kwargs in [{"quotes": [quote(), quote()]}, {"snapshots": [snapshot(), snapshot()]},
                   {"days": [day(), day()]}, {"gaps": [GAP, GAP]}]:
        with pytest.raises(ValueError): review(**kwargs)


def test_unknown_activity_state_with_positive_unadjusted_close_is_not_qfq_coverage():
    assert status(snapshots=[snapshot(close=3, suspend_type="", suspension_status="trading")]) == "unresolved"
