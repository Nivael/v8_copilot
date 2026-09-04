import pytest

from p8_funnel import (
    _checks, _current_episode_events, _exploration_lane, _persistent_activity_lane, _scenario_lane,
    _verified_event_lane,
)


def _map(family: str, position: float | None = None) -> dict:
    return {
        "symbol": "000001",
        "reference_family": family,
        "reference_status": "distribution" if position is not None else "empty",
        "reference_n": 8 if position is not None else 0,
        "position_pct_in_layer": position,
        "current_old_equity_value": 10.0 if position is not None else None,
        "stage": "formal_restructuring_accepted",
        "stage_source": "p6b3_verified:test",
        "days_since_last_verified_node": 12,
        "next_possible_successors": ["plan_key_terms_disclosed"],
        "scenario_implied_weight": None,
        "distance_to_par_delisting_pct": 0.25,
        "distance_to_mv_delisting_pct": None,
        "data_gaps": ["market_value_delisting_threshold_not_registered"],
    }


def test_five_checks_surface_stage_reference_risk_activity_and_source() -> None:
    event = {
        "available_as_of": "2026-08-20",
        "node": "formal_restructuring_accepted",
        "evidence_status": "deterministic_verified",
        "possible_successors": ["plan_key_terms_disclosed"],
        "source_spans": [{"excerpt": "法院裁定受理公司重整"}],
    }
    checks, gaps, _risks = _checks(
        symbol="000001", event=event,
        activity={"shape_label": "persistent_activity_price_stable"},
        scenario_maps=[
            _map("strategic_entry_reference"),
            _map("failure_exit_reference"),
            _map("public_node_reference"),
        ],
        chip={"holder_status": "observed", "top_list_status": "unknown",
              "block_trade_status": "unknown", "margin_status": "unknown"},
    )
    assert [item.check_id for item in checks] == [
        "official_evidence", "stage_frontier", "scenario_reference",
        "capital_structure_and_risk", "market_activity_context",
    ]
    assert "formal_restructuring_accepted" in checks[1].detail
    assert "p*=unknown" in checks[3].detail
    assert "market_value_delisting_threshold_not_registered" in gaps


def test_scenario_lane_is_tail_only_and_deduplicates_symbol() -> None:
    rows = [
        _map("strategic_entry_reference", 0.05),
        _map("public_node_reference", 0.08),
        {**_map("failure_exit_reference", 0.50), "symbol": "000002"},
    ]
    selected = _scenario_lane(rows)
    assert len(selected) == 1
    assert selected[0]["symbol"] == "000001"
    assert selected[0]["position_pct_in_layer"] == 0.05


def test_funnel_event_context_cannot_cross_current_membership_boundary() -> None:
    events = [
        {"symbol": "000001", "available_as_of": "2026-01-10", "event_id": "old"},
        {"symbol": "000001", "available_as_of": "2026-08-10", "event_id": "current"},
        {"symbol": "000002", "available_as_of": "2026-08-10", "event_id": "not-current-member"},
    ]
    selected = _current_episode_events(
        events,
        [{"symbol": "000001", "membership_start_date": "2026-07-01"}],
        current_symbols={"000001"}, as_of="2026-09-03",
    )
    assert [item["event_id"] for item in selected] == ["current"]

    with pytest.raises(ValueError, match="缺 frontier"):
        _current_episode_events(
            events, [], current_symbols={"000001"}, as_of="2026-09-03",
        )


def test_persistent_lane_excludes_single_day_and_same_day_announcement_reactions() -> None:
    rows = [
        {"symbol": "000001", "shape_label": "persistent_activity_price_stable", "single_day_strict_input": False},
        {"symbol": "000002", "shape_label": "persistent_activity_price_down", "single_day_strict_input": True},
        {"symbol": "000003", "shape_label": "single_day_activity_price_jump", "single_day_strict_input": True},
        {"symbol": "000004", "shape_label": "persistent_activity_price_stable", "single_day_strict_input": False},
    ]
    selected = _persistent_activity_lane(rows, same_day_event_symbols={"000004"})
    assert [item["symbol"] for item in selected] == ["000001"]


def test_event_lane_rejects_title_only_and_provisional_nodes() -> None:
    rows = [
        {"symbol": "000001", "evidence_status": "body_verified"},
        {"symbol": "000002", "evidence_status": "deterministic_verified"},
        {"symbol": "000003", "evidence_status": "title_derived"},
        {"symbol": "000004", "evidence_status": "provisional_body"},
    ]
    assert [item["symbol"] for item in _verified_event_lane(rows)] == ["000001", "000002"]


def test_exploration_lane_uses_frozen_evidence_order_not_symbol_order() -> None:
    events = [
        {"symbol": "900001"},
        {"symbol": "800001"},
    ]
    activity = [
        {"symbol": "900001"},
        {"symbol": "800001"},
    ]
    chips = [
        {
            "symbol": "000001", "top_list_status": "not_triggered_in_complete_cross_section",
            "top_institution_status": "not_reported_in_complete_cross_section",
            "block_trade_status": "none_in_complete_cross_section",
            "holder_change_pct": -0.20, "holder_latest_announcement_date": "2026-08-01",
        },
        {
            "symbol": "700001", "top_list_status": "triggered",
            "top_institution_status": "not_reported_in_complete_cross_section",
            "block_trade_status": "none_in_complete_cross_section",
            "holder_change_pct": None, "holder_latest_announcement_date": "",
        },
    ]
    selected = _exploration_lane(events, activity, chips)
    assert [item["symbol"] for item in selected] == [
        "800001", "900001", "700001", "000001",
    ]
