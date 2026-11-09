"""Broaden dated issuer evidence without presenting it as a complete exchange roster."""
from collections import Counter
from hashlib import sha256
from math import prod
import re
from canonical_json import digest
from st_pre_rule_membership import document_date

ANCHOR='2026-07-03'
def timely_inventory(inputs,reading):
    fixed={r['symbol']:r['name']for r in inputs['members']if r['trade_date']==ANCHOR and r['symbol'].startswith(('000','001','002','003','600','601','603','605'))}
    records={c:[e for e in reading['verified_events']if e['symbol']==c and e['published_on']<=ANCHOR]for c in fixed}
    return [{'symbol':c,'name':name,'has_timely_reading_facts':bool(records[c]),'latest_fact_on':max((e['published_on']for e in records[c]),default=None),'fact_ids':[e['id']for e in records[c]]}for c,name in sorted(fixed.items())]
def selected_catalog_rows(inputs,reading):
    result=[]
    for r in timely_inventory(inputs,reading):
        c=r['symbol']
        if r['has_timely_reading_facts']or not c.startswith(('000','001','002','003')):continue
        candidates=[x for x in inputs['announcement_study']['catalogs'][c]['rows']if x['announcement_date']==ANCHOR and re.search('异常波动|股价异动|风险警示相关事项',x['title'])]
        if candidates:result.append(sorted(candidates,key=lambda r:r['announcement_id'])[0])
    return result

