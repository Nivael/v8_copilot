"""Build a stable human-readable logic chain from validated response objects."""
from __future__ import annotations

from typing import Any

from api_contract import ClaimBacking, ResearchRequest, VerifiedClaim
from api_contract_v1 import ResearchResponseV1
from api_contract_v2 import (
    BoundaryRewrite,
    NarrativeStatement,
    NarrativeStep,
    ResearchNarrative,
)


_AUDIT_PHRASES = (
    "本地证据表", "M6 事件索引", "pilot 对该股票", "官方公告表提供",
    "机械计算",
)
_FIXED_CAVEAT_PREFIXES = (
    "本卡仅供历史研究", "不输出买卖", "所有结论均受",
)


def _backing(kind: str, ref: str) -> ClaimBacking:
    return ClaimBacking(kind=kind, ref=ref)


def _statement(text: str, kind: str, ref: str) -> NarrativeStatement:
    return NarrativeStatement(text=text, backing=[_backing(kind, ref)])


def _claim_statement(claim: VerifiedClaim) -> NarrativeStatement:
    return NarrativeStatement(text=claim.text, backing=[claim.backing])


def _row_id(row: dict[str, Any]) -> str:
    return str(row.get("row_id") or "")


def _first_row(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], str] | None:
    for row in rows:
        row_id = _row_id(row)
        if row_id:
            return row, row_id
    return None


def _basis_note(card: dict[str, Any]) -> str:
    lens_count = len(card.get("lens_invocations", []))
    if lens_count:
        return f"本题调用 {lens_count} 条适用的冻结 Lens；其余内容来自可回链的本地查询。"
    return "本题没有匹配到适用的冻结 Lens；查询结果只作为描述性证据，不升级为历史先验。"


def _checklist_narrative(card: dict[str, Any]) -> ResearchNarrative:
    rows = list(card.get("body_rows", []))
    first = _first_row(rows)
    if first is None:
        raise ValueError("checklist narrative 缺可回链 body row")
    _, first_id = first
    watch_items = [
        _statement(
            f"{row.get('该看的窗口', '观察窗口')}：{row.get('依据', '回到公开资料逐项核查')}。",
            "query_row",
            _row_id(row),
        )
        for row in rows
        if _row_id(row)
    ]
    uncertainties = [
        _statement(
            "这些窗口只能用于验证事件是否推进，不能推出推进的最晚日期或价格方向。",
            "query_row",
            first_id,
        )
    ]
    platform = next(
        (row for row in rows if row.get("当前机械平台段")),
        None,
    )
    question = "".join(str(card.get("question") or "").lower().split())
    if platform and any(term in question for term in ("从什么时候", "到什么时候", "平台")):
        direct = _statement(
            f"固定带宽机械检测得到的最近平台段为 {platform.get('当前机械平台段')}；"
            f"它不能确认爆发点或最晚推进日期，接下来可核对 {len(watch_items)} 个公开窗口。",
            "query_row",
            _row_id(platform),
        )
    else:
        direct = _statement(
            f"当前证据不能确认所谓“爆发点”或最晚推进日期；可以把问题拆成 {len(watch_items)} 个可验证窗口。",
            "query_row",
            first_id,
        )
    return ResearchNarrative(
        direct_answer=direct,
        reasoning_steps=[NarrativeStep(
            title="先把预测问题改成验证问题",
            text="价格平台本身不说明后续方向；公开公告、风险状态和控制权节点才是可核查的推进信号。",
            backing=[_backing("query_row", first_id)],
        )],
        uncertainties=uncertainties,
        watch_items=watch_items,
        basis_note=_basis_note(card),
    )


