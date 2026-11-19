from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import gzip
import json
import pytest
from canonical_json import digest
from st_eleventh_period_followup import followup_view


def fixture():
    return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-eleventh-period-followup.json.gz').read_bytes()))


def test_later_facts_preserve_initial_state_and_separate_procedures():
    data=fixture();before=deepcopy(data)
    r=followup_view(data,data['test_prior'])
    assert data==before
    assert r['counts']['initial_coverage']==86
    assert r['counts']['complete_windows']==45
    assert r['counts']['unfinished_windows']==9
    assert r['counts']['stock_endpoint_gaps']==0
    assert len(r['chains'])==14 and len(r['financial_bridge'])==16
    assert '仍待交易所批准' in r['answer']
    rail=next(c for c in r['chains']if c['source']=='1225574915')
    school=next(c for c in r['chains']if c['source']=='1225670150')
    assert '13767' in rail['changed'] and '006349' in school['changed']
    assert '不是同一案件' in rail['open']
    contract=next(c for c in r['chains']if c['source']=='1225577942')
    assert '成立生效' in contract['changed'] and '批准' in contract['changed']
    assert '捐赠' in contract['open']


def test_quarter_cash_and_adjusted_comparison_basis():
    data=fixture();r=followup_view(data,data['test_prior'])
    cash={v['symbol']:v for v in r['financial_bridge']if v['metric']=='operating_cash'}
    assert {k:v['quarter_yuan']for k,v in cash.items()}=={'002822':'-2734915.12','002856':'-2421234.59','002872':'-9771024.86','002883':'-22500310.48'}
    assert all(v['reported_quarter_yuan'] is None and '推算' in v['quarter_boundary']for v in cash.values())
    assert all('重述' in v['comparison_basis']for v in r['financial_bridge']if v['symbol']=='002883')
    scan=next(v for v in r['financial_bridge']if v['symbol']=='002856'and v['metric']=='parent_profit')
    assert scan['q3_evidence_method']=='manual_visual_transcription'
    assert scan['quarter_yuan']=='-46888036.47'


@pytest.mark.parametrize('bad',['prior','market','duplicate','missing','identity','date','page','rehash','review','window','scan_fabricated_text'])
def test_resealed_packet_rejects_rewritten_evidence(bad):
    data=fixture();p=data['eleventh_period_followup'];s=p['sources'][0]
    if bad=='prior':data['test_prior']['counts']['after']=87
    elif bad=='market':data['current_extension']['market_inputs']['through']='2026-11-20'
    elif bad=='duplicate':p['sources'].append(deepcopy(s))
    elif bad=='missing':p['sources'].pop()
    elif bad=='identity':s['symbol']='999999'
    elif bad=='date':s['published_on']='2026-11-20'
    elif bad=='page':s['selected_pages']['1']='changed'
    elif bad=='rehash':
        s['selected_pages']['1']='changed';s['page_hashes'][0]=sha256(b'changed').hexdigest()
    elif bad=='review':p['visual_read'].pop()
    elif bad=='window':p['event_windows_digest']='changed'
    elif bad=='scan_fabricated_text':
        s=next(s for s in p['sources']if s['announcement_id']=='1225641381')
        s['selected_pages']['2']='237596488.52 -76932993.36';s['page_hashes'][1]=sha256(s['selected_pages']['2'].encode()).hexdigest()
    p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
    with pytest.raises(ValueError):followup_view(data,data['test_prior'])


def test_absent_packet_preserves_previous_reader():
    assert followup_view({},None) is None
