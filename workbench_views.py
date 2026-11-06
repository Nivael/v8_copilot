"""Small, published reading views; deep source verification stays off the first request."""
from __future__ import annotations

import argparse
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from threading import Lock
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from canonical_json import digest
from case_research_scopes import OUTPUT as RUN_SCOPES, current_company_runs
from data_refresh import atomic_write_json
from settings import DATA_ROOT, EXPERIENCE_REPOSITORY_DB, RESEARCH_RUN_LEDGER_DB

VERSION = 'workbench_reading_view_v1'
OUTPUT = DATA_ROOT / 'local_data/v8_copilot/workbench_views'
MARKET_ROOT = DATA_ROOT / 'local_data/v8_copilot/market_risk'
ETF_NAMES = {
    '510300.SH': '华泰柏瑞沪深300ETF', '510310.SH': '易方达沪深300ETF',
    '510330.SH': '华夏沪深300ETF', '159919.SZ': '嘉实沪深300ETF',
    '510500.SH': '南方中证500ETF', '159922.SZ': '嘉实中证500ETF',
    '512100.SH': '南方中证1000ETF', '159845.SZ': '华夏中证1000ETF',
}
# Explicit owner watchlist; comparison mentions alone do not add companies.
WATCHED = ('603398.SH', '600363.SH', '002667.SZ', '688053.SH')
WATCH_LABELS={'603398.SH':'沐邦高科','600363.SH':'联创光电','002667.SZ':'威领股份','688053.SH':'思科瑞'}
WATCH_ALIASES={'603398.SH':('沐邦',),'600363.SH':('联光','联创光电'),'002667.SZ':('威领',),'688053.SH':('思科瑞',)}
CATEGORY_NAMES = ('重整进程', '市场与价格', '历史先例', '风险条件', '证据判断', '表达与复盘')
CATEGORIES = {
    'EXP-E6A0A3C110D74FE7A6DF': '重整进程', 'EXP-D891F04538BD671515FF': '重整进程',
    'EXP-3EF25D62ECE7A4453211': '市场与价格', 'EXP-9192C8C1A3DBE188C75F': '市场与价格',
    'EXP-EF92B88B66DCC4ECCB68': '历史先例', 'EXP-6035511EF7BD09AED0B3': '风险条件',
    'EXP-74E679332AEE94ADC122': '证据判断', 'EXP-0C78ABF99736BAB325B2': '证据判断',
    'EXP-F0A962407D4FF75D3ACE': '证据判断', 'EXP-D9A1B99AA6A1DF488296': '表达与复盘',
}


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    result = Decimal(str(value))
    return float(result) if result.is_finite() else None


def change(first, last):
    a, b = number(first), number(last)
    return (b / a - 1) * 100 if a is not None and b is not None and a > 0 and b > 0 else None


def pct(value):
    return '待更新' if value is None else f'{value:+.2f}%'


