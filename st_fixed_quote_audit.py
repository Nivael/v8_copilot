"""Fixed July cohort quote coverage: price agreement is not source independence or causal proof."""
from decimal import Decimal, ROUND_HALF_UP
from statistics import median
from math import prod,isfinite
from canonical_json import digest
from st_stock_price_crosscheck import quotes_from_source

KEYS=('calendar','through','members','fixed_prices','benchmarks')
def scope_digest(i):
    return digest({k:i[k] for k in KEYS})
def fixed_quote_audit_view(i,daily):
    p=i.get('fixed_quote_audit')
    if p is None:return None
    if p['content_digest']!=digest({k:v for k,v in p.items() if k!='content_digest'}) or p['scope_digest']!=scope_digest(i):raise ValueError('fixed audit binding changed')
    cal=i['calendar'];end=i['through'];anchor='2026-07-03'
    members={r['symbol']:r['name'] for r in i['members'] if r['trade_date']==anchor and r['symbol'].startswith(('000','001','002','003','600','601','603','605'))}
    companies=p['original_prices']['companies']
    if len(members)!=150 or len(companies)!=150 or {c['symbol'] for c in companies}!=set(members):raise ValueError('fixed audit cohort changed')
    if p['original_prices']['calendar']!=cal or p['original_prices']['through']!=end:raise ValueError('fixed audit calendar changed')
    frozen={(r['symbol'],r['trade_date']):r for r in i['fixed_prices']};sources=p['sources'];seen=set();maps={};refs={}
    for s in sources:
        pair=(s['symbol'],s['key'])
        if pair in seen or pair[0] not in members or pair[1] not in ('tencent_raw','tencent_qfq'):raise ValueError('duplicate or out of scope audit channel')
        if not s.get('url') or not s.get('observed_at'):raise ValueError('audit source missing metadata')
        seen.add(pair);q=quotes_from_source(s)
        if not set(q)<=set(cal):raise ValueError('audit quote outside calendar')
        maps[pair]=q;refs[pair]={k:s[k] for k in ('key','url','sha256','observed_at','reused')}
    prior=p['prior_exit_receipts']
    if set(prior)!={'000016','002731'}:raise ValueError('exit receipt scope changed')
    j=cal.index(anchor)
    specs=[('all',anchor,end),('before20',cal[j-20],anchor),('after20',anchor,cal[j+20]),('before40',cal[j-40],anchor),('after40',anchor,cal[j+40]),('20',cal[-21],end),('5',cal[-6],end)]
    rows=[]
    for c in companies:
        symbol=c['symbol'];base={r['date']:r for r in c['rows']}
        if [r['date'] for r in c['rows']]!=cal or c['name']!=members[symbol]:raise ValueError('original price identity/date changed')
        factor=Decimal(str(c['normalization_factor']))
        if not factor.is_finite() or factor<=0:raise ValueError('invalid normalization factor')
        for d,r in base.items():
            f=frozen.get((symbol,d))
            if f and (f.get('has_trade') is True)!=r['has_trade']:raise ValueError('frozen trade state changed')
            if r['volume'] is not None and not isfinite(r['volume']):raise ValueError('invalid volume')
            if r['has_trade']!=bool(r['volume'] is not None and r['volume']>0):raise ValueError('original trade state changed')
            if r['has_trade']:
                if any(not isfinite(r[k]) or r[k]<=0 for k in ('raw_close','adj_factor','qfq_close')):raise ValueError('invalid original price')
                expected=float(Decimal(str(r['raw_close']))*Decimal(str(r['adj_factor']))/factor)
                f=frozen.get((symbol,d))
                if not f or f.get('has_trade') is not True or abs(expected-r['qfq_close'])>1e-10 or abs(f['close']-expected)>1e-10:raise ValueError('original raw/factor/frozen prices changed')
        traded={d for d,r in base.items() if r['has_trade']};channels=[]
        for key in ('tencent_raw','tencent_qfq'):
            if (symbol,key) not in maps:continue
            q=maps[(symbol,key)];field='raw_close' if key.endswith('raw') else 'qfq_close'
            differences=[{'date':d,'primary':base[d][field],'checked':float(q[d])} for d in sorted(traded&set(q)) if Decimal(str(base[d][field])).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)!=q[d]]
            channels.append({'key':key,'points':len(q),'missing_trade_dates':sorted(traded-set(q)),'extra_nontrade_dates':sorted(set(q)-traded),'differences':differences,'source':refs[(symbol,key)]})
        if symbol not in prior and len(channels)!=2:raise ValueError('unexplained missing audit channel')
        if symbol in prior:
            expected=i['sample_integrity']['price_verification']['results'][symbol]
            if prior[symbol]!=expected:raise ValueError('old exit receipts changed')
        windows={}
        for key,start,stop in specs:
            usable=base[start]['has_trade'] and base[stop]['has_trade'];a=frozen.get((symbol,start));b=frozen.get((symbol,stop));old=(b['close']/a['close']-1)*100 if usable and a and b else None;q=maps.get((symbol,'tencent_qfq'),{})
            checked=float((q[stop]/q[start]-1)*100) if old is not None and start in q and stop in q else None
            market=[r for r in daily if start<r['date']<=stop]
            windows[key]={'anchor':start,'through':stop,'market_days':len(market),'primary_pct':old,'checked_pct':checked,'difference_pp':checked-old if checked is not None else None,'market_pct':(prod(1+r['market_pct']/100 for r in market)-1)*100,'st_pct':(prod(1+r['return_pct']/100 for r in market)-1)*100,'gap':None if checked is not None else '沿用退出案例，未重新重放原字节' if symbol in prior else '所选共同日期缺实际成交端点'}
        raw=next((x for x in channels if x['key']=='tencent_raw'),None);qfq=next((x for x in channels if x['key']=='tencent_qfq'),None)
        complete=lambda x:bool(x is not None and not x['missing_trade_dates'] and not x['extra_nontrade_dates'])
        rows.append({'symbol':symbol,'name':c['name'],'traded_days':len(traded),'channels':channels,'prior_exit_receipt':prior.get(symbol),'raw_agree':bool(complete(raw) and not raw['differences']),'qfq_agree':bool(complete(qfq) and not qfq['differences']),'qfq_difference_days':len(qfq['differences']) if qfq else None,'basis_reconciled':symbol=='603517' and bool(i.get('juewei_adjustment')),'windows':windows})
    summaries={}
    for key,_,_ in specs:
        other={'before20':'after20','after20':'before20','before40':'after40','after40':'before40'}.get(key)
        eligible=[r for r in rows if r['windows'][key]['checked_pct'] is not None and (other is None or r['windows'][other]['checked_pct'] is not None)]
        pairs=[r['windows'][key] for r in eligible];a=[r['primary_pct'] for r in pairs];b=[r['checked_pct'] for r in pairs]
        summaries[key]={'anchor':pairs[0]['anchor'] if pairs else None,'through':pairs[0]['through'] if pairs else None,'market_days':pairs[0]['market_days'] if pairs else None,'paired':len(pairs),'paired_symbols':[r['symbol'] for r in eligible],'paired_other_window':other,'primary_median_pct':median(a) if a else None,'checked_median_pct':median(b) if b else None,'primary_positive':sum(x>0 for x in a),'checked_positive':sum(x>0 for x in b),'sign_changes':sum((x['primary_pct']>0)!=(x['checked_pct']>0) for x in pairs),'max_return_difference_pp':max((abs(x['difference_pp']) for x in pairs),default=None),'unpaired':150-len(pairs),'market_pct':pairs[0]['market_pct'] if pairs else None,'st_pct':pairs[0]['st_pct'] if pairs else None}
    full=summaries['all'];raw_count=sum(r['raw_agree'] for r in rows);different=sum(bool(r['qfq_difference_days']) for r in rows)
    unchanged=full['primary_median_pct'] is not None and full['checked_median_pct'] is not None and full['primary_positive']==full['checked_positive'] and round(full['primary_median_pct'],2)==round(full['checked_median_pct'],2)
    answer=f"固定150只中，{raw_count}只的腾讯原始收盘与原提供方逐日一致；其中{different}只的直接前复权读数有差异。共同完整窗口{full['paired']}只可比股票的上涨家数和两位小数中位数{'未变' if unchanged else '需要分别查看'}，但这不等于所有价格口径已完全认证。"
    return {'through':end,'anchor':anchor,'rows':rows,'summaries':summaries,'total':150,'replayed_companies':sum(bool(r['channels']) for r in rows),'raw_agree_companies':sum(r['raw_agree'] for r in rows),'qfq_agree_companies':sum(r['qfq_agree'] for r in rows),'qfq_difference_companies':sum(bool(r['qfq_difference_days']) for r in rows),'valid_responses':len(sources),'new_responses':sum(not s['reused'] for s in sources),'reused_responses':sum(s['reused'] for s in sources),'quote_points':sum(c['points'] for r in rows for c in r['channels']),'traded_security_days_replayed':sum(r['traded_days'] for r in rows if r['channels']),'cached_provider_responses':len(p['original_prices']['source_refs']),'failures':p['failed_requests'],'answer':answer,'boundary':'腾讯原始与前复权是同一渠道两种口径，不算两个独立来源；与原提供方不同渠道也不证明底层供数独立。只核固定7月3日150只，不能认证每日新进成员、ST逐日等权线或制度净因果。复权差异先保留，不覆盖原数据；康佳与萃华沿用原退出核对记录，本轮未重新重放其原字节。'}
