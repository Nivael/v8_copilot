from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import gzip,json
import pytest
from canonical_json import digest
from st_thirteenth_period_followup import followup_view

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-thirteenth-period-followup.json.gz').read_bytes()))

def test_legal_accounting_and_share_lots_stay_separate():
 d=fixture();before=deepcopy(d);r=followup_view(d,d['test_prior']);assert d==before
 assert r['counts']['initial_coverage']==94 and r['counts']['files']==25
 assert r['counts']['complete_windows']==69 and r['counts']['unfinished_windows']==6
 assert len(r['chains'])==10 and len(r['financial_bridge'])==16
 chains={c['source']:c for c in r['chains']}
 assert '过户登记后续办理' in chains['1225590832']['open']
 assert '股东股份处置不是上市公司收款' in chains['1225601565']['open']
 assert '410万与450万' in chains['1225636636']['open']
 assert '8月收到原告上诉状' in chains['1225465715']['changed']
 assert '入账冲回不当现金回款' in chains['1225640975']['open']

def test_financial_bridge_uses_adjusted_comparison_and_unreported_markers():
 d=fixture();r=followup_view(d,d['test_prior']);rows=r['financial_bridge']
 assert sum(x['reported_quarter_yuan']is not None for x in rows)==13
 assert sum(x['reported_h1_yoy_pct']is None for x in rows)==9
 assert sum(x['reported_h1_yoy_marker']=='-' for x in rows)==2
 assert sum(x['reported_h1_yoy_marker']=='不适用' for x in rows)==7
 cash={x['symbol']:x for x in rows if x['metric']=='operating_cash'}
 assert cash['600084']['quarter_yuan']=='5152670.31' and cash['600084']['reported_quarter_yuan']is None
 assert cash['600119']['quarter_yuan']=='-44761253.08' and cash['600119']['reported_quarter_yuan']=='-44761253.08'
 revenue=next(x for x in rows if x['symbol']=='600119'and x['metric']=='revenue')
 assert revenue['prior_h1_yuan']=='113211629.87' and revenue['q3_page']==2

@pytest.mark.parametrize('bad',['prior','market','duplicate','missing','identity','date','page','rehash','review','window'])
def test_resealing_does_not_authorize_rewritten_evidence(bad):
 d=fixture();p=d['thirteenth_period_followup'];s=p['sources'][0]
 if bad=='prior':d['test_prior']['counts']['after']=95
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
