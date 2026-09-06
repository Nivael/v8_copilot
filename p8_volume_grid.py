"""Compact, exploratory P8C grid: two axes, entry episodes, two pooled tests."""
from __future__ import annotations

import argparse
import bisect
import hashlib
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from data_refresh import atomic_write_json
from market_activity import MarketActivityRepository
from p7_announcements import classify_announcement, load_announcements
from p7_daily import load_valuation_stage_map
from p8_backtest_v2 import _benchmarks, _calendar_membership, _latest_records
from p8_prices import qfq_series
from p8_grid_price_coverage import verified_suspensions
from p8_research import P8ResearchRepository, canonical_json
from p8_walk_forward_basket import load_trade_states
from settings import (ANNOUNCEMENT_REFRESH_DIR, DATA_ROOT, MARKET_ACTIVITY_DB,
                      MARKET_CONTEXT_DB, P8_QFQ_DB, P8_RESEARCH_DB, VALUATION_EPISODE_DB)

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "p8_grid_config.json"
BASE = DATA_ROOT / "shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3"
FOCUS = "low_flat"
CAP_WORDS = ("转增", "让渡", "缩股", "股份注销", "股本变动", "股本变化")


def digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def in_window(rows, start, end):
    return rows[bisect.bisect_left(rows, start):bisect.bisect_right(rows, end)]


def classify(position, drift, cumulative, elevated, z, amplitude, config):
    t = config["thresholds"]
    band = "low" if position <= t["position_tail"] else "high" if position >= 1-t["position_tail"] else "mid"
    direction = "flat" if abs(drift) <= t["flat_band"] else "up" if drift > 0 else "down"
    active = cumulative >= t["cum_log_excess_min"] and elevated >= t["elevated_ratio_min"]
    pulse = None if z is None or amplitude is None else z >= t["pulse_z_min"] and amplitude >= t["pulse_amplitude_min"]
    return band + "_" + direction, active, pulse


def price_position(price, suspended, index, size):
    """Fixed market-day horizon; only proven full-day suspensions explain gaps."""
    if index < size-1:
        return None, 0, 0, "price_history_short"
    window = price[index-size+1:index+1]
    valid = np.isfinite(window) & (window > 0)
    missing = ~valid
    if not valid[-1]:
        return None, int(valid.sum()), 0, "current_price_missing"
    excused = missing & suspended[index-size+1:index+1]
    if (missing & ~excused).any():
        return None, int(valid.sum()), int(excused.sum()), "price_gap_unverified"
    observed = window[valid]
    position = (np.sum(observed < price[index]) + .5*np.sum(observed == price[index])) / len(observed)
    return float(position), len(observed), int(excused.sum()), None


