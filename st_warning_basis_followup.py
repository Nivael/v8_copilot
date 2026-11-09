"""Source-bound warning origins and follow-up stages, without backdating completion."""
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal
from hashlib import sha256
from collections import Counter
from canonical_json import digest

EXPECTED = {
 '1223381687':('002305','2025-04-29',('净资产为-17.53亿元','2025年4月30日')),
 '1225215035':('002305','2026-04-28',('标准无保留意见','尚需深交所核准')),
 '1225328398':('002305','2026-05-26',('补充材料','不计入')),
 '1225618730':('002305','2026-10-24',('同一控制下企业合并','未经审计','合并范围发生变化')),
 '1225247389':('000639','2026-04-29',('否定意见','2026年4月30日')),
 '1225471401':('000639','2026-08-14',('无人出价','流拍')),
 '1225573373':('000639','2026-09-19',('2026年9月21日','仍为10%','占用余额为13,000万元')),
 '1225600966':('000639','2026-10-13',('尚未通过深圳证券交易所','实施期限尚未届满')),
 '1225610079':('000639','2026-10-20',('全部交割完毕','资金占用余额为0元','498.02万元')),
 '1225646118':('000639','2026-10-31',('已全部偿还完毕','连续两个会计年度')),
}


def warning_basis_followup(inputs, reading, initial, membership, context):
    p=inputs.get('warning_basis_followup')
    if p is None:return None,reading
    if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('warning followup packet changed')
    if p['through']!=inputs['through'] or p['prior_reading_digest']!=digest(reading) or p['prior_initial_digest']!=digest(initial):raise ValueError('warning followup reading/date binding changed')
    if p['scope_digest']!=digest({k:inputs[k]for k in ('calendar','through','fixed_prices','members')}):raise ValueError('warning followup member/price scope changed')
    if p['method_promotions']!=0 or p['full_membership_certification_added']is not False or p['resolved_basis_symbols']!=['002305','000639']:raise ValueError('basis evidence is not full membership certification')
    sources={s['announcement_id']:s for s in p['sources']}
    if set(sources)!=set(EXPECTED) or len(p['sources'])!=len(sources) or {r['source_id']for r in p['rows']}!=set(sources) or len(p['rows'])!=len(sources):raise ValueError('followup source scope incomplete or duplicated')
    for aid,s in sources.items():
        code,day,tokens=EXPECTED[aid]
        if (s['symbol'],s['announcement_date'])!=(code,day) or day>p['through'] or not s['protected_gate_passed']:raise ValueError('followup source identity/date changed')
        if len(s['page_hashes'])!=s['pages'] or set(s['selected_pages'])!={str(n)for n in range(1,s['pages']+1)}:raise ValueError('followup pages incomplete')
        for n,t in s['selected_pages'].items():
            if sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('followup evidence page changed')
        text=''.join(s['selected_pages'].values())
        if code not in text or any(t not in text for t in tokens):raise ValueError('followup evidence clause absent')
        meta=s.get('metadata')
        if meta:
            actual=datetime.fromtimestamp(meta['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()
            if meta['announcementId']!=aid or meta['secCode']!=code or actual!=day or s['url']!='https://static.cninfo.com.cn/'+meta['adjunctUrl']:raise ValueError('followup official metadata conflict')
        else:
            cat=inputs['announcement_study']['catalogs'][code]['rows']
            if not any(r['announcement_id']==aid and r['announcement_date']==day and r['url']==s['url']and r['title']==s['title']for r in cat):raise ValueError('followup source absent from frozen catalog')
    settlement=p['settlement']
    expected={'principal_yuan':'130000000','assets_yuan':'68000000','cash_principal_yuan':'62000000','interest_yuan':'4980200','remaining_yuan':'0','assets_delivered':True,'cash_principal_paid':True,'all_principal_cash':False}
    if settlement!=expected or Decimal(settlement['assets_yuan'])+Decimal(settlement['cash_principal_yuan'])!=Decimal(settlement['principal_yuan']):raise ValueError('asset/cash principal settlement was conflated')
    q=p['nanzhi_q3'];text=''.join(sources['1225618730']['selected_pages'].values()).replace(',','')
    if q['period_end']!='2026-09-30' or q['published_on']!='2026-10-24' or q['audited']is not False or q['unit']!='yuan' or q['comparison_restated']is not True:raise ValueError('quarter period/audit/comparison changed')
    expected_amounts={'revenue':'215230949.01','parent_profit':'25486155.00','deducted_profit':'21994791.45','operating_cash':'-28863316.49','parent_equity':'257493036.64','nonrecurring_total':'3491363.55','prior_equity_unadjusted':'234532974.22','prior_equity_adjusted':'237093405.64'}
    if any(q[k]!=value for k,value in expected_amounts.items()):raise ValueError('quarter row/amount mapping changed')
    for k in ('revenue','parent_profit','deducted_profit','operating_cash','parent_equity','nonrecurring_total','prior_equity_unadjusted','prior_equity_adjusted'):
        if q[k]not in text:raise ValueError('quarter amount absent from source')
    if Decimal(q['parent_profit'])-Decimal(q['deducted_profit'])!=Decimal(q['nonrecurring_total']):raise ValueError('quarter profit reconciliation changed')
    official=next(r for r in membership['venues']if r['venue']=='SZ')
    name=next(r['name']for r in official['rows']if r['symbol']=='002305')
    provider=next(r['name']for r in inputs['members']if r['symbol']=='002305'and r['trade_date']==p['through'])
    if official['as_of']!=p['through']or official['status']!='dated_match'or name!=provider or name!='*ST南置':raise ValueError('Nanzhi endpoint status not corroborated')
    events=[]
    for r in p['rows']:
        s=sources[r['source_id']];code,day,_=EXPECTED[r['source_id']]
        if r['symbol']!=code or r['published_on']!=day or r['document_dated_on']>day or any(str(n)not in s['selected_pages']for n in r['evidence_pages']):raise ValueError('followup event/date/page conflict')
        y,m,d=map(int,r['document_dated_on'].split('-'))
        if f'{y}年{m}月{d}日'not in ''.join(s['selected_pages'].values()):raise ValueError('followup document date not in text')
        public={k:v for k,v in s.items()if k not in ('selected_pages','page_hashes')}
        e={**{k:v for k,v in r.items()if k!='source_id'},'source':{**public,'page':r['evidence_pages'][0]},'source_record_count':1,'observation_key':code+':'+day,'same_company_day_facts':1};e['observation']=context(e);events.append(e)
    old=reading['verified_events']
    if {e['id']for e in old}&{e['id']for e in events}:raise ValueError('followup record already present')
    if len({e['id']for e in events})!=len(events):raise ValueError('duplicate followup event')
    settlement_events=[e for e in events if e['change_kind']=='occupation_settled']
    if len(settlement_events)!=1 or settlement_events[0]['matter_id']!='xiwang_occupation' or next(e for e in events if e['change_kind']=='remaining_risk_reaffirmed')['matter_id']!='xiwang_occupation':raise ValueError('same settlement must not be counted twice')
    merged=sorted([*old,*events],key=lambda e:(e['published_on'],e['symbol'],e['id']));counts=Counter((e['symbol'],e['published_on'])for e in merged)
    for e in events:e['same_company_day_facts']=counts[e['symbol'],e['published_on']]
    current={**reading,'supplement':{**reading['supplement'],'unique_company_days':len(counts)},'verified_events':merged,'verified_documents':reading['verified_documents']+len(sources),'raw_fact_records':reading['raw_fact_records']+len(events),'deduplicated_event_count':len(merged),'warning_basis_update_digest':p['content_digest'],'coverage_note':reading['coverage_note']+' 南置与西王另补10份32页原因及后续，原问和旧事实保留；10月31日仅重申同笔占款已清，不重复增加清偿次数。'}
    view={'reading_company_days':len(counts),'historical_company_day_counter':reading['supplement']['unique_company_days'],'through':p['through'],'rows':events,'settlement':settlement,'nanzhi_q3':q,'resolved_basis_symbols':p['resolved_basis_symbols'],'nanzhi_endpoint':{'day':p['through'],'provider_name':provider,'official_name':name,'sources':official['sources']},'new_files':len(sources),'new_pages':sum(s['pages']for s in sources.values()),'method_promotions':0,'full_membership_certification_added':False,'next':p['next'],'boundary':'原始触发依据缺口已补，不表示全部状态连续性或全表无遗漏已认证；新文件与同事项重申不是独立机制验证，来源只到日级，行情同窗不证明因果。'}
    return view,current