def instant(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('undated research or publication time')
    return result


def series(points, start, end, field='close'):
    selected = [p for p in points if start <= p['date'] <= end]
    dates = [p['date'] for p in selected]
    if not selected or dates != sorted(set(dates)) or dates[0] != start or dates[-1] != end:
        return []
    values = [number(p[field]) for p in selected]
    if any(v is None or v <= 0 for v in values):
        return []
    return [{'date': p['date'], 'value': v, 'level': v / values[0] * 100} for p, v in zip(selected, values, strict=True)]


def market_view(data):
    """Descriptive reading, not a calibrated probability or a cash-flow claim."""
    period = data.get('recent_window') or {}
    if data.get('status') != 'observed_snapshot' or period.get('availability') != 'defined':
        return {'availability': 'unavailable', 'headline': '最近的市场判断正在更新', 'as_of': data.get('requested_through'), 'chart': []}
    start, end = period['start'], period['end']
    index = next((i for i in data['indices'] if i['code'] == '000985.CSI' and i['through'] == end), None)
    path = series(index['path'], start, end) if index else []
    if not path or len(path) != period['sessions'] + 1 or period.get('calendar') and [p['date'] for p in path] != period['calendar']:
        return {'availability': 'unavailable', 'headline': '大盘走势尚未齐备', 'as_of': end, 'chart': []}
    dates = [p['date'] for p in path]
    recent = change(path[0]['value'], path[-1]['value'])
    latest = change(path[-2]['value'], path[-1]['value']) if len(path) > 1 else None
    month, week = number(index.get('return_20d_pct')), number(index.get('return_5d_pct'))
    from market_price_reading import price_judgment
    headline, stance = price_judgment(latest, week, month)
    chart = [{'key': 'market', 'name': '大盘 · 中证全指', 'points': path, 'change_pct': recent}]
    st = data.get('st_reconstruction') or {}
    membership_confirmation = (st.get('daily_close_extension') or {}).get('membership_confirmation')
    st_path = series([{'date': p['date'], 'close': p['all']['close']} for p in st.get('points', [])], start, end)
    if st.get('availability') != 'reconstructed' or [p['date'] for p in st_path] != dates:
        st_path = []
    st_change = change(st_path[0]['value'], st_path[-1]['value']) if st_path else None
    if st_path:
        chart.append({'key': 'st', 'name': 'ST参考指数', 'points': st_path, 'change_pct': st_change})
    latest_breadth = next((p['all'] for p in (data.get('combined_breadth_history') or {}).get('points', []) if p['date'] == end), None)
    advancing_pct = (latest_breadth['advancing'] / latest_breadth['observed_trading_stocks'] * 100
                     if latest_breadth and latest_breadth.get('observed_trading_stocks', 0) > 0 else None)
    why = [{'title': '一次反弹，还没有收回近月跌幅' if month is not None and month < 0 and latest and latest > 0 else '先看短中期是否同向',
            'text': f'{end}大盘涨跌{pct(latest)}；最近5个交易日{pct(week)}，最近20个交易日{pct(month)}。',
            'source_label': '中证全指原始来源', 'source_url': index['source_url']}]
    if st_change is not None:
        relative = st_change - recent
        st_summary = f'近两个月ST参考{pct(st_change)}，大盘{pct(recent)}；ST比大盘多跌{abs(relative):.2f}个百分点。' if relative < 0 else f'近两个月ST参考{pct(st_change)}，相对大盘高{relative:.2f}个百分点。'
        why.append({'title': 'ST还弱于大盘' if relative < 0 else 'ST相对大盘更强', 'text': st_summary,
                    'source_label': 'ST参考的来源与算法', 'source_url': '/market/evidence#st-reference'})
    else:
        st_summary = 'ST同窗参考正在更新。'
    source_notes = []
    if membership_confirmation is not None:
        source_notes.append({'title': 'ST收盘分类已交叉核对', 'text': membership_confirmation['note'],
                    'source_label': '深交所风险警示名单原文',
                    'source_url': 'http://www.szse.cn/disclosure/listed/warn/index.html'})
    funds = []
    for fund in data.get('etfs', []):
        window = fund.get('windows', {}).get('recent') or {}
        value = number(window.get('share_change_pct'))
        if window.get('window_start') == start and window.get('window_end') == end and value is not None:
            funds.append({'code': fund['code'], 'name': ETF_NAMES.get(fund['code'], fund.get('name') or fund['code']),
                          'group': fund['group'], 'share_change_pct': value,
                          'cash_estimate_yuan': number(window.get('estimated_net_subscription_yuan')),
                          'cash_estimate_ready': window.get('flow_estimate_ready') is True})
    up, down = sum(f['share_change_pct'] > 0 for f in funds), sum(f['share_change_pct'] < 0 for f in funds)
    if funds and up == len(funds):
        etf_headline = f'这{len(funds)}只ETF份额都在增加，未出现份额普遍撤出的迹象'
    elif funds and down == len(funds):
        etf_headline = f'这{len(funds)}只ETF份额都在减少，值得继续跟踪'
    elif funds and up == down == 0:
        etf_headline = f'这{len(funds)}只ETF公布份额没有变化'
    elif funds:
        etf_headline = f'ETF份额出现分化：{up}只增加、{down}只减少'
    else:
        etf_headline = 'ETF份额数据正在更新'
    cash_ready = (len(funds) == len(ETF_NAMES) and {f['code'] for f in funds} == set(ETF_NAMES)
                  and all(f['cash_estimate_ready'] and f['cash_estimate_yuan'] is not None for f in funds))
    return {'availability': 'available', 'as_of': end, 'start': start, 'headline': headline, 'stance': stance,
            'summary': f'大盘最近20日{pct(month)}。{st_summary}',
            'metrics': {'day_change_pct': latest, 'five_day_change_pct': week, 'twenty_day_change_pct': month,
                        'period_change_pct': recent, 'st_change_pct': st_change, 'advancing_pct': advancing_pct},
            'chart': chart, 'why': why, **({'source_notes': source_notes} if source_notes else {}),
            'watch_next': ['反弹能否延续到5日、20日走势改善', 'ST能否不再落后大盘'],
            'etf': {'headline': etf_headline, 'funds': funds, 'increasing': up, 'decreasing': down,
                    'cash_estimate_yuan': sum(f['cash_estimate_yuan'] for f in funds) if cash_ready else None,
                    'interpretation': '价格下跌与ETF份额增加可以同时发生。这组样本的份额变化，不支持把本轮下跌简单说成ETF普遍撤出。' if funds and up == len(funds) else '把ETF份额的方向与价格方向放在一起看；两者相互印证或背离，含义不同。',
                    'how_to_read': '份额是基金发行的份数。净申购金额还需要核对折算、登记范围和修订；这里不会把份额增减直接换名为现金流入流出。'},
            'reading_note': '风险判断是根据已发生的短中期走势作出的定性解读，不是风险概率或经过校准的预警分数。图中同一起点比较，ST参考为自建样本价格参考，编制和原始来源可展开查看。'
                            + (('最新交易日以两所完整收盘和独立名单交叉核对后续接，名单实际读取于' + membership_confirmation['observed_on'] + '，停牌不补零收益。')
                               if membership_confirmation is not None else
                               ('最新交易日以两所完整收盘和当日名单核对后续接，停牌不补零收益。' if data.get('reading_update') else '')),
            'parameter_version': data['parameter_version'], 'source_snapshot_digest': data['snapshot_digest']}


def watch_basis(data, symbol, *, root=MARKET_ROOT):
    if symbol.endswith('.SZ'):
        return szse_watch_basis(data, symbol, root=root)
    if not symbol.endswith('.SH') or data.get('sse_history_archive', {}).get('availability') != 'observed':
        return {'symbol': symbol, 'availability': 'unavailable'}
    archive = root / 'sse_history_archive'; pointer = json.loads((archive / 'current.json').read_text())
    if digest({k: v for k, v in pointer.items() if k != 'content_digest'}) != pointer['content_digest'] or pointer['content_digest'] != data['sse_history_archive']['content_digest']:
        raise ValueError('watch quote not bound to the verified market archive')
    capture = archive / 'sources' / pointer['input_digest']
    index = json.loads((capture / 'full_prices/complete.json').read_text())
    ref, = [r for r in index['source_refs'] if r['code'] == symbol[:6]]
    raw = (capture / 'full_prices' / (ref['sha256'] + '.raw')).read_bytes()
    if sha256(raw).hexdigest() != ref['sha256'] or len(raw) != ref['bytes']:
        raise ValueError('watch quote original changed')
    payload = json.loads(raw, parse_float=Decimal)
    if payload['code'] != symbol[:6] or ref['params'] != {'select': 'date,close,prevClose,chg_rate,volume,amount', 'begin': -126, 'end': -1, 'period': 'day'}:
        raise ValueError('watch quote identity or fields changed')
    total, begin, finish = payload['total'], payload['begin'], payload['end']
    if any(type(v) is not int for v in (total, begin, finish)) or total <= 0 or finish != total or begin != max(0, total - 125) or len(payload['kline']) != finish - begin:
        raise ValueError('watch quote pagination incomplete')
    end = data['requested_through']; records = []
    fetched = instant(ref['observed_at']).astimezone(ZoneInfo('Asia/Shanghai'))
    seen = []
    for row in payload['kline']:
        if not isinstance(row,list) or len(row)!=6 or type(row[0]) is not int:
            raise ValueError('watch quote columns changed')
        day = datetime.strptime(str(row[0]), '%Y%m%d').date().isoformat()
        seen.append(day)
        if day > fetched.date().isoformat():
            raise ValueError('future watch quote')
        # The saved response contains an intraday 11-05 row. A later page visit
        # must never turn a quote captured before the close into a final close.
        if day > end or day > fetched.date().isoformat() or day == fetched.date().isoformat() and fetched.hour < 15:
            continue
        close, previous = number(row[1]), number(row[2])
        volume, amount = number(row[4]), number(row[5])
        if volume is None or amount is None or min(volume,amount)<0 or (volume==0)!=(amount==0):
            raise ValueError('invalid watch quote activity')
        if volume==0:
            records.append({'date':day,'close':None,'previous_close':None,'is_trading':False})
            continue
        if close is None or previous is None or min(close,previous)<=0 or number(row[3]) is None or abs((close/previous-1)*100-float(row[3]))>.015:
            raise ValueError('invalid watch price/reference')
        records.append({'date': day, 'close': close, 'previous_close': previous,'is_trading':True})
    if not records or seen != sorted(set(seen)) or records[-1]['date'] != end:
        raise ValueError('watch quote dates incomplete')
    gap_review=data.get('sse_gap_review') or {}
    if (gap_review.get('availability') in ('reviewed','partial') and gap_review.get('archive_digest')==data['sse_history_archive']['content_digest']):
        existing={p['date'] for p in records}
        for episode in gap_review.get('episodes',[]):
            if episode['symbol']==symbol[:6] and episode.get('interval_closed') is True and episode.get('unresolved_missing_days')==0:
                for day in episode['window_days']:
                    if day not in existing and records[0]['date']<=day<=end:
                        records.append({'date':day,'close':None,'previous_close':None,'is_trading':False,'price_status':'verified_suspension'})
                        existing.add(day)
        records.sort(key=lambda p:p['date'])
    name = next((r['name'] for r in data.get('exchange_risk_membership', {}).get('rows', []) if r['ts_code'] == symbol), symbol)
    return {'availability': 'available', 'symbol': symbol, 'name': name, 'as_of': end, 'prices': records,
            'source_url': ref['url'] + '?' + urlencode(ref['params']), 'source_label':'上交所原始行情',
            'source_observed_at': ref['observed_at'], 'raw_sha256': ref['sha256']}


def szse_watch_basis(data, symbol, *, root=MARKET_ROOT):
    import market_breadth_history as history
    source=data.get('breadth_history') or {}
    if source.get('availability')!='observed':
        return {'symbol':symbol,'availability':'unavailable'}
    directory=root/'public_breadth_history';key=source['content_digest']
    frozen=json.loads((directory/'snapshots'/(key+'.json')).read_text())
    if (digest({k:v for k,v in frozen.items() if k!='content_digest'})!=key or frozen['content_digest']!=key
        or frozen['processor_digest']!=history.PROCESSOR_DIGEST or history.processor_digest()!=history.PROCESSOR_DIGEST
        or frozen['through']!=data['requested_through']):
        raise ValueError('watch history not bound to the verified market source')
    records=[];observed=[];refs=[];name=None;now=datetime.now(timezone.utc)
    for day in frozen['calendar']:
        daily=history._read_day(directory,frozen['daily_snapshots'][day],day,now,check_raw=True)
        row,=[r for r in daily['block']['rows'] if r['ts_code']==symbol]
        records.append({'date':day,'close':row['last'] if row['is_trading'] else None,
                        'previous_close':row['prev_close'] if row['is_trading'] else None,'is_trading':row['is_trading']})
        name=row['security_name'];observed.append(daily['fetched_at']);refs.extend(daily['responses'])
    if not records or [p['date'] for p in records]!=sorted(set(frozen['calendar'])):
        raise ValueError('watch history calendar incomplete')
    last=refs[-1]
    return {'availability':'available','symbol':symbol,'name':name,'as_of':frozen['through'],'prices':records,
            'source_url':last['url']+'?'+urlencode(last['params']),'source_label':'深交所历史收盘日表',
            'source_observed_at':max(observed),'source_snapshot_digest':key}


def rows(path, query):
    if not path.is_file():
        return []
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(r) for r in connection.execute(query)]


