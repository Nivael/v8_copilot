from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace

from pydantic import ValidationError

from answer_engine import (
    AnalysisClaim,
    AnswerCard,
    BackingRef,
)
from api_contract import ClaimBacking as ApiClaimBacking
from api_contract_v2 import NarrativeStatement, NarrativeStep, ResearchNarrative
from llm.boundaries import LLM_FORBIDDEN_WORDING
from llm.config import LLMConfigurationError, resolve_model
from llm.providers import LLMProviderError, StructuredLLMProvider
from llm.schemas import (
    BackingEntry,
    FilteredAnswerCard,
    NarrativeClaim,
    NarrativeDraft,
)
from research_judgments import (
    comparison_density_focus,
    comparison_direction_contradiction,
    comparison_phase_insight,
)


COMPOSER_SYSTEM_PROMPT = """你是 ST Research Copilot 的证据分析师。
你只能根据 filtered_answer_card、backing_catalog 和 evidence_summary 生成 claim blocks 和面向研究者的完整 narrative。
先直接回答用户真正问的内容，再用 2-4 个有顺序的 reasoning_steps 解释证据如何支持答案；把不能确认的部分放入 uncertainties，把可核查的后续公开节点放入 watch_items。
主回答是研究判断，不是字段清单：用 2-4 句人话先给出最重要的 1-3 个结论及其意义。不要为了显得精确而罗列所有日期、数量、收盘价或百分比；非关键数字留在证据层。
每个 statement 和每条 claim 都必须引用 backing_catalog 中真实存在的 query_row、lens_invocation、provenance_ref、data_debt 或 lens_gap。
比较题必须先指出最有解释力的实质差异，再补充口径和边界；允许作有 backing 的单一维度判断，例如哪一方公开程序节点更深入，但不得升级成整体优劣、成功率或投资价值排序。公告条数和价格变化通常只作背景，不得替代对用户真正问题的回答。
如果 payload 含 required_research_judgment，它是查询证据机械确定的方向性结论；主回答和所有解释都必须与它方向一致，不得说反。
阶段题必须把当前公开里程碑与历史后续分布分开。研究判断不等于预测：可以说明当前阶段差异及其含义，但不能断言未来结果。
阶段题必须区分当前里程碑日期与公告清单截至日期，不得把清单截至日冒充里程碑日期。
重整阶段历史比例必须说明 episode case 去重口径、起点总数、可观察后续数和右删失数；阶段类别百分比以可观察后续为分母。
公告题必须根据公告正文证据片段总结，不得只复述标题。
巨潮公告ID是披露平台文档标识，不是上市公司正文中的公告编号；只有“公告编号”字段才可称为公告编号。
某一来源未找到记录，只能表述为该来源口径未找到或未披露；不得扩大成现实中尚未发生。若 backing 标出未覆盖渠道，必须单独说明该覆盖缺口。
不得补造数字、日期、事件、因果或证据等级，不得输出买卖、持有、仓位、目标价或排序建议。
数量和日期必须原样保留 backing 中的阿拉伯数字，不要改写成新的中文数量表达。
缺乏 backing 时不要生成该 statement 或 claim。输出只包含结构化字段，不输出 schema 外自由文本。
"""


@dataclass(frozen=True)
class RejectedClaim:
    claim: NarrativeClaim
    reason: str


@dataclass(frozen=True)
class CompositionResult:
    answer_card: AnswerCard
    accepted_claims: list[AnalysisClaim]
    rejected_claims: list[RejectedClaim]
    research_narrative: ResearchNarrative | None = None
    llm_used: bool = True
    degraded_reasons: list[str] | None = None

    def public_payload(self) -> dict:
        """Only validated AnswerCard content may cross the API/UI boundary."""
        return self.answer_card.to_dict()

    def verified_claims_payload(self) -> list[dict]:
        return [
            {
                "text": claim.text,
                "claim_type": claim.claim_type,
                "backing": {
                    "kind": claim.backing.kind,
                    "ref": claim.backing.ref,
                },
            }
            for claim in self.answer_card.analysis_claims
        ]


