from __future__ import annotations

from narrative_builder import _two_week_narrative


def _panel_rows() -> list[dict[str, object]]:
    return [
        {
            "row_id": "st_panel_quantiles",
            "p05": "-25.00%",
            "p25": "-15.00%",
            "p50": "-10.00%",
            "p75": "-4.00%",
            "p95": "+8.00%",
        },
    ]


def test_microcap_narrative_answers_the_cohort_comparison_directly() -> None:
    card = {
        "body_rows": _panel_rows() + [
            {
                "row_id": "microcap_definition",
                "微盘阈值": "20.61亿元",
                "因子日期": "2026-07-06",
                "ST成员数": 211,
                "市值覆盖率": "98.58%",
            },
            {
                "row_id": "microcap_distribution",
                "成员数": 63,
                "有效收益数": 60,
                "收益覆盖率": "95.24%",
                "平均收益": "-11.75%",
                "中位收益": "-14.01%",
            },
            {
                "row_id": "other_st_distribution",
                "成员数": 145,
                "有效收益数": 142,
                "收益覆盖率": "97.93%",
                "平均收益": "-12.40%",
                "中位收益": "-10.67%",
            },
            {
                "row_id": "microcap_comparison_summary",
                "微盘减普通ST平均收益": "+0.65个百分点",
                "微盘减普通ST中位收益": "-3.34个百分点",
            },
        ],
        "source_provenance": [],
    }

    narrative = _two_week_narrative(card, [])

    assert "微盘 ST 平均收益 -11.75%" in narrative.direct_answer.text
    assert "中位收益差 -3.34个百分点" in narrative.direct_answer.text
    assert "不是 alpha 或交易信号" in narrative.direct_answer.text
    assert len(narrative.direct_answer.backing) == 4
    assert "不使用当前市值倒推历史" in narrative.reasoning_steps[0].text


def test_microcap_narrative_surfaces_operational_gap_without_c14_debt() -> None:
    card = {
        "body_rows": _panel_rows() + [{
            "row_id": "microcap_comparison_gap",
            "缺口": "market-factor manifest 不存在",
        }],
        "source_provenance": [],
    }

    narrative = _two_week_narrative(card, [])

    assert "无法完成微盘 ST 与普通 ST 的可靠比较" in narrative.direct_answer.text
    assert "market-factor manifest 不存在" in narrative.direct_answer.text
    assert narrative.direct_answer.backing[0].ref == "microcap_comparison_gap"
