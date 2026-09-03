from __future__ import annotations

from datetime import date, timedelta
import sqlite3

from market_activity import MarketActivityFact
from p7_anomalies import (
    ActivityEpisode, AnomalyRun, P7IntelligenceRepository, build_anomaly_run,
)
from p7_announcements import (
    AnnouncementBundle,
    AnnouncementRun,
    AnnouncementIntelligenceRepository,
    IssuerTransition,
)
from p7_daily import (
    LinkageRepository, LinkageRun, ResearchQueueItem, build_daily_payload,
    build_linkage_run,
)
from market_activity import MarketActivityRepository


def _fact(symbol: str, day: str, turnover: float, market_value: float):
    return MarketActivityFact(
        symbol=symbol, ts_code=f"{symbol}.SZ", name="ST样本", trade_date=day,
        turnover_rate_f=turnover, total_mv_10k_cny=market_value,
        suspension_status="trading", one_price_limit=False,
        terminal_phase_status="not_terminal", eligible_for_anomaly=True,
    )


def test_linkage_keeps_timing_relations_and_shadow_separate():
    start = date(2026, 1, 1)
    calendar = [(start + timedelta(days=index)).isoformat() for index in range(90)]
    facts = []
    for index, day in enumerate(calendar[:70]):
        facts.append(_fact("000001", day, 20 if index == 60 else 1 + index * .01, 10000))
        facts.append(_fact("000002", day, 1 + index * .005, 11000))
    anomaly_run = build_anomaly_run(facts)
    spike_day = calendar[60]
    announcement_day = calendar[63]
    bundle = AnnouncementBundle(
        bundle_id="P7AB-11111111111111111111", symbol="000001",
        announcement_date=announcement_day,
        category="restructuring_and_pre_restructuring", topic_key="受理重整",
        announcement_ids=["A1"], titles=["法院裁定受理公司重整"],
        source_urls=["https://example/A1"], hard_event_types=["court_restructuring_accepted"],
        priority_reasons=["hard_state_transition"], conflict_status="clear",
    )
    transition = IssuerTransition(
        transition_id="P7TR-11111111111111111111", symbol="000001",
        dimension="restructuring", from_state="unknown",
        to_state="formal_restructuring_accepted", event_type="court_restructuring_accepted",
        announced_at=announcement_day, effective_at=announcement_day,
        available_as_of=announcement_day, bundle_id=bundle.bundle_id,
        source_refs=["official_announcement:A1"], evidence_status="verified",
    )
    announcement_run = AnnouncementRun(
        run_id="P7AN-11111111111111111111", generated_at="2026-04-01T00:00:00+00:00",
        start_date=calendar[0], through=calendar[-1], announcement_count=1,
        bundle_count=1, priority_bundle_count=1, hard_transition_count=1,
        category_counts={"restructuring_and_pre_restructuring": 1},
        facts=[], bundles=[bundle], transitions=[transition],
    )
    result = build_linkage_run(
        anomaly_run=anomaly_run, announcement_run=announcement_run,
        trading_calendar=calendar,
    )
    item = next(item for item in result.queue_items if item.symbol == "000001")
    outcome = next(item for item in result.shadow_outcomes if item.symbol == "000001")
    assert item.relation == "activity_before_announcement"
    assert item.priority == "investigate_now"
    assert outcome.horizon_5 is True
    assert outcome.trading_days_to_hard_transition == 3
    assert outcome.exchange_reference_status == "unavailable"
    assert "inference_status" in result.shadow_summary
    assert result.shadow_summary["summary_contract"] == "p7d_shadow_summary_v2"
    assert result.shadow_summary["uncertainty"]["episode_wilson_95"] is not None


def test_weekend_hard_transition_maps_to_next_trading_day():
    anomaly_run = AnomalyRun(
        run_id="P7AR-1234567890ABCDEFABCD", generated_at="2026-01-01T00:00:00Z",
        start_date="2026-01-02", through="2026-01-06", fact_count=1,
        calculable_count=1, broad_hit_count=1, balanced_hit_count=1,
        strict_hit_count=0, zero_mad_breakout_count=0,
        episode_counts={"balanced_5": 1}, anomalies=[],
        episodes=[ActivityEpisode(
            episode_id="P7AE-1234567890ABCDEFABCD", symbol="000001",
            profile="balanced", merge_gap=5, start_date="2026-01-02",
            end_date="2026-01-02", hit_count=1, member_dates=["2026-01-02"],
            peak_turnover_rate_f=10, peak_robust_z=5,
        )],
    )
    bundle = AnnouncementBundle(
        bundle_id="P7AB-1234567890ABCDEFABCD", symbol="000001",
        announcement_date="2026-01-03", category="restructuring_and_pre_restructuring",
        topic_key="plan", announcement_ids=["A1"], titles=["法院批准重整计划"],
        source_urls=["https://example/A1"], hard_event_types=["restructuring_plan_approved"],
        priority_reasons=["hard_state_transition"], conflict_status="clear",
    )
    transition = IssuerTransition(
        transition_id="P7TR-1234567890ABCDEFABCD", symbol="000001",
        dimension="restructuring", from_state="unknown", to_state="plan_approved",
        event_type="restructuring_plan_approved", announced_at="2026-01-03",
        effective_at="2026-01-03", available_as_of="2026-01-03",
        bundle_id=bundle.bundle_id, source_refs=["official_announcement:A1"],
        evidence_status="verified",
    )
    announcement_run = AnnouncementRun(
        run_id="P7AN-1234567890ABCDEFABCD", generated_at="2026-01-01T00:00:00Z",
        start_date="2026-01-01", through="2026-01-06", announcement_count=1,
        bundle_count=1, priority_bundle_count=1, hard_transition_count=1,
        category_counts={}, facts=[], bundles=[bundle], transitions=[transition],
    )
    result = build_linkage_run(
        anomaly_run=anomaly_run, announcement_run=announcement_run,
        trading_calendar=[
            "2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07",
            "2026-01-08", "2026-01-09", "2026-01-12",
        ],
    )
    assert result.shadow_outcomes[0].horizon_5 is True
    assert result.shadow_outcomes[0].trading_days_to_hard_transition == 1


