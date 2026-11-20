import json,copy
from pathlib import Path
import pytest
from st_official_raw_recheck import replay

def data():return json.loads((Path(__file__).resolve().parents[1]/'ST_OFFICIAL_RAW_RECHECK_EVIDENCE_2026_11_21.json').read_text())
def test_saved_official_raw_counts_and_halt_gap():
 e=data();r=replay(e);assert sum(x['total']for x in r)==281
 assert sum(x['historical']for x in r)==254
 assert e['results'][1]['official_absent_dates']==['2026-10-19']
def test_original_byte_tampering_stops():
 e=data();e['inputs'][0]['official_raw_text']+=' '
 with pytest.raises(ValueError):replay(e)
def test_comparison_price_or_scope_tampering_stops():
 e=data();first=next(iter(e['inputs'][0]['historical_primary_raw']));e['inputs'][0]['historical_primary_raw'][first]='1'
 with pytest.raises(ValueError):replay(e)
 e=data();e['inputs'][0]['later_primary_paired']['2026-11-20']='1'
 with pytest.raises(ValueError):replay(e)
