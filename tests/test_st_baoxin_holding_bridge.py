from pathlib import Path
import json,gzip
import pytest
from canonical_json import digest
from st_baoxin_holding_bridge import holding_bridge_view

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/baoxin-holding-bridge.json.gz').read_bytes()))
def seal(i):
 p=i['baoxin_holding_bridge'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_source_bound_continuous_bridge_and_partial_default():
 v=holding_bridge_view(fixture())
 assert v['explained_shares']==27660000 and v['unexplained_shares']==0
 assert [r['registered_shares']for r in v['rows']]==[8840000,5500000,9320000,4000000]
 assert v['partial']['registered_shares']+v['partial']['defaulted_shares']==9420000
 assert not v['debt']['registered'] and v['debt']['yuhong_shares']==2618800
 assert 'evidence_pages'not in v and v['method_promotions']==0
@pytest.mark.parametrize('bad',['quantity','continuity','asof','published','buyer','default','full','ruling','text','source_date','scope'])
def test_false_completion_identity_dates_or_arithmetic_rejected(bad):
 i=fixture();p=i['baoxin_holding_bridge'];r=p['rows'][0]
 if bad=='quantity':r['registered_shares']+=1
 elif bad=='continuity':r['after']-=1
 elif bad=='asof':r['as_of']='2026-09-24'
 elif bad=='published':r['published_on']='2026-09-23'
 elif bad=='buyer':r['identity_tokens']=['陈飞跃','S2290']
 elif bad=='default':p['partial']['defaulted_buyer']='其他人'
 elif bad=='full':p['partial']['registered_shares']=9420000
 elif bad=='ruling':p['debt']['registered']=True
 elif bad=='text':p['evidence_pages'][0]['text']='changed'
 elif bad=='source_date':p['sources'][-1]['announcement_date']='2026-09-23'
 elif bad=='scope':i['through']='2026-11-05'
 seal(i)
 with pytest.raises(ValueError):holding_bridge_view(i)
def test_missing_packet_is_compatible():assert holding_bridge_view({})is None