def _stock_timeline_narrative(
    card: dict[str, Any],
    claims: list[VerifiedClaim],
) -> ResearchNarrative:
    rows = list(card.get("body_rows", []))
    status = next((row for row in rows if row.get("记录类型") == "状态区间"), None)
    trigger = next((row for row in rows if row.get("记录类型") == "触发公告"), None)
    official = next((row for row in rows if row.get("记录类型") == "近期官方公告"), None)
    episode = next((row for row in rows if row.get("记录类型") == "近期分类节点"), None)
    first = _first_row(rows)
    if first is None:
        raise ValueError("stock timeline narrative 缺可回链 body row")
    _, first_id = first

    if trigger:
        direct = _statement(
            "当前资料能确认 ST 状态区间，并有与状态开始日匹配的一级公告可回链；具体触发原因仍需阅读公告原文。",
            "query_row",
            _row_id(trigger),
        )
    else:
        direct = _statement(
            "当前资料只能确认 ST 状态区间，尚不能仅凭状态简称解释触发原因。",
            "query_row",
            _row_id(status) if status else first_id,
        )

    steps: list[NarrativeStep] = []
    if status:
        steps.append(NarrativeStep(
            title="先确认状态区间",
            text=(
                f"{status.get('状态', '风险警示状态')}自 {status.get('开始日', '未记录')} 起；"
                f"结束日为 {status.get('结束日', '未记录')}。"
            ),
            backing=[_backing("query_row", _row_id(status))],
        ))
    if trigger:
        steps.append(NarrativeStep(
            title="再回到触发公告",
            text=f"一级匹配公告为 {trigger.get('日期', '日期未记录')} 的《{trigger.get('标题', '标题未记录')}》。",
            backing=[_backing("query_row", _row_id(trigger))],
        ))
    if official:
        steps.append(NarrativeStep(
            title="检查状态后的最新披露",
            text=f"近期正式公告包括 {official.get('日期', '日期未记录')} 的《{official.get('标题', '标题未记录')}》。",
            backing=[_backing("query_row", _row_id(official))],
        ))
    if episode:
        steps.append(NarrativeStep(
            title="区分公告与已分类事件",
            text=f"M6 最近分类到的节点为 {episode.get('日期', '日期未记录')} 的《{episode.get('标题', '标题未记录')}》。",
            backing=[_backing("query_row", _row_id(episode))],
        ))

    uncertainty_claims = [
        _claim_statement(claim) for claim in claims
        if claim.claim_type in {"caveat", "data_gap"}
        and not any(phrase in claim.text for phrase in _AUDIT_PHRASES)
    ]
    if not uncertainty_claims:
        uncertainty_claims = [_statement(
            "状态区间描述的是生命周期，不自动解释原因；原因判断必须回到公告原文。",
            "query_row",
            _row_id(trigger) if trigger else (_row_id(status) if status else first_id),
        )]
    return ResearchNarrative(
        direct_answer=direct,
        reasoning_steps=steps,
        uncertainties=uncertainty_claims[:6],
        watch_items=[],
        basis_note=_basis_note(card),
    )