def learning_view(packet, *, experience_db=EXPERIENCE_REPOSITORY_DB, ledger_db=RESEARCH_RUN_LEDGER_DB, reviews_dir=OUTPUT / 'case_reviews', latest_quotes=(), run_scopes_path=RUN_SCOPES / 'current.json'):
    methods = []
    for row in rows(experience_db, 'select experience_id,status,payload_json from experiences order by created_at desc'):
        value = json.loads(row['payload_json'])
        if (value['experience_id'], value['status']) != (row['experience_id'], row['status']):
            raise ValueError('experience metadata changed')
        if row['status'] not in ('accepted', 'candidate'):
            continue
        methods.append({'id': value['experience_id'], 'title': value['title'], 'summary': value['value_summary'],
                        'category': CATEGORIES.get(value['experience_id'], '表达与复盘' if value['experience_type']=='presentation_rule' else '待分类'), 'status': value['status'],
                        'when_to_use': value['trigger_conditions'], 'source_run_refs': value['source_run_refs']})
    runs = rows(ledger_db, 'select run_id,question_text,object_refs_json,final_answer,experience_hits_json,source_freshness_json,completed_at from research_runs order by completed_at desc')
    runs = current_company_runs(runs, path=run_scopes_path)
    from research_corrections import corrected_run_ids
    corrected = corrected_run_ids(ledger_db=ledger_db)
    runs = [run for run in runs if run['run_id'] not in corrected]
    cases = []
    for basis in packet.get('watch_bases', []):
        symbol = basis['symbol']; code = symbol[:6]
        history = [r for r in runs if re.search(r'(?<!\d)' + code + r'(?!\d)', r['object_refs_json'])
                   or any(alias in r['question_text'] for alias in WATCH_ALIASES.get(symbol,()))]
        history.sort(key=lambda r: instant(r['completed_at']), reverse=True)
        case = {**basis, 'research_count': len(history), 'history': [], 'review': None}
        latest=next((quote for quote in latest_quotes if quote['symbol']==symbol and quote['availability']=='available'
                     and quote['as_of']>=basis.get('as_of','')),None)
        if latest and latest['as_of']==basis.get('as_of'):
            closing=(basis.get('prices') or [{}])[-1]
            if (not closing.get('is_trading',True) or closing.get('date')!=latest['as_of']
                or number(closing.get('close'))!=number(latest.get('close'))
                or number(closing.get('previous_close'))!=number(latest.get('previous_close'))):
                latest=None
        if latest:
            case['latest_quote']={key:latest[key] for key in ('as_of','close','day_change_pct','five_day_change_pct','twenty_day_change_pct','stage')}
            case['name']=latest['name']
            case['current_observation']=latest.get('note')
            case['last_close']=latest['close'];case['day_change_pct']=latest['day_change_pct']
        for run in history[:4]:
            case['history'].append({'run_id': run['run_id'], 'completed_at': run['completed_at'],
                                    'judgment': run['final_answer'].split('\n\n')[0], 'full_answer': run['final_answer'],
                                    'experience_hits': json.loads(run['experience_hits_json']), 'source_freshness': json.loads(run['source_freshness_json'])})
        if basis['availability'] == 'available':
            prices = basis['prices']; start = packet['market'].get('start'); current = prices[-1]
            anchor_prices=prices
            if latest and latest['as_of']>basis.get('as_of',''):
                current={'date':latest['as_of'],'close':latest['close'],'previous_close':latest['previous_close'],'is_trading':True}
                anchor_prices=[*prices,current]
            period_prices = [p for p in prices if start and p['date'] >= start]
            case['last_close'] = current['close']; case['day_change_pct'] = change(current['previous_close'], current['close'])
            expected_dates=[p['date'] for p in packet['market'].get('chart',[{'points':[]}])[0]['points']]
            complete=([p['date'] for p in period_prices]==expected_dates and bool(period_prices)
                      and period_prices[0].get('is_trading',True) and period_prices[-1].get('is_trading',True))
            level=1.0
            comparable=[]
            if complete:
                comparable=[{'date':period_prices[0]['date'],'value':period_prices[0]['close'],'level':100.0}]
                for point in period_prices[1:]:
                    if not point.get('is_trading',True):
                        comparable.append({'date':point['date'],'value':None,'level':None})
                        continue
                    level*=point['close']/point['previous_close']
                    comparable.append({'date':point['date'],'value':point['close'],'level':level*100})
            case['period_change_pct'] = (level-1)*100 if complete else None
            case['period_path']=comparable
            st = packet['market'].get('metrics', {}).get('st_change_pct')
            case['relative_to_st_pp'] = case['period_change_pct'] - st if case['period_change_pct'] is not None and st is not None else None
            if history:
                completed = instant(history[0]['completed_at']).astimezone(ZoneInfo('Asia/Shanghai'))
                anchors = [p for p in anchor_prices if p.get('is_trading',True) and (p['date'] < completed.date().isoformat() or p['date'] == completed.date().isoformat() and completed.hour >= 15)]
                anchor = anchors[-1] if anchors else None
                case['last_research_anchor'] = anchor
                case['since_research_change_pct'] = change(anchor['close'], current['close']) if anchor and current['date']>anchor['date'] else None
            relative = case['relative_to_st_pp']
            case['headline'] = f'同期弱于ST参考{abs(relative):.2f}个百分点' if relative is not None and relative < 0 else f'同期强于ST参考{relative:.2f}个百分点' if relative is not None else '继续看后续价格变化'
            relevant_start=min(start,case['last_research_anchor']['date']) if case.get('last_research_anchor') and start else start
            relevant_prices=[p for p in prices if relevant_start and p['date']>=relevant_start]
            case['basis_digest'] = digest({'symbol': symbol, 'as_of': basis['as_of'], 'prices': relevant_prices,
                                          'latest_quote':case.get('latest_quote'),'current_observation':case.get('current_observation'),
                                          'latest_run': history[0]['run_id'] if history else None,
                                          'market_metrics': packet['market'].get('metrics')})
            path = reviews_dir / (code + '.json')
            if path.is_file():
                review = json.loads(path.read_text())
                if (review.get('symbol') == symbol and review.get('version')=='workbench_case_review_v1'
                    and digest({k:v for k,v in review.items() if k!='content_digest'})==review.get('content_digest')
                    and instant(review['reviewed_at'])<=datetime.now(timezone.utc)):
                    case['previous_review']=review
                    if review.get('basis_digest') == case['basis_digest']:
                        case['review'] = review
            case['used_method_ids'] = [m['id'] for m in methods if history and m['id'] in json.loads(history[0]['experience_hits_json'])]
        cases.append(case)
    categories=list(CATEGORY_NAMES)+(['待分类'] if any(m['category']=='待分类' for m in methods) else [])
    return {'availability': 'available', 'methods': methods, 'categories': categories, 'cases': cases,'market_context':packet['market'],
            'latest_price_as_of':max((case.get('latest_quote',{}).get('as_of',case.get('as_of','')) for case in cases),default=packet['market'].get('as_of')),
            'codex_sync_note': '在Codex里继续研究，新的判断和复盘记录会同步到这里。',
            'inventory': {'accepted': sum(m['status'] == 'accepted' for m in methods), 'candidate': sum(m['status'] == 'candidate' for m in methods)}}


