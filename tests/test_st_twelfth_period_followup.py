from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import gzip,json
import pytest
from canonical_json import digest
from st_twelfth_period_followup import followup_view

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-twelfth-period-followup.json.gz').read_bytes()))

def test_completed_transfers_and_accounting_do_not_remove_other_conditions():
 d=fixture();before=deepcopy(d);r=followup_view(d,d['test_prior']);assert d==before
 assert r['counts']['initial_coverage']==90
 assert r['counts']['new_files']==19 and r['counts']['reused_files']==2
 assert r['counts']['complete_windows']==54 and r['counts']['unfinished_windows']==6
 assert len(r['chains'])==12 and len(r['financial_bridge'])==16
 assert '5.14亿元' in r['answer']
 sale=next(c for c in r['chains']if c['source']=='1225547841')
 assert '5.14亿元' in sale['changed'] and sale['supporting'][0]['pages']==[3]
 arb=next(c for c in r['chains']if c['source']=='1225599349')
 assert '不等于裁决失效' in arb['open']
 assert '不能从净利润再扣一次' in arb['supporting'][0]['state']
 assert not any(e['aid']=='1225397191'for e in r['event_windows'])

def test_reported_and_derived_financial_numbers_and_physical_pages_are_distinct():
 d=fixture();r=followup_view(d,d['test_prior']);rows=r['financial_bridge']
 assert sum(v['reported_quarter_yuan']is not None for v in rows)==14
 assert sum(v['reported_h1_yoy_pct']is None for v in rows)==4
 cash={v['symbol']:v for v in rows if v['metric']=='operating_cash'}
 assert cash['002932']['quarter_yuan']=='9001862.79' and cash['002932']['reported_quarter_yuan']is None
 assert cash['600053']['quarter_yuan']=='-89373620.68' and cash['600053']['q3_page']==2
 assert cash['600079']['quarter_yuan']=='778405856.66' and cash['600079']['reported_quarter_yuan']=='778405856.66'
 assert cash['600080']['quarter_yuan']=='8812057.55' and cash['600080']['reported_quarter_yuan']=='8812057.55'
 assert all(v['h1_page']==8 for v in rows if v['symbol']=='002932')

@pytest.mark.parametrize('bad',['prior','market','duplicate','missing','identity','date','page','rehash','review','window'])
def test_resealing_does_not_authorize_rewritten_evidence(bad):
 d=fixture();p=d['twelfth_period_followup'];s=p['sources'][0]
 if bad=='prior':d['test_prior']['counts']['after']=91
 elif bad=='market':d['current_extension']['market_inputs']['through']='2026-11-20'
 elif bad=='duplicate':p['sources'].append(deepcopy(s))
 elif bad=='missing':p['sources'].pop()
 elif bad=='identity':s['symbol']='999999'
 elif bad=='date':s['published_on']='2026-11-20'
 elif bad in ['page','rehash']:
  s['selected_pages']['1']='changed'
  if bad=='rehash':s['page_hashes'][0]=sha256(b'changed').hexdigest()
 elif bad=='review':p['visual_read'].pop()
 elif bad=='window':p['event_windows_digest']='changed'
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):followup_view(d,d['test_prior'])

def test_absent_packet_preserves_existing_reader():assert followup_view({},None)is None
