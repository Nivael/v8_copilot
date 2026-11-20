from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json
import pytest
from canonical_json import digest
from market_breadth_export import EXPORT_KIND,EXPORT_URL,export_params,parse_export
from exchange_risk_membership import SZSE_API
from recent_breadth_inputs import verify_szse_day,verify_szse_capture
import test_market_breadth_export as fixture
DAY='2026-11-20';NOW=datetime(2026,11,20,17,tzinfo=timezone.utc)

def ready(p):
 rows=fixture.records()
 for r in rows:r['jyrq']=DAY
 head,tail=fixture.controls(rows);body=fixture.workbook(rows);params={'SHOWTYPE':'JSON','CATALOGID':'1815_stock_snapshot','TABKEY':'tab1','txtBeginDate':DAY,'txtEndDate':DAY}
 refs=[];(p/'responses').mkdir(parents=True)
 for payload,url,query,kind in [(head,SZSE_API,{**params,'PAGENO':1},None),(tail,SZSE_API,{**params,'PAGENO':2},None),(body,EXPORT_URL,export_params(DAY),EXPORT_KIND)]:
  raw=payload if isinstance(payload,bytes) else json.dumps(payload).encode();key=sha256(raw).hexdigest();(p/'responses'/(key+('.xlsx'if kind else'.json'))).write_bytes(raw)
  r={'venue':'SZSE','url':url,'params':query,'response_sha256':key,'bytes':len(raw),'observed_at':NOW.isoformat()}
  if kind:r['kind']=kind
  refs.append(r)
 d={'version':'recent_szse_breadth_day_v1','date':DAY,'scope':'SZSE_A_shares_only','responses':refs,'block':parse_export(body,head,tail,DAY),'observed_at':NOW.isoformat(),'materialized_at':NOW.isoformat()};d['content_digest']=digest(d)
 (p/'days').mkdir();(p/'days'/(DAY+'.json')).write_text(json.dumps(d))
 c={'version':'recent_szse_breadth_capture_v1','scope':'SZSE_A_shares_only','start':DAY,'through':DAY,'calendar':[DAY],'days':{DAY:d['content_digest']},'completed_at':NOW.isoformat()};c['content_digest']=digest(c);(p/'complete.json').write_text(json.dumps(c));return d

def test_shanghai_closed_date_after_utc_midnight_boundary_and_single_venue_never_whole_market(tmp_path):
 d=ready(tmp_path);r=verify_szse_capture(tmp_path,now=NOW)
 assert len(r['points'])==1 and not r['complete_market_history'] and r['missing_venues']==['SSE']
 assert verify_szse_day(d,tmp_path,now=NOW)['all']['declining']==11
 with pytest.raises(ValueError):verify_szse_day(d,tmp_path,now=NOW.replace(tzinfo=None))

@pytest.mark.parametrize('change',['bytes','projection','source','missing_control','future','query'])
def test_source_changes_are_not_accepted_as_recent_venue_history(change,tmp_path):
 d=ready(tmp_path)
 if change=='bytes':(tmp_path/'responses'/(d['responses'][2]['response_sha256']+'.xlsx')).write_bytes(b'changed')
 elif change=='projection':d['block']['rows'][0]['security_name']='changed'
 elif change=='source':d['responses'][1]['url']='http://untrusted.example'
 elif change=='missing_control':d['responses'].pop(1)
 elif change=='future':d['responses'][0]['observed_at']='2027-01-01T00:00:00+00:00'
 else:d['responses'][0]['params']['txtBeginDate']='2026-11-19'
 d.pop('content_digest');d['content_digest']=digest(d)
 with pytest.raises(ValueError):verify_szse_day(d,tmp_path,now=NOW)

def test_missing_trade_date_does_not_get_bridged(tmp_path):
 ready(tmp_path);c=json.loads((tmp_path/'complete.json').read_text());c['start']='2026-11-19';c.pop('content_digest');c['content_digest']=digest(c);(tmp_path/'complete.json').write_text(json.dumps(c))
 with pytest.raises(ValueError):verify_szse_capture(tmp_path,now=NOW)
