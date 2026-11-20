from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
import json

import pytest
from canonical_json import digest
from market_breadth import SOURCES,SSE_SELECT
from market_breadth_refresh import parse_sse,parse_szse,refresh_public_breadth
from market_breadth_export import EXPORT_URL,EXPORT_KIND,export_params,parse_export
from exchange_risk_membership import SZSE_API
from latest_breadth_reading import verified_breadth,newer_breadth
import test_market_breadth_public as fixture
import test_market_breadth_export as export_fixture

DAY='2026-09-04';NOW=datetime(2026,11,5,tzinfo=timezone.utc)

def ready(path,export=False):
 def ref(venue,payload,params,url=None,kind=None):
  body=payload if isinstance(payload,bytes) else json.dumps(payload).encode(); key=sha256(body).hexdigest()
  folder=path/'responses';folder.mkdir(parents=True,exist_ok=True)
  (folder/(key+('.xlsx' if kind else '.json'))).write_bytes(body)
  result={'venue':venue,'url':url or SOURCES[venue]['api_url'],'params':params,'response_sha256':key,'bytes':len(body),'observed_at':NOW.isoformat()}
  if kind:result['kind']=kind
  return result
 class Client:
  def get_venue(self,venue,through):
   if venue=='SSE':
    pages=fixture.sse_pages();page={**pages[0],'date':20260904,'begin':0,'end':4,'list':pages[0]['list']+pages[1]['list']}
    return parse_sse([page],DAY),[ref(venue,page,{'select':SSE_SELECT,'begin':0,'end':500})]
   params={'SHOWTYPE':'JSON','CATALOGID':SOURCES[venue]['catalog'],'TABKEY':'tab1','txtBeginDate':DAY,'txtEndDate':DAY}
   if export:
    rows=export_fixture.records();head,tail=export_fixture.controls(rows);body=export_fixture.workbook(rows)
    return parse_export(body,head,tail,DAY),[ref(venue,head,{**params,'PAGENO':1}),ref(venue,tail,{**params,'PAGENO':2},SZSE_API),ref(venue,body,export_params(DAY),EXPORT_URL,EXPORT_KIND)]
   pages=fixture.szse_pages()
   for page in pages:
    for row in page[0]['data']:row['jyrq']=DAY
   return parse_szse(pages,DAY),[ref(venue,page,{**params,'PAGENO':i+1}) for i,page in enumerate(pages)]
 assert refresh_public_breadth(Client(),through=DAY,output=path,now=NOW)['status']=='complete'
 return json.loads((path/'current.json').read_text())

@pytest.mark.parametrize('export',[False,True])
def test_complete_originals_replay_both_acquisition_modes_without_mutating_history(tmp_path,export):
 ready(tmp_path,export);before=(tmp_path/'current.json').read_bytes()
 result=verified_breadth(tmp_path,now=NOW)
 assert result['as_of']==DAY and result['groups'][0]['observed_trading_stocks']>0
 assert result['groups'][0]['nontrading_stocks']>=1
 assert '不是跌停家数' in result['limits'][0]
 assert 'ST' in result['groups'][1]['name']
 assert newer_breadth({'as_of':'2026-09-03'},directory=tmp_path,now=NOW)==result
 assert newer_breadth({'as_of':DAY},directory=tmp_path,now=NOW) is None
 assert (tmp_path/'current.json').read_bytes()==before

@pytest.mark.parametrize('change',['query','url','future','missing_ref','projection','original','digest'])
def test_invalid_or_incomplete_observations_do_not_replace_old_breadth(tmp_path,change):
 packet=ready(tmp_path,True);old={'as_of':'2026-09-03'};before=deepcopy(old)
 if change=='query':packet['responses'][1]['params']['txtEndDate']='2026-09-03'
 elif change=='url':packet['responses'][1]['url']='http://untrusted.example/report'
 elif change=='future':packet['responses'][1]['observed_at']='2027-01-01T00:00:00+00:00'
 elif change=='missing_ref':packet['responses'].pop()
 elif change=='projection':packet['venues']['SSE']['rows'][0]['security_name']='changed source projection'
 elif change=='original':
  r=packet['responses'][-1];(tmp_path/'responses'/(r['response_sha256']+'.xlsx')).write_bytes(b'changed')
 packet.pop('content_digest');packet['content_digest']=digest(packet)
 if change=='digest':packet['content_digest']='0'*64
 (tmp_path/'current.json').write_text(json.dumps(packet))
 assert newer_breadth(old,directory=tmp_path,now=NOW) is None and old==before