def _stock_overview_narrative(
    card: dict[str, Any],
    claims: list[VerifiedClaim],
) -> ResearchNarrative:
    rows = [row for row in card.get("body_rows", []) if _row_id(row)]
    question = "".join(str(card.get("question") or "").lower().split())
    if any(term in question for term in ("为什么st", "为什么被st", "为何st", "st原因")):
        return _stock_timeline_narrative(card, claims)

    price_coverage = next(
        (row for row in rows if row.get("记录类型") == "公告后价格覆盖"),
        None,
    )
    recent_price = next(
        (row for row in rows if row.get("记录类型") == "近期价格窗口"),
        None,
    )
    announcement_search = next(
        (row for row in rows if row.get("记录类型") == "题面公告检索"),
        None,
    )
    official = next(
        (row for row in rows if row.get("记录类型") == "近期官方公告"),
        None,
    )
    shareholder = next(
        (row for row in rows if row.get("记录类型") == "股东人数"),
        None,
    )
    equity = next(
        (row for row in rows if row.get("记录类型") == "股权事件"),
        None,
    )

    if price_coverage:
        direct = _statement(
            str(price_coverage.get("结论")),
            "query_row",
            _row_id(price_coverage),
        )
        steps = [NarrativeStep(
            title="先核对事件与价格的时间边界",
            text=(
                f"公告日期为 {price_coverage.get('公告日期')}，价格快照截至 "
                f"{price_coverage.get('价格截至')}。"
            ),
            backing=[_backing("query_row", _row_id(price_coverage))],
        )]
        if official:
            steps.append(NarrativeStep(
                title="公告记录",
                text=f"已记录 {official.get('日期')} 的《{official.get('标题')}》。",
                backing=[_backing("query_row", _row_id(official))],
            ))
        uncertainties = [_statement(
            "价格数据未覆盖公告之后的交易日时，不能用公告前的价格替代事件后表现。",
            "query_row",
            _row_id(price_coverage),
        )]
        return ResearchNarrative(
            direct_answer=direct,
            reasoning_steps=steps,
            uncertainties=uncertainties,
            watch_items=[],
            basis_note=_basis_note(card),
        )

    if announcement_search:
        hit_count = int(announcement_search.get("标题与日期命中数") or 0)
        if hit_count and official:
            direct_text = (
                f"当前正式公告清单确认 {official.get('日期')} 的"
                f"《{official.get('标题')}》；当前快照的正文状态为“{official.get('正文状态')}”。"
            )
            direct_ref = _row_id(official)
        else:
            direct_text = (
                "当前可检索的正式公告标题与日期没有命中题面条件；"
                "由于正文未全量采集，不能把标题未命中解释为事项一定未发生。"
            )
            direct_ref = _row_id(announcement_search)
        steps = [NarrativeStep(
            title="检索口径",
            text=(
                f"检索日期：{announcement_search.get('检索日期')}；标题关键词："
                f"{announcement_search.get('标题关键词')}；命中 {hit_count} 条。"
            ),
            backing=[_backing("query_row", _row_id(announcement_search))],
        )]
        if hit_count and official:
            steps.append(NarrativeStep(
                title="最近或题面命中的公告",
                text=f"{official.get('日期')}《{official.get('标题')}》。",
                backing=[_backing("query_row", _row_id(official))],
            ))
        return ResearchNarrative(
            direct_answer=_statement(direct_text, "query_row", direct_ref),
            reasoning_steps=steps,
            uncertainties=[_statement(
                "公告标题只能确认披露存在和主题；涉及原因、条款或是否完成，必须阅读公告正文。",
                "query_row",
                direct_ref,
            )],
            watch_items=[],
            basis_note=_basis_note(card),
        )

    if recent_price:
        changes = "；".join(
            f"{key}{value}"
            for key, value in recent_price.items()
            if key.startswith("近") and key != "记录类型"
        )
        direct_text = (
            f"截至 {recent_price.get('截至')}，最新前复权收盘为 {recent_price.get('最新收盘')}，"
            f"窗口范围为 {recent_price.get('窗口最低')} 至 {recent_price.get('窗口最高')}。"
        )
        steps = [NarrativeStep(
            title="窗口变化",
            text=changes or "当前窗口没有足够记录计算分段变化。",
            backing=[_backing("query_row", _row_id(recent_price))],
        )]
        if official:
            steps.append(NarrativeStep(
                title="同期最新公告",
                text=f"最近正式公告为 {official.get('日期')} 的《{official.get('标题')}》。",
                backing=[_backing("query_row", _row_id(official))],
            ))
        status = next(
            (row for row in rows if row.get("记录类型") == "状态区间"),
            None,
        )
        if status:
            steps.append(NarrativeStep(
                title="风险状态",
                text=f"状态区间从 {status.get('开始日')} 开始，记录状态为 {status.get('状态')}。",
                backing=[_backing("query_row", _row_id(status))],
            ))
        return ResearchNarrative(
            direct_answer=_statement(
                direct_text,
                "query_row",
                _row_id(recent_price),
            ),
            reasoning_steps=steps,
            uncertainties=[_statement(
                "价格窗口为机械历史描述，不解释后续方向。",
                "query_row",
                _row_id(recent_price),
            )],
            watch_items=[],
            basis_note=_basis_note(card),
        )

    if shareholder:
        return ResearchNarrative(
            direct_answer=_statement(
                f"最近一期 {shareholder.get('报告期')} 记录股东人数 {shareholder.get('股东人数')}，"
                f"较上期变化 {shareholder.get('较上期变化率')}。",
                "query_row",
                _row_id(shareholder),
            ),
            reasoning_steps=[],
            uncertainties=[
                _claim_statement(claim) for claim in claims if claim.claim_type == "data_gap"
            ],
            watch_items=[],
            basis_note=_basis_note(card),
        )

    if equity:
        return ResearchNarrative(
            direct_answer=_statement(
                f"最近结构化股权记录为 {equity.get('日期')} 的《{equity.get('标题')}》。",
                "query_row",
                _row_id(equity),
            ),
            reasoning_steps=[],
            uncertainties=[],
            watch_items=[],
            basis_note=_basis_note(card),
        )

    if official:
        return ResearchNarrative(
            direct_answer=_statement(
                f"最近正式公告为 {official.get('日期')} 的《{official.get('标题')}》。",
                "query_row",
                _row_id(official),
            ),
            reasoning_steps=[],
            uncertainties=[],
            watch_items=[],
            basis_note=_basis_note(card),
        )
    return _stock_timeline_narrative(card, claims)