def initial_day_corroboration(inputs,reading,context,daily):
    p=inputs.get('initial_day_corroboration')
    if p is None:return None,reading
    if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('initial-day packet changed')
    if p['anchor']!=ANCHOR or p['through']!=inputs['through']or p['prior_reading_digest']!=digest(reading):raise ValueError('initial-day prior/cutoff conflict')
    if p['scope_digest']!=digest({k:inputs[k]for k in('calendar','through','members','fixed_prices','benchmarks')}):raise ValueError('initial-day market scope changed')
    if p['method_promotions']!=0 or p['full_membership_certification_added']is not False:raise ValueError('issuer notices cannot certify full roster or promote methods')
    chosen=selected_catalog_rows(inputs,reading);expected={r['announcement_id']:r for r in chosen};sources={s['announcement_id']:s for s in p['sources']};before=timely_inventory(inputs,reading)
    if len(before)!=150 or len(chosen)!=22 or len(sources)!=22 or len(p['sources'])!=22 or set(sources)!=set(expected)or len(p['rows'])!=22 or {r['source_id']for r in p['rows']}!=set(sources):raise ValueError('dated cohort differs from deterministic pre-outcome selection')
    names={r['symbol']:r['name']for r in before}
    for aid,s in sources.items():
        cat=expected[aid]
        if any(s[k]!=cat[k]for k in('symbol','announcement_id','announcement_date','url','title'))or s['protected_gate_passed']is not True or set(s['selected_pages'])!={str(n)for n in range(1,s['pages']+1)}or len(s['page_hashes'])!=s['pages']:raise ValueError('dated issuer source/catalog/page scope conflict')
        for n,t in s['selected_pages'].items():
            if sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('dated source selected page changed')
        head=s['selected_pages']['1'][:1000]
        if s['symbol']not in head or names[s['symbol']]not in head:raise ValueError('issuer header code/name does not match target-day provider record')
    events=[];prices={(r['symbol'],r['trade_date']):r for r in inputs['fixed_prices']};end=inputs['through'];start_index=inputs['calendar'].index(ANCHOR);end_index=inputs['calendar'].index(end);period=[r for r in daily if ANCHOR<r['date']<=end];market=(prod(1+r['market_pct']/100 for r in period)-1)*100;st=(prod(1+r['return_pct']/100 for r in period)-1)*100
    for row in p['rows']:
        s=sources[row['source_id']];c=s['symbol'];text=''.join(s['selected_pages'].values())
        if row['symbol']!=c or row['name']!=names[c]or row['published_on']!=ANCHOR or row['entity_scope']!='issuer'or row['change_kind']!='dated_initial_state_corroboration'or row['id']!='initial_day_'+s['announcement_id']or not row['evidence_pages']or any(str(n)not in s['selected_pages']for n in row['evidence_pages']):raise ValueError('dated event/source binding changed')
        if row['document_dated_on']!=document_date(s)or row['document_dated_on']is not None and row['document_dated_on']>ANCHOR:raise ValueError('issuer printed date conflict')
        if not row['required_source_tokens']or any(t not in text for t in row['required_source_tokens']):raise ValueError('dated risk/state source clause missing')
        if row['specific_conditions_present']is not(c not in {'000016','000698','002102','002175','002586','002691'}):raise ValueError('generic status notice cannot become a complete risk explanation')
        if c=='000010'and('-3,456,44'not in text or '格式异常'not in row['source_note']):raise ValueError('ambiguous printed profit must retain its limitation')
        conflict=c=='002977'
        if row['internal_name_conflict']is not conflict or conflict and '证券简称:天箭科技'not in text:raise ValueError('internal issuer name conflict must be retained')
        public={k:v for k,v in s.items()if k not in('selected_pages','page_hashes')};e={**{k:v for k,v in row.items()if k not in('source_id','required_source_tokens')},'source':{**public,'page':row['evidence_pages'][0]},'source_record_count':1,'observation_key':c+':'+ANCHOR,'same_company_day_facts':1};e['observation']=context(e)
        a=prices.get((c,ANCHOR));z=prices.get((c,end));usable=bool(a and z and a['has_trade']and z['has_trade']);e['full_period']={'anchor':ANCHOR,'through':end,'market_days':end_index-start_index,'stock_pct':(z['close']/a['close']-1)*100 if usable else None,'market_pct':market,'st_pct':st,'gap':None if usable else'共同日期缺实际成交端点，保留退出/停牌解释，不填零'};events.append(e)
    if {e['id']for e in events}&{e['id']for e in reading['verified_events']}or {s['sha256']for s in sources.values()}&{e['source']['sha256']for e in reading['verified_events']}:raise ValueError('dated issuer document already counted')
    merged=sorted([*reading['verified_events'],*events],key=lambda e:(e['published_on'],e['symbol'],e['id']));days=Counter((e['symbol'],e['published_on'])for e in merged);after=timely_inventory(inputs,{'verified_events':merged});b=sum(r['has_timely_reading_facts']for r in before);a=sum(r['has_timely_reading_facts']for r in after)
    if b!=20 or a!=42:raise ValueError('initial-day timely coverage changed unexpectedly')
    for r in after:r['new_this_batch']=r['symbol']in{s['symbol']for s in sources.values()}
    current={**reading,'verified_events':merged,'verified_documents':reading['verified_documents']+22,'raw_fact_records':reading['raw_fact_records']+22,'deduplicated_event_count':len(merged),'verified_companies':len({e['symbol']for e in merged}),'supplement':{**reading['supplement'],'unique_company_days':len(days)},'initial_day_update_digest':p['content_digest'],'coverage_note':reading['coverage_note']+' 期初深市22份当日原件补证，仅印证选样状态/条件，不替代完整官方名单；天箭内部简称冲突与美丽金额格式保留。'}
    return {'anchor':ANCHOR,'through':end,'rows':events,'inventory':after,'counts':{'initial_members':150,'timely_before':b,'timely_after':a,'remaining':150-a,'new_issuer_documents':22,'new_pages':sum(s['pages']for s in sources.values()),'internal_name_conflicts':1,'header_without_conflict':21,'with_specific_conditions':sum(r['specific_conditions_present']for r in p['rows']),'general_state_only':sum(not r['specific_conditions_present']for r in p['rows']),'dated_official_full_roster_added':0},'selection_note':'从期初尚缺截止日前事实的公司中，按深市主板、2026-07-03当日、异动或风险警示进展标题筛全部22家；每公司取最小公告ID，不按后续收益选。47家当日有任意公告不是同一范围；不是全ST或随机样本。','boundary':'42/150是截止日前选样事实覆盖，不等于42家初始原因全部核清，更不是完整官方名单认证。页首简称相符不等于全部正文无冲突；未列原因继续留缺口。涨幅偏离值不是个股收益，重述风险不增加独立经验验证次数。','method_promotions':0,'full_membership_certification_added':False},current
