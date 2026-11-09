"""A bond payment, an approved claim and a liability balance are different facts."""
from collections import Counter
from decimal import Decimal
from hashlib import sha256
from canonical_json import digest
from st_stock_price_crosscheck import quotes_from_source

BALANCES={'short_borrowing':('606202205.92','146719897.69'),'other_payables':('217904617.99','953011230.99'),'current_noncurrent_debt':('1053267596.00','678635098.60'),'long_borrowing':('894448000.00','1134448973.19'),'liabilities':('4876850866.10','4570019422.33'),'assets':('4747146541.52','4065072080.34'),'parent_equity':('-131520259.38','-511713101.23'),'minority_equity':('1815934.80','6765759.24'),'total_equity':('-129704324.58','-504947341.99')}

def zhongyan_debt_followup(inputs,reading,three,context):
    p=inputs.get('zhongyan_debt_followup')
    if p is None:return None,reading
    if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('Zhongyan debt packet changed')
    if p['through']!=inputs['through']or p['prior_reading_digest']!=digest(reading)or p['prior_three_digest']!=digest(three):raise ValueError('Zhongyan debt prior case/cutoff conflict')
    if p['scope_digest']!=digest({k:inputs[k]for k in('calendar','through','members','fixed_prices','benchmarks')}):raise ValueError('Zhongyan debt market scope changed')
    if p['method_promotions']!=0 or p['full_membership_certification_added']is not False:raise ValueError('debt evidence cannot promote methods or membership coverage')
    sources={s['announcement_id']:s for s in p['sources']}
    expected={'1225520969':('2026-08-28',('指定清算账户支付全额兑付资金','518,500,000.00','2026年8月27日')),'1225570143':('2026-09-18',('2026年9月17日','审议通过','确认控股股东代偿债权','93.5748%','已回避表决'))}
    if set(sources)!=set(expected)or len(p['sources'])!=2 or {r['source_id']for r in p['rows']}!=set(expected)or len(p['rows'])!=2:raise ValueError('debt evidence source cohort changed')
    q=p['replayed_quarter'];original=next(s for s in inputs['initial_three_followup']['sources']if s['announcement_id']=='1225641111')
    if any(q[k]!=original[k]for k in ('symbol','announcement_id','announcement_date','url','title','sha256','pages','page_hashes')):raise ValueError('quarter replay identity changed')
    for s in [*sources.values(),q]:
        if s['symbol']!='002542'or s['protected_gate_passed']is not True or len(s['page_hashes'])!=s['pages']:raise ValueError('debt source issuer or protection conflict')
        for n,t in s['selected_pages'].items():
            if not 1<=int(n)<=s['pages']or sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('debt source page changed')
        if not any(r['announcement_id']==s['announcement_id']and r['announcement_date']==s['announcement_date']and r['url']==s['url']for r in inputs['announcement_study']['catalogs']['002542']['rows']):raise ValueError('debt official catalog binding changed')
    for aid,(day,tokens)in expected.items():
        s=sources[aid];text=''.join(s['selected_pages'].values())
        if s['announcement_date']!=day or '002542'not in text or any(t not in text for t in tokens):raise ValueError('debt source amount/date/approval clause absent')
    if set(q['selected_pages'])!={'3','5','10','11','12'}or q['announcement_date']!='2026-10-30':raise ValueError('quarter debt evidence page scope changed')
    text=''.join(q['selected_pages'].values());plain=text.replace(',','')
    if any(t not in text for t in ('合并资产负债表','2026年09月30日','2026年9月17日','审议通过了','不超过6.39亿元','主要是本期兴城集团代为偿还借款和中期票据')):raise ValueError('quarter approval/debt explanation absent')
    if p['claims']!={'meeting_on':'2026-09-17','published_on':'2026-09-18','approved':True,'bond_paid_on':'2026-08-27','bond_paid_yuan':'518500000.00','approved_ceiling_yuan':'638741589.98','debt_waived':False,'ceiling_all_paid_verified':False,'current_shareholder_balance_verified':False,'bank_receipt_or_clearing_direct_verified':False,'court_acceptance_verified':False,'quarter_audited':False}:raise ValueError('approval, receipt, ceiling or waiver level changed')
    board=next(s for s in inputs['initial_three_followup']['sources']if s['announcement_id']=='1225541480')
    if '638,741,589.98'not in ''.join(board['selected_pages'].values()):raise ValueError('exact approved proposal ceiling changed')
    if p['balance_periods']!=['2025-12-31','2026-09-30']or p['balance_unit']!='yuan'or set(p['balances'])!=set(BALANCES):raise ValueError('balance period/unit/scope conflict')
    balances=[]
    for k,values in BALANCES.items():
        if p['balances'][k]!=list(values)or any(x not in plain for x in values):raise ValueError('balance row or sign conflict')
        a,b=map(Decimal,values);balances.append({'key':k,'before':str(a),'after':str(b),'change':str(b-a),'change_pct':float((b/a-1)*100)if a else None})
    for n in (0,1):
        get=lambda k:Decimal(BALANCES[k][n])
        if get('liabilities')+get('total_equity')!=get('assets')or get('parent_equity')+get('minority_equity')!=get('total_equity'):raise ValueError('consolidated accounting equation conflict')
    events=[];quote=next(s for s in inputs['fixed_quote_audit']['sources']if s['symbol']=='002542'and s['key']=='tencent_qfq');qm=quotes_from_source(quote)
    for r in p['rows']:
        s=sources[r['source_id']];kind='bond_payment_disclosed'if r['source_id']=='1225520969'else'shareholder_claim_approved'
        if r['symbol']!='002542'or r['published_on']!=s['announcement_date']or r['change_kind']!=kind or r['entity_scope']!='issuer'or any(str(n)not in s['selected_pages']for n in r['evidence_pages']):raise ValueError('debt event/source/stage binding changed')
        pub={k:v for k,v in s.items()if k not in('selected_pages','page_hashes')};e={**{k:v for k,v in r.items()if k!='source_id'},'source':{**pub,'page':r['evidence_pages'][0]},'source_record_count':1,'observation_key':'002542:'+r['published_on'],'same_company_day_facts':1};e['observation']=context(e);e['quote_replay']={}
        for n,w in e['observation']['windows'].items():
            a=e['observation']['anchor'];z=w['through'];checked=float((qm[z]/qm[a]-1)*100)if w['stock_pct']is not None and a in qm and z in qm else None;e['quote_replay'][n]={'checked_pct':checked,'agreement_to_2dp':round(checked,2)==round(w['stock_pct'],2)if checked is not None else None}
        events.append(e)
    if {e['id']for e in reading['verified_events']}&{e['id']for e in events}or {s['sha256']for s in sources.values()}&{e['source']['sha256']for e in reading['verified_events']}:raise ValueError('new debt sources already counted')
    merged=sorted([*reading['verified_events'],*events],key=lambda e:(e['published_on'],e['symbol'],e['id']));days=Counter((e['symbol'],e['published_on'])for e in merged);current={**reading,'verified_events':merged,'verified_documents':reading['verified_documents']+2,'raw_fact_records':reading['raw_fact_records']+2,'deduplicated_event_count':len(merged),'supplement':{**reading['supplement'],'unique_company_days':len(days)},'zhongyan_debt_update_digest':p['content_digest'],'coverage_note':reading['coverage_note']+' 中岩新补2份6页兑付与股东会；旧季报重放债务附注，不重复计文件或代偿。'}
    xi=next(s for s in inputs['warning_basis_followup']['sources']if s['announcement_id']=='1225610079');xt=''.join(xi['selected_pages'].values()).replace(',','')
    if any(t not in xt for t in ('6800','6200','清偿')):raise ValueError('Xiwang prior settlement comparator changed')
    public=lambda s,page:{**{k:v for k,v in s.items()if k not in('selected_pages','page_hashes')},'page':page}
    return {'through':p['through'],'claims':p['claims'],'rows':events,'balance_periods':p['balance_periods'],'balance_unit':'yuan','balances':balances,'quarter_source':public(q,5),'quarter_balance_source':public(q,11),'proposal_source':public(board,1),'settlement_comparator_source':public(xi,1),'new_files':2,'new_pages':6,'replayed_quarter_pages':15,'selected_pages':sum(len(s['selected_pages'])for s in [*sources.values(),q]),'quote_source':{k:quote[k]for k in ('symbol','key','url','sha256','observed_at')},'method_promotions':0,'boundary':'5.185亿元是发行人披露已付到指定清算账户；股东债权上限和季报其他应付款不是同一笔金额，不重复相加。季报未经审计，缺准确对股东余额、每笔新增代偿和实际清算回单，不当全款、豁免或法院受理。'},current