def make_grid(features, facts, prices, calendar, memberships, stages, announcements, events, config, suspension_evidence=None):
    by_symbol = defaultdict(dict)
    for f in features:
        by_symbol[f["symbol"]][f["trade_date"]] = f
    fact_map = {(f.symbol, f.trade_date): f for f in facts}
    suspended = verified_suspensions(facts, suspension_evidence)
    news, capital, refs = defaultdict(set), defaultdict(set), defaultdict(list)
    for a in announcements:
        s, day = a["symbol"], a["announcement_date"]
        category, _ = classify_announcement(a["title"], a.get("announcement_type", ""))
        if category in {"restructuring_and_pre_restructuring", "risk_warning_and_delisting"}:
            news[s].add(day)
            refs[(s, day)].append(a["announcement_id"])
        if any(word in a["title"] for word in CAP_WORDS):
            capital[s].add(day)
    for e in events:
        if e.get("precursor_candidates_for") or not e.get("not_hard_outcome", True):
            news[e["symbol"]].add(e["available_as_of"])
            refs[(e["symbol"], e["available_as_of"])].extend(e.get("source_ids", []))
    news = {s: sorted(v) for s, v in news.items()}
    capital = {s: sorted(v) for s, v in capital.items()}
    w = config["windows"]
    output, gaps = [], Counter()
    for symbol, fs in sorted(by_symbol.items()):
        p = dict(prices.get(symbol, []))
        price = np.array([p.get(d, np.nan) for d in calendar])
        suspension_mask = np.array([(symbol, d) in suspended for d in calendar])
        sf = [fact_map.get((symbol, d)) for d in calendar]
        turns = np.array([f.turnover_rate_f if f and f.eligible_for_anomaly and f.turnover_rate_f else np.nan for f in sf])
        shares = np.array([f.total_share_10k if f and f.total_share_10k else np.nan for f in sf])
        changes = [calendar[i] for i in range(1, len(calendar)) if np.isfinite(shares[i-1:i+1]).all() and shares[i] != shares[i-1]]
        for i, day in enumerate(calendar):
            if day > config["signal_through"] or symbol not in memberships.get(day, set()):
                continue
            f = fs.get(day, {})
            year = day[:4]
            gaps[f"{year}:member_days"] += 1
            position, observed, skipped, gap = price_position(price, suspension_mask, i, w["position"])
            values = [f.get(k) for k in ("cum_turnover_log_excess_20", "elevated_day_ratio_20", "excess_return_st_20")]
            if gap:
                gaps[f"{year}:{gap}"] += 1
                continue
            gaps[f"{year}:price_window_valid"] += 1
            gaps[f"{year}:price_window_with_verified_suspensions"] += bool(skipped)
            if any(v is None for v in values) or f.get("baseline_observations", 0) < w["baseline"] or not np.isfinite(turns[i-w["activity"]+1:i+1]).all():
                gaps[f"{year}:activity_window_or_baseline_missing"] += 1
                continue
            gaps[f"{year}:grid_valid"] += 1
            past = turns[max(0, i-w["baseline"]):i]
            med = float(np.median(past)) if np.isfinite(past).all() and len(past) == w["baseline"] else np.nan
            mad = float(np.median(np.abs(past-med)))
            z = float((turns[i]-med)/(1.4826*mad)) if np.isfinite(mad) and mad > 0 else None
            grid, active, pulse = classify(position, values[2], values[0], values[1], z, f.get("single_day_amplitude_ratio"), config)
            gaps[f"{year}:low_flat_active_days"] += grid == FOCUS and active
            news_days = in_window(news.get(symbol, []), calendar[max(0, i-w["announcement"])], day)
            cap_start = calendar[i-w["position"]+1]
            cap_days = in_window(capital.get(symbol, []), cap_start, day) + in_window(changes, cap_start, day)
            share_complete = bool(np.isfinite(shares[i-w["position"]+1:i+1]).all())
            output.append(dict(symbol=symbol, day=day, index=i, grid=grid, active=active, pulse=pulse,
                               position=position, drift=values[2], cumulative=values[0], elevated=values[1],
                               price_observations=observed, price_window_start=calendar[i-w["position"]+1],
                               suspended_dates=[calendar[j] for j in range(i-w["position"]+1, i+1)
                                                if suspension_mask[j] and (not np.isfinite(price[j]) or price[j] <= 0)],
                               stage=stages.get((symbol, day), "unknown"),
                               announcement="detected" if news_days else "none_detected",
                               announcement_refs=sorted({r for d in news_days for r in refs[(symbol, d)]}),
                               capital="detected" if cap_days else "none_detected" if share_complete else "unknown",
                               capital_dates=sorted(set(cap_days))))
    return sorted(output, key=lambda r: (r["symbol"], r["index"])), dict(gaps)


def make_episodes(rows, config):
    result = []
    last, state, current, exits = None, None, None, {}
    for row in rows:
        key = (row["grid"], row["active"])
        continuous = last is not None and row["symbol"] == last["symbol"] and row["index"] == last["index"]+1
        if not continuous or key != state:
            if last is not None:
                exits[(last["symbol"], state)] = last["index"]+1
                if current is not None:
                    current.update(exit_index=last["index"]+1, exit_reason="state_change" if continuous else "coverage_or_membership_gap")
            current = None
            exited = exits.get((row["symbol"], key), -100000)
            if continuous and row["index"]-exited > config["windows"]["cooldown"]:
                current = dict(row, episode_id=f"GRID-{row['symbol']}-{row['day']}-{key[0]}-{int(key[1])}")
                result.append(current)
        last, state = row, key
    if current is not None:
        current.update(exit_index=None, exit_reason="right_censored_state")
    return [r for r in result if config["signal_start"] <= r["day"] <= config["signal_through"]]


