"""Verify recent venue inputs independently; a single venue is never whole-market breadth."""
from datetime import date,datetime,timezone
from pathlib import Path
from hashlib import sha256
import json
from zoneinfo import ZoneInfo
from canonical_json import digest
from market_calendar import sessions_2026
from market_breadth import SOURCES,cross_section
from market_breadth_export import EXPORT_URL,EXPORT_KIND,export_params,parse_export
from exchange_risk_membership import SZSE_API


def instant(text,now):
    value=datetime.fromisoformat(text)
    if value.tzinfo is None or value>now:raise ValueError('invalid source observation time')
    return value

def verify_szse_day(packet,folder,*,now=None):
    now=now or datetime.now(timezone.utc);folder=Path(folder)
    if now.tzinfo is None:raise ValueError('timezone-aware verification required')
    if (packet['version']!='recent_szse_breadth_day_v1' or packet['scope']!='SZSE_A_shares_only'
        or digest({k:v for k,v in packet.items()if k!='content_digest'})!=packet['content_digest']):raise ValueError('venue day binding changed')
    day=packet['date'];d=date.fromisoformat(day)
    if sessions_2026(d,d)!=[day] or d>=now.astimezone(ZoneInfo('Asia/Shanghai')).date():raise ValueError('closed trading date required')
    observed=instant(packet['observed_at'],now);materialized=instant(packet['materialized_at'],now)
    if observed>materialized:raise ValueError('materialization predates source')
    refs=packet['responses']
    if len(refs)!=3:raise ValueError('export and both control pages required')
    params={'SHOWTYPE':'JSON','CATALOGID':SOURCES['SZSE']['catalog'],'TABKEY':'tab1','txtBeginDate':day,'txtEndDate':day}
    def body(ref,expected,export=False):
        allowed=(EXPORT_URL,)if export else(SOURCES['SZSE']['api_url'],SZSE_API)
        if ref['venue']!='SZSE' or ref['url']not in allowed or ref['params']!=expected or (export and ref.get('kind')!=EXPORT_KIND) or (not export and ref.get('kind')is not None):raise ValueError('venue source or full query changed')
        then=instant(ref['observed_at'],now)
        if then>observed or then.astimezone(ZoneInfo('Asia/Shanghai')).date()<d:raise ValueError('source chronology changed')
        key=ref['response_sha256']
        if len(key)!=64 or any(c not in '0123456789abcdef'for c in key):raise ValueError('invalid original identity')
        raw=(folder/'responses'/(key+('.xlsx'if export else'.json'))).read_bytes()
        if len(raw)!=ref['bytes']or sha256(raw).hexdigest()!=key:raise ValueError('original bytes changed')
        return raw if export else json.loads(raw)
    head=body(refs[0],{**params,'PAGENO':1});count=head[0]['metadata']['pagecount']
    tail=body(refs[1],{**params,'PAGENO':count});raw=body(refs[2],export_params(day),True)
    block=parse_export(raw,head,tail,day)
    if block!=packet['block']or max(instant(r['observed_at'],now)for r in refs)!=observed:raise ValueError('normalized source or observation time changed')
    return {'date':day,'scope':'SZSE_A_shares_only','source_digest':packet['content_digest'],'all':cross_section(block['rows'])}


def verify_szse_capture(folder,*,now=None):
    folder=Path(folder);now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError('timezone-aware verification required')
    raw=json.loads((folder/'complete.json').read_text())
    calendar=sessions_2026(date.fromisoformat(raw['start']),date.fromisoformat(raw['through']))
    if(raw['version']!='recent_szse_breadth_capture_v1'or raw['scope']!='SZSE_A_shares_only'or raw['calendar']!=calendar
       or set(raw['days'])!=set(calendar)or digest({k:v for k,v in raw.items()if k!='content_digest'})!=raw['content_digest']):raise ValueError('venue history is incomplete or changed')
    completed=instant(raw['completed_at'],now);points=[]
    for day in calendar:
        packet=json.loads((folder/'days'/(day+'.json')).read_text())
        if packet['date']!=day or packet['content_digest']!=raw['days'][day]or instant(packet['materialized_at'],now)>completed:raise ValueError('venue day pointer changed')
        points.append(verify_szse_day(packet,folder,now=now))
    return {'version':'recent_szse_verified_breadth_v1','scope':'SZSE_A_shares_only','complete_market_history':False,
            'missing_venues':['SSE'],'historical_PIT':False,'start':raw['start'],'through':raw['through'],
            'source_digest':raw['content_digest'],'points':points,'source_files':len(points)*3}
