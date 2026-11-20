import json,hashlib
from pathlib import Path
import pytest
from exit_quote_official import verify

def evidence():return json.loads((Path(__file__).resolve().parents[1]/'ST_EXIT_QUOTE_OFFICIAL_EVIDENCE_2026_11_21.json').read_text())
def test_failed_sources_remain_unknown_and_four_endpoints_unusable():
 e=evidence();r=verify(e);assert r==e['verified_result'];assert not any(s['usable_endpoint']for s in r)
 assert sum(s['status']=='official_request_failed'for s in r)==2
 assert next(s for s in r if s['symbol']=='002717')['raw_matched_days']==66

def test_changed_original_or_primary_quote_is_rejected():
 e=evidence();e['sources'][0]['raw_text']+=' '
 with pytest.raises(ValueError):verify(e)
 e=evidence();e['primary_historical_raw']['002717']['2026-07-03']='0'
 with pytest.raises(ValueError):verify(e)

def test_new_endpoint_data_requires_review_rather_than_silent_replacement():
 e=evidence();s=next(s for s in e['sources']if s['symbol']=='002717');p=json.loads(s['raw_text']);row=p['data']['picupdata'][-1].copy();row[0]='2026-11-19';p['data']['picupdata'].append(row);s['raw_text']=json.dumps(p);raw=s['raw_text'].encode();s['source']['sha256']=hashlib.sha256(raw).hexdigest();s['source']['bytes']=len(raw)
 with pytest.raises(ValueError):verify(e)
