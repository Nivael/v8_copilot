"""Official two-close fixed-cohort observation; never a current legal ST roster."""
from pathlib import Path
from hashlib import sha256
from decimal import Decimal as D
from statistics import median
import json
from recent_breadth_inputs import verify_szse_day


def analyze(e, szse_folder):
    folder=Path(szse_folder);fixed=e['fixed_symbols'];days=['2026-11-19','2026-11-20']
    if len(fixed)!=150 or len(set(fixed))!=150:raise ValueError('fixed 150 scope changed')
    expected_sh={c[:6]for c in fixed if c.endswith('.SH')};expected_sz={c for c in fixed if c.endswith('.SZ')}
    if len(expected_sh)!=69 or len(expected_sz)!=81:raise ValueError('fixed venue scope changed')
    if [r['date']for r in e['szse_day_refs']]!=days:raise ValueError('two SZSE source days required')
    sz={}
    for ref in e['szse_day_refs']:
        raw=(folder/'days'/(ref['date']+'.json')).read_bytes()
        if sha256(raw).hexdigest()!=ref['sha256']:raise ValueError('SZSE normalized packet bytes changed')
        packet=json.loads(raw)
        if packet['content_digest']!=ref['content_digest']:raise ValueError('SZSE content identity changed')
        verify_szse_day(packet,folder)
        sz[ref['date']]={r['ts_code']:r for r in packet['block']['rows']}
    if {s['code']for s in e['sse_sources']}!=expected_sh or len(e['sse_sources'])!=len(expected_sh):raise ValueError('all fixed SSE raw sources required')
    sh={}
    for src in e['sse_sources']:
        raw=src['text'].encode()
        if sha256(raw).hexdigest()!=src['sha256']or len(raw)!=src['bytes']:raise ValueError('SSE source bytes changed')
        p=json.loads(raw);code=src['code']
        if p['code']!=code or src['url']!='https://yunhq.sse.com.cn:32042/v1/sh1/dayk/'+code or src['params']!={'select':'date,close,prevClose,chg_rate,volume,amount','begin':-126,'end':-1,'period':'day'}:raise ValueError('SSE source identity/request changed')
        rows={}
        for r in p['kline']:
            if len(r)!=6 or r[0]in rows:raise ValueError('SSE duplicate/schema changed')
            rows[r[0]]=r
        sh[code]=rows
    results=[];values=[]
    for symbol in fixed:
        if symbol.endswith('.SZ'):
            before=sz[days[0]].get(symbol);current=sz[days[1]].get(symbol)
            a=None if before is None else {'close':before['last'],'volume':before['volume'],'trading':before['is_trading']}
            b=None if current is None else {'close':current['last'],'pre_close':current['prev_close'],'volume':current['volume'],'trading':current['is_trading']}
        else:
            before=sh[symbol[:6]].get(20261119);current=sh[symbol[:6]].get(20261120)
            a=None if before is None else {'close':before[1],'volume':before[4],'trading':D(str(before[4]))>0}
            b=None if current is None else {'close':current[1],'pre_close':current[2],'volume':current[4],'trading':D(str(current[4]))>0}
        row={'symbol':symbol}
        if b is None:row['status']='missing_quote20'
        elif not b['trading']:row['status']='nontrading20'
        elif a is None or not a['trading']:row['status']='no_trading_anchor19'
        else:
            old,close,ref=map(lambda x:D(str(x)),[a['close'],b['close'],b['pre_close']])
            if any(not v.is_finite()or v<=0 for v in (old,close,ref)):raise ValueError('invalid paired price')
            if old!=ref:row.update(status='reference_mismatch',close19=str(old),reference20=str(ref),close20=str(close))
            else:
                change=(close/old-1)*100;values.append(change)
                row.update(status='paired',close19=str(old),reference20=str(ref),close20=str(close),change_pct=float(change))
        results.append(row)
    benchmark=e['benchmark_points']
    if [r['trade_date']for r in benchmark]!=days or any(r['ts_code']!='000985.CSI'for r in benchmark):raise ValueError('same-day benchmark required')
    a,b=[D(str(r['close']))for r in benchmark]
    if not a.is_finite()or not b.is_finite()or min(a,b)<=0:raise ValueError('invalid benchmark price')
    market=(b/a-1)*100
    n=len(values);average=sum(values)/n if n else None
    return {'version':'fixed150_official_nov20_v1','anchor':days[0],'through':days[1],'fixed_members':150,'paired':n,
            'advancing':sum(v>0 for v in values),'declining':sum(v<0 for v in values),'flat':sum(v==0 for v in values),
            'declining_at_least_5pct':sum(v<=-5 for v in values),
            'equal_weight_one_day_pct':float(average)if average is not None else None,'median_one_day_pct':float(median(values))if values else None,
            'market_one_day_pct':float(market),'equal_weight_minus_market_pp':float(average-market)if average is not None else None,
            'rows':results,'boundary':'固定7月3日150只旧样本，包含后来离开ST的公司，不是20日法定ST名单。只比较19日和20日实际有成交且当日参考前收与19日原价一致的子样本；停牌、无报价和参考差异分别保留，不记零。单日算术等权不是旧动态ST复合参考、账户收益或趋势判断；跌幅至少5%不是实际跌停。',
            'independent_validations_added':0}
