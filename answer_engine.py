"""
v8 ST Research Copilot — Answer Engine（P1，lens-invocation 脊梁版）

最小闭环（D-052 修正案）：
  question_card → candidate_lenses → selected_lens_invocations
  → query/checklist/evidence/data_debt execution → answer_card
  →（无可用 lens）lens_gap → 沉淀 question_card / data_debt

红线（硬编在 AnswerCard.validate）：
- 每张卡必带：出处、as_of、样本范围、证据等级、缺口，且**必带 lens_invocations 或 lens_gap**
  （答案不能凭 sqlite+手写逻辑凭空产生，必须显式声明消费了哪些 v7.4 release lens）。
- 版本/新鲜度必带：v7_release_library_version、episode_index_version、data_snapshot_as_of、source_freshness。
- 不输出买卖/持有/仓位/交易信号/排序权重措辞。
- data_debt 行必须挂既有债台账 id。

治理：独立消费者，不 import forum_signals / v7 内部模块；只读 sqlite + episode index + 冻结 release library。
"""
from __future__ import annotations

import json
import re
import sqlite3
import statistics
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from typing import Any, Iterable

from announcement_inventory import OfficialAnnouncement, load_announcement_inventory
from announcement_body import (
    AnnouncementBodyError,
    load_announcement_body,
    official_announcement_number,
    relevant_excerpt,
)
from lens_binding import LensRegistry, LensInvocation, LensGap
from recruitment_precedent import (
    RecruitmentMaterializationError,
    analyze_recruitment_precedents,
    load_recruitment_deadlines,
)
from settings import (
    ANNOUNCEMENT_REFRESH_DIR,
    DATA_ROOT,
    RECRUITMENT_DEADLINE_MATERIALIZATION,
)
from snapshot_metadata import (
    limiting_as_of,
    load_episode_snapshot,
    load_price_snapshot,
    load_table_snapshot,
)

_ROOT = DATA_ROOT
BASE_DB = _ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"
SHAREHOLDER_DB = _ROOT / "shared_data/v7/shareholder_count_pilot/shareholder_count.sqlite3"
EPISODE_INDEX = _ROOT / "shared_data/v7/episode_index_v0/episode_index.jsonl"
EPISODE_MANIFEST = _ROOT / "shared_data/v7/episode_index_v0/builder_run_manifest.json"

FORBIDDEN_WORDING = [
    "买入", "卖出", "加仓", "减仓", "目标价", "建议持有", "买卖点",
    "应该买", "应该卖", "推荐买", "推荐卖", "止损", "止盈", "仓位",
    "target price", "position sizing",
]
FIXED_CAVEATS = [
    "输出为历史路径描述，不表示可交易/可预测/可复现（D-037）。",
    "语料/样本为 ST 及论坛提及边界，非全市场（D-024）；episode 均为 case_note_only，非验证结论。",
]
VALID_VIEWS = {"query", "evidence", "checklist", "methodology", "data_debt"}
VALID_CLAIM_TYPES = {"fact", "inference", "caveat", "question", "data_gap"}
VALID_BACKING_KINDS = {
    "lens_invocation", "query_row", "provenance_ref", "data_debt", "lens_gap",
}
CONTRACT_VERSION = "v8_answer_contract_v0"

_REGISTRY = LensRegistry()


@dataclass
class DataDebtRow:
    gap: str
    affects: str
    debt_ref: str


class EventNotFoundError(LookupError):
    """A selected event does not resolve to the read-only announcement/episode sources."""


class StockNotFoundError(LookupError):
    """A requested stock has no rows in the required read-only source."""


@dataclass
class BackingRef:
    kind: str
    ref: str


@dataclass
class AnalysisClaim:
    text: str
    claim_type: str
    backing: BackingRef


@dataclass
class AnswerCard:
    question: str
    object_ref: str
    view: str
    as_of: str
    sample_scope: str
    evidence_grade: str
    contract_version: str = CONTRACT_VERSION
    # ---- lens 脊梁（必带其一）----
    lens_invocations: list[LensInvocation] = field(default_factory=list)
    lens_gap: list[LensGap] = field(default_factory=list)
    # ---- 版本 / 新鲜度（必带）----
    v7_release_library_version: str = _REGISTRY.library_version
    episode_index_version: str = "not_used"
    data_snapshot_as_of: str = ""
    source_freshness: dict[str, str] = field(default_factory=dict)
    # ---- 主体 ----
    body_rows: list[dict[str, Any]] = field(default_factory=list)
    analysis_claims: list[AnalysisClaim] = field(default_factory=list)
    data_debt: list[DataDebtRow] = field(default_factory=list)
    data_debt_refs: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    provenance: list[str] = field(default_factory=list)

    def validate(self) -> None:
        errs: list[str] = []
        for field_name in ("question", "object_ref"):
            if not getattr(self, field_name):
                errs.append(f"缺 {field_name}")
        if self.view not in VALID_VIEWS:
            errs.append(f"view 非法: {self.view}")
        for field_name in (
            "as_of", "sample_scope", "evidence_grade", "contract_version",
            "v7_release_library_version", "episode_index_version", "data_snapshot_as_of",
        ):
            if not getattr(self, field_name):
                errs.append(f"缺 {field_name}")
        if self.contract_version != CONTRACT_VERSION:
            errs.append(
                f"contract_version 非法: {self.contract_version}，应为 {CONTRACT_VERSION}"
            )
        if not self.source_freshness or any(not value for value in self.source_freshness.values()):
            errs.append("缺 source_freshness")
        if not self.provenance:
            errs.append("缺 provenance")
        if not self.lens_invocations and not self.lens_gap:
            errs.append("缺脊梁：既无 lens_invocations 也无 lens_gap（答案不得凭空产生）")

        release_ids = [invocation.release_id for invocation in self.lens_invocations]
        if len(release_ids) != len(set(release_ids)):
            errs.append("lens_invocations release_id 重复")
        gap_ids = [gap.gap_id for gap in self.lens_gap]
        if len(gap_ids) != len(set(gap_ids)):
            errs.append("lens_gap gap_id 重复")
        for g in self.lens_gap:
            if not g.gap_id:
                errs.append(f"lens_gap 缺 gap_id: {g.missing_for}")
            if not g.sediment_as:
                errs.append(f"lens_gap 未沉淀（缺 sediment_as）: {g.missing_for}")
            elif not g.sediment_as.startswith(("question_card:", "data_debt:")):
                errs.append(f"lens_gap sediment_as 非法: {g.sediment_as}")

        for fc in FIXED_CAVEATS:
            if fc not in self.caveats:
                errs.append("缺固定 caveat: " + fc[:16] + "…")
        if self.view in {"query", "checklist", "evidence"} and not self.body_rows:
            errs.append(f"{self.view} 视图缺 body_rows")

        raw_row_ids = [row.get("row_id") for row in self.body_rows]
        if any(not isinstance(row_id, str) or not row_id for row_id in raw_row_ids):
            errs.append("body_rows 每行必须带 row_id")
        row_ids = [row_id for row_id in raw_row_ids if isinstance(row_id, str)]
        if len(row_ids) != len(set(row_ids)):
            errs.append("body_rows row_id 重复")

        for d in self.data_debt:
            if not d.debt_ref:
                errs.append(f"data_debt 行缺 debt_ref: {d.gap}")
        if {d.debt_ref for d in self.data_debt} - set(self.data_debt_refs):
            errs.append("data_debt_refs 未覆盖全部 data_debt 行")
        if len(self.data_debt_refs) != len(set(self.data_debt_refs)):
            errs.append("data_debt_refs 重复")
        if self.view == "data_debt" and not self.data_debt:
            errs.append("data_debt 视图缺 data_debt 行")
        if self.view in {"methodology", "data_debt"} and self.evidence_grade not in {
            "context_only", "insufficient_data"}:
            errs.append(f"{self.view} 视图 evidence_grade 不应为 {self.evidence_grade}")
        if self.view == "evidence":
            evidence_invocations = [
                invocation for invocation in self.lens_invocations
                if invocation.lens_kind == "evidence" and invocation.release_role == "evidence_lens"
            ]
            if not evidence_invocations:
                errs.append("evidence 视图必须调用 evidence_lens")
            for invocation in evidence_invocations:
                if not all((
                    invocation.evidence_grade,
                    invocation.cohort_id,
                    invocation.provenance_refs,
                    invocation.allowed_wording,
                )):
                    errs.append(f"evidence invocation 字段不完整: {invocation.release_id}")

        valid_refs = {
            "lens_invocation": set(release_ids),
            "query_row": set(row_ids),
            "provenance_ref": set(self.provenance),
            "data_debt": set(self.data_debt_refs),
            "lens_gap": set(gap_ids),
        }
        for index, claim in enumerate(self.analysis_claims):
            if not claim.text:
                errs.append(f"analysis_claim[{index}] 缺 text")
            if claim.claim_type not in VALID_CLAIM_TYPES:
                errs.append(f"analysis_claim[{index}] claim_type 非法: {claim.claim_type}")
            if not isinstance(claim.backing, BackingRef):
                errs.append(f"analysis_claim[{index}] 缺合法 backing")
                continue
            if claim.backing.kind not in VALID_BACKING_KINDS:
                errs.append(f"analysis_claim[{index}] backing.kind 非法: {claim.backing.kind}")
            elif claim.backing.ref not in valid_refs[claim.backing.kind]:
                errs.append(
                    f"analysis_claim[{index}] backing 无对应对象: "
                    f"{claim.backing.kind}:{claim.backing.ref}"
                )

        blob = json.dumps(asdict(self), ensure_ascii=False, default=str)
        hit = [w for w in FORBIDDEN_WORDING if w in blob]
        if hit:
            errs.append(f"命中禁用交易措辞: {hit}")
        if errs:
            raise ValueError("AnswerCard 契约不通过:\n  - " + "\n  - ".join(errs))

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        d = asdict(self)
        d["lens_invocations"] = [li.to_dict() for li in self.lens_invocations]
        d["lens_gap"] = [g.to_dict() for g in self.lens_gap]
        return d

    def to_markdown(self) -> str:
        self.validate()
        L = [f"### 问题：{self.question}",
             f"对象：{self.object_ref}  ·  视图：{self.view}  ·  证据等级：{self.evidence_grade}",
             f"as_of：{self.as_of}  ·  样本范围：{self.sample_scope}",
             f"契约：{self.contract_version} · library={self.v7_release_library_version} · "
             f"episode={self.episode_index_version} · price_as_of={self.data_snapshot_as_of}",
             ""]
        L.append("**lens invocations（脊梁）**")
        if self.lens_invocations:
            for li in self.lens_invocations:
                L.append(f"- {li.release_id} [{li.lens_kind}/{li.release_role}] → 贡献「{li.contributed_section}」"
                         + (f"（{li.evidence_grade}）" if li.evidence_grade else ""))
        else:
            L.append("- （无 evidence/methodology lens 命中）")
        for g in self.lens_gap:
            L.append(f"- ⚠ lens_gap：{g.missing_for} → 沉淀 {g.sediment_as}")
        L.append("")
        if self.body_rows:
            L.append("**结果**")
            for r in self.body_rows:
                L.append("- " + "；".join(
                    f"{k}：{v}" for k, v in r.items() if k != "row_id"
                ))
            L.append("")
        if self.analysis_claims:
            L.append("**分析说明**")
            for claim in self.analysis_claims:
                L.append(
                    f"- [{claim.claim_type}] {claim.text} "
                    f"（依据 {claim.backing.kind}:{claim.backing.ref}）"
                )
            L.append("")
        if self.data_debt:
            L.append("**数据缺口（data_debt）**")
            for d in self.data_debt:
                L.append(f"- 缺 {d.gap} → 影响 {d.affects}（债台账 {d.debt_ref}）")
            L.append("")
        L.append("**caveat**")
        for c in self.caveats:
            L.append(f"- {c}")
        L.append("")
        L.append("**出处**：" + "；".join(self.provenance))
        return "\n".join(L)


# ---- read-only data access ----
def _db() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{BASE_DB}?mode=ro", uri=True)


def _pd(s: str) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"日期字段非法: {s!r}") from exc


def _iter_episodes(symbol_filter: str | None = None) -> Iterable[dict]:
    with open(EPISODE_INDEX, encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            if symbol_filter and symbol_filter not in line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"episode index JSON 非法: {EPISODE_INDEX}:{line_number}: {exc}"
                ) from exc
            if not isinstance(d, dict):
                raise ValueError(
                    f"episode index 行必须是 object: {EPISODE_INDEX}:{line_number}"
                )
            if symbol_filter and d.get("symbol") != symbol_filter:
                continue
            yield d


