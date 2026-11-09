"""Distinct issuer cases, repeated measurements, and conditional counterexamples.

This is a descriptive audit of a frozen post-selected event set, never a method
promotion or an estimate of predictive/causal performance.
"""
from itertools import combinations
from urllib.parse import urlparse
from statistics import median
from math import isfinite
from canonical_json import digest

HORIZONS=('5','20','40')
ANN_KEYS=('verified_events','raw_fact_records','verified_documents','verified_companies','deduplicated_event_count')
def announcement_digest(ann):return digest({k:ann[k]for k in ANN_KEYS})
def scope_digest(i):return digest({k:i[k]for k in ('calendar','through')})
def support_sources(i,comparison):
    used={aid for r in comparison['rows']for key in HORIZONS for aid in (r['windows'][key]['from_resume_close'].get('action_support')or{}).get('source_ids',[])}
    selected=[s for s in (comparison.get('action_basis')or{}).get('sources',[])if s['announcement_id']in used]
    if any(r['windows'][key]['from_resume_close']['support_kind']=='verified_action_factor_reconstruction'for r in comparison['rows']for key in HORIZONS):selected+=i['juewei_adjustment']['sources']
    result=[]
    for s in selected:
        row={k:s[k]for k in ('announcement_id','symbol','title','url','sha256','published_on')};row['host_is_official']=urlparse(s['url']).hostname in ('static.cninfo.com.cn','disc.static.szse.cn','www.sse.com.cn')
        result.append(row)
    if len({s['announcement_id']for s in result})!=len(result):raise ValueError('duplicate supporting source roles')
    return sorted(result,key=lambda r:r['announcement_id'])

def seal_packet(i,comparison,ann,prior_digest):
    p={'version':1,'question_id':'first-up-followthrough-v1','through':i['through'],'primary_horizon':20,'horizons':[5,20,40],'new_network_queries':0,'method_promotions':0,'scope_digest':scope_digest(i),'support_sources_digest':digest(support_sources(i,comparison)),'comparison_digest':digest(comparison),'announcement_digest':announcement_digest(ann),'prior_snapshot_digest':prior_digest}
    return {**p,'content_digest':digest(p)}

