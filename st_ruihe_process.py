"""Distinguish reported deposit, contingent funding clocks and strengthened promises."""
from collections import Counter
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from zoneinfo import ZoneInfo
from canonical_json import digest

EXPECTED={'1225307829':('2026-05-15',('已支付的报名保证金5,000万元','书面付款通知之日起10个工作日','法院裁定批准')),'1225464983':('2026-08-08',('口头沟通','公安机关正在立案侦查','尚未收到任何公安机关')),'1225623866':('2026-10-27',('未经审计','73,858,559.84','-121,614,589.16')),'1225646013':('2026-10-30',('36个月','60个月','自有资金比例将不低于50%','不代表法院最终受理'))}

def ruihe_process(inputs,reading,initial,context):
    p=inputs.get('ruihe_process')
    if p is None:return None,reading
    if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('Ruihe packet changed')
    if p['through']!=inputs['through']or p['prior_reading_digest']!=digest(reading)or p['prior_initial_digest']!=digest(initial):raise ValueError('Ruihe prior reading or cutoff changed')
    if p['scope_digest']!=digest({k:inputs[k]for k in ('calendar','through','fixed_prices','members')}):raise ValueError('Ruihe market/member scope changed')
    if p['method_promotions']!=0 or p['full_membership_certification_added']is not False:raise ValueError('Ruihe evidence cannot promote methods or certify membership')
    sources={s['announcement_id']:s for s in p['sources']}
    if set(sources)!=set(EXPECTED)or len(sources)!=len(p['sources'])or {r['source_id']for r in p['rows']}!=set(sources)or len(p['rows'])!=4:raise ValueError('Ruihe source cohort incomplete or repeated')
    for aid,s in sources.items():
        day,tokens=EXPECTED[aid]
        if s['symbol']!='002620'or s['announcement_date']!=day or not s['protected_gate_passed']:raise ValueError('Ruihe source issuer/date conflict')
        if len(s['page_hashes'])!=s['pages']or not {'1',str(s['pages'])}<=s['selected_pages'].keys():raise ValueError('Ruihe evidence pages incomplete')
        for n,t in s['selected_pages'].items():
            if not 1<=int(n)<=s['pages']or sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('Ruihe selected page changed')
        if aid=='1225307829'and set(s['selected_pages'])&{str(n)for n in range(3,11)}:raise ValueError('unnecessary personal-profile pages are excluded')
        text=''.join(s['selected_pages'].values())
        if '002620'not in text or any(t not in text for t in tokens):raise ValueError('Ruihe source clause absent')
        meta=s.get('metadata')
        if meta:
            date=datetime.fromtimestamp(meta['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()
            if meta['announcementId']!=aid or meta['secCode']!='002620'or date!=day or s['url']!='https://static.cninfo.com.cn/'+meta['adjunctUrl']:raise ValueError('Ruihe contract catalog conflict')
        elif not any(r['announcement_id']==aid and r['announcement_date']==day and r['url']==s['url']and r['title']==s['title']for r in inputs['announcement_study']['catalogs']['002620']['rows']):raise ValueError('Ruihe source absent from frozen catalog')
    expected_shares=['243750000','7550000','45700000','45000000','46000000','46000000','46000000'];expected_amounts=['951234375.00','29463875.00','178344250.00','175612500.00','179515000.00','179515000.00','179515000.00']
    investors=p['investors'];text=''.join(sources['1225307829']['selected_pages'].values()).replace(',','')
    if len(investors)!=7 or len({r['role']for r in investors})!=7:raise ValueError('same investor cannot count twice')
    for r,shares,amount in zip(investors,expected_shares,expected_amounts):
        if r['shares']!=shares or r['planned_yuan']!=amount or r['price']!='3.9025'or Decimal(shares)*Decimal(r['price'])!=Decimal(amount)or shares not in text or amount not in text:raise ValueError('Ruihe planned investor amounts changed')
    f=p['funding']
    amounts={'planned_total_yuan':'1873200000.00','industry_planned_yuan':'951234375.00','industry_reported_deposit_yuan':'50000000','industry_remaining_if_converted_yuan':'901234375.00','finance_platform_contract_deposit_yuan':'1500000','other_finance_contract_deposit_each_yuan':'5000000'}
    if any(f[k]!=v for k,v in amounts.items())or sum(Decimal(r['planned_yuan'])for r in investors)!=Decimal(f['planned_total_yuan'])or Decimal(f['industry_planned_yuan'])-Decimal(f['industry_reported_deposit_yuan'])!=Decimal(f['industry_remaining_if_converted_yuan']):raise ValueError('planned funding is not reported payment')
    if f['deposit_status']!='issuer_reported_paid_registration_deposit_converted_to_performance_deposit'or f['deposit_to_investment_trigger']!='court_approves_reorganization_plan'or f['remaining_payment_trigger']!='manager_written_payment_notice'or f['remaining_payment_business_days']!=10 or f['other_finance_count']!=5:raise ValueError('funding clock or payment level changed')
    if any(f[k]is not False for k in ('finance_deposits_paid_verified','full_investment_paid_verified','court_acceptance_verified','plan_approval_verified','share_transfer_verified')):raise ValueError('unsupported procedural completion')
    if p['commitment']!={'subject':'industry_investor_only','old_lock_months':36,'new_lock_months':60,'lock_start':'actual_share_transfer_to_investor_account','own_fund_ratio_min':'0.50','own_funds_received_verified':False}:raise ValueError('commitment is conditional, not completed transfer/payment')
    q=p['q3'];expected={'revenue':'292372051.52','parent_profit':'-66300454.50','deducted_profit':'-66845265.99','operating_cash':'73858559.84','parent_equity':'-121614589.16','nonrecurring_total':'544811.49'};qt=''.join(sources['1225623866']['selected_pages'].values()).replace(',','')
    if q['period_end']!='2026-09-30'or q['published_on']!='2026-10-27'or q['unit']!='yuan'or q['audited']is not False or any(q[k]!=v or v not in qt for k,v in expected.items())or Decimal(q['parent_profit'])-Decimal(q['deducted_profit'])!=Decimal(q['nonrecurring_total']):raise ValueError('Ruihe financial period/row/audit conflict')
    date_tokens={'1225307829':('2026-05-14','二〇二六年五月十四日'),'1225464983':('2026-08-07','二〇二六年八月七日'),'1225623866':('2026-10-26','2026年10月26日'),'1225646013':('2026-10-30','二〇二六年十月三十日')}
    events=[]
    for r in p['rows']:
        s=sources[r['source_id']]
        if r['symbol']!='002620'or r['published_on']!=s['announcement_date']or r['document_dated_on']>r['published_on']or any(str(n)not in s['selected_pages']for n in r['evidence_pages']):raise ValueError('Ruihe event/source binding changed')
        printed,token=date_tokens[r['source_id']]
        if r['document_dated_on']!=printed or token not in ''.join(s['selected_pages'].values()):raise ValueError('Ruihe printed document date conflict')
        public={k:v for k,v in s.items()if k not in ('selected_pages','page_hashes')};e={**{k:v for k,v in r.items()if k!='source_id'},'source':{**public,'page':r['evidence_pages'][0]},'source_record_count':1,'observation_key':'002620:'+r['published_on'],'same_company_day_facts':1};e['observation']=context(e);events.append(e)
    old=reading['verified_events']
    if {e['id']for e in old}&{e['id']for e in events}:raise ValueError('Ruihe source must not create duplicate event')
    merged=sorted([*old,*events],key=lambda e:(e['published_on'],e['symbol'],e['id']));days=Counter((e['symbol'],e['published_on'])for e in merged)
    for e in events:e['same_company_day_facts']=days[e['symbol'],e['published_on']]
    current={**reading,'verified_events':merged,'verified_documents':reading['verified_documents']+4,'raw_fact_records':reading['raw_fact_records']+4,'deduplicated_event_count':len(merged),'supplement':{**reading['supplement'],'unique_company_days':len(days)},'ruihe_process_update_digest':p['content_digest'],'coverage_note':reading['coverage_note']+' 瑞和另补4份36页签约/立案说明/季报/承诺函；只公开相关选页，计划款、已披露保证金、承诺与程序完成分层，未晋级经验。'}
    comparisons=[]
    for code,aid,agency,subject,page in [('000639','1225405413','中国证监会','公司与实际控制人分别被信披立案；当时未有结论',1),('000909','1225405831','中国证监会','公司因涉嫌信披违法违规被立案；不当最终处罚',2)]:
        s=next(s for s in inputs['initial_status_coverage']['sources']if s['announcement_id']==aid)
        if s['symbol']!=code or '证监会'not in s['selected_pages'][str(page)]:raise ValueError('prior investigation comparator source changed')
        comparisons.append({'symbol':code,'name':'ST西王'if code=='000639'else'*ST数源','agency':agency,'subject':subject,'evidence_level':'7月3日公司原件披露收到立案告知/被立案，不认证最终结果','source':{**{k:v for k,v in s.items()if k not in ('selected_pages','page_hashes')},'page':page}})
    comparisons.insert(0,{'symbol':'002620','name':'*ST瑞和','agency':'公安机关','subject':'欠付劳动报酬相关案件；具体书面责任主体和法律处理另待核','evidence_level':'公司称经口头沟通获知移送/立案侦查，当时未收到公安书面告知或通知','source':next(e['source']for e in events if e['change_kind']=='police_inquiry_oral')})
    return {'through':p['through'],'rows':events,'funding':f,'investors':investors,'commitment':p['commitment'],'q3':q,'investigation_comparison':comparisons,'new_files':4,'new_pages':36,'selected_source_pages':sum(len(s['selected_pages'])for s in sources.values()),'method_promotions':0,'full_membership_certification_added':False,'reading_company_days':len(days),'boundary':'合同预计金额不是到账金额；已付报名保证金、履约保证金、投资款与股份登记分层。截止日前公司覆盖仍20/150，机关/事项三案例仅核定义与证据层次，不当结局概率或独立制度实验。'},current
