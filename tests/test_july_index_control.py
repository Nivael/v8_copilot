from pathlib import Path
from hashlib import sha256
import json
import pytest
from july_index_control import verify


def test_seven_closes_and_both_window_endpoints_match_without_replacing_primary_precision():
    e=verify();assert e==json.loads(Path('JULY_SHORT_SPELL_INDEX_CONTROL_EVIDENCE_2026_11_21.json').read_text())
    r=e['reading'];assert r['matched_closes']==7 and r['matched_at_two_decimal_precision']
    assert abs(r['primary_before_pct']-r['official_before_pct'])<.002
    assert abs(r['primary_remaining_pct']-r['official_remaining_pct'])<.002


def test_correct_hash_for_wrong_index_is_still_rejected(tmp_path):
    ref=json.loads(Path('JULY_INDEX_CONTROL_SOURCE_2026_11_21.json').read_text());raw=(Path(ref['source_store'])/(ref['response_sha256']+'.json')).read_bytes();body=json.loads(raw);body['data'][0]['indexCode']='000300';changed=json.dumps(body).encode();key=sha256(changed).hexdigest();(tmp_path/(key+'.json')).write_bytes(changed)
    ref.update(source_store=str(tmp_path),response_sha256=key,bytes=len(changed))
    with pytest.raises(ValueError,match='date/code'):verify(ref)
