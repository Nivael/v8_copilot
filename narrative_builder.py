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
from research_judgments import comparison_density_focus, comparison_phase_insight


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
    official_rows = [row for row in rows if row.get("记录类型") == "近期官方公告"]
    official = next(
        (row for row in official_rows if any(term in str(row.get("标题") or "") for term in (
            "风险", "异常波动", "重整", "诉讼", "仲裁", "重大", "年度报告", "审计",
        ))),
        official_rows[0] if official_rows else None,
    )
    shareholder = next(
        (row for row in rows if row.get("记录类型") == "股东人数"),
        None,
    )
    equity = next(
        (row for row in rows if row.get("记录类型") == "股权事件"),
        None,
    )
    body = next(
        (row for row in rows if row.get("记录类型") == "公告正文证据"),
        None,
    )
    boundary = next(
        (row for row in rows if row.get("记录类型") == "分析时间边界"),
        None,
    )

    if body and not price_coverage:
        excerpts = list(body.get("正文证据片段") or [])
        preferred_markers = [
            marker for marker in ("公开招募", "投资协议", "申请人", "债权人", "预重整", "重整")
            if marker in question
        ]
        preferred_markers.extend(["公开招募", "申请人", "债权人", "申请对"])
        first_fact = next(
            (item for marker in preferred_markers for item in excerpts if marker in str(item)),
            excerpts[0] if excerpts else "",
        )
        uncertainty = next(
            (item for item in excerpts if any(term in str(item) for term in ("尚未", "能否", "不确定"))),
            next((item for item in excerpts if item != first_fact), ""),
        )
        direct_text = "；".join(str(item) for item in (first_fact, uncertainty) if item)
        steps = [NarrativeStep(
            title=f"正文证据 {index}",
            text=str(item),
            backing=[_backing("query_row", _row_id(body))],
        ) for index, item in enumerate(excerpts[:8], 1)]
        return ResearchNarrative(
            direct_answer=NarrativeStatement(
                text=direct_text or "已取得公告正文，但当前没有抽取到可读证据片段。",
                backing=[_backing("query_row", _row_id(body))],
            ),
            reasoning_steps=steps,
            uncertainties=[_statement(
                "正文片段用于回链核对；事项影响和后续进度仍需以后续正式公告为准。",
                "query_row",
                _row_id(body),
            )],
            watch_items=[],
            basis_note=_basis_note(card),
        )

    if any(term in question for term in ("分析一下", "分析下", "综合分析", "整体分析")):
        status = next((row for row in rows if row.get("记录类型") == "状态区间"), None)
        episode = next((row for row in rows if row.get("记录类型") == "近期分类节点"), None)
        backing_rows = [row for row in (status, official, episode, recent_price) if row]
        direct_parts = []
        if status:
            direct_parts.append(f"当前记录的状态为 {status.get('状态')}，起于 {status.get('开始日')}")
        if official:
            direct_parts.append(f"最近正式公告是 {official.get('日期')}《{official.get('标题')}》")
        if recent_price:
            direct_parts.append(
                f"价格快照截至 {recent_price.get('截至')}，窗口为 {recent_price.get('窗口最低')} 至 {recent_price.get('窗口最高')}"
            )
        steps: list[NarrativeStep] = []
        if status:
            steps.append(NarrativeStep(
                title="先看 ST 生命周期",
                text=f"状态区间：{status.get('开始日')} 至 {status.get('结束日')}，记录为 {status.get('状态')}。",
                backing=[_backing("query_row", _row_id(status))],
            ))
        if boundary:
            coverage = (
                f"公告覆盖ST后={boundary.get('公告覆盖ST后')}，"
                f"价格覆盖ST后={boundary.get('价格覆盖ST后')}，"
                f"事件覆盖ST后={boundary.get('事件覆盖ST后')}"
            )
            steps.append(NarrativeStep(
                title="先守住时间边界",
                text=(
                    f"ST 状态开始于 {boundary.get('ST状态开始')}；公告截至 {boundary.get('公告截至')}，"
                    f"价格截至 {boundary.get('价格截至')}，事件索引截至 {boundary.get('事件索引截至')}；{coverage}。"
                ),
                backing=[_backing("query_row", _row_id(boundary))],
            ))
        if official:
            steps.append(NarrativeStep(
                title="再看近期正式披露",
                text=f"最近正式公告为 {official.get('日期')} 的《{official.get('标题')}》。",
                backing=[_backing("query_row", _row_id(official))],
            ))
        if episode:
            steps.append(NarrativeStep(
                title="区分公告与已分类事件",
                text=f"最近分类节点为 {episode.get('日期')} 的《{episode.get('标题')}》，事件段为 {episode.get('事件段')}。",
                backing=[_backing("query_row", _row_id(episode))],
            ))
        if recent_price:
            steps.append(NarrativeStep(
                title="最后核对价格窗口",
                text="；".join(
                    f"{key}={value}" for key, value in recent_price.items()
                    if key in {"截至", "最新收盘", "窗口最低", "窗口最高", "近20日变化", "近60日变化"}
                ),
                backing=[_backing("query_row", _row_id(recent_price))],
            ))
        uncertainties = [
            _claim_statement(claim) for claim in claims
            if claim.claim_type in {"caveat", "data_gap"}
            and not any(phrase in claim.text for phrase in _AUDIT_PHRASES)
        ]
        return ResearchNarrative(
            direct_answer=NarrativeStatement(
                text="；".join(direct_parts) or "当前快照提供了多维材料，但没有形成可回链的核心事实。",
                backing=[_backing("query_row", _row_id(row)) for row in backing_rows] or [
                    _backing("query_row", _row_id(rows[0]))
                ],
            ),
            reasoning_steps=steps,
            uncertainties=uncertainties[:8],
            watch_items=[],
            basis_note=_basis_note(card),
        )

    if price_coverage:
        observed_changes = [
            f"{key}为{value}"
            for key, value in price_coverage.items()
            if str(key).startswith("T+") and str(key).endswith("变化")
        ]
        direct_text = str(price_coverage.get("结论"))
        if observed_changes:
            direct_text = (
                f"以 {price_coverage.get('基准交易日')} 前复权收盘"
                f" {price_coverage.get('基准收盘')} 为基准，"
                f"{'，'.join(observed_changes)}；{direct_text}。"
            )
        direct = _statement(
            direct_text,
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
        if observed_changes:
            uncertainties = [_statement(
                "只报告当前价格快照已经覆盖的交易日；尚未覆盖的后续窗口不作补推。",
                "query_row",
                _row_id(price_coverage),
            )]
        else:
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

    episode_rows = [
        row for row in rows if row.get("记录类型") == "近期分类节点"
    ]
    if official and episode_rows and any(
        term in question for term in ("哪些公告", "分类事件", "事件节点")
    ):
        official_summary = "；".join(
            f"{row.get('日期')}《{row.get('标题')}》" for row in official_rows[:3]
        )
        episode_summary = "；".join(
            f"{row.get('日期')}《{row.get('标题')}》" for row in episode_rows[:3]
        )
        backing_rows = [*official_rows[:3], *episode_rows[:3]]
        return ResearchNarrative(
            direct_answer=NarrativeStatement(
                text=(
                    f"正式公告库存最近包括：{official_summary}。"
                    f"已分类事件索引最近包括：{episode_summary}。"
                ),
                backing=[
                    _backing("query_row", _row_id(row)) for row in backing_rows
                ],
            ),
            reasoning_steps=[],
            uncertainties=[_statement(
                "公告库存与已分类事件索引覆盖范围不同；未分类公告不能自动视为没有研究价值。",
                "query_row",
                _row_id(official),
            )],
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


def _restructuring_progress_narrative(
    card: dict[str, Any], claims: list[VerifiedClaim]
) -> ResearchNarrative:
    rows = list(card.get("body_rows", []))
    current = next(row for row in rows if row.get("记录类型") == "当前公开里程碑")
    body = next((row for row in rows if row.get("记录类型") == "当前里程碑正文证据"), None)
    historical = [row for row in rows if row.get("记录类型") == "同阶段历史后续"]
    stage_historical = [
        row for row in historical if row.get("后续口径") == "下一个不同重整阶段"
    ]
    any_historical = [
        row for row in historical if row.get("后续口径") == "下一个任意正式公告"
    ]
    direct_text = (
        f"按公司正式公告口径，当前能确认到“{current.get('阶段判断')}”："
        f"{current.get('日期')}《{current.get('标题')}》。"
        f"{current.get('公开招募记录')}；但本题未覆盖{current.get('未覆盖渠道')}，"
        "不能据此判断实际公开招募是否已经开始。"
    )
    direct_backing = [_backing("query_row", _row_id(current))]
    if stage_historical:
        first_stage = stage_historical[0]
        stage_categories = "、".join(
            str(row.get("后续类别")) for row in stage_historical[:2]
        )
        direct_text += (
            f"历史同阶段共 {first_stage.get('起点事件总数')} 个重整案例，"
            f"其中 {first_stage.get('可观察后续总数')} 个观察到不同阶段后续，"
            f"{first_stage.get('未观察到后续')} 个截至快照仍属右删失；"
            f"已观察类别包括{stage_categories}，只作描述性先验。"
        )
        direct_backing.extend(
            _backing("query_row", _row_id(row)) for row in stage_historical[:2]
        )
    direct = NarrativeStatement(
        text=direct_text,
        backing=direct_backing,
    )
    steps = [NarrativeStep(
        title="先核对当前个案",
        text=(
            f"当前里程碑日期为 {current.get('日期')}，公告清单截至 {current.get('公告清单截至')}；"
            f"按正式公告标题判定为“{current.get('阶段判断')}”，"
            "不能把提问中的阶段假设直接当成已发生事实。"
        ),
        backing=[_backing("query_row", _row_id(current))],
    )]
    if body:
        snippets = list(body.get("正文证据片段") or [])
        if snippets:
            steps.append(NarrativeStep(
                title="再读公告正文",
                text="；".join(str(item) for item in snippets[:3]),
                backing=[_backing("query_row", _row_id(body))],
            ))
    displayed_historical = [*stage_historical[:2], *any_historical[:1]]
    for row in displayed_historical:
        steps.append(NarrativeStep(
            title=f"{row.get('后续口径')}：{row.get('后续类别')}",
            text=(
                f"同阶段历史起点重整案例共 {row.get('起点事件总数')} 个；"
                f"其中 {row.get('可观察后续总数')} 个观察到该口径后续，"
                f"{row.get('未观察到后续')} 个截至快照未观察到后续（右删失）。"
                f"该类别出现 {row.get('次数')} 次，占 {row.get('占可观察后续')}，"
                f"等待中位数 {row.get('等待中位数(天)')} 天。"
            ),
            backing=[_backing("query_row", _row_id(row))],
        ))
    return ResearchNarrative(
        direct_answer=direct,
        reasoning_steps=steps,
        uncertainties=[
            _claim_statement(claim) for claim in claims if claim.claim_type in {"caveat", "data_gap"}
        ][:8],
        watch_items=[_statement(
            "本系统只在公司正式公告出现法院受理、公开招募、投资协议或重整计划等节点时更新阶段；其他渠道需另行核查。",
            "query_row",
            _row_id(current),
        )],
        basis_note=_basis_note(card),
    )


def _administrator_history_narrative(
    card: dict[str, Any], claims: list[VerifiedClaim]
) -> ResearchNarrative:
    rows = list(card.get("body_rows", []))
    facts = [row for row in rows if row.get("记录类型") == "管理人任职事实"]
    cases = [row for row in rows if row.get("记录类型") == "管理人节点案例"]
    thresholds = [row for row in rows if row.get("记录类型") == "管理人样本门槛"]
    if not facts:
        return _generic_narrative(card, claims)
    first = facts[0]
    managers = "、".join(dict.fromkeys(
        str(row.get("管理人")) for row in facts if row.get("管理人")
    ))
    direct_text = (
        f"公司正式公告可确认的管理人为{managers}；"
        f"首条可回链任职是 {first.get('生效日')} 的"
        f"{first.get('任职类型')}。"
    )
    direct_backing = [_backing("query_row", _row_id(first))]
    if cases:
        direct_text += (
            f"当前展示 {len(cases)} 个按案件和节点类型去重的历史节点窗口。"
        )
        direct_backing.append(_backing("query_row", _row_id(cases[0])))
    if thresholds:
        minimum = thresholds[0]
        direct_text += (
            f"{minimum.get('管理人')}只有"
            f"{minimum.get('按案件去重样本数')} 个案件，低于"
            f"{minimum.get('生成分布所需最少案件数')} 个门槛，"
            "所以不生成成功率、分布结论或排名。"
        )
        direct_backing.append(_backing("query_row", _row_id(minimum)))

    steps = [NarrativeStep(
        title="先确认任职事实",
        text=(
            f"{first.get('公告标题')}明确记载{first.get('管理人')}，"
            f"参与方式为{first.get('参与方式')}；原文摘录已随答案卡保存。"
        ),
        backing=[_backing("query_row", _row_id(first))],
    )]
    for case in cases[:3]:
        steps.append(NarrativeStep(
            title=f"再看 {case.get('股票')} 的{case.get('节点类型')}窗口",
            text=(
                f"为避免使用披露当日未知信息，基线取 {case.get('基线交易日')}，"
                f"首个可观察交易日为 {case.get('首个可观察交易日')}；"
                f"后20日个股收益 {case.get('任职后20日个股收益(%)')}%，"
                f"相对 ST {case.get('后20日相对ST(百分点)')} 个百分点，"
                f"相对中证2000 {case.get('后20日相对中证2000(百分点)')} 个百分点。"
            ),
            backing=[_backing("query_row", _row_id(case))],
        ))
    return ResearchNarrative(
        direct_answer=NarrativeStatement(text=direct_text, backing=direct_backing),
        reasoning_steps=steps,
        uncertainties=[
            _claim_statement(claim)
            for claim in claims
            if claim.claim_type in {"caveat", "data_gap"}
        ][:8],
        watch_items=[_statement(
            "后续只有在新增法院或公司正式公告出现管理人更换、联合任职或程序节点时才更新事实链。",
            "query_row",
            _row_id(first),
        )],
        basis_note=_basis_note(card),
    )


def _comparison_narrative(card: dict[str, Any], claims: list[VerifiedClaim]) -> ResearchNarrative:
    rows = [row for row in card.get("body_rows", []) if row.get("记录类型") == "股票并列比较"]
    if len(rows) != 2:
        return _generic_narrative(card, claims)
    left, right = rows
    shared_backing = [
        _backing("query_row", _row_id(left)),
        _backing("query_row", _row_id(right)),
    ]
    if comparison_density_focus(str(card.get("question") or "")):
        cutoff = left.get("共同公告截止日")
        left_count = left.get("近30日公告数量(共同截止)")
        right_count = right.get("近30日公告数量(共同截止)")
        if isinstance(left_count, int) and isinstance(right_count, int):
            if left_count > right_count:
                density_judgment = f"{left.get('股票')}在该窗口披露更频繁"
            elif right_count > left_count:
                density_judgment = f"{right.get('股票')}在该窗口披露更频繁"
            else:
                density_judgment = "两者在该窗口披露频率相同"
        else:
            density_judgment = "当前快照只能并列数量，不能稳定判断哪一方更频繁"
        return ResearchNarrative(
            direct_answer=NarrativeStatement(
                text=(
                    f"近30日公告密度按两只股票都覆盖到的共同截止日 {cutoff} 计算："
                    f"{left.get('股票')}有 {left_count} 条正式公告，{right.get('股票')}有 {right_count} 条。"
                    f"{density_judgment}，但公告数量只反映信息披露活跃度，"
                    "不直接代表重整进度、风险高低或整体优劣。"
                ),
                backing=shared_backing,
            ),
            reasoning_steps=[
                NarrativeStep(
                    title="先统一比较窗口",
                    text=f"两边都只统计截至 {cutoff} 的最近30日正式公告，避免用各自不同的最新日期混比。",
                    backing=shared_backing,
                ),
                NarrativeStep(
                    title="再解释数量差异",
                    text=(
                        f"同一窗口内，{left.get('股票')}为 {left_count} 条，"
                        f"{right.get('股票')}为 {right_count} 条；差异描述的是披露频率，不是公告内容的重要性。"
                    ),
                    backing=shared_backing,
                ),
            ],
            uncertainties=[
                _claim_statement(claim) for claim in claims
                if claim.claim_type in {"caveat", "data_gap"}
            ][:3],
            watch_items=[],
            basis_note=_basis_note(card),
        )

    insight = comparison_phase_insight(rows)
    if insight is None:
        return _generic_narrative(card, claims)
    left_label, right_label = insight.left_label, insight.right_label
    left_stage, right_stage = insight.left_stage, insight.right_stage
    phase_judgment = insight.directional_judgment or (
        "两者当前公开重整节点不能仅凭阶段标签拉开明确先后"
    )

    def price_direction(value: object) -> str:
        try:
            number = float(str(value).removesuffix("%"))
        except ValueError:
            return "当前快照无可读方向"
        if number > 0:
            return "为正"
        if number < 0:
            return "为负"
        return "大致持平"

    def related_summary(row: dict[str, Any]) -> str:
        value = str(row.get("各自最新关联主体重整事项") or "")
        if "未找到关联主体重整事项" in value:
            return "正式公告清单未找到关联主体重整事项"
        if "孙公司" in value:
            return "有孙公司重整事项，须与上市公司本体分开"
        if "子公司" in value:
            return "有子公司重整事项，须与上市公司本体分开"
        if "控股股东" in value:
            return "有控股股东重整事项，须与上市公司本体分开"
        return "有已披露的关联主体重整事项" if value else "当前快照无记录"

    left_change, right_change = left.get("近20日变化"), right.get("近20日变化")
    price_context = (
        f"价格快照中两者近20日方向不同（{left_label}{price_direction(left_change)}，"
        f"{right_label}{price_direction(right_change)}）"
        if left_change and right_change else "价格快照覆盖不足"
    )
    steps = [
        NarrativeStep(
            title="先看最实质的程序差异",
            text=(
                f"{left_label}的各自最新上市公司本体节点为“{left_stage}”；"
                f"{right_label}为“{right_stage}”。{phase_judgment}。"
            ),
            backing=shared_backing,
        ),
        NarrativeStep(
            title="再分清时间与主体口径",
            text=(
                f"公告数量只能比较到共同截止日 {left.get('共同公告截止日')}；各自最新节点则保留各自日期。"
                f"关联主体事项也必须与上市公司本体分开：{left_label}{related_summary(left)}；"
                f"{right_label}{related_summary(right)}。"
            ),
            backing=shared_backing,
        ),
        NarrativeStep(
            title="其他指标只作背景",
            text=(
                f"两者都处于风险警示状态；{price_context}。"
                "公告活跃度和价格方向不能替代重整程序判断，也不能推出整体优劣。"
            ),
            backing=shared_backing,
        ),
    ]
    return ResearchNarrative(
        direct_answer=NarrativeStatement(
            text=(
                f"如果重点是重整进度，{phase_judgment}：{left_label}当前公开节点为“{left_stage}”，"
                f"{right_label}为“{right_stage}”。这说明两者公开程序位置不同，"
                "不能据此推断重整成功率或投资价值；公告数量和价格表现只应放在背景层阅读。"
            ),
            backing=shared_backing,
        ),
        reasoning_steps=steps,
        uncertainties=[
            _claim_statement(claim) for claim in claims if claim.claim_type in {"caveat", "data_gap"}
        ][:8],
        watch_items=[NarrativeStatement(
            text="后续应分别核查两家上市公司本体是否出现法院启动、正式受理或新的重整方案节点，并继续把关联主体事项单列。",
            backing=shared_backing,
        )],
        basis_note=_basis_note(card),
    )


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
    definition = next(
        (row for row in rows if _row_id(row) == "microcap_definition"), None,
    )
    microcap = next(
        (row for row in rows if _row_id(row) == "microcap_distribution"), None,
    )
    other = next(
        (row for row in rows if _row_id(row) == "other_st_distribution"), None,
    )
    comparison = next(
        (row for row in rows if _row_id(row) == "microcap_comparison_summary"), None,
    )
    comparison_gap = next(
        (row for row in rows if _row_id(row) == "microcap_comparison_gap"), None,
    )

    if definition and microcap and other and comparison:
        shared_backing = [
            _backing("query_row", _row_id(row))
            for row in (definition, microcap, other, comparison)
        ]
        direct = NarrativeStatement(
            text=(
                f"按收益窗口起点总市值划分（最小 30%，阈值 {definition.get('微盘阈值')}），"
                f"微盘 ST 平均收益 {microcap.get('平均收益')}、中位收益 {microcap.get('中位收益')}；"
                f"普通 ST 平均收益 {other.get('平均收益')}、中位收益 {other.get('中位收益')}。"
                f"微盘相对普通 ST 的平均收益差 {comparison.get('微盘减普通ST平均收益')}，"
                f"中位收益差 {comparison.get('微盘减普通ST中位收益')}。"
                "这只是该窗口的历史横截面描述，不是 alpha 或交易信号。"
            ),
            backing=shared_backing,
        )
        steps = [
            NarrativeStep(
                title="先冻结市值口径",
                text=(
                    f"市值因子取自 {definition.get('因子日期')}，与收益窗口起点一致；"
                    f"ST 成员 {definition.get('ST成员数')} 只，市值覆盖率 "
                    f"{definition.get('市值覆盖率')}，不使用当前市值倒推历史。"
                ),
                backing=[_backing("query_row", _row_id(definition))],
            ),
            NarrativeStep(
                title="再比较两组分布和覆盖率",
                text=(
                    f"微盘 ST 为 {microcap.get('成员数')} 只、有效收益 "
                    f"{microcap.get('有效收益数')} 只（{microcap.get('收益覆盖率')}）；"
                    f"普通 ST 为 {other.get('成员数')} 只、有效收益 "
                    f"{other.get('有效收益数')} 只（{other.get('收益覆盖率')}）。"
                ),
                backing=[
                    _backing("query_row", _row_id(microcap)),
                    _backing("query_row", _row_id(other)),
                ],
            ),
        ]
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

    if comparison_gap:
        direct = _statement(
            (
                "当前无法完成微盘 ST 与普通 ST 的可靠比较："
                f"{comparison_gap.get('缺口')}。全体 ST 的 T+10 分布仍可作为背景，"
                f"其中中位数为 {quantiles.get('p50')}。"
            ),
            "query_row",
            _row_id(comparison_gap),
        )
    else:
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


def _recruitment_precedent_narrative(
    card: dict[str, Any],
    claims: list[VerifiedClaim],
) -> ResearchNarrative:
    rows = [row for row in card.get("body_rows", []) if _row_id(row)]
    summary = next(
        (row for row in rows if row.get("记录类型") == "招募截止前连续跌停先例汇总"),
        None,
    )
    if summary is None:
        raise ValueError("recruitment precedent narrative 缺汇总行")
    precedents = [
        row for row in rows if row.get("记录类型") == "招募截止前连续跌停先例"
    ]
    covered = int(summary.get("截止日与价格完整覆盖") or 0)
    precedent_count = int(summary.get("观察到连续跌停先例") or 0)
    if precedent_count and precedents:
        first = precedents[0]
        direct = NarrativeStatement(
            text=(
                f"有。在本地截止日和价格路径完整覆盖的 {covered} 个上市公司本体 ST 招募案例中，"
                f"有 {precedent_count} 个在报名截止前出现至少两个相邻交易日收盘跌停。"
                f"例如 {first.get('股票')} 在 {first.get('连续交易日')} 连续 "
                f"{first.get('最长连续跌停')} 个交易日跌停；其招募公告日为 "
                f"{first.get('招募公告日')}，报名截止日为 {first.get('报名截止日')}。"
            ),
            backing=[
                _backing("query_row", _row_id(summary)),
                _backing("query_row", _row_id(first)),
            ],
        )
    else:
        direct = _statement(
            (
                f"在当前截止日和价格路径完整覆盖的 {covered} 个案例中，"
                "没有观察到按本题口径定义的连续跌停；这不能扩展为全市场不存在先例。"
            ),
            "query_row",
            _row_id(summary),
        )

    steps = [NarrativeStep(
        title="先固定检索口径",
        text=str(summary.get("连续跌停定义")),
        backing=[_backing("query_row", _row_id(summary))],
    ), NarrativeStep(
        title="再看有效样本",
        text=(
            f"材料化案例 {summary.get('材料化招募案例')} 个，其中招募时处于 ST 且"
            f"截止日与价格路径完整覆盖 {covered} 个；正文提取失败 "
            f"{summary.get('正文提取失败')} 个。"
        ),
        backing=[_backing("query_row", _row_id(summary))],
    )]
    if len(precedents) > 1:
        examples = "；".join(
            f"{row.get('股票')}（{row.get('最长连续跌停')}个交易日）"
            for row in precedents[:4]
        )
        steps.append(NarrativeStep(
            title="已观察到的先例",
            text=examples + "。",
            backing=[
                _backing("query_row", _row_id(row)) for row in precedents[:4]
            ],
        ))

    premise = next(
        (row for row in rows if row.get("记录类型") == "题面当日价格前提"),
        None,
    )
    uncertainties = [
        _claim_statement(claim) for claim in claims
        if claim.claim_type in {"caveat", "data_gap"}
        and not (premise and "题面所述" in claim.text)
        and not (premise and "当前招募截止日" in claim.text)
    ]
    if premise and not premise.get("本地是否覆盖"):
        uncertainties.insert(0, _statement(
            (
                f"题面所述 {premise.get('题面日期')} 跌停晚于本地价格截止日 "
                f"{premise.get('本地价格截至')}，这里只把它作为未独立核验的提问前提。"
            ),
            "query_row",
            _row_id(premise),
        ))
    if premise and premise.get("本地是否验证处于招募截止前") == "未验证":
        uncertainties.append(_statement(
            "当前个案的招募截止日未进入公司公告口径材料化；题面所述“截止前”也未由本卡独立核验。",
            "query_row",
            _row_id(premise),
        ))
    uncertainties.append(_statement(
        "历史先例回答的是“是否出现过”，不说明当前个案的后续价格或重整结果。",
        "query_row",
        _row_id(summary),
    ))
    return ResearchNarrative(
        direct_answer=direct,
        reasoning_steps=steps,
        uncertainties=uncertainties[:6],
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
    if "recruitment_deadline_price_precedent_query" in response.route.matched_rules:
        return _recruitment_precedent_narrative(card, response.claims)
    if "restructuring_next_node_query" in response.route.matched_rules:
        return _timing_narrative(card, response.claims)
    if "stock_restructuring_progress_query" in response.route.matched_rules:
        return _restructuring_progress_narrative(card, response.claims)
    if "stock_administrator_history_query" in response.route.matched_rules:
        return _administrator_history_narrative(card, response.claims)
    if "stock_comparison_query" in response.route.matched_rules:
        return _comparison_narrative(card, response.claims)
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
