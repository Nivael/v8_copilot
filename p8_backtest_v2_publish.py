"""Publish the final human-readable P8 v2 rank and tradable-basket scorecard."""
from __future__ import annotations

import argparse
import html
import json
import sqlite3
from pathlib import Path
from typing import Any

from data_refresh import atomic_write_json
from p8_backtest_v2 import CONTRACT_VERSION
from p8_research import P8ResearchRepository, build_run, content_id
from settings import P8_RESEARCH_DB


def _latest_record(
    repository: P8ResearchRepository, run_kind: str, record_type: str,
) -> tuple[str, str, dict[str, Any]]:
    if not repository.path.is_file():
        return "", "", {}
    with sqlite3.connect(f"file:{repository.path}?mode=ro", uri=True) as connection:
        row = connection.execute(
            "select p.run_id,p.content_digest,r.payload_json from p8_runs p "
            "join p8_records r on r.run_id=p.run_id "
            "where p.run_kind=? and r.record_type=? "
            "order by p.created_at desc,p.run_id desc limit 1", (run_kind, record_type),
        ).fetchone()
    return (str(row[0]), str(row[1]), json.loads(str(row[2]))) if row else ("", "", {})


def build_final_report(repository: P8ResearchRepository) -> dict[str, Any]:
    rank_run_id, rank_digest, rank = _latest_record(
        repository, "p8_backtest_v2_report", "p8_backtest_v2_report",
    )
    basket_run_id, basket_digest, basket = _latest_record(
        repository, "p8_walk_forward_basket_v2", "p8_walk_forward_basket_v2",
    )
    if not rank or not basket:
        raise ValueError("最终发布需要 rank 与 basket 两个完整 run")
    scorecards = [dict(item) for item in rank["signal_scorecards"]]
    reference_run_id, reference_digest, reference = _latest_record(
        repository, "p8_reference_backtest_v2", "p8_reference_backtest_v2",
    )
    if reference:
        scorecards.extend(dict(item) for item in reference["family_scorecards"])
    for item in scorecards:
        if item["signal_family"] not in {"p8c_accumulation", "p8c_holder"}:
            continue
        if item["status"] == "supported_pending_basket":
            incremental = basket.get(
                "persistent_lane_incremental_compounded_excess_st"
                if item["signal_family"] == "p8c_accumulation"
                else "holder_lane_incremental_compounded_excess_st"
            )
            item["status"] = "supported" if incremental is not None and incremental >= 0 else "weak"
            item["basket_incremental_excess_st"] = incremental
            item["basket_resolution"] = (
                "persistent_lane_did_not_drag" if item["status"] == "supported"
                else "persistent_lane_dragged_or_unavailable"
            )
    scorecards.append({
        "signal_family": "p8d_funnel_basket",
        "status": basket["status"],
        "positive_excess_year_count": basket["positive_excess_year_count"],
        "overall_compounded_excess_st": basket["overall_compounded_excess_st"],
        "top_two_removed_compounded_excess_st": basket["top_two_removed_compounded_excess_st"],
        "last_observable_terminal_compounded_excess_st": basket.get(
            "last_observable_terminal_compounded_excess_st"
        ),
    })
    unavailable = sum(item["status"] == "unavailable" for item in scorecards)
    killed = sum(item["status"] == "killed" for item in scorecards)
    supported = sum(item["status"] == "supported" for item in scorecards)
    headline = (
        "数据门仍未完成，不能给研究方向下结论。" if unavailable == len(scorecards)
        else f"{len(scorecards)} 个独立账中：支持 {supported}，弱证据 {len(scorecards) - unavailable - killed - supported}，杀 {killed}，不可用 {unavailable}。"
    )
    return {
        "record_id": content_id("P8BT2FINAL", {
            "contract": CONTRACT_VERSION, "rank_digest": rank_digest, "basket_digest": basket_digest,
        }),
        "contract_version": CONTRACT_VERSION,
        "source_run_ids": [rank_run_id, basket_run_id, *([reference_run_id] if reference_run_id else [])],
        "source_digests": {
            "rank": rank_digest, "basket": basket_digest,
            **({"reference": reference_digest} if reference_digest else {}),
        },
        "headline": headline,
        "scorecards": scorecards,
        "rank_report": rank,
        "basket_report": basket,
        "human_validation": {
            "required_for": ["p8b_llm_stage_direction_extraction"],
            "sequential_batch_sizes": [60, 120, 200],
            "current_completed": 0,
            "status": "pending_explicit_body_egress_consent",
            "owner_daily_review_required": 0,
        },
        "prospective_gate": {
            "operating_days_required": 10,
            "validation_days_required": 60,
            "cannot_be_backfilled": True,
        },
        "not_a_trading_signal": True,
    }


