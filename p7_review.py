"""Compressed P7 release review queue, static file:// panel and idempotent import."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from settings import MARKET_ACTIVITY_MANIFEST_PATH, P7_INTELLIGENCE_DB, P7_REVIEW_DIR


REVIEW_VERSION = "p7_release_review_v1"
Decision = Literal["keep_shadow", "publish_descriptive_only", "return_to_data_gap"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ReviewOption(StrictModel):
    value: Decision
    label: str
    description: str


class P7ReviewCard(StrictModel):
    card_id: str = Field(pattern=r"^P7RC-[A-F0-9]{20}$")
    title: str
    affected_area: str
    target_field: str
    scope: Literal["release_gate"] = "release_gate"
    decision_requested: str
    why_surfaced: str
    recommendation: Decision
    recommendation_label: str
    recommendation_reason: str
    evidence_summary: list[str]
    impact: str
    options: list[ReviewOption]


class P7ReviewQueue(StrictModel):
    review_session_id: str = Field(pattern=r"^P7RV-[A-F0-9]{20}$")
    review_version: Literal[REVIEW_VERSION] = REVIEW_VERSION
    title: str
    source_packet: str
    created_at: str
    max_pending: int = Field(default=2, ge=1, le=20)
    cards: list[P7ReviewCard] = Field(min_length=1, max_length=20)


class P7ReviewDecision(StrictModel):
    card_id: str
    decision: Decision
    note: str = Field(default="", max_length=2000)
    target_field: str
    affected_area: str
    scope: Literal["release_gate"] = "release_gate"
    recommended_decision: Decision
    question: str


class P7ReviewDecisionExport(StrictModel):
    review_session_id: str
    review_version: Literal[REVIEW_VERSION] = REVIEW_VERSION
    exported_at: str
    source_packet: str
    decisions: list[P7ReviewDecision] = Field(min_length=1, max_length=20)


OPTIONS = [
    ReviewOption(value="keep_shadow", label="继续影子观察", description="保存事实与结果，但不向用户发布行动性排序。"),
    ReviewOption(value="publish_descriptive_only", label="只发布描述事实", description="只显示发生了什么、覆盖和来源，不输出交易建议。"),
    ReviewOption(value="return_to_data_gap", label="退回数据缺口", description="不发布，并把本卡列出的缺口重新设为阻塞。"),
]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _card_id(area: str, target: str) -> str:
    return f"P7RC-{_digest((REVIEW_VERSION, area, target))[:20].upper()}"


def build_review_queue(metrics: dict[str, Any]) -> P7ReviewQueue:
    announcement = metrics.get("announcement", {})
    activity = metrics.get("activity", {})
    shadow = metrics.get("shadow", {})
    provider = metrics.get("provider", {})
    cards = [
        P7ReviewCard(
            card_id=_card_id("p7a", "announcement_release_status"),
            title="P7A 正式公告事实流",
            affected_area="每日公告与发行人状态",
            target_field="p7a_release_status",
            decision_requested="是否把公告分类、证据包和硬状态变化作为描述性事实发布？",
            why_surfaced="确定性规则、正式来源回链和 conflict/unknown 路径已经完成；不需要逐公告人审。",
            recommendation="publish_descriptive_only",
            recommendation_label="建议：只发布描述事实",
            recommendation_reason="P7A 不依赖量价预测力；只要来源和状态机可复算，就可以独立提供研究整理。",
            evidence_summary=[
                f"公告记录 {announcement.get('announcement_count', 0)} 条，证据包 {announcement.get('bundle_count', 0)} 个。",
                f"硬状态跃迁 {announcement.get('hard_transition_count', 0)} 条；普通进展固定不算硬结果。",
                "无法自动确定的公告保持 unknown/conflicted，不转成人工流水线。",
            ],
            impact="决定每日页中的公告和硬节点区是否对用户可见；不会改变原始公告或重整真值。",
            options=OPTIONS,
        ),
        P7ReviewCard(
            card_id=_card_id("p7bc", "activity_linkage_release_status"),
            title="P7B/P7C 异常活动与联动队列",
            affected_area="异常交易活跃与研究优先级",
            target_field="p7bc_release_status",
            decision_requested="在真实前瞻观察尚未达到 60 个交易日前，量价和联动是否继续保持 shadow？",
            why_surfaced="工程和历史回放已完成，但前瞻时间门不能用历史回测替代。",
            recommendation="keep_shadow",
            recommendation_label="建议：继续影子观察",
            recommendation_reason="当前只能证明算法可复算和历史工作量可控，不能证明前瞻研究增益。",
            evidence_summary=[
                f"活动数据截至 {activity.get('checked_through', '—')}，自由流通换手覆盖 {activity.get('coverage_pct', 0)}%。",
                f"balanced 历史 episode {shadow.get('episode_count', 0)} 个、公司 {shadow.get('company_count', 0)} 家；结论仅 descriptive。",
                f"前瞻进度 {shadow.get('prospective_days', 0)}/60 个交易日。",
                "daily_basic 未返回 limit_status；shadow 使用 raw OHLC + stk_limit 双源识别并 fail closed。",
                f"交易所公开标签接口：{provider.get('exchange_reference_status', 'unavailable')}（非阻塞）。",
            ],
            impact="决定异常量价和联动区是继续内部积累，还是仅以描述性、非交易信号方式展示。",
            options=[item for item in OPTIONS if item.value != "publish_descriptive_only"],
        ),
    ]
    source_packet = f"sha256:{_digest({'metrics': metrics, 'cards': [card.model_dump(mode='json') for card in cards]})}"
    return P7ReviewQueue(
        review_session_id=f"P7RV-{_digest(source_packet)[:20].upper()}",
        title="P7 发布校验（2 个决定）", source_packet=source_packet,
        created_at=datetime.now(timezone.utc).isoformat(), cards=cards,
    )


def validate_decision_export(queue: P7ReviewQueue, export: P7ReviewDecisionExport) -> None:
    if export.review_session_id != queue.review_session_id or export.source_packet != queue.source_packet:
        raise ValueError("决定导出与审阅队列身份不一致")
    cards = {card.card_id: card for card in queue.cards}
    if len({item.card_id for item in export.decisions}) != len(export.decisions):
        raise ValueError("同一 card_id 不得重复")
    for decision in export.decisions:
        card = cards.get(decision.card_id)
        if card is None:
            raise ValueError(f"未知 card_id: {decision.card_id}")
        if decision.target_field != card.target_field or decision.affected_area != card.affected_area:
            raise ValueError("决定目标与审阅卡不一致")
        if decision.recommended_decision != card.recommendation or decision.question != card.decision_requested:
            raise ValueError("决定上下文与审阅卡不一致")
        if decision.decision not in {option.value for option in card.options}:
            raise ValueError("该发布门当前不允许所选决定")


class P7ReviewRepository:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.executescript("""
            create table if not exists p7_review_queues (
                review_session_id text primary key, source_packet text not null,
                payload_json text not null, created_at text not null
            );
            create table if not exists p7_review_decisions (
                review_session_id text not null, card_id text not null,
                decision_json text not null, imported_at text not null,
                primary key(review_session_id,card_id)
            );
        """)
        return connection

    def save_queue(self, queue: P7ReviewQueue) -> None:
        with self._connect() as connection:
            existing = connection.execute(
                "select payload_json from p7_review_queues where review_session_id=?",
                (queue.review_session_id,),
            ).fetchone()
            payload = queue.model_dump_json()
            if existing is not None:
                previous = json.loads(existing[0])
                current = json.loads(payload)
                previous.pop("created_at", None)
                current.pop("created_at", None)
                if previous != current:
                    raise ValueError("review_session_id 已绑定不同队列")
                return
            connection.execute(
                "insert or ignore into p7_review_queues values (?,?,?,?)",
                (queue.review_session_id, queue.source_packet, payload, queue.created_at),
            )

    def import_decisions(self, queue: P7ReviewQueue, export: P7ReviewDecisionExport) -> list[dict[str, Any]]:
        validate_decision_export(queue, export)
        applied = []
        with self._connect() as connection:
            for decision in export.decisions:
                payload = decision.model_dump_json()
                existing = connection.execute(
                    "select decision_json from p7_review_decisions where review_session_id=? and card_id=?",
                    (queue.review_session_id, decision.card_id),
                ).fetchone()
                if existing is not None:
                    if json.loads(existing[0]) != json.loads(payload):
                        raise ValueError("同一审阅卡已经导入不同决定")
                    applied.append({"card_id": decision.card_id, "replayed": True})
                    continue
                connection.execute(
                    "insert into p7_review_decisions values (?,?,?,?)",
                    (queue.review_session_id, decision.card_id, payload, datetime.now(timezone.utc).isoformat()),
                )
                applied.append({"card_id": decision.card_id, "replayed": False})
        return applied


def _panel_html(queue: P7ReviewQueue) -> str:
    queue_json = queue.model_dump_json()
    safe_json = queue_json.replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(queue.title)}</title><style>
:root{{--ink:#171717;--muted:#6b7280;--line:#dedede;--paper:#f6f5f1;--blue:#174ea6;--amber:#8a5a00}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}header.top{{position:sticky;top:0;z-index:3;background:#f6f5f1ee;backdrop-filter:blur(12px);border-bottom:1px solid var(--line);padding:18px max(24px,calc((100vw - 1160px)/2));display:flex;justify-content:space-between;gap:20px;align-items:center}}.top h1{{font-size:18px;margin:0}}.top p{{margin:4px 0 0;color:var(--muted);font-size:12px}}button{{font:inherit;border:1px solid var(--line);background:#fff;border-radius:5px;padding:9px 12px;cursor:pointer}}button.primary{{background:#171717;color:#fff;border-color:#171717}}main{{max-width:1160px;margin:auto;padding:38px 24px 80px;display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:24px}}.intro{{grid-column:1/-1;border-bottom:1px solid var(--line);padding-bottom:24px}}.intro strong{{font-size:34px;letter-spacing:-.04em}}.intro p{{color:var(--muted);max-width:760px;line-height:1.6}}.cards{{display:grid;gap:16px}}article{{background:#fff;border:1px solid var(--line);border-radius:7px;padding:22px}}article>small{{font:11px ui-monospace;color:var(--muted)}}h2{{font-size:22px;margin:8px 0 12px}}.question{{font-size:15px;line-height:1.55}}.recommend{{background:#edf4ff;border-left:3px solid var(--blue);padding:12px 14px;margin:16px 0}}.recommend strong{{color:var(--blue);font-size:13px}}.recommend p{{font-size:12px;margin:5px 0 0;line-height:1.55;color:#364152}}ul{{padding-left:18px;color:#4b5563;font-size:12px;line-height:1.7}}fieldset{{border:0;padding:0;margin:20px 0 0;display:grid;gap:8px}}legend{{font-size:12px;font-weight:700;margin-bottom:8px}}label.option{{display:flex;gap:10px;border:1px solid var(--line);border-radius:6px;padding:11px;cursor:pointer}}label.option:has(input:checked){{border-color:#174ea6;background:#f5f8ff}}label.option span{{display:grid;gap:3px}}label.option small{{color:var(--muted)}}textarea{{width:100%;min-height:74px;border:1px solid var(--line);border-radius:6px;padding:10px;font:inherit;resize:vertical}}aside{{position:sticky;top:100px;align-self:start;background:#111;color:#e5e7eb;border-radius:7px;padding:18px;max-height:calc(100vh - 124px);overflow:auto}}aside h2{{font-size:14px;margin:0 0 4px}}aside p{{font-size:11px;color:#9ca3af}}pre{{white-space:pre-wrap;word-break:break-word;font:11px/1.55 ui-monospace}}.impact{{font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:12px}}.note-label{{display:grid;gap:6px;font-size:12px;margin-top:12px}}@media(max-width:860px){{main{{grid-template-columns:1fr}}aside{{position:static;max-height:none}}header.top{{align-items:flex-start;flex-direction:column}}}}
</style></head><body><header class="top"><div><h1>{html.escape(queue.title)}</h1><p id="progress">0/{len(queue.cards)} 已决定 · 草稿自动保存在本浏览器</p></div><div><button id="accept">一键采用全部建议</button> <button id="copy">复制 JSON</button> <button class="primary" id="download">下载决定 JSON</button></div></header><main><section class="intro"><small>只审发布决定，不审逐股和逐公告</small><br><strong>2 张卡，几分钟完成</strong><p>系统已经完成数据核验、规则回归和历史 shadow。你只决定哪些内容现在可见；任何选择都不会覆盖原始事实。</p></section><section class="cards" id="cards"></section><aside><h2>可导入决定 JSON</h2><p>选择会实时更新；备注可留空。</p><pre id="preview"></pre></aside></main>
<script id="queue" type="application/json">{safe_json}</script><script>
const q=JSON.parse(document.getElementById('queue').textContent);const key='p7-review:'+q.review_session_id;let drafts=JSON.parse(localStorage.getItem(key)||'{{}}');
function exp(){{return{{review_session_id:q.review_session_id,review_version:q.review_version,exported_at:new Date().toISOString(),source_packet:q.source_packet,decisions:q.cards.filter(c=>drafts[c.card_id]?.decision).map(c=>({{card_id:c.card_id,decision:drafts[c.card_id].decision,note:drafts[c.card_id].note||'',target_field:c.target_field,affected_area:c.affected_area,scope:c.scope,recommended_decision:c.recommendation,question:c.decision_requested}}))}}}}
function save(){{localStorage.setItem(key,JSON.stringify(drafts));document.getElementById('preview').textContent=JSON.stringify(exp(),null,2);document.getElementById('progress').textContent=`${{exp().decisions.length}}/${{q.cards.length}} 已决定 · 草稿已自动保存`}}
function render(){{const root=document.getElementById('cards');root.innerHTML='';q.cards.forEach((c,i)=>{{const a=document.createElement('article');a.innerHTML=`<small>0${{i+1}} · ${{c.affected_area}}</small><h2>${{c.title}}</h2><p class="question">${{c.decision_requested}}</p><div class="recommend"><strong>${{c.recommendation_label}}</strong><p>${{c.recommendation_reason}}</p></div><ul>${{c.evidence_summary.map(x=>`<li>${{x}}</li>`).join('')}}</ul><p class="impact">影响：${{c.impact}}</p><fieldset><legend>你的决定</legend>${{c.options.map(o=>`<label class="option"><input type="radio" name="${{c.card_id}}" value="${{o.value}}" ${{drafts[c.card_id]?.decision===o.value?'checked':''}}><span><b>${{o.label}}${{o.value===c.recommendation?'（推荐）':''}}</b><small>${{o.description}}</small></span></label>`).join('')}}</fieldset><label class="note-label">可选备注<textarea placeholder="可以不填">${{drafts[c.card_id]?.note||''}}</textarea></label>`;a.querySelectorAll('input').forEach(x=>x.onchange=()=>{{drafts[c.card_id]={{...(drafts[c.card_id]||{{}}),decision:x.value}};save();render()}});a.querySelector('textarea').oninput=e=>{{drafts[c.card_id]={{...(drafts[c.card_id]||{{}}),note:e.target.value}};save()}};root.appendChild(a)}});save()}}
document.getElementById('accept').onclick=()=>{{q.cards.forEach(c=>drafts[c.card_id]={{...(drafts[c.card_id]||{{}}),decision:c.recommendation}});save();render()}};document.getElementById('copy').onclick=()=>navigator.clipboard.writeText(JSON.stringify(exp(),null,2));document.getElementById('download').onclick=()=>{{if(exp().decisions.length!==q.cards.length){{alert('请先完成两张卡，或一键采用建议。');return}}const b=new Blob([JSON.stringify(exp(),null,2)],{{type:'application/json'}}),u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download=q.review_session_id+'-decisions.json';a.click();URL.revokeObjectURL(u)}};render();
</script></body></html>"""


