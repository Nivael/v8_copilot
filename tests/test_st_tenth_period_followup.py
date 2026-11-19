from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import gzip
import json
import pytest
from canonical_json import digest
from st_tenth_period_followup import followup_view


def fixture():
    return json.loads(gzip.decompress((Path(__file__).parent / 'fixtures/st-tenth-period-followup.json.gz').read_bytes()))


def test_later_facts_keep_initial_state_and_exit_nulls():
    data=fixture()
    before=deepcopy(data)
    result=followup_view(data,data['test_prior'])
    assert data==before
    assert result['counts']['initial_coverage']==82
    assert result['counts']['complete_windows']==64
    assert result['counts']['unfinished_windows']==11
    assert result['counts']['stock_endpoint_gaps']==18
    assert len(result['chains'])==11
    assert len(result['financial_bridge'])==12
    assert not any(r['symbol']=='002731' for r in result['financial_bridge'])
    cuihua=[e for e in result['event_windows'] if e['symbol']=='002731']
    assert all(w['stock_pct'] is None and w['market_pct'] is not None and w['st_pct'] is not None for e in cuihua for w in e['windows'])
    assert not any(e['aid']=='1225222296' for e in result['event_windows'])


def test_quarter_cash_is_derived_and_not_cumulative_or_zero():
    data=fixture()
    result=followup_view(data,data['test_prior'])
    cash={r['symbol']:r for r in result['financial_bridge'] if r['metric']=='operating_cash'}
    assert cash['002726']['quarter_yuan']=='-15832672.21'
    assert cash['002789']['quarter_yuan']=='16086584.23'
    assert cash['002816']['quarter_yuan']=='-21835354.65'
    assert all(r['reported_quarter_yuan'] is None and '推算' in r['quarter_boundary'] for r in cash.values())


@pytest.mark.parametrize('bad',['prior','market','duplicate','missing','identity','date','page','rehash','review','window'])
def test_resealed_packet_does_not_accept_rewritten_evidence(bad):
    data=fixture();p=data['tenth_period_followup'];s=p['sources'][0]
    if bad=='prior':data['test_prior']['counts']['after']=83
    elif bad=='market':data['current_extension']['market_inputs']['through']='2026-11-20'
    elif bad=='duplicate':p['sources'].append(deepcopy(s))
    elif bad=='missing':p['sources'].pop()
    elif bad=='identity':s['symbol']='999999'
    elif bad=='date':s['published_on']='2026-11-20'
    elif bad=='page':s['selected_pages']['1']='changed'
    elif bad=='rehash':
        s['selected_pages']['1']='changed'
        s['page_hashes'][0]=sha256(b'changed').hexdigest()
    elif bad=='review':p['visual_read'].pop()
    elif bad=='window':p['event_windows_digest']='changed'
    p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
    with pytest.raises(ValueError):followup_view(data,data['test_prior'])


def test_absent_packet_keeps_previous_reader():
    assert followup_view({},None) is None