def _timing_narrative(card: dict[str, Any], claims: list[VerifiedClaim]) -> ResearchNarrative:
    rows = [row for row in card.get("body_rows", []) if _row_id(row)]
    if len(rows) < 3:
        raise ValueError("timing narrative 需要三种节点口径")
    direct = NarrativeStatement(
        text=(
            "“下一个节点”没有单一答案：下一个任意公告的中位等待期为 "
            f"{rows[0].get('中位(天)')} 天，下一个已分类重整节点为 {rows[1].get('中位(天)')} 天，"
            f"下一个不同阶段里程碑为 {rows[2].get('中位(天)')} 天。"
        ),
        backing=[_backing("query_row", _row_id(row)) for row in rows[:3]],
    )
    steps = [NarrativeStep(
        title=str(row.get("节点定义") or f"口径 {index}"),
        text=(
            f"样本 N={row.get('N')}；中位 {row.get('中位(天)')} 天；"
            f"均值 {row.get('均值')} 天；中间 50% 位于 {row.get('p25/p75')} 天。"
        ),
        backing=[_backing("query_row", _row_id(row))],
    ) for index, row in enumerate(rows[:3], 1)]
    uncertainties = [
        _claim_statement(claim) for claim in claims
        if claim.claim_type in {"caveat", "data_gap"}
    ]
    return ResearchNarrative(
        direct_answer=direct,
        reasoning_steps=steps,
        uncertainties=uncertainties,
        watch_items=[],
        basis_note=_basis_note(card),
    )


def _two_week_narrative(card: dict[str, Any], claims: list[VerifiedClaim]) -> ResearchNarrative:
    rows = [row for row in card.get("body_rows", []) if _row_id(row)]
    quantiles = next((row for row in rows if "p50" in row), None)
    frequency = next((row for row in rows if "|>10%|" in row), None)
    if quantiles is None:
        raise ValueError("two-week narrative 缺收益分位行")
    direct = _statement(
        (
            f"当前只能确认 ST 面板自身的 T+10 分布：中位数为 {quantiles.get('p50')}，"
            f"5% 到 95% 分位为 {quantiles.get('p05')} 至 {quantiles.get('p95')}。"
        ),
        "query_row",
        _row_id(quantiles),
    )
    steps = [NarrativeStep(
        title="先看分布中心和尾部",
        text=(
            f"25%/75% 分位为 {quantiles.get('p25')}/{quantiles.get('p75')}；"
            "这些是历史横截面描述，不代表未来路径。"
        ),
        backing=[_backing("query_row", _row_id(quantiles))],
    )]
    if frequency:
        steps.append(NarrativeStep(
            title="再看大幅波动出现频率",
            text=(
                f"绝对变化超过 10% 的比例为 {frequency.get('|>10%|')}，"
                f"超过 20% 的比例为 {frequency.get('|>20%|')}。"
            ),
            backing=[_backing("query_row", _row_id(frequency))],
        ))
    return ResearchNarrative(
        direct_answer=direct,
        reasoning_steps=steps,
        uncertainties=[
            _claim_statement(claim) for claim in claims
            if claim.claim_type in {"caveat", "data_gap"}
        ],
        watch_items=[],
        basis_note=_basis_note(card),
    )


