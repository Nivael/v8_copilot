from pathlib import Path
import gzip,json
from copy import deepcopy
from hashlib import sha256
import pytest
from canonical_json import digest
from st_initial_fourteenth_four import initial_fourteenth_four

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-initial-fourteenth-four.json.gz').read_bytes()))

def test_repairs_and_remaining_conditions_have_separate_evidence():
 d=fixture();old=deepcopy(d);r=initial_fourteenth_four(d,d['test_prior'],d['test_current']);assert d==old
 assert r['counts']==dict(before=94,after=98,remaining=52,members=150,new_companies=4,new_files=19,new_pages=736)
 assert [x['symbol']for x in r['rows']]==['600136','600165','600169','600180']
 assert '1月12日获准撤销' in r['rows'][1]['known_at_anchor'] and '旧持续经营审计事项已消除' in r['rows'][1]['known_at_anchor']
 assert '不把新强调事项当保留意见' in r['rows'][1]['known_at_anchor']
 assert '拟先行庭外重组' in r['rows'][3]['known_at_anchor']
 assert r['rows'][2]['comparisons']['full']['stock_pct']>0 and r['rows'][3]['comparisons']['full']['stock_pct']<-50
 assert r['quote_audit']['stock_endpoint_points']==12 and r['quote_audit']['stock_return_windows']==8
 assert r['quote_audit']['index_endpoint_points_at_official_precision']==6
 assert '宁科240/242' in r['boundary'] and '2条缺口保持' in r['boundary']

@pytest.mark.parametrize('bad',['order','prior','market','future','identity','sha','page','rehash','date','visual','quote','catalog'])
def test_resealed_packet_cannot_rewrite_evidence_or_selection(bad):
 d=fixture();p=d['initial_fourteenth_four'];s=p['sources'][0]
 if bad=='catalog':p['catalog_scope']['historical_catalog_complete']=True
 elif bad=='order':p['selection'].reverse()
 elif bad=='prior':d['test_prior']['inventory'][0]['name']='changed'
 elif bad=='market':d['current_extension']['market_inputs']['through']='2026-11-20'
 elif bad=='future':s['published_on']='2026-07-04'
 elif bad=='identity':s['symbol']='999999'
 elif bad=='sha':s['sha256']='changed'
 elif bad in ['page','rehash']:
  s['selected_pages']['1']='changed'
  if bad=='rehash':s['page_hashes'][0]=sha256(b'changed').hexdigest()
 elif bad=='date':next(x for x in p['sources']if x['announcement_id']=='1225172319')['document_dated_on']='2026-04-24'
 elif bad=='visual':p['visual_read'].pop()
 elif bad=='quote':p['cross_sources'].pop()
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):initial_fourteenth_four(d,d['test_prior'],d['test_current'])

def test_scan_text_and_dates_do_not_replace_publication():
 d=fixture();ss={s['announcement_id']:s for s in d['initial_fourteenth_four']['sources']}
 assert ss['1225251063']['selected_pages']['2']==''
 assert ss['1225172319']['selected_pages']['2']==''
 assert ss['1225172319']['document_dated_on']=='2026-04-23' and ss['1225172319']['published_on']=='2026-04-24'
 assert ss['1225251063']['document_dated_on']=='2026-04-28' and ss['1225251063']['published_on']=='2026-04-29'
 assert len(d['initial_fourteenth_four']['visual_read'])==18

def test_absent_packet_preserves_previous_reader():assert initial_fourteenth_four({},None,None)is None
