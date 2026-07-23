import json

from query_templates import TEMPLATES, template_for_rules


def test_query_templates_cover_existing_executors() -> None:
    assert len(TEMPLATES) == 9
    assert template_for_rules(["restructuring_next_node_query"]).template_id == "QT-001"
    assert template_for_rules(["stock_st_status_timeline"]).template_id == "QT-003"
    assert template_for_rules(["missing_market_index_series"]).template_id == "QT-005"
    assert template_for_rules(
        ["stock_administrator_history_query"]
    ).template_id == "QT-009"


def test_query_templates_are_explicitly_not_evidence() -> None:
    blob = json.dumps(
        [template.model_dump(mode="json") for template in TEMPLATES],
        ensure_ascii=False,
    )

    assert all(template.not_evidence is True for template in TEMPLATES)
    assert "effect_digest" not in blob
    assert "evidence_grade" not in blob
