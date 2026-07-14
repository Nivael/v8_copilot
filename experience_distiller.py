"""Novelty-gated deterministic conversion from user feedback to experience candidates."""
from __future__ import annotations

from experience_contract import ExperienceCandidateInput, ExperienceFeedbackRequest, ExperienceType


def distill_feedback(
    run_id: str,
    feedback: ExperienceFeedbackRequest,
) -> ExperienceCandidateInput | None:
    if feedback.category == "no_experience" or feedback.feedback_text.strip() in {
        "可以", "这版可以", "好的", "通过", "ok", "OK",
    }:
        return None
    common = {
        "source_run_refs": [run_id],
        "supersedes": [],
    }
    if feedback.category == "presentation":
        return ExperienceCandidateInput(
            experience_type=ExperienceType.PRESENTATION_RULE,
            title="主回答先给判断，再下沉精度",
            value_summary="总览先回答实质差异或当前判断，日期、比例和口径细节放到依据与证据层。",
            trigger_conditions=["比较问题", "阶段问题", "公告摘要问题"],
            scope=["stock", "comparison", "announcement"],
            required_inputs=["validated_evidence_pack"],
            query_plan=["先识别用户真正关心的判断", "再选择最有解释力的证据", "最后补充口径与缺口"],
            definitions=["主回答可脱离证据明细单独读懂"],
            answer_rubric=["首段直接回答", "只保留影响判断的关键数字", "不确定性单列"],
            anti_patterns=["用公告条数或系统口径开头", "把字段清单当作研究判断"],
            coverage_boundaries=["表达规则不改变证据强度，也不提供事实"],
            validation_refs=["regression:judgment_first_readability"],
            **common,
        )
    if feedback.category == "coverage":
        return ExperienceCandidateInput(
            experience_type=ExperienceType.COVERAGE_BOUNDARY,
            title="来源未找到只能收窄到来源口径",
            value_summary="公司正式公告未找到记录，不代表管理人、破产重整平台或其他渠道没有披露。",
            trigger_conditions=["未找到", "尚未披露", "公开招募", "其他渠道"],
            scope=["announcement", "restructuring", "materialized_source"],
            required_inputs=["source_inventory", "coverage_manifest"],
            query_plan=["确认已检索来源", "列出未覆盖渠道", "将结论限定到已覆盖来源"],
            definitions=["来源缺失不等于事实不存在"],
            answer_rubric=["已确认事实先说", "覆盖缺口单列", "避免全口径否定"],
            anti_patterns=["把公司公告未找到写成现实中没有发生"],
            coverage_boundaries=["不能替代对管理人渠道或破产重整平台的独立材料化"],
            validation_refs=["regression:source_absence_scope"],
            **common,
        )
    if feedback.category in {"routing", "query_plan"}:
        return ExperienceCandidateInput(
            experience_type=(
                ExperienceType.ROUTING_RULE if feedback.category == "routing"
                else ExperienceType.QUERY_PLAN
            ),
            title="组合事件先例需要连接验证时点与逐日路径",
            value_summary="遇到‘某节点前是否出现连续价格状态’时，应连接事件截止日、主体范围、ST区间和逐交易日价格。",
            trigger_conditions=["截止日前", "连续跌停", "历史先例"],
            scope=["event_window", "price_path", "restructuring"],
            required_inputs=["verified_event_deadline", "daily_prices", "st_status_history"],
            query_plan=["验证事件起止时点", "限定上市公司本体和ST区间", "连接逐交易日价格", "计算相邻交易日序列"],
            definitions=["连续按相邻交易日定义", "截止日必须来自正文或验证材料"],
            answer_rubric=["先回答有无先例", "给出代表案例", "当前个案未验证前提单列"],
            anti_patterns=["用下一公告等待期代替事件窗口价格检验", "把公告日当截止日"],
            coverage_boundaries=["历史先例不预测当前个案后续", "价格快照后的题面事实不能自动确认"],
            validation_refs=["tests/test_recruitment_precedent.py"],
            **common,
        )
    return ExperienceCandidateInput(
        experience_type=ExperienceType.ANTI_PATTERN,
        title="用户指出的可泛化研究反模式",
        value_summary=feedback.feedback_text,
        trigger_conditions=["同类研究输出再次出现该症状"],
        scope=["research_answer"],
        required_inputs=["research_run", "user_feedback"],
        query_plan=["复现原运行", "识别可泛化原因", "加入最小回归"],
        definitions=["只沉淀可跨问题复用的失败模式"],
        answer_rubric=["修正后仍需重新查询最新证据"],
        anti_patterns=[feedback.feedback_text],
        coverage_boundaries=["单次偏好或单票事实不得晋升为经验"],
        validation_refs=["review:human_feedback"],
        **common,
    )