def observe(episodes, rows, prices, calendar, benchmark, trades, terminals, config):
    lookup = {(r["symbol"], r["index"]): r for r in rows}
    pmap = {s: dict(v) for s, v in prices.items()}
    w = config["windows"]
    result = []
    for e in episodes:
        s, i = e["symbol"], e["index"]
        p, terminal = pmap.get(s, {}), terminals.get(s, "9999-12-31")
        finish = i+w["transition"]
        future = [lookup.get((s, j)) for j in range(i+1, min(finish+1, len(calendar)))]
        hits = [r for r in future if r and r["active"] and r["grid"].endswith("_up") and r["day"] < terminal]
        complete = finish < len(calendar) and all(r is not None for r in future)
        failed = finish < len(calendar) and e["day"] < terminal <= calendar[finish]
        transition = 1.0 if hits else 0.0 if complete or failed else None
        entry = next((j for j in range(i+1, min(i+w["activity"]+1, len(calendar)))
                      if trades.get((s, calendar[j]), {}).get("buy") and calendar[j] in p and calendar[j] < terminal), None)
        for h in config["horizons"]:
            r = dict(e, horizon=h, entry_day=calendar[entry] if entry is not None else None,
                     excess=None, excess_last=None, end_sellable=None, delisted=None,
                     transition_60=transition, transition_day=hits[0]["day"] if hits else None,
                     transition_grid=hits[0]["grid"] if hits else None, positive_node_rate=None,
                     outcome_status="entry_unavailable" if entry is None else "right_censored")
            if entry is not None and entry+h < len(calendar):
                start, end = calendar[entry], calendar[entry+h]
                dead = start < terminal <= end
                end_state = trades.get((s, end), {})
                r.update(end_day=end, delisted=dead, end_sellable=bool(end_state.get("sell")) if end_state.get("known") else None)
                b0, b1 = benchmark.get(start), benchmark.get(end)
                if b0 and b1 and (dead or end in p):
                    stock = -1.0 if dead else p[end]/p[start]-1
                    last = [v for d, v in prices[s] if start <= d <= min(terminal, end)]
                    r.update(excess=stock-(b1/b0-1), excess_last=(last[-1]/p[start]-1 if dead else stock)-(b1/b0-1), outcome_status="observed")
            result.append(r)
    return result


def contrast(treatment, control, value, config, infer=False):
    """Common-stratum ATT; resample companies with the same weight on both arms."""
    cells = defaultdict(lambda: [[], []])
    for side, records in enumerate((treatment, control)):
        for r in records:
            if r.get(value) is not None and r["stage"] != "unknown":
                key = (r["stage"], r["day"][:4], "H1" if r["day"][5:7] <= "06" else "H2", r["announcement"], r["capital"])
                cells[key][side].append(r)
    cells = [v for v in cells.values() if all(v)]
    arms = [[r for c in cells for r in c[side]] for side in (0, 1)]
    out = {"treated_matched": len(arms[0]), "control_matched": len(arms[1]), "common_strata": len(cells),
           "treated_companies": len({r["symbol"] for r in arms[0]}), "control_companies": len({r["symbol"] for r in arms[1]}),
           "treated_total": len(treatment), "difference": None, "ci95": None, "p": None, "status": "descriptive_only"}
    if not cells:
        return out
    companies = sorted({r["symbol"] for arm in arms for r in arm})
    company_index = {s: i for i, s in enumerate(companies)}
    sums, counts = np.zeros((2, len(cells), len(companies))), np.zeros((2, len(cells), len(companies)))
    for c, pair in enumerate(cells):
        for side, records in enumerate(pair):
            for r in records:
                j = company_index[r["symbol"]]
                sums[side, c, j] += r[value]
                counts[side, c, j] += 1
    def estimate(weights):
        n, total = counts @ weights, sums @ weights
        ok = (n[0] > 0) & (n[1] > 0)
        return float(np.average(total[0, ok]/n[0, ok]-total[1, ok]/n[1, ok], weights=n[0, ok])) if ok.any() else None
    out["difference"] = estimate(np.ones(len(companies)))
    gate = config["minimum"]
    if not infer or any(len(a) < gate["episodes"] or len({r["symbol"] for r in a}) < gate["companies"] for a in arms):
        return out
    rng = np.random.default_rng(config["bootstrap"]["seed"])
    boot = [estimate(rng.multinomial(len(companies), np.ones(len(companies))/len(companies))) for _ in range(config["bootstrap"]["replicates"])]
    boot = np.array([x for x in boot if x is not None])
    out.update(ci95=np.quantile(boot, [.025, .975]).tolist(),
               p=float((1+np.sum(np.abs(boot-out["difference"]) >= abs(out["difference"])))/(len(boot)+1)),
               status="exploratory_only")
    return out


