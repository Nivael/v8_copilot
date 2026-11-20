from pathlib import Path
import json
from hashlib import sha256
import pytest
from qihuan_ohlc_crosscheck import crosscheck
FOLDER=Path('/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk/recovered_limit_cohorts/20261109-20261119')
def evidence():return json.loads(Path('QIHUAN_OHLC_CROSSCHECK_EVIDENCE_2026_11_21.json').read_text())

def test_nine_days_match_but_new_non_single_price_does_not_determine_limit_status():
    e=evidence();r=crosscheck(e,FOLDER);assert r==e['reading']
    assert r['paired_ohlc_values']==36
    assert r['one_price_dates']==['2026-11-18','2026-11-19']
    assert r['new_day']['single_price_streak_observed_end']=='2026-11-19'
    assert not r['new_day']['one_observed_price']
    assert r['new_day']['close_at_actual_down_limit']is None


def alter_official(e,mutate):
    d=json.loads(e['official_text']);mutate(d);e['official_text']=json.dumps(d)
    raw=e['official_text'].encode();e['official_source'].update(sha256=sha256(raw).hexdigest(),bytes=len(raw))


def test_rejects_changed_bytes_and_same_envelope_with_cross_channel_conflict():
    e=evidence();e['official_text']+=' '
    with pytest.raises(ValueError,match='bytes'):crosscheck(e,FOLDER)
    e=evidence()
    def change(d):
        row=next(r for r in d['data']['picupdata']if r[0]=='2026-11-09');row[1]='1.74'
    alter_official(e,change)
    with pytest.raises(ValueError,match='conflict'):crosscheck(e,FOLDER)


def test_requires_new_day_and_all_old_provider_days():
    e=evidence();alter_official(e,lambda d:d['data'].update(picupdata=[r for r in d['data']['picupdata']if r[0]!='2026-11-20']))
    with pytest.raises(ValueError,match='new observation'):crosscheck(e,FOLDER)
    e=evidence();e['provider_refs'].pop()
    with pytest.raises(ValueError,match='nine'):crosscheck(e,FOLDER)
