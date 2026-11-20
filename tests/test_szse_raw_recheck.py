import json,hashlib
from pathlib import Path
import pytest
from szse_raw_recheck import replay

def evidence():return json.loads((Path(__file__).resolve().parents[1]/'ST_SZSE_RAW_RECHECK_EVIDENCE_2026_11_21.json').read_text())
def test_saved_window_is_raw_not_adjusted_and_totals_are_separate():
 r=replay(evidence());assert sum(x['historical']for x in r)==170;assert sum(x['later']for x in r)==18;assert sum(x['total']for x in r)==188

def test_source_bytes_and_endpoint_changed_stop():
 e=evidence();e['inputs'][0]['official_raw_text']+=' '
 with pytest.raises(ValueError):replay(e)
 e=evidence();e['inputs'][0]['source']['url']=e['inputs'][0]['source']['url'].replace('marketId=1','marketId=2')
 with pytest.raises(ValueError):replay(e)

def test_rehashed_response_error_or_missing_target_date_stops():
 for change in ['status','missing']:
  e=evidence();s=e['inputs'][0];raw=json.loads(s['official_raw_text'])
  if change=='status':raw['code']='-1'
  else:raw['data']['picupdata']=[r for r in raw['data']['picupdata']if r[0]!='2026-07-03']
  s['official_raw_text']=json.dumps(raw);b=s['official_raw_text'].encode();s['source']['sha256']=hashlib.sha256(b).hexdigest();s['source']['bytes']=len(b)
  with pytest.raises(ValueError):replay(e)

def test_substituting_adjusted_price_for_raw_is_rejected():
 e=evidence();e['inputs'][0]['historical_primary_raw']['2026-07-03']='6.595971985473949'
 with pytest.raises(ValueError):replay(e)