def _evidence_narrative(card: dict[str, Any], claims: list[VerifiedClaim]) -> ResearchNarrative:
    rows = [row for row in card.get("body_rows", []) if _row_id(row)]
    if not rows:
        raise ValueError("evidence narrative 缺 evidence row")
    row = rows[0]
    invocation = next(iter(card.get("lens_invocations", [])), None)
    release_id = str((invocation or {}).get("release_id") or row.get("release_id") or "")
    if not release_id:
        raise ValueError("evidence narrative 缺 Lens release_id")
    question = "".join(str(card.get("question") or "").lower().split())
    direction_question = any(term in question for term in (
        "向上", "上涨", "突破", "会涨", "方向", "信号",
    ))
    if direction_question:
        direct = _statement(
            "不能据此判断向上突破或价格方向；该 Lens 只允许描述历史样本中的短窗波动特征。",
            "lens_invocation",
            release_id,
        )
    else:
        direct_claim = next((claim for claim in claims if claim.claim_type == "fact"), None)
        direct = _claim_statement(direct_claim) if direct_claim else _statement(
            "当前记录是带验证材料的历史先验，但必须连同样本量、反例和使用边界一起阅读。",
            "lens_invocation",
            release_id,
        )
    effect = row.get("effect_digest") or {}
    steps = [
        NarrativeStep(
            title="样本范围",
            text=f"触发样本 N={row.get('触发样本N')}；对照样本 N={row.get('对照样本N')}。",
            backing=[_backing("query_row", _row_id(row))],
        ),
        NarrativeStep(
            title="历史结果摘要",
            text="；".join(f"{key}={value}" for key, value in effect.items()) or "当前记录未提供效应摘要。",
            backing=[_backing("query_row", _row_id(row))],
        ),
        NarrativeStep(
            title="反例边界",
            text=str(row.get("反例形状") or "必须同时检查反转和集中贡献的切片。"),
            backing=[_backing("query_row", _row_id(row))],
        ),
    ]
    return ResearchNarrative(
        direct_answer=direct,
        reasoning_steps=steps,
        uncertainties=[],
        watch_items=[],
        basis_note=_basis_note(card),
    )


def _generic_narrative(card: dict[str, Any], claims: list[VerifiedClaim]) -> ResearchNarrative:
    rows = list(card.get("body_rows", []))
    first = _first_row(rows)
    substantive = [
        claim for claim in claims
        if claim.claim_type in {"fact", "inference"}
        and not any(phrase in claim.text for phrase in _AUDIT_PHRASES)
    ]
    if substantive:
        direct = _claim_statement(substantive[0])
    elif first:
        row, row_id = first
        direct = _statement(
            "当前可确认的内容见下方逻辑链；它描述本地记录，不构成方向性判断。",
            "query_row",
            row_id,
        )
    else:
        gap_claim = next((claim for claim in claims if claim.claim_type == "data_gap"), None)
        if gap_claim is None:
            raise ValueError("narrative 缺可回链内容")
        direct = _claim_statement(gap_claim)

    steps = [
        NarrativeStep(
            title=f"依据 {index}",
            text=claim.text,
            backing=[claim.backing],
        )
        for index, claim in enumerate(substantive[1:], 1)
    ]
    uncertainties = [
        _claim_statement(claim) for claim in claims
        if claim.claim_type in {"caveat", "data_gap"}
        and not any(phrase in claim.text for phrase in _AUDIT_PHRASES)
    ]
    watch_items = [
        _claim_statement(claim) for claim in claims if claim.claim_type == "question"
    ]
    return ResearchNarrative(
        direct_answer=direct,
        reasoning_steps=steps[:12],
        uncertainties=uncertainties[:12],
        watch_items=watch_items[:12],
        basis_note=_basis_note(card),
    )


def build_narrative(response: ResearchResponseV1) -> ResearchNarrative | None:
    card = response.answer_card
    if card is None:
        return None
    if response.route.route == "answer_checklist":
        return _checklist_narrative(card)
    if "restructuring_next_node_query" in response.route.matched_rules:
        return _timing_narrative(card, response.claims)
    if "st_panel_two_week_distribution" in response.route.matched_rules:
        return _two_week_narrative(card, response.claims)
    if response.route.route == "answer_evidence":
        return _evidence_narrative(card, response.claims)
    if any(rule in response.route.matched_rules for rule in (
        "stock_st_status_timeline",
    )):
        return _stock_timeline_narrative(card, response.claims)
    if "stock_research_overview" in response.route.matched_rules:
        return _stock_overview_narrative(card, response.claims)
    return _generic_narrative(card, response.claims)


def build_boundary_rewrite(
    request: ResearchRequest,
    response: ResearchResponseV1,
) -> BoundaryRewrite | None:
    if response.route.route != "refuse_or_rewrite":
        return None
    rewritten = next(
        (card.question for card in response.question_cards if card.status == "answerable"),
        "接下来有哪些公开节点和可验证的观察窗口？",
    )
    return BoundaryRewrite(
        message="不能判断是否应采取买卖、持有或仓位行动。",
        rewritten_question=rewritten,
        why="系统可以分析公开事实、历史分布和观察窗口，但不会把这些材料升级成交易指令。",
    )
