"""Replay official lookup/catalog and identical mirror PDF before changing source label."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime
from zoneinfo import ZoneInfo
import json


def reading():
    path=Path('HUAWEI_OFFICIAL_DIVIDEND_RECOVERY_2026_11_21.json');e=json.loads(path.read_text());p=e['pdf'];store=Path(p['source_store']);refs=e['catalog_refs']
    def original(ref):
        raw=(store/(ref['sha256']+'.bin')).read_bytes()
        if len(raw)!=ref['bytes'] or sha256(raw).hexdigest()!=ref['sha256'] or ref['status']!=200:raise ValueError('catalog source differs')
        return json.loads(raw)
    lookup,query=refs
    if lookup['url']!='https://www.cninfo.com.cn/new/information/topSearch/query' or lookup['params']!={'keyWord':'600360','maxNum':'10'}:raise ValueError('lookup request differs')
    matches=[r for r in original(lookup) if r['code']=='600360']
    if len(matches)!=1:raise ValueError('ambiguous issuer')
    params={'pageNum':'1','pageSize':'30','column':'sse','tabName':'fulltext','plate':'sh','stock':'600360,'+matches[0]['orgId'],'searchkey':'','secid':'','category':'','trade':'','seDate':'2026-10-21~2026-10-21','sortName':'','sortType':'','isHLtitle':'true'}
    if query['url']!='https://www.cninfo.com.cn/new/hisAnnouncement/query' or query['params']!=params:raise ValueError('catalog scope differs')
    catalog=original(query)
    if catalog['totalAnnouncement']!=1 or catalog['hasMore'] is not False or len(catalog['announcements'])!=1:raise ValueError('catalog coverage differs')
    row=catalog['announcements'][0]
    if row['secCode']!='600360' or row['orgId']!=matches[0]['orgId'] or str(row['announcementId'])!='1225611990' or datetime.fromtimestamp(row['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()!='2026-10-21':raise ValueError('official event differs')
    url='https://static.cninfo.com.cn/'+row['adjunctUrl']
    if url!=p['url'] or p['final_url']!=url or p['status']!=200:raise ValueError('PDF request differs')
    raw=(store/(p['sha256']+'.pdf')).read_bytes()
    if not raw.startswith(b'%PDF-') or len(raw)!=p['bytes'] or sha256(raw).hexdigest()!=p['sha256']:raise ValueError('PDF bytes differ')
    debt=json.loads(Path('OFFICIAL_MIRROR_RECOVERY_QUEUE_2026_11_21.json').read_text());old=next(r for r in debt['rows'] if r['announcement_id']==e['mirror_id'])
    if old['symbol']!='600360' or old['sha256']!=p['sha256'] or not p['exact_mirror_bytes']:raise ValueError('mirror bytes differ')
    return dict(evidence_sha256=sha256(path.read_bytes()).hexdigest(),mirror_id=old['announcement_id'],mirror_sha256=old['sha256'],official_id=str(row['announcementId']),official_url=url,published_on='2026-10-21',viewed_pages=e['viewed_pages'],total_pages=e['total_pages'])

if __name__=='__main__':
    Path('web/src/huaweiOfficialDividend.json').write_text(json.dumps(reading(),ensure_ascii=False,indent=2)+'\n')