def _stats(g: list[int]) -> dict[str, Any]:
    g = sorted(g)
    n = len(g)
    if n == 0:
        return {
            "n": 0, "median": None, "mean": None,
            "p25": None, "p75": None, "min": None, "max": None,
        }
    return {"n": n, "median": statistics.median(g), "mean": round(statistics.mean(g), 1),
            "p25": g[n // 4], "p75": g[(3 * n) // 4], "min": g[0], "max": g[-1]}


def _row(row_id: str, **values: Any) -> dict[str, Any]:
    if not row_id:
        raise ValueError("row_id 不得为空")
    return {"row_id": row_id, **values}


# ================= card builders (through the lens binding spine) =================

def card_next_node_gap(
    trigger_subtype: str = "restructuring_investor_recruitment",
    *,
    include_out_of_court_debt: bool = False,
) -> AnswerCard:
    """#01 重整招募→下一节点。lens：重整方法论框架贡献 caveat；无 evidence lens → lens_gap 沉淀。"""
    episode_snapshot = load_episode_snapshot(EPISODE_INDEX, EPISODE_MANIFEST)
    announcement_snapshot = load_table_snapshot(
        BASE_DB, table="company_announcements", date_column="announcement_date"
    )
    SAME = {trigger_subtype, trigger_subtype + "_progress"}
    g_classified, g_milestone, recs = [], [], []
    for d in _iter_episodes():
        evs = [e for e in d.get("anchor_events", []) if e.get("announcement_date")]
        evs.sort(key=lambda e: e["announcement_date"])
        for i, e in enumerate(evs):
            if trigger_subtype in e.get("event_subtypes", []):
                recs.append((d.get("symbol"), e["announcement_date"]))
                d0 = _pd(e["announcement_date"])
                for j in range(i + 1, len(evs)):
                    d1 = _pd(evs[j]["announcement_date"])
                    if d0 and d1 and d1 > d0:
                        g_classified.append((d1 - d0).days); break
                for j in range(i + 1, len(evs)):
                    if set(evs[j].get("event_subtypes", [])) & SAME:
                        continue
                    d1 = _pd(evs[j]["announcement_date"])
                    if d0 and d1 and d1 > d0:
                        g_milestone.append((d1 - d0).days); break
    g_any = []
    con = _db(); cur = con.cursor()
    for sym, ad in recs:
        r = cur.execute("select announcement_date from company_announcements "
                        "where symbol=? and announcement_date>? order by announcement_date asc limit 1",
                        (sym, ad)).fetchone()
        if r:
            d0, d1 = _pd(ad), _pd(r[0])
            if d0 and d1 and d1 > d0:
                g_any.append((d1 - d0).days)
    con.close()
    def row(row_id: str, label: str, s: dict[str, Any]) -> dict[str, Any]:
        return _row(
            row_id,
            节点定义=label,
            N=s["n"],
            **{
                "中位(天)": s["median"],
                "均值": s["mean"],
                "p25/p75": f"{s['p25']}/{s['p75']}",
                "范围": f"{s['min']}-{s['max']}",
            },
        )
    # ---- lens binding ----
    cands = _REGISTRY.candidate_lenses(clusters=["C04"], topic_terms=["重整", "资产重组", "资产注入", "共益债"])
    invs = [_REGISTRY.invoke(r, "重整路径框架/caveat") for r in cands]
    gaps = [LensGap(gap_id="restructuring_timing_evidence",
                    missing_for="重整阶段时点分布的验证证据",
                    sediment_as="question_card:QC-20260710-009",
                    note="冻结 Lens 库没有经过验证的重整阶段等待期证据；当前分布仅为描述性查询。")]
    debts: list[DataDebtRow] = []
    provenance = [
        "shared_data/v7/episode_index_v0/episode_index.jsonl",
        "shared_data/v5/.../st_stocks_v5_backup.sqlite3::company_announcements",
    ]
    freshness = {
        "episode_index_as_of": episode_snapshot.as_of,
        "company_announcements_as_of": announcement_snapshot.as_of,
    }
    if include_out_of_court_debt:
        debts.append(DataDebtRow(
            gap="庭外/庭内重整标记",
            affects="庭外重组子样本的单独等待期分布",
            debt_ref="D-051B",
        ))
        gaps.append(LensGap(
            gap_id="out_of_court_timing_stratification",
            missing_for="庭外重组子样本等待期分层",
            sediment_as="data_debt:D-051B",
            note="总体重整招募分布可答；当前不能把样本可靠筛成庭外/庭内。",
        ))
        provenance.append(
            "v7_worksite/coordination/debt_cards/D-051B_out_of_court_flag.md"
        )
        freshness["data_debt_registry_as_of"] = "2026-07-10"
    body_rows = [
        row("next_any_announcement", "下一个任意公告", _stats(g_any)),
        row("next_classified_restructuring", "下一个已分类重整节点", _stats(g_classified)),
        row("next_stage_milestone", "下一个不同阶段里程碑", _stats(g_milestone)),
    ]
    return AnswerCard(
        question=f"{trigger_subtype} 之后，下一个公告节点平均多久？",
        object_ref=f"cohort:{trigger_subtype}（{len(recs)} 事件）",
        view="query", as_of=limiting_as_of(
            episode_snapshot.as_of, announcement_snapshot.as_of
        ),
        sample_scope=f"M6 episode index canonical 语料，{len({s for s,_ in recs})} 只股票 / {len(recs)} 触发事件",
        evidence_grade="descriptive_query",
        episode_index_version=episode_snapshot.version,
        data_snapshot_as_of=limiting_as_of(
            episode_snapshot.as_of, announcement_snapshot.as_of
        ),
        source_freshness=freshness,
        lens_invocations=invs, lens_gap=gaps,
        body_rows=body_rows,
        analysis_claims=[
            AnalysisClaim(
                text="“下一个节点”定义不同会得到不同等待期，答案保留三种口径。",
                claim_type="caveat",
                backing=BackingRef(kind="lens_gap", ref="restructuring_timing_evidence"),
            ),
            *([AnalysisClaim(
                text="总体分布可答，但当前不能单独筛出庭外重组子样本。",
                claim_type="data_gap",
                backing=BackingRef(kind="data_debt", ref="D-051B"),
            )] if include_out_of_court_debt else []),
        ],
        data_debt=debts,
        data_debt_refs=[debt.debt_ref for debt in debts],
        caveats=FIXED_CAVEATS + [
            "『平均多久』无单一答案：节点定义不同，中位数可差数倍——三口径并列，由提问者选。"],
        provenance=provenance)


def _question_claimed_date(question: str) -> str:
    normalized = re.sub(r"\s+", "", question)
    full = re.search(r"(20\d{2})年?(\d{1,2})月(\d{1,2})(?:日|号)?", normalized)
    if full:
        try:
            return date(int(full.group(1)), int(full.group(2)), int(full.group(3))).isoformat()
        except ValueError:
            return ""
    short = re.search(r"(\d{1,2})月(\d{1,2})(?:日|号)", normalized)
    if short:
        try:
            return date(date.today().year, int(short.group(1)), int(short.group(2))).isoformat()
        except ValueError:
            return ""
    return ""


def card_recruitment_limit_down_precedent(
    symbol: str | None,
    question: str,
) -> AnswerCard:
    """Answer recruitment-deadline × consecutive-limit-down precedent questions."""
    price_snapshot = load_price_snapshot(BASE_DB)
    current_price_snapshot = (
        load_price_snapshot(BASE_DB, symbol=symbol) if symbol else price_snapshot
    )
    materialization_error = ""
    payload: dict[str, Any] = {}
    try:
        cases, payload = load_recruitment_deadlines(
            RECRUITMENT_DEADLINE_MATERIALIZATION
        )
    except RecruitmentMaterializationError as exc:
        cases = []
        materialization_error = str(exc)

    precedents, counts = analyze_recruitment_precedents(
        BASE_DB,
        cases,
        price_as_of=price_snapshot.as_of,
    )
    rows: list[dict[str, Any]] = []
    claimed_date = _question_claimed_date(question)
    current_deadlines = sorted(
        case.recruitment_deadline for case in cases
        if symbol and case.symbol == symbol and case.subject_scope == "listed_company"
    )
    if claimed_date:
        rows.append(_row(
            "question_price_premise",
            **{
                "记录类型": "题面当日价格前提",
                "股票": symbol or "题面未绑定股票",
                "题面日期": claimed_date,
                "题面陈述": "当日跌停" if "跌停" in question else "当日价格异动",
                "本地价格截至": current_price_snapshot.as_of,
                "本地是否覆盖": claimed_date <= current_price_snapshot.as_of,
                "本地公司公告口径招募截止日": (
                    current_deadlines[-1] if current_deadlines else "未材料化"
                ),
                "本地是否验证处于招募截止前": (
                    claimed_date <= current_deadlines[-1]
                    if current_deadlines else "未验证"
                ),
                "处理方式": (
                    "当前价格与招募窗口单独核对，不纳入历史样本计算"
                    if claimed_date <= current_price_snapshot.as_of and current_deadlines
                    else "当前价格或招募窗口作为未独立核验前提，不纳入历史样本计算"
                ),
            },
        ))

    summary_id = "recruitment_limit_down_summary"
    rows.append(_row(
        summary_id,
        **{
            "记录类型": "招募截止前连续跌停先例汇总",
            "材料化招募案例": len(cases),
            "上市公司本体案例": counts["listed_company_cases"],
            "招募时处于ST案例": counts["st_eligible_cases"],
            "截止日与价格完整覆盖": counts["price_covered_cases"],
            "观察到连续跌停先例": counts["precedent_cases"],
            "连续跌停定义": "招募公告日至报名截止日之间，至少2个相邻交易日收盘跌停",
            "跌停识别": "ST区间内日涨跌幅不高于-4.8%（含价格取整容差）",
            "价格截至": price_snapshot.as_of,
            "截止日晚于价格快照": counts["future_deadline_cases"],
            "价格路径不完整": counts["incomplete_price_cases"],
            "正文提取失败": int(payload.get("failure_count") or 0),
            "材料化状态": materialization_error or "已读取本地截止日材料化文件",
        },
    ))
    for index, precedent in enumerate(precedents[:12], 1):
        display_stock = (
            f"{precedent['stock_name']}（{precedent['symbol']}）"
            if precedent.get("stock_name") else precedent["symbol"]
        )
        rows.append(_row(
            f"recruitment_limit_down_precedent_{index:02d}",
            **{
                "记录类型": "招募截止前连续跌停先例",
                "股票": display_stock,
                "招募公告日": precedent["announcement_date"],
                "报名截止日": precedent["recruitment_deadline"],
                "最长连续跌停": precedent["run_length"],
                "连续交易日": "、".join(precedent["run_dates"]),
                "窗口内跌停交易日": precedent["limit_down_days"],
                "巨潮公告ID": precedent["announcement_id"],
                "公告标题": precedent["title"],
                "原文链接": precedent["source_url"],
            },
        ))

    gap = LensGap(
        gap_id="recruitment_deadline_limit_down_evidence",
        missing_for="招募截止日前连续跌停与后续结果之间的验证型关系",
        sediment_as="question_card:recruitment_deadline_limit_down_precedent",
        note="本卡只回答历史上是否出现过该组合事件，不把先例解释成后续方向或结果。",
    )
    gaps = [gap]
    claims = [AnalysisClaim(
        text=(
            f"在截止日和价格路径完整覆盖的 {counts['price_covered_cases']} 个案例中，"
            f"观察到 {counts['precedent_cases']} 个招募截止前连续跌停先例。"
        ),
        claim_type="fact",
        backing=BackingRef(kind="query_row", ref=summary_id),
    )]
    if materialization_error:
        claims.append(AnalysisClaim(
            text="公开招募截止日尚未完成本地材料化，当前不能把公告日当作截止日替代计算。",
            claim_type="data_gap",
            backing=BackingRef(kind="query_row", ref=summary_id),
        ))
    if claimed_date and claimed_date > current_price_snapshot.as_of:
        claims.append(AnalysisClaim(
            text=(
                f"题面所述 {claimed_date} 价格状态晚于本地价格截止日 "
                f"{current_price_snapshot.as_of}，本卡不独立确认该陈述。"
            ),
            claim_type="caveat",
            backing=BackingRef(kind="query_row", ref="question_price_premise"),
        ))
    if symbol and not current_deadlines:
        channel_gap = LensGap(
            gap_id="current_recruitment_deadline_channel_coverage",
            missing_for=f"{symbol} 在非公司公告渠道披露的当前招募截止日",
            sediment_as="data_debt:restructuring_recruitment_channel_coverage",
            note="截止日材料化只覆盖正式公司公告；破产重整信息平台和管理人渠道未纳入。",
        )
        gaps.append(channel_gap)
        claims.append(AnalysisClaim(
            text=(
                f"本地公司公告口径没有材料化 {symbol} 的当前招募截止日，"
                "不能独立确认题面日期是否仍处于招募窗口。"
            ),
            claim_type="data_gap",
            backing=BackingRef(kind="lens_gap", ref=channel_gap.gap_id),
        ))

    materialization_as_of = max(
        (case.announcement_date for case in cases),
        default=price_snapshot.as_of,
    )
    as_of = limiting_as_of(price_snapshot.as_of, materialization_as_of)
    provenance = [
        "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3::daily_prices",
        "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3::st_status_history",
    ]
    if not materialization_error:
        provenance.append("local_data/v8_copilot/recruitment_deadlines.json")
    return AnswerCard(
        question=question,
        object_ref=(
            f"stock:{symbol};cohort:listed-company-recruitment-windows"
            if symbol else "cohort:listed-company-recruitment-windows"
        ),
        view="query",
        as_of=as_of,
        sample_scope=(
            f"{counts['price_covered_cases']} 个已验证报名截止日且价格路径完整的上市公司本体 ST 招募案例"
        ),
        evidence_grade="descriptive_query",
        lens_gap=gaps,
        data_snapshot_as_of=as_of,
        source_freshness={
            "price_data_as_of": price_snapshot.as_of,
            **(
                {f"price_{symbol}_as_of": current_price_snapshot.as_of}
                if symbol else {}
            ),
            "recruitment_announcement_materialization_as_of": materialization_as_of,
        },
        body_rows=rows,
        analysis_claims=claims,
        caveats=FIXED_CAVEATS + [
            "先例仅表示历史组合事件出现过，不说明当前个案会延续同一路径。",
            "连续跌停按相邻交易日定义，不按自然日定义。",
        ],
        provenance=provenance,
    )


def card_two_week_move(
    *, include_market_debt: bool = True, include_microcap_debt: bool = True
) -> AnswerCard:
    """#02 两周异动。无 evidence lens 直接命中『两周横截面异动』→ lens_gap 沉淀 + 两条 data_debt。"""
    import numpy as np, pandas as pd
    price_snapshot = load_price_snapshot(BASE_DB)
    con = _db()
    df = pd.read_sql("select symbol,trade_date,close from daily_prices where adjust='qfq'", con)
    con.close()
    df = df.sort_values(["symbol", "trade_date"])
    r = (df.groupby("symbol")["close"].shift(-10) / df["close"] - 1).dropna() * 100
    pcts = {f"p{q:02d}": round(float(np.percentile(r, q)), 1) for q in [5, 25, 50, 75, 95]}
    body = [
        _row(
            "two_week_return_quantiles",
            **{"指标": "ST面板两周(T+10)收益分位", **{k: f"{v}%" for k, v in pcts.items()}},
        ),
        _row(
            "two_week_move_frequency",
            **{
                "指标": "异动频率",
                "|>10%|": f"{(r.abs()>10).mean()*100:.1f}%",
                "|>20%|": f"{(r.abs()>20).mean()*100:.1f}%",
                "N": int(len(r)),
            },
        ),
    ]
    debts: list[DataDebtRow] = []
    if include_market_debt:
        debts.append(DataDebtRow(
            "大盘指数日线序列", "『相对大盘』无真基准，只能 ST-relative 代理", "D-051C"
        ))
    if include_microcap_debt:
        debts.append(DataDebtRow(
            "as-of 市值/股本", "『微盘』cohort 无法定义（市值字段全空）", "C14"
        ))
    debt_refs = [debt.debt_ref for debt in debts]
    # 尝试绑定：日历 regime evidence lens 存在，但它是月份口径，不解答两周横截面 → 记为 gap
    gaps = [LensGap(gap_id="two_week_cross_section_evidence",
                    missing_for="两周横截面异动分布的验证证据",
                    sediment_as="question_card:QC-20260710-013",
                    note="release library 仅有月份 calendar-regime(RL-A-001/002) 与 C17 短窗(RL-A-003)，"
                         "均不直接验证『两周横截面异动』；ST 分布为无 lens 背书的 descriptive query。")]
    return AnswerCard(
        question="ST/微盘相对大盘异动的两周分布如何？",
        object_ref="universe: ST panel (daily_prices qfq)",
        view="query", as_of=price_snapshot.as_of,
        sample_scope=(
            f"{price_snapshot.symbol_count} 只 ST 面板，"
            f"{price_snapshot.min_date}~{price_snapshot.as_of}，"
            f"源价格行 {price_snapshot.row_count:,}；T+10 收益观测 "
            f"{price_snapshot.return_observation_count:,}"
        ),
        evidence_grade="descriptive_query",
        data_snapshot_as_of=price_snapshot.as_of,
        source_freshness={"price_data_as_of": price_snapshot.as_of},
        lens_invocations=[], lens_gap=gaps,
        body_rows=body, data_debt=debts, data_debt_refs=debt_refs,
        analysis_claims=[
            *([AnalysisClaim(
                text="相对大盘层缺少大盘指数日线序列。",
                claim_type="data_gap",
                backing=BackingRef(kind="data_debt", ref="D-051C"),
            )] if include_market_debt else []),
            *([AnalysisClaim(
                text="微盘分层缺少 as-of 市值或可复算字段。",
                claim_type="data_gap",
                backing=BackingRef(kind="data_debt", ref="C14"),
            )] if include_microcap_debt else []),
        ],
        caveats=FIXED_CAVEATS + [
            "退市股价格可能右截断（生存偏差）；两周=10 交易日口径。",
            "请求包含相对大盘或微盘分层时，缺失维度明确进入 data debt；ST 面板自身分布仍为描述性 query。"],
        provenance=["shared_data/v5/.../st_stocks_v5_backup.sqlite3::daily_prices"])


def card_stock_event_window(
    symbol: str,
    event_id: str,
    event_date: str,
    event_title: str = "",
) -> AnswerCard:
    """Describe one selected event through linked price, announcement, and episode rows."""
    requested_date = _pd(event_date)
    if requested_date is None:
        raise EventNotFoundError("事件窗口缺 event_date")
    price_snapshot = load_price_snapshot(BASE_DB, symbol=symbol)
    announcement_snapshot = load_table_snapshot(
        BASE_DB,
        table="company_announcements",
        date_column="announcement_date",
        where_sql="symbol=?",
        parameters=(symbol,),
    )
    episode_snapshot = load_episode_snapshot(EPISODE_INDEX, EPISODE_MANIFEST)

    matched_episode: dict[str, Any] | None = None
    matched_anchor: dict[str, Any] | None = None
    for episode in _iter_episodes(symbol):
        for anchor in episode.get("anchor_events", []):
            source_ids = [str(item) for item in anchor.get("source_material_ids", [])]
            if event_id in source_ids:
                matched_episode = episode
                matched_anchor = anchor
                break
        if matched_episode:
            break

    announcement_key = event_id.split(":", 1)[1] if event_id.startswith("announcement:") else event_id

    with _db() as connection:
        official_announcement = connection.execute(
            "select announcement_id,announcement_date,title,url from company_announcements "
            "where symbol=? and announcement_id=? limit 1",
            (symbol, announcement_key),
        ).fetchone()
        if official_announcement:
            official_id, official_date, official_title, _ = official_announcement
            anchor_date = _pd(str(official_date))
            resolved_event_id = (
                event_id if matched_anchor else f"announcement:{official_id}"
            )
            resolved_title = str(official_title)
        elif matched_anchor:
            anchor_date = _pd(str(matched_anchor.get("announcement_date", "")))
            resolved_event_id = event_id
            resolved_title = str(matched_anchor.get("title") or event_title or "未命名公告")
        else:
            raise EventNotFoundError(
                f"选中事件未命中正式公告或 episode: {symbol}:{event_id}"
            )
        if anchor_date is None:
            raise EventNotFoundError(f"选中事件缺合法日期: {symbol}:{event_id}")
        prices = connection.execute(
            "select trade_date,close from daily_prices "
            "where symbol=? and adjust='qfq' order by trade_date",
            (symbol,),
        ).fetchall()
        announcements = connection.execute(
            "select announcement_id,announcement_date,title,url from company_announcements "
            "where symbol=? and announcement_date between ? and ? "
            "order by announcement_date,announcement_id",
            (
                symbol,
                (anchor_date - timedelta(days=14)).isoformat(),
                (anchor_date + timedelta(days=14)).isoformat(),
            ),
        ).fetchall()
    if not prices:
        raise ValueError(f"当前快照无股票 {symbol} 的 qfq 价格数据")

    before_indexes = [
        index for index, (trade_date, _) in enumerate(prices)
        if _pd(trade_date) and _pd(trade_date) <= anchor_date
    ]
    if not before_indexes:
        raise EventNotFoundError(
            f"事件日期早于 {symbol} 的价格覆盖范围: {anchor_date.isoformat()}"
        )
    anchor_index = before_indexes[-1]
    before_index = max(0, anchor_index - 10)
    after_index = min(len(prices) - 1, anchor_index + 10)
    base_close = float(prices[anchor_index][1])
    before_close = float(prices[before_index][1])
    after_close = float(prices[after_index][1])

    episode_type = str((matched_episode or {}).get("episode_type", "unclassified"))
    event_sources = [str(item) for item in (matched_anchor or {}).get("source_material_ids", [])]
    if official_announcement:
        event_sources.append(f"announcement:{official_announcement[0]}")
    body_rows = [
        _row(
            "selected_event",
            事件编号=resolved_event_id,
            日期=anchor_date.isoformat(),
            标题=resolved_title,
            episode=episode_type,
        ),
        _row(
            "event_price_window",
            窗口=f"锚点前后各 10 个交易日（可得范围）",
            前端日期=str(prices[before_index][0])[:10],
            前端收盘=round(before_close, 2),
            锚点交易日=str(prices[anchor_index][0])[:10],
            锚点收盘=round(base_close, 2),
            后端日期=str(prices[after_index][0])[:10],
            后端收盘=round(after_close, 2),
            后段变化=f"{(after_close / base_close - 1) * 100:.1f}%",
        ),
        *[
            _row(
                f"nearby_announcement_{index:02d}",
                巨潮公告ID=str(announcement_id),
                日期=str(announcement_date)[:10],
                标题=str(title),
                原文=str(url or ""),
            )
            for index, (announcement_id, announcement_date, title, url)
            in enumerate(announcements, 1)
        ],
    ]

    topic_terms: list[str] = []
    if "restructuring" in episode_type:
        topic_terms = ["重整", "资产重组", "资产注入", "共益债"]
    elif "control" in episode_type or "investor" in episode_type:
        topic_terms = ["股东行为", "拍卖", "控制权", "原实控人"]
    invocations = [
        _REGISTRY.invoke(record, "选中节点的事件解释边界")
        for record in _REGISTRY.candidate_lenses(topic_terms=topic_terms)
    ]
    gaps = [] if invocations else [LensGap(
        gap_id="stock_event_window_lens",
        missing_for="选中节点的可用 lens 解释",
        sediment_as="question_card:QC-20260710-004",
        note="价格、公告和 episode 可描述；无匹配 frozen lens 时不补造解释。",
    )]
    freshness = {
        "price_data_as_of": price_snapshot.as_of,
        "company_announcements_as_of": announcement_snapshot.as_of,
        "episode_index_as_of": episode_snapshot.as_of,
    }
    if invocations:
        freshness["release_library_frozen_at"] = _REGISTRY.frozen_at
    data_as_of = limiting_as_of(*freshness.values())
    provenance = [
        f"shared_data/v5/.../st_stocks_v5_backup.sqlite3::daily_prices[{symbol}]",
        f"shared_data/v5/.../st_stocks_v5_backup.sqlite3::company_announcements[{symbol}]",
        "shared_data/v7/episode_index_v0/episode_index.jsonl",
        *event_sources,
    ]
    if invocations:
        provenance.append("shared_data/v7/release_library_v1/release_library.json")
    return AnswerCard(
        question=f"{symbol} 在 {anchor_date.isoformat()} 的节点前后发生了什么？",
        object_ref=f"stock:{symbol};{resolved_event_id};episode:{episode_type}",
        view="query",
        as_of=data_as_of,
        sample_scope=(
            f"{symbol} 单票；选中节点 1 个；邻近公告 {len(announcements)} 条；"
            "价格窗口为锚点前后各 10 个交易日"
        ),
        evidence_grade="descriptive_query",
        lens_invocations=invocations,
        lens_gap=gaps,
        episode_index_version=episode_snapshot.version,
        data_snapshot_as_of=data_as_of,
        source_freshness=freshness,
        body_rows=body_rows,
        analysis_claims=[
            AnalysisClaim(
                text="节点窗口只描述公开公告、episode 分类和可复算价格，不推断后续方向。",
                claim_type="caveat",
                backing=BackingRef(kind="query_row", ref="selected_event"),
            )
        ],
        caveats=FIXED_CAVEATS + [
            "事件日非交易日时，价格锚点取不晚于事件日的最近交易日。",
            "前后窗口为描述性查询；episode 分类与 lens 只约束解释边界。",
        ],
        provenance=list(dict.fromkeys(provenance)),
    )


def card_consolidation_checklist(symbol: str = "603398", band: float = 0.25, window: int = 42) -> AnswerCard:
    """#03 沐邦平台整理。lens：C17 短窗波动收敛(evidence, C17 wording 边界) + 股东行为/控制权 methodology。"""
    import numpy as np, pandas as pd
    episode_snapshot = load_episode_snapshot(EPISODE_INDEX, EPISODE_MANIFEST)
    con = _db()
    p = pd.read_sql("select trade_date,close from daily_prices where symbol=? and adjust='qfq' order by trade_date",
                    con, params=(symbol,))
    con.close()
    if p.empty:
        raise StockNotFoundError(f"当前快照无股票 {symbol} 的 qfq 价格数据")
    price_snapshot = load_price_snapshot(BASE_DB, symbol=symbol)
    p["trade_date"] = pd.to_datetime(p["trade_date"]); p = p.set_index("trade_date")
    rng = (p["close"].rolling(window).max() - p["close"].rolling(window).min()) / p["close"].rolling(window).mean()
    plat = p[rng < band]
    latest = None
    if len(plat):
        grp = (plat.index.to_series().diff().dt.days > 5).cumsum()
        seg = list(plat.groupby(grp))[-1][1]
        latest = f"{seg.index.min().date()}~{seg.index.max().date()}（均价{seg['close'].mean():.2f}）"
    fam: dict[str, int] = {}
    n_nodes = 0
    for d in _iter_episodes(symbol):
        for e in d.get("anchor_events", []):
            if e.get("announcement_date"):
                n_nodes += 1
                fam[d.get("episode_type", "?")] = fam.get(d.get("episode_type", "?"), 0) + 1
    top = sorted(fam.items(), key=lambda x: -x[1])[:5]
    body = [
        _row("risk_warning_window", **{
            "该看的窗口": "退市风险警示节点串",
            "依据": "风险警示、可能终止上市及撤销风险警示的正式公告",
        }),
        _row("restructuring_window", **{
            "该看的窗口": "预重整与重整推进",
            "依据": "预重整启动、重整进展、投资人招募及协议节点",
        }),
        _row("volatility_window", **{
            "该看的窗口": "短窗波动是否继续收敛",
            "依据": "前复权价格的短窗形态；只描述波动，不解释方向",
            "当前机械平台段": latest or "未检出",
        }),
        _row("controller_window", **{
            "该看的窗口": "控股股东与控制权处置",
            "依据": "冻结、拍卖、过户及控制权变更的正式公告",
        }),
        _row("abnormal_move_window", **{
            "该看的窗口": "交易异常波动与平台变化",
            "依据": "异常波动公告及价格区间被打破的日期",
        }),
    ]
    # ---- lens binding ----
    invs = []
    for r in _REGISTRY.candidate_lenses(clusters=["C17"]):
        invs.append(_REGISTRY.invoke(r, "均线回踩/短窗波动收敛窗口（守 C17 wording：非上涨信号）"))
    for r in _REGISTRY.candidate_lenses(topic_terms=["股东行为", "拍卖", "控制权", "原实控人"]):
        invs.append(_REGISTRY.invoke(r, "控股股东/控制权观察清单项"))
    gaps = []
    if not invs:
        gaps = [LensGap(
            gap_id="consolidation_case_framework",
            missing_for="平台整理个案框架",
            sediment_as="question_card:QC-20260710-015",
        )]
    return AnswerCard(
        question=f"{symbol} 平台整理期该看哪些窗口？",
        object_ref=f"stock:{symbol}（最近平台段 {latest or '未检出'}）",
        view="checklist", as_of=limiting_as_of(
            price_snapshot.as_of, episode_snapshot.as_of, _REGISTRY.frozen_at
        ),
        sample_scope=f"{symbol} 单票：{n_nodes} 个已分类事件节点；近期节点构成：" +
                     ", ".join(f"{k}×{v}" for k, v in top),
        evidence_grade="anecdotal_support",
        episode_index_version=episode_snapshot.version,
        data_snapshot_as_of=limiting_as_of(
            price_snapshot.as_of, episode_snapshot.as_of, _REGISTRY.frozen_at
        ),
        source_freshness={
            "price_data_as_of": price_snapshot.as_of,
            "episode_index_as_of": episode_snapshot.as_of,
            "release_library_frozen_at": _REGISTRY.frozen_at,
        },
        lens_invocations=invs, lens_gap=gaps,
        body_rows=body,
        analysis_claims=[
            AnalysisClaim(
                text="C17 只支持短窗波动收敛描述，不能提供方向性解释。",
                claim_type="caveat",
                backing=BackingRef(kind="lens_invocation", ref="RL-A-003"),
            )
        ] if any(inv.release_id == "RL-A-003" for inv in invs) else [],
        caveats=FIXED_CAVEATS + [
            "个案叙事，不预测突破方向；C17 lens 只表短窗波动收敛，非上涨信号（D-037）；平台段为固定带宽机械检测。"],
        provenance=[f"shared_data/v5/.../st_stocks_v5_backup.sqlite3::daily_prices[{symbol}]",
                    "shared_data/v7/episode_index_v0/episode_index.jsonl",
                    "shared_data/v7/release_library_v1/release_library.json"])


def card_release_lens_evidence(release_id: str) -> AnswerCard:
    """直接消费 frozen evidence lens，展示 N、effect digest、反例和措辞边界。"""
    record = _REGISTRY.get(release_id)
    if record.get("release_role") != "evidence_lens":
        raise ValueError(f"{release_id} 不是 evidence_lens")

    sample_n = record["sample_n"]
    invocation = _REGISTRY.invoke(record, "历史日历窗口证据、反例与措辞边界")
    row_id = f"release_evidence_{release_id.lower().replace('-', '_')}"
    body = _row(
        row_id,
        **{
            "release_id": release_id,
            "历史证据等级": record["evidence_grade"],
            "触发样本N": sample_n["trigger"],
            "对照样本N": sample_n["control"],
            "effect_digest": record.get("effect_digest", {}),
            "反例形状": record["counterexample_shape"],
            "允许措辞": record["v8_allowed_wording"],
        },
    )
    provenance = [
        "shared_data/v7/release_library_v1/release_library.json",
        record["validation_report_ref"],
        record["effect_report_ref"],
    ]
    return AnswerCard(
        question=f"{release_id} 的历史先验、反例和使用边界是什么？",
        object_ref=f"lens:{release_id}",
        view="evidence",
        as_of=record["as_of"],
        sample_scope=(
            f"{record['cohort_id']}；trigger N={sample_n['trigger']}；"
            f"control N={sample_n['control']}"
        ),
        evidence_grade=record["evidence_grade"],
        data_snapshot_as_of=record["as_of"],
        source_freshness={"release_library_frozen_at": _REGISTRY.frozen_at},
        lens_invocations=[invocation],
        body_rows=[body],
        analysis_claims=[
            AnalysisClaim(
                text=(
                    f"{release_id} 是带验证报告的历史弱先验；"
                    "使用时必须同时展示样本量、反例和语料边界。"
                ),
                claim_type="fact",
                backing=BackingRef(kind="lens_invocation", ref=release_id),
            )
        ],
        caveats=FIXED_CAVEATS + list(record.get("caveats", [])[:2]) + [
            record["source_universe_caveat"],
        ],
        provenance=provenance,
    )


def card_calendar_regime_evidence(release_id: str = "RL-A-001") -> AnswerCard:
    """兼容 P1 seed 名称；实际由通用 frozen evidence builder 生成。"""
    return card_release_lens_evidence(release_id)


def card_control_structure_methodology() -> AnswerCard:
    """控制权/股东行为只作为方法论观察框架，不升级为 evidence。"""
    records = _REGISTRY.candidate_lenses(
        topic_terms=["股东行为", "拍卖", "控制权", "原实控人"]
    )
    invocations = [
        _REGISTRY.invoke(record, "控制权与股东行为观察框架") for record in records
    ]
    if not invocations:
        raise ValueError("release library 无控制权/股东行为 methodology lens")
    body_rows = [
        _row(
            f"methodology_{invocation.release_id.lower().replace('-', '_')}",
            **{
                "release_id": invocation.release_id,
                "逻辑链": invocation.logic_chain_summary,
                "允许措辞": invocation.allowed_wording,
            },
        )
        for invocation in invocations
    ]
    data_as_of = str(_REGISTRY.frozen_at)[:10]
    return AnswerCard(
        question="控股股东、司法拍卖和控制权变化应该如何组织观察？",
        object_ref="methodology:control_structure",
        view="methodology",
        as_of=data_as_of,
        sample_scope=f"frozen release library 中 {len(invocations)} 条 methodology frame",
        evidence_grade="context_only",
        data_snapshot_as_of=data_as_of,
        source_freshness={"release_library_frozen_at": _REGISTRY.frozen_at},
        lens_invocations=invocations,
        body_rows=body_rows,
        analysis_claims=[
            AnalysisClaim(
                text="这些记录约束观察维度和措辞，不构成历史效果证据。",
                claim_type="caveat",
                backing=BackingRef(
                    kind="lens_invocation", ref=invocations[0].release_id
                ),
            )
        ],
        caveats=FIXED_CAVEATS + [
            "methodology frame 只约束分析方式，不携带效果结论。"
        ],
        provenance=[
            "shared_data/v7/release_library_v1/release_library.json",
            *[
                provenance_ref
                for invocation in invocations
                for provenance_ref in invocation.provenance_refs
            ],
        ],
    )


DATA_DEBT_CATALOG: dict[str, dict[str, str]] = {
    "D-051A": {
        "gap": "symbol→省份/注册地映射",
        "affects": "省份分层",
        "provenance": "v7_worksite/coordination/debt_cards/D-051A_province_mapping.md",
        "as_of": "2026-07-10",
    },
    "D-051B": {
        "gap": "庭外/庭内重整标记",
        "affects": "重整路径阶段分层",
        "provenance": "v7_worksite/coordination/debt_cards/D-051B_out_of_court_flag.md",
        "as_of": "2026-07-10",
    },
    "D-051C": {
        "gap": "大盘指数日线序列",
        "affects": "相对大盘分布",
        "provenance": "v7_worksite/coordination/debt_cards/D-051C_market_index_series.md",
        "as_of": "2026-07-10",
    },
    "C14": {
        "gap": "as-of 市值/股本",
        "affects": "微盘 cohort 定义",
        "provenance": "shared_data/v7/release_library_v1/release_library.json",
        "as_of": "2026-07-10",
    },
    "D-021": {
        "gap": "股东人数全量覆盖",
        "affects": "ST 前后股东人数变化比较",
        "provenance": "v7_worksite/coordination/decisions.md#D-021",
        "as_of": "2026-07-10",
    },
}


def card_data_debt(
    question: str,
    object_ref: str,
    debt_refs: list[str],
) -> AnswerCard:
    """把已登记数据债转换为合法 AnswerCard；未知 debt id 直接失败。"""
    unknown = [debt_ref for debt_ref in debt_refs if debt_ref not in DATA_DEBT_CATALOG]
    if unknown:
        raise ValueError(f"未知 data debt id: {unknown}")
    if not debt_refs:
        raise ValueError("data_debt AnswerCard 至少需要一个已登记 debt id")

    rows = [
        DataDebtRow(
            gap=DATA_DEBT_CATALOG[debt_ref]["gap"],
            affects=DATA_DEBT_CATALOG[debt_ref]["affects"],
            debt_ref=debt_ref,
        )
        for debt_ref in debt_refs
    ]
    gaps = [
        LensGap(
            gap_id=f"data_debt_{debt_ref.lower().replace('-', '_')}",
            missing_for=DATA_DEBT_CATALOG[debt_ref]["affects"],
            sediment_as=f"data_debt:{debt_ref}",
            note="该缺口已进入统一数据债台账。",
        )
        for debt_ref in debt_refs
    ]
    data_as_of = limiting_as_of(
        *(DATA_DEBT_CATALOG[debt_ref]["as_of"] for debt_ref in debt_refs)
    )
    return AnswerCard(
        question=question,
        object_ref=object_ref,
        view="data_debt",
        as_of=data_as_of,
        sample_scope="请求维度所需字段在当前只读快照中不可用",
        evidence_grade="insufficient_data",
        data_snapshot_as_of=data_as_of,
        source_freshness={"data_debt_registry_as_of": data_as_of},
        lens_gap=gaps,
        analysis_claims=[
            AnalysisClaim(
                text=f"{DATA_DEBT_CATALOG[debt_ref]['affects']} 当前不可答。",
                claim_type="data_gap",
                backing=BackingRef(kind="data_debt", ref=debt_ref),
            )
            for debt_ref in debt_refs
        ],
        data_debt=rows,
        data_debt_refs=debt_refs,
        caveats=FIXED_CAVEATS + ["缺字段时不使用文本猜测、代理字段或静默降维。"],
        provenance=[DATA_DEBT_CATALOG[debt_ref]["provenance"] for debt_ref in debt_refs],
    )


def card_province_mapping_debt() -> AnswerCard:
    """省份分层不可答时的稳定 data-debt 出口。"""
    gap_id = "province_mapping_missing"
    debt_ref = "D-051A"
    return AnswerCard(
        question="重整路径按省份分层如何？",
        object_ref="cohort:restructuring_by_province",
        view="data_debt",
        as_of=DATA_DEBT_CATALOG[debt_ref]["as_of"],
        sample_scope="当前 base DB 无 symbol→省份/注册地映射，无法形成省份分层样本",
        evidence_grade="insufficient_data",
        data_snapshot_as_of=DATA_DEBT_CATALOG[debt_ref]["as_of"],
        source_freshness={
            "data_debt_registry_as_of": DATA_DEBT_CATALOG[debt_ref]["as_of"]
        },
        lens_gap=[LensGap(
            gap_id=gap_id,
            missing_for="省份/注册地分层",
            sediment_as=f"data_debt:{debt_ref}",
            note="缺 symbol 到省份/注册地的稳定映射；不从公司名称或公告文本猜测。",
        )],
        analysis_claims=[
            AnalysisClaim(
                text="当前不能按省份给出分布，缺口已进入统一数据债台账。",
                claim_type="data_gap",
                backing=BackingRef(kind="data_debt", ref=debt_ref),
            )
        ],
        data_debt=[DataDebtRow(
            gap="symbol→省份/注册地映射",
            affects="重整路径的省份分层",
            debt_ref=debt_ref,
        )],
        data_debt_refs=[debt_ref],
        caveats=FIXED_CAVEATS + ["缺字段时不从公司名称、简称或公告措辞推断省份。"],
        provenance=["v7_worksite/coordination/debt_cards/D-051A_province_mapping.md"],
    )


def card_stock_research_overview(
    symbol: str,
    question: str,
    dimensions: Iterable[str] = (),
) -> AnswerCard:
    """Answer an open stock question from available read-only dimensions."""
    requested = set(dimensions)
    card = card_st_status_timeline(symbol)
    card.question = question
    matched_announcements: list[OfficialAnnouncement] = []

    if requested & {"shareholder_count", "equity", "capital_structure", "control_structure"}:
        control_records = _REGISTRY.candidate_lenses(
            topic_terms=["股东行为", "拍卖", "原实控人", "控制权"],
        )
        existing_release_ids = {invocation.release_id for invocation in card.lens_invocations}
        card.lens_invocations.extend(
            _REGISTRY.invoke(record, "股东、股权与控制权字段的解释框架")
            for record in control_records
            if str(record["release_id"]) not in existing_release_ids
        )

    if not requested or "announcement" in requested:
        inventory = load_announcement_inventory(
            symbol=symbol,
            base_db=BASE_DB,
            refresh_dir=ANNOUNCEMENT_REFRESH_DIR,
        )
        normalized_question = "".join(question.lower().split())
        full_dates = {
            f"{year}-{int(month):02d}-{int(day):02d}"
            for year, month, day in re.findall(
                r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})日?",
                normalized_question,
            )
        }
        month_days = {
            f"-{int(month):02d}-{int(day):02d}"
            for month, day in re.findall(r"(?<!\d)(\d{1,2})月(\d{1,2})日", normalized_question)
        }
        if full_dates:
            month_days = set()
        term_groups = (
            ("投资协议", ("投资协议", "重整投资协议")),
            ("公开招募", ("公开招募", "招募", "重整投资人")),
            ("预重整", ("预重整",)),
            ("重整", ("重整",)),
            ("风险警示", ("风险警示",)),
        )
        if "投资协议" in normalized_question and "重整" in normalized_question:
            required_term_groups = (("投资协议",), ("重整",))
        else:
            first_terms = next(
                (terms for marker, terms in term_groups if marker in normalized_question),
                (),
            )
            required_term_groups = (first_terms,) if first_terms else ()
        search_terms = tuple(
            term for group in required_term_groups for term in group
        )

        def matches_question(record: OfficialAnnouncement) -> bool:
            date_matches = (
                not full_dates and not month_days
                or record.announcement_date in full_dates
                or any(record.announcement_date.endswith(item) for item in month_days)
            )
            title_matches = not required_term_groups or all(
                any(term in record.title for term in group)
                for group in required_term_groups
            )
            return date_matches and title_matches

        matched_announcements = [
            record for record in inventory.records if matches_question(record)
        ] if full_dates or month_days or search_terms else []
        selected_announcements = list(dict.fromkeys([
            *matched_announcements,
            *inventory.records[:8],
        ]))[:8]
        existing_ids = {
            str(row.get("巨潮公告ID"))
            for row in card.body_rows
            if row.get("巨潮公告ID")
        }
        official_row_ids: list[str] = []
        for index, record in enumerate(selected_announcements, 1):
            if record.announcement_id in existing_ids:
                continue
            row_id = f"recent_official_announcement_{index:02d}"
            official_row_ids.append(row_id)
            card.body_rows.append(_row(
                row_id,
                **{
                    "记录类型": "近期官方公告",
                    "巨潮公告ID": record.announcement_id,
                    "日期": record.announcement_date,
                    "标题": record.title,
                    "来源范围": (
                        "CNINFO 本地增量快照"
                        if record.source == "cninfo_local_refresh"
                        else "冻结 v5 公告快照"
                    ),
                    "原文链接": record.url or "当前快照未记录链接",
                    "正文状态": "已采集" if record.body_available else "未采集，仅可核对标题与日期",
                },
            ))
        body_focus = any(term in normalized_question for term in (
            "说了什么", "公告内容", "具体内容", "最新公告", "主要内容",
        ))
        body_record = (
            matched_announcements[0]
            if matched_announcements
            else (selected_announcements[0] if body_focus and selected_announcements else None)
        )
        if body_record is not None:
            try:
                body = load_announcement_body(
                    body_record, source_db=BASE_DB, allow_network=False
                )
                excerpts = relevant_excerpt(body.text, question)
                card.body_rows.append(_row(
                    "official_announcement_body_01",
                    **{
                        "记录类型": "公告正文证据",
                        "巨潮公告ID": body_record.announcement_id,
                        "公告编号": official_announcement_number(body.text) or "正文未抽取",
                        "日期": body_record.announcement_date,
                        "标题": body_record.title,
                        "正文页数": body.page_count or "原始文本快照",
                        "正文字符数": len(body.text),
                        "正文来源": body.source,
                        "正文证据片段": excerpts or [body.text[:1200]],
                        "原文链接": body.source_url,
                    },
                ))
                card.analysis_claims.append(AnalysisClaim(
                    text=(
                        "已读取本地冻结公告正文；答案中的内容判断只可引用正文证据片段。"
                        if body.source.startswith("embedded_")
                        else "已读取本地缓存的官方公告 PDF 正文；答案中的内容判断只可引用正文证据片段。"
                    ),
                    claim_type="fact",
                    backing=BackingRef(kind="query_row", ref="official_announcement_body_01"),
                ))
                if body.source == "cache":
                    card.provenance.append(
                        "local_data/v8_copilot/announcement_bodies/"
                        f"{body_record.announcement_id[:4]}/{body_record.announcement_id}.json"
                    )
            except AnnouncementBodyError as exc:
                gap = LensGap(
                    gap_id="announcement_body_unavailable",
                    missing_for=f"公告 {body_record.announcement_id} 的可提取正文",
                    sediment_as="question_card:announcement_body_unavailable",
                    note=str(exc),
                )
                if not any(item.gap_id == gap.gap_id for item in card.lens_gap):
                    card.lens_gap.append(gap)
                card.analysis_claims.append(AnalysisClaim(
                    text="官方公告正文读取失败，当前只能确认标题、日期和原文链接。",
                    claim_type="data_gap",
                    backing=BackingRef(kind="lens_gap", ref=gap.gap_id),
                ))
        if full_dates or month_days or search_terms:
            latest_match = matched_announcements[0] if matched_announcements else None
            card.body_rows.append(_row(
                "announcement_query_summary",
                **{
                    "记录类型": "题面公告检索",
                    "检索日期": (
                        ", ".join(sorted(full_dates))
                        if full_dates
                        else ", ".join(
                            f"{int(value[1:3])}月{int(value[4:6])}日"
                            for value in sorted(month_days)
                        ) or "未限定"
                    ),
                    "标题关键词": ", ".join(search_terms) or "未限定",
                    "标题与日期命中数": len(matched_announcements),
                    "最近命中": (
                        f"{latest_match.announcement_date}《{latest_match.title}》"
                        if latest_match else "未命中"
                    ),
                    "检索边界": "检索正式公告标题与日期；正文未采集时不能据此解释公告内容",
                },
            ))
        if official_row_ids:
            card.analysis_claims.append(AnalysisClaim(
                text=f"正式公告清单共 {len(inventory.records)} 条，当前展示最近或题面命中的记录。",
                claim_type="fact",
                backing=BackingRef(kind="query_row", ref=official_row_ids[0]),
            ))
        card.source_freshness["company_announcements_as_of"] = inventory.announcement_as_of
        if inventory.refresh_checked_at:
            card.source_freshness["announcement_refresh_checked_at"] = (
                inventory.refresh_checked_at
            )
        card.provenance.append(
            f"shared_data/v5/.../st_stocks_v5_backup.sqlite3::company_announcements[{symbol}]"
        )
        if inventory.refresh_count:
            card.provenance.append(
                f"local_data/v8_copilot/announcement_refresh/{symbol}.json"
            )

    if "price" in requested:
        with _db() as connection:
            prices = connection.execute(
                "select trade_date,close,turnover_rate from daily_prices "
                "where symbol=? and adjust='qfq' order by trade_date desc limit 61",
                (symbol,),
            ).fetchall()
        prices = list(reversed(prices))
        if prices:
            price_snapshot = load_price_snapshot(BASE_DB, symbol=symbol)
            latest_date, latest_close, _ = prices[-1]
            values = [float(row[1]) for row in prices]
            price_row: dict[str, Any] = {
                "记录类型": "近期价格窗口",
                "截至": str(latest_date)[:10],
                "最新收盘": round(float(latest_close), 2),
                "窗口最低": round(min(values), 2),
                "窗口最高": round(max(values), 2),
            }
            for window in (10, 20, 60):
                if len(prices) > window:
                    price_row[f"近{window}日变化"] = (
                        f"{(float(latest_close) / float(prices[-window - 1][1]) - 1) * 100:.1f}%"
                    )
            turnover = [float(row[2]) for row in prices[-20:] if row[2] is not None]
            if turnover:
                price_row["近20日平均换手率"] = f"{statistics.mean(turnover):.2f}%"
            card.body_rows.append(_row("recent_price_window", **price_row))
            card.analysis_claims.append(AnalysisClaim(
                text="近期价格窗口由前复权日线机械计算，只描述历史区间，不解释方向。",
                claim_type="caveat",
                backing=BackingRef(kind="query_row", ref="recent_price_window"),
            ))
            if "后" in question and matched_announcements:
                event = matched_announcements[0]
                with _db() as connection:
                    event_prices = connection.execute(
                        "select trade_date,close from daily_prices "
                        "where symbol=? and adjust='qfq' and trade_date>=? "
                        "order by trade_date limit 11",
                        (symbol, event.announcement_date),
                    ).fetchall()
                coverage: dict[str, Any] = {
                    "记录类型": "公告后价格覆盖",
                    "公告日期": event.announcement_date,
                    "公告标题": event.title,
                    "价格截至": price_snapshot.as_of,
                }
                if event.announcement_date > price_snapshot.as_of or not event_prices:
                    coverage["结论"] = "价格快照早于该公告，当前无法计算公告后的价格表现"
                    claim_type = "data_gap"
                    claim_text = (
                        f"价格快照截至 {price_snapshot.as_of}，早于 {event.announcement_date} 的公告，"
                        "当前不能回答公告后的价格表现。"
                    )
                else:
                    base_date, base_close = event_prices[0]
                    coverage["基准交易日"] = str(base_date)[:10]
                    coverage["基准收盘"] = round(float(base_close), 2)
                    for offset in (1, 5, 10):
                        if len(event_prices) > offset:
                            coverage[f"T+{offset}变化"] = (
                                f"{(float(event_prices[offset][1]) / float(base_close) - 1) * 100:.1f}%"
                            )
                    coverage["结论"] = "按前复权收盘价机械计算，不解释方向"
                    claim_type = "caveat"
                    claim_text = "公告后价格窗口按前复权收盘价机械计算，只描述历史变化。"
                card.body_rows.append(_row("requested_event_price_window", **coverage))
                card.analysis_claims.append(AnalysisClaim(
                    text=claim_text,
                    claim_type=claim_type,
                    backing=BackingRef(kind="query_row", ref="requested_event_price_window"),
                ))
            card.source_freshness["price_data_as_of"] = price_snapshot.as_of
        else:
            gap = LensGap(
                gap_id="stock_price_coverage",
                missing_for=f"{symbol} 的前复权价格窗口",
                sediment_as="question_card:stock_price_coverage",
                note="当前只读价格快照无该股票记录。",
            )
            card.lens_gap.append(gap)
            card.analysis_claims.append(AnalysisClaim(
                text="当前快照没有该股票的可复算价格窗口。",
                claim_type="data_gap",
                backing=BackingRef(kind="lens_gap", ref=gap.gap_id),
            ))
        card.provenance.append(
            f"shared_data/v5/.../st_stocks_v5_backup.sqlite3::daily_prices[{symbol}]"
        )

    if "shareholder_count" in requested:
        shareholder_snapshot = load_table_snapshot(
            SHAREHOLDER_DB,
            table="shareholder_count_snapshots",
            date_column="report_date",
        )
        with sqlite3.connect(f"file:{SHAREHOLDER_DB}?mode=ro", uri=True) as connection:
            holders = connection.execute(
                "select report_date,holder_count,holder_count_delta,holder_count_delta_pct "
                "from shareholder_count_snapshots where symbol=? "
                "order by report_date desc limit 8",
                (symbol,),
            ).fetchall()
        for index, (report_date, holder_count, delta, delta_pct) in enumerate(holders, 1):
            card.body_rows.append(_row(
                f"shareholder_count_{index:02d}",
                **{
                    "记录类型": "股东人数",
                    "报告期": str(report_date)[:10],
                    "股东人数": int(holder_count),
                    "较上期变化": delta if delta is not None else "无上期值",
                    "较上期变化率": (
                        f"{float(delta_pct):.1f}%" if delta_pct is not None else "无上期值"
                    ),
                },
            ))
        if holders:
            card.analysis_claims.append(AnalysisClaim(
                text=f"股东人数 pilot 对该股票提供最近 {len(holders)} 个报告期快照。",
                claim_type="fact",
                backing=BackingRef(kind="query_row", ref="shareholder_count_01"),
            ))
        else:
            gap = LensGap(
                gap_id="shareholder_count_coverage",
                missing_for=f"{symbol} 的结构化股东人数快照",
                sediment_as="question_card:shareholder_count_coverage",
                note="当前 57 股 pilot 没有该股票记录；不把全局 pilot 截止日当作个股覆盖。",
            )
            card.lens_gap.append(gap)
            card.analysis_claims.append(AnalysisClaim(
                text="当前股东人数 pilot 没有该股票的结构化记录。",
                claim_type="data_gap",
                backing=BackingRef(kind="lens_gap", ref=gap.gap_id),
            ))
        if "D-021" not in card.data_debt_refs:
            card.data_debt.append(DataDebtRow(
                gap="股东人数当前只有 57 股 pilot，非全市场完整覆盖",
                affects="跨股票异常比较和全样本历史先验",
                debt_ref="D-021",
            ))
            card.data_debt_refs.append("D-021")
        card.source_freshness["shareholder_count_as_of"] = shareholder_snapshot.as_of
        card.provenance.append(
            f"shared_data/v7/shareholder_count_pilot/shareholder_count.sqlite3::shareholder_count_snapshots[{symbol}]"
        )

    if requested & {"equity", "capital_structure"}:
        with sqlite3.connect(f"file:{SHAREHOLDER_DB}?mode=ro", uri=True) as connection:
            equity_events = connection.execute(
                "select event_date,event_category,event_type,event_title,actor,shares_delta,pct_total_after "
                "from equity_timeline_events where symbol=? order by event_date desc limit 8",
                (symbol,),
            ).fetchall()
        for index, event in enumerate(equity_events, 1):
            event_date, category, event_type, title, actor, shares_delta, pct_total = event
            card.body_rows.append(_row(
                f"equity_event_{index:02d}",
                **{
                    "记录类型": "股权事件",
                    "日期": str(event_date)[:10],
                    "类别": category,
                    "类型": event_type,
                    "标题": title,
                    "主体": actor or "未结构化",
                    "股份变化": shares_delta if shares_delta is not None else "未结构化",
                    "占总股本": (
                        f"{float(pct_total):.2f}%" if pct_total is not None else "未结构化"
                    ),
                },
            ))
        if equity_events:
            equity_snapshot = load_table_snapshot(
                SHAREHOLDER_DB,
                table="equity_timeline_events",
                date_column="event_date",
            )
            card.analysis_claims.append(AnalysisClaim(
                text=f"股权事件 pilot 对该股票提供最近 {len(equity_events)} 个结构化节点。",
                claim_type="fact",
                backing=BackingRef(kind="query_row", ref="equity_event_01"),
            ))
            card.source_freshness["equity_timeline_as_of"] = equity_snapshot.as_of
        else:
            gap = LensGap(
                gap_id="equity_timeline_coverage",
                missing_for=f"{symbol} 的结构化股权/股本时间线",
                sediment_as="question_card:equity_timeline_coverage",
                note="当前 pilot 没有该股票的结构化股权事件；不从公告标题推算股份变化。",
            )
            card.lens_gap.append(gap)
            card.analysis_claims.append(AnalysisClaim(
                text="当前 pilot 没有该股票的结构化股权/股本事件。",
                claim_type="data_gap",
                backing=BackingRef(kind="lens_gap", ref=gap.gap_id),
            ))
        card.provenance.append(
            f"shared_data/v7/shareholder_count_pilot/shareholder_count.sqlite3::equity_timeline_events[{symbol}]"
        )

    dimension_labels = {
        "announcement": "正式公告",
        "price": "价格与换手率",
        "shareholder_count": "股东人数",
        "equity": "股权事件",
        "capital_structure": "股本结构",
        "control_structure": "控制权",
    }
    loaded_dimensions = ", ".join(
        dimension_labels.get(dimension, dimension)
        for dimension in sorted(requested)
    ) or "基础概览"
    card.sample_scope += f"；按题面加载维度：{loaded_dimensions}"
    relevant_freshness: list[str] = []
    if "announcement" in requested:
        relevant_freshness.append(card.source_freshness["company_announcements_as_of"])
    if "price" in requested:
        relevant_freshness.append(card.source_freshness["price_data_as_of"])
    if "shareholder_count" in requested:
        relevant_freshness.append(card.source_freshness["shareholder_count_as_of"])
    if requested & {"equity", "capital_structure"} and "equity_timeline_as_of" in card.source_freshness:
        relevant_freshness.append(card.source_freshness["equity_timeline_as_of"])
    normalized_question = "".join(question.lower().split())
    if any(term in normalized_question for term in (
        "为什么st", "为什么被st", "为何st", "st原因",
    )):
        relevant_freshness.extend([
            card.source_freshness["st_status_fetched_at"],
            card.source_freshness["st_evidence_generated_at"],
        ])
    if any(term in normalized_question for term in ("已分类", "事件节点", "关键节点")):
        relevant_freshness.append(card.source_freshness["episode_index_as_of"])
    if any(term in normalized_question for term in ("分析一下", "分析下", "综合分析", "整体分析")):
        status_rows = [
            row for row in card.body_rows if row.get("记录类型") == "状态区间"
        ]
        latest_status = status_rows[-1] if status_rows else None
        if latest_status:
            status_start = str(latest_status.get("开始日") or "")[:10]
            announcement_as_of = card.source_freshness.get("company_announcements_as_of", "")
            price_as_of = card.source_freshness.get("price_data_as_of", "")
            episode_as_of = card.source_freshness.get("stock_episode_latest_event", "")
            card.body_rows.append(_row(
                "analysis_freshness_boundary",
                **{
                    "记录类型": "分析时间边界",
                    "ST状态开始": status_start,
                    "公告截至": announcement_as_of,
                    "价格截至": price_as_of,
                    "事件索引截至": episode_as_of,
                    "公告覆盖ST后": bool(announcement_as_of and announcement_as_of >= status_start),
                    "价格覆盖ST后": bool(price_as_of and price_as_of >= status_start),
                    "事件覆盖ST后": bool(episode_as_of and episode_as_of >= status_start),
                },
            ))
            card.analysis_claims.append(AnalysisClaim(
                text="个股分析显式区分 ST 状态开始日与各数据源截止日。",
                claim_type="caveat",
                backing=BackingRef(kind="query_row", ref="analysis_freshness_boundary"),
            ))
    if any(term in normalized_question for term in ("分析一下", "分析下", "综合分析", "整体分析")):
        analysis_dates = [
            str(value)[:10]
            for row in card.body_rows
            for key, value in row.items()
            if key in {"开始日", "日期", "截至", "报告期"}
            and re.fullmatch(r"20\d{2}-\d{2}-\d{2}", str(value)[:10])
        ]
        card.as_of = max(analysis_dates) if analysis_dates else limiting_as_of(*card.source_freshness.values())
    else:
        card.as_of = limiting_as_of(*(
            relevant_freshness or list(card.source_freshness.values())
        ))
    card.data_snapshot_as_of = card.as_of
    card.provenance = list(dict.fromkeys(card.provenance))
    return card


