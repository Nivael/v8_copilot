"""Frozen, cluster-level backfill of reusable methods from the first 23 audited runs."""
from __future__ import annotations

import argparse
import hashlib
import json

from experience_contract import ExperienceCandidateInput, ExperienceFeedbackRequest, ExperienceType
from experience_distiller import distill_feedback
from research_repository import ExperienceRepository, ResearchRunLedger
from settings import EXPERIENCE_REPOSITORY_DB, RESEARCH_RUN_LEDGER_DB


BACKFILL_VERSION = "v8_experience_backfill_24_runs_v1"


def _candidate(**kwargs) -> ExperienceCandidateInput:
    return ExperienceCandidateInput(**kwargs)


def candidates() -> list[ExperienceCandidateInput]:
    presentation = distill_feedback(
        "RUN-340479D35039407CA45CB250",
        ExperienceFeedbackRequest(feedback_text="先给判断", category="presentation"),
    ).model_copy(update={
        "source_run_refs": [
            "RUN-340479D35039407CA45CB250", "RUN-305D770CCDA8466FAF7BF873",
            "RUN-ECA3F846A35B4042ADB961EE", "RUN-C7A9D716EEDF48E5936C2EA4",
        ]
    })
    coverage = distill_feedback(
        "RUN-ECA3F846A35B4042ADB961EE",
        ExperienceFeedbackRequest(feedback_text="来源边界", category="coverage"),
    ).model_copy(update={
        "source_run_refs": [
            "RUN-ECA3F846A35B4042ADB961EE", "RUN-C7B168B2AEAE4BC990B965E6",
            "RUN-D59EA045DF364CDBB00430D9", "RUN-C7A9D716EEDF48E5936C2EA4",
        ]
    })
    event_path = distill_feedback(
        "RUN-BECD62E8036B429FB97BF9E7",
        ExperienceFeedbackRequest(feedback_text="事件窗口", category="query_plan"),
    ).model_copy(update={
        "source_run_refs": [
            "RUN-BECD62E8036B429FB97BF9E7", "RUN-51AF02BF4B104B839BC2CFC6",
            "RUN-C3DDF9AB5EF140AEB0193E36", "RUN-4F7209C563E24562937EF189",
            "RUN-521F9B9287CA4F1E9F69EB8D",
        ]
    })
    comparison = _candidate(
        experience_type=ExperienceType.REASONING_RULE,
        title="比较题先统一主体，再给单维度实质判断",
        value_summary="先区分上市公司本体和关联主体，并分开共同截止日与各自最新日期；在证据允许时给出程序阶段等单维度判断。",
        trigger_conditions=["两只股票怎么比较", "重整阶段比较", "主体进展比较"],
        topic_tags=["横截面比较", "主体边界", "重整程序"],
        scope=["comparison", "restructuring", "entity_scope"],
        required_inputs=["per_stock_latest_milestone", "common_cutoff", "entity_scope"],
        query_plan=["分别确定本体最新节点", "剔除关联主体混淆", "统一可比口径", "给出最重要的单维度差异"],
        definitions=["共同截止日用于横向数量", "各自最新日期用于当前阶段"],
        answer_rubric=["主回答只有一个清晰方向", "解释主体和时间边界", "不升级为整体优劣"],
        anti_patterns=["同一段出现相反的阶段排序", "用公告条数替代实质比较", "把子公司阶段当本体阶段"],
        coverage_boundaries=["程序节点更深入不等于结果更好或成功率更高"],
        validation_refs=["tests/test_p2_4_analysis_engine.py"],
        source_run_refs=[
            "RUN-340479D35039407CA45CB250", "RUN-305D770CCDA8466FAF7BF873",
            "RUN-334FF66AE2434C8EBF7B7C3E", "RUN-D59EA045DF364CDBB00430D9",
            "RUN-E4440D0BA7404AFBBB9BA9B3",
        ],
    )
    return [presentation, coverage, event_path, comparison,
        _candidate(
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
            source_run_refs=["RUN-ECA3F846A35B4042ADB961EE", "RUN-C7B168B2AEAE4BC990B965E6", "RUN-C7A9D716EEDF48E5936C2EA4"],
        ),
        _candidate(
            experience_type=ExperienceType.REASONING_RULE,
            title="历史结果统计保留未完成案例与右删失",
            value_summary="事件后尚未走到结果日的案例不能被当作失败或从样本中删除；成功、失败、未完成和退市应分别保留。",
            trigger_conditions=["后来走势", "历史成功率", "回复函到摘星", "尚未完成"],
            topic_tags=["历史先例", "事件时点", "状态时序"],
            scope=["historical_outcome", "event_study", "restructuring"],
            required_inputs=["point_in_time_episode", "observation_cutoff", "outcome_status"],
            query_plan=["冻结共同观察截止日", "区分完成与右删失", "保留失败和退市案例"],
            definitions=["右删失表示截至观察日结果尚不可见"],
            answer_rubric=["同时报告分母和删失数", "不把未完成样本塞进成功或失败"],
            anti_patterns=["只统计已经成功的公司", "用当前结果倒填历史时点"],
            coverage_boundaries=["小样本描述不升级为成功概率或交易预测"],
            validation_refs=["regression:right_censoring"],
            source_run_refs=["RUN-BECD62E8036B429FB97BF9E7", "RUN-51AF02BF4B104B839BC2CFC6", "RUN-521F9B9287CA4F1E9F69EB8D", "RUN-C7A9D716EEDF48E5936C2EA4"],
        ),
        _candidate(
            experience_type=ExperienceType.DEFINITION,
            title="纪律处分与资本运作必须按对象和时间分层",
            value_summary="公开谴责、通报批评和监管警示不是同一口径；公司本体与董事高管受罚也不能互换，后续资本运作必须严格晚于处分节点。",
            trigger_conditions=["公开谴责", "通报批评", "监管警示", "后续重组", "发行股票"],
            topic_tags=["监管纪律", "事件时点", "控制权与重组"],
            scope=["discipline", "corporate_action", "chronology"],
            required_inputs=["official_discipline_document", "sanctioned_subject", "corporate_action_announcement"],
            query_plan=["核对处分类型", "识别受罚对象", "验证后续事项日期和工具类型"],
            definitions=["纪律处分类型按交易所正式文书", "受罚对象分公司本体与自然人"],
            answer_rubric=["逐例给出处分来源", "严格按日期先后", "区分现金收购与发行股份"],
            anti_patterns=["把监管警示写成公开谴责", "把高管受罚写成公司被罚"],
            coverage_boundaries=["历史上存在后续资本运作不代表当前公司具备审批条件"],
            validation_refs=["regression:discipline_taxonomy"],
            source_run_refs=["RUN-B5822A45DCA74883B193096B", "RUN-F46AD934B68B469EBC044385", "RUN-E4440D0BA7404AFBBB9BA9B3"],
        ),
        _candidate(
            experience_type=ExperienceType.QUERY_PLAN,
            title="全量ST扫描使用点时成员与共同截止日",
            value_summary="全市场扫描必须按当时 ST 状态开始日构造成员，并把公告、价格和市值统一到共同截止日，不能用当前名单回算历史。",
            trigger_conditions=["所有新进入ST", "全量扫描", "共同截止日", "当前状态"],
            topic_tags=["状态时序", "横截面比较", "事件时点"],
            scope=["full_universe", "point_in_time_membership", "cross_section"],
            required_inputs=["st_status_history", "common_cutoff", "coverage_manifest"],
            query_plan=["按点时状态切成员", "冻结共同截止日", "逐项检查覆盖率"],
            definitions=["新进入 ST 以状态区间开始日定义"],
            answer_rubric=["报告 universe 数量和覆盖率", "缺失项单列", "当前状态与历史节点分开"],
            anti_patterns=["用当前 ST 名单倒算历史", "混用不同股票的最新日期"],
            coverage_boundaries=["覆盖不足时不输出完整横截面排序"],
            validation_refs=["regression:point_in_time_universe"],
            source_run_refs=[
                "RUN-54EB8E76122348ABBB1008CB", "RUN-3009C08DB9D047DEB68181AE",
                "RUN-2E341CBFEC9D4B7A98D74AC1", "RUN-91D435851FE347929D609A49",
                "RUN-A89687341F874BA2AB9E77A4", "RUN-069CD74433354DF0BE65E845",
            ],
        ),
        _candidate(
            experience_type=ExperienceType.COVERAGE_BOUNDARY,
            title="公开硬节点与下一节点判断必须分开",
            value_summary="当前阶段只由已发生的官方硬节点决定；下一节点只能列观察条件和阻力，不能把常见路径写成公司正在筹划。",
            trigger_conditions=["当前阶段", "下一个节点", "很可能筹划", "主要阻力"],
            topic_tags=["重整程序", "控制权与重组", "覆盖边界"],
            scope=["current_stage", "next_milestone", "scenario_boundary"],
            required_inputs=["official_milestones", "current_cutoff", "missing_node"],
            query_plan=["列出已发生硬节点", "指出尚缺的决定性节点", "把历史机制放入旁证"],
            definitions=["当前阶段不使用传闻或历史相似性晋级"],
            answer_rubric=["事实、推断和观察条件分栏", "下一节点使用条件句"],
            anti_patterns=["把可能路径写成已筹划", "用历史案例替代本票正式公告"],
            coverage_boundaries=["历史机制只能解释路径，不证明当前事项会发生"],
            validation_refs=["regression:source_absence_scope"],
            source_run_refs=[
                "RUN-8BF25204E58F4DEB936E27BF", "RUN-39908D1CCB974EC78BDDCB10",
                "RUN-E4440D0BA7404AFBBB9BA9B3", "RUN-2E341CBFEC9D4B7A98D74AC1",
                "RUN-91D435851FE347929D609A49", "RUN-A89687341F874BA2AB9E77A4",
                "RUN-069CD74433354DF0BE65E845", "RUN-E0F1580155504AE2B1829C6B",
            ],
        )]


