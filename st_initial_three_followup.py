"""Update three initial-cohort cases without conflating approvals, issuers or cash."""
from collections import Counter
from decimal import Decimal
from hashlib import sha256
from canonical_json import digest

# Source-specific clauses prevent adjacent procedural steps from substituting for one another.
EXPECTED={
 '1225556368':('000909','2026-09-10','regulatory_prior_notice',('拟决定','800万元','最终结果','行政处罚决定书')),
 '1225556367':('000909','2026-09-10','layered_warning',('2026年9月10日','不停牌','仍为10%')),
 '1225582995':('000909','2026-09-28','accounting_restatement',('再次进行会计差错更正','对2025年合并','对2026年半年度合并')),
 '1225621493':('000909','2026-10-24','quarterly_financials',('第三季度','□是','否')),
 '1225446816':('002547','2026-07-30','out_of_court_start',('不具有司法强制效力','不代表公司进入重整程序')),
 '1225590833':('002547','2026-10-08','investor_selection',('2026年9月28日','尚未与重整投资人签署')),
 '1225607502':('002547','2026-10-16','investment_contract',('47,000,000.00','47,355,000.00','20个工作日','股东会审批通过后生效')),
 '1225652178':('002547','2026-11-03','shareholder_contract_approval',('2026年11月02日','生效的议案','审议通过')),
 '1225633536':('002547','2026-10-29','quarterly_financials',('第三季度','未经审计')),
 '1225431048':('002542','2026-07-18','board_application_plan',('2026年7月17日','尚需','股东会审议')),
 '1225454951':('002542','2026-08-04','shareholder_application_approval',('拟向法院申请重整及预重整','审议通过')),
 '1225473990':('002542','2026-08-15','subsidiary_liquidation_application',('上海远方','破产清算')),
 '1225611814':('002542','2026-10-21','subsidiary_application_withdrawn',('准许申请人','撤回破产清算申请','未进入破产清算程序')),
 '1225541480':('002542','2026-09-02','shareholder_debt_substitution',('2026年8月27日','518,500,000.00','638,741,589.98','全额债权')),
 '1225641111':('002542','2026-10-30','quarterly_financials',('第三季度','□是','否')),
}
FINANCIALS={'000909':('1225621493',('167896372.92','-26549448.81','-39978801.31','26548936.11','592854250.04')),'002547':('1225633536',('1463756604.95','-189586835.60','-182275246.57','46705733.60','-561527071.62')),'002542':('1225641111',('177969433.09','-404252307.51','-406618115.22','-110017404.08','-511713101.23'))}
CLAIMS={'shuyuan_penalty_stage':'prior_notice_not_final','shuyuan_company_proposed_fine_yuan':'8000000','shuyuan_new_warning_effective':'2026-09-10','shuyuan_name_changed':False,'shuyuan_suspended':False,'shuyuan_band_pct':10,'correction_2025_profit_cash_effect':False,'correction_2026_half_profit_cash_effect':False,'chunxing_contract_approval_meeting':'2026-11-02','chunxing_contract_approval_published':'2026-11-03','chunxing_reported_registration_deposit_yuan':'47000000','chunxing_contract_performance_deposit_yuan':'47355000','chunxing_performance_fully_paid_verified':False,'chunxing_remainder_trigger':'court_plan_approval','chunxing_remainder_business_days':20,'chunxing_court_acceptance_verified':False,'chunxing_full_funding_verified':False,'zhongyan_application_approval_meeting':'2026-08-03','zhongyan_application_approval_published':'2026-08-04','zhongyan_court_acceptance_verified':False,'zhongyan_subsidiary':'上海远方','subsidiary_application_result':'court_permitted_withdrawal_not_entered_liquidation','shareholder_repaid_bond_yuan':'518500000.00','shareholder_repaid_on':'2026-08-27','shareholder_debt_ceiling_yuan':'638741589.98','shareholder_ceiling_all_paid_verified':False,'shareholder_debt_waived':False}