def _restructuring_stage(title: str) -> str:
    if "重整投资协议" in title or ("投资协议" in title and "重整" in title):
        return "已披露重整投资协议"
    if "公开招募" in title or "招募重整投资人" in title:
        return "已公开招募重整投资人"
    if "重整计划" in title:
        return "已披露重整计划相关文件"
    if "裁定受理" in title or "受理重整" in title:
        return "法院已裁定受理重整"
    if "预重整" in title and any(term in title for term in ("受理", "决定", "启动")):
        return "已进入或启动预重整"
    if "预重整" in title and any(term in title for term in ("进展", "债权申报", "债权人会议")):
        return "预重整工作推进中"
    if "被债权人申请" in title or "债权人申请" in title:
        return "债权人已提出预重整或重整申请"
    if "重整" in title:
        return "其他重整进展披露"
    return "非重整节点"


def _historical_next_restructuring_rows(
    stage: str,
    *,
    subject_mode: str = "listed_company",
) -> list[dict[str, Any]]:
    next_any: list[tuple[str, int]] = []
    next_stage_transitions: list[tuple[str, int]] = []
    triggers: list[tuple[str, str, str]] = []
    stage_observed_triggers: set[tuple[str, str, str]] = set()

    subsidiary_terms = ("孙公司", "子公司")
    related_entity_terms = (*subsidiary_terms, "控股股东")

    def subject_matches(title: str) -> bool:
        if subject_mode == "subsidiary":
            return any(term in title for term in subsidiary_terms)
        return not any(term in title for term in related_entity_terms)

    for episode in _iter_episodes():
        if episode.get("episode_type") != "restructuring_path":
            continue
        symbol = str(episode.get("symbol") or "")
        episode_id = str(episode.get("episode_id") or "")
        events = sorted(
            (
                (str(anchor.get("announcement_date") or anchor.get("anchor_date") or ""),
                 str(anchor.get("title") or ""))
                for anchor in episode.get("anchor_events", [])
            ),
            key=lambda item: item[0],
        )
        eligible = [
            (index, event_date, title)
            for index, (event_date, title) in enumerate(events)
            if _restructuring_stage(title) == stage and subject_matches(title)
        ]
        if not eligible:
            continue
        # One episode is one case. Use the latest disclosure still in the
        # current stage so frequent progress notices do not overweight a case.
        index, event_date, _ = eligible[-1]
        trigger_key = (episode_id, symbol, event_date)
        triggers.append(trigger_key)
        start = _pd(event_date)
        for next_date, next_title in events[index + 1:]:
            if not subject_matches(next_title):
                continue
            end = _pd(next_date)
            if not start or not end or end <= start:
                continue
            next_stage_label = _restructuring_stage(next_title)
            if next_stage_label in {stage, "非重整节点"}:
                continue
            stage_observed_triggers.add(trigger_key)
            next_stage_transitions.append((next_stage_label, (end - start).days))
            break

    def announcement_category(title: str) -> str:
        stage_label = _restructuring_stage(title)
        if stage_label != "非重整节点":
            return stage_label
        if any(term in title for term in ("诉讼", "仲裁", "冻结")):
            return "诉讼、仲裁或冻结公告"
        if any(term in title for term in ("风险", "异常波动", "问询")):
            return "风险提示或监管公告"
        if any(term in title for term in ("年度报告", "审计", "业绩")):
            return "财务报告或审计公告"
        if any(term in title for term in ("董事", "股东会", "章程")):
            return "治理事项公告"
        return "其他正式公告"

    any_observed_triggers: set[tuple[str, str, str]] = set()
    unique_triggers = set(triggers)
    with _db() as connection:
        for episode_id, symbol, event_date in sorted(unique_triggers):
            row = connection.execute(
                "select announcement_date,title from company_announcements "
                "where symbol=? and announcement_date>? order by announcement_date,announcement_id limit 1",
                (symbol, event_date),
            ).fetchone()
            if row:
                start, end = _pd(event_date), _pd(str(row[0]))
                if start and end and end > start:
                    any_observed_triggers.add((episode_id, symbol, event_date))
                    next_any.append((announcement_category(str(row[1])), (end - start).days))

    rows: list[dict[str, Any]] = []
    for prefix, label, transitions, observed_triggers in (
        ("any", "下一个任意正式公告", next_any, any_observed_triggers),
        ("stage", "下一个不同重整阶段", next_stage_transitions, stage_observed_triggers),
    ):
        counts = Counter(category for category, _ in transitions)
        total = len(transitions)
        for index, (category, count) in enumerate(counts.most_common(4), 1):
            waits = [days for candidate, days in transitions if candidate == category]
            rows.append(_row(
                f"historical_next_{prefix}_{index:02d}",
                **{
                    "记录类型": "同阶段历史后续",
                    "后续口径": label,
                    "起点阶段": stage,
                    "后续类别": category,
                    "次数": count,
                    "占可观察后续": f"{count / total * 100:.1f}%" if total else "无样本",
                    "等待中位数(天)": statistics.median(waits) if waits else "无样本",
                    "可观察后续总数": total,
                    "起点事件总数": len(unique_triggers),
                    "未观察到后续": len(unique_triggers - observed_triggers),
                },
            ))
    return rows


