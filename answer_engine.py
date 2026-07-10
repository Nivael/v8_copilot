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
import sqlite3
import statistics
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from lens_binding import LensRegistry, LensInvocation, LensGap

_ROOT = Path(__file__).resolve().parent.parent
BASE_DB = _ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"
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
_EP_VERSION = "unknown"
_EP_ASOF = "unknown"
if EPISODE_MANIFEST.exists():
    _m = json.loads(EPISODE_MANIFEST.read_text(encoding="utf-8"))
    _EP_VERSION = _m.get("builder_version", "unknown")
    _EP_ASOF = _m.get("as_of", "unknown")
PRICE_ASOF = "2026-06-26"  # daily_prices 最新交易日


@dataclass
class DataDebtRow:
    gap: str
    affects: str
    debt_ref: str


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
    episode_index_version: str = _EP_VERSION
    data_snapshot_as_of: str = PRICE_ASOF
    source_freshness: dict[str, str] = field(default_factory=lambda: {
        "release_library_frozen_at": _REGISTRY.frozen_at,
        "episode_index_as_of": _EP_ASOF,
        "price_data_as_of": PRICE_ASOF,
    })
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

def card_next_node_gap(trigger_subtype: str = "restructuring_investor_recruitment") -> AnswerCard:
    """#01 重整招募→下一节点。lens：重整方法论框架贡献 caveat；无 evidence lens → lens_gap 沉淀。"""
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
                    note="现有 release library 无验证重整阶段 timing 的 evidence_lens；分布为 query 视图。")]
    body_rows = [
        row("next_any_announcement", "下一个任意公告", _stats(g_any)),
        row("next_classified_restructuring", "下一个已分类重整节点", _stats(g_classified)),
        row("next_stage_milestone", "下一个不同阶段里程碑", _stats(g_milestone)),
    ]
    return AnswerCard(
        question=f"{trigger_subtype} 之后，下一个公告节点平均多久？",
        object_ref=f"cohort:{trigger_subtype}（{len(recs)} 事件）",
        view="query", as_of="2026-06-26",
        sample_scope=f"M6 episode index canonical 语料，{len({s for s,_ in recs})} 只股票 / {len(recs)} 触发事件",
        evidence_grade="descriptive_query",
        lens_invocations=invs, lens_gap=gaps,
        body_rows=body_rows,
        analysis_claims=[
            AnalysisClaim(
                text="“下一个节点”定义不同会得到不同等待期，答案保留三种口径。",
                claim_type="caveat",
                backing=BackingRef(kind="lens_gap", ref="restructuring_timing_evidence"),
            )
        ],
        caveats=FIXED_CAVEATS + [
            "『平均多久』无单一答案：节点定义不同，中位数可差数倍——三口径并列，由提问者选。"],
        provenance=["shared_data/v7/episode_index_v0/episode_index.jsonl",
                    "shared_data/v5/.../st_stocks_v5_backup.sqlite3::company_announcements"])


def card_two_week_move() -> AnswerCard:
    """#02 两周异动。无 evidence lens 直接命中『两周横截面异动』→ lens_gap 沉淀 + 两条 data_debt。"""
    import numpy as np, pandas as pd
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
    debts = [DataDebtRow("大盘指数日线序列", "『相对大盘』无真基准，只能 ST-relative 代理", "D-051C"),
             DataDebtRow("as-of 市值/股本", "『微盘』cohort 无法定义（市值字段全空）", "C14")]
    # 尝试绑定：日历 regime evidence lens 存在，但它是月份口径，不解答两周横截面 → 记为 gap
    gaps = [LensGap(gap_id="two_week_cross_section_evidence",
                    missing_for="两周横截面异动分布的验证证据",
                    sediment_as="question_card:QC-20260710-013",
                    note="release library 仅有月份 calendar-regime(RL-A-001/002) 与 C17 短窗(RL-A-003)，"
                         "均不直接验证『两周横截面异动』；ST 分布为无 lens 背书的 descriptive query。")]
    return AnswerCard(
        question="ST/微盘相对大盘异动的两周分布如何？",
        object_ref="universe: ST panel (daily_prices qfq)",
        view="query", as_of="2026-06-26",
        sample_scope="902 只 ST 面板，2018-01-02~2026-06-26，1,006,352 股票-日观测",
        evidence_grade="descriptive_query",
        lens_invocations=[], lens_gap=gaps,
        body_rows=body, data_debt=debts, data_debt_refs=["D-051C", "C14"],
        analysis_claims=[
            AnalysisClaim(
                text="相对大盘层缺少大盘指数日线序列。",
                claim_type="data_gap",
                backing=BackingRef(kind="data_debt", ref="D-051C"),
            ),
            AnalysisClaim(
                text="微盘分层缺少 as-of 市值或可复算字段。",
                claim_type="data_gap",
                backing=BackingRef(kind="data_debt", ref="C14"),
            ),
        ],
        caveats=FIXED_CAVEATS + [
            "退市股价格可能右截断（生存偏差）；两周=10 交易日口径。",
            "半题可答：ST 分布可给，『相对大盘』『微盘』因缺数据不可答；且无 evidence lens 背书——见 lens_gap。"],
        provenance=["shared_data/v5/.../st_stocks_v5_backup.sqlite3::daily_prices"])