def _comparison_contradiction(card: AnswerCard, draft: NarrativeDraft) -> str:
    insight = comparison_phase_insight(card.body_rows)
    if (
        insight is None
        or not insight.directional_judgment
        or comparison_density_focus(card.question)
        or draft.narrative is None
    ):
        return ""
    statements = [
        draft.narrative.direct_answer,
        *draft.narrative.reasoning_steps,
        *draft.narrative.uncertainties,
        *draft.narrative.watch_items,
    ]
    for statement in statements:
        if comparison_direction_contradiction(statement.text, insight):
            return statement.text
    return ""


def _compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _numeric_tokens(text: str) -> set[str]:
    tokens: set[str] = set()

    def normalized_number(value: str) -> str:
        return value.replace(",", "").removeprefix("+")

    def mask(pattern: str, formatter) -> None:
        nonlocal text

        def replace_match(match: re.Match[str]) -> str:
            tokens.add(formatter(match))
            return " " * len(match.group(0))

        text = re.sub(pattern, replace_match, text)

    mask(
        r"(?<!\d)(20\d{2})[-/](\d{1,2})[-/](\d{1,2})(?!\d)",
        lambda match: (
            f"date:{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
        ),
    )
    mask(
        r"(?<!\d)(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        lambda match: (
            f"date:{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
        ),
    )
    number = r"[-+]?\d[\d,]*(?:\.\d+)?%?"
    mask(
        rf"(?<![A-Za-z0-9])({number})\s*(?:至|到|~|—|–|-)\s*({number})",
        lambda match: (
            f"range:{normalized_number(match.group(1))}..{normalized_number(match.group(2))}"
        ),
    )
    tokens.update(
        normalized_number(token)
        for token in re.findall(r"(?<![A-Za-z0-9])[-+]?\d[\d,]*(?:\.\d+)?%?", text)
    )
    return tokens


def _unsupported_numbers(text: str, backing_summary: str) -> list[str]:
    unsupported = _numeric_tokens(text) - _numeric_tokens(backing_summary)
    quantity_pattern = (
        r"(?<![下第某每其])[两三四五六七八九十百千万亿]+"
        r"(?:天|周|个?月|年|倍|成)"
    )
    unsupported.update(
        set(re.findall(quantity_pattern, text))
        - set(re.findall(quantity_pattern, backing_summary))
    )
    chinese_percent = r"(?:百分之[一二两三四五六七八九十百千万亿]+|[一二两三四五六七八九十百千万亿]+%)"
    unsupported.update(
        set(re.findall(chinese_percent, text))
        - set(re.findall(chinese_percent, backing_summary))
    )
    return sorted(unsupported)


def _unsupported_source_absence(text: str, backing_summary: str) -> str:
    coverage_markers = (
        "未覆盖渠道", "非公司正式公告渠道", "未覆盖破产重整信息平台",
    )
    if not any(marker in backing_summary for marker in coverage_markers):
        return ""
    absence_phrases = (
        "公开招募尚未推进", "尚未推进到", "尚未公开招募",
        "尚未启动公开招募", "未开展公开招募", "没有公开招募",
    )
    scope_phrases = (
        "正式公告口径", "正式公告清单", "公司正式公告", "公司公告中",
    )
    for clause in re.split(r"[。；：]", text):
        if any(phrase in clause for phrase in absence_phrases) and not any(
            scope in clause for scope in scope_phrases
        ):
            return clause.strip()
    return ""


def _filtered_card(card: AnswerCard) -> FilteredAnswerCard:
    return FilteredAnswerCard(
        question=card.question,
        object_ref=card.object_ref,
        view=card.view,
        as_of=card.as_of,
        sample_scope=card.sample_scope,
        evidence_grade=card.evidence_grade,
        body_rows=card.body_rows,
        caveats=card.caveats,
        data_debt_summary=[
            f"{row.debt_ref}: {row.gap} -> {row.affects}" for row in card.data_debt
        ],
        lens_gap_summary=[
            f"{gap.gap_id}: {gap.missing_for} -> {gap.sediment_as}" for gap in card.lens_gap
        ],
    )


