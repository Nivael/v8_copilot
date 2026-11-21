"""Dated SZSE risk-list evidence separated from undated current observations."""
from datetime import datetime
from hashlib import sha256
import json
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
from exchange_risk_membership import (SZSE_API,SSE_API,PROOFS,parameters,definition_fragment,szse_table,sse_table)


def review(e):
    sources={s['key']:s for s in e['sources']}
    expected={'szse_risk:'+str(n)for n in range(1,7)}|{'szse_delisting:1','sse_main_risk','szse_definition','sse_definition'}
    if set(sources)!=expected or len(sources)!=len(e['sources']):raise ValueError('all selected list pages and definitions required')
    def load(key,url,params):
        src=sources[key];raw=src['text'].encode()
        if src['url']!=url or src['params']!=params or src['final_url']!=url+('?' + urlencode(params)if params else''):raise ValueError('source request identity changed')
        if sha256(raw).hexdigest()!=src['response_sha256']or len(raw)!=src['bytes']:raise ValueError('source bytes changed')
        observed=datetime.fromisoformat(src['observed_at'])
        if observed.tzinfo is None or observed.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()!=e['observation_day']:raise ValueError('observation date changed')
        return src['text']
    for key,(url,expected_sha)in PROOFS.items():
        if sha256(definition_fragment(key,load(key,url,{})).encode()).hexdigest()!=expected_sha:raise ValueError('list definition changed')
    records=[];control=None
    for n in range(1,7):
        page=json.loads(load('szse_risk:'+str(n),SZSE_API,parameters('szse_risk',n)))
        rows,meta=szse_table('szse_risk',page,n,e['source_target_day'])
        if control is None:control=meta
        if control!=meta or meta[1]!=6:raise ValueError('SZSE pagination changed')
        records.extend(rows)
    if len(records)!=control[0]or len({r['ts_code']for r in records})!=len(records):raise ValueError('incomplete or duplicate SZSE roster')
    sse_raw=json.loads(load('sse_main_risk',SSE_API,parameters('sse_main_risk')));sse=sse_table('sse_main_risk',sse_raw)
    if sse_raw.get('queryDate')not in ('',None):raise ValueError('SSE date now supplied; requires new review')
    empty_raw=json.loads(load('szse_delisting:1',SZSE_API,parameters('szse_delisting')))
    empty,empty_meta=szse_table('szse_delisting',empty_raw,1,'')
    if empty or empty_meta[0]!=0:raise ValueError('undated empty table changed; requires new review')
    prior={r['symbol']:r['name']for r in e['prior_main_members']}
    def main(r):return r['share_class']=='A'and r['ts_code'].startswith(('000','001','002','003','600','601','603','605'))
    comparisons=[]
    for key,rows,suffix,asof in [('szse_risk',records,'.SZ',e['source_target_day']),('sse_main_risk',sse,'.SH',None)]:
        selected=[r for r in rows if main(r)];codes={r['ts_code']for r in selected};old={c for c in prior if c.endswith(suffix)}
        comparisons.append({'group':key,'source_as_of':asof,'observed_on':e['observation_day'],'all_rows':len(rows),'a_shares':sum(r['share_class']=='A'for r in rows),'b_shares':sum(r['share_class']=='B'for r in rows),'main_a_shares':len(selected),
                            'prior_reference_day':e['prior_reference_day'],'codes_equal_prior':codes==old,'new_codes':sorted(codes-old),'absent_codes':sorted(old-codes),
                            'name_differences':[{'symbol':r['ts_code'],'official':r['name'],'prior':prior.get(r['ts_code'])}for r in selected if r['name']!=prior.get(r['ts_code'])],
                            'rows':selected})
    return {'version':'mainboard_risk_list_nov20_review_v1','target_day':e['source_target_day'],'observation_day':e['observation_day'],'comparisons':comparisons,
            'szse_delisting_empty_source_as_of':None,'complete_two_venue_target_membership':False,
            'boundary':'深市风险警示表明确20日适用日期，沪市当前列表未声明数据日，不能因代码简称与19日供应商相同就认证沪市20日法定名单。深市退市整理空表也未声明日期，不当作20日零记录证明。仅主板A股对照，创业/科创/B股范围分别保留。读取日不是适用日，不倒填历史时点已知。','independent_validations_added':0}
