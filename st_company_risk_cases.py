"""Two independent companies, source-bound risk axes and common-date comparisons."""
from decimal import Decimal
from math import prod
from canonical_json import digest

def scope_digest(i):
    huapeng=next(c for c in i['official_membership_audit']['issuer_checks'] if c['symbol']=='603021')
    return digest({**{k:i[k] for k in ('calendar','through','fixed_prices','benchmarks')},'huapeng_followup':huapeng['followup']})

def company_risk_case_view(i,daily):
    p=i.get('gaoke_risk_case')
    if p is None:return None
    if p['content_digest']!=digest({k:v for k,v in p.items() if k!='content_digest'}) or p['scope_digest']!=scope_digest(i):raise ValueError('company risk case source or comparison scope changed')
    if p['symbol']!='600730' or p['through']!=i['through']:raise ValueError('company case identity/cutoff changed')
    if p['criminal']['scope']!='individuals' or p['criminal']['status']!='investigation' or p['criminal']['final_disposition'] is not None:raise ValueError('unverified criminal stage')
    civil=p['civil']
    if civil['original_case_id']!=civil['revoked_case_id'] or not(civil['first_published_on']<=civil['revocation_received_on']<=civil['revocation_published_on']<=i['through']) or civil['final_merits_judgment'] is not None:raise ValueError('civil proceeding identity/stage changed')
    for f in p['facts']:
        if f['published_on']>i['through'] or f['document_dated_on']>f['published_on'] or not all(f['source'].get(k) for k in ('sha256','url','title','page')):raise ValueError('company case lacks timely source')
    h=next(c for c in i['official_membership_audit']['issuer_checks'] if c['symbol']=='603021')['followup']['reports'][-1];g=p['financial']
    if any(r['period_start']!='2026-01-01' or r['period_end']!='2026-09-30' or r['unit']!='yuan' or r['currency']!='CNY' or r['audited'] is not False or r['published_on']>i['through'] for r in (h,g)):raise ValueError('incomparable financial periods/units')
    rows=[]
    for symbol,name,r,cause in [('600730','*ST高科',g,p['warning']['cause']),('603021','*ST华鹏',h,'负净资产触发的退市风险警示，部分子公司账户解冻/新冻结另核')]:
        prices={x['trade_date']:x for x in i['fixed_prices'] if x['symbol']==symbol};a=prices.get('2026-07-03');b=prices.get(i['through']);usable=bool(a and b and a.get('has_trade') is True and b.get('has_trade') is True);days=[d for d in daily if '2026-07-03'<d['date']<=i['through']]
        rows.append({'symbol':symbol,'name':name,'warning_cause':cause,'financial':r,'price_window':{'anchor':'2026-07-03','through':i['through'],'market_days':len(days),'stock_pct':(b['close']/a['close']-1)*100 if usable else None,'market_pct':(prod(1+x['market_pct']/100 for x in days)-1)*100,'st_pct':(prod(1+x['return_pct']/100 for x in days)-1)*100}})
        for k in ('revenue','parent_profit','operating_cash','parent_equity'):Decimal(r[k])
    return {**{k:v for k,v in p.items() if k not in ('content_digest','scope_digest')},'subsidiary_civil':subsidiary_civil_view(p),'comparison':rows,'independent_companies':2,'experience_status':'两个独立公司仅作条件对照，不汇总胜率、不由相邻公告或窗口增加验证次数，不自动晋级经验。'}

def subsidiary_civil_view(p):
    s=p.get('subsidiary_civil')
    if s is None:return None
    if s['entity']==p['name'] or s['case_id']==p['civil']['original_case_id'] or s['case_id']!=s['released_case_id']:raise ValueError('subsidiary proceeding identity conflict')
    if not(s['first_published_on']<=s['release_received_on']<=s['release_published_on']<=p['through']):raise ValueError('subsidiary release date conflict')
    if s['original_received_on'] is not None or s['restraint_duration_days'] is not None or s['final_merits_judgment'] is not None:raise ValueError('unverified subsidiary receipt/duration/merits')
    if s['release_scope']!='all_behaviour_measures_in_this_case' or len(s['requests'])!=4 or len(s['order_items'])!=3:raise ValueError('subsidiary request/order/release scope changed')
    if set(x['key'] for x in s['order_items'])!=set(x['key'] for x in s['requests'])-{'hold_shareholder_meeting'}:raise ValueError('requests mistaken for order')
    if s['reconsideration_at_first_disclosure']!='planned_not_proven_submitted':raise ValueError('unverified reconsideration submission')
    if p.get('open_catalog_items'):raise ValueError('verified subsidiary documents still marked unread')
    return {**s,'procedure_rows':[{'entity':'上市公司中国高科','court':'武汉市青山区人民法院','case_id':p['civil']['original_case_id'],'first_published_on':p['civil']['first_published_on'],'release_received_on':p['civil']['revocation_received_on'],'release_published_on':p['civil']['revocation_published_on'],'stage':'撤销原裁定并解除相关行为保全','source':p['civil']['source']},{'entity':s['short_name'],'court':s['court'],'case_id':s['case_id'],'first_published_on':s['first_published_on'],'release_received_on':s['release_received_on'],'release_published_on':s['release_published_on'],'stage':'解除本案全部行为保全措施','source':next(f['source'] for f in s['facts'] if f['published_on']==s['release_published_on'])}]}