def summarize(observations, config):
    focus = [r for r in observations if r["grid"] == FOCUS and r["active"]]
    table = []
    groups = defaultdict(list)
    for r in observations:
        groups[(r["grid"], r["active"], r["horizon"], r["announcement"], r["capital"])].append(r)
    mean = lambda rows, key: float(np.mean([r[key] for r in rows if r.get(key) is not None])) if any(r.get(key) is not None for r in rows) else None
    for (grid, active, horizon, news, capital), records in sorted(groups.items()):
        target = [r for r in focus if r["horizon"] == horizon and r["announcement"] == news and r["capital"] == capital]
        diff = contrast(target, records, "excess", config) if not (grid == FOCUS and active) else {}
        table.append(dict(grid=grid, active=active, horizon=horizon, announcement=news, capital=capital,
                          episodes=len(records), companies=len({r["symbol"] for r in records}),
                          observed=sum(r["excess"] is not None for r in records),
                          entered=sum(r["entry_day"] is not None for r in records),
                          excess=mean(records, "excess"), excess_last=mean(records, "excess_last"),
                          focus_minus_cell=diff.get("difference"), focus_matched=diff.get("treated_matched", 0),
                          control_matched=diff.get("control_matched", 0), end_sellable=mean(records, "end_sellable"),
                          transition_60=mean(records, "transition_60"), transition_observed=sum(r["transition_60"] is not None for r in records),
                          transition_lower=float(np.mean([r["transition_60"] or 0 for r in records])),
                          transition_upper=float(np.mean([1 if r["transition_60"] is None else r["transition_60"] for r in records])),
                          pulse_share=mean(records, "pulse"), pulse_known=sum(r["pulse"] is not None for r in records),
                          delisted=mean(records, "delisted"), negative_node_rate=None,
                          positive_node_rate=None, node_status="body_gold_gate_unavailable"))
    h = config["primary_horizon"]
    no_news = [r for r in observations if r["horizon"] == h and r["announcement"] == "none_detected"]
    treated = [r for r in no_news if r["grid"] == FOCUS and r["active"]]
    other = [r for r in no_news if r["grid"] != FOCUS and r["active"]]
    quiet = [r for r in no_news if r["grid"] == FOCUS and not r["active"]]
    tests = {"H1_120d_excess": contrast(treated, other, "excess", config, True),
             "H2_transition_60": contrast(treated, quiet, "transition_60", config, True)}
    sensitivity = {"H1_last_observable": contrast(treated, other, "excess_last", config)}
    for bound in (0, 1):
        fill = lambda arm: [dict(r, transition_bound=r["transition_60"] if r["transition_60"] is not None else float(bound)) for r in arm]
        sensitivity[f"H2_missing_as_{bound}"] = contrast(fill(treated), fill(quiet), "transition_bound", config)
    for name, t_fill, c_fill in (("lower", 0, 1), ("upper", 1, 0)):
        fill = lambda arm, v: [dict(r, transition_bound=r["transition_60"] if r["transition_60"] is not None else float(v)) for r in arm]
        sensitivity[f"H2_difference_{name}"] = contrast(fill(treated, t_fill), fill(quiet, c_fill), "transition_bound", config)
    previous = 0.0
    for rank, (name, test) in enumerate(sorted(tests.items(), key=lambda kv: kv[1]["p"] if kv[1]["p"] is not None else 1)):
        if test["p"] is not None:
            previous = max(previous, min(1.0, (2-rank)*test["p"]))
            test["p_holm"] = previous
    return table, tests, sensitivity


