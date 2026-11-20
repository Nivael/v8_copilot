from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_endpoint_selection_audit import endpoint_selection_audit

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-endpoint-selection-audit.json.gz').read_bytes()))
def test_all_members_remain_but_unverified_returns_do_not_enter_certified_statistics():
 d=fixture();before=deepcopy(d);r=endpoint_selection_audit(d,d['test_current'],d['test_reasons']);assert d==before
 full,recent=r['windows'];assert len(full['rows'])==len(recent['rows'])==150
 assert full['summary']['primary_paired']==146 and full['summary']['verified_paired']==141 and full['summary']['primary_missing']==4
 assert {x['symbol']for x in full['rows']if x['status']=='quote_conflict_or_unverified'}=={'002592','002598','600079','603517','603869'}
 assert all(x['certified_return_pct']is None and x['primary_return_pct']is not None for x in full['rows']if x['status']=='quote_conflict_or_unverified')
 assert recent['summary']['verified_paired']==147 and recent['summary']['primary_missing']==3
 assert [g['members']for g in full['groups']]==[136,14] and [g['verified_paired']for g in full['groups']]==[130,11]
 assert full['summary']['verified_subset_positive_denominator']==141
 assert {x['symbol']for x in full['rows']if x['status']=='primary_endpoint_gap'}=={'000016','002717','002731','600491'}
 assert endpoint_selection_audit({},None,None)is None

@pytest.mark.parametrize('change',['text','identity','duplicate','market','current','membership','reasons','view','snapshot'])
def test_resealed_changes_cannot_override_frozen_sources_or_denominators(change):
 d=fixture();p=d['endpoint_selection_audit']
 if change=='text':p['sources'][0]['text']='{}'
 elif change=='identity':p['sources'][0]['symbol']='999999'
 elif change=='duplicate':p['sources'].append(deepcopy(p['sources'][0]))
 elif change=='market':
  d['current_extension']['market_inputs']['fixed_prices'][0]['close']=0;p['market_digest']=digest(d['current_extension']['market_inputs'])
 elif change=='current':
  d['test_current']['full_comparison']['fixed_after']['rows'].pop();p['current_digest']=digest(d['test_current'])
 elif change=='membership':
  d['test_current']['full_comparison']['fixed_after']['rows'][0]['still_st_at_end']=False;p['current_digest']=digest(d['test_current'])
 elif change=='reasons':
  d['test_reasons']['through']='2026-11-20';p['reasons_digest']=digest(d['test_reasons'])
 elif change=='view':p['view_digest']='bad'
 else:p['prior_snapshot']='bad'
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):endpoint_selection_audit(d,d['test_current'],d['test_reasons'])
