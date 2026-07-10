"""
v8 lens binding layer —— v8 的脊梁（D-052 修正案）。

最小闭环：question_card → candidate_lenses → selected_lens_invocations
          → query/checklist/evidence/data_debt execution → answer_card
          →（若无可用 lens）lens_gap → 沉淀为 question_card / data_debt。

答案卡不是最终抽象，**lens invocation 才是**。每张答案卡必须显式记录它调用了
哪些 v7.4 release record、各自 kind、贡献了哪个 answer section；没有可用 lens
时必须写 lens_gap，不得用 sqlite+手写逻辑冒充 lens 消费。

只读冻结 release library（D-049 pinned v1），不读施工中产物。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
RELEASE_LIBRARY = _ROOT / "shared_data/v7/release_library_v1/release_library.json"

# release_role → D-050 lens_kind
_ROLE_TO_KIND = {
    "evidence_lens": "evidence",
    "case_note_evidence": "evidence",          # 但 grade=anecdotal，不聚合
    "methodology_frame": "methodology",
    "data_debt_feature_spec": "data_debt",
    "case_note": "checklist",
}


@dataclass
class LensInvocation:
    release_id: str
    lens_kind: str                 # evidence | methodology | data_debt | checklist
    release_role: str
    contributed_section: str       # 该 lens 贡献了答案的哪一节
    logic_chain_summary: str
    allowed_wording: str = ""       # carry v7.4 v8_allowed_wording
    forbidden_wording: list[str] = field(default_factory=list)
    evidence_grade: str = ""
    cohort_id: str = ""
    provenance_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "release_id": self.release_id,
            "lens_kind": self.lens_kind,
            "release_role": self.release_role,
            "contributed_section": self.contributed_section,
            "logic_chain_summary": self.logic_chain_summary,
            "evidence_grade": self.evidence_grade,
            "cohort_id": self.cohort_id,
            "allowed_wording": self.allowed_wording,
            "forbidden_wording": self.forbidden_wording,
            "provenance_refs": self.provenance_refs,
        }


class LensRegistry:
    """只读加载 pinned v1 release library，并按主题/cluster 检索候选 lens。"""

    def __init__(self, path: Path = RELEASE_LIBRARY):
        if not path.exists():
            raise FileNotFoundError(f"frozen release library 不存在: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"frozen release library JSON 非法: {path}: {exc}") from exc

        self._validate_library(data, path)
        self.path = path
        self.available = True
        self.records = data["records"]
        self.library_version = data["library_version"]
        self.frozen_at = data["frozen_at"]
        self.schema_version = data.get("schema_version", "v74_release_library_schema_v1")

    @staticmethod
    def _validate_library(data: Any, path: Path) -> None:
        if not isinstance(data, dict):
            raise ValueError(f"frozen release library 顶层必须是 object: {path}")
        for field_name in ("library_version", "frozen_at", "records"):
            if not data.get(field_name):
                raise ValueError(f"frozen release library 缺字段 {field_name}: {path}")
        records = data["records"]
        if not isinstance(records, list):
            raise ValueError(f"frozen release library records 必须是 list: {path}")

        release_ids: set[str] = set()
        required = {"release_id", "release_role", "logic_chain_summary", "provenance_refs"}
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise ValueError(f"release record[{index}] 必须是 object: {path}")
            missing = sorted(field_name for field_name in required if not record.get(field_name))
            if missing:
                raise ValueError(f"release record[{index}] 缺字段 {missing}: {path}")
            release_id = str(record["release_id"])
            if release_id in release_ids:
                raise ValueError(f"release_id 重复: {release_id}: {path}")
            release_ids.add(release_id)
            release_role = str(record["release_role"])
            if release_role not in _ROLE_TO_KIND:
                raise ValueError(f"release_role 非法: {release_role}: {release_id}: {path}")
            if release_role == "evidence_lens":
                evidence_required = {
                    "sample_n", "cohort_id", "evidence_grade",
                    "validation_report_ref", "v8_allowed_wording",
                }
                evidence_missing = sorted(
                    field_name for field_name in evidence_required if not record.get(field_name)
                )
                if evidence_missing:
                    raise ValueError(
                        f"evidence record {release_id} 缺字段 {evidence_missing}: {path}"
                    )

    def get(self, release_id: str) -> dict[str, Any]:
        for record in self.records:
            if record.get("release_id") == release_id:
                return record
        raise KeyError(f"release library 中无 {release_id}")

    @staticmethod
    def _topic_label(record: dict[str, Any]) -> str:
        """lens 的主题标签 = logic_chain_summary 冒号前缀（如 '重大资产重组 / 资产注入'）。
        只在这个稳定标签上做主题匹配，避免命中正文里的偶发词（如日历 lens 正文提到'重整'）。"""
        s = str(record.get("logic_chain_summary", ""))
        for sep in ("：", ":"):
            if sep in s:
                return s.split(sep, 1)[0]
        return s[:40]

    def candidate_lenses(self, *, clusters: list[str] | None = None,
                         topic_terms: list[str] | None = None) -> list[dict[str, Any]]:
        """精确匹配：cluster_id 命中 或 topic_terms 命中主题标签（非全文）。"""
        clusters = clusters or []
        topic_terms = topic_terms or []
        out = []
        for r in self.records:
            hit = False
            if clusters and r.get("cluster_id") in clusters:
                hit = True
            if topic_terms and any(t in self._topic_label(r) for t in topic_terms):
                hit = True
            if hit:
                out.append(r)
        return out

    def invoke(self, record: dict[str, Any], contributed_section: str) -> LensInvocation:
        role = record.get("release_role", "")
        return LensInvocation(
            release_id=record.get("release_id", "?"),
            lens_kind=_ROLE_TO_KIND[role],
            release_role=role,
            contributed_section=contributed_section,
            logic_chain_summary=str(record.get("logic_chain_summary", "")),
            allowed_wording=str(record.get("v8_allowed_wording", "")),
            forbidden_wording=list(record.get("v8_forbidden_wording", []) or []),
            evidence_grade=str(record.get("evidence_grade", "") or ""),
            cohort_id=str(record.get("cohort_id", "") or ""),
            provenance_refs=list(record.get("provenance_refs", []) or []),
        )


@dataclass
class LensGap:
    """无可用 lens 时的显式缺口，必须沉淀为 question_card 或 data_debt。"""
    gap_id: str                     # AnswerCard 内稳定引用 id
    missing_for: str                # 哪个 answer section 缺 lens
    sediment_as: str                # question_card:QC-xxx | data_debt:D-xxx
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "missing_for": self.missing_for,
            "sediment_as": self.sediment_as,
            "note": self.note,
        }
