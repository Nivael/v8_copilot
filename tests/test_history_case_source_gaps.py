from copy import deepcopy
import pytest
from research_history_case_period import case_period_paths,SOURCE_GAP_REASON,GAP_VERSION
from research_history_events import freeze_argument_timelines,project_argument_timeline
from test_history_case_period import period,setup
from test_argument_event_timelines import seal

def source_gap_period():
    value=period();value['version']=GAP_VERSION
    ref=next(r for r in value['source_refs'] if r['key']=='tencent_unadjusted')
    value['gap_notes']=[{'date':'2021-05-18','reason':SOURCE_GAP_REASON,'support_kind':'unverified_source_gap',
                         'source_key':ref['key'],'source_sha256':ref['sha256'],'url':ref['url']}]
    return seal(value)

def verify(value):
    return case_period_paths(seal(value),symbol='002514.SZ',asked_on='2026-06-01',current_start='2026-05-29')

def test_unverified_missing_quote_has_its_own_raw_source_and_stays_missing():
    value=source_gap_period();before=deepcopy(value)
    result=verify(value)
    assert value==before and result['stocks']['002514.SZ']['points'][2]['value'] is None

@pytest.mark.parametrize('change',[
    lambda p:p['gap_notes'][0].update(reason='经核实停牌一天'),
    lambda p:p['gap_notes'][0].update(source_key='market'),
    lambda p:p['gap_notes'][0].update(source_sha256='b'*64),
    lambda p:p['gap_notes'][0].update(url='https://example.com/another-quote'),
    lambda p:p['gap_notes'][0].update(announcement_id='1209994983'),
    lambda p:p['gap_notes'][0].update(support_kind='verified_suspension'),
    lambda p:p['gap_notes'][0].pop('support_kind'),
    lambda p:p['gap_notes'][0].pop('source_sha256'),
    lambda p:p['gap_notes'].append(deepcopy(p['gap_notes'][0])),
    lambda p:p['gap_notes'].clear(),
])
def test_missing_quote_cannot_be_resealed_as_a_suspension_or_foreign_observation(change):
    value=source_gap_period();change(value)
    with pytest.raises((ValueError,KeyError,TypeError)):verify(value)

def test_new_profile_can_keep_a_primary_verified_suspension():
    value=period();value['version']=GAP_VERSION;value['gap_notes'][0]['support_kind']='verified_suspension'
    assert verify(value)==value['paths']

def test_new_gap_kind_is_bound_into_the_existing_study_and_original_review():
    review,args=setup();args['case_periods']['002514.SZ']=source_gap_period()
    result=freeze_argument_timelines(review,**args);timeline=result['event_timelines']['002514.SZ']
    assert project_argument_timeline(timeline,record=args['record'],review=result,paths=args['paths'],symbol='002514.SZ')==timeline
    altered=deepcopy(timeline);altered['case_period']['gap_notes'][0]['reason']='已经确认停牌'
    seal(altered['case_period']);seal(altered)
    assert project_argument_timeline(altered,record=args['record'],review=result,paths=args['paths'],symbol='002514.SZ') is None