def processor_digest():
    return digest({name:sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                   for name in (Path(__file__).name,'case_research_scopes.py','research_corrections.py','broad_etf_reading.py','trader_research_notes.py','market_reading_updates.py','market_close_membership.py',
                                'market_price_reading.py','market_public_refresh.py','market_calendar.py')})


PROCESSOR_DIGEST = processor_digest()


class ReadingViews:
    def __init__(self, directory=OUTPUT, builder=None, ttl_seconds=600, price_directory=MARKET_ROOT / 'trader_observations/latest_index'):
        self.directory = directory; self.builder = builder; self.ttl_seconds = ttl_seconds
        self.price_directory = price_directory
        self.lock = Lock(); self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='reading-view')
        self.future: Future | None = None; self.last_error = None; self.last_attempt = None

    def read(self):
        try:
            packet = json.loads((self.directory / 'current.json').read_text())
            if processor_digest() != PROCESSOR_DIGEST or packet['version'] != VERSION or packet['processor_digest'] != PROCESSOR_DIGEST or digest({k: v for k, v in packet.items() if k != 'content_digest'}) != packet['content_digest']:
                return None
            if instant(packet['checked_at']) > datetime.now(timezone.utc):
                return None
            return packet
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def publish(self):
        if processor_digest() != PROCESSOR_DIGEST:
            raise ValueError('reload changed reading-view implementation')
        if self.builder is None:
            from market_risk import build_market_risk_status
            data = build_market_risk_status()
        else:
            data = self.builder()
        bases = []
        for symbol in WATCHED:
            try:
                bases.append(watch_basis(data, symbol))
            except (OSError, ValueError, TypeError, KeyError, IndexError):
                bases.append({'symbol': symbol, 'name':WATCH_LABELS.get(symbol,symbol), 'availability': 'unavailable'})
        broad = None
        if self.builder is None:
            from market_reading_updates import load_update
            update = load_update(data, bases)
            if update:
                data, bases, broad = update
        view = market_view(data)
        if view['availability'] != 'available':
            raise ValueError('no verified market reading available')
        from broad_etf_reading import build_broad_etf_reading
        if broad is not None:
            view['broad_etf'] = broad
        else:
            try:
                view['broad_etf']=build_broad_etf_reading(data)
            except (OSError,ValueError,KeyError,TypeError,IndexError):
                view['broad_etf']={'availability':'unavailable'}
        from market_price_reading import newer_price
        latest = newer_price(view, directory=self.price_directory)
        if latest is not None:
            view['latest_price'] = latest
        packet = {'version': VERSION, 'processor_digest': PROCESSOR_DIGEST, 'checked_at': datetime.now(timezone.utc).isoformat(),
                  'market': view, 'watch_bases': bases, 'source_snapshot_digest': data['snapshot_digest']}
        packet['content_digest'] = digest(packet)
        if processor_digest() != PROCESSOR_DIGEST:
            raise ValueError('reading-view implementation changed during publication')
        atomic_write_json(self.directory / 'snapshots' / (packet['content_digest'] + '.json'), packet)
        atomic_write_json(self.directory / 'current.json', packet)
        return packet

    def _refresh(self):
        try:
            result = self.publish(); self.last_error = None; return result
        except Exception as error:
            self.last_error = type(error).__name__; return None

    def schedule(self, force=False):
        if processor_digest() != PROCESSOR_DIGEST:
            self.last_error = 'reload_required'; return
        now = datetime.now(timezone.utc); packet = self.read()
        with self.lock:
            if self.future is not None and not self.future.done():
                return
            if not force and self.last_attempt and now - self.last_attempt < timedelta(seconds=self.ttl_seconds):
                return
            if not force and packet and now - instant(packet['checked_at']) < timedelta(seconds=self.ttl_seconds):
                return
            self.last_attempt = now; self.future = self.executor.submit(self._refresh)

    def status(self):
        return {'in_progress': self.future is not None and not self.future.done(), 'last_error': self.last_error}


