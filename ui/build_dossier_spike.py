"""
v8 UI Spike #01 — 沐邦(603398) 个股证据面板 builder。

范围闸（统一 v8 PRD P1.5）：真实数据、只读、静态、一只票、一页。
不接 LLM、不做服务、不写库。产出单个自包含 HTML（内联 SVG 图 + 交互，无 CDN 依赖）。

验证三件事：
1. 股价图 + 公告节点能否成为研究入口；
2. episode anchor_events 是否够撑可导航时间线；
3. 面板与 AnswerCard 能否共享同一个 ResearchContext。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_DB = ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"
EPISODE_INDEX = ROOT / "shared_data/v7/episode_index_v0/episode_index.jsonl"
ANSWER_CARDS = Path(__file__).resolve().parents[1] / "out/answer_cards.json"
OUT = Path(__file__).resolve().parent / "dossier_603398.html"
SYMBOL = "603398"

# episode_type -> (lane label, color)
LANES = [
    ("重整/预重整", "#b45309", {"restructuring_path"}),
    ("ST/退市风险", "#dc2626", {"st_entry_or_escalation_path", "delisting_terminal_path", "risk_warning_removal_path"}),
    ("控制权/股东", "#7c3aed", {"control_or_investor_path"}),
    ("监管", "#475569", {"regulatory_pressure_path"}),
    ("财报/资金占用", "#0d9488", {"financial_reporting_path", "fund_occupation_resolution_path", "other_event_path"}),
]

EPISODE_LABELS = {
    "restructuring_path": "重整路径",
    "st_entry_or_escalation_path": "ST 风险进入或升级",
    "delisting_terminal_path": "终止上市风险",
    "risk_warning_removal_path": "风险警示撤销路径",
    "control_or_investor_path": "控制权或投资人变化",
    "regulatory_pressure_path": "监管压力",
    "financial_reporting_path": "财报与审计",
    "fund_occupation_resolution_path": "资金占用处置",
    "other_event_path": "其他事件",
}

SUBTYPE_LABELS = {
    "annual_report_release": "年报或定期报告披露",
    "annual_report_st_continues": "年报后风险警示延续",
    "annual_report_st_start_problem": "年报触发风险警示问题",
    "audit_opinion_issue_resolved": "审计意见相关问题消除",
    "audit_opinion_nonstandard": "非标审计意见或内控问题",
    "audit_progress": "年报编制或审计进展",
    "controlling_shareholder_pledge_or_execution": "控股股东质押、冻结或执行",
    "delisting_possible_termination": "可能终止上市风险提示",
    "earnings_forecast_or_preannouncement": "业绩预告或业绩预披露",
    "fund_occupation_rectification": "资金占用整改",
    "fund_occupation_repayment_or_clearing": "资金占用清偿",
    "fund_occupation_special_report": "资金占用专项报告",
    "investor_or_control_change": "投资人或控制权变化",
    "regulatory_discipline_or_measure": "监管措施或纪律处分",
    "regulatory_inquiry_delay": "监管问询延期回复",
    "regulatory_inquiry_letter": "监管问询函",
    "regulatory_inquiry_reply": "监管问询回复",
    "regulatory_investigation_opened": "监管立案或调查启动",
    "regulatory_letter": "监管工作函",
    "regulatory_penalty_decision": "行政处罚告知或决定",
    "restructuring_pre_restructuring_started": "预重整启动",
    "restructuring_progress_update": "重整或预重整进展",
    "risk_warning_removal_application": "申请撤销风险警示",
}

EVIDENCE_GRADE_LABELS = {
    "aggregate_weak": "汇总弱证据",
    "small_n_case_notes": "小样本案例证据",
    "anecdotal_support": "个案支持",
    "descriptive_query": "描述性查询",
}

COHORT_LABELS = {
    "C17:stock_price_behavior_episode": "股价行为事件样本",
    "C04:stock_event_episode": "股票事件段样本",
}

LENS_KIND_LABELS = {
    "evidence": "证据",
    "methodology": "方法论",
    "query": "查询",
    "checklist": "观察清单",
    "data_debt": "数据债",
    "case_note": "案例笔记",
}

RELEASE_ROLE_LABELS = {
    "evidence_lens": "证据 lens",
    "case_note_evidence": "案例证据",
    "methodology_frame": "方法论框架",
    "checklist_lens": "清单 lens",
    "query_template": "查询模板",
    "data_debt": "数据债",
}


def _label(mapping: dict[str, str], value: str | None, fallback: str = "未归类") -> str:
    if not value:
        return fallback if fallback != "未归类" else "无"
    return mapping.get(value, fallback)


def _announcement_label(value: str | None) -> str:
    if not value:
        return "无"
    if value.startswith("announcement:"):
        return f"巨潮公告 ID {value.split(':', 1)[1]}"
    return "来源编号已记录"


def _display_text(value: str | None) -> str:
    return (
        (value or "")
        .replace("守 C17 wording", "守历史股价行为样本的措辞边界")
        .replace("C17 wording", "历史股价行为样本措辞边界")
        .replace("wording", "措辞边界")
    )


def _display_nodes(nodes: list[dict]) -> list[dict]:
    return [
        {
            "date": n["date"],
            "lane": n["lane"],
            "title": n["title"],
            "episode_label": _label(EPISODE_LABELS, n.get("episode_type")),
            "subtype_label": _label(SUBTYPE_LABELS, n.get("subtype")),
            "announcement_label": _announcement_label(n.get("ann_id")),
        }
        for n in nodes
    ]


def _display_invocations(invocations: list[dict]) -> list[dict]:
    rows = []
    for inv in invocations:
        rows.append({
            "release_id": inv.get("release_id", ""),
            "lens_label": (
                f"{_label(LENS_KIND_LABELS, inv.get('lens_kind'))}/"
                f"{_label(RELEASE_ROLE_LABELS, inv.get('release_role'))}"
            ),
            "contributed_section": _display_text(inv.get("contributed_section")),
            "evidence_grade": _label(EVIDENCE_GRADE_LABELS, inv.get("evidence_grade"), ""),
            "cohort": _label(COHORT_LABELS, inv.get("cohort_id"), ""),
        })
    return rows


def lane_of(et: str) -> int:
    for i, (_, _, s) in enumerate(LANES):
        if et in s:
            return i
    return len(LANES) - 1


def _pd(s: str) -> date | None:
    try:
        y, m, d = s[:10].split("-"); return date(int(y), int(m), int(d))
    except Exception:
        return None


def load_data():
    con = sqlite3.connect(f"file:{BASE_DB}?mode=ro", uri=True)
    prices = con.execute(
        "select trade_date,close from daily_prices where symbol=? and adjust='qfq' order by trade_date",
        (SYMBOL,)).fetchall()
    stt = con.execute(
        "select start_date,end_date,status_name,status_type "
        "from st_status_history where symbol=? order by start_date",
        (SYMBOL,)).fetchall()
    con.close()
    # nodes from episode index (dedup by date+title)
    seen = set(); nodes = []
    with open(EPISODE_INDEX) as f:
        for line in f:
            if SYMBOL not in line:
                continue
            d = json.loads(line)
            if d.get("symbol") != SYMBOL:
                continue
            et = d.get("episode_type", "?")
            for ev in d.get("anchor_events", []):
                ad = ev.get("announcement_date")
                if not ad:
                    continue
                title = (ev.get("title") or "").strip()
                key = (ad, title[:20])
                if key in seen:
                    continue
                seen.add(key)
                nodes.append({
                    "date": ad, "episode_type": et, "lane": lane_of(et),
                    "subtype": (ev.get("event_subtypes") or [""])[0],
                    "title": title,
                    "ann_id": (ev.get("source_material_ids") or [""])[0],
                })
    nodes.sort(key=lambda n: n["date"])
    # #03 answer card (lens invocations + platform segment)
    card = {}
    if ANSWER_CARDS.exists():
        card = json.load(open(ANSWER_CARDS)).get("slice03_consolidation_checklist", {})
    return prices, stt, nodes, card


def build_svg(prices, nodes):
    # geometry
    W, H = 1080, 300
    padL, padR, padT, padB = 46, 12, 12, 22
    xs = [_pd(t) for t, _ in prices]
    d0, d1 = xs[0], xs[-1]
    span = (d1 - d0).days or 1
    ys = [c for _, c in prices]
    ymin, ymax = min(ys), max(ys)
    yr = (ymax - ymin) or 1
    def X(dt): return padL + (dt - d0).days / span * (W - padL - padR)
    def Y(v): return padT + (1 - (v - ymin) / yr) * (H - padT - padB)
    # price path
    pts = " ".join(f"{X(_pd(t)):.1f},{Y(c):.1f}" for t, c in prices)
    # y gridlines
    grid = []
    for k in range(5):
        v = ymin + yr * k / 4
        y = Y(v)
        grid.append(f'<line x1="{padL}" y1="{y:.1f}" x2="{W-padR}" y2="{y:.1f}" class="grid"/>'
                    f'<text x="{padL-6}" y="{y+3:.1f}" class="ytick">{v:.1f}</text>')
    # year ticks
    yearticks = []
    for yr_ in range(d0.year, d1.year + 1):
        dt = date(yr_, 1, 1)
        if dt < d0:
            continue
        x = X(dt)
        yearticks.append(f'<line x1="{x:.1f}" y1="{padT}" x2="{x:.1f}" y2="{H-padB}" class="grid"/>'
                         f'<text x="{x:.1f}" y="{H-6}" class="xtick">{yr_}</text>')
    # price lookup for node y
    pmap = {t: c for t, c in prices}
    def price_at(ad):
        if ad in pmap:
            return pmap[ad]
        tgt = _pd(ad); best = None
        for t, c in prices:
            if abs((_pd(t) - tgt).days) <= 7:
                best = c
        return best if best is not None else (ymin + ymax) / 2
    # node markers
    marks = []
    for i, n in enumerate(nodes):
        dt = _pd(n["date"])
        if not dt or dt < d0 or dt > d1:
            continue
        x = X(dt); y = Y(price_at(n["date"]))
        color = LANES[n["lane"]][1]
        label = (n["title"] or _label(EPISODE_LABELS, n.get("episode_type")) or "公告节点").replace('"', "&quot;")
        marks.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.4" fill="{color}" class="node" '
                     f'data-i="{i}" opacity="0.78" tabindex="0" role="button" '
                     f'aria-label="{n["date"]} {label}"/>')
    return f'''<svg viewBox="0 0 {W} {H}" class="chart" xmlns="http://www.w3.org/2000/svg">
      {''.join(grid)}
      {''.join(yearticks)}
      <polyline points="{pts}" class="pline"/>
      {''.join(marks)}
    </svg>''', (W, padL, padR, d0, span)


def build_lanes_svg(nodes, geom):
    W, padL, padR, d0, span = geom
    laneH = 26; H = laneH * len(LANES) + 24
    def X(dt): return padL + (dt - d0).days / span * (W - padL - padR)
    rows = []
    for li, (label, color, _) in enumerate(LANES):
        y = 14 + li * laneH
        rows.append(f'<text x="4" y="{y+4}" class="lanelbl" fill="{color}">{label}</text>')
        rows.append(f'<line x1="{padL}" y1="{y}" x2="{W-padR}" y2="{y}" class="lane"/>')
        for i, n in enumerate(nodes):
            if n["lane"] != li:
                continue
            dt = _pd(n["date"])
            if not dt:
                continue
            x = X(dt)
            label = (n["title"] or _label(EPISODE_LABELS, n.get("episode_type")) or "公告节点").replace('"', "&quot;")
            rows.append(f'<circle cx="{x:.1f}" cy="{y}" r="3.4" fill="{color}" class="node" '
                        f'data-i="{i}" opacity="0.72" tabindex="0" role="button" '
                        f'aria-label="{n["date"]} {label}"/>')
    return f'<svg viewBox="0 0 {W} {H}" class="lanes" xmlns="http://www.w3.org/2000/svg">{"".join(rows)}</svg>'


def main():
    prices, stt, nodes, card = load_data()
    chart_svg, geom = build_svg(prices, nodes)
    lanes_svg = build_lanes_svg(nodes, geom)
    invocations = card.get("lens_invocations", [])
    latest_platform = card.get("object_ref", "")
    platform_label = latest_platform.replace("stock:", "股票 ") if latest_platform else ""
    st_last = stt[-1] if stt else None
    st_badge = (st_last[2] or st_last[1] or "*ST") if st_last else "ST"
    nodes_json = json.dumps(_display_nodes(nodes), ensure_ascii=False)
    inv_json = json.dumps(_display_invocations(invocations), ensure_ascii=False)

    html = f'''<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>个股证据面板 {SYMBOL}</title>
<link rel="icon" href="data:,">
<style>
:root{{--fg:#0a0a0a;--mut:#6b7280;--bd:#e5e7eb;--sep:#f3f4f6;--acc:#0070f3;}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:ui-sans-serif,-apple-system,"Geist","Inter","PingFang SC",sans-serif;color:var(--fg);background:#fff;font-size:13px;line-height:1.5}}
.mono{{font-family:ui-monospace,"Geist Mono",Menlo,monospace}}
header{{display:flex;align-items:baseline;gap:12px;padding:14px 20px;border-bottom:1px solid var(--bd);flex-wrap:wrap}}
header .name{{font-size:18px;font-weight:600}}
header .code{{color:var(--mut)}}
.badge{{font-size:11px;padding:2px 7px;border-radius:5px;border:1px solid var(--bd);color:var(--mut)}}
.badge.st{{color:#dc2626;border-color:#fecaca;background:#fef2f2}}
.badge.acc{{color:var(--acc);border-color:#bfdbfe;background:#eff6ff}}
.spacer{{flex:1}}
.wrap{{display:grid;grid-template-columns:1fr 320px;gap:0}}
.main{{padding:16px 20px;border-right:1px solid var(--bd);min-width:0}}
.rail{{padding:16px;background:#fcfcfd;min-height:calc(100vh - 56px)}}
h2{{font-size:11px;letter-spacing:.04em;color:var(--mut);margin:0 0 8px;font-weight:600}}
.card{{border:1px solid var(--bd);border-radius:6px;padding:12px;margin-bottom:12px;background:#fff}}
.chartwrap{{overflow-x:auto;overscroll-behavior-x:contain;border:1px solid var(--bd);border-radius:6px;background:#fff}}
.chart,.lanes{{width:100%;height:auto;display:block}}
.pline{{fill:none;stroke:var(--fg);stroke-width:1.1}}
.grid{{stroke:var(--sep);stroke-width:1}}
.lane{{stroke:var(--bd);stroke-width:1}}
.ytick,.xtick{{fill:var(--mut);font-size:9px;font-family:ui-monospace,monospace}}
.ytick{{text-anchor:end}} .xtick{{text-anchor:middle}}
.lanelbl{{font-size:10px;font-weight:600}}
.node{{cursor:pointer;transition:opacity .12s,stroke-width .12s}} .node:hover{{opacity:1}}
.node:focus{{outline:none;stroke:var(--acc);stroke-width:2}}
.node.sel{{stroke:var(--acc);stroke-width:2}}
.legend{{display:flex;gap:14px;flex-wrap:wrap;margin:8px 0 2px;font-size:11px;color:var(--mut)}}
.legend i{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px;vertical-align:middle}}
.det .dt{{font-weight:600}} .det .ttl{{margin:6px 0}}
.kv{{display:flex;gap:8px;margin:3px 0;align-items:flex-start}} .kv .k{{color:var(--mut);min-width:62px;flex:0 0 62px}}
.kv span:last-child{{min-width:0;overflow-wrap:anywhere;word-break:break-word}}
.btn{{display:inline-block;margin-top:8px;padding:6px 10px;border:1px solid var(--acc);color:var(--acc);border-radius:6px;background:#eff6ff;cursor:pointer;font-size:12px;white-space:nowrap}}
.inv{{border:1px solid var(--bd);border-left:3px solid var(--acc);border-radius:5px;padding:8px;margin:6px 0;background:#fff}}
.inv .id{{font-weight:600}} .inv .k{{color:var(--mut);font-size:11px}}
.gap{{border-left:3px solid #d97706;background:#fffbeb}}
.ctx{{background:#0a0a0a;color:#e5e7eb;border-radius:6px;padding:10px;font-size:11px;white-space:pre-wrap;overflow-wrap:anywhere}}
.foot{{color:var(--mut);font-size:11px;padding:10px 20px;border-top:1px solid var(--bd)}}
@media (max-width: 760px){{
  header{{padding:12px 14px;gap:8px}}
  header .name{{font-size:17px}}
  .spacer{{display:none}}
  .wrap{{display:block}}
  .main{{padding:14px 12px;border-right:0}}
  .rail{{padding:14px 12px;border-top:1px solid var(--bd);min-height:0;background:#fff}}
  .chartwrap .chart,.chartwrap .lanes{{width:760px;max-width:none}}
  h2{{font-size:10px;letter-spacing:.04em}}
  .legend{{gap:8px 12px}}
  .card{{padding:10px}}
  .foot{{padding:10px 12px}}
}}
</style></head>
<body>
<header>
  <span class="name">*ST沐邦</span><span class="code mono">{SYMBOL} · SH</span>
  <span class="badge st">{st_badge}</span>
  <span class="badge">生命周期起 {stt[0][0] if stt else '无'}</span>
  <span class="spacer"></span>
  <span class="badge">价格截至 2026-06-26</span>
  <span class="badge acc">证据库 v7.4 v1</span>
</header>
<div class="wrap">
  <div class="main">
    <h2>股价 · qfq（公告节点可点击）</h2>
    <div class="chartwrap">{chart_svg}</div>
    <div class="legend">
      {''.join(f'<span><i style="background:{c}"></i>{l}</span>' for l,c,_ in LANES)}
    </div>
    <h2 style="margin-top:18px">事件时间线 · {len(nodes)} 个已分类节点</h2>
    <div class="chartwrap">{lanes_svg}</div>
    <div class="card" style="margin-top:14px">
      <h2>#03 答案卡（观察清单）· 该看哪些窗口</h2>
      <div class="mono" style="color:var(--mut);font-size:11px">{platform_label}</div>
      <div style="margin-top:6px">退市风险警示串 · 预重整/重整进展 · 均线回踩短窗波动收敛（历史股价行为样本，非上涨信号） · 控股股东司法处置 · 交易异常波动</div>
    </div>
  </div>
  <div class="rail">
    <h2>证据检查器</h2>
    <div class="card det" id="det">
      <div style="color:var(--mut)">点击图上任意节点查看详情</div>
    </div>
    <h2>调用的 Lens（#03 脊梁）</h2>
    <div id="invs"></div>
    <h2>研究上下文（联动对象）</h2>
    <div class="ctx mono" id="ctx"></div>
  </div>
</div>
<div class="foot mono">v8 个股证据面板 #01 · 只读静态 · 真实数据（日线 qfq + M6 事件节点 + v7.4 release library v1）· 不接 LLM/服务 · 非投顾，历史路径描述不表预测</div>
<script>
const NODES = {nodes_json};
const INVS = {inv_json};
const invBox = document.getElementById('invs');
INVS.forEach(v => {{
  const d = document.createElement('div'); d.className='inv';
  d.innerHTML = `<div class="id">${{v.release_id}} · ${{v.lens_label}}</div>`+
    `<div class="k">贡献：${{v.contributed_section}}</div>`+
    (v.evidence_grade?`<div class="k">证据等级：${{v.evidence_grade}}</div>`:'')+
    (v.cohort?`<div class="k">样本组：${{v.cohort}}</div>`:'');
  invBox.appendChild(d);
}});
if(!INVS.length){{invBox.innerHTML='<div class="inv gap">无 lens 命中，记录 lens_gap（诚实缺口）</div>';}}

function ctx(sel){{
  const lines = [
    "股票：{SYMBOL}",
    "区间：2018-01-02 至 2026-06-26",
    `选中节点：${{sel ? sel.date + " " + (sel.title || "").slice(0, 26) : "未选择"}}`,
    `调用 lens：${{INVS.map(v=>v.release_id).join(", ") || "无"}}`,
    `当前问题：${{sel ? "围绕此节点提问？" : "未选择节点"}}`
  ];
  document.getElementById('ctx').textContent = lines.join("\\n");
}}
ctx(null);

let selEl=null;
function select(i, el){{
  const n=NODES[i];
  document.querySelectorAll('.node.sel').forEach(e=>e.classList.remove('sel'));
  document.querySelectorAll('.node[data-i="'+i+'"]').forEach(e=>e.classList.add('sel'));
  const det=document.getElementById('det');
  det.innerHTML = `<div class="dt mono">${{n.date}}</div>`+
    `<div class="ttl">${{n.title||'(无标题)'}}</div>`+
    `<div class="kv"><span class="k">事件段</span><span>${{n.episode_label}}</span></div>`+
    `<div class="kv"><span class="k">子类型</span><span>${{n.subtype_label||'无'}}</span></div>`+
    `<div class="kv"><span class="k">出处</span><span>${{n.announcement_label||'无'}}</span></div>`+
    `<div class="btn" role="button" tabindex="0">围绕此节点提问</div>`;
  ctx(n);
  if(window.matchMedia('(max-width: 760px)').matches){{
    document.querySelector('.rail').scrollIntoView({{block:'start', behavior:'smooth'}});
  }}
}}
document.querySelectorAll('.node').forEach(el=>{{
  el.addEventListener('click',()=>select(+el.dataset.i, el));
  el.addEventListener('keydown',(e)=>{{
    if(e.key === 'Enter' || e.key === ' '){{e.preventDefault(); select(+el.dataset.i, el);}}
  }});
}});
</script>
</body></html>'''
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT}  ({len(html)//1024} KB) · nodes={len(nodes)} · prices={len(prices)} · invocations={len(invocations)}")


if __name__ == "__main__":
    main()
