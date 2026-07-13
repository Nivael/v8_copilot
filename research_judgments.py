"""Small evidence-derived judgments shared by deterministic and LLM narratives."""
from __future__ import annotations

from dataclasses import dataclass
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
    )


def comparison_direction_contradiction(
    text: str,
    insight: ComparisonPhaseInsight,
) -> bool:
    """Detect a directional statement that reverses an evidence-derived order."""
    later, earlier = insight.later_label, insight.earlier_label
    if not later or not earlier:
        return False
    compact = "".join(str(text or "").split())
    if f"{later}落后于{earlier}" in compact or f"{later}不如{earlier}" in compact:
        return True
    markers = ("更深入", "更进一步", "更靠后", "领先")
    for marker in markers:
        offset = 0
        while True:
            marker_at = compact.find(marker, offset)
            if marker_at < 0:
                break
            before = compact[:marker_at]
            later_at, earlier_at = before.rfind(later), before.rfind(earlier)
            nearest_at = max(later_at, earlier_at)
            if nearest_at >= 0:
                nearest = later if later_at > earlier_at else earlier
                prefix = before[:nearest_at]
                other_at = earlier_at if nearest == later else later_at
                is_comparison_object = any(
                    prefix.endswith(comparator)
                    for comparator in ("比", "较", "相较于", "相比于")
                ) and other_at >= 0
                subject = (
                    earlier if nearest == later else later
                ) if is_comparison_object else nearest
                if subject == earlier:
                    return True
            offset = marker_at + len(marker)
    return False
