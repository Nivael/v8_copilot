"""Read-only official-catalog to exact retained-mirror byte audit."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime
from zoneinfo import ZoneInfo
import json,re


def audit(path=Path('REMAINING_OFFICIAL_RECOVERY_CAPTURE_2026_11_21.json')):
    capture=json.loads(Path(path).read_text());store=Path(capture['source_store'])
    queue=json.loads(Path('OFFICIAL_MIRROR_RECOVERY_QUEUE_2026_11_21.json').read_text())
    expected={r['announcement_id']:r for r in queue['rows'] if r['symbol']!='600360'}
    rows=capture['rows']
    if len(rows)!=7 or {r['mirror']['announcement_id'] for r in rows}!=set(expected):raise ValueError('seven original notices required')
    def original(ref):
        raw=(store/(ref['sha256']+'.bin')).read_bytes()
        if sha256(raw).hexdigest()!=ref['sha256'] or len(raw)!=ref['bytes'] or ref['status']!=200 or ref['method']!='POST':raise ValueError('catalog bytes differ')
        return json.loads(raw)
    verified=[]
    for result in rows:
        item=result['mirror'];code=item['symbol'];aid=item['announcement_id']
        if item!=expected[aid] or result['status']!='exact_pdf_bytes':raise ValueError('mirror identity or outcome differs')
        if len(result['refs'])!=2:raise ValueError('lookup/catalog pair required')
        lookup,query=result['refs']
        if lookup['url']!='https://www.cninfo.com.cn/new/information/topSearch/query' or lookup['params']!={'keyWord':code,'maxNum':'10'}:raise ValueError('lookup scope differs')
        issuer=[r for r in original(lookup) if r['code']==code]
        if len(issuer)!=1:raise ValueError('issuer not unique')
        day=re.search(r'/(2026-\d\d-\d\d)/',item['url'])[1]
        params={'pageNum':'1','pageSize':'30','column':'sse','tabName':'fulltext','plate':'sh','stock':code+','+issuer[0]['orgId'],'searchkey':'','secid':'','category':'','trade':'','seDate':day+'~'+day,'sortName':'','sortType':'','isHLtitle':'true'}
        if query['url']!='https://www.cninfo.com.cn/new/hisAnnouncement/query' or query['params']!=params:raise ValueError('catalog request differs')
        catalog=original(query);announcements=catalog['announcements'] or []
        if catalog['hasMore'] is not False or catalog['totalAnnouncement']!=len(announcements) or len(announcements)>=30:raise ValueError('catalog incomplete')
        for r in announcements:
            if r['secCode']!=code or r['orgId']!=issuer[0]['orgId'] or datetime.fromtimestamp(r['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()!=day:raise ValueError('catalog identity/date differs')
        selected=[r for r in announcements if ('权益分派实施公告' in r['announcementTitle'] if '权益分派' in item['title'] else '撤销退市风险警示' in r['announcementTitle'] and not any(w in r['announcementTitle'] for w in ('申请','进展','提示')))]
        if len(selected)!=1 or selected!=result['candidate_rows']:raise ValueError('notice selection differs')
        r=selected[0];pdf=result['pdf'];url='https://static.cninfo.com.cn/'+r['adjunctUrl']
        if pdf['url']!=url or pdf['final_url']!=url or pdf['status']!=200:raise ValueError('PDF request differs')
        raw=(store/(pdf['sha256']+'.pdf')).read_bytes()
        if not raw.startswith(b'%PDF-') or sha256(raw).hexdigest()!=item['sha256'] or sha256(raw).hexdigest()!=pdf['sha256'] or len(raw)!=pdf['bytes']:raise ValueError('PDF/mirror bytes differ')
        verified.append(dict(symbol=code,mirror_id=aid,mirror_sha256=item['sha256'],official_id=str(r['announcementId']),official_url=url,published_on=day,title=r['announcementTitle'],bytes=len(raw)))
    return dict(version='remaining_official_recovery_audit_v1',capture_sha256=sha256(Path(path).read_bytes()).hexdigest(),verified=verified,verified_count=len(verified),new_independent_validations=0,limits=['Source byte recovery only; not a new event or full-page rereview','Official availability observed retrospectively, not proof of then-known access','Exact byte equality preserves old content; does not certify accounting truth or actual cash receipt'])

if __name__=='__main__':
    result=audit();Path('REMAINING_OFFICIAL_RECOVERY_AUDIT_2026_11_21.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(result['verified_count'])
