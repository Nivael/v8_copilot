"""Bound public catalog dates; does not read announcement bodies or outcomes."""
from datetime import date,datetime,timedelta,timezone
from hashlib import sha256
import json,re
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from canonical_json import digest
from settings import DATA_ROOT

VERSION='node_publication_metadata_v1'
PROFILE_PATH=Path(__file__).with_name(VERSION+'.json')
PROFILE=json.loads(PROFILE_PATH.read_text())
PROFILE_DIGEST=digest(PROFILE)
OUTPUT=DATA_ROOT/'local_data/v8_copilot/market_risk/node_market_audit/publication_metadata'
LOOKUP='https://www.cninfo.com.cn/new/information/topSearch/query'
QUERY='https://www.cninfo.com.cn/new/hisAnnouncement/query'


def catalog_day(millis):
    if type(millis) is not int or not 1_000_000_000_000<=millis<10_000_000_000_000:raise ValueError('invalid catalog millisecond date')
    return datetime.fromtimestamp(millis//1000,ZoneInfo('Asia/Shanghai')).date().isoformat()


def stamp(value,now):
    result=datetime.fromisoformat(value)
    if result.tzinfo is None or result>now:raise ValueError('invalid metadata observation time')
    return result


def collect(directory,now):
    if PROFILE['version']!=VERSION or digest(json.loads(PROFILE_PATH.read_text()))!=PROFILE_DIGEST:raise ValueError('reload changed metadata profile')
    completed=stamp(PROFILE['capture_completed_at'],now);lookups={};queries={};refs={}
    for ref in PROFILE['metadata_refs']:
        label=ref['label'];params=ref['params'];observed=stamp(ref['observed_at'],completed)
        if label in refs or ref['method']!='POST' or ref['response_url']!=ref['url']:raise ValueError('metadata request identity mismatch')
        raw=(directory/(ref['response_sha256']+'.json')).read_bytes()
        if len(raw)!=ref['bytes'] or sha256(raw).hexdigest()!=ref['response_sha256']:raise ValueError('changed metadata bytes')
        data=json.loads(raw);refs[label]=ref
        if ref['url']==LOOKUP:
            code=params['keyWord']
            if params!={'keyWord':code,'maxNum':'10'} or label!='lookup-'+code or not re.fullmatch(r'\d{6}',code):raise ValueError('lookup scope changed')
            matching=[r for r in data if r['code']==code]
            if len(matching)!=1 or not matching[0]['orgId']:raise ValueError('lookup company ambiguous')
            lookups[code]=matching[0]['orgId']
        elif ref['url']==QUERY:
            code,org=params['stock'].split(',');start,end=params['seDate'].split('~')
            expected={'pageNum':'1','pageSize':'100','column':'sse' if code.startswith('6') else 'szse','tabName':'fulltext','plate':'sh' if code.startswith('6') else 'sz',
                      'stock':code+','+org,'searchkey':'','secid':'','category':'','trade':'','seDate':start+'~'+end,'sortName':'','sortType':'','isHLtitle':'true'}
            rows=data['announcements'] or []
            if (params!=expected or not re.fullmatch(r'\d{6}',code) or date.fromisoformat(start)>date.fromisoformat(end)
                or end>observed.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
                or data['hasMore'] is not False or data['totalAnnouncement']!=len(rows)
                or len({str(r['announcementId']) for r in rows})!=len(rows)
                or any(r['secCode']!=code or r['orgId']!=org or not start<=catalog_day(r['announcementTime'])<=end for r in rows)):
                raise ValueError('metadata query company, date or paging changed')
            queries[label]=(code,org,rows,ref)
        else:raise ValueError('foreign metadata endpoint')
    reviews=[];unbound=[];seen=set();events=set();used=set()
    for item in PROFILE['items']:
        code,source=item['symbol'],item['source_ref'];key=(code,source)
        if key in seen or not item['event_ids'] or len(set(item['event_ids']))!=len(item['event_ids']):raise ValueError('duplicate or empty document identity')
        if events.intersection(item['event_ids']):raise ValueError('event bound to multiple documents')
        seen.add(key);events.update(item['event_ids'])
        if item['status']=='noncanonical_source_id':
            if re.fullmatch(r'cninfo:\d+',source):raise ValueError('canonical source incorrectly excluded')
            unbound.append({'symbol':code,'source_ref':source,'event_count':len(item['event_ids']),'reason':'noncanonical_source_id'});continue
        if item['status']!='matched':raise ValueError('unreviewed metadata status')
        query=item['query_ref'];qcode,org,rows,ref=queries[query];used.add(query);used.add(item['lookup_ref'])
        if code!=qcode or org!=item['org_id'] or lookups.get(code)!=org or item['lookup_ref']!='lookup-'+code:raise ValueError('lookup/query company disagreement')
        if source!='cninfo:'+item['announcement_id'] or query!='notice-'+item['announcement_id']:raise ValueError('announcement identity changed')
        path=item['attachment_path'];hint=re.fullmatch(r'/finalpage/(\d{4}-\d{2}-\d{2})/(\d+)\.PDF',path)
        if not hint or hint[2]!=item['announcement_id'] or any(urlparse(u).hostname!='static.cninfo.com.cn' or urlparse(u).path!=path for u in item['parent_source_urls']):raise ValueError('parent attachment identity changed')
        matches=[r for r in rows if str(r['announcementId'])==item['announcement_id'] and '/'+r['adjunctUrl']==path]
        if len(matches)!=1:raise ValueError('catalog attachment missing or ambiguous')
        record=matches[0];day=catalog_day(record['announcementTime']);title=re.sub('<[^>]+>','',record['announcementTitle'])
        if (day!=item['official_catalog_date'] or day!=hint[1] or record['announcementTime']!=item['announcement_time_raw_ms'] or title!=item['title']
            or ref['params']['seDate']!=item['query_start']+'~'+item['query_end']):raise ValueError('catalog day/title/raw time changed')
        old=item['parent_published_dates'];utc_day=datetime.fromtimestamp(record['announcementTime']//1000,timezone.utc).date().isoformat()
        if not old or any(date.fromisoformat(d).isoformat()!=d for d in old):raise ValueError('invalid parent dates')
        bounds=[date.fromisoformat(d) for d in old+[hint[1]]]
        if (item['query_start'],item['query_end'])!=((min(bounds)-timedelta(days=1)).isoformat(),(max(bounds)+timedelta(days=1)).isoformat()):raise ValueError('parent/query date bounds changed')
        reviews.append({'document_id':source,'symbol':code,'official_catalog_date':day,'parent_published_dates':old,'source_url':'https://static.cninfo.com.cn'+path,
                        'title':title,'announcement_time_raw_ms':record['announcementTime'],'utc_interpretation_date':utc_day,
                        'utc_date_matches_parent':utc_day in old,'changed_from_parent_date':day not in old,'event_ids':item['event_ids'],
                        'availability':'observed','query_ref':query,'query_params':ref['params'],'response_sha256':ref['response_sha256'],'observed_at':ref['observed_at'],
                        'date_precision':'catalog_day_not_exact_release_timestamp'})
    if (len(seen)!=PROFILE['frame_document_items'] or len(events)!=PROFILE['frame_events'] or len({c for c,_ in seen})!=PROFILE['frame_companies']
        or used!=set(refs)):raise ValueError('metadata frame/reference coverage changed')
    return {'version':VERSION,'availability':'observed','frame_document_items':len(seen),'frame_events':len(events),'frame_companies':len({c for c,_ in seen}),
            'matched_documents':len(reviews),'matched_events':sum(len(r['event_ids']) for r in reviews),'unbound_documents':len(unbound),'metadata_responses':len(refs),
            'changed_parent_date_documents':sum(r['changed_from_parent_date'] for r in reviews),'reviews':reviews,'unbound':unbound,
            'p6_run':PROFILE['p6_run'],'captured_at':PROFILE['capture_completed_at'],'profile_digest':PROFILE_DIGEST,
            'historical_PIT':False,'full_body_semantics_checked':False,'exact_release_timestamps_verified':False}


def metadata_status(p6_run,directory=OUTPUT,now=None):
    base={'version':VERSION,'availability':'missing','reviews':[],'matched_documents':None,'matched_events':None,'unbound_documents':None,
          'historical_PIT':False,'full_body_semantics_checked':False,'exact_release_timestamps_verified':False}
    if p6_run!=PROFILE['p6_run']:return {**base,'availability':'source_frame_changed'}
    try:return collect(directory,now or datetime.now(timezone.utc))
    except (OSError,ValueError,TypeError,KeyError,IndexError,AttributeError):return {**base,'availability':'invalid' if directory.exists() else 'missing'}
