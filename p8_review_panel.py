"""Build a self-contained, optional-action P8 owner review panel."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sqlite3
from pathlib import Path
from typing import Any


REVIEW_VERSION = "p8_human_review_panel_v1"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _names(base_database: Path) -> dict[str, str]:
    with sqlite3.connect(f"file:{base_database}?mode=ro", uri=True) as connection:
        result = {
            str(row[0]): str(row[1])
            for row in connection.execute("select symbol,name from stocks_meta")
        }
        for row in connection.execute(
            "select h.symbol,h.status_name from st_status_history h "
            "where h.start_date=(select max(x.start_date) from st_status_history x where x.symbol=h.symbol)"
        ):
            result.setdefault(str(row[0]), str(row[1]))
        return result


def _recommendation(item: dict[str, Any]) -> tuple[str, str, str]:
    checks = {str(check["check_id"]): check for check in item.get("checks") or []}
    official = checks.get("official_evidence", {})
    if official.get("status") != "ready":
        return "unknown", "暂不判断", "公告正文或独立核证仍有缺口，先保留候选，不替你下结论。"
    if len(item.get("matched_lanes") or []) >= 2:
        return "keep", "建议继续深挖", "至少两个独立研究通道重合，且已有可回链的官方事实。"
    return "unknown", "暂不判断", "只有一个研究通道，保留观察比强行取舍更诚实。"


def build_queue(
    *, funnel: dict[str, Any], backtest: dict[str, Any], dry_plan: dict[str, Any],
    names: dict[str, str],
) -> dict[str, Any]:
    source_ids = sorted(set(
        list(funnel.get("source_run_ids") or [])
        + list(backtest.get("source_run_ids") or [])
        + [str(dry_plan.get("plan_id") or "")]
    ))
    identity = {
        "version": REVIEW_VERSION, "as_of": funnel.get("as_of"),
        "source_ids": source_ids,
        "item_ids": [item.get("item_id") for item in funnel.get("items") or []],
    }
    session = "P8REV-" + hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:16].upper()
    cards = []
    for item in funnel.get("items") or []:
        symbol = str(item["symbol"])
        recommendation, recommendation_label, recommendation_reason = _recommendation(item)
        gaps = list(item.get("data_gaps") or [])
        why = "；".join(item.get("reasons") or [])
        if gaps:
            why += " 当前缺口：" + "、".join(gaps) + "。"
        cards.append({
            "card_id": str(item["item_id"]),
            "title": f"{names.get(symbol, '')} {symbol}".strip(),
            "affected_area": "p8_daily_research_funnel",
            "target_field": "owner_review_status",
            "scope": f"symbol:{symbol}|as_of:{item['as_of']}",
            "decision_requested": "这只股票今天是否值得继续深挖？",
            "why_surfaced": why,
            "recommendation": recommendation,
            "recommendation_label": recommendation_label,
            "recommendation_reason": recommendation_reason,
            "impact": "只改变你的研究队列，不改事实库、不改阈值，也不会触发交易动作。",
            "options": [
                {"value": "keep", "label": "继续深挖", "description": "放进 owner 研究清单。"},
                {"value": "drop", "label": "本轮略过", "description": "仅跳过今天这轮，不形成长期排除。"},
                {"value": "unknown", "label": "暂不判断", "description": "证据不足，维持观察。"},
            ],
            "source_lens_ids": list(item.get("matched_lanes") or []),
            "supporting_atom_ids": list(item.get("source_ids") or []),
            "evidence_examples": [
                {"label": str(check.get("check_id")), "status": str(check.get("status")), "detail": str(check.get("detail"))}
                for check in item.get("checks") or []
            ],
            "counterexamples": [
                {"label": "风险/缺口", "detail": value}
                for value in list(item.get("risk_flags") or []) + gaps
            ][:5],
            "affected_count": 1,
            "prior_decisions": [],
            "primary_lane": item.get("primary_lane"),
            "matched_lanes": item.get("matched_lanes") or [],
            "lane_rank": item.get("lane_rank"),
            "human_action_required": False,
        })
    return {
        "review_session_id": session,
        "review_version": REVIEW_VERSION,
        "title": f"P8 研究漏斗 · {funnel.get('as_of', '')}",
        "source_packet": {
            "dry_plan_id": dry_plan.get("plan_id"),
            "funnel_run_id": funnel.get("run_id"),
            "backtest_run_id": backtest.get("run_id"),
            "source_run_ids": source_ids,
        },
        "human_actions_required": 0,
        "cards": cards,
    }


def _metric(value: Any, *, pct: bool = False) -> str:
    if value is None:
        return "—"
    if pct:
        return f"{float(value) * 100:.1f}%"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def render_html(
    *, queue: dict[str, Any], funnel: dict[str, Any], backtest: dict[str, Any],
    dry_plan: dict[str, Any], chip: dict[str, Any],
) -> str:
    cards_html = []
    for card in queue["cards"]:
        options = "".join(
            f'<button class="decision" type="button" data-card="{html.escape(card["card_id"])}" data-value="{html.escape(option["value"])}">{html.escape(option["label"])}</button>'
            for option in card["options"]
        )
        evidence = "".join(
            f'<li><span class="status {html.escape(item["status"])}">{html.escape(item["status"])}</span><strong>{html.escape(item["label"])}</strong><br>{html.escape(item["detail"])}</li>'
            for item in card["evidence_examples"]
        )
        provenance = "、".join(html.escape(value) for value in card["supporting_atom_ids"]) or "无"
        lanes = " / ".join(html.escape(value) for value in card["matched_lanes"])
        cards_html.append(f"""
        <article class="review-card" id="{html.escape(card['card_id'])}">
          <div class="card-kicker"><span>{lanes}</span><span>#{card['lane_rank']}</span></div>
          <h3>{html.escape(card['title'])}</h3>
          <p class="question">{html.escape(card['decision_requested'])}</p>
          <div class="recommendation"><b>机器建议：{html.escape(card['recommendation_label'])}</b><span>{html.escape(card['recommendation_reason'])}</span></div>
          <p>{html.escape(card['why_surfaced'])}</p>
          <p class="impact">影响：{html.escape(card['impact'])}</p>
          <div class="actions">{options}</div>
          <label class="note-label">可选备注<textarea data-note="{html.escape(card['card_id'])}" placeholder="不填也可以"></textarea></label>
          <details><summary>证据、缺口与来源</summary><ul class="evidence">{evidence}</ul><p class="provenance">来源指针：{provenance}</p></details>
        </article>""")

    overall = backtest.get("activity_scorecard", {}).get("overall", {})
    shape_rows = []
    for label, values in overall.items():
        horizon = values.get("by_horizon", {}).get("20", {})
        shape_rows.append(
            f"<tr><td>{html.escape(label)}</td><td>{values.get('episode_count', 0)}</td>"
            f"<td>{horizon.get('completed_return_n', 0)}</td>"
            f"<td>{_metric(horizon.get('median_excess_return_st'), pct=True)}</td>"
            f"<td>{html.escape(horizon.get('status', ''))}</td></tr>"
        )
    anchor_rows = []
    for label, value in backtest.get("replay_anchors", {}).items():
        anchor_rows.append(
            f"<tr><td>{html.escape(label)}</td><td>{html.escape(str(value.get('anchor_date','')))}</td>"
            f"<td>{value.get('activity_candidate_count',0)}</td><td>{html.escape('、'.join(value.get('symbols') or [])) or '—'}</td></tr>"
        )
    control = backtest.get("activity_scorecard", {}).get("same_universe_quiet_control", {})
    source_packet = json.dumps(queue["source_packet"], ensure_ascii=False, indent=2)
    queue_json = json.dumps(queue, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(queue['title'])}</title>
<style>
:root{{--ink:#171916;--muted:#676c65;--line:#d7d9d2;--paper:#f7f6f1;--card:#fff;--accent:#214c3b;--warn:#8b5a1d;--bad:#8d3f37;--good:#2d654b}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}
.top{{position:sticky;top:0;z-index:10;background:rgba(247,246,241,.96);border-bottom:1px solid var(--line);backdrop-filter:blur(10px)}}
.top-inner{{max-width:1240px;margin:auto;padding:14px 22px;display:flex;gap:18px;align-items:center}} h1{{font-size:20px;margin:0;letter-spacing:-.02em}} .top-meta{{color:var(--muted);flex:1}} button{{border:1px solid var(--line);background:#fff;color:var(--ink);padding:8px 12px;border-radius:6px;cursor:pointer}} button:hover{{border-color:var(--accent)}}
main{{max-width:1240px;margin:0 auto;padding:28px 22px 70px}} .intro{{display:grid;grid-template-columns:1.5fr 1fr;gap:24px;margin-bottom:24px}} .intro h2{{font-size:34px;line-height:1.15;margin:0 0 12px;letter-spacing:-.04em}} .intro p{{color:var(--muted);max-width:720px}}
.metrics{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:20px 0 28px}} .metric{{border-top:3px solid var(--ink);padding:12px 2px}} .metric b{{font-size:24px;display:block}} .metric span{{font-size:12px;color:var(--muted)}}
.section{{border-top:1px solid var(--line);padding-top:24px;margin-top:32px}} .section h2{{font-size:22px;margin:0 0 6px}} .section-lead{{color:var(--muted);margin:0 0 18px}}
.grid{{display:grid;grid-template-columns:minmax(0,2fr) minmax(260px,1fr);gap:22px;align-items:start}} .cards{{display:grid;gap:14px}} .review-card{{background:var(--card);border:1px solid var(--line);padding:18px;border-radius:7px}} .card-kicker{{display:flex;justify-content:space-between;color:var(--muted);font-size:12px;text-transform:uppercase}} .review-card h3{{font-size:20px;margin:7px 0 2px}} .question{{font-size:17px;font-weight:650;margin:0 0 12px}} .recommendation{{border-left:3px solid var(--accent);background:#f2f6f2;padding:10px 12px;display:grid;gap:2px}} .impact,.provenance{{color:var(--muted);font-size:13px}} .actions{{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0 10px}} .decision.active{{background:var(--accent);border-color:var(--accent);color:#fff}} .note-label{{font-size:12px;color:var(--muted);display:grid;gap:4px}} textarea{{width:100%;min-height:54px;border:1px solid var(--line);border-radius:5px;padding:8px;font:inherit;resize:vertical}} details{{margin-top:12px}} summary{{cursor:pointer;color:var(--accent)}} .evidence{{padding-left:18px}} .evidence li{{margin:8px 0}} .status{{font-size:11px;border:1px solid var(--line);padding:1px 5px;margin-right:6px;border-radius:9px}} .status.ready{{color:var(--good)}} .status.gap,.status.unavailable{{color:var(--warn)}}
.side{{position:sticky;top:82px;background:#efeee8;border:1px solid var(--line);padding:16px;border-radius:7px}} .side h3{{margin:0 0 8px}} pre{{white-space:pre-wrap;word-break:break-word;max-height:300px;overflow:auto;background:#1d211e;color:#dce4dc;padding:12px;border-radius:5px;font-size:11px}} table{{width:100%;border-collapse:collapse;background:#fff}} th,td{{padding:10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}} th{{font-size:12px;color:var(--muted)}} .boundary{{border-left:3px solid var(--warn);padding:12px;background:#fff8ee}}
@media(max-width:850px){{.intro,.grid{{grid-template-columns:1fr}}.metrics{{grid-template-columns:repeat(2,1fr)}}.side{{position:static}}.top-inner{{flex-wrap:wrap}}.intro h2{{font-size:28px}}}}
</style></head>
<body><header class="top"><div class="top-inner"><h1>{html.escape(queue['title'])}</h1><span class="top-meta"><b id="decided">0</b> 已选择 · <b id="unresolved">{len(queue['cards'])}</b> 未选择 · 必审 0</span><span id="save-state">已载入</span><button id="copy">复制 JSON</button><button id="export">导出 JSON</button></div></header>
<main><section class="intro"><div><h2>先看研究价值，再决定要不要深挖</h2><p>这是研究优先级面板，不是买入榜。今天没有任何强制人审；不点击就保持 unreviewed，不会被系统当作 drop。</p></div><div class="boundary"><b>当前最重要的边界</b><br>正文 LLM 尚未获得外部发送授权，旧股东精确权益账仍为 0。两项都不会被数字外观掩盖。</div></section>
<section class="metrics"><div class="metric"><b>{funnel.get('item_count',0)}</b><span>今日候选</span></div><div class="metric"><b>{dry_plan.get('activity_feature_capacity',{}).get('calculable_count',0)}</b><span>可计算活动观察</span></div><div class="metric"><b>{backtest.get('extraction_scorecard',{}).get('body_verified_event_count',0)}</b><span>正文核证事件</span></div><div class="metric"><b>{backtest.get('scenario_reference_scorecard',{}).get('exact_old_equity_count',0)}</b><span>精确旧权益参照</span></div><div class="metric"><b>{chip.get('holder_observed_count',0)}/{chip.get('member_count',0)}</b><span>股东户数覆盖</span></div></section>
<section class="section"><h2>三次历史快照</h2><p class="section-lead">一周、一个月、一年前同样按当时可见数据回放；未走满窗口的继续右删失。</p><table><thead><tr><th>锚点</th><th>日期</th><th>候选数</th><th>股票</th></tr></thead><tbody>{''.join(anchor_rows)}</tbody></table></section>
<section class="section"><h2>量价成绩单</h2><p class="section-lead">20 日 ST 超额收益只作描述；同日同板块 quiet 对照的均值差为 {_metric(control.get('mean_difference'),pct=True)}，公司聚类区间 {_metric((control.get('company_cluster_bootstrap_95') or [None])[0],pct=True)} 至 {_metric((control.get('company_cluster_bootstrap_95') or [None,None])[1],pct=True)}。</p><table><thead><tr><th>冻结形态</th><th>episode</th><th>完成 20 日</th><th>中位 ST 超额</th><th>状态</th></tr></thead><tbody>{''.join(shape_rows)}</tbody></table></section>
<section class="section"><h2>今日研究漏斗</h2><p class="section-lead">系统已经给出机器建议。只有你主动选择才写入导出文件；所有动作只影响研究队列。</p><div class="grid"><div class="cards">{''.join(cards_html) or '<p>今天没有候选。</p>'}</div><aside class="side"><h3>导出预览</h3><p>自动保存在本机浏览器；JSON 不含交易指令。</p><pre id="preview"></pre><details><summary>运行来源</summary><pre>{html.escape(source_packet)}</pre></details></aside></div></section></main>
<script id="queue" type="application/json">{queue_json}</script>
<script>
const queue=JSON.parse(document.getElementById('queue').textContent); const key='p8-review:'+queue.review_session_id;
let state=JSON.parse(localStorage.getItem(key)||'{{"decisions":{{}}}}');
function exportPayload(){{const decisions=Object.entries(state.decisions).map(([card_id,value])=>{{const card=queue.cards.find(x=>x.card_id===card_id);return{{card_id,decision:value.decision,note:value.note||'',target_field:card.target_field,affected_area:card.affected_area,scope:card.scope,recommended_decision:card.recommendation,question:card.decision_requested}}}});return{{review_session_id:queue.review_session_id,review_version:queue.review_version,exported_at:new Date().toISOString(),source_packet:queue.source_packet,decisions,unreviewed_card_ids:queue.cards.filter(c=>!state.decisions[c.card_id]).map(c=>c.card_id)}}}}
function render(){{document.querySelectorAll('.decision').forEach(b=>b.classList.toggle('active',state.decisions[b.dataset.card]?.decision===b.dataset.value));document.querySelectorAll('textarea[data-note]').forEach(t=>{{t.value=state.decisions[t.dataset.note]?.note||''}});const n=Object.keys(state.decisions).length;document.getElementById('decided').textContent=n;document.getElementById('unresolved').textContent=queue.cards.length-n;document.getElementById('preview').textContent=JSON.stringify(exportPayload(),null,2)}}
function save(){{localStorage.setItem(key,JSON.stringify(state));document.getElementById('save-state').textContent='已自动保存';render()}}
document.querySelectorAll('.decision').forEach(b=>b.addEventListener('click',()=>{{const prior=state.decisions[b.dataset.card]||{{note:''}};state.decisions[b.dataset.card]={{decision:b.dataset.value,note:prior.note||''}};save()}}));
document.querySelectorAll('textarea[data-note]').forEach(t=>t.addEventListener('input',()=>{{const prior=state.decisions[t.dataset.note]||{{decision:'unknown'}};state.decisions[t.dataset.note]={{decision:prior.decision,note:t.value}};save()}}));
document.getElementById('copy').addEventListener('click',async()=>{{await navigator.clipboard.writeText(JSON.stringify(exportPayload(),null,2));document.getElementById('save-state').textContent='JSON 已复制'}});
document.getElementById('export').addEventListener('click',()=>{{const blob=new Blob([JSON.stringify(exportPayload(),null,2)],{{type:'application/json'}});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=queue.review_session_id+'-decisions.json';a.click();URL.revokeObjectURL(a.href)}});render();
</script></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--funnel-json", type=Path, required=True)
    parser.add_argument("--backtest-json", type=Path, required=True)
    parser.add_argument("--dry-plan-json", type=Path, required=True)
    parser.add_argument("--chip-json", type=Path, required=True)
    parser.add_argument("--base-database", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    funnel, backtest, dry_plan, chip = map(_load, (
        args.funnel_json, args.backtest_json, args.dry_plan_json, args.chip_json,
    ))
    queue = build_queue(
        funnel=funnel, backtest=backtest, dry_plan=dry_plan,
        names=_names(args.base_database),
    )
    args.output_directory.mkdir(parents=True, exist_ok=True)
    queue_path = args.output_directory / "review_queue.json"
    html_path = args.output_directory / "index.html"
    queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(render_html(
        queue=queue, funnel=funnel, backtest=backtest, dry_plan=dry_plan, chip=chip,
    ), encoding="utf-8")
    print(json.dumps({
        "review_session_id": queue["review_session_id"],
        "card_count": len(queue["cards"]), "human_actions_required": 0,
        "queue_json": str(queue_path), "html": str(html_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
