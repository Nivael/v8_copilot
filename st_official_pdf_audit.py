"""Corroborate mirrored bytes from an official disclosure host, without new facts."""
from urllib.parse import urlparse
from canonical_json import digest

OFFICIAL_IDS={'1225312843','1225337556','1225368908','1225368522','1225378259','1225397352','1225463681','1225611990'}

def official_pdf_audit(inputs,ann):
 p=inputs.get('official_pdf_audit')
 if p is None:return None
 if p['version']!=1 or p['through']!=inputs['through']or p['prior_announcement_digest']!=digest(ann)or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('official-copy audit scope changed')
 mirrors={s['sha256']:s for e in ann['verified_events']for s in [e['source'],*e.get('supporting_sources',[])]if s.get('host_is_official')is False}
 rows=p['rows']
 if len(rows)!=8 or {r['mirror_sha256']for r in rows}!=set(mirrors)or {r['official_id']for r in rows}!=OFFICIAL_IDS:raise ValueError('official-copy audit source inventory changed')
 for r in rows:
  old=mirrors[r['mirror_sha256']];meta=r['metadata']
  if r['official_sha256']!=old['sha256']or r['symbol']!=old['symbol']or r['pages']!=old['pages']or not r['protected_gate_passed']:raise ValueError('copy bytes or company differ')
  if meta['secCode']!=r['symbol']or meta['announcementId']!=r['official_id']or meta['announcementTitle']!=r['official_title']:raise ValueError('official metadata identity differs')
  if urlparse(r['official_url']).hostname!='static.cninfo.com.cn'or r['official_url']!='https://static.cninfo.com.cn/'+meta['adjunctUrl']or r['published_on']not in meta['adjunctUrl']:raise ValueError('official URL/date identity differs')
  if r['catalog_url']!=old['catalog_url']or r['mirror_url']!=old['url']or r['catalog_id']!=old['catalog_announcement_id']:raise ValueError('old source provenance changed')
  if r['sse_direct_verified']is not False or r['sse_attempt']['pdf']is not False:raise ValueError('failed SSE fetch cannot be certified')
 if p['method_promotions']!=0 or p['new_facts']!=0:raise ValueError('same source copies cannot create facts or methods')
 return {'through':p['through'],'rows':rows,'official_copies':len(rows),'affected_companies':len({r['symbol']for r in rows}),'pages':sum(r['pages']for r in rows),'byte_identical':len(rows),'remaining_official_copy_gaps':0,'remaining_sse_direct_gaps':len(rows),'new_facts':0,'new_unique_documents':0,'method_promotions':0,'boundary':'已取得巨潮正式披露PDF且与原镜像逐字节相同；交易所直链仍未返回可核PDF。是同一发行人同一文件的来源补强，不是新增独立事实、案例或经验验证；旧镜像记录与来源标签保留供追溯。'}
