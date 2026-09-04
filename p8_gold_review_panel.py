"""Build the sequential, capped P8 body-extraction gold review panel."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from data_refresh import atomic_write_json
from p8_backtest_v2 import _latest_records
from p8_research import P8ResearchRepository, canonical_json
from p8_regimes import regime_for_date
from settings import P8_RESEARCH_DB


REVIEW_VERSION = "p8_llm_gold_review_v1"
MAX_BATCH = 60


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _eligible(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item for item in events
        if item.get("llm_status") == "completed"
        and item.get("source_spans")
        and item.get("evidence_status") in {"body_verified", "provisional", "conflicted"}
    ]


def _stratified_first(events: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], deque[dict[str, Any]]] = defaultdict(deque)
    for item in sorted(events, key=lambda value: (str(value.get("available_as_of")), str(value.get("event_id")))):
        day = str(item.get("available_as_of") or "1900-01-01")
        key = (
            str(item.get("track") or "unknown"),
            str(item.get("process_direction") or "unknown"),
            day[:4], regime_for_date(day).regime_version,
        )
        groups[key].append(item)
    selected: list[dict[str, Any]] = []
    keys = sorted(groups)
    while len(selected) < limit and any(groups.values()):
        for key in keys:
            if groups[key] and len(selected) < limit:
                selected.append(groups[key].popleft())
    return selected


def build_review_queue(repository: P8ResearchRepository, *, limit: int = MAX_BATCH) -> dict[str, Any]:
    if limit < 1 or limit > MAX_BATCH:
        raise ValueError(f"单轮金标必须在 1..{MAX_BATCH}")
    run_id, run_digest, events = _latest_records(repository, "event_graph", "derived_event")
    selected = _stratified_first(_eligible(events), limit)
    cards: list[dict[str, Any]] = []
    for item in selected:
        verified = item.get("evidence_status") == "body_verified"
        recommendation = "accept_suggested" if verified else "need_more_evidence"
        excerpts = [
            {
                "source_ref": str(span.get("source_ref") or ""),
                "excerpt": str(span.get("excerpt") or ""),
            }
            for span in (item.get("source_spans") or [])[:3]
        ]
        cards.append({
            "card_id": str(item["event_id"]),
            "title": f"{item.get('symbol')} · {item.get('node')}",
            "affected_area": "p8b_llm_extraction",
            "target_field": "p8_event_gold_label",
            "scope": f"{item.get('track')}|{item.get('node')}|{item.get('available_as_of')}",
            "decision_requested": "正文是否支持机器给出的阶段、程序方向和老股东影响？",
            "why_surfaced": "这是顺序金标样本，用于判断正文抽取能否达到 85% precision/recall 门。",
            "recommendation": recommendation,
            "recommendation_label": "接受机器标签" if verified else "先要求补证",
            "recommendation_reason": (
                "确定性规则与正文抽取一致，且已有可定位原文。" if verified
                else "机器结果仍有冲突或未达到自动核证门，不能直接升级真值。"
            ),
            "impact": "决定只写入独立 gold decision 层，不覆盖公告原文或模型输出。",
            "machine_proposal": {
                "stage_node": item.get("node"),
                "process_direction": item.get("process_direction"),
                "old_equity_effect": item.get("old_equity_effect"),
                "evidence_status": item.get("evidence_status"),
            },
            "options": [
                {"value": "accept_suggested", "label": "接受机器标签", "description": "四个字段均可作为本条金标。"},
                {"value": "modify", "label": "修改标签", "description": "方向基本对，但需在备注写明正确阶段/方向。"},
                {"value": "reject", "label": "拒绝", "description": "正文不支持该事件抽取。"},
                {"value": "need_more_evidence", "label": "需要更多证据", "description": "引用不足或正文不完整，本轮不形成金标。"},
            ],
            "evidence_examples": excerpts,
            "source_lens_ids": list(item.get("source_ids") or []),
            "supporting_atom_ids": [str(span.get("source_ref") or "") for span in item.get("source_spans") or []],
            "affected_count": 1,
        })
    identity = {"version": REVIEW_VERSION, "source_run_id": run_id, "card_ids": [item["card_id"] for item in cards]}
    session_id = f"P8GOLD-{_digest(identity)[:20].upper()}"
    return {
        "review_session_id": session_id,
        "review_version": REVIEW_VERSION,
        "title": "P8 正文抽取第一批金标",
        "source_packet": f"p8_event_graph:{run_id}@{run_digest}",
        "selection_rule": "track × direction × year × regime round-robin",
        "candidate_count": len(_eligible(events)),
        "card_count": len(cards),
        "pending_count": len(cards),
        "cards": cards,
        "empty_reason": (
            "尚无 llm_status=completed 的正文抽取；未获正文外发授权时这是正确的空结果。"
            if not cards else ""
        ),
    }


def render_html(queue: dict[str, Any]) -> str:
    embedded = json.dumps(queue, ensure_ascii=False).replace("</", "<\\/")
    empty = html.escape(str(queue.get("empty_reason") or ""))
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,">
<title>P8 正文金标</title><style>
:root{{--ink:#17211c;--muted:#657169;--paper:#f1efe8;--card:#fffdf8;--line:#d5cdbc;--accent:#24543d;--warn:#93621f}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}
header{{position:sticky;top:0;z-index:4;background:rgba(241,239,232,.96);border-bottom:1px solid var(--line);padding:14px 22px;display:flex;gap:18px;align-items:center;flex-wrap:wrap}}
header strong{{font-size:19px}}header span{{color:var(--muted)}}button{{border:1px solid var(--line);background:white;padding:9px 12px;border-radius:6px;cursor:pointer}}button.primary{{background:var(--accent);color:white;border-color:var(--accent)}}
main{{max-width:1120px;margin:auto;padding:24px;display:grid;grid-template-columns:minmax(0,760px) 300px;gap:18px}}.card,aside{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:22px;margin-bottom:14px}}h1{{font:700 34px/1.15 Georgia,"Songti SC",serif;margin:0 0 8px}}h2{{margin:6px 0;font-size:22px}}.question{{font-size:18px;margin:15px 0}}.recommend{{border-left:4px solid var(--accent);padding:10px 14px;background:#edf3ed}}.choices{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:14px 0}}.choices button.selected{{outline:3px solid #98b4a2;background:#edf3ed}}textarea{{width:100%;min-height:70px;border:1px solid var(--line);padding:9px}}details{{margin-top:12px}}blockquote{{margin:8px 0;padding-left:12px;border-left:3px solid var(--line);color:#38443d}}aside{{position:sticky;top:88px;height:max-content}}pre{{white-space:pre-wrap;word-break:break-word;max-height:360px;overflow:auto;background:#f4f2ec;padding:10px;font-size:11px}}.empty{{padding:40px;border:1px dashed var(--line);background:var(--card)}}
@media(max-width:850px){{main{{grid-template-columns:1fr}}aside{{position:static}}}}@media(max-width:520px){{.choices{{grid-template-columns:1fr}}main{{padding:12px}}}}
</style><header><strong>P8 正文金标</strong><span id="progress">0 / {queue['card_count']}</span><span id="save">已启用本机自动保存</span><button id="export" class="primary">导出决定 JSON</button></header>
<main><div><h1>人只判断正文支不支持。</h1><p>机器已给出标签、推荐动作和原文片段；你不需要重新做研究。</p><div id="cards"></div></div><aside><b>本轮导出预览</b><pre id="preview"></pre></aside></main>
<script>const queue={embedded};const key='p8-gold-'+queue.review_session_id;let state=JSON.parse(localStorage.getItem(key)||'{{}}');
function exportPayload(){{return{{review_session_id:queue.review_session_id,review_version:queue.review_version,exported_at:new Date().toISOString(),source_packet:queue.source_packet,decisions:queue.cards.map(c=>({{card_id:c.card_id,decision:state[c.card_id]?.decision||'pending',note:state[c.card_id]?.note||'',target_field:c.target_field,affected_area:c.affected_area,scope:c.scope,recommended_decision:c.recommendation,question:c.decision_requested}}))}}}}
function save(){{localStorage.setItem(key,JSON.stringify(state));document.querySelector('#save').textContent='已保存到本机';renderMeta()}}
function renderMeta(){{const done=queue.cards.filter(c=>state[c.card_id]?.decision&&state[c.card_id].decision!=='pending').length;document.querySelector('#progress').textContent=`${{done}} / ${{queue.card_count}}`;document.querySelector('#preview').textContent=JSON.stringify(exportPayload(),null,2)}}
function render(){{const root=document.querySelector('#cards');if(!queue.cards.length){{root.innerHTML=`<div class="empty">{empty}</div>`;renderMeta();return}}root.innerHTML='';queue.cards.forEach(c=>{{const el=document.createElement('section');el.className='card';const evidence=c.evidence_examples.map(e=>`<blockquote>${{escapeHtml(e.excerpt)}}<br><small>${{escapeHtml(e.source_ref)}}</small></blockquote>`).join('');el.innerHTML=`<small>${{escapeHtml(c.card_id)}} · ${{escapeHtml(c.affected_area)}}</small><h2>${{escapeHtml(c.title)}}</h2><div class="question">${{escapeHtml(c.decision_requested)}}</div><div class="recommend"><b>机器建议：${{escapeHtml(c.recommendation_label)}}</b><br>${{escapeHtml(c.recommendation_reason)}}<br><small>${{escapeHtml(c.impact)}}</small></div><div class="choices">${{c.options.map(o=>`<button data-value="${{o.value}}" title="${{escapeHtml(o.description)}}">${{escapeHtml(o.label)}}</button>`).join('')}}</div><textarea placeholder="只有修改标签或补充语境时才需要备注">${{escapeHtml(state[c.card_id]?.note||'')}}</textarea><details><summary>查看最强原文与来源</summary>${{evidence}}</details>`;el.querySelectorAll('button[data-value]').forEach(b=>{{if(state[c.card_id]?.decision===b.dataset.value)b.classList.add('selected');b.onclick=()=>{{state[c.card_id]={{...(state[c.card_id]||{{}}),decision:b.dataset.value}};save();render()}}}});el.querySelector('textarea').oninput=e=>{{state[c.card_id]={{...(state[c.card_id]||{{}}),note:e.target.value}};save()}};root.appendChild(el)}});renderMeta()}}
function escapeHtml(s){{return String(s??'').replace(/[&<>"']/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}}[m]))}}
document.querySelector('#export').onclick=()=>{{const blob=new Blob([JSON.stringify(exportPayload(),null,2)],{{type:'application/json'}});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=queue.review_session_id+'-decisions.json';a.click();URL.revokeObjectURL(a.href)}};render();</script></html>'''


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=P8_RESEARCH_DB)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=MAX_BATCH)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    queue = build_review_queue(P8ResearchRepository(args.repository), limit=args.limit)
    args.output_directory.mkdir(parents=True, exist_ok=True)
    atomic_write_json(args.output_directory / "review_queue.json", queue)
    (args.output_directory / "index.html").write_text(render_html(queue), encoding="utf-8")
    print(json.dumps({
        "review_session_id": queue["review_session_id"],
        "card_count": queue["card_count"],
        "output_directory": str(args.output_directory),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