def card_stock_restructuring_progress(symbol: str, question: str) -> AnswerCard:
    """Separate a stock's verified public milestone from cohort transitions."""
    inventory = load_announcement_inventory(
        symbol=symbol,
        base_db=BASE_DB,
        refresh_dir=ANNOUNCEMENT_REFRESH_DIR,
    )
    episode_snapshot = load_episode_snapshot(EPISODE_INDEX, EPISODE_MANIFEST)
    all_relevant = [record for record in inventory.records if "重整" in record.title]
    subsidiary_focus = any(term in question for term in ("孙公司", "子公司", "江西捷锐"))
    if subsidiary_focus:
        relevant = [
            record for record in all_relevant
            if any(term in record.title for term in ("孙公司", "子公司", "江西捷锐"))
        ]
        subject_scope = "子公司或孙公司"
    else:
        relevant = [
            record for record in all_relevant
            if not any(term in record.title for term in ("孙公司", "子公司", "控股股东"))
        ]
        subject_scope = "上市公司本体"
    current = relevant[0] if relevant else None
    if current is None:
        raise StockNotFoundError(f"{symbol} 当前公告清单没有重整节点")
    stage = _restructuring_stage(current.title)
    cohort_stage = stage
    recruitment = [
        record for record in relevant
        if "公开招募" in record.title or "招募重整投资人" in record.title
    ]
    body = None
    try:
        body = load_announcement_body(
            current, source_db=BASE_DB, allow_network=False
        )
        if "启动预重整" in body.text and "尚未收到" in body.text and "受理重整申请" in body.text:
            stage = "预重整已启动，尚未获法院正式受理重整"
    except AnnouncementBodyError:
        body = None
    rows = [_row(
        "current_restructuring_milestone",
        **{
            "记录类型": "当前公开里程碑",
            "股票": symbol,
            "主体范围": subject_scope,
            "日期": current.announcement_date,
            "公告清单截至": inventory.announcement_as_of,
            "标题": current.title,
            "阶段判断": stage,
            "公开招募记录": (
                f"已找到 {len(recruitment)} 条，最近为 {recruitment[0].announcement_date}"
                if recruitment else "当前正式公告清单未找到公开招募记录"
            ),
            "公开招募证据口径": "仅核查公司正式公告清单",
            "未覆盖渠道": "破产重整信息平台、管理人发布渠道及其他非公司公告来源",
            "原文链接": current.url or "当前快照未记录链接",
        },
    )]
    if body is not None:
        rows.append(_row(
            "current_restructuring_body",
            **{
                "记录类型": "当前里程碑正文证据",
                "巨潮公告ID": current.announcement_id,
                "正文证据片段": relevant_excerpt(body.text, question),
                "正文页数": body.page_count or "原始文本快照",
                "正文来源": body.source,
                "原文链接": body.source_url,
            },
        ))
    historical_rows = _historical_next_restructuring_rows(
        cohort_stage,
        subject_mode="subsidiary" if subsidiary_focus else "listed_company",
    )
    rows.extend(historical_rows)
    cands = _REGISTRY.candidate_lenses(
        clusters=["C04"], topic_terms=["重整", "资产重组", "资产注入"]
    )
    invocations = [_REGISTRY.invoke(item, "重整路径的解释边界") for item in cands]
    gap = LensGap(
        gap_id="stock_restructuring_transition_evidence",
        missing_for="该股票当前阶段到下一阶段的验证型预测证据",
        sediment_as="question_card:stock_restructuring_transition_evidence",
        note="历史后续类别只作描述性参照，不等于该股票将按同一路径推进。",
    )
    channel_gap = LensGap(
        gap_id="restructuring_recruitment_channel_coverage",
        missing_for="非公司正式公告渠道的公开招募进展",
        sediment_as="data_debt:restructuring_recruitment_channel_coverage",
        note="当前 Answer 只读来源未覆盖破产重整信息平台或管理人发布渠道。",
    )
    claims = [
        AnalysisClaim(
            text=f"当前正式公告可确认的里程碑是：{stage}。",
            claim_type="fact",
            backing=BackingRef(kind="query_row", ref="current_restructuring_milestone"),
        ),
        AnalysisClaim(
            text="历史后续频率描述同类样本，不是对该股票下一份公告的预测。",
            claim_type="caveat",
            backing=BackingRef(kind="lens_gap", ref=gap.gap_id),
        ),
        AnalysisClaim(
            text=(
                "本题只核查公司正式公告清单，未覆盖破产重整信息平台、管理人发布渠道"
                "或其他非公司公告来源；不能据此判断实际公开招募是否已经开始。"
            ),
            claim_type="data_gap",
            backing=BackingRef(kind="lens_gap", ref=channel_gap.gap_id),
        ),
    ]
    if historical_rows:
        claims.append(AnalysisClaim(
            text="已按当前阶段汇总历史样本中的首个后续分类节点。",
            claim_type="fact",
            backing=BackingRef(kind="query_row", ref=historical_rows[0]["row_id"]),
        ))
    as_of = limiting_as_of(inventory.announcement_as_of, episode_snapshot.as_of)
    return AnswerCard(
        question=question,
        object_ref=f"stock:{symbol}",
        view="query",
        as_of=as_of,
        sample_scope=(
            f"{symbol} 正式公告 {len(inventory.records)} 条；{subject_scope}重整标题节点 {len(relevant)} 条；"
            f"同阶段历史可观察后续 {historical_rows[0]['可观察后续总数'] if historical_rows else 0} 个"
        ),
        evidence_grade="descriptive_query",
        lens_invocations=invocations,
        lens_gap=[gap, channel_gap],
        episode_index_version=episode_snapshot.version,
        data_snapshot_as_of=as_of,
        source_freshness={
            "company_announcements_as_of": inventory.announcement_as_of,
            "episode_index_as_of": episode_snapshot.as_of,
        },
        body_rows=rows,
        analysis_claims=claims,
        caveats=FIXED_CAVEATS + [
            "当前阶段只按已公开公告判定；没有公告时不推定法院、债权人或投资人动作。",
            "正式公告清单未找到记录只说明该来源未披露，不代表其他公开渠道没有相关进展。",
            "历史上更常出现的后续类别不表示本案下一节点的概率。",
        ],
        provenance=[
            f"shared_data/v5/.../st_stocks_v5_backup.sqlite3::company_announcements[{symbol}]",
            "shared_data/v7/episode_index_v0/episode_index.jsonl",
            *( [f"local_data/v8_copilot/announcement_refresh/{symbol}.json"] if inventory.refresh_count else [] ),
        ],
    )


