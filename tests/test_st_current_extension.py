from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_current_extension import current_extension

def fixture():
    return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-current-extension.json.gz').read_bytes()))

def seal(i):
    p=i['current_extension'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})

def test_preserves_history_and_retains_exit_and_missing_samples():
    i=fixture();before=deepcopy(i);v=current_extension(i,i['test_daily'])
    assert i==before
    assert v['latest']['days']==9 and v['full_comparison']['after']['days']==93
    assert v['latest']['reference_change_pct']==pytest.approx(-10.0479533252)
    assert v['fixed']['covered']==147
    assert {r['symbol']for r in v['fixed']['rows']if r['return_pct']is None}=={'000016','002717','002731'}
    s=next(s for s in v['tracked']if s['symbol']=='688053.SH')
    assert not s['still_st']and not s['in_main_board_reference']and s['change_pct']<0
    assert v['crosscheck']['000985']['matching_points_at_official_two_decimals']==10
    assert len(v['crosscheck']['000985']['unrounded_differences'])==10

@pytest.mark.parametrize('bad',['history','promotion','recursive','page','receipt','member','quote','precision'])
def test_resealed_packet_cannot_hide_scope_stage_or_quote_corruption(bad):
    i=fixture();p=i['current_extension']
    if bad=='history':i['through']='2026-11-05'
    elif bad=='promotion':p['method_promotions']=1
    elif bad=='recursive':p['market_inputs']['current_extension']={'version':1}
    elif bad=='page':p['sources'][0]['selected_pages']['1']+='changed'
    elif bad=='receipt':p['events'][0]['document_dated_on']='2026-11-12'
    elif bad=='member':p['market_inputs']['members']=[r for r in p['market_inputs']['members']if not(r['symbol']=='688053'and r['trade_date']=='2026-11-10')]
    elif bad=='quote':p['tracked_quotes']['603398.SH'][-1]['raw_close']=9.99
    elif bad=='precision':p['crosscheck']['000985']['unrounded_differences']=[]
    seal(i)
    with pytest.raises(ValueError):current_extension(i,i['test_daily'])

def test_absence_keeps_legacy_available():
    assert current_extension({},[])is None