def experience_case_audit(i,comparison,ann):
    p=i.get('experience_case_audit')
    if p is None:return None
    if not comparison or not ann:raise ValueError('experience audit lacks its source views')
    if p['version']!=1 or p['question_id']!='first-up-followthrough-v1' or p['through']!=i['through']or p['scope_digest']!=scope_digest(i)or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('experience case audit binding changed')
    if p['comparison_digest']!=digest(comparison)or p['announcement_digest']!=announcement_digest(ann):raise ValueError('experience source comparison or corpus changed')
    if p['primary_horizon']!=comparison['default_days']or p['primary_horizon']!=20 or p['horizons']!=[5,20,40]or p['new_network_queries']!=0 or p['method_promotions']!=0:raise ValueError('experience audit question or promotion scope changed')
    support=support_sources(i,comparison)
    if p['support_sources_digest']!=digest(support):raise ValueError('case support source inventory changed')
    support_map={s['announcement_id']:s for s in support}
    source_rows=comparison['rows'];cal=i['calendar'];through=i['through']
    if len(source_rows)!=49 or len({r['symbol']for r in source_rows})!=49 or {era:sum(r['era']==era for r in source_rows)for era in ('pre','post')}!={'pre':37,'post':12}:raise ValueError('issuer case scope must not be inflated')
    rows=[]
    for src in source_rows:
        first=src['first_resume'];day=src['effective_on']
        if first['status']!='valid'or not isfinite(first['stock_pct'])or first['through']!=day or src['announced_on']>day:raise ValueError('first resumption classification lacks known-time evidence')
        follow={}
        for key in HORIZONS:
            w=src['windows'][key]['from_resume_close'];n=int(key)
            if w['anchor']!=day:raise ValueError('follow-through includes the first resumption unexpectedly')
            end=w['through'];dates=[d for d in cal if day<d<=end]if end else[]
            if end and (end>through or len(dates)!=n):raise ValueError('follow-up calendar was shortened')
            if w['status']=='valid'and (not end or any(w[k]is None or not isfinite(w[k])for k in ('stock_pct','market_pct','st_pct'))):raise ValueError('valid case lacks a complete matched window')
            certificate=w.get('action_support')or{};action_ids=list(certificate.get('source_ids',[]))
            if w['support_kind']=='verified_action_factor_reconstruction':action_ids+=[s['announcement_id']for s in support if s['symbol']==src['symbol']]
            strict=src['official_body']and not certificate.get('has_mirror',False)and all(support_map[aid]['host_is_official']for aid in action_ids)
            follow[key]={**w,'action_source_ids':action_ids,'official_only_eligible':strict,'market_dates':dates,'outcome':'up'if w['status']=='valid'and w['stock_pct']>0 else'down'if w['status']=='valid'and w['stock_pct']<0 else'flat'if w['status']=='valid'else'unresolved'}
        rows.append({'case_id':'WARNING-REMOVAL-'+src['symbol']+'-'+day,'symbol':src['symbol'],'name':src['name'],'era':src['era'],'announced_on':src['announced_on'],'effective_on':day,'first_up':first['stock_pct']>0,'first_resume':first,'follow':follow,'source':src['source'],'official_body':src['official_body']})
    tables={}
    for key in HORIZONS:
        tables[key]={}
        for level in ('all','official_only'):
            tables[key][level]={}
            for era in ('pre','post'):
                pool=[r for r in rows if r['era']==era];groups={};included=[]
                for name,up in (('first_up',True),('first_not_up',False)):
                    cases=[r for r in pool if r['first_up']==up];valid=[];excluded=[]
                    for r in cases:
                        w=r['follow'][key];reason=w['status']if w['status']!='valid'else'source_not_strict_official'if level=='official_only'and not w['official_only_eligible']else None
                        if reason:excluded.append({'case_id':r['case_id'],'symbol':r['symbol'],'reason':reason})
                        else:valid.append(r)
                    values=[r['follow'][key]['stock_pct']for r in valid];counts={state:sum(r['follow'][key]['outcome']==state for r in valid)for state in ('up','down','flat')}
                    groups[name]={'case_total':len(cases),'eligible':len(valid),'excluded':excluded,**counts,'up_pct':100*counts['up']/len(valid)if valid else None,'median_pct':median(values)if values else None,'symbols':[r['symbol']for r in valid]};included+=valid
                overlap=[]
                for a,b in combinations(included,2):
                    shared=set(a['follow'][key]['market_dates'])&set(b['follow'][key]['market_dates'])
                    if shared:overlap.append({'a':a['symbol'],'b':b['symbol'],'shared_days':len(shared)})
                concurrency={d:sum(d in r['follow'][key]['market_dates']for r in included)for d in cal}
                # Descriptive difference only. Neither the strata nor overlapping cases are random controls.
                x,y=groups['first_up']['up_pct'],groups['first_not_up']['up_pct']
                tables[key][level][era]={'total':len(pool),'groups':groups,'up_rate_difference_pp':x-y if x is not None and y is not None else None,'overlap_pair_count':len(overlap),'possible_pairs':len(included)*(len(included)-1)//2,'max_concurrent_cases':max(concurrency.values(),default=0),'overlap_pairs':overlap}
    repeated=[{'symbol':r['symbol'],'event_id':r['id'],'event_key':r['event_key'],'source_records':r['source_record_count'],'distinct_source_files':len({s['source']['sha256']for s in r.get('source_records',[r])})}for r in ann['verified_events']if r.get('source_record_count',1)>1]
    source_ids={r['source']['sha256']for r in rows};actions={aid for r in rows for w in r['follow'].values()for aid in w['action_source_ids']}
    counts={'companies':len(rows),'events':len(rows),'horizons':len(HORIZONS),'followup_measurements':len(rows)*len(HORIZONS),'valid_followup_measurements':sum(w['status']=='valid'for r in rows for w in r['follow'].values()),'primary_documents':len(source_ids),'reused_action_support_documents':len(actions),'corpus_documents':ann['verified_documents'],'corpus_fact_records':ann['raw_fact_records'],'corpus_reading_items':ann['deduplicated_event_count'],'corpus_companies':ann['verified_companies']}
    return {'through':through,'primary_horizon':20,'question':'摘帽首日上涨，能当成后续继续涨的经验吗？','answer':'现有案例不足以把首日上涨直接当作续涨信号。制度前后分组与5/20/40日读数不一致；保留支持案例和反例，不晋级为交易方法。','counts':counts,'tables':tables,'rows':rows,'support_sources':support,'repeated_reading_records':repeated,'prior_snapshot_digest':p['prior_snapshot_digest'],'method_promotions':0,'new_network_queries':0,'what_is_kept':'首日与后续分开、同窗比较并保留反例的核对方法；不是“首日上涨就会续涨”的收益经验。','not_established':'首日上涨是否提高未来上涨概率，仍未建立稳定、样本外可复验的结论。','what_would_change':['已核公告日期、实际成交端点或本公司复权构造更正时，按原规则重算，保留旧判断。','绝味、四通后续20/40市场日齐备后，补原两例，不当成新公司；停牌端点仍不缩窗。','新增不同公司案例须按事先冻结的身份、首日条件、20日窗口与来源门槛入组，纳入所有结果及退出，不能按涨跌挑样本。','若不同市场时期的新增公司与样本外对照反复支持稳定增益，才重新评估“尚无稳定信号”；同公司多日期、同事件多文件和换窗口不能充当新增验证。'],'boundary':'49家公司是49个不同公司事件案例，不是49次统计独立试验。制度前37与制度后12来自不同事后识别名单及时期；前组许多窗口跨7月6日，不能识别制度净因果。股票事件窗口共享市场日期，三种后续窗口重叠且重复使用同公司；上涨率差只是描述，不是经市场风险调整的预测优势。仅检查本研究既有案例，不称完整全市场摘帽事件库或全部公告事项的跨文档去重。'}