def card_stock_comparison(symbols: list[str], question: str) -> AnswerCard:
    """Compare public dimensions on one explicit, reproducible snapshot."""
    if len(symbols) != 2 or len(set(symbols)) != 2:
        raise ValueError("首版股票比较必须提供两只不同股票")
    episode_snapshot = load_episode_snapshot(EPISODE_INDEX, EPISODE_MANIFEST)
    rows: list[dict[str, Any]] = []
    inventories = [
        load_announcement_inventory(
            symbol=symbol,
            base_db=BASE_DB,
            refresh_dir=ANNOUNCEMENT_REFRESH_DIR,
        )
        for symbol in symbols
    ]
    announcement_dates = [inventory.announcement_as_of for inventory in inventories]
    common_announcement_cutoff = min(announcement_dates)
    provenance: list[str] = [
        "shared_data/v5/.../st_stocks_v5_backup.sqlite3::daily_prices",
        "shared_data/v7/episode_index_v0/episode_index.jsonl",
    ]
    actual_information_dates: list[str] = []
    per_stock_freshness: dict[str, str] = {}
    price_dates: list[str] = []
    for symbol, inventory in zip(symbols, inventories):
        latest = inventory.records[0] if inventory.records else None
        comparable_records = [
            item for item in inventory.records
            if item.announcement_date <= common_announcement_cutoff
        ]
        cutoff_date = _pd(common_announcement_cutoff)
        window_start = cutoff_date - timedelta(days=29) if cutoff_date else None
        recent_30d_count = sum(
            1 for item in comparable_records
            if window_start and _pd(item.announcement_date) and _pd(item.announcement_date) >= window_start
        )
        comparable_latest = comparable_records[0] if comparable_records else None
        related_entity_terms = ("孙公司", "子公司", "控股股东")
        listed_restructurings = [
            item for item in comparable_records
            if "重整" in item.title
            and not any(term in item.title for term in related_entity_terms)
        ]
        comparable_restructuring = (
            listed_restructurings[0] if listed_restructurings else None
        )
        latest_restructuring = next(
            (
                item for item in inventory.records
                if "重整" in item.title
                and not any(term in item.title for term in related_entity_terms)
            ),
            None,
        )
        latest_related_restructuring = next(
            (
                item for item in inventory.records
                if "重整" in item.title
                and any(term in item.title for term in related_entity_terms)
            ),
            None,
        )
        with _db() as connection:
            status = connection.execute(
                "select start_date,end_date,status_name from st_status_history "
                "where symbol=? order by start_date desc limit 1",
                (symbol,),
            ).fetchone()
            prices = connection.execute(
                "select trade_date,close from daily_prices where symbol=? and adjust='qfq' "
                "order by trade_date desc limit 61",
                (symbol,),
            ).fetchall()
        price_values = list(reversed(prices))
        latest_price = float(price_values[-1][1]) if price_values else None
        anchors = sorted(
            (
                (str(anchor.get("announcement_date") or anchor.get("anchor_date") or ""),
                 str(anchor.get("title") or ""), str(episode.get("episode_type") or ""))
                for episode in _iter_episodes(symbol)
                for anchor in episode.get("anchor_events", [])
                if anchor.get("announcement_date") or anchor.get("anchor_date")
            ),
            reverse=True,
        )
        row: dict[str, Any] = {
            "记录类型": "股票并列比较",
            "股票": symbol,
            "当前ST状态": status[2] if status else "当前快照无记录",
            "状态开始": str(status[0])[:10] if status else "当前快照无记录",
            "最近正式公告": (
                f"{comparable_latest.announcement_date}《{comparable_latest.title}》"
                if comparable_latest else "共同截止日前无记录"
            ),
            "各自最新公告": (
                f"{latest.announcement_date}《{latest.title}》" if latest else "当前快照无记录"
            ),
            "共同公告截止日": common_announcement_cutoff,
            "正式公告数量(共同截止前)": len(comparable_records),
            "近30日公告数量(共同截止)": recent_30d_count,
            "比较模式": "各自最新状态并列；公告数量按共同截止日计算",
            "最近上市公司本体重整里程碑": (
                f"{comparable_restructuring.announcement_date}《{comparable_restructuring.title}》；"
                f"阶段标签：{_restructuring_stage(comparable_restructuring.title)}"
                if comparable_restructuring else "共同截止日前未找到上市公司本体重整节点"
            ),
            "各自最新上市公司本体重整里程碑": (
                f"{latest_restructuring.announcement_date}《{latest_restructuring.title}》；"
                f"阶段标签：{_restructuring_stage(latest_restructuring.title)}"
                if latest_restructuring
                else "当前正式公告清单未找到上市公司本体重整节点"
            ),
            "各自最新关联主体重整事项": (
                f"关联主体（子公司/孙公司/控股股东）："
                f"{latest_related_restructuring.announcement_date}"
                f"《{latest_related_restructuring.title}》"
                if latest_related_restructuring
                else "当前正式公告清单未找到关联主体重整事项"
            ),
            "最近分类事件": (
                f"{anchors[0][0]}《{anchors[0][1]}》" if anchors else "当前快照无记录"
            ),
            "价格截至": str(price_values[-1][0])[:10] if price_values else "当前快照无记录",
            "最新收盘": round(latest_price, 2) if latest_price is not None else "当前快照无记录",
        }
        for window in (20, 60):
            if latest_price is not None and len(price_values) > window:
                row[f"近{window}日变化"] = (
                    f"{(latest_price / float(price_values[-window - 1][1]) - 1) * 100:.1f}%"
                )
        rows.append(_row(f"comparison_{symbol}", **row))
        if latest:
            actual_information_dates.append(latest.announcement_date)
        if status:
            actual_information_dates.append(str(status[0])[:10])
        if price_values:
            actual_price_date = str(price_values[-1][0])[:10]
            actual_information_dates.append(actual_price_date)
            price_dates.append(actual_price_date)
            per_stock_freshness[f"price_{symbol}_as_of"] = actual_price_date
        if anchors:
            actual_information_dates.append(anchors[0][0])
            per_stock_freshness[f"episode_{symbol}_latest_event"] = anchors[0][0]
        provenance.append(
            f"shared_data/v5/.../st_stocks_v5_backup.sqlite3::company_announcements[{symbol}]"
        )
        if inventory.refresh_count:
            provenance.append(f"local_data/v8_copilot/announcement_refresh/{symbol}.json")
    gap = LensGap(
        gap_id="stock_comparison_evidence",
        missing_for="两只股票跨维度优劣排序的验证证据",
        sediment_as="question_card:stock_comparison_evidence",
        note="本卡只做同口径并列，不输出优劣或行动排序。",
    )
    as_of = max(actual_information_dates)
    return AnswerCard(
        question=question,
        object_ref="cohort:comparison:" + ",".join(symbols),
        view="query",
        as_of=as_of,
        sample_scope=f"两只股票（{', '.join(symbols)}）的状态、公告、事件与前复权价格并列",
        evidence_grade="descriptive_query",
        lens_gap=[gap],
        episode_index_version=episode_snapshot.version,
        data_snapshot_as_of=as_of,
        source_freshness={
            **({"price_data_as_of": min(price_dates)} if price_dates else {}),
            "episode_index_as_of": episode_snapshot.as_of,
            **per_stock_freshness,
            **{f"company_announcements_{symbol}_as_of": date for symbol, date in zip(symbols, announcement_dates)},
        },
        body_rows=rows,
        analysis_claims=[
            AnalysisClaim(
                text="两只股票已按同一字段集合并列，差异只描述当前快照事实。",
                claim_type="fact",
                backing=BackingRef(kind="query_row", ref=rows[0]["row_id"]),
            ),
            AnalysisClaim(
                text="当前没有支持跨股票优劣排序的验证证据。",
                claim_type="caveat",
                backing=BackingRef(kind="lens_gap", ref=gap.gap_id),
            ),
        ],
        caveats=FIXED_CAVEATS + [
            "卡片 as_of 是本题纳入的最晚信息日期；公告密度和共同字段比较另用两股都覆盖的共同截止日。",
            "公告、事件、状态和价格快照可能有不同截止日，逐字段日期必须同时阅读。",
            "并列比较不构成优劣、方向或行动排序。",
        ],
        provenance=list(dict.fromkeys(provenance)),
    )