def persist_final(repository: P8ResearchRepository, report: dict[str, Any]) -> str:
    run = build_run(
        run_kind="p8_backtest_v2_report", contract_version=f"{CONTRACT_VERSION}+final",
        start_date="2023-01-01", through="2025-12-31",
        source_run_ids=list(report["source_run_ids"]),
        source_digests=dict(report["source_digests"]),
        record_payloads={"p8_backtest_v2_final": [report]},
    )
    repository.persist(run=run, records={"p8_backtest_v2_final": [report]})
    return run.run_id


def _pct(value: Any) -> str:
    return "—" if value is None else f"{float(value):+.1%}"


FAMILY_LABELS = {
    "p8a_p_star": "公司自身 p*",
    "p8b_precursor": "公告前哨",
    "p8c_accumulation": "持续量价",
    "p8c_holder": "股东户数",
    "p8a_reference_layer:strategic_entry_reference": "战投成交参考",
    "p8a_reference_layer:failure_exit_reference": "失败退出参考",
    "p8a_reference_layer:public_node_reference": "公开节点市值",
    "p8d_funnel_basket": "前 20 篓子",
}


def _family_label(value: str) -> str:
    return FAMILY_LABELS.get(value, value)


def render_markdown(report: dict[str, Any]) -> str:
    rows = [
        "# P8-BT2 最终成绩单", "", report["headline"], "",
        "| 方向 | 结论 | 120 日排序差 / 篓子超额 |", "| --- | --- | ---: |",
    ]
    for item in report["scorecards"]:
        value = item.get("cell_equal_high_minus_low_120d_excess_st")
        if value is None:
            value = item.get("overall_compounded_excess_st")
        rows.append(f"| {_family_label(item['signal_family'])} | {item['status']} | {_pct(value)} |")
    rows.extend(["", "## 可交易篓子", "", "| 年份 | 组合 | ST 等权 | 超额 | 最大回撤 |", "| --- | ---: | ---: | ---: | ---: |"])
    for item in report["basket_report"]["per_year"]:
        rows.append(
            f"| {item['year']} | {_pct(item.get('portfolio_return'))} | {_pct(item.get('st_benchmark_return'))} | "
            f"{_pct(item.get('excess_return_st'))} | {_pct(item.get('max_drawdown'))} |"
        )
    rows.extend([
        "", "主排序与篓子均另外展示退市按最后可观察价处理的敏感度；主判定仍按预注册的 -100% 终值。", "",
        "", "## 仍需人类校验", "",
        "正文 LLM 的阶段/方向抽取需按 60→120→200 顺序金标；当前尚未获得正文外发授权，因此不伪造准确率。",
        "真实 10/60 交易日前瞻门继续独立累积，历史结果不能补造。", "",
    ])
    return "\n".join(rows)


