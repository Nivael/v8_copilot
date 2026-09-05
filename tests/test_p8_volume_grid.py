import json
from copy import deepcopy

import pytest

from p8_volume_grid import CONFIG, classify, contrast, make_episodes, make_grid, observe, summarize


@pytest.fixture
def config():
    return json.loads(CONFIG.read_text())


def row(i, grid="low_flat", active=True, symbol="000001"):
    return dict(symbol=symbol, index=i, day=f"2023-01-{i+1:02}", grid=grid, active=active,
                stage="st", announcement="none_detected", capital="unknown", pulse=None)


def test_grid_is_two_axes_and_pulse_is_independent(config):
    assert len(config["thresholds"]) == 6
    for pos, expected in ((.3, "low"), (.5, "mid"), (.7, "high")):
        for drift, direction in ((-.2, "down"), (0, "flat"), (.2, "up")):
            g, a, p = classify(pos, drift, 2, .4, 4, 1.2, config)
            assert (g, a, p) == (expected+"_"+direction, True, True)
    assert classify(.2, 0, 1, .5, None, 1.2, config) == ("low_flat", False, None)


def test_episodes_first_entry_not_every_day_and_cooldown(config):
    config["windows"]["cooldown"] = 2
    rows = [row(0, active=False), row(1), row(2), row(3, active=False), row(4),
            row(5, active=False), row(6, active=False), row(7, active=False), row(8)]
    selected = [e for e in make_episodes(rows, config) if e["active"]]
    assert [r["index"] for r in selected] == [1, 8]
    assert selected[0]["exit_index"] == 3
    # No invented entry on a first observation or after a coverage gap.
    assert make_episodes([row(0), row(5)], config) == []


def test_transition_keeps_low_origin_and_returns_start_next_buyable_close(config):
    config["horizons"] = [2]
    config["windows"]["transition"] = 4
    days = [f"2023-01-{i+1:02}" for i in range(8)]
    rows = [row(0), row(1), row(2, "mid_up"), row(3, "mid_up"), row(4, "high_up")]
    e = dict(row(0), episode_id="e")
    prices = {"000001": list(zip(days, [10, 20, 30, 60, 90, 90, 90, 90]))}
    trades = {("000001", d): {"buy": True, "sell": True} for d in days}
    trades[("000001", days[1])]["buy"] = False
    result = observe([e], rows, prices, days, dict.fromkeys(days, 100), trades, {}, config)[0]
    assert result["transition_60"] == 1
    assert result["transition_grid"] == "mid_up"
    assert result["entry_day"] == days[2]
    assert result["excess"] == 2  # 90 / 30 - 1; never start at signal close 10.


def test_missing_followup_is_censored_and_delisting_is_failure(config):
    config["windows"]["transition"] = 4
    days = [f"2023-01-{i+1:02}" for i in range(8)]
    prices = {"000001": [(days[0], 10), (days[1], 10)]}
    e = dict(row(0), episode_id="e")
    missing = observe([e], [row(0)], prices, days, {}, {}, {}, config)[0]
    assert missing["transition_60"] is None
    failed = observe([e], [row(0)], prices, days, {}, {}, {"000001": days[3]}, config)[0]
    assert failed["transition_60"] == 0


def test_common_stratum_gate_uses_matched_not_full_pool(config):
    a = [dict(row(1, symbol=f"{i:06}"), excess=.1) for i in range(50)]
    b = [dict(row(2, symbol=f"{i+100:06}"), excess=.0, stage="other") for i in range(50)]
    assert contrast(a, b, "excess", config, True)["difference"] is None
    b[0]["stage"] = "st"
    result = contrast(a, b, "excess", config, True)
    assert result["difference"] == pytest.approx(.1)
    assert result["status"] == "descriptive_only"
    assert result["control_matched"] == 1


def test_company_bootstrap_preserves_paired_company_effect(config):
    a = [dict(row(1, symbol=f"{i:06}"), excess=i/100+.2) for i in range(40)]
    b = [dict(row(2, symbol=f"{i:06}"), excess=i/100) for i in range(40)]
    result = contrast(a, b, "excess", config, True)
    assert result["status"] == "exploratory_only"
    assert result["difference"] == pytest.approx(.2)
    assert result["ci95"] == pytest.approx([.2, .2])


def test_delisted_return_has_both_terminal_conventions(config):
    config["horizons"] = [2]
    days = [f"2023-01-{i+1:02}" for i in range(5)]
    prices = {"000001": [(days[0], 5), (days[1], 10), (days[2], 8)]}
    trades = {("000001", days[1]): {"buy": True, "known": True}}
    result = observe([row(0)], [row(0)], prices, days, dict.fromkeys(days, 100), trades,
                     {"000001": days[3]}, config)[0]
    assert result["excess"] == -1
    assert result["excess_last"] == pytest.approx(-.2)
    assert result["end_sellable"] is None


def test_price_rank_and_announcement_flags_cannot_see_future(config):
    from types import SimpleNamespace
    cfg = deepcopy(config)
    cfg["windows"].update(position=3, baseline=2, activity=2)
    days = [f"2023-01-{i+1:02}" for i in range(6)]
    facts = [SimpleNamespace(symbol="000001", trade_date=d, eligible_for_anomaly=True,
                             turnover_rate_f=2, total_share_10k=100) for d in days]
    features = [dict(symbol="000001", trade_date=d, baseline_observations=2,
                     cum_turnover_log_excess_20=3, elevated_day_ratio_20=.5,
                     excess_return_st_20=0, single_day_amplitude_ratio=1) for d in days]
    prices = {"000001": list(zip(days, [10, 9, 8, 7, 6, 5]))}
    args = (features, facts, prices, days, dict.fromkeys(days, {"000001"}), {}, [], [], cfg)
    before, _ = make_grid(*args)
    prices["000001"][-1] = (days[-1], 10000)
    after, _ = make_grid(*args)
    assert before[:-1] == after[:-1]
    announcements = [dict(symbol="000001", announcement_date=days[-1], title="关于重整转增股份的公告", announcement_id="future")]
    flagged, _ = make_grid(features, facts, prices, days, dict.fromkeys(days, {"000001"}), {}, announcements, [], cfg)
    assert flagged[0]["announcement"] == "none_detected"
    assert flagged[0]["capital"] == "none_detected"
    assert flagged[-1]["announcement"] == "detected"
    assert flagged[-1]["capital"] == "detected"
