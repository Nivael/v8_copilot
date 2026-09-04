import json

import pytest

from p8_backfill_market_activity import _retry_dates


def test_retry_dates_are_strict_subset_bound_to_frozen_plan(tmp_path):
    plan = {"plan_id": "P1", "content_digest": "D1"}
    report = tmp_path / "prior.json"
    report.write_text(json.dumps({
        "source_plan_id": "P1", "source_plan_digest": "D1",
        "result": {"failures": {"2021-05-18": "limited"}},
    }))
    assert _retry_dates(
        plan=plan, planned_dates=["2021-05-18", "2021-05-19"], retry_report=report,
    ) == ["2021-05-18"]


def test_retry_dates_reject_mismatched_or_out_of_plan_report(tmp_path):
    plan = {"plan_id": "P1", "content_digest": "D1"}
    report = tmp_path / "prior.json"
    report.write_text(json.dumps({
        "source_plan_id": "P2", "source_plan_digest": "D1",
        "result": {"failures": {"2021-05-18": "limited"}},
    }))
    with pytest.raises(ValueError, match="不匹配"):
        _retry_dates(plan=plan, planned_dates=["2021-05-18"], retry_report=report)
    report.write_text(json.dumps({
        "source_plan_id": "P1", "source_plan_digest": "D1",
        "result": {"failures": {"2022-01-01": "limited"}},
    }))
    with pytest.raises(ValueError, match="合法失败日期"):
        _retry_dates(plan=plan, planned_dates=["2021-05-18"], retry_report=report)