def render_html(report: dict[str, Any]) -> str:
    status_label = {
        "supported": "对", "weak": "弱", "killed": "杀", "unavailable": "不可用",
        "supported_pending_basket": "待篓子", "not_reaction_dominant": "非公告回声",
    }
    score_rows = "".join(
        f"<tr><td><b>{html.escape(_family_label(item['signal_family']))}</b><small>{html.escape(item['signal_family'])}</small></td><td><span class='pill {html.escape(item['status'])}'>"
        f"{html.escape(status_label.get(item['status'], item['status']))}</span></td><td>{html.escape(_pct(item.get('cell_equal_high_minus_low_120d_excess_st') if item.get('cell_equal_high_minus_low_120d_excess_st') is not None else item.get('overall_compounded_excess_st')))}</td>"
        f"<td>{html.escape(_pct(item.get('cell_equal_high_minus_low_120d_excess_st_last_observable') if item.get('cell_equal_high_minus_low_120d_excess_st_last_observable') is not None else item.get('last_observable_terminal_compounded_excess_st')))}</td>"
        f"<td>{html.escape(str(item.get('reason') or item.get('basket_resolution') or '按预注册条件判定'))}</td></tr>"
        for item in report["scorecards"]
    )
    rank_cards = [
        item for item in report["scorecards"]
        if item.get("signal_family") in {"p8c_accumulation", "p8c_holder"}
    ]
    rank_rows = "".join(
        f"<tr><td><b>{html.escape(_family_label(item['signal_family']))}</b></td>"
        f"<td>{int(item.get('observation_count') or 0):,}</td><td>{int(item.get('company_count') or 0):,}</td>"
        f"<td>{_pct(item.get('cell_equal_high_minus_low_60d_excess_st'))}</td>"
        f"<td>{_pct(item.get('cell_equal_high_minus_low_120d_excess_st'))}</td>"
        f"<td>{_pct(item.get('cell_equal_high_minus_low_120d_excess_st_last_observable'))}</td>"
        f"<td>{_pct(item.get('cell_equal_high_minus_low_120d_excess_csi2000'))}</td></tr>"
        for item in rank_cards
    )
    per_year_rows = "".join(
        f"<tr><td>{html.escape(_family_label(item['signal_family']))}</td><td>{year}</td>"
        f"<td>{_pct(metrics.get('high_minus_low_120d_excess_st'))}</td>"
        f"<td>{_pct(metrics.get('high_minus_low_120d_excess_st_last_observable'))}</td>"
        f"<td>{_pct(metrics.get('high_minus_low_60d_excess_st'))}</td>"
        f"<td>{_pct((metrics.get('delisted_120d') or {{}}).get('high_minus_low_rate'))}</td></tr>"
        for item in rank_cards for year, metrics in sorted((item.get("per_year") or {}).items())
    )
    basket_rows = "".join(
        f"<tr><td>{main['year']}</td><td>{_pct(main.get('portfolio_return'))}</td>"
        f"<td>{_pct(main.get('st_benchmark_return'))}</td><td>{_pct(main.get('excess_return_st'))}</td>"
        f"<td>{_pct(upper.get('excess_return_st'))}</td><td>{_pct(main.get('max_drawdown'))}</td>"
        f"<td>{main.get('delist_total_loss_settlements', 0)}</td><td>{main.get('trade_count', 0)}</td></tr>"
        for main, upper in zip(
            report["basket_report"]["per_year"],
            report["basket_report"].get("last_observable_terminal_per_year") or [],
        )
    )
    leadingness = next(
        (item.get("leadingness_diagnostic") for item in rank_cards if item["signal_family"] == "p8c_accumulation"),
        None,
    ) or {}
    leadingness_rows = "".join(
        f"<tr><td>{year}</td><td>{int(value.get('hit_count') or 0):,}</td>"
        f"<td>{_pct(value.get('recent_covered_announcement_share'))}</td>"
        f"<td>{_pct(value.get('no_covered_announcement_share'))}</td></tr>"
        for year, value in sorted((leadingness.get("per_year") or {}).items())
    )
    summary = {
        "supported": sum(item["status"] == "supported" for item in report["scorecards"]),
        "weak": sum(item["status"] == "weak" for item in report["scorecards"]),
        "killed": sum(item["status"] == "killed" for item in report["scorecards"]),
        "unavailable": sum(item["status"] == "unavailable" for item in report["scorecards"]),
    }
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,">
<title>P8-BT2 成绩单</title><style>
:root{{--ink:#14201b;--muted:#66716a;--paper:#f1efe8;--card:#fffdf8;--line:#d8d1c2;--green:#24543d;--amber:#8f621e;--red:#923e31;--gray:#69716c}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}
main{{max-width:1160px;margin:auto;padding:54px 26px 80px}}.kicker{{color:var(--green);font-weight:800;letter-spacing:.12em}}h1{{font:700 clamp(38px,6vw,70px)/1.02 Georgia,"Songti SC",serif;margin:.15em 0}}
.lead{{font-size:21px;max-width:880px;color:var(--muted)}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:28px 0}}.metric,section{{background:var(--card);border:1px solid var(--line);padding:24px;border-radius:10px}}.metric strong{{display:block;font:700 34px/1 Georgia,serif;margin-top:8px}}.metric small,td small{{display:block;color:var(--muted)}}section{{margin-top:16px}}h2{{margin:0 0 14px}}
.scroll{{overflow:auto}}table{{width:100%;border-collapse:collapse;min-width:760px}}th,td{{padding:12px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}.pill{{display:inline-block;padding:3px 9px;border-radius:99px;font-weight:700}}
.supported{{background:#dceadf;color:var(--green)}}.weak{{background:#f3e7c9;color:var(--amber)}}.killed{{background:#f1d9d4;color:var(--red)}}.unavailable{{background:#e6e7e3;color:var(--gray)}}
.notice{{border-left:5px solid var(--amber)}}.danger{{border-left:5px solid var(--red)}}footer{{margin-top:28px;color:var(--muted);font-size:13px}}@media(max-width:760px){{main{{padding:30px 14px}}table{{font-size:14px}}.grid{{grid-template-columns:1fr 1fr}}}}
</style><main><div class="kicker">P8 / PRE-REGISTERED SCORECARD</div><h1>方向有没有用，用两张账说话。</h1>
<p class="lead">{html.escape(report['headline'])} 排序与可交易篓子分开，稀有节点率不再冒充主结论。</p>
<div class="grid"><div class="metric"><small>支持</small><strong>{summary['supported']}</strong></div><div class="metric"><small>弱证据</small><strong>{summary['weak']}</strong></div><div class="metric"><small>杀</small><strong>{summary['killed']}</strong></div><div class="metric"><small>不可用</small><strong>{summary['unavailable']}</strong></div></div>
<section><h2>独立方向账</h2><div class="scroll"><table><thead><tr><th>方向</th><th>结论</th><th>主口径</th><th>退市最后价敏感度</th><th>边界</th></tr></thead><tbody>{score_rows}</tbody></table></div></section>
<section><h2>同阶段同期排序</h2><p>数值是高分档减低分档；正数才表示高分档后续更强。主口径对窗口内退市按 −100% 处理。</p><div class="scroll"><table><thead><tr><th>方向</th><th>观察</th><th>公司</th><th>60日 / ST</th><th>120日 / ST</th><th>120日 / ST 最后价</th><th>120日 / 中证2000</th></tr></thead><tbody>{rank_rows}</tbody></table></div></section>
<section><h2>三个独立测试年</h2><div class="scroll"><table><thead><tr><th>方向</th><th>年份</th><th>120日 / ST</th><th>最后价敏感度</th><th>60日 / ST</th><th>退市率差</th></tr></thead><tbody>{per_year_rows}</tbody></table></div></section>
<section class="danger"><h2>50bp 单边成本下的年度篓子</h2><div class="scroll"><table><thead><tr><th>年份</th><th>组合</th><th>ST 等权</th><th>主超额</th><th>退市最后价超额</th><th>最大回撤</th><th>退市结算</th><th>交易</th></tr></thead><tbody>{basket_rows}</tbody></table></div>
<p>主口径三年正超额：{report['basket_report']['positive_excess_year_count']}/3；全期超额 {_pct(report['basket_report'].get('overall_compounded_excess_st'))}；最后价敏感度 {_pct(report['basket_report'].get('last_observable_terminal_compounded_excess_st'))}；去掉每年最佳两只后 {_pct(report['basket_report'].get('top_two_removed_compounded_excess_st'))}。</p></section>
<section><h2>是不是公告回声</h2><p>这里只检查持续量价高分日之前 5 个交易日及当天是否已有覆盖公告；它是诊断，不是因果证明。状态：{html.escape(status_label.get(str(leadingness.get('status') or 'unavailable'), str(leadingness.get('status') or 'unavailable')))}。</p><div class="scroll"><table><thead><tr><th>年份</th><th>高分持续形态日</th><th>近期有公告</th><th>近期无覆盖公告</th></tr></thead><tbody>{leadingness_rows}</tbody></table></div></section>
<section class="notice"><h2>人类只校验一件事</h2><p>正文 LLM 的阶段与方向抽取采用 60→120→200 顺序金标。当前未获正文外发授权，因此状态保持 unavailable，不用标题候选伪造准确率。日常候选无需逐条审核。</p></section>
<footer>{html.escape(report['record_id'])} · contract {CONTRACT_VERSION} · 不构成交易建议</footer></main></html>'''


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=P8_RESEARCH_DB)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path)
    parser.add_argument("--output-html", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repository = P8ResearchRepository(args.repository)
    report = build_final_report(repository)
    run_id = persist_final(repository, report)
    report["run_id"] = run_id
    atomic_write_json(args.output_json, report)
    if args.output_markdown:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(render_markdown(report), encoding="utf-8")
    if args.output_html:
        args.output_html.parent.mkdir(parents=True, exist_ok=True)
        args.output_html.write_text(render_html(report), encoding="utf-8")
    print(json.dumps({"run_id": run_id, "headline": report["headline"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
