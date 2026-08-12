"""Novelty-gated deterministic conversion from user feedback to experience candidates."""
from __future__ import annotations

from experience_contract import ExperienceCandidateInput, ExperienceFeedbackRequest, ExperienceType
from experience_topics import detect_topic_tags
from research_repository import ResearchRunRecord


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
            topic_tags=["答案表达"],
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
            topic_tags=["覆盖边界", "重整程序"],
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
            topic_tags=["事件时点", "价格路径", "历史先例", "重整程序"],
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
        topic_tags=detect_topic_tags(feedback.feedback_text) or ["答案表达"],
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


def distill_run_feedback(
    run: ResearchRunRecord,
    feedback: ExperienceFeedbackRequest,
) -> ExperienceCandidateInput | None:
    """Use the audited run only to choose a reusable template, never as new evidence."""
    topics = set(detect_topic_tags(f"{run.question_text} {feedback.feedback_text}"))
    common = {"source_run_refs": [run.run_id], "supersedes": []}
    if feedback.category == "anti_pattern":
        families = [
            ("主体边界", "混淆上市主体与关联主体的程序", "先冻结法律主体；不得把子公司或孙公司的程序状态写成上市公司本体状态。", "regression:entity_scope_boundary"),
            ("公告证据包", "把关联附件数量当成多个独立事件", "同一事项的正文和附件应还原为一套证据链，不按文件数量累计结论。", "regression:same_day_evidence_bundle"),
            ("事件时点", "用公告日期替代真实事件边界", "申请、回复、决定和生效日必须分开；事件窗口使用正式材料核证的边界。", "tests/test_recruitment_precedent.py"),
            ("监管纪律", "混用纪律处分类型或受罚对象", "公开谴责、通报批评和监管警示，以及公司与自然人受罚，必须分别核对。", "regression:discipline_taxonomy"),
        ]
        selected = next((row for row in families if row[0] in topics), None)
        if selected is not None:
            topic, title, summary, validation_ref = selected
            return ExperienceCandidateInput(
                experience_type=ExperienceType.ANTI_PATTERN,
                title=title,
                value_summary=summary,
                trigger_conditions=[f"同类{topic}研究再次出现该症状"],
                topic_tags=[topic, *sorted(topics - {topic})[:2]],
                scope=["research_answer", run.normalized_intent],
                required_inputs=["research_run", "validated_evidence_pack"],
                query_plan=["复核原运行的对象和时点", "按冻结口径重新查询", "加入对应回归"],
                definitions=["错误模式只约束研究方法，不保存本票事实"],
                answer_rubric=["修正后重新查询最新证据", "明确原错误影响的结论范围"],
                anti_patterns=[summary],
                coverage_boundaries=["单次偏好或单票事实不得晋升为通用反模式"],
                validation_refs=[validation_ref],
                **common,
            )
        return distill_feedback(run.run_id, feedback)
    if feedback.category not in {"routing", "query_plan"}:
        return distill_feedback(run.run_id, feedback)
    if "主体边界" in topics:
        return ExperienceCandidateInput(
            experience_type=ExperienceType.QUERY_PLAN,
            title="跨层级重整比较先冻结上市主体边界",
            value_summary="母公司、子公司和孙公司的程序不能混作同一事件；先确认法律主体和程序关系，再比较上市公司股价路径。",
            trigger_conditions=["母公司", "子公司", "孙公司", "共同重整", "实质合并"],
            topic_tags=["主体边界", "重整程序", "历史先例"],
            scope=["cross_entity", "restructuring", "precedent"],
            required_inputs=["verified_legal_entity", "official_procedure_documents", "daily_prices"],
            query_plan=["识别每个法律主体", "区分并行、协同与实质合并", "统一上市公司价格观察窗口"],
            definitions=["程序关系必须由正式文书支持", "价格主体固定为上市公司本体"],
            answer_rubric=["先列纳入与排除口径", "逐例说明主体关系", "股价观察使用共同截止日"],
            anti_patterns=["把子公司受理写成上市公司受理", "把并行程序写成实质合并"],
            coverage_boundaries=["历史主体关系不推导当前方案必然扩围"],
            validation_refs=["regression:entity_scope_boundary"],
            **common,
        )
    if "公告证据包" in topics:
        return ExperienceCandidateInput(
            experience_type=ExperienceType.QUERY_PLAN,
            title="同日关联公告按一套证据包还原逻辑链",
            value_summary="同日公告及附件应按回复对象、前置问题和结论关系组成证据包，不能把附件数量当成多个独立利好。",
            trigger_conditions=["同日公告", "全部公告", "回复函", "附件", "逻辑链"],
            topic_tags=["公告证据包", "事件时点", "状态时序"],
            scope=["announcement_bundle", "status_removal", "timeline"],
            required_inputs=["same_day_announcements", "announcement_bodies", "status_rules"],
            query_plan=["按披露日收齐正文与附件", "连接问询、回复与决定", "分别判断摘星和摘帽条件"],
            definitions=["同一回复事项的正文与附件是一套证据包"],
            answer_rubric=["先给逻辑链", "条件逐项核对", "未出现的决定不得提前确认"],
            anti_patterns=["按文件数量累计利好", "把回复日当成决定生效日"],
            coverage_boundaries=["回复材料不等于交易所已经作出撤销风险警示决定"],
            validation_refs=["regression:same_day_evidence_bundle"],
            **common,
        )
    return distill_feedback(run.run_id, feedback)
