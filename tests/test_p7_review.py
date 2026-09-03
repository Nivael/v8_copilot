from __future__ import annotations

from datetime import datetime, timezone

import pytest

from p7_review import (
    P7ReviewDecision,
    P7ReviewDecisionExport,
    P7ReviewRepository,
    build_review_queue,
    build_static_panel,
)


def test_review_panel_is_two_decisions_and_import_is_idempotent(tmp_path):
    queue = build_review_queue({
        "announcement": {"announcement_count": 12, "bundle_count": 8, "hard_transition_count": 2},
        "activity": {"checked_through": "2026-08-17", "coverage_pct": 99.5},
        "shadow": {"episode_count": 3, "company_count": 2, "prospective_days": 0},
        "provider": {"exchange_reference_status": "unavailable"},
    })
    assert len(queue.cards) == 2
    assert queue.cards[0].recommendation == "publish_descriptive_only"
    assert queue.cards[1].recommendation == "keep_shadow"
    paths = build_static_panel(queue, tmp_path / "panel")
    assert "file://" not in paths["html"].read_text(encoding="utf-8")
    assert "一键采用全部建议" in paths["html"].read_text(encoding="utf-8")

    export = P7ReviewDecisionExport(
        review_session_id=queue.review_session_id,
        exported_at=datetime.now(timezone.utc).isoformat(),
        source_packet=queue.source_packet,
        decisions=[
            P7ReviewDecision(
                card_id=card.card_id, decision=card.recommendation,
                target_field=card.target_field, affected_area=card.affected_area,
                recommended_decision=card.recommendation,
                question=card.decision_requested,
            )
            for card in queue.cards
        ],
    )
    repository = P7ReviewRepository(tmp_path / "p7.sqlite3")
    repository.save_queue(queue)
    assert all(not row["replayed"] for row in repository.import_decisions(queue, export))
    assert all(row["replayed"] for row in repository.import_decisions(queue, export))
    changed = export.model_copy(deep=True)
    changed.decisions[0].decision = "return_to_data_gap"
    with pytest.raises(ValueError, match="已经导入不同决定"):
        repository.import_decisions(queue, changed)
