from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from market_activity import (
    MarketActivityFact,
    MarketActivityBootstrapService,
    MarketActivityRepository,
    build_market_activity_manifest,
    normalize_activity_rows,
    write_market_activity_manifest_set,
)
from p7_anomalies import build_activity_episodes, build_anomaly_run, compute_anomalies


def _raw(symbol: str, day: str, close: float = 10.0):
    return {
        "ts_code": f"{symbol}.SZ", "trade_date": day.replace("-", ""),
        "open": close, "high": close + 0.2, "low": close - 0.1,
        "close": close, "pre_close": close - 0.1, "change": 0.1,
        "pct_chg": 1.0, "vol": 1000, "amount": 10000,
    }


def _basic(symbol: str, day: str, turnover: float = 2.0):
    return {
        "ts_code": f"{symbol}.SZ", "trade_date": day.replace("-", ""),
        "close": 10, "turnover_rate": turnover / 2,
        "turnover_rate_f": turnover, "volume_ratio": 1.2,
        "total_share": 1000, "float_share": 800, "free_share": 500,
        "total_mv": 10000, "circ_mv": 8000,
    }


def _member(symbol: str):
    return {
        "symbol": symbol, "ts_code": f"{symbol}.SZ", "name": "*ST样本",
        "risk_type": "ST", "risk_type_name": "风险警示板",
    }


def test_activity_normalization_uses_raw_limit_fallback_and_suspension_negative_evidence(tmp_path):
    day = "2026-08-17"
    rows = normalize_activity_rows(
        trade_date=day,
        memberships=[_member("000001"), _member("000002")],
        daily_rows=[_raw("000001", day), _raw("000002", day)],
        daily_basic_rows=[_basic("000001", day), _basic("000002", day)],
        suspend_rows=[{
            "ts_code": "000002.SZ", "trade_date": "20260817",
            "suspend_timing": "全天", "suspend_type": "停牌",
        }],
        limit_rows=[
            {"ts_code": f"{symbol}.SZ", "trade_date": "20260817", "pre_close": 9.9, "up_limit": 10.4, "down_limit": 9.4}
            for symbol in ("000001", "000002")
        ],
    )
    assert rows[0].suspension_status == "trading"
    assert rows[0].one_price_limit is False
    assert rows[0].eligible_for_anomaly is True
    assert rows[0].amplitude_pct is not None
    assert rows[1].suspension_status == "suspended"
    assert rows[1].eligible_for_anomaly is False
    assert "suspended" in rows[1].exclusion_reasons

    repository = MarketActivityRepository(tmp_path / "activity.sqlite3")
    first = repository.store_snapshot(
        trade_date=day, facts=rows, daily_row_count=2,
        daily_basic_row_count=2, suspend_row_count=1, limit_row_count=2,
        fetched_at="2026-08-18T00:00:00+00:00",
    )
    second = repository.store_snapshot(
        trade_date=day, facts=rows, daily_row_count=2,
        daily_basic_row_count=2, suspend_row_count=1, limit_row_count=2,
        fetched_at="2026-08-19T00:00:00+00:00",
    )
    assert first.snapshot_id == second.snapshot_id
    assert len(repository.latest_facts()) == 2


def test_one_price_conflict_unknown_suspension_and_terminal_unknown_fail_closed():
    day = "2026-08-17"
    one_price = _raw("000001", day, close=10.4)
    one_price.update({"open": 10.4, "high": 10.4, "low": 10.4, "pre_close": 9.9})
    conflict_basic = _basic("000002", day)
    conflict_basic["limit_status"] = 3
    rows = normalize_activity_rows(
        trade_date=day,
        memberships=[_member("000001"), _member("000002"), {
            "symbol": "000003", "ts_code": "000003.SZ", "name": "样本",
            "risk_type": "", "risk_type_name": "",
        }],
        daily_rows=[one_price, _raw("000002", day), _raw("000003", day)],
        daily_basic_rows=[_basic("000001", day), conflict_basic, _basic("000003", day)],
        suspend_rows=[], suspension_query_complete=False,
        limit_rows=[
            {"ts_code": f"{symbol}.SZ", "trade_date": "20260817", "pre_close": 9.9, "up_limit": 10.4, "down_limit": 9.4}
            for symbol in ("000001", "000002", "000003")
        ],
    )
    assert rows[0].one_price_limit is True and rows[0].eligible_for_anomaly is False
    assert "one_price_limit" in rows[0].exclusion_reasons
    assert rows[1].limit_state_conflict is True and rows[1].eligible_for_anomaly is False
    assert rows[2].suspension_status == "unknown"
    assert rows[2].terminal_phase_status == "unknown"
    assert rows[2].eligible_for_anomaly is False


def _fact(symbol: str, day: str, turnover: float, *, eligible: bool = True) -> MarketActivityFact:
    return MarketActivityFact(
        symbol=symbol, ts_code=f"{symbol}.SZ", name="ST样本", trade_date=day,
        turnover_rate_f=turnover, suspension_status="trading",
        one_price_limit=False, terminal_phase_status="not_terminal",
        eligible_for_anomaly=eligible,
        exclusion_reasons=[] if eligible else ["suspended"],
        pct_chg=1.0,
    )