def _backing_catalog(card: AnswerCard) -> list[BackingEntry]:
    entries = [
        BackingEntry(
            kind="query_row",
            ref=str(row["row_id"]),
            summary=_compact_json({key: value for key, value in row.items() if key != "row_id"}),
        )
        for row in card.body_rows
    ]
    entries.extend(
        BackingEntry(
            kind="lens_invocation",
            ref=invocation.release_id,
            summary=_compact_json({
                "lens_kind": invocation.lens_kind,
                "contributed_section": invocation.contributed_section,
                "logic_chain_summary": invocation.logic_chain_summary,
                "evidence_grade": invocation.evidence_grade,
                "cohort_id": invocation.cohort_id,
                "allowed_wording": invocation.allowed_wording,
                "forbidden_wording": invocation.forbidden_wording,
            }),
        )
        for invocation in card.lens_invocations
    )
    entries.extend(
        BackingEntry(
            kind="data_debt",
            ref=row.debt_ref,
            summary=_compact_json({"gap": row.gap, "affects": row.affects}),
        )
        for row in card.data_debt
    )
    entries.extend(
        BackingEntry(
            kind="lens_gap",
            ref=gap.gap_id,
            summary=_compact_json({
                "missing_for": gap.missing_for,
                "sediment_as": gap.sediment_as,
                "note": gap.note,
            }),
        )
        for gap in card.lens_gap
    )
    entries.extend(
        BackingEntry(
            kind="provenance_ref",
            ref=ref,
            summary=_compact_json({"source": ref}),
        )
        for ref in card.provenance
    )
    return entries


def _validated_statement(
    statement: object,
    backing_summaries: dict[tuple[str, str], str],
    *,
    title: str | None = None,
) -> NarrativeStatement | NarrativeStep:
    text = str(getattr(statement, "text"))
    raw_backing = list(getattr(statement, "backing"))
    keys = [(item.kind, item.ref) for item in raw_backing]
    missing = [key for key in keys if key not in backing_summaries]
    if missing:
        raise ValidationError.from_exception_data(
            "StructuredNarrativeDraft",
            [{"type": "value_error", "loc": ("backing",), "input": keys,
              "ctx": {"error": ValueError(f"backing 不在可引用目录: {missing}")}}],
        )
    hit = [term for term in LLM_FORBIDDEN_WORDING if term in text]
    if hit:
        raise ValidationError.from_exception_data(
            "StructuredNarrativeDraft",
            [{"type": "value_error", "loc": ("text",), "input": text,
              "ctx": {"error": ValueError(f"命中禁用交易措辞: {hit}")}}],
        )
    combined = " ".join(backing_summaries[key] for key in keys)
    unsupported_absence = _unsupported_source_absence(text, combined)
    if unsupported_absence:
        raise ValidationError.from_exception_data(
            "StructuredNarrativeDraft",
            [{"type": "value_error", "loc": ("text",), "input": text,
              "ctx": {"error": ValueError(
                  f"来源缺失被扩大为现实未发生: {unsupported_absence}"
              )}}],
        )
    if title is not None:
        normalized_title = re.sub(
            r"^\s*[一二三四五六七八九十0-9]+[.、：:]\s*", "", title
        )
        title_hit = [term for term in LLM_FORBIDDEN_WORDING if term in title]
        if title_hit:
            raise ValidationError.from_exception_data(
                "StructuredNarrativeDraft",
                [{"type": "value_error", "loc": ("title",), "input": title,
                  "ctx": {"error": ValueError(f"标题命中禁用交易措辞: {title_hit}")}}],
            )
        title_unsupported = _unsupported_numbers(normalized_title, combined)
        if title_unsupported:
            raise ValidationError.from_exception_data(
                "StructuredNarrativeDraft",
                [{"type": "value_error", "loc": ("title",), "input": title,
                  "ctx": {"error": ValueError(
                      f"标题含 backing 未出现的数字: {title_unsupported}"
                  )}}],
            )
    unsupported = _unsupported_numbers(text, combined)
    if unsupported:
        raise ValidationError.from_exception_data(
            "StructuredNarrativeDraft",
            [{"type": "value_error", "loc": ("text",), "input": text,
              "ctx": {"error": ValueError(f"statement 含 backing 未出现的数字: {unsupported}")}}],
        )
    backing = [ApiClaimBacking(kind=item.kind, ref=item.ref) for item in raw_backing]
    if title is not None:
        return NarrativeStep(title=normalized_title, text=text, backing=backing)
    return NarrativeStatement(text=text, backing=backing)


