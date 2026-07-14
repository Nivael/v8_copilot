"""Seed generic, reviewable experience candidates from the P2.4 recovery."""
from __future__ import annotations

import json

from experience_contract import ExperienceCandidateInput, ExperienceFeedbackRequest, ExperienceType
from experience_distiller import distill_feedback
from research_repository import ExperienceRepository
from settings import EXPERIENCE_REPOSITORY_DB


MIGRATION_REF = "migration:p2.4-analysis-recovery"


def candidates() -> list[ExperienceCandidateInput]:
    values = [
        distill_feedback(MIGRATION_REF, ExperienceFeedbackRequest(
            feedback_text="总览研究回答要先给判断，不要为了额外精度牺牲可读性。",
            category="presentation",
        )),
        distill_feedback(MIGRATION_REF, ExperienceFeedbackRequest(
            feedback_text="公司公告未覆盖管理人和破产重整信息平台，缺失只能限定到来源口径。",
            category="coverage",
        )),
        distill_feedback(MIGRATION_REF, ExperienceFeedbackRequest(
            feedback_text="截止日前连续跌停先例必须连接截止日和逐交易日价格。",
            category="query_plan",
        )),
        ExperienceCandidateInput(
            experience_type=ExperienceType.REASONING_RULE,
            title="比较题先统一主体，再给单维度实质判断",
            value_summary="先区分上市公司本体和关联主体，并分开共同截止日与各自最新日期；在证据允许时给出程序阶段等单维度判断。",
            trigger_conditions=["两只股票怎么比较", "重整阶段比较", "主体进展比较"],
            scope=["comparison", "restructuring", "entity_scope"],
            required_inputs=["per_stock_latest_milestone", "common_cutoff", "entity_scope"],
            query_plan=["分别确定本体最新节点", "剔除关联主体混淆", "统一可比口径", "给出最重要的单维度差异"],
            definitions=["共同截止日用于横向数量", "各自最新日期用于当前阶段"],
            answer_rubric=["主回答只有一个清晰方向", "解释主体和时间边界", "不升级为整体优劣"],
            anti_patterns=["同一段出现相反的阶段排序", "用公告条数替代实质比较", "把子公司阶段当本体阶段"],
            coverage_boundaries=["程序节点更深入不等于结果更好或成功率更高"],
            validation_refs=["tests/test_p2_4_analysis_engine.py"],
            source_run_refs=[MIGRATION_REF],
        ),
    ]
    return [value for value in values if value is not None]


def main() -> int:
    repository = ExperienceRepository(EXPERIENCE_REPOSITORY_DB)
    records = [repository.propose(candidate) for candidate in candidates()]
    print(json.dumps({
        "candidate_count": len(records),
        "experience_ids": [record.experience_id for record in records],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
