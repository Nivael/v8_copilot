"""Replay cached price channels against the newly researched case-event windows."""
from decimal import Decimal,ROUND_HALF_UP
from canonical_json import digest
from st_stock_price_crosscheck import quotes_from_source

CODES=('000909','002547','002542')
def three_quoteproof(inputs,three):
    p=inputs.get('initial_three_quoteproof')
    if p is None:return None
    if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('three quote proof changed')
    if not three or p['case_digest']!=digest(three)or p['scope_digest']!=digest({k:inputs[k]for k in ('calendar','through','members','fixed_prices','benchmarks')}):raise ValueError('three quote proof case/market binding changed')
    if p['new_quote_requests']!=0 or p['new_pdf_downloads']!=0 or p['method_promotions']!=0:raise ValueError('replay cannot count as new acquisition or method')
    audit=inputs['fixed_quote_audit'];sources=[s for s in audit['sources']if s['symbol']in CODES];receipts=[{k:s[k]for k in ('symbol','key','sha256','url','observed_at')}for s in sources]
    if p['receipts']!=receipts or len(receipts)!=6 or {(s['symbol'],s['key'])for s in sources}!={(c,k)for c in CODES for k in ('tencent_raw','tencent_qfq')}:raise ValueError('cached quote identity/receipt scope changed')
    maps={(s['symbol'],s['key']):quotes_from_source(s)for s in sources};frozen={(r['symbol'],r['trade_date']):r for r in inputs['fixed_prices']};companies={c['symbol']:c for c in audit['original_prices']['companies']if c['symbol']in CODES};rows=[];observations={};references=[]
    for code in CODES:
        c=companies[code];base={r['date']:r for r in c['rows']};traded={d for d,r in base.items()if r['has_trade']};channels=[]
        for key,field in [('tencent_raw','raw_close'),('tencent_qfq','qfq_close')]:
            q=maps[code,key];differences=[{'date':d,'primary':base[d][field],'checked':str(q[d])}for d in sorted(traded&set(q))if Decimal(str(base[d][field])).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)!=q[d]]
            channels.append({'key':key,'points':len(q),'missing_dates':sorted(traded-set(q)),'extra_dates':sorted(set(q)-traded),'differences':differences})
        for d in traded:
            f=frozen.get((code,d))
            if not f or f['has_trade']is not True or abs(f['close']-base[d]['qfq_close'])>1e-10:raise ValueError('original case price changed')
        all_agree=all(not r['missing_dates']and not r['extra_dates']and not r['differences']for r in channels)
        rows.append({'symbol':code,'name':next(r['name']for r in three['rows']if r['symbol']==code),'traded_days':len(traded),'channels':channels,'all_agree':all_agree})
    for e in three['rows']:
        key=e['observation_key'];a=e['observation']['anchor'];windows={};q=maps[e['symbol'],'tencent_qfq']
        for n,w in e['observation']['windows'].items():
            z=w['through'];eligible=w['stock_pct']is not None;checked=float((q[z]/q[a]-1)*100)if eligible and a in q and z in q else None
            windows[n]={'through':z,'primary_pct':w['stock_pct'],'checked_pct':checked,'difference_pp':checked-w['stock_pct']if checked is not None else None,'agreement_to_2dp':round(checked,2)==round(w['stock_pct'],2)if checked is not None else None,'status':'compared'if checked is not None else'unfinished'if z is None else'missing_quote'}
        obs={'observation_key':key,'symbol':e['symbol'],'published_on':e['published_on'],'anchor':a,'windows':windows}
        if key in observations and observations[key]!=obs:raise ValueError('same-day case must share one comparison')
        observations[key]=obs;references.append({'event_id':e['id'],'observation_key':key})
    obs=list(observations.values());wins=[w for r in obs for w in r['windows'].values()];valid=[w for w in wins if w['checked_pct']is not None]
    return {'through':inputs['through'],'companies':rows,'sources':receipts,'observations':obs,'event_refs':references,'new_quote_requests':0,'new_pdf_downloads':0,'replayed_responses':len(sources),'quote_points':sum(len(q)for q in maps.values()),'traded_security_days':sum(r['traded_days']for r in rows),'event_records':len(three['rows']),'unique_company_days':len(obs),'window_slots':len(wins),'compared_windows':len(valid),'unfinished_windows':sum(w['status']=='unfinished'for w in wins),'missing_quote_windows':sum(w['status']=='missing_quote'for w in wins),'all_quotes_agree':all(r['all_agree']for r in rows),'window_sign_changes':sum((w['primary_pct']>0)!=(w['checked_pct']>0)for w in valid),'max_return_difference_pp':max((abs(w['difference_pp'])for w in valid),default=None),'all_windows_agree_to_2dp':all(w['agreement_to_2dp']for w in valid),'search_boundary':p['search_boundary'],'boundary':'重放腾讯原始及前复权是同一渠道两种口径，与原提供方不同渠道也不证明底层供数独立。只核这三家与对应窗口，不认证ST每日等权线、制度净因果、发布分钟或可交易收益；已有报价不算新增采集或新增案例。'}