def build_packet(ledger: ResearchRunLedger) -> dict[str, object]:
    records = candidates()
    missing = sorted({ref for row in records for ref in row.source_run_refs if not _run_exists(ledger, ref)})
    if missing:
        raise ValueError(f"backfill 引用了不存在的运行: {missing}")
    covered = sorted({ref for row in records for ref in row.source_run_refs})
    payload = {
        "backfill_version": BACKFILL_VERSION,
        "source_run_count": len(covered),
        "candidate_cluster_count": len(records),
        "source_run_refs": covered,
        "candidates": [row.model_dump(mode="json") for row in records],
    }
    payload["packet_digest"] = hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return payload


def _run_exists(ledger: ResearchRunLedger, run_id: str) -> bool:
    try:
        ledger.get(run_id)
        return True
    except KeyError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write candidates and run links")
    args = parser.parse_args()
    ledger = ResearchRunLedger(RESEARCH_RUN_LEDGER_DB)
    repository = ExperienceRepository(EXPERIENCE_REPOSITORY_DB)
    packet = build_packet(ledger)
    result: dict[str, object] = {key: value for key, value in packet.items() if key != "candidates"}
    if args.apply:
        records = [repository.propose(ExperienceCandidateInput.model_validate(row)) for row in packet["candidates"]]
        for record in records:
            for run_id in record.source_run_refs:
                if run_id.startswith("RUN-"):
                    ledger.link_experience(run_id, record.experience_id, "backfill_cluster_source")
        result["experience_ids"] = [row.experience_id for row in records]
        result["applied"] = True
    else:
        result["applied"] = False
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