def test_post_suspension_recovery_is_excluded_for_five_symbol_observations():
    start = date(2026, 1, 1)
    calendar = [(start + timedelta(days=index)).isoformat() for index in range(70)]
    facts = [_fact("000001", day, 1 + index * .01, 10000) for index, day in enumerate(calendar[:60])]
    facts.append(MarketActivityFact(
        symbol="000001", ts_code="000001.SZ", name="ST样本", trade_date=calendar[60],
        turnover_rate_f=None, total_mv_10k_cny=10000, suspension_status="suspended",
        one_price_limit=None, terminal_phase_status="not_terminal",
        eligible_for_anomaly=False, exclusion_reasons=["suspended"],
    ))
    facts.extend(_fact("000001", day, 2, 10000) for day in calendar[61:67])
    run = build_anomaly_run(facts)
    first_recovery = next(item for item in run.anomalies if item.trade_date == calendar[61])
    sixth_observation = next(item for item in run.anomalies if item.trade_date == calendar[66])
    assert first_recovery.post_suspension is True
    assert "post_suspension_recovery" in first_recovery.exclusion_reasons
    assert first_recovery.calculable is False
    assert sixth_observation.post_suspension is False
    assert sixth_observation.calculable is True


def test_top_n_only_limits_daily_view_and_keeps_canonical_queue(tmp_path):
    day = "2026-08-17"
    activity_database = tmp_path / "activity.sqlite3"
    MarketActivityRepository(activity_database).store_snapshot(
        trade_date=day, facts=[_fact("000001", day, 1, 10000)],
        daily_row_count=1, daily_basic_row_count=1, suspend_row_count=0,
        limit_row_count=1, fetched_at="2026-08-18T00:00:00+00:00",
    )
    intelligence = tmp_path / "p7.sqlite3"
    anomaly = AnomalyRun(
        run_id="P7AR-33333333333333333333", generated_at="2026-08-18T00:00:00+00:00",
        start_date=day, through=day, fact_count=1, calculable_count=0,
        broad_hit_count=0, balanced_hit_count=0, strict_hit_count=0,
        zero_mad_breakout_count=0, episode_counts={}, anomalies=[], episodes=[],
    )
    P7IntelligenceRepository(intelligence).store_anomaly_run(anomaly)
    announcements = AnnouncementRun(
        run_id="P7AN-33333333333333333333", generated_at="2026-08-18T00:00:00+00:00",
        start_date=day, through=day, announcement_count=0, bundle_count=0,
        priority_bundle_count=0, hard_transition_count=0, category_counts={},
        facts=[], bundles=[], transitions=[],
    )
    AnnouncementIntelligenceRepository(intelligence).store(announcements)
    items = [ResearchQueueItem(
        item_id=f"P7QI-{'1' if index == 0 else '2'}{'0' * 19}", symbol=f"00000{index + 1}",
        as_of=day, priority="monitor", relation="activity_without_announcement",
        reasons=["test"], first_check="test",
    ) for index in range(2)]
    linkage = LinkageRun(
        run_id="P7LR-33333333333333333333", generated_at="2026-08-18T00:00:00+00:00",
        through=day, anomaly_run_id=anomaly.run_id, announcement_run_id=announcements.run_id,
        queue_items=items, shadow_outcomes=[], relation_counts={"activity_without_announcement": 2},
        shadow_summary={"mode": "prospective"},
    )
    LinkageRepository(intelligence).store(linkage)
    payload = build_daily_payload(
        as_of=day, activity_database=activity_database,
        intelligence_database=intelligence, top_n=1,
    )
    assert len(payload.research_queue) == 1
    assert payload.overflow_count == 1
    with sqlite3.connect(intelligence) as connection:
        assert connection.execute("select count(*) from research_queue_items").fetchone()[0] == 2