def _validated_narrative(
    card: AnswerCard,
    draft: object | None,
    backing_summaries: dict[tuple[str, str], str],
) -> tuple[ResearchNarrative | None, int]:
    if draft is None:
        return None, 0
    try:
        direct = _validated_statement(draft.direct_answer, backing_summaries)
    except ValidationError:
        return None, 1
    rejected = 0

    insight = comparison_phase_insight(card.body_rows)
    if (
        insight is not None
        and insight.directional_judgment
        and not comparison_density_focus(card.question)
        and "更深入" not in direct.text
    ):
        row_backings = [
            ApiClaimBacking(kind="query_row", ref=str(row["row_id"]))
            for row in card.body_rows
            if row.get("记录类型") == "股票并列比较" and row.get("row_id")
        ]
        backing_by_key = {
            (item.kind, item.ref): item for item in [*row_backings, *direct.backing]
        }
        direct = NarrativeStatement(
            text=f"{insight.directional_judgment}。{direct.text}",
            backing=list(backing_by_key.values())[:10],
        )

    def collect(items: list[object], *, with_title: bool = False) -> list:
        nonlocal rejected
        accepted = []
        for item in items:
            try:
                accepted.append(_validated_statement(
                    item,
                    backing_summaries,
                    title=getattr(item, "title") if with_title else None,
                ))
            except ValidationError:
                rejected += 1
        return accepted

    steps = collect(list(draft.reasoning_steps), with_title=True)[:4]
    uncertainties = collect(list(draft.uncertainties))[:3]
    watch_items = collect(list(draft.watch_items))[:3]
    stage_row = next((
        row for row in card.body_rows
        if row.get("记录类型") == "同阶段历史后续"
        and row.get("后续口径") == "下一个不同重整阶段"
    ), None)
    if stage_row is not None:
        uncertainty_text = " ".join(item.text for item in uncertainties)
        observed = stage_row.get("可观察后续总数")
        censored = stage_row.get("未观察到后续")
        starts = stage_row.get("起点事件总数")
        if not (
            "episode" in uncertainty_text
            and str(observed) in uncertainty_text
            and str(censored) in uncertainty_text
            and ("右删失" in uncertainty_text or "未观察到后续" in uncertainty_text)
        ):
            uncertainties.append(NarrativeStatement(
                text=(
                    f"历史阶段转移按 episode case 去重：{starts} 个起点中，"
                    f"{observed} 个观察到不同阶段后续，{censored} 个截至快照仍未观察到后续"
                    "（右删失）；阶段类别百分比以可观察到后续的 case 为分母。"
                ),
                backing=[ApiClaimBacking(
                    kind="query_row", ref=str(stage_row["row_id"])
                )],
            ))
    return ResearchNarrative(
        direct_answer=direct,
        reasoning_steps=steps,
        uncertainties=uncertainties,
        watch_items=watch_items,
        basis_note=(
            f"本分析仅组织 {len(card.body_rows)} 行可回链查询证据和 "
            f"{len(card.lens_invocations)} 条冻结 Lens；审阅材料与正文链接单独保留。"
        ),
    ), rejected


