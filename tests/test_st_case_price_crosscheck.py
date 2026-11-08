from copy import deepcopy
from hashlib import sha256
import json
import pytest
from canonical_json import digest
from test_st_halt_price_crosscheck import fixture
from st_case_price_crosscheck import case_price_check_view,scope_digest

def case_fixture():
 i,d=fixture();p=i.pop('halt_price_crosscheck');mapping={'600491':'600730','002717':'603021'}
 for c in p['original_prices']['companies']:
  c['symbol']=mapping[c['symbol']]
  for r in c['rows']:r['volume']=100;r['has_trade']=True
 for r in p['sources']:
  old=r['symbol'];s=mapping[old];r['symbol']=s
  raw=r['raw_text'].replace(old,s).replace('sz'+s,'sh'+s).replace('"market": 0','"market": 1')
  x=json.loads(raw)
  if r['key'].startswith('tencent'):
   b=x['data']['sh'+s];b['day']=[[day,'1','1','1','1','100'] for day in i['calendar']];b['qfqday']=b['day']
  else:x['data']['klines']=[day+',1,1,1,1,100' for day in i['calendar']]
  r['raw_text']=json.dumps(x);r['sha256']=sha256(r['raw_text'].encode()).hexdigest()
 i['announcement_study']['verified_events']=[{'symbol':'600730','id':'event','title':'event','published_on':'2026-07-03','alternate_published_on':'2026-07-02'}]
 p['scope_digest']=scope_digest(i);i['case_price_crosscheck']=p;seal(i);return i,d

def seal(i):
 p=i['case_price_crosscheck'];p['content_digest']=digest({k:v for k,v in p.items() if k!='content_digest'})

def test_partial_channel_is_not_cross_source_certification_and_alternate_is_retained():
 i,d=case_fixture();p=i['case_price_crosscheck'];p['sources']=[r for r in p['sources'] if not(r['symbol']=='603021' and r['key'].startswith('eastmoney'))];seal(i)
 v=case_price_check_view(i,d);a,b=v['rows'];assert a['all_available_prices_agree'] and b['available_prices_agree'] and not b['all_available_prices_agree'];assert b['distinct_quote_channels']==1 and len(b['missing_channels'])==2;assert '缺失渠道尚未认证' in v['answer'];assert len(a['events'])==2 and a['events'][1]['windows']['1']['anchor']=='2026-07-02'

def test_real_price_disagreement_is_visible_not_described_as_agreement():
 i,d=case_fixture();r=i['case_price_crosscheck']['sources'][0];x=json.loads(r['raw_text']);x['data']['sh600730']['day'][0][2]='1.02';r['raw_text']=json.dumps(x);r['sha256']=sha256(r['raw_text'].encode()).hexdigest();seal(i)
 v=case_price_check_view(i,d);assert not v['rows'][0]['available_prices_agree'];assert '存在价格或日期差异' in v['answer'];assert v['rows'][0]['channels'][0]['price_differences'][0]['date']=='2026-07-02'

def test_source_identity_or_bytes_cannot_be_substituted():
 i,d=case_fixture();i['case_price_crosscheck']['sources'][0]['raw_text']+=' ';seal(i)
 with pytest.raises(ValueError,match='original changed'):case_price_check_view(i,d)

def test_absent_optional_packet_does_not_invent_coverage():assert case_price_check_view({},[]) is None
