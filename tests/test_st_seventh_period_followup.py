import gzip,json
from pathlib import Path
from hashlib import sha256
import pytest
from canonical_json import digest
from st_seventh_period_followup import followup_view

def fixture():return json.loads(gzip.decompress(Path('tests/fixtures/st-seventh-period-followup.json.gz').read_bytes()))
def test_preserves_cash_subjects_repeated_stages_and_unfinished_windows():
 x=fixture();v=followup_view(x,x['test_prior']);assert v['counts']==dict(files=18,pages=73,viewed_pages=36,initial_coverage=70,complete_windows=45,unfinished_windows=3)
 assert len(v['chains'])==10 and len(v['event_windows'])==16
 assert next(e for e in v['event_windows']if e['aid']=='1225409315')['windows'][0]['through']=='2026-07-06'
 assert len(next(c for c in v['chains']if c['chain']=='利源-重大资产重组')['continuity'])==5
 assert v['method_promotions']==0
@pytest.mark.parametrize('kind',['digest','prior','market','date','page','rehash','sha','visual','source_count','main_signature'])
def test_rejects_corrupted_evidence_even_after_packet_rehash(kind):
 x=fixture();p=x['seventh_period_followup'];s=p['sources'][0]
 if kind=='digest':p['content_digest']='bad'
 elif kind=='prior':p['prior_digest']='bad'
 elif kind=='market':p['market_digest']='bad'
 elif kind=='date':s['published_on']='2026-07-03'
 elif kind in ['page','rehash']:
  s['selected_pages']['1']+='forged'
  if kind=='rehash':s['page_hashes'][0]=sha256(s['selected_pages']['1'].encode()).hexdigest()
 elif kind=='sha':s['sha256']='bad'
 elif kind=='visual':p['visual_read']=[]
 elif kind=='source_count':p['sources'].pop()
 elif kind=='main_signature':next(s for s in p['sources']if s['announcement_id']=='1225625467')['document_dated_on']=None
 if kind!='digest':p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):followup_view(x,x['test_prior'])
def test_optional_packet():assert followup_view({},None)is None