class NarrativeComposer:
    def __init__(self, provider: StructuredLLMProvider, *, model: str | None = None) -> None:
        self._provider = provider
        self._model = model

    def compose(self, card: AnswerCard) -> CompositionResult:
        card.validate()
        filtered = _filtered_card(card)
        catalog = _backing_catalog(card)
        payload = {
            "filtered_answer_card": filtered.model_dump(mode="json"),
            "backing_catalog": [entry.model_dump(mode="json") for entry in catalog],
            "evidence_summary": [entry.summary for entry in catalog],
        }
        insight = comparison_phase_insight(card.body_rows)
        if (
            insight is not None
            and insight.directional_judgment
            and not comparison_density_focus(card.question)
        ):
            payload["required_research_judgment"] = insight.directional_judgment
        draft: NarrativeDraft | None = None
        for attempt in range(2):
            draft = self._provider.generate(
                response_model=NarrativeDraft,
                system_prompt=COMPOSER_SYSTEM_PROMPT,
                payload=payload,
                model=resolve_model(self._model),
            )
            contradiction = _comparison_contradiction(card, draft)
            if not contradiction:
                break
            if attempt == 0:
                payload["direction_correction"] = (
                    f"上一版把比较方向说反：{contradiction}。"
                    f"必须改为与 {insight.directional_judgment if insight else ''} 一致。"
                )
                continue
            raise LLMProviderError("LLM 比较方向连续两次与查询证据矛盾")
        if draft is None:
            raise LLMProviderError("LLM 未返回叙述草稿")

        backing_summaries = {(entry.kind, entry.ref): entry.summary for entry in catalog}
        valid_backings = set(backing_summaries)
        accepted: list[AnalysisClaim] = []
        rejected: list[RejectedClaim] = []
        seen: set[tuple[str, str, str]] = {
            (claim.text, claim.backing.kind, claim.backing.ref)
            for claim in card.analysis_claims
        }
        for claim in draft.claims:
            backing_key = (claim.backing.kind, claim.backing.ref)
            hit = [term for term in LLM_FORBIDDEN_WORDING if term in claim.text]
            dedupe_key = (claim.text, *backing_key)
            if backing_key not in valid_backings:
                rejected.append(RejectedClaim(claim, "backing 不在可引用目录"))
                continue
            if hit:
                rejected.append(RejectedClaim(claim, f"命中禁用交易措辞: {hit}"))
                continue
            unsupported_numbers = _unsupported_numbers(
                claim.text, backing_summaries[backing_key]
            )
            if unsupported_numbers:
                rejected.append(RejectedClaim(
                    claim,
                    f"claim 含 backing 未出现的数字: {unsupported_numbers}",
                ))
                continue
            if dedupe_key in seen:
                rejected.append(RejectedClaim(claim, "重复 claim"))
                continue
            seen.add(dedupe_key)
            accepted.append(AnalysisClaim(
                text=claim.text,
                claim_type=claim.claim_type,
                backing=BackingRef(kind=claim.backing.kind, ref=claim.backing.ref),
            ))

        research_narrative, rejected_statements = _validated_narrative(
            card, draft.narrative, backing_summaries
        )
        composed = replace(card, analysis_claims=[*card.analysis_claims, *accepted])
        composed.validate()
        return CompositionResult(
            answer_card=composed,
            accepted_claims=accepted,
            rejected_claims=rejected,
            research_narrative=research_narrative,
            llm_used=True,
            degraded_reasons=(
                [f"LLM 主叙述有 {rejected_statements} 个 statement 未通过 backing 校验，已剔除。"]
                if rejected_statements else []
            ) + (["LLM 未返回可用的主叙述。"] if research_narrative is None else []),
        )

    def compose_or_fallback(self, card: AnswerCard) -> CompositionResult:
        try:
            return self.compose(card)
        except (LLMProviderError, LLMConfigurationError, ValidationError) as exc:
            card.validate()
            return CompositionResult(
                answer_card=card,
                accepted_claims=[],
                rejected_claims=[],
                research_narrative=None,
                llm_used=False,
                degraded_reasons=[f"LLM 叙述生成降级: {type(exc).__name__}"],
            )
