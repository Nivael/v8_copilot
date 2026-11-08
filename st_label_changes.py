"""Primary-source label transitions and source-specific ex-dividend price comparisons."""
from decimal import Decimal,ROUND_HALF_UP
import re,unicodedata
from canonical_json import digest
from st_stock_price_crosscheck import quotes_from_source

SUBJECTS={'002731','000793','600238','603869','600079'}

def label_scope_digest(inputs):
    return digest({k:inputs[k] for k in ('calendar','through','members','fixed_prices','activities')})

def normalized(name):return re.sub(r'\s+','',unicodedata.normalize('NFKC',name or ''))

def dividend_view(row,packet,inputs,daily):
    symbol=row['symbol'];end=row['effective_on'];calendar=inputs['calendar'];previous=calendar[calendar.index(end)-1];following=calendar[calendar.index(end)+1];needed=[previous,end,following];sources=[s for s in packet['quote_sources'] if s['symbol']==symbol]
    if len(sources)!=4 or {s['key'] for s in sources}!={'tencent_raw','tencent_qfq','eastmoney_raw','eastmoney_qfq'}:raise ValueError('dividend quote channels incomplete')
    cache={}
    for ref in packet['cache_rows']:
        for r in ref['rows']:
            key=(ref['api'],ref['date'],r['ts_code'][:6])
            if key in cache:raise ValueError('duplicate dividend cache quote')
            cache[key]=r
    raw={d:cache[('daily',d,symbol)] for d in needed};factors={d:Decimal(str(cache[('adj_factor',d,symbol)]['adj_factor'])) for d in needed}
    if any(r['vol']<=0 for r in raw.values()) or any(f<=0 for f in factors.values()):raise ValueError('dividend price endpoint not traded')
    first=Decimal(str(raw[previous]['close']));close=Decimal(str(raw[end]['close']));reference=Decimal(str(raw[end]['pre_close']));cash=Decimal(row['dividend']['reference_cash_per_share']);expected=(first-cash).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    channels=[];qfq_returns=[]
    for s in sources:
        q=quotes_from_source(s)
        if set(q)!=set(needed):raise ValueError('dividend quote calendar mismatch')
        rawbasis=s['key'].endswith('_raw');differences=[d for d in needed if rawbasis and q[d]!=Decimal(str(raw[d]['close']))]
        value=float((q[end]/q[previous]-1)*100)
        if not rawbasis:qfq_returns.append(value)
        channels.append({'key':s['key'],'points':len(q),'basis':'raw' if rawbasis else 'qfq','values':[{'date':d,'price':float(q[d]),'original_precision':str(q[d])} for d in needed],'event_return_pct':value,'raw_price_differences':differences,'source':{k:s[k] for k in ('url','sha256','observed_at')}})
    day,=[d for d in daily if d['date']==end];provider_qfq=float((close*factors[end]/(first*factors[previous])-1)*100)
    return {'previous_session':previous,'ex_date':end,'next_session':following,'previous_raw_close':float(first),'ex_raw_close':float(close),'provider_adjusted_previous_close':float(reference),'cash_per_eligible_share':float(Decimal(row['dividend']['cash_per_share'])),'reference_cash_per_share':float(cash),'reference_before_cent_rounding':float(first-cash),'calculated_cent_reference':float(expected),'reference_matches_formula':reference==expected,'raw_close_change_pct':float((close/first-1)*100),'reference_price_change_pct':float((close/reference-1)*100),'provider_reported_pct':raw[end]['pct_chg'],'provider_qfq_change_pct':provider_qfq,'factor_before':float(factors[previous]),'factor_on':float(factors[end]),'market_pct':day['market_pct'],'st_pct':day['return_pct'],'channels':channels,'raw_quotes_match':all(not c['raw_price_differences'] for c in channels),'qfq_channel_return_spread_pp':max(qfq_returns)-min(qfq_returns),'boundary':'相邻日比值保留各渠道回看口径；复权返回价不当作历史当时可成交价。参考价与实际有权分红、税费及个人到账分开，价格变化不是实际含息总收益。供应商算法未由数值相近来认证。'}

def label_change_view(inputs,daily):
    p=inputs.get('label_changes')
    if p is None:return None
    if p['content_digest']!=digest({k:v for k,v in p.items() if k!='content_digest'}):raise ValueError('label source packet changed')
    if p['scope_digest']!=label_scope_digest(inputs) or p['through']!=inputs['through']:raise ValueError('label scope binding changed')
    if len(p['rows'])!=5 or {r['symbol'] for r in p['rows']}!=SUBJECTS:raise ValueError('label subject scope changed')
    cal=inputs['calendar'];members={(r['symbol'],r['trade_date']):r for r in inputs['members']};output=[]
    for row in p['rows']:
        kind=row['kind'];d=row['effective_on'];symbol=row['symbol']
        if kind not in ('add_delisting_warning','remove_delisting_keep_other','ex_dividend_marker') or d not in cal or not(row['published_on']<=d<=inputs['through']):raise ValueError('unknown label stage or invalid date')
        facts=[*row['facts'],*([row['later_fact']] if row.get('later_fact') else [])]
        if not row['facts']:raise ValueError('label has no primary facts')
        for f in facts:
            if f['published_on']>inputs['through'] or not all(f['source'].get(k) for k in ('title','url','page','sha256')):raise ValueError('label lacks timely source')
        before=cal[cal.index(d)-1];a=members.get((symbol,before));b=members.get((symbol,d));boundaries=[{'date':d,'expected_before':row['before_name'],'expected_after':row['effective_name'],'observed_before':a['name'] if a else None,'observed_after':b['name'] if b else None,'matches':bool(a and b and normalized(a['name'])==normalized(row['before_name']) and normalized(b['name'])==normalized(row['effective_name']))}]
        if kind=='ex_dividend_marker':
            r=row['restore_on']
            if r not in cal or cal.index(r)!=cal.index(d)+1:raise ValueError('XD return is not next market session')
            c=members.get((symbol,r));boundaries.append({'date':r,'expected_before':row['effective_name'],'expected_after':row['before_name'],'observed_before':b['name'] if b else None,'observed_after':c['name'] if c else None,'matches':bool(b and c and normalized(b['name'])==normalized(row['effective_name']) and normalized(c['name'])==normalized(row['before_name']))})
        else:c=b
        output.append({**row,'boundaries':boundaries,'matching_boundaries':sum(r['matches'] for r in boundaries),'same_st_presence_at_boundary':bool(a and b and c),'dividend_observation':dividend_view(row,p,inputs,daily) if kind=='ex_dividend_marker' else None})
    return {'through':inputs['through'],'rows':output,'warning_changes':sum(r['kind']!='ex_dividend_marker' for r in output),'dividend_episodes':sum(r['kind']=='ex_dividend_marker' for r in output),'name_boundaries':sum(len(r['boundaries']) for r in output),'matching_boundaries':sum(r['matching_boundaries'] for r in output),'new_primary_documents':len(p['new_primary_sources']),'new_primary_pages':sum(s['pages'] for s in p['new_primary_sources']),'identifier_rule':p['identifier_rule'],'quote_responses':len(p['quote_sources']),'quote_points':sum(c['points'] for r in output if r['dividend_observation'] for c in r['dividend_observation']['channels']),'boundary':'只核本轮5个事项及7个名称边界，不认证全部每日成员。摘星、继续其他警示、XD除息分开；风险警示板字段不代替具体类别。XD进出算同一次公司行动，阅读事项不是独立机制验证。旧名单、价格和原问原答不倒填。'}