def initial_three_followup(inputs,reading,initial,context):
    p=inputs.get('initial_three_followup')
    if p is None:return None,reading
    if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('three-case packet changed')
    if p['through']!=inputs['through']or p['prior_reading_digest']!=digest(reading)or p['prior_initial_digest']!=digest(initial):raise ValueError('three-case parent/cutoff conflict')
    if p['scope_digest']!=digest({k:inputs[k]for k in ('calendar','through','fixed_prices','members')}):raise ValueError('three-case market scope changed')
    if p['method_promotions']!=0 or p['full_membership_certification_added']is not False:raise ValueError('three cases cannot promote experience or certify membership')
    sources={s['announcement_id']:s for s in p['sources']}
    if set(sources)!=set(EXPECTED)or len(sources)!=len(p['sources'])or len(p['rows'])!=len(sources)or {r['source_id']for r in p['rows']}!=set(sources):raise ValueError('three-case source cohort repeated or incomplete')
    for aid,s in sources.items():
        code,day,_,tokens=EXPECTED[aid]
        if s['symbol']!=code or s['announcement_date']!=day or s['protected_gate_passed']is not True:raise ValueError('three-case source subject/date conflict')
        if len(s['page_hashes'])!=s['pages']or '1'not in s['selected_pages']:raise ValueError('three-case source page scope incomplete')
        for n,t in s['selected_pages'].items():
            if not 1<=int(n)<=s['pages']or sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('three-case source page hash conflict')
        text=''.join(s['selected_pages'].values())
        if code not in text or any(t not in text for t in tokens):raise ValueError('three-case source clause missing: '+aid)
        if aid=='1225607502'and set(s['selected_pages'])&{str(n)for n in range(4,15)}:raise ValueError('unneeded investor profiles are excluded')
        if not any(r['announcement_id']==aid and r['announcement_date']==day and r['url']==s['url']and r['title']==s['title']for r in inputs['announcement_study']['catalogs'][code]['rows']):raise ValueError('three-case official catalog binding conflict')
    if p['claims']!=CLAIMS:raise ValueError('procedural completion, subject or money level changed')
    financials=p['financials']
    if len(financials)!=3 or {q['symbol']for q in financials}!=set(FINANCIALS):raise ValueError('financial cohort changed')
    for q in financials:
        aid,values=FINANCIALS[q['symbol']];text=''.join(sources[aid]['selected_pages'].values()).replace(',','')
        if q['source_id']!=aid or q['period_start']!='2026-01-01'or q['period_end']!='2026-09-30'or q['unit']!='yuan'or q['audited']is not False:raise ValueError('financial period/unit/audit conflict')
        for k,value in zip(('revenue','parent_profit','deducted_profit','operating_cash','parent_equity'),values):
            if q[k]!=value or value not in text:raise ValueError('financial source row conflict')
    events=[]
    for r in p['rows']:
        s=sources[r['source_id']];code,day,kind,_=EXPECTED[r['source_id']];entity='subsidiary'if kind in('subsidiary_liquidation_application','subsidiary_application_withdrawn')else'issuer'
        if r['symbol']!=code or r['published_on']!=day or r['change_kind']!=kind or r['entity_scope']!=entity or r['id']!='initial_three_'+r['source_id']or not r['evidence_pages']or any(str(n)not in s['selected_pages']for n in r['evidence_pages']):raise ValueError('event subject/stage/source binding conflict')
        public={k:v for k,v in s.items()if k not in ('selected_pages','page_hashes')};e={**{k:v for k,v in r.items()if k!='source_id'},'source':{**public,'page':r['evidence_pages'][0]},'source_record_count':1,'observation_key':code+':'+day};e['observation']=context(e);events.append(e)
    old=reading['verified_events']
    if {e['id']for e in old}&{e['id']for e in events}or {e['source']['sha256']for e in old}&{s['sha256']for s in sources.values()}:raise ValueError('repeated primary document cannot count as new fact')
    merged=sorted([*old,*events],key=lambda e:(e['published_on'],e['symbol'],e['id']));days=Counter((e['symbol'],e['published_on'])for e in merged)
    for e in events:e['same_company_day_facts']=days[e['symbol'],e['published_on']]
    current={**reading,'verified_events':merged,'verified_documents':reading['verified_documents']+len(sources),'raw_fact_records':reading['raw_fact_records']+len(events),'deduplicated_event_count':len(merged),'supplement':{**reading['supplement'],'unique_company_days':len(days)},'initial_three_update_digest':p['content_digest'],'coverage_note':reading['coverage_note']+' 数源、春兴、中岩补15份127页，拟罚/叠加、股东会通过与法院受理、子公司清算申请撤回、代偿后债权和季报分层；不是15次独立验证。'}
    return {'through':p['through'],'rows':events,'financials':financials,'claims':p['claims'],'new_files':len(sources),'new_pages':sum(s['pages']for s in sources.values()),'company_day_groups':len({(e['symbol'],e['published_on'])for e in events}),'reading_company_days':len(days),'selected_source_pages':sum(len(s['selected_pages'])for s in sources.values()),'method_promotions':0,'full_membership_certification_added':False,'boundary':'三家为同一期初六家后续选样，不是随机样本或成功率统计。重复风险、同日两公告、投资人数量均不算独立验证；公司内部通过、法院节点、资金到账和年度审计分别核。'},current
