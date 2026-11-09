"""Read-only, reproducible cross-sectional ST rule-change observations.

This is a descriptive daily-member reference, never an investable portfolio or
an estimate of the causal effect of a rule. The old research DBs stay untouched.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import gzip
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import sqlite3
from statistics import mean, median, pstdev

from st_sample_integrity import load_integrity, fixed_gap_note
from canonical_json import digest
from data_refresh import atomic_write_json
from market_calendar import sessions_2026
from settings import BASE_DB, DATA_ROOT, MARKET_ACTIVITY_DB, MARKET_CONTEXT_DB

VERSION = 'st_main_board_regime_comparison_v1'
RULE_DAY = '2026-07-06'
ANCHOR = '2026-07-03'
ROOT = Path(os.environ.get('V8_ST_REGIME_DIR', str(DATA_ROOT / 'local_data/v8_copilot/market_risk/st_regime_comparison')))
from st_regime_themes import build_themes
MAIN_PREFIXES = ('000', '001', '002', '003', '600', '601', '603', '605')
RULE_SOURCES = [
    {'label': '上交所：5%改10%及7月6日生效说明',
     'url': 'https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20260424_10816474.shtml',
     'published_on': '2026-04-24'},
    {'label': '上交所：2026年交易规则发布通知',
     'url': 'https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20260424_10816492.shtml',
     'published_on': '2026-04-24'},
    {'label': '深交所：2026年交易规则发布通知',
     'url': 'https://www.szse.cn/lawrules/rule/trade/t20260424_620190.html',
     'published_on': '2026-04-24'},
]


def finite(v):
    return type(v) in (int, float) and math.isfinite(v)


def main_board(symbol):
    return len(symbol) == 6 and symbol.isdigit() and symbol.startswith(MAIN_PREFIXES)


def quantile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    i = (len(ordered) - 1) * q
    low = math.floor(i)
    return ordered[low] + (ordered[math.ceil(i)] - ordered[low]) * (i - low)


def compounded(values):
    if not values or any(not finite(x) or x <= -100 for x in values):
        return None
    return (math.prod(1 + x / 100 for x in values) - 1) * 100


def db_read(path):
    c = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    c.execute('begin')
    return c


def extract_inputs(*, through='2026-09-03'):
    """Freeze scoped rows, not copies of large SQLite databases."""
    calendar = sessions_2026(date(2026, 5, 6), date.fromisoformat(through))
    if through < '2026-08-28' or through > '2026-09-03':
        raise ValueError('this local extractor owns only the audited through-Sep3 source range')
    m, a, p = db_read(MARKET_CONTEXT_DB), db_read(MARKET_ACTIVITY_DB), db_read(BASE_DB)
    try:
        members = [dict(r) for r in m.execute('select trade_date,symbol,ts_code,name,source,fetched_at from st_membership_daily where trade_date between ? and ? order by trade_date,symbol', (calendar[0], through))]
        benchmarks = [dict(r) for r in m.execute("select benchmark_id,trade_date,close,pct_change,source,fetched_at from benchmark_daily where benchmark_id in ('csi_all_share','csi_2000') and trade_date between ? and ? order by benchmark_id,trade_date", (calendar[0], through))]
        activities = []
        snapshot_refs = []
        for day in calendar:
            snap = a.execute('select snapshot_id,trade_date,row_count,content_digest,fetched_at from activity_snapshots where trade_date=? order by fetched_at desc,snapshot_id desc limit 1', (day,)).fetchone()
            if snap is None:
                raise ValueError(f'missing complete activity snapshot: {day}')
            rows = [json.loads(r[0]) for r in a.execute('select payload_json from market_activity_daily where snapshot_id=? order by symbol', (snap['snapshot_id'],))]
            if len(rows) != snap['row_count'] or any(r['trade_date'] != day for r in rows):
                raise ValueError('snapshot row count or date mismatch')
            snapshot_refs.append(dict(snap))
            for row in rows:
                if main_board(row['symbol']):
                    activities.append({k: row.get(k) for k in ('symbol','trade_date','name','pct_chg','pre_close','close','high','low','volume','amount','turnover_rate_f','suspension_status','terminal_phase_status','up_limit','down_limit','limit_state_conflict','source')})
        fixed = sorted(r['symbol'] for r in members if r['trade_date'] == ANCHOR and main_board(r['symbol']))
        placeholders = ','.join('?' for _ in fixed)
        prices = [dict(r) for r in p.execute(f"select symbol,trade_date,close,source,fetched_at from daily_prices where adjust='qfq' and symbol in ({placeholders}) and trade_date between ? and ? order by symbol,trade_date", (*fixed, calendar[0], through))]
        return {'version': VERSION, 'through': through, 'calendar': calendar, 'members': members,
                'activities': activities, 'benchmarks': benchmarks, 'fixed_prices': prices,
                'activity_snapshots': snapshot_refs,
                'source_tables': [
                    {'path': str(MARKET_CONTEXT_DB.relative_to(DATA_ROOT)), 'tables': ['st_membership_daily','benchmark_daily']},
                    {'path': str(MARKET_ACTIVITY_DB.relative_to(DATA_ROOT)), 'tables': ['activity_snapshots','market_activity_daily']},
                    {'path': str(BASE_DB.relative_to(DATA_ROOT)), 'tables': ['daily_prices'], 'adjust': 'qfq'},
                ]}
    finally:
        m.close(); a.close(); p.close()


def indexed(rows, keys):
    result = {}
    for row in rows:
        key = tuple(row[k] for k in keys)
        if key in result:
            raise ValueError('duplicate source identity')
        result[key] = row
    return result


def daily_observation(members, activity):
    """Do not count suspensions/missing rows as flat returns or limit hits."""
    observed, suspended, missing, terminal = [], [], [], []
    for symbol in sorted(members):
        row = activity.get(symbol)
        if row is None:
            missing.append(symbol)
        elif row['terminal_phase_status'] != 'not_terminal':
            terminal.append(symbol)
        elif row['suspension_status'] == 'suspended':
            suspended.append(symbol)
        elif (row['suspension_status'] != 'trading' or not finite(row['pct_chg'])
              or not finite(row['volume']) or row['volume'] <= 0
              or not finite(row['close']) or row['close'] <= 0):
            missing.append(symbol)
        else:
            observed.append(row)
    returns = [r['pct_chg'] for r in observed]
    # Compare actual rounded price bands, not an approximate ±5.x% threshold:
    # a sub-3-yuan stock can legally exceed 5.1% under the old five-percent rule.
    comparable = [r for r in observed if finite(r['pre_close']) and r['pre_close'] > 0]
    def beyond(row, direction):
        reference = Decimal(str(row['pre_close']))
        tick = Decimal('.01')
        factor = Decimal('1.05') if direction == 'up' else Decimal('.95')
        boundary = (reference*factor).quantize(tick, rounding=ROUND_HALF_UP)
        boundary = max(boundary, reference+tick) if direction == 'up' else min(boundary, reference-tick)
        price = Decimal(str(row['close']))
        return price > boundary if direction == 'up' else price < boundary
    band_share = lambda direction: sum(beyond(r,direction) for r in comparable)/len(comparable)*100 if comparable else None
    denominator = len(observed)
    valid_turnover = [r['turnover_rate_f'] for r in observed if finite(r['turnover_rate_f']) and r['turnover_rate_f'] >= 0]
    share = lambda condition: sum(condition(v) for v in returns) / denominator * 100 if denominator else None
    return {'member_count': len(members), 'observed_count': denominator,
            'coverage_pct': denominator / len(members) * 100 if members else None,
            'suspended': suspended, 'missing': missing, 'terminal_excluded': terminal,
            'return_pct': mean(returns) if returns else None,
            'median_pct': median(returns) if returns else None,
            'p10_pct': quantile(returns, .1), 'p90_pct': quantile(returns, .9),
            'dispersion_pp': quantile(returns, .9) - quantile(returns, .1) if returns else None,
            'positive_pct': share(lambda v: v > 0), 'beyond_old_down_pct': band_share('down'),
            'beyond_old_up_pct': band_share('up'), 'band_comparable_count': len(comparable),
            'median_turnover_pct': median(valid_turnover) if valid_turnover else None,
            'turnover_count': len(valid_turnover),
            'band_basis': 'rounded_previous_close_5pct_with_one_tick_minimum'}


def relation(rows):
    x = [r['market_pct'] for r in rows]
    y = [r['return_pct'] for r in rows]
    if len(x) < 3 or pstdev(x) == 0 or pstdev(y) == 0:
        return {'days': len(x), 'correlation': None, 'beta': None, 'r_squared': None}
    mx, my = mean(x), mean(y)
    cov = mean([(a-mx)*(b-my) for a, b in zip(x, y, strict=True)])
    corr = cov / (pstdev(x)*pstdev(y))
    return {'days': len(x), 'correlation': corr, 'beta': cov / pstdev(x)**2, 'r_squared': corr**2}


def period_metrics(rows):
    valid = [r for r in rows if finite(r['return_pct']) and finite(r['market_pct'])]
    # Never shorten a broken comparison into a convenient successful window.
    complete = len(valid) == len(rows) and len(rows) > 0
    levels = [100.]
    if complete:
        for row in rows:
            levels.append(levels[-1]*(1+row['return_pct']/100))
    peak = 100.
    drawdown = 0.
    for level in levels:
        peak = max(peak, level)
        drawdown = min(drawdown, (level/peak-1)*100)
    conditions = []
    for key, label, test in [('up','大盘上涨日',lambda x:x>0),('down','大盘下跌日',lambda x:x<0),('stress','大盘跌超1%日',lambda x:x<-1)]:
        sub = [r for r in valid if test(r['market_pct'])]
        conditions.append({'key': key, 'label': label, 'days': len(sub),
                           'market_mean_pct': mean(r['market_pct'] for r in sub) if sub else None,
                           'st_mean_pct': mean(r['return_pct'] for r in sub) if sub else None,
                           'mean_excess_pp': mean(r['return_pct']-r['market_pct'] for r in sub) if sub else None,
                           'positive_breadth_pct': mean(r['positive_pct'] for r in sub) if sub else None})
    total = sum(r['observed_count'] for r in rows)
    expected = sum(r['member_count'] for r in rows)
    return {'start': rows[0]['date'], 'through': rows[-1]['date'], 'days': len(rows), 'complete': complete,
            'reference_change_pct': compounded([r['return_pct'] for r in rows]) if complete else None,
            'market_change_pct': compounded([r['market_pct'] for r in rows]) if complete else None,
            'small_cap_change_pct': compounded([r['small_cap_pct'] for r in rows]) if complete else None,
            'daily_volatility_pct': pstdev([r['return_pct'] for r in rows]) if complete else None,
            'mean_absolute_move_pct': mean(abs(r['return_pct']) for r in rows) if complete else None,
            'max_drawdown_pct': drawdown if complete else None,
            'mean_positive_breadth_pct': mean(r['positive_pct'] for r in rows) if complete else None,
            'mean_dispersion_pp': mean(r['dispersion_pp'] for r in rows) if complete else None,
            'beyond_old_down_pct': sum(r['beyond_old_down_pct']*r['band_comparable_count']/100 for r in rows)/sum(r['band_comparable_count'] for r in rows)*100,
            'beyond_old_up_pct': sum(r['beyond_old_up_pct']*r['band_comparable_count']/100 for r in rows)/sum(r['band_comparable_count'] for r in rows)*100,
            'minimum_coverage_pct': min(r['coverage_pct'] for r in rows),
            'member_observations': expected, 'trading_observations': total,
            'suspended_observations': sum(len(r['suspended']) for r in rows),
            'missing_observations': sum(len(r['missing']) for r in rows),
            'terminal_exclusions': sum(len(r['terminal_excluded']) for r in rows),
            'relation': relation(valid), 'conditions': conditions}


def endpoint_trade_state(price, activity):
    """Require evidence of a trade; a carried reference close is not a trade."""
    if price is None:return {'status':'missing_price','reason':'缺参考收盘价'}
    flag=price.get('has_trade');raw_volume=price.get('raw_volume')
    no_trade=flag is False or (finite(raw_volume) and raw_volume<=0)
    positive=flag is True and finite(raw_volume) and raw_volume>0
    if activity:
        suspended=activity.get('suspension_status')=='suspended'
        active=activity.get('suspension_status')=='trading' and finite(activity.get('volume')) and activity['volume']>0
        if (positive and suspended) or (no_trade and active):return {'status':'conflict','reason':'成交标记、成交量与停牌状态有冲突'}
        no_trade=no_trade or suspended
        positive=positive or active
    if no_trade:return {'status':'not_traded','reason':'有参考价但无实际成交'}
    if positive:return {'status':'traded','reason':'当日有成交证据'}
    return {'status':'unknown','reason':'缺少当日成交证据'}


def fixed_observation(inputs, days):
    """Keep every pre-rule member visible; incomplete endpoints stay null."""
    anchor = days[0]['anchor']
    end = days[-1]['date']
    fixed = {r['symbol']: r for r in inputs['members'] if r['trade_date'] == ANCHOR and main_board(r['symbol'])}
    prices = indexed(inputs['fixed_prices'], ('trade_date','symbol'))
    activities = indexed(inputs['activities'], ('trade_date','symbol'))
    current = {r['symbol'] for r in inputs['members'] if r['trade_date'] == end}
    result = []
    integrity = load_integrity(inputs)
    for symbol, member in sorted(fixed.items()):
        first, last = prices.get((anchor,symbol)), prices.get((end,symbol))
        missing_days = [r['date'] for r in days if (r['date'],symbol) not in prices]
        checked, mismatches = 0, 0
        for row in days:
            before, after = prices.get((row['anchor'],symbol)), prices.get((row['date'],symbol))
            act = activities.get((row['date'],symbol))
            if before and after and act and finite(act['pct_chg']) and act['suspension_status']=='trading':
                checked += 1
                if abs((after['close']/before['close']-1)*100-act['pct_chg']) > .06:
                    mismatches += 1
        value = None
        reason = None
        if not first or not last:
            reason = ('起点与期末均缺参考收盘价' if not first and not last else '起点缺参考收盘价，期末有价' if not first else '起点有价，期末缺参考收盘价') + '；未填零或改用其他日期'
        elif mismatches:
            reason = '前复权价格与逐日涨跌幅不一致，待核复权或公司行动'
        elif not all(finite(p['close']) and p['close']>0 for p in (first,last)):
            reason = '起止价格无效'
        else:
            value = (last['close']/first['close']-1)*100
        reference_value=value
        trade_states={'anchor':endpoint_trade_state(first,activities.get((anchor,symbol))),'endpoint':endpoint_trade_state(last,activities.get((end,symbol)))}
        if value is not None and any(r['status']!='traded' for r in trade_states.values()):
            value=None
            reason='；'.join(('起点' if key=='anchor' else '期末')+'：'+r['reason'] for key,r in trade_states.items() if r['status']!='traded')+'；不改用其他日期或填零'
        result.append({'reference_return_pct':reference_value,'endpoint_trade_states':trade_states,'symbol': symbol, 'name': member['name'], 'venue': '上海' if symbol.startswith('6') else '深圳',
                       'risk_label_at_anchor': '*ST' if '*ST' in member['name'].upper() else 'ST',
                       'still_st_at_end': symbol in current, 'return_pct': value,
                       'market_excess_pp': value-compounded([r['market_pct'] for r in days]) if value is not None else None,
                       'missing_quote_days': len(missing_days), 'consistency_days': checked,
                       'consistency_mismatches': mismatches, 'gap': reason,
                       'endpoint_availability': {'anchor_present': first is not None, 'endpoint_present': last is not None},
                       'sample_note': fixed_gap_note(integrity,symbol,anchor,end)})
    valid = [r['return_pct'] for r in result if r['return_pct'] is not None]
    reference = [r['reference_return_pct'] for r in result if r['reference_return_pct'] is not None]
    return {'reference_summary':{'covered':len(reference),'missing':len(result)-len(reference),'median_pct':median(reference) if reference else None,'p10_pct':quantile(reference,.1),'p90_pct':quantile(reference,.9),'positive_pct':sum(x>0 for x in reference)/len(reference)*100 if reference else None},'nontraded_reference_count':sum(r['reference_return_pct'] is not None and r['return_pct'] is None for r in result),** {'anchor': anchor, 'through': end, 'total': len(result), 'covered': len(valid),
            'missing': len(result)-len(valid), 'median_pct': median(valid) if valid else None,
            'p10_pct': quantile(valid,.1), 'p90_pct': quantile(valid,.9),
            'positive_pct': sum(x>0 for x in valid)/len(valid)*100 if valid else None,
            'rows': result,
            'note': '固定7月3日主板ST名单，主分布仅用两端均有成交证据的前复权收盘变化。缺价、无成交、状态不明或冲突都留空，股票仍保留，不填零或改日期。旧参考价分布另列，不当作实际成交端点；完整端点子样本仍有选择偏差。前窗使用未来7月3日名单只作组成核对，价格变化不是个人含息交易收益。'}}


def build(inputs):
    if inputs['version'] != VERSION:
        raise ValueError('wrong input version')
    calendar = inputs['calendar']
    if calendar != sessions_2026(date.fromisoformat(calendar[0]), date.fromisoformat(inputs['through'])):
        raise ValueError('calendar has a missing or extra session')
    members = indexed(inputs['members'], ('trade_date','symbol'))
    activity = indexed(inputs['activities'], ('trade_date','symbol'))
    benchmark = indexed(inputs['benchmarks'], ('benchmark_id','trade_date'))
    daily = []
    for i, day in enumerate(calendar[1:], 1):
        names = {s: r for (d,s),r in members.items() if d == day and main_board(s)}
        if not names:
            raise ValueError('missing historical membership')
        facts = {s: r for (d,s),r in activity.items() if d == day}
        point = daily_observation(names, facts)
        if point['missing'] or point['terminal_excluded'] or point['observed_count']==0:
            raise ValueError(f'unresolved observations prevent whole-window publication: {day}')
        rates = []
        for key in ('csi_all_share','csi_2000'):
            now, before = benchmark.get((key,day)), benchmark.get((key,calendar[i-1]))
            if not now or not before or not finite(now['close']) or not finite(before['close']) or min(now['close'],before['close'])<=0:
                raise ValueError('benchmark calendar incomplete')
            rates.append((now['close']/before['close']-1)*100)
        daily.append({'date': day, 'anchor': calendar[i-1], **point, 'market_pct': rates[0], 'small_cap_pct': rates[1]})
    before = [r for r in daily if r['date'] < RULE_DAY]
    after = [r for r in daily if r['date'] >= RULE_DAY]
    comparisons = []
    for n in (20,40):
        if min(len(before),len(after))<n:
            raise ValueError('not enough same-length windows')
        pre, post = before[-n:], after[:n]
        comparisons.append({'key': str(n), 'label': f'前后各{n}个交易日', 'before': period_metrics(pre),
                            'after': period_metrics(post), 'fixed_before': fixed_observation(inputs,pre),
                            'fixed_after': fixed_observation(inputs,post)})
    comparisons.append({'key': 'all', 'label': '完整已覆盖后窗', 'before': period_metrics(before[-40:]),
                        'after': period_metrics(after), 'fixed_before': fixed_observation(inputs,before[-40:]),
                        'fixed_after': fixed_observation(inputs,after)})
    for comparison in comparisons:
        pre = {r['symbol']: r for r in comparison['fixed_before']['rows']}
        post = {r['symbol']: r for r in comparison['fixed_after']['rows']}
        matched = sorted(s for s in pre if pre[s]['return_pct'] is not None and post[s]['return_pct'] is not None)
        reference_matched=sorted(s for s in pre if pre[s]['reference_return_pct'] is not None and post[s]['reference_return_pct'] is not None)
        comparison['reference_paired']={'count':len(reference_matched),'symbols':reference_matched,'before_median_pct':median(pre[s]['reference_return_pct'] for s in reference_matched) if reference_matched else None,'after_median_pct':median(post[s]['reference_return_pct'] for s in reference_matched) if reference_matched else None}
        comparison['paired'] = {'count': len(matched), 'symbols': matched,
                                'before_median_pct': median(pre[s]['return_pct'] for s in matched) if matched else None,
                                'after_median_pct': median(post[s]['return_pct'] for s in matched) if matched else None}
    levels = {'st': 100., 'market': 100., 'small': 100.}
    paths = [{'date': calendar[0], 'st': 100., 'market': 100., 'small': 100.}]
    for row in daily:
        for key, field in [('st','return_pct'),('market','market_pct'),('small','small_cap_pct')]:
            levels[key] *= 1+row[field]/100
        paths.append({'date': row['date'], **levels})
    baseline = {r['symbol'] for r in inputs['members'] if r['trade_date']==ANCHOR and main_board(r['symbol'])}
    endpoint = {r['symbol'] for r in inputs['members'] if r['trade_date']==inputs['through'] and main_board(r['symbol'])}
    return {'version': VERSION, 'availability': 'available', 'rule_day': RULE_DAY, 'announcement_day': '2026-04-24',
            'start': calendar[0], 'through': inputs['through'], 'daily': daily, 'path': paths, 'comparisons': comparisons,
            'themes': build_themes(inputs, daily),
            'universe': {'anchor_members': len(baseline), 'endpoint_members': len(endpoint),
                         'entrants': sorted(endpoint-baseline), 'exits': sorted(baseline-endpoint),
                         'distinct_main_board_members': len({r['symbol'] for r in inputs['members'] if main_board(r['symbol'])}),
                         'excluded_board_member_days': sum(not main_board(r['symbol']) for r in inputs['members'])},
            'sources': RULE_SOURCES + [
                {'label': 'Tushare逐日ST名单口径', 'url': 'https://tushare.pro/document/2?doc_id=397'},
                {'label': 'Tushare日线口径（不复权）', 'url': 'https://tushare.pro/document/2?doc_id=27'},
                {'label': 'Tushare指数日线口径', 'url': 'https://tushare.pro/document/2?doc_id=95'}],
            'limitations': [
                f"完整逐日成员及成交资料截至{inputs['through']}；截止日后行情不纳入，重读快照不会触发补采。",
                *(['本轮行情来自用户指定的Tushare兼容服务，非官方直连；已核返回身份、日期、算术和原字节摘要，尚未逐笔双源独立核对全部行情。旧活动标签与正成交报价冲突时采用实际报价，不回填旧库。'] if inputs.get('refresh_provenance') else []),
                '主图每日按当日Tushare主板ST名单，对有成交成员的提供方日涨跌幅取等权均值并连乘。停牌从当天收益分母排除，未填零；这是风格参考，不能交易复制。',
                '成员变动会改变每天分母；当日名单含当天已生效事项，不能作为前一晚可执行信号。Tushare历史名单尚未逐日对照沪深交易所全部原公告。',
                '大盘用中证全指，小盘风格用中证2000。涨跌相关、回归斜率和同日超额都不是大盘造成的贡献，也不是规则净因果；季报、摘帽、退市与风格变化仍会混杂。',
                '4月24日已公布规则，5月至7月规则前窗也可能包含预期交易；前后比较不等于没有规则预期的对照实验。',
                '突破旧边界按当日参考前收盘价×1.05或0.95、分币四舍五入且至少一分的价格边界判断；低价股合法的5.1%以上变动不会误算。突破旧边界不等于10%封板，旧连板个数不能直接衡量赚钱能力。',
                '波动与分化来自同一批交易日，只有一次制度事件。重叠20/40日窗、不同公司或重复追问不算独立制度样本；经验暂不自动晋级。',
            ], 'input_digest': digest(inputs)}


def publish(inputs, *, root=ROOT):
    data = build(inputs)
    encoded = json.dumps(inputs, ensure_ascii=False, sort_keys=True, separators=(',',':')).encode()
    root.mkdir(parents=True, exist_ok=True)
    source = 'inputs-' + sha256(encoded).hexdigest() + '.json.gz'
    if not (root/source).exists():
        (root/source).write_bytes(gzip.compress(encoded, mtime=0))
    payload = {**data, 'generated_at': datetime.now(timezone.utc).isoformat(), 'source_asset': source,
               'processor_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
               'themes_processor_sha256': sha256(Path(__file__).with_name('st_regime_themes.py').read_bytes()).hexdigest(),
               'integrity_processor_sha256': sha256(Path(__file__).with_name('st_sample_integrity.py').read_bytes()).hexdigest(),
               'membership_processor_sha256': sha256(Path(__file__).with_name('st_member_transitions.py').read_bytes()).hexdigest(),
               'company_risk_cases_processor_sha256':sha256(Path(__file__).with_name('st_company_risk_cases.py').read_bytes()).hexdigest(),
               'initial_status_processor_sha256':sha256(Path(__file__).with_name('st_initial_status_coverage.py').read_bytes()).hexdigest(),
               'huke_date_proof_processor_sha256':sha256(Path(__file__).with_name('st_huke_date_proof.py').read_bytes()).hexdigest(),
               'official_pdf_audit_processor_sha256':sha256(Path(__file__).with_name('st_official_pdf_audit.py').read_bytes()).hexdigest(),
               'announcement_reading_processor_sha256':sha256(Path(__file__).with_name('st_announcement_reading.py').read_bytes()).hexdigest(),
               'baoxin_holding_bridge_processor_sha256':sha256(Path(__file__).with_name('st_baoxin_holding_bridge.py').read_bytes()).hexdigest(),
               'baoxin_auction_links_processor_sha256':sha256(Path(__file__).with_name('st_baoxin_auction_links.py').read_bytes()).hexdigest(),
               'disclosure_chains_processor_sha256':sha256(Path(__file__).with_name('st_disclosure_chains.py').read_bytes()).hexdigest(),
               'experience_case_audit_processor_sha256':sha256(Path(__file__).with_name('st_experience_case_audit.py').read_bytes()).hexdigest(),
               'price_band_audit_processor_sha256':sha256(Path(__file__).with_name('st_price_band_audit.py').read_bytes()).hexdigest(),
               'removal_action_basis_processor_sha256':sha256(Path(__file__).with_name('st_removal_action_basis.py').read_bytes()).hexdigest(),
               'removal_era_comparison_processor_sha256':sha256(Path(__file__).with_name('st_removal_era_comparison.py').read_bytes()).hexdigest(),
               'pre_rule_membership_processor_sha256':sha256(Path(__file__).with_name('st_pre_rule_membership.py').read_bytes()).hexdigest(),
               'dynamic_reference_audit_processor_sha256':sha256(Path(__file__).with_name('st_dynamic_reference_audit.py').read_bytes()).hexdigest(),
               'exit_quote_replay_processor_sha256':sha256(Path(__file__).with_name('st_exit_quote_replay.py').read_bytes()).hexdigest(),
               'remaining_basis_processor_sha256':sha256(Path(__file__).with_name('st_remaining_basis.py').read_bytes()).hexdigest(),
               'dividend_basis_processor_sha256':sha256(Path(__file__).with_name('st_dividend_basis.py').read_bytes()).hexdigest(),
               'fixed_quote_audit_processor_sha256':sha256(Path(__file__).with_name('st_fixed_quote_audit.py').read_bytes()).hexdigest(),
               'tianji_conditions_processor_sha256':sha256(Path(__file__).with_name('st_tianji_conditions.py').read_bytes()).hexdigest(),
               'shenwu_execution_processor_sha256':sha256(Path(__file__).with_name('st_shenwu_execution.py').read_bytes()).hexdigest(),
               'strong_removal_cases_processor_sha256':sha256(Path(__file__).with_name('st_strong_removal_cases.py').read_bytes()).hexdigest(),
               'juewei_adjustment_processor_sha256':sha256(Path(__file__).with_name('st_juewei_adjustment.py').read_bytes()).hexdigest(),
               'removal_cohort_processor_sha256':sha256(Path(__file__).with_name('st_removal_cohort.py').read_bytes()).hexdigest(),
               'removal_followup_processor_sha256':sha256(Path(__file__).with_name('st_removal_followup.py').read_bytes()).hexdigest(),
               'case_price_processor_sha256':sha256(Path(__file__).with_name('st_case_price_crosscheck.py').read_bytes()).hexdigest(),
               'halt_price_processor_sha256': sha256(Path(__file__).with_name('st_halt_price_crosscheck.py').read_bytes()).hexdigest(),
               'halt_stages_processor_sha256': sha256(Path(__file__).with_name('st_halt_stages.py').read_bytes()).hexdigest(),
               'membership_audit_processor_sha256': sha256(Path(__file__).with_name('st_membership_audit.py').read_bytes()).hexdigest(),
               'label_processor_sha256': sha256(Path(__file__).with_name('st_label_changes.py').read_bytes()).hexdigest(),
               'stock_price_check_processor_sha256': sha256(Path(__file__).with_name('st_stock_price_crosscheck.py').read_bytes()).hexdigest(),
               'index_crosscheck_processor_sha256': sha256(Path(__file__).with_name('st_index_crosscheck.py').read_bytes()).hexdigest(),
               'entry_processor_sha256': sha256(Path(__file__).with_name('st_member_entries.py').read_bytes()).hexdigest(),
               'source_tables': inputs['source_tables']}
    payload['content_digest'] = digest(payload)
    atomic_write_json(root/'snapshots'/(payload['content_digest']+'.json'),payload)
    atomic_write_json(root/'current.json',payload)
    return payload


def load(root=ROOT):
    try:
        value = json.loads((root/'current.json').read_text())
        if (value['version']!=VERSION or digest({k:v for k,v in value.items() if k!='content_digest'})!=value['content_digest']
                or value['processor_sha256']!=sha256(Path(__file__).read_bytes()).hexdigest()
                or value.get('themes_processor_sha256')!=sha256(Path(__file__).with_name('st_regime_themes.py').read_bytes()).hexdigest()
                or value.get('integrity_processor_sha256')!=sha256(Path(__file__).with_name('st_sample_integrity.py').read_bytes()).hexdigest()
                or value.get('membership_processor_sha256')!=sha256(Path(__file__).with_name('st_member_transitions.py').read_bytes()).hexdigest()
                or value.get('company_risk_cases_processor_sha256')!=sha256(Path(__file__).with_name('st_company_risk_cases.py').read_bytes()).hexdigest()
                or value.get('initial_status_processor_sha256')!=sha256(Path(__file__).with_name('st_initial_status_coverage.py').read_bytes()).hexdigest()
                or value.get('huke_date_proof_processor_sha256')!=sha256(Path(__file__).with_name('st_huke_date_proof.py').read_bytes()).hexdigest()
                or value.get('official_pdf_audit_processor_sha256')!=sha256(Path(__file__).with_name('st_official_pdf_audit.py').read_bytes()).hexdigest()
                or value.get('announcement_reading_processor_sha256')!=sha256(Path(__file__).with_name('st_announcement_reading.py').read_bytes()).hexdigest()
                or value.get('baoxin_holding_bridge_processor_sha256')!=sha256(Path(__file__).with_name('st_baoxin_holding_bridge.py').read_bytes()).hexdigest()
                or value.get('baoxin_auction_links_processor_sha256')!=sha256(Path(__file__).with_name('st_baoxin_auction_links.py').read_bytes()).hexdigest()
                or value.get('disclosure_chains_processor_sha256')!=sha256(Path(__file__).with_name('st_disclosure_chains.py').read_bytes()).hexdigest()
                or value.get('experience_case_audit_processor_sha256')!=sha256(Path(__file__).with_name('st_experience_case_audit.py').read_bytes()).hexdigest()
                or value.get('price_band_audit_processor_sha256')!=sha256(Path(__file__).with_name('st_price_band_audit.py').read_bytes()).hexdigest()
                or value.get('removal_action_basis_processor_sha256')!=sha256(Path(__file__).with_name('st_removal_action_basis.py').read_bytes()).hexdigest()
                or value.get('removal_era_comparison_processor_sha256')!=sha256(Path(__file__).with_name('st_removal_era_comparison.py').read_bytes()).hexdigest()
                or value.get('pre_rule_membership_processor_sha256')!=sha256(Path(__file__).with_name('st_pre_rule_membership.py').read_bytes()).hexdigest()
                or value.get('dynamic_reference_audit_processor_sha256')!=sha256(Path(__file__).with_name('st_dynamic_reference_audit.py').read_bytes()).hexdigest()
                or value.get('exit_quote_replay_processor_sha256')!=sha256(Path(__file__).with_name('st_exit_quote_replay.py').read_bytes()).hexdigest()
                or value.get('remaining_basis_processor_sha256')!=sha256(Path(__file__).with_name('st_remaining_basis.py').read_bytes()).hexdigest()
                or value.get('dividend_basis_processor_sha256')!=sha256(Path(__file__).with_name('st_dividend_basis.py').read_bytes()).hexdigest()
                or value.get('fixed_quote_audit_processor_sha256')!=sha256(Path(__file__).with_name('st_fixed_quote_audit.py').read_bytes()).hexdigest()
                or value.get('tianji_conditions_processor_sha256')!=sha256(Path(__file__).with_name('st_tianji_conditions.py').read_bytes()).hexdigest()
                or value.get('shenwu_execution_processor_sha256')!=sha256(Path(__file__).with_name('st_shenwu_execution.py').read_bytes()).hexdigest()
                or value.get('strong_removal_cases_processor_sha256')!=sha256(Path(__file__).with_name('st_strong_removal_cases.py').read_bytes()).hexdigest()
                or value.get('juewei_adjustment_processor_sha256')!=sha256(Path(__file__).with_name('st_juewei_adjustment.py').read_bytes()).hexdigest()
                or value.get('removal_cohort_processor_sha256')!=sha256(Path(__file__).with_name('st_removal_cohort.py').read_bytes()).hexdigest()
                or value.get('removal_followup_processor_sha256')!=sha256(Path(__file__).with_name('st_removal_followup.py').read_bytes()).hexdigest()
                or value.get('case_price_processor_sha256')!=sha256(Path(__file__).with_name('st_case_price_crosscheck.py').read_bytes()).hexdigest()
                or value.get('halt_price_processor_sha256')!=sha256(Path(__file__).with_name('st_halt_price_crosscheck.py').read_bytes()).hexdigest()
                or value.get('halt_stages_processor_sha256')!=sha256(Path(__file__).with_name('st_halt_stages.py').read_bytes()).hexdigest()
                or value.get('membership_audit_processor_sha256')!=sha256(Path(__file__).with_name('st_membership_audit.py').read_bytes()).hexdigest()
                or value.get('label_processor_sha256')!=sha256(Path(__file__).with_name('st_label_changes.py').read_bytes()).hexdigest()
                or value.get('stock_price_check_processor_sha256')!=sha256(Path(__file__).with_name('st_stock_price_crosscheck.py').read_bytes()).hexdigest()
                or value.get('index_crosscheck_processor_sha256')!=sha256(Path(__file__).with_name('st_index_crosscheck.py').read_bytes()).hexdigest()
                or value.get('entry_processor_sha256')!=sha256(Path(__file__).with_name('st_member_entries.py').read_bytes()).hexdigest()):
            raise ValueError('snapshot or processor binding changed')
        source = value['source_asset']
        if not source.startswith('inputs-') or not source.endswith('.json.gz') or Path(source).name != source:
            raise ValueError('invalid source asset')
        encoded = gzip.decompress((root/source).read_bytes())
        if sha256(encoded).hexdigest() != source[7:-8] or digest(json.loads(encoded)) != value['input_digest']:
            raise ValueError('source binding changed')
        return value
    except (OSError, ValueError, KeyError, TypeError):
        return {'availability': 'unavailable', 'message': '横向复盘快照尚未生成或校验未通过；未沿用旧数值。'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT)
    parser.add_argument('--replay-input',type=Path)
    args = parser.parse_args()
    inputs = json.loads(gzip.decompress(args.replay_input.read_bytes())) if args.replay_input else extract_inputs()
    value = publish(inputs,root=args.output)
    print(json.dumps({'availability': value['availability'], 'through': value['through'], 'universe': value['universe'],
                      'content_digest': value['content_digest']},ensure_ascii=False))


if __name__=='__main__':
    main()
