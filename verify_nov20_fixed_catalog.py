"""Verify one-day fixed-group catalog capture; titles are not reviewed facts."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime,date
from zoneinfo import ZoneInfo
import json,re


def verify(e):
    pp=Path('NOV20_FIXED_CATALOG_PLAN_2026_11_21.json');plan=json.loads(pp.read_text())
    if sha256(pp.read_bytes()).hexdigest()!=e['plan_sha256']or e['query_date']!='2026-11-20':raise ValueError('plan changed')
    symbols=plan['fixed_symbols'];companies=e['companies']
    if len(set(symbols))!=len(symbols)or len(symbols)!=150 or [c['code']for c in companies]!=symbols:raise ValueError('fixed scope differs')
    cp=Path('CATALOG_POSITIVE_CONTROL_EVIDENCE_2026_11_21.json');control=json.loads(cp.read_text())
    if sha256(cp.read_bytes()).hexdigest()!=plan['positive_control_sha256']:raise ValueError('positive control identity changed')
    def source(root,ref):
        raw=(Path(root)/(ref['sha256']+'.json')).read_bytes()
        if sha256(raw).hexdigest()!=ref['sha256']or len(raw)!=ref['bytes']:raise ValueError('source bytes changed')
        at=datetime.fromisoformat(ref['observed_at'])
        if at.tzinfo is None or at.astimezone(ZoneInfo('Asia/Shanghai')).date()<date(2026,11,20):raise ValueError('source observation changed')
        return json.loads(raw)
    known=source(control['source_store'],control)
    if control['params']['seDate']!='2026-11-12~2026-11-12'or not any(r['secCode']=='002717'and r['announcementId']=='1225667855'for r in known['announcements']):raise ValueError('known positive row missing')
    captured=0;gaps=[];seen_rows=[];empty_hashes=set();page_count=0
    for c in companies:
        code=c['code'];identity=plan['identities'][code];r=identity['identity_source'];raw=Path(r['locator']).read_bytes()
        if sha256(raw).hexdigest()!=r['sha256']or len(raw)!=r['bytes']:raise ValueError('identity source changed')
        orgs={a['orgId']for a in json.loads(raw)['announcements']if a['secCode']==code}
        if orgs!={identity['org_id']}or c['org_id']!=identity['org_id']:raise ValueError('organization changed')
        if c['status']!='captured':
            if not c.get('error'):raise ValueError('unresolved reason missing')
            gaps.append(dict(code=code,error=c['error']));continue
        actual=[];total=None
        if not c['pages']:raise ValueError('no query pages')
        for page,ref in enumerate(c['pages'],1):
            expected={'pageNum':str(page),'pageSize':'30','column':'sse'if code.startswith('6')else'szse','tabName':'fulltext','plate':'sh'if code.startswith('6')else'sz','stock':code+','+identity['org_id'],'searchkey':'','secid':'','category':'','trade':'','seDate':'2026-11-20~2026-11-20','sortName':'','sortType':'','isHLtitle':'true'}
            if ref['url']!='https://www.cninfo.com.cn/new/hisAnnouncement/query'or ref['params']!=expected:raise ValueError('query scope differs')
            p=source(e['source_store'],ref);n=p['totalAnnouncement'];more=p['hasMore'];items=p['announcements']
            if type(n)is not int or type(more)is not bool or n<0:raise ValueError('invalid declared total')
            if total is None:total=n
            if n!=total or more!=(page<len(c['pages'])):raise ValueError('pagination differs')
            if items is None:
                if n!=0 or more:raise ValueError('null rows not declared empty')
                items=[]
            if not isinstance(items,list)or len(items)!=min(30,max(0,n-(page-1)*30)):raise ValueError('page row count differs')
            actual.extend(items);page_count+=1
            if n==0:empty_hashes.add(ref['sha256'])
        if actual!=c['rows']or len(actual)!=c['total']or len({r['announcementId']for r in actual})!=len(actual):raise ValueError('complete query rows differ')
        for row in actual:
            if row['secCode']!=code or not re.search(r'/2026-11-20/',row['adjunctUrl']):raise ValueError('foreign date/security')
            seen_rows.append(row)
        captured+=1
    identities={}
    for row in seen_rows:
        key=(row['announcementId'],row['adjunctUrl'])
        if key not in identities:identities[key]=dict(announcement_id=key[0],adjunct_url=key[1],title=row['announcementTitle'],codes=[])
        if row['secCode']not in identities[key]['codes']:identities[key]['codes'].append(row['secCode'])
    return dict(requested_companies=150,captured_companies=captured,unresolved=gaps,query_pages=page_count,title_sightings=len(seen_rows),unique_attachment_identities=len(identities),nonempty_companies=sum(c.get('total',0)>0 for c in companies if c['status']=='captured'),unique_empty_response_bodies=len(empty_hashes),titles=list(identities.values()),positive_control_matched=True,body_reviewed=0)


if __name__=='__main__':
    e=json.loads(Path('NOV20_FIXED_CATALOG_EVIDENCE_2026_11_21.json').read_text());r=verify(e);Path('NOV20_FIXED_CATALOG_REVIEW_2026_11_21.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False,indent=2))
