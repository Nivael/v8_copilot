import pytest

from research_judgments import comparison_direction_contradiction, comparison_phase_insight


def insight(left="预重整工作推进中", right="债权人已提出预重整或重整申请"):
    return comparison_phase_insight([
        {"记录类型": "股票并列比较", "股票": "111111", "当前ST状态": "ST甲",
         "各自最新上市公司本体重整里程碑": f"阶段标签：{left}"},
        {"记录类型": "股票并列比较", "股票": "222222", "当前ST状态": "ST乙",
         "各自最新上市公司本体重整里程碑": f"阶段标签：{right}"},
    ])


@pytest.mark.parametrize("text", [
    "乙的公开节点比甲更深入。", "乙的公开节点更进一步。", "222222的程序节点领先。",
    "后者的程序更靠后。", "甲落后于乙。",
])
def test_reversed_comparison_is_rejected_for_names_codes_and_pronouns(text):
    assert comparison_direction_contradiction(text, insight())


@pytest.mark.parametrize("text", [
    "甲的公开节点比乙更深入，但不能据此判断整体优劣。",
    "111111的程序节点更进一步。", "前者的程序领先。", "乙落后于甲。",
    "无法判断谁的节点更深入。", "不能据此认定乙的程序领先。", "乙不比甲更深入。",
])
def test_supported_direction_and_explicit_uncertainty_are_allowed(text):
    assert not comparison_direction_contradiction(text, insight())


@pytest.mark.parametrize("stage", ["已披露重整投资协议", "其他重整进展披露", "预重整工作推进中"])
def test_unknown_or_equal_stages_do_not_support_a_new_direction(stage):
    comparison = insight(stage, stage)
    assert comparison.directional_judgment is None
    assert comparison_direction_contradiction("甲的公开节点比乙更深入。", comparison)
    assert not comparison_direction_contradiction("不能据此判断甲的公开节点比乙更深入。", comparison)


def test_later_caveat_does_not_erase_an_unsupported_assertion():
    assert comparison_direction_contradiction(
        "甲的公开节点比乙更深入，但不能据此判断整体优劣。",
        insight("已披露重整投资协议"),
    )