def render(report):
    labels = {"grid": "格子", "active": "持续活跃", "horizon": "后续交易日", "announcement": "此前公告", "capital": "250日股本标记",
              "episodes": "段数", "companies": "公司数", "observed": "收益可观察", "excess": "ST超额", "excess_last": "最后价口径", "focus_minus_cell": "①减本格（分层）", "transition_60": "60日向上接续", "transition_observed": "接续可观察", "focus_matched": "①匹配段数", "control_matched": "本格匹配段数", "pulse_share": "脉冲比例", "pulse_known": "脉冲可判", "delisted": "期内退市率"}
    names = {f"{p}_{d}": f"{pl}·{dl}" for p, pl in (("low", "低位"), ("mid", "中位"), ("high", "高位")) for d, dl in (("flat", "价稳"), ("up", "向上"), ("down", "向下"))}
    names.update(detected="检出", none_detected="覆盖内未检出", unknown="未知")
    def show(k, v):
        if v is None: return "—"
        if k in {"excess", "excess_last", "focus_minus_cell"}: return f"{v*100:+.1f}pp"
        if k in {"transition_60", "pulse_share", "delisted"}: return f"{v*100:.1f}%"
        if isinstance(v, bool): return "是" if v else "否"
        return html.escape(names.get(str(v), str(v)))
    heads = "".join(f"<th>{v}</th>" for v in labels.values())
    rows = "".join("<tr>"+"".join(f"<td>{show(k,r.get(k))}</td>" for k in labels)+"</tr>" for r in report["table"])
    test_names = {"H1_120d_excess": "①之后120日收益是否更强", "H2_transition_60": "①之后60日是否更常转为放量向上"}
    summaries = "".join(f"<p><b>{test_names[name]}</b>：{'样本不足，仅描述' if test['status']=='descriptive_only' else '探索性检验'}；差值 {show('excess',test['difference'])}；共同层处理/对照 {test['treated_matched']}/{test['control_matched']} 段；公司 {test['treated_companies']}/{test['control_companies']}；95%区间 {'不做推断' if test['ci95'] is None else ' 至 '.join(show('excess',v) for v in test['ci95'])}。</p>" for name, test in report["tests"].items())
    sensitivity = report["sensitivity"]
    censor_note = f"接续结果缺失取最不利/最有利分配时，H2差值范围 {show('excess',sensitivity['H2_difference_lower']['difference'])} 至 {show('excess',sensitivity['H2_difference_upper']['difference'])}。"
    coverage_note = "；".join(f"{year}年① {count}段" for year, count in sorted(report["focus_by_year"].items()))
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="icon" href="data:,"><title>P8C 双轴网格</title>
<style>body{{margin:0;background:#f4f1e9;color:#24362d;font:16px/1.6 system-ui}}main{{padding:32px;max-width:1600px;margin:auto}}h1{{font-size:38px}}.scroll{{overflow:auto;max-height:70vh;background:#fffdf8}}table{{border-collapse:collapse;white-space:nowrap;width:100%}}td,th{{padding:9px;border-bottom:1px solid #ded8ca;text-align:right}}th{{position:sticky;top:0;background:#e8e5da}}input{{padding:12px;min-width:280px}}small{{color:#586860}}</style>
<main><h1>低位价稳放量，之后发生了什么？</h1><p>v3.1停牌语义修正版 · 探索性历史复查；①=低位价稳且持续活跃。六个固定阈值，两项检验。</p>
<p>{coverage_note}。价位仍看250个市场交易日，仅从分母排除已证全天停牌日；没有延长窗口或填旧价，不明缺口仍阻断。每段的真实观察数与停牌日期见JSON。</p>
{summaries}<p>{censor_note}</p><p>“未检出公告”有正文覆盖缺口。股本标记包括标题提及或总股本变化。正面节点准确率尚未通过，节点结果留空。收益是下一可买入收盘后的价格路径，端点可卖比例见CSV；不能直接当组合回报。</p>
<p><input id="filter" placeholder="筛选，例如：低位 价稳 未检出"><small>空白=全部；多个词同时匹配。完整字段与删失上下界见同目录CSV/JSON。</small></p><div class="scroll"><table><thead><tr>{heads}</tr></thead><tbody>{rows}</tbody></table></div>
<p><small>输入摘要 {report['input_digest']} · 行情结论未写回生产配额</small></p></main><script>document.querySelector('#filter').addEventListener('input',e=>{{const words=e.target.value.trim().split(/\\s+/);document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!words.every(w=>r.textContent.includes(w)))}})</script></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--suspension-evidence", type=Path)
    args = parser.parse_args()
    cfg = json.loads(CONFIG.read_text())
    evidence = json.loads(args.suspension_evidence.read_text()) if args.suspension_evidence else None
    repo = P8ResearchRepository(P8_RESEARCH_DB)
    sources, payloads = {}, {}
    for kind, record in (("activity_features", "activity_feature"), ("event_graph", "derived_event"), ("p8_terminal_history_v2", "p8_terminal_outcome_v2")):
        run, sha, records = _latest_records(repo, kind, record)
        sources[kind] = dict(run=run, digest=sha)
        payloads[kind] = records
    start, through = "2021-03-17", cfg["outcome_through"] if args.evaluate else cfg["signal_through"]
    calendar, members = _calendar_membership(MARKET_CONTEXT_DB, start, through)
    prices = qfq_series(BASE, overlay_database=P8_QFQ_DB, start=start, through=through)
    facts = MarketActivityRepository(MARKET_ACTIVITY_DB).latest_facts(start_date=start, through=cfg["signal_through"])
    announcements = load_announcements(base_database=BASE, refresh_directory=ANNOUNCEMENT_REFRESH_DIR, start_date=start, through=cfg["signal_through"])
    stages = load_valuation_stage_map(VALUATION_EPISODE_DB, dates=calendar)
    features = [f for f in payloads["activity_features"] if f["trade_date"] <= cfg["signal_through"]]
    grid, gaps = make_grid(features, facts, prices, calendar, members, stages, announcements, payloads["event_graph"], cfg, evidence)
    episodes = make_episodes(grid, cfg)
    source = dict(config=cfg, sources=sources, grid_digest=digest(grid), episode_digest=digest(episodes),
                  suspension_evidence_digest=digest(evidence),
                  coverage_code_sha=hashlib.sha256((ROOT / "p8_grid_price_coverage.py").read_bytes()).hexdigest(),
                  code_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    inventory = dict(input_digest=digest(source), inputs=source, outcomes_read=False, grid_days=len(grid), episodes=len(episodes),
                     episode_cells=dict(Counter(f"{r['grid']}|{r['active']}" for r in episodes)), gaps=gaps,
                     focus_episodes=sum(r["grid"] == FOCUS and r["active"] for r in episodes),
                     focus_companies=len({r["symbol"] for r in episodes if r["grid"] == FOCUS and r["active"]}),
                     focus_by_year=dict(Counter(r["day"][:4] for r in episodes if r["grid"] == FOCUS and r["active"])),
                     unknown_stage=sum(r["stage"] == "unknown" for r in episodes))
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.evaluate:
        atomic_write_json(args.output / "inventory.json", inventory)
        print(json.dumps({k:v for k,v in inventory.items() if k != "inputs"}, ensure_ascii=False))
        return
    if not args.inventory or json.loads(args.inventory.read_text())["input_digest"] != inventory["input_digest"]:
        raise ValueError("先运行同配置/代码/输入的无结果盘点，再传 --inventory")
    trades = load_trade_states(market_activity_database=MARKET_ACTIVITY_DB, base_database=BASE, start=start, through=through)
    terminals = {r["symbol"]: r["delist_date"] for r in payloads["p8_terminal_history_v2"]}
    benchmark = _benchmarks(MARKET_CONTEXT_DB, start, through)["st_equal_weight_v1"]
    observations = observe(episodes, grid, prices, calendar, benchmark, trades, terminals, cfg)
    table, tests, sensitivity = summarize(observations, cfg)
    report = dict(inventory, outcomes_read=True, table=table, tests=tests, sensitivity=sensitivity,
                  outcome_input_digest=digest(dict(prices=prices, benchmark=benchmark, terminals=terminals,
                                                   trades=sorted((s,d,v) for (s,d),v in trades.items()))),
                  status="exploratory_only", observations=observations)
    atomic_write_json(args.output / "report.json", report)
    pd.DataFrame(table).to_csv(args.output / "grid.csv", index=False)
    (args.output / "index.html").write_text(render(report), encoding="utf-8")
    print(json.dumps(dict(tests=tests, sensitivity=sensitivity, rows=len(table)), ensure_ascii=False))


if __name__ == "__main__":
    main()