def card_consolidation_checklist(symbol: str = "603398", band: float = 0.25, window: int = 42) -> AnswerCard:
    """#03 沐邦平台整理。lens：C17 短窗波动收敛(evidence, C17 wording 边界) + 股东行为/控制权 methodology。"""
    import numpy as np, pandas as pd
    con = _db()
    p = pd.read_sql("select trade_date,close from daily_prices where symbol=? and adjust='qfq' order by trade_date",
                    con, params=(symbol,))
    con.close()
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
        _row("risk_warning_window", **{"该看的窗口": "退市风险警示节点串", "依据": "delisting_terminal_path"}),
        _row("restructuring_window", **{"该看的窗口": "预重整/重整进展节点", "依据": "restructuring_path"}),
        _row("volatility_window", **{"该看的窗口": "均线回踩/短窗波动收敛", "依据": "C17 lens（波动收敛，非上涨信号）"}),
        _row("controller_window", **{"该看的窗口": "控股股东司法处置节点", "依据": "control_or_investor 冻结/拍卖/过户"}),
        _row("abnormal_move_window", **{"该看的窗口": "交易异常波动公告", "依据": "平台被打破的即时标记"}),
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
        view="checklist", as_of="2026-06-26",
        sample_scope=f"{symbol} 单票：{n_nodes} 个已分类 episode 节点；节点族 top: " +
                     ", ".join(f"{k}×{v}" for k, v in top),
        evidence_grade="anecdotal_support",
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


def card_calendar_regime_evidence(release_id: str = "RL-A-001") -> AnswerCard:
    """直接消费 frozen evidence lens，展示 N、effect digest、反例和措辞边界。"""
    record = _REGISTRY.get(release_id)
    if record.get("release_role") != "evidence_lens":
        raise ValueError(f"{release_id} 不是 evidence_lens")

    sample_n = record["sample_n"]
    invocation = _REGISTRY.invoke(record, "历史日历窗口证据、反例与措辞边界")
    row_id = f"calendar_evidence_{release_id.lower().replace('-', '_')}"
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
        question=f"{release_id} 的月份/日历历史先验站得住吗？",
        object_ref=f"lens:{release_id}",
        view="evidence",
        as_of=record["as_of"],
        sample_scope=(
            f"{record['cohort_id']}；trigger N={sample_n['trigger']}；"
            f"control N={sample_n['control']}"
        ),
        evidence_grade=record["evidence_grade"],
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


def card_province_mapping_debt() -> AnswerCard:
    """省份分层不可答时的稳定 data-debt 出口。"""
    gap_id = "province_mapping_missing"
    debt_ref = "D-051A"
    return AnswerCard(
        question="重整路径按省份分层如何？",
        object_ref="cohort:restructuring_by_province",
        view="data_debt",
        as_of="2026-07-10",
        sample_scope="当前 base DB 无 symbol→省份/注册地映射，无法形成省份分层样本",
        evidence_grade="insufficient_data",
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


def card_st_status_timeline(symbol: str = "603398") -> AnswerCard:
    """读取 ST 生命周期区间；原因解释仍显式保留为 lens gap。"""
    con = _db()
    rows = con.execute(
        "select start_date,end_date,status_name,status_type,source,fetched_at "
        "from st_status_history where symbol=? order by start_date",
        (symbol,),
    ).fetchall()
    con.close()

    body_rows = [
        _row(
            f"st_interval_{index:02d}",
            **{
                "开始日": start_date,
                "结束日": end_date or "仍在持续/未记录结束日",
                "状态": status_name,
                "状态类型": status_type,
                "来源": source,
            },
        )
        for index, (start_date, end_date, status_name, status_type, source, _) in enumerate(rows, 1)
    ]
    if not body_rows:
        body_rows = [_row("st_interval_missing", **{"状态": "当前快照无 ST 生命周期记录"})]

    gap_id = "st_reason_announcement_binding"
    fetched_at = max((row[5] for row in rows), default=PRICE_ASOF)
    provenance_ref = "shared_data/v5/.../st_stocks_v5_backup.sqlite3::st_status_history"
    return AnswerCard(
        question=f"{symbol} 的 ST 状态关键节点是什么，为什么进入 ST？",
        object_ref=f"stock:{symbol}",
        view="query",
        as_of=str(fetched_at)[:10],
        sample_scope=f"{symbol} 的 st_status_history，{len(rows)} 个状态区间",
        evidence_grade="descriptive_query",
        lens_gap=[LensGap(
            gap_id=gap_id,
            missing_for="ST 原因公告与生命周期节点的验证绑定",
            sediment_as="question_card:QC-20260710-001",
            note="状态区间可直接读取；具体原因仍需公告/episode 绑定，不能由状态名称反推。",
        )],
        body_rows=body_rows,
        analysis_claims=[
            AnalysisClaim(
                text="状态区间来自 st_status_history；具体 ST 原因不能仅凭状态名称确定。",
                claim_type="caveat",
                backing=BackingRef(kind="lens_gap", ref=gap_id),
            )
        ],
        data_snapshot_as_of=str(fetched_at)[:10],
        source_freshness={
            "release_library_frozen_at": _REGISTRY.frozen_at,
            "episode_index_as_of": _EP_ASOF,
            "st_status_fetched_at": str(fetched_at),
        },
        caveats=FIXED_CAVEATS + [
            "生命周期表描述状态区间，不自动解释触发原因；原因解释需回到公告原文。",
            "不同 source 的状态区间可能重叠；本卡保留原始 source 行，不擅自合并冲突。",
        ],
        provenance=[provenance_ref],
    )
