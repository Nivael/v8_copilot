from types import SimpleNamespace

import pytest

from p8_grid_price_coverage import acquire, full_day, gap_plan, sha, verified_suspensions


def fact(kind="S", timing="", close=None):
    return SimpleNamespace(symbol="000001", trade_date="2023-01-03", suspend_type=kind,
                           suspend_timing=timing, close=close)


def evidence(kind="S", timing=None):
    rows = [dict(ts_code="000001.SZ", trade_date="20230103", suspend_type=kind, suspend_timing=timing)]
    return dict(days=[dict(trade_date="2023-01-03", rows=rows, rows_digest=sha(rows), source="tushare:suspend_d")])


@pytest.mark.parametrize("kind,timing,ok", [("S", None, True), ("S", "None", True),
                                             ("R", "", False), ("S", "09:30-10:00", False), ("S；R", "", False)])
def test_full_day_not_resume_or_intraday(kind, timing, ok):
    assert full_day(kind, timing) is ok


def test_suspension_proof_positive_only_and_raw_price_conflict():
    key = ("000001", "2023-01-03")
    assert verified_suspensions([], evidence()) == {key}  # Pre-ST also supported.
    assert verified_suspensions([fact()]) == {key}
    assert verified_suspensions([fact(close=10)], evidence()) == set()
    assert verified_suspensions([fact()], evidence("R")) == set()
    assert verified_suspensions([], dict(days=[])) == set()
    broken = evidence()
    broken["days"][0]["rows"][0]["suspend_type"] = "R"
    with pytest.raises(ValueError, match="digest"):
        verified_suspensions([], broken)
    broken = evidence()
    broken["days"][0]["trade_date"] = "2023-01-04"
    with pytest.raises(ValueError, match="date"):
        verified_suspensions([], broken)


def test_gap_plan_is_date_only_frozen_and_reuses_local_proof():
    days = ["2023-01-02", "2023-01-03", "2023-01-04"]
    prices = {"000001": [(days[0], 10), (days[2], 9)], "000002": [(days[0], 10), (days[2], 9)]}
    members = {days[2]: {"000001", "000002"}}
    plan = gap_plan(prices, days, members, [fact()], 3)
    assert plan["targets"] == {days[1]: ["000002"]}
    assert plan["request_upper_bound"] == 1
    assert plan["outcomes_read"] is False
    assert gap_plan(prices, days, members, [fact()], 3) == plan


def test_provider_cache_is_resumable_and_empty_not_positive(tmp_path):
    calls = []
    class Client:
        def fetch_suspend_daily(self, *, trade_date):
            calls.append(trade_date)
            return []
    plan = dict(targets={"2023-01-03": ["000001"]}, plan_digest="fixed")
    first = acquire(plan, tmp_path, Client(), delay=0)
    second = acquire(plan, tmp_path, Client(), delay=0)
    assert calls == ["2023-01-03"]
    assert first == second
    assert first["status"] == "complete"
    assert verified_suspensions([], first) == set()


def test_failed_request_does_not_create_success_cache(tmp_path):
    class Client:
        def fetch_suspend_daily(self, *, trade_date):
            raise RuntimeError("sensitive error must not be persisted")
    plan = dict(targets={"2023-01-03": ["000001"]}, plan_digest="fixed")
    result = acquire(plan, tmp_path, Client(), delay=0)
    assert result["status"] == "partial"
    assert result["days"] == []
    assert result["failures"] == {"2023-01-03": "RuntimeError"}
    assert list(tmp_path.iterdir()) == []
