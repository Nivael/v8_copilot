"""Audit initial-cohort reading coverage separately from full membership certification."""
from math import prod
from hashlib import sha256
from canonical_json import digest


EXPECTED = {'002620':('1225405535',True,('净资产为负','预重整','重整投资协议')), '002305':('1225407050',False,('仍被实施退市风险警示','补充材料')), '000909':('1225405831',True,('营业收入低于3亿元','立案')), '002547':('1225405415',True,('净资产为负','诉讼','持续经营')), '002542':('1225406067',True,('净资产为负','退市风险警示')), '000639':('1225405413',False,('司法变卖','公示阶段','计划增持'))}

def initial_status_coverage(inputs, reading, context, daily):
    p = inputs.get('initial_status_coverage')
    if p is None:
        return None, reading
    if p['version'] != 1 or p['content_digest'] != digest({k:v for k,v in p.items() if k != 'content_digest'}):
        raise ValueError('initial status packet changed')
    if p['anchor'] != '2026-07-03' or p['through'] != inputs['through'] or p['reading_digest'] != digest(reading):
        raise ValueError('initial status reading/date binding changed')
    if p['scope_digest'] != digest({k:inputs[k] for k in ('calendar','through','members','fixed_prices')}):
        raise ValueError('initial status member/price scope changed')
    if p['method_promotions'] != 0 or p['full_membership_certification_added'] is not False:
        raise ValueError('reading evidence cannot certify full membership or promote methods')
    initial = {r['symbol']:r for r in inputs['members'] if r['trade_date'] == p['anchor'] and r['symbol'].startswith(('000','001','002','003','600','601','603','605'))}
    old = reading['verified_events']
    before = {e['symbol'] for e in old if e['published_on'] <= p['anchor']} & initial.keys()
    sources = {s['announcement_id']:s for s in p['sources']}
    if len(sources) != len(p['sources']) or len(p['rows']) != len(sources) or len({r['symbol'] for r in p['rows']}) != len(sources):
        raise ValueError('duplicate initial status source or company')
    if {r['symbol'] for r in p['rows']} != set(EXPECTED):
        raise ValueError('selected initial status cohort incomplete')
    events = []
    for r in p['rows']:
        s = sources[r['source_id']]
        if r['symbol'] not in initial or r['symbol'] in before or r['symbol'] != s['symbol'] or r['published_on'] != p['anchor'] or s['announcement_date'] != p['anchor'] or r['document_dated_on'] > r['published_on']:
            raise ValueError('initial status anchor/issuer changed')
        catalog = inputs['announcement_study']['catalogs'][r['symbol']]['rows']
        if not any(x['announcement_id'] == s['announcement_id'] and x['url'] == s['url'] and x['announcement_date'] == r['published_on'] and x['title'] == s['title'] for x in catalog):
            raise ValueError('initial status source not in frozen directory')
        if not s['protected_gate_passed'] or len(s['page_hashes']) != s['pages'] or set(s['selected_pages']) != {str(n) for n in range(1,s['pages']+1)}:
            raise ValueError('initial status source pages incomplete')
        for n,t in s['selected_pages'].items():
            if sha256(t.encode()).hexdigest() != s['page_hashes'][int(n)-1]:
                raise ValueError('initial status evidence page changed')
        expected_id, known, tokens = EXPECTED[r['symbol']]
        if s['announcement_id'] != expected_id or r['origin_basis_in_this_document'] is not known or any(token not in ''.join(s['selected_pages'].values()) for token in tokens):
            raise ValueError('initial status identity or stated evidence basis changed')
        first=s['selected_pages']['1']
        if r['symbol'] not in first or r['name'] not in first or initial[r['symbol']]['name'] != r['name']:
            raise ValueError('initial status header/name conflict')
        if any(str(n) not in s['selected_pages'] for n in r['evidence_pages']):
            raise ValueError('initial status cited page absent')
        public = {k:v for k,v in s.items() if k not in ('selected_pages','page_hashes')}
        event = {**{k:v for k,v in r.items() if k != 'source_id'},'source':{**public,'page':r['evidence_pages'][0]},'source_record_count':1,'observation_key':r['symbol']+':'+r['published_on'],'same_company_day_facts':1}
        event['observation'] = context(event)
        prices = {(x['symbol'],x['trade_date']):x for x in inputs['fixed_prices']}
        start, end = prices.get((r['symbol'],p['anchor'])), prices.get((r['symbol'],p['through']))
        common = [x for x in daily if p['anchor'] < x['date'] <= p['through']]
        usable = bool(start and end and start.get('has_trade') is True and end.get('has_trade') is True)
        event['full_period'] = {'anchor':p['anchor'],'through':p['through'],'market_days':len(common),'stock_pct':(end['close']/start['close']-1)*100 if usable else None,'market_pct':(prod(1+x['market_pct']/100 for x in common)-1)*100,'st_pct':(prod(1+x['return_pct']/100 for x in common)-1)*100,'gap':None if usable else '起止缺成交证据，不延用末价或补零'}
        events.append(event)
    if {e['id'] for e in old} & {e['id'] for e in events}:
        raise ValueError('initial status event already present')
    merged = sorted([*old,*events],key=lambda e:(e['published_on'],e['symbol'],e['id']))
    after = {e['symbol'] for e in merged if e['published_on'] <= p['anchor']} & initial.keys()
    inventory = []
    for c,m in sorted(initial.items()):
        facts = [e for e in merged if e['symbol'] == c and e['published_on'] <= p['anchor']]
        inventory.append({'symbol':c,'name':m['name'],'has_timely_reading_facts':bool(facts),'new_this_round':any(e['symbol']==c for e in events),'fact_ids':[e['id'] for e in facts],'latest_fact_on':max((e['published_on'] for e in facts),default=None)})
    companies = len({e['symbol'] for e in merged})
    current = {**reading,'verified_events':merged,'verified_companies':companies,'verified_documents':reading['verified_documents']+len(sources),'raw_fact_records':reading['raw_fact_records']+len(events),'deduplicated_event_count':len(merged),'initial_status_update_digest':p['content_digest'],'coverage_note':reading['coverage_note']+' 新补六家期初成员7月3日异动公告；是既有风险重述，不新增独立机制验证。'}
    counts = {'initial_members':len(initial),'timely_reading_before':len(before),'timely_reading_after':len(after),'without_timely_reading':len(initial)-len(after),'new_companies':len(events),'new_files':len(sources),'new_pages':sum(s['pages']for s in sources.values()),'origin_basis_in_new_documents':sum(r['origin_basis_in_this_document']for r in p['rows'])}
    return {'anchor':p['anchor'],'through':p['through'],'counts':counts,'inventory':inventory,'rows':events,'selection_note':p['selection_note'],'full_membership_certification_added':False,'method_promotions':0,'boundary':'有截止日前事实记录不等于该公司警示原因、状态连续性或全表无遗漏均已认证；没有记录也不等于当时未被ST。六份同日异动公告是选样补证，不是六次独立制度实验。'},current
