"""Compare provider members with dated or explicitly undated official lists."""
from hashlib import sha256
from html import unescape
import json,re
from canonical_json import digest

PREFIXES=('000','001','002','003','600','601','603','605')
def is_main(code):return isinstance(code,str) and len(code)==6 and code.isdigit() and code.startswith(PREFIXES)
def scope_digest(inputs):return digest({k:inputs[k] for k in ('members','through')})
def clean_name(value):return unescape(re.sub(r'<[^>]*>','',value)).strip()
def parse_source(source):
    raw=source['raw_json']
    if sha256(raw.encode()).hexdigest()!=source['sha256']:raise ValueError('official membership raw source changed')
    data=json.loads(raw)
    if source['venue']=='SH':
        if data.get('sqlId')!='PL_SSGSXX_FXJSBGPLB' or data.get('actionErrors') or data.get('fieldErrors'):raise ValueError('unexpected SSE report')
        rows=data['result'];meta=data['pageHelp']
        if meta['total']!=len(rows) or len({r['INSTRUMENT_ID'] for r in rows})!=len(rows):raise ValueError('SSE list incomplete or duplicate')
        return {'date':data.get('queryDate') or None,'page':1,'pages':1,'total':len(rows),'rows':[{'symbol':r['INSTRUMENT_ID'],'name':r['INSTRUMENT_SHORT']} for r in rows]}
    if source['venue']!='SZ':raise ValueError('unsupported official venue')
    matches=[r for r in data if r['metadata']['catalogid']=='fxjsb' and r['metadata']['tabkey']=='tab1']
    if len(matches)!=1:raise ValueError('unexpected SZSE report')
    row=matches[0];m=row['metadata']
    if row.get('error') or m['name']!='风险警示股票':raise ValueError('wrong SZSE list type')
    return {'date':m['subname'].strip() or None,'page':m['pageno'],'pages':m['pagecount'],'total':m['recordcount'],'rows':[{'symbol':r['zqdm'],'name':clean_name(r['gsjc'])} for r in row['data']]}

def membership_audit_view(inputs):
    p=inputs.get('official_membership_audit')
    if p is None:return None
    if p['content_digest']!=digest({k:v for k,v in p.items() if k!='content_digest'}) or p['scope_digest']!=scope_digest(inputs):raise ValueError('official membership audit binding changed')
    if p['target_dates']!=['2026-07-03',inputs['through']]:raise ValueError('official audit target dates changed')
    output=[]
    for venue in ('SZ','SH'):
        sources=[s for s in p['list_sources'] if s['venue']==venue]
        if not sources:raise ValueError('missing official venue')
        parsed=[parse_source(s) for s in sources];first=parsed[0]
        if any((r['date'],r['pages'],r['total'])!=(first['date'],first['pages'],first['total']) for r in parsed):raise ValueError('official pagination metadata drift')
        if sorted(r['page'] for r in parsed)!=list(range(1,first['pages']+1)):raise ValueError('official list pages incomplete or repeated')
        rows=[r for page in parsed for r in page['rows']]
        if len(rows)!=first['total'] or len({r['symbol'] for r in rows})!=len(rows):raise ValueError('official list rows incomplete or duplicate')
        for r in rows:
            if not re.fullmatch(r'\d{6}',r['symbol']) or not r['name']:raise ValueError('invalid official member identity')
            if is_main(r['symbol']) and (r['symbol'].startswith('6'))!=(venue=='SH'):raise ValueError('official venue mismatch')
        selected={r['symbol']:r for r in rows if is_main(r['symbol'])};original={r['symbol']:r for r in inputs['members'] if r['trade_date']==inputs['through'] and r['ts_code'].endswith('.'+venue) and is_main(r['symbol'])}
        only_official=sorted(selected.keys()-original.keys());only_provider=sorted(original.keys()-selected.keys());name_differences=[{'symbol':c,'official':selected[c]['name'],'provider':original[c]['name']} for c in sorted(selected.keys()&original.keys()) if clean_name(selected[c]['name'])!=clean_name(original[c]['name'])]
        dated_match=first['date']==inputs['through'];same=not only_official and not only_provider and not name_differences
        output.append({'venue':venue,'as_of':first['date'],'observed_at':max(s['observed_at'] for s in sources),'status':'dated_match' if dated_match and same else ('dated_conflict' if dated_match else 'undated_observation'),'official_total':len(rows),'main_board_count':len(selected),'excluded_count':len(rows)-len(selected),'provider_target_count':len(original),'pages':len(parsed),'same_codes_and_names':same,'only_official':only_official,'only_provider':only_provider,'name_differences':name_differences,'rows':[selected[c] for c in sorted(selected)],'excluded_rows':[r for r in rows if not is_main(r['symbol'])],'sources':[{k:s[k] for k in ('url','sha256','observed_at')} for s in sources]})
    dates=[]
    for date in p['target_dates']:
        members=[r for r in inputs['members'] if r['trade_date']==date and is_main(r['symbol'])]
        verified=sum(r['main_board_count'] for r in output if r['as_of']==date and r['status']=='dated_match')
        dates.append({'date':date,'provider_count':len(members),'directly_verified_count':verified,'not_directly_verified_count':len(members)-verified})
    return {'issuer_checks':issuer_checks(inputs,p),'through':inputs['through'],'targets':dates,'venues':output,'official_scope_sources':p['official_scope_sources'],'answer':'；'.join(('深市' if r['venue']=='SZ' else '沪市')+('期末官方名单有明确日期，代码与简称一致' if r['status']=='dated_match' else '有日期的官方名单存在差异，需先复核' if r['status']=='dated_conflict' else '当前列表'+('代码与简称相符' if r['same_codes_and_names'] else '存在差异')+'，但没有目标日的明确适用日期') for r in output)+'。期初名单仍缺直接官方名录。','boundary':'只认证明确日期、完整翻页且范围一致的名录。无日期当前列表不倒填历史；已核进出或改名边界不等于初始全名单与全部每日成员获独立认证。风险警示板还包括退市整理；本研究按主板A股ST/*ST范围比较，B股、创业板、科创板和北交所不混入。'}