def build_static_panel(queue: P7ReviewQueue, output_directory: Path) -> dict[str, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    queue_path = output_directory / "review_queue.json"
    html_path = output_directory / "index.html"
    template_path = output_directory / "decision_template.json"
    handoff_path = output_directory / "HANDOFF.md"
    queue_path.write_text(queue.model_dump_json(indent=2), encoding="utf-8")
    html_path.write_text(_panel_html(queue), encoding="utf-8")
    template = {
        "review_session_id": queue.review_session_id,
        "review_version": queue.review_version,
        "exported_at": "",
        "source_packet": queue.source_packet,
        "decisions": [],
    }
    template_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    handoff_path.write_text(
        "# P7 发布校验\n\n直接双击 `index.html`。选择两张卡后下载 JSON；随后运行：\n\n"
        "`python p7_review.py import --queue review_queue.json --decisions <下载的文件>`\n",
        encoding="utf-8",
    )
    return {"queue": queue_path, "html": html_path, "template": template_path, "handoff": handoff_path}


def main() -> int:
    parser = argparse.ArgumentParser(description="P7 compressed release review")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--metrics", type=Path, required=True)
    build.add_argument("--output-directory", type=Path, default=P7_REVIEW_DIR)
    build.add_argument("--database", type=Path, default=P7_INTELLIGENCE_DB)
    apply = sub.add_parser("import")
    apply.add_argument("--queue", type=Path, required=True)
    apply.add_argument("--decisions", type=Path, required=True)
    apply.add_argument("--database", type=Path, default=P7_INTELLIGENCE_DB)
    args = parser.parse_args()
    if args.command == "build":
        metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
        queue = build_review_queue(metrics)
        P7ReviewRepository(args.database).save_queue(queue)
        paths = build_static_panel(queue, args.output_directory)
        print(json.dumps({"review_session_id": queue.review_session_id, "cards": len(queue.cards), "paths": {key: str(value) for key, value in paths.items()}}, ensure_ascii=False, indent=2))
        return 0
    queue = P7ReviewQueue.model_validate_json(args.queue.read_text(encoding="utf-8"))
    export = P7ReviewDecisionExport.model_validate_json(args.decisions.read_text(encoding="utf-8"))
    applied = P7ReviewRepository(args.database).import_decisions(queue, export)
    print(json.dumps({"review_session_id": queue.review_session_id, "applied": applied}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
