"""Deterministic smoke for the EvidencePack → validation workbench path."""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_contract import ResearchRequest
from evidence_gateway import ResearchDraft, build_evidence_pack, validate_research_draft
from research_repository import ExperienceRepository
from settings import EXPERIENCE_REPOSITORY_DB


CASES = [
    "南都最新的公告具体说了什么？",
    "沐邦的公开招募推进到哪一步了？下一个节点可能是什么？",
    "沐邦和南都怎么比较？",
    "分析一下 ST 闻泰。",
    "沐邦今天7月14号跌停，有在公开招募截止前连续跌停的先例吗？",
]


def main() -> int:
    repository = ExperienceRepository(EXPERIENCE_REPOSITORY_DB)
    results: list[dict[str, object]] = []
    for question in CASES:
        pack = build_evidence_pack(
            ResearchRequest(question=question, llm_mode="off"),
            experience_repository=repository,
        )
        narrative = pack.deterministic_response.get("narrative")
        if narrative is None:
            raise AssertionError(f"workbench baseline 缺 narrative: {question}")
        report = validate_research_draft(
            pack,
            ResearchDraft.model_validate({"narrative": narrative}),
        )
        direct = str(narrative["direct_answer"]["text"])
        if not report.valid:
            raise AssertionError(f"workbench validation failed: {question}: {report.issues}")
        if direct.startswith(("本分析", "本题", "查询结果", "描述性查询")):
            raise AssertionError(f"workbench answer opening is indirect: {question}")
        results.append({
            "question": question,
            "pack_id": pack.pack_id,
            "row_count": len(pack.rows),
            "experience_hits": len(pack.applicable_experiences),
            "valid": report.valid,
        })
    print(json.dumps({"passed": len(results), "cases": results}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
