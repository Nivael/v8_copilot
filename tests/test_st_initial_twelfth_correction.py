from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import gzip,json
import pytest
from canonical_json import digest
from st_initial_twelfth_correction import correction_view

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-initial-twelfth-correction.json.gz').read_bytes()))

def test_missed_initial_arrangement_and_later_confirmation_are_separate():
 d=fixture();before=deepcopy(d);r=correction_view(d,d['test_prior'])['600080'];assert d==before
 assert '6月30日已公开' in r['change'] and '抵付' in r['change']
 assert '不是现金退款到账' in r['boundary'] and '8月22日' in r['boundary']
 assert '不把8月确认倒填' in r['boundary']
 assert [(s['published_on'],s['page'])for s in r['sources']]==[('2026-08-22',25),('2026-06-30',5)] or [(s['published_on'],s['page'])for s in r['sources']]==[('2026-06-30',5),('2026-08-22',25)]
 assert '保留上一版' in r['history_note']

@pytest.mark.parametrize('bad',['prior','date','symbol','sha','duplicate','page','rehash','visual'])
def test_resealing_cannot_rewrite_correction_evidence(bad):
 d=fixture();p=d['initial_twelfth_correction'];s=p['sources'][0]
 if bad=='prior':d['test_prior']['counts']['after']=91
 elif bad=='date':s['published_on']='2026-07-03'
 elif bad=='symbol':s['symbol']='600079'
 elif bad=='sha':s['sha256']='changed'
 elif bad=='duplicate':p['sources'].append(deepcopy(s))
 elif bad in ['page','rehash']:
  s['selected_pages']['1']='changed'
  if bad=='rehash':s['page_hashes'][0]=sha256(b'changed').hexdigest()
 elif bad=='visual':p['visual_read'].pop()
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):correction_view(d,d['test_prior'])

def test_no_correction_preserves_legacy_reader():assert correction_view({},None)is None