views = ReadingViews()


def current_learning_view(packet,**kwargs):
    from trader_swing_reading import load
    return learning_view(packet,latest_quotes=load().get('watchlist',[]),**kwargs)


def get_reading_view(kind, *, force=False, service=views, experience_db=EXPERIENCE_REPOSITORY_DB, ledger_db=RESEARCH_RUN_LEDGER_DB):
    packet = service.read(); service.schedule(force)
    base = {'version': VERSION, 'availability': 'warming', 'refresh': service.status()}
    if packet is None:
        return base
    result = packet['market'] if kind == 'market' else current_learning_view(packet, experience_db=experience_db, ledger_db=ledger_db)
    return {**base, 'availability': 'available', 'checked_at': packet['checked_at'], 'as_of': result.get('latest_price_as_of',packet['market']['as_of']),
            'content_digest': packet['content_digest'], 'data': result}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--publish', action='store_true')
    parser.add_argument('--review-symbol');parser.add_argument('--assessment');parser.add_argument('--takeaway',action='append',default=[])
    args = parser.parse_args()
    if args.publish:
        packet = views.publish(); print(json.dumps({'as_of': packet['market']['as_of'], 'content_digest': packet['content_digest']}, ensure_ascii=False))
    if args.review_symbol:
        packet=views.read()
        if packet is None:raise ValueError('publish the current reading view before reviewing a case')
        case,=[c for c in current_learning_view(packet)['cases'] if c['symbol']==args.review_symbol]
        if not args.assessment or not args.takeaway or not case.get('basis_digest'):raise ValueError('case basis, assessment and takeaway are required')
        review={'version':'workbench_case_review_v1','symbol':case['symbol'],'basis_digest':case['basis_digest'],
                'research_run_id':case['history'][0]['run_id'] if case['history'] else None,'reviewed_at':datetime.now(timezone.utc).isoformat(),
                'assessment':args.assessment,'takeaways':args.takeaway,'scope':'case_review_not_method_effect_validation'}
        review['content_digest']=digest(review)
        atomic_write_json(OUTPUT/'case_reviews'/'history'/(review['content_digest']+'.json'),review)
        atomic_write_json(OUTPUT/'case_reviews'/(case['symbol'][:6]+'.json'),review)
        print(json.dumps({'symbol':case['symbol'],'review_digest':review['content_digest']},ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
