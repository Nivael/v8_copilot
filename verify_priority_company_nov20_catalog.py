"""Replay bounded empty catalog responses without inferring legal or reporting absence."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime,date
from zoneinfo import ZoneInfo
import json


def verify(e):
    if e['query_date']!='2026-11-20'or [c['code']for c in e['companies']]!=['002717','600165','601718','000826']:raise ValueError('scope changed')
    root=Path(e['source_store']);used=[];rows=[]
    def body(ref):
        raw=(root/(ref['sha256']+'.json')).read_bytes()
        if len(raw)!=ref['bytes']or sha256(raw).hexdigest()!=ref['sha256']:raise ValueError('source bytes changed')
        at=datetime.fromisoformat(ref['observed_at'])
        if at.tzinfo is None or at.astimezone(ZoneInfo('Asia/Shanghai')).date()<date(2026,11,20):raise ValueError('observation date changed')
        used.append(ref);return json.loads(raw)
    for c in e['companies']:
        code=c['code'];lookup=c['lookup']
        if c['status']!='captured'or lookup['url']!='https://www.cninfo.com.cn/new/information/topSearch/query'or lookup['params']!={'keyWord':code,'maxNum':'10'}:raise ValueError('lookup scope changed')
        matches=[r for r in body(lookup)if r['code']==code]
        if len(matches)!=1 or matches[0]['orgId']!=c['org_id']:raise ValueError('organization identity differs')
        if len(c['pages'])!=1 or c['rows']!=[]or c['total']!=0:raise ValueError('this empty-response audit requires new review for nonempty results')
        ref=c['pages'][0];expected={'pageNum':'1','pageSize':'30','column':'sse'if code.startswith('6')else'szse','tabName':'fulltext','plate':'sh'if code.startswith('6')else'sz','stock':code+','+c['org_id'],'searchkey':'','secid':'','category':'','trade':'','seDate':'2026-11-20~2026-11-20','sortName':'','sortType':'','isHLtitle':'true'}
        if ref['url']!='https://www.cninfo.com.cn/new/hisAnnouncement/query'or ref['params']!=expected:raise ValueError('catalog query changed')
        p=body(ref)
        if p['totalAnnouncement']!=0 or p['totalRecordNum']!=0 or p['totalpages']!=0 or p['hasMore']is not False or p['announcements']not in(None,[]):raise ValueError('empty declaration differs')
        rows.append(dict(code=code,requested_date=e['query_date'],reported_records=0,source_data_date=None,response_sha256=ref['sha256']))
    if used!=e['all_source_refs']:raise ValueError('source manifest differs')
    return dict(companies=rows,query_count=len(rows),unique_empty_response_bodies=len({r['response_sha256']for r in rows}),new_body_candidates=0,legal_or_financial_status_changed=False)


if __name__=='__main__':
    e=json.loads(Path('PRIORITY_COMPANY_NOV20_CATALOG_EVIDENCE_2026_11_21.json').read_text());print(json.dumps(verify(e),ensure_ascii=False,indent=2))