def test_anomaly_window_excludes_current_and_episode_merging_is_frozen():
    start = date(2026, 1, 1)
    facts = [
        _fact("000001", (start + timedelta(days=index)).isoformat(), 1 + index * 0.01)
        for index in range(60)
    ]
    spike_day = (start + timedelta(days=60)).isoformat()
    facts.append(_fact("000001", spike_day, 20.0))
    anomalies = compute_anomalies(facts)
    spike = anomalies[-1]
    assert spike.history_count == 60
    assert spike.turnover_median_120 is not None and spike.turnover_median_120 < 2
    assert spike.balanced is True

    future = _fact("000001", (start + timedelta(days=61)).isoformat(), 99.0)
    assert compute_anomalies([*facts, future])[-2] == spike
    episodes = build_activity_episodes(compute_anomalies([*facts, future]), profile="balanced", merge_gap=5)
    assert len(episodes) == 1
    assert episodes[0].member_dates == [spike_day, future.trade_date]


def test_zero_mad_breakout_never_enters_default_profile():
    start = date(2026, 1, 1)
    facts = [_fact("000001", (start + timedelta(days=index)).isoformat(), 1.0) for index in range(60)]
    facts.append(_fact("000001", (start + timedelta(days=60)).isoformat(), 5.0))
    result = build_anomaly_run(facts)
    assert result.zero_mad_breakout_count == 1
    assert result.balanced_hit_count == 0


def test_volume_ratio_and_share_scale_do_not_change_main_profile():
    start = date(2026, 1, 1)
    base = [_fact("000001", (start + timedelta(days=index)).isoformat(), 1 + index * .01) for index in range(60)]
    spike = _fact("000001", (start + timedelta(days=60)).isoformat(), 20)
    low_context = [item.model_copy(update={"volume_ratio": .1, "total_share": 10}) for item in [*base, spike]]
    high_context = [item.model_copy(update={"volume_ratio": 99, "total_share": 10_000_000}) for item in [*base, spike]]
    left = compute_anomalies(low_context)[-1]
    right = compute_anomalies(high_context)[-1]
    assert (left.broad, left.balanced, left.strict) == (right.broad, right.balanced, right.strict)


def test_activity_manifest_is_idempotent_and_content_addressed(tmp_path):
    day = "2026-08-17"
    repository = MarketActivityRepository(tmp_path / "activity.sqlite3")
    repository.store_snapshot(
        trade_date=day, facts=[_fact("000001", day, 1)], daily_row_count=1,
        daily_basic_row_count=1, suspend_row_count=0, limit_row_count=1,
        fetched_at="2026-08-18T00:00:00+00:00",
    )
    first = build_market_activity_manifest(repository, through=day)
    second = build_market_activity_manifest(repository, through=day)
    assert first["manifest_id"] == second["manifest_id"]
    current = tmp_path / "current.json"
    directory = tmp_path / "manifests"
    path = write_market_activity_manifest_set(first, current_path=current, manifest_directory=directory)
    replay = write_market_activity_manifest_set(second, current_path=current, manifest_directory=directory)
    assert replay == path
    assert path.name.startswith(f"{day}_MAM-")


def test_bootstrap_can_execute_a_frozen_date_subset_and_refresh_existing(tmp_path):
    context = tmp_path / "context.sqlite3"
    with sqlite3.connect(context) as connection:
        connection.execute("create table benchmark_daily (benchmark_id text,trade_date text)")
        connection.execute(
            "create table st_membership_daily (trade_date text,symbol text,ts_code text,name text,"
            "risk_type text,risk_type_name text)"
        )
        for day in ("2026-01-02", "2026-01-05"):
            connection.execute("insert into benchmark_daily values ('csi_all_share',?)", (day,))
            connection.execute(
                "insert into st_membership_daily values (?,?,?,?,?,?)",
                (day, "000001", "000001.SZ", "ST样本", "ST", "风险警示"),
            )

    class Provider:
        requested = []

        def fetch_daily(self, *, trade_date):
            self.requested.append(("daily", trade_date))
            return [_raw("000001", trade_date)]

        def fetch_daily_basic(self, *, trade_date):
            self.requested.append(("daily_basic", trade_date))
            return [_basic("000001", trade_date)]

        def fetch_suspend_daily(self, *, trade_date):
            self.requested.append(("suspend_d", trade_date))
            return []

        def fetch_stock_limits(self, *, trade_date):
            self.requested.append(("stk_limit", trade_date))
            return [{
                "ts_code": "000001.SZ", "trade_date": trade_date.replace("-", ""),
                "pre_close": 9.9, "up_limit": 10.4, "down_limit": 9.4,
            }]

    provider = Provider()
    result = MarketActivityBootstrapService(
        provider=provider,
        repository=MarketActivityRepository(tmp_path / "activity.sqlite3"),
        market_context_database=context,
    ).bootstrap(
        start_date="2026-01-02", through="2026-01-05",
        target_dates=["2026-01-05"], refresh_existing=True,
    )
    assert result.requested_date_count == 1
    assert {day for _endpoint, day in provider.requested} == {"2026-01-05"}
