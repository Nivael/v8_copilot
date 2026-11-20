from pathlib import Path
from hashlib import sha256
import json
import pytest
from risk_list_nov20_review import review

def evidence():return json.loads(Path('RISK_LIST_NOV20_EVIDENCE_2026_11_21.json').read_text())

def test_explicit_source_day_is_not_the_reading_day_or_undated_sse_observation():
    e=evidence();r=review(e);assert r==e['reading'];sz,sh=r['comparisons']
    assert (sz['source_as_of'],sz['observed_on'],sz['main_a_shares'])==('2026-11-20','2026-11-21',74)
    assert sz['all_rows']==115 and sz['a_shares']==113 and sz['b_shares']==2
    assert sh['source_as_of']is None and sh['main_a_shares']==68
    assert sz['codes_equal_prior']and sh['codes_equal_prior']
    assert not r['complete_two_venue_target_membership']
    assert r['szse_delisting_empty_source_as_of']is None


def test_missing_page_byte_change_and_relabelled_target_stop_review():
    e=evidence();e['sources'].pop()
    with pytest.raises(ValueError,match='all selected'):review(e)
    e=evidence();e['sources'][0]['text']+=' '
    with pytest.raises(ValueError,match='bytes'):review(e)
    e=evidence();e['source_target_day']='2026-11-19'
    with pytest.raises(ValueError,match='misdated'):review(e)


def test_sse_date_newly_available_requires_reassessment_instead_of_old_unknown_label():
    e=evidence();s=next(s for s in e['sources']if s['key']=='sse_main_risk');d=json.loads(s['text']);d['queryDate']='2026-11-20';s['text']=json.dumps(d);raw=s['text'].encode();s.update(response_sha256=sha256(raw).hexdigest(),bytes=len(raw))
    with pytest.raises(ValueError,match='date now supplied|mismatched SSE'):review(e)
