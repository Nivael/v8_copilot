"""Deterministic Chinese topic normalization for reusable research methods."""
from __future__ import annotations

import re


TOPIC_PATTERNS: dict[str, tuple[str, ...]] = {
    "公告证据包": ("公告", "附件", "回复函", "问询函", "一套证据", "逻辑链"),
    "事件时点": ("截止日", "申请日", "回复日", "决定日", "生效日", "先后", "时点"),
    "价格路径": ("股价", "走势", "跌停", "涨停", "价格路径", "砸盘", "回撤"),
    "历史先例": ("历史", "先例", "案例", "后来", "样本"),
    "重整程序": ("预重整", "重整", "投资人", "招募", "债权申报", "管理人"),
    "主体边界": ("母公司", "上市公司", "子公司", "孙公司", "主体", "实质合并", "协同重整"),
    "状态时序": ("摘星", "摘帽", "st状态", "风险警示", "状态开始日", "退市风险"),
    "监管纪律": ("公开谴责", "通报批评", "监管警示", "纪律处分", "处罚"),
    "控制权与重组": ("控制权", "收购", "资产注入", "重大资产重组", "发行股票"),
    "横截面比较": ("比较", "全量扫描", "同日", "共同截止日", "市值位置"),
    "覆盖边界": ("未找到", "没有披露", "来源", "渠道", "覆盖", "信息不足"),
    "答案表达": ("先给判断", "人话", "总览", "结论", "字段清单"),
}


def normalize_text(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.casefold())


def detect_topic_tags(text: str) -> list[str]:
    normalized = normalize_text(text)
    return [
        topic for topic, phrases in TOPIC_PATTERNS.items()
        if any(normalize_text(phrase) in normalized for phrase in phrases)
    ]


def retrieval_score(question: str, *, topic_tags: list[str], fields: list[str]) -> int:
    """Return an explainable integer score; zero means no useful method match."""
    normalized_question = normalize_text(question)
    question_topics = set(detect_topic_tags(question))
    score = 8 * len(question_topics & set(topic_tags))
    for field in fields:
        normalized = normalize_text(field)
        if len(normalized) >= 2 and normalized in normalized_question:
            score += 4
        elif len(normalized) >= 2 and any(
            normalize_text(phrase) in normalized_question
            for phrase in TOPIC_PATTERNS.get(field, ())
        ):
            score += 2
    return score
