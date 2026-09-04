from p8_references import ScenarioReference, build_distribution, scenario_weight


def _reference(symbol: str, board: str, value: float) -> ScenarioReference:
    return ScenarioReference(
        reference_id=f"P8REF-{'A' * 14}{symbol}",
        family="public_node_reference",
        symbol=symbol,
        available_as_of="2026-08-01",
        stage="plan_approved",
        stage_source="body_verified",
        delisting_risk_type="financial",
        board=board,
        regime_version="2024_exit_reform",
        old_equity_value=value,
        value_status="exact_old_equity",
        contamination_flags=[], source_ids=[f"source-{symbol}"],
        evidence_status="body_verified",
    )


def test_distribution_follows_frozen_drop_board_relaxation():
    refs = [
        _reference(f"00000{index}", "主板" if index < 4 else "创业板", float(index))
        for index in range(1, 10)
    ]
    result = build_distribution(
        refs, family="public_node_reference", as_of="2026-09-01",
        stage="plan_approved", risk_type="financial", board="主板",
        regime_version="2024_exit_reform",
    )
    assert result.status == "distribution"
    assert result.relaxation_path == ["drop_board"]
    assert result.n == 9
    assert result.company_n == 9


def test_scenario_weight_fails_closed_and_does_not_clamp():
    assert scenario_weight(current=None, failure=0, success=10) == (None, "input_unknown")
    assert scenario_weight(current=5, failure=10, success=5) == (None, "non_positive_scenario_spread")
    value, status = scenario_weight(current=15, failure=0, success=10)
    assert value == 1.5
    assert status == "outside_scenario_range"


def test_reference_module_does_not_import_activity_or_funnel():
    source = open("p8_references.py", encoding="utf-8").read()
    assert "import p8_activity" not in source
    assert "import p8_funnel" not in source
