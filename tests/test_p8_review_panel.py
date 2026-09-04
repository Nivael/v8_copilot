from p8_review_panel import build_queue


def test_review_queue_is_optional_and_every_card_has_machine_proposal() -> None:
    funnel = {
        "as_of": "2026-09-03", "run_id": "funnel", "source_run_ids": ["source"],
        "items": [{
            "item_id": "P8FI-AAAAAAAAAAAAAAAAAAAA", "symbol": "000001",
            "as_of": "2026-09-03", "primary_lane": "event_frontier",
            "matched_lanes": ["event_frontier"], "lane_rank": 1,
            "reasons": ["存在程序前沿。"],
            "checks": [{
                "check_id": "official_evidence", "status": "gap",
                "detail": "正文待核证。",
            }],
            "source_ids": ["announcement-1"], "data_gaps": ["body_gap"],
            "risk_flags": [],
        }],
    }
    queue = build_queue(
        funnel=funnel, backtest={"source_run_ids": ["backtest"]},
        dry_plan={"plan_id": "dry"}, names={"000001": "*ST测试"},
    )
    assert queue["human_actions_required"] == 0
    assert len(queue["cards"]) == 1
    card = queue["cards"][0]
    assert card["recommendation"] == "unknown"
    assert {item["value"] for item in card["options"]} == {"keep", "drop", "unknown"}
    assert card["human_action_required"] is False