def card_st_status_timeline(symbol: str = "603398") -> AnswerCard:
    """Read ST intervals, matched trigger announcements, and recent episode nodes."""
    status_snapshot = load_table_snapshot(
        BASE_DB,
        table="st_status_history",
        date_column="fetched_at",
    )
    evidence_snapshot = load_table_snapshot(
        BASE_DB,
        table="st_status_history_evidence",
        date_column="generated_at",
    )
    episode_snapshot = load_episode_snapshot(EPISODE_INDEX, EPISODE_MANIFEST)
    with _db() as con:
        rows = con.execute(
            "select start_date,end_date,status_name,status_type,source,fetched_at "
            "from st_status_history where symbol=? order by start_date",
            (symbol,),
        ).fetchall()
        evidence_rows = con.execute(
            "select start_date,status_name,announcement_id,announcement_date,title,"
            "match_reason,confidence from st_status_history_evidence "
            "where symbol=? and evidence_status='matched' and evidence_rank=1 "
            "order by start_date",
            (symbol,),
        ).fetchall()

    status_body_rows = [
        _row(
            f"st_interval_{index:02d}",
            **{
                "记录类型": "状态区间",
                "开始日": start_date,
                "结束日": end_date or "仍在持续/未记录结束日",
                "状态": status_name,
                "状态类型": status_type,
                "来源": source,
            },
        )
        for index, (start_date, end_date, status_name, status_type, source, _) in enumerate(rows, 1)
    ]
    if not status_body_rows:
        status_body_rows = [_row("st_interval_missing", **{"状态": "当前快照无 ST 生命周期记录"})]

    trigger_rows = [
        _row(
            f"st_trigger_announcement_{index:02d}",
            **{
                "记录类型": "触发公告",
                "状态开始日": start_date,
                "状态": status_name,
                "巨潮公告ID": announcement_id,
                "日期": announcement_date,
                "标题": title,
                "匹配说明": match_reason,
                "匹配置信度": confidence,
            },
        )
        for index, (
            start_date,
            status_name,
            announcement_id,
            announcement_date,
            title,
            match_reason,
            confidence,
        ) in enumerate(evidence_rows, 1)
    ]

    anchors: list[tuple[str, str, str, str]] = []
    for episode in _iter_episodes(symbol):
        episode_type = str(episode.get("episode_type", "unclassified"))
        for anchor in episode.get("anchor_events", []):
            event_date = str(anchor.get("announcement_date") or anchor.get("anchor_date") or "")
            title = str(anchor.get("title") or "未命名节点")
            source_ids = [str(item) for item in anchor.get("source_material_ids", [])]
            announcement_id = next(
                (item.split(":", 1)[1] for item in source_ids if item.startswith("announcement:")),
                str(anchor.get("announcement_id") or ""),
            )
            if event_date:
                anchors.append((event_date, title, episode_type, announcement_id))
    recent_anchors = sorted(set(anchors), reverse=True)[:8]
    stock_episode_latest_event = recent_anchors[0][0] if recent_anchors else None
    episode_rows = [
        _row(
            f"recent_episode_node_{index:02d}",
            **{
                "记录类型": "近期分类节点",
                "日期": event_date,
                "标题": title,
                "事件段": episode_type,
                "巨潮公告ID": announcement_id,
            },
        )
        for index, (event_date, title, episode_type, announcement_id) in enumerate(recent_anchors, 1)
    ]
    body_rows = [*status_body_rows, *trigger_rows, *episode_rows]

    gap_id = "st_reason_announcement_binding"
    fetched_at = max((row[5] for row in rows), default=status_snapshot.as_of)
    data_as_of = limiting_as_of(
        str(fetched_at), evidence_snapshot.as_of, episode_snapshot.as_of
    )
    provenance_ref = "shared_data/v5/.../st_stocks_v5_backup.sqlite3::st_status_history"
    return AnswerCard(
        question=f"{symbol} 的 ST 状态关键节点是什么，为什么进入 ST？",
        object_ref=f"stock:{symbol}",
        view="query",
        as_of=data_as_of,
        sample_scope=(
            f"{symbol}：{len(rows)} 个 ST 状态区间，{len(evidence_rows)} 条一级匹配触发公告，"
            f"{len(recent_anchors)} 个近期已分类事件节点"
        ),
        evidence_grade="descriptive_query",
        lens_gap=[LensGap(
            gap_id=gap_id,
            missing_for="ST 原因公告与生命周期节点的验证绑定",
            sediment_as="question_card:QC-20260710-001",
            note="状态区间可直接读取；具体原因仍需公告/episode 绑定，不能由状态名称反推。",
        )],
        episode_index_version=episode_snapshot.version,
        body_rows=body_rows,
        analysis_claims=[
            AnalysisClaim(
                text=(
                    "ST 状态区间来自生命周期表；触发原因只展示已与状态开始日匹配的一级公告，"
                    "不从状态简称反推。"
                ),
                claim_type="caveat",
                backing=BackingRef(kind="lens_gap", ref=gap_id),
            ),
            *([AnalysisClaim(
                text=f"本地证据表为 {len(evidence_rows)} 个状态开始节点匹配到一级触发公告。",
                claim_type="fact",
                backing=BackingRef(kind="query_row", ref="st_trigger_announcement_01"),
            )] if evidence_rows else []),
            *([AnalysisClaim(
                text=f"M6 事件索引提供最近 {len(recent_anchors)} 个已分类公告节点供继续核查。",
                claim_type="fact",
                backing=BackingRef(kind="query_row", ref="recent_episode_node_01"),
            )] if recent_anchors else []),
        ],
        data_snapshot_as_of=data_as_of,
        source_freshness={
            "st_status_fetched_at": str(fetched_at),
            "st_evidence_generated_at": evidence_snapshot.as_of,
            "episode_index_as_of": episode_snapshot.as_of,
            **(
                {"stock_episode_latest_event": stock_episode_latest_event}
                if stock_episode_latest_event else {}
            ),
        },
        caveats=FIXED_CAVEATS + [
            "生命周期表描述状态区间，不自动解释触发原因；原因解释需回到公告原文。",
            "不同 source 的状态区间可能重叠；本卡保留原始 source 行，不擅自合并冲突。",
        ],
        provenance=[
            provenance_ref,
            "shared_data/v5/.../st_stocks_v5_backup.sqlite3::st_status_history_evidence",
            "shared_data/v7/episode_index_v0/episode_index.jsonl",
        ],
    )