def issuer_checks(inputs, packet):
    from decimal import Decimal
    checks=packet.get('issuer_checks',[])
    for c in checks:
        if c['scope_digest']!=digest({k:inputs[k] for k in ('calendar','through','fixed_prices','members')}):raise ValueError('issuer anchor price/member scope changed')
        members=[r for r in inputs['members'] if r['trade_date']==c['anchor'] and r['symbol']==c['symbol']]
        if len(members)!=1 or re.sub(r'\s+','',members[0]['name'])!=re.sub(r'\s+','',c['name']):raise ValueError('issuer anchor name conflicts with provider')
        if c['anchor']!=packet['target_dates'][0] or c['status_disclosed_on']!=c['anchor']:raise ValueError('issuer status not disclosed at anchor')
        if sum(Decimal(x['amount_yuan']) for x in c['released_accounts'])!=Decimal(c['released_total_yuan']):raise ValueError('released account total conflicts')
        for f in c['facts']:
            if f['published_on']>c['anchor'] or f['document_dated_on']>f['published_on'] or not all(f['source'].get(k) for k in ('sha256','url','title','page')):raise ValueError('issuer anchor source is not timely')
    return [{**c,'followup':issuer_followup_view(c,inputs)} for c in checks]

def issuer_followup_view(c, inputs):
    from decimal import Decimal
    followup=c.get('followup')
    if followup is None:return None
    if followup['as_of']!=inputs['through']:raise ValueError('issuer followup cutoff changed')
    reports=followup['reports']
    if len(reports)!=2 or [r['period_end'] for r in reports]!=['2026-06-30','2026-09-30']:raise ValueError('issuer financial periods changed')
    for r in reports:
        if not(c['anchor']<r['published_on']<=inputs['through']) or r['period_end']>r['published_on'] or r['currency']!='CNY' or r['unit']!='yuan' or r['audited'] is not False or r['period_start']!='2026-01-01':raise ValueError('issuer report period/unit/audit conflict')
        for field in ('revenue','parent_profit','operating_cash','parent_equity'):
            Decimal(r[field])
        if not all(r['source'].get(k) for k in ('sha256','url','title','page')):raise ValueError('issuer report lacks source')
    h,q=reports
    for field in ('revenue','parent_profit'):
        if Decimal(q[field])-Decimal(h[field])!=Decimal(followup['reported_single_quarter'][field]):raise ValueError('reported quarter conflicts with cumulative difference')
    cash=followup['cash_rollforward']
    if Decimal(cash['opening_yuan'])+Decimal(cash['net_change_yuan'])!=Decimal(cash['closing_yuan']):raise ValueError('cash equivalent rollforward conflict')
    freeze=followup['new_freeze']
    if not(c['anchor']<freeze['published_on']<=inputs['through']):raise ValueError('new freeze cutoff changed')
    if freeze['entity']==followup['prior_unfreeze_entity'] or freeze['account_count']!=len(freeze['accounts']) or sum(Decimal(a['amount_yuan']) for a in freeze['accounts'])!=Decimal(freeze['frozen_yuan']):raise ValueError('freeze entity/count/amount conflict')
    for f in followup['facts']:
        if not(c['anchor']<f['published_on']<=inputs['through']) or f['document_dated_on']>f['published_on'] or not all(f['source'].get(k) for k in ('sha256','url','title','page')):raise ValueError('issuer followup fact not timely/source-bound')
    return {**followup,'quarter_revenue_yuan':str(Decimal(q['revenue'])-Decimal(h['revenue'])),'quarter_parent_profit_yuan':str(Decimal(q['parent_profit'])-Decimal(h['parent_profit'])),'quarter_difference_basis':'同口径前三季累计减去半年累计，并与三季报单季列核对；不是半年对前三季同比。'}
