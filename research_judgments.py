"""Small evidence-derived judgments shared by deterministic and LLM narratives."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True)
class ComparisonPhaseInsight:
    left_label: str
    right_label: str
    left_stage: str
    right_stage: str
    later_label: str | None
    earlier_label: str | None
    directional_judgment: str | None
    left_ref: str = ""
    right_ref: str = ""


def comparison_density_focus(question: str) -> bool:
    normalized = "".join(str(question or "").lower().split())
    return any(term in normalized for term in (
        "公告密度", "公告数量", "公告数", "最近一个月公告", "近30日公告",
    ))


def _stage_label(row: dict[str, Any]) -> str:
    value = str(row.get("各自最新上市公司本体重整里程碑") or "当前快照无记录")
    return value.rsplit("阶段标签：", 1)[-1] if "阶段标签：" in value else value


def _stage_rank(label: str) -> int | None:
    if "法院已裁定受理重整" in label:
        return 3
    if any(term in label for term in ("已进入或启动预重整", "预重整工作推进中")):
        return 2
    if "债权人已提出预重整或重整申请" in label:
        return 1
    return None


def _stock_label(row: dict[str, Any]) -> str:
    status = str(row.get("当前ST状态") or "").strip()
    for prefix in ("*ST", "ST"):
        if status.startswith(prefix) and status[len(prefix):].strip():
            return status[len(prefix):].strip()
    return str(row.get("股票") or "该股票")


def comparison_phase_insight(
    rows: list[dict[str, Any]],
) -> ComparisonPhaseInsight | None:
    comparison_rows = [
        row for row in rows if row.get("记录类型") == "股票并列比较"
    ]
    if len(comparison_rows) != 2:
        return None
    left, right = comparison_rows
    left_label, right_label = _stock_label(left), _stock_label(right)
    left_stage, right_stage = _stage_label(left), _stage_label(right)
    left_rank, right_rank = _stage_rank(left_stage), _stage_rank(right_stage)
    directional: str | None = None
    later_label: str | None = None
    earlier_label: str | None = None
    if left_rank is not None and right_rank is not None and left_rank != right_rank:
        later_label, earlier_label = (
            (left_label, right_label) if left_rank > right_rank
            else (right_label, left_label)
        )
        directional = (
            "在上市公司本体的公开程序维度，"
            f"{later_label}的公开节点比{earlier_label}更深入"
        )
    return ComparisonPhaseInsight(
        left_label=left_label,
        right_label=right_label,
        left_stage=left_stage,
        right_stage=right_stage,
        later_label=later_label,
        earlier_label=earlier_label,
        directional_judgment=directional,
        left_ref=str(left.get("股票") or ""),
        right_ref=str(right.get("股票") or ""),
    )


def comparison_direction_contradiction(
    text: str,
    insight: ComparisonPhaseInsight,
) -> bool:
    """Reject reversed orders and orders that the observed stages cannot support."""
    later, earlier = insight.later_label, insight.earlier_label
    aliases = {
        insight.left_label: insight.left_label, insight.right_label: insight.right_label,
        "前者": insight.left_label, "后者": insight.right_label,
        "第一家": insight.left_label, "第二家": insight.right_label,
        "第一只": insight.left_label, "第二只": insight.right_label,
    }
    for ref, label in ((insight.left_ref, insight.left_label), (insight.right_ref, insight.right_label)):
        if ref:
            aliases[ref] = label
    # An uncertainty in a later clause must not erase an unsupported assertion before it.
    for clause in re.split(r"[。！？!?；;，,\n]", str(text or "")):
        compact = "".join(clause.split())
        if re.search(r"(?:不能|无法|不足以|不宜|不应|难以|不支持).*(?:判断|认定|证明|推断|断言|比较)", compact):
            continue
        if re.search(r"不比|未比|没有比|(?:不|未|没有|并非)(?:明显|显著)?(?:更深入|更进一步|更靠后|领先)", compact):
            continue
        for marker in re.finditer(r"更深入|更进一步|更靠后|领先|落后于|不如", compact):
            before = compact[:marker.start()]
            locations = [(before.rfind(alias), len(alias), label) for alias, label in aliases.items() if alias]
            locations = [item for item in locations if item[0] >= 0]
            if not locations:
                continue
            position, _, subject = max(locations)
            # In "甲比乙更深入", the nearest name is the object, not the subject.
            if before[:position].endswith(("比", "较", "相较于", "相比于")):
                other = [item for item in locations if item[2] != subject]
                if other:
                    subject = max(other)[2]
            if not later or not earlier:
                return True
            expected = earlier if marker.group() in {"落后于", "不如"} else later
            if subject != expected:
                return True
    return False
