from p8_review_panel import build_queue, render_html


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


def test_conflicts_are_compressed_into_optional_visual_cluster() -> None:
    funnel = {"as_of": "2026-09-03", "run_id": "funnel", "source_run_ids": [], "items": []}
    backtest = {
        "source_run_ids": [],
        "activity_scorecard": {},
        "funnel_scorecard": {"historical_daily_shadow_count": 1},
        "scenario_reference_scorecard": {},
        "extraction_scorecard": {
            "conflict_clusters": {
                "llm_only_node": {
                    "count": 12,
                    "samples": [{
                        "symbol": "000001", "available_as_of": "2026-08-01",
                        "title": "关于重整进展的公告",
                    }],
                }
            }
        },
        "replay_anchors": {},
    }
    queue = build_queue(funnel=funnel, backtest=backtest, dry_plan={}, names={})
    page = render_html(queue=queue, funnel=funnel, backtest=backtest, dry_plan={}, chip={})
    assert "正文抽取冲突簇" in page
    assert "llm_only_node" in page
    assert "不要求逐条审核" in page
