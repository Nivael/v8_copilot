import gzip,json
from pathlib import Path
from hashlib import sha256
import pytest
from canonical_json import digest
from st_eighth_period_followup import followup_view

def fixture():return json.loads(gzip.decompress(Path('tests/fixtures/st-eighth-period-followup.json.gz').read_bytes()))
def test_preserves_cash_subjects_repeated_stages_and_unfinished_windows():
 x=fixture();v=followup_view(x,x['test_prior']);assert v['counts']==dict(files=14,pages=108,viewed_pages=34,initial_coverage=74,complete_windows=38,unfinished_windows=4)
 assert len(v['chains'])==11 and len(v['event_windows'])==14
 assert v['method_promotions']==0
@pytest.mark.parametrize('kind',['digest','prior','market','date','page','rehash','sha','visual','source_count','main_signature'])
def test_rejects_corrupted_evidence_even_after_packet_rehash(kind):
 x=fixture();p=x['eighth_period_followup'];s=p['sources'][0]
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
 elif kind=='main_signature':next(s for s in p['sources']if s['announcement_id']=='1225499449')['document_dated_on']=None
 if kind!='digest':p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):followup_view(x,x['test_prior'])
def test_optional_packet():assert followup_view({},None)is None

def test_summary_dates_cannot_be_replaced_with_dates_of_reported_events():
 x=fixture();p=x['eighth_period_followup']
 for aid in ['1225520778','1225526423','1225480400']:
  assert next(s for s in p['sources']if s['announcement_id']==aid)['document_dated_on'] is None
 next(s for s in p['sources']if s['announcement_id']=='1225520778')['document_dated_on']='2026-06-26'
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):followup_view(x,x['test_prior'])

def test_each_case_retains_primary_source_and_watched_boundaries():
 x=fixture();v=followup_view(x,x['test_prior']);sources={s['announcement_id']:s for s in v['sources']}
 for c in v['chains']:
  assert c['source'] in sources and c['open'] and (c.get('changed')or c.get('closed'))
  assert all(1<=n<=sources[c['source']]['pages']for n in c['pages'])
  for step in c.get('continuity',[]):assert step['source'] in sources and step['stage']
 text=json.dumps(v,ensure_ascii=False)
 for phrase in ['信托专户','正式受理','自由','无法保证','归母','36','60']:assert phrase in text
 assert len(v['h1_metrics'])==16
