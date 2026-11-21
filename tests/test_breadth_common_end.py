import json
from pathlib import Path
import pytest
from breadth_common_end import compare_common_end
from st_breadth_alignment import analyze


def source():
    return json.loads(Path('ST_BREADTH_ALIGNMENT_EVIDENCE_2026_11_21.json').read_text())


def test_all_spells_share_one_endpoint_within_spell_and_keep_unformed_conditions():
    r = compare_common_end(source())
    assert len(r['episodes']) == 15
    assert r['episodes'][0]['left_boundary_unknown']
    assert r['episodes'][0]['checks'][1] == {'wait': 2, 'formed': False}
    nov = r['episodes'][-1]
    assert nov['target_end'] == nov['observed_end'] == '2026-11-19'
    assert nov['complete']
    assert [c['remaining_sessions'] for c in nov['checks']] == [5, 4, 3]
    assert nov['checks'][2]['remaining_market_pct'] == pytest.approx(-1.648377)
    assert nov['checks'][2]['remaining_st_pct'] == pytest.approx(-5.880245)
    for ep in r['episodes']:
        for c in ep['checks']:
            if not c['formed']: continue
            for key in ('st', 'market'):
                total=((1+c['already_'+key+'_pct']/100)*(1+c['remaining_'+key+'_pct']/100)-1)*100
                assert total == pytest.approx(ep['total_'+key+'_pct'])


def test_calendar_endpoint_is_not_shortened_when_data_ends_early():
    e = source(); i=e['inputs']
    i['extension_days']=[r for r in i['extension_days'] if r['date']<='2026-11-16']
    e['reading']=analyze({'daily':i['daily'],'themes':{'current_extension':{'days':i['extension_days']}}},{'sequence':{'days':i['breadth_days']}})
    ep=compare_common_end(e)['episodes'][-1]
    assert ep['target_end']=='2026-11-19'
    assert ep['observed_end']=='2026-11-16'
    assert not ep['complete'] and ep['total_market_pct'] is None
    assert all(c['remaining_market_pct'] is None for c in ep['checks'])
    assert ep['checks'][2]['remaining_sessions']==0
    assert ep['checks'][2]['partial_market_pct']==0


def test_identical_endpoint_can_change_the_apparent_direction_of_old_separate_windows():
    ep=compare_common_end(source())['episodes'][1]
    assert ep['target_end']=='2026-09-16'
    assert ep['checks'][2]['remaining_market_pct'] != pytest.approx(1.6122001381446882)
