"""Resumable Jul-Aug SZSE raw exports; does not publish market conclusions."""
from pathlib import Path
from datetime import datetime,timezone,date
from hashlib import sha256
from urllib.request import Request,urlopen
from urllib.parse import urlencode
import json,time
from canonical_json import digest
from data_refresh import atomic_write_json
from market_calendar import sessions_2026
from market_breadth import SOURCES,cross_section
from market_breadth_export import HistoricalExportClient,EXPORT_URL,export_params,parse_export
from exchange_risk_membership import SZSE_API
import argparse
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--folder',type=Path,required=True);args=parser.parse_args()
p=args.folder;p.mkdir(parents=True,exist_ok=True)
client=HistoricalExportClient(p,repair=True)
calendar=sessions_2026(date(2026,7,1),date(2026,8,31));days=[]
def json_source(url,params):
 q=digest({'url':url,'params':params});cache=p/'cache'/(q+'.json')
 if cache.exists():
  ref=json.loads(cache.read_text());body=(p/'responses'/(ref['response_sha256']+'.json')).read_bytes();assert sha256(body).hexdigest()==ref['response_sha256'];return json.loads(body),ref
 time.sleep(.4)
 with urlopen(Request(url+'?'+urlencode(params),headers={'User-Agent':'Mozilla/5.0','Referer':SOURCES['SZSE']['url']}),timeout=20)as response:body=response.read(4000001)
 assert len(body)<=4000000
 result=json.loads(body);key=sha256(body).hexdigest();(p/'responses').mkdir(exist_ok=True);(p/'responses'/(key+'.json')).write_bytes(body)
 ref={'venue':'SZSE','url':url,'params':params,'response_sha256':key,'bytes':len(body),'observed_at':datetime.now(timezone.utc).isoformat()};atomic_write_json(cache,ref);return result,ref
for day in calendar:
 target=p/'days'/(day+'.json')
 if target.exists():
  d=json.loads(target.read_text());assert digest({k:v for k,v in d.items() if k!='content_digest'})==d['content_digest'];days.append(d);continue
 params={'SHOWTYPE':'JSON','CATALOGID':SOURCES['SZSE']['catalog'],'TABKEY':'tab1','txtBeginDate':day,'txtEndDate':day}
 try:
  head,first=json_source(SZSE_API,{**params,'PAGENO':1});count=head[0]['metadata']['pagecount']
  assert type(count)is int and 1<=count<=700
  tail,last=json_source(SZSE_API,{**params,'PAGENO':count});body,export=client._export(day);refs=[first,last,export]
  block=parse_export(body,head,tail,day)
  data={'version':'recent_szse_breadth_day_v1','date':day,'scope':'SZSE_A_shares_only','responses':refs,'block':block,'observed_at':max(r['observed_at'] for r in refs),'materialized_at':datetime.now(timezone.utc).isoformat()};data['content_digest']=digest(data);atomic_write_json(target,data);days.append(data);print(json.dumps({'date':day,'completed':len(days),'expected':len(calendar),'listed':len(block['rows'])}),flush=True)
 except Exception as e:
  print(json.dumps({'date':day,'error_type':type(e).__name__,'completed':len(days),'expected':len(calendar)}),flush=True);raise
raw={'version':'recent_szse_breadth_capture_v1','scope':'SZSE_A_shares_only','start':calendar[0],'through':calendar[-1],'calendar':calendar,'days':{d['date']:d['content_digest'] for d in days},'completed_at':datetime.now(timezone.utc).isoformat()};raw['content_digest']=digest(raw);atomic_write_json(p/'complete.json',raw)
print(json.dumps({'status':'complete','days':len(days),'scope':raw['scope']}),flush=True)
