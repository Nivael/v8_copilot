from copy import deepcopy
import pytest
from research_history_question_period import question_period_paths, VERSION, GAP_NOTE
from research_history_events import freeze_argument_timelines, project_argument_timeline
from research_history import assemble, question_digest
from research_history_reviews import freeze_argument_review
from test_history_case_period import period
from test_argument_event_timelines import fixture, seal


def prices():
    p=period();p['version']=VERSION;p['price_basis']='supplier_qfq_price_not_total_return'
    p['qfq_closes']=p.pop('unadjusted_closes')
    p['source_refs']=[r for r in p['source_refs'] if r['key'] in {'tencent_qfq','market','st'}]
    ref=p['source_refs'][0]
    p['gap_notes']=[{'date':'2021-05-18','reason':GAP_NOTE,'source_sha256':ref['sha256'],'url':ref['url']}]
    return seal(p)


def setup():
    _,a=fixture();a['record'].update(asked_at='2021-05-17T08:00:00Z')
    a['events']=a['events'][:1];a['events'][0]['published_on']='2021-05-19'
    a['sources']['0']['published_on']='2021-05-19'
    a['annotations']={'0':a['annotations']['0']}
    a['sources']={'0':a['sources']['0']}
    r=freeze_argument_review({'question_digest':question_digest(a['record']),'then_quote':'更像洗盘','focused_symbol':'002514.SZ','headline':'依据需修正'},a['record'])
    a['question_periods']={'002514.SZ':prices()}
    return r,a


def test_old_original_uses_its_own_prices_without_changing_global_paths_or_other_questions():
    r,a=setup();original=deepcopy(a['paths']);f=freeze_argument_timelines(r,**a)
    q=assemble([a['record']],a['paths'],reviews={a['record']['id']:f})['details']['002514.SZ']['questions'][0]
    assert q['anchor_date']=='2021-05-17' and q['review']['assessment_basis']=='original_argument_only'
    assert q['question_chart_sources']['stock'][2]['value'] is None
    assert q['review']['event_timeline']['events'][0]['context']['reference_close']=='2021-05-19'
    assert a['paths']==original
    other=assemble([a['record']],a['paths'])['details']['002514.SZ']['questions'][0]
    assert other['anchor_date'] is None and 'question_chart_sources' not in other


@pytest.mark.parametrize('change',[
    lambda p:p.update(price_basis='unadjusted_price'),
    lambda p:p['source_refs'][0].update(url='https://example.com/foreign'),
    lambda p:p['source_refs'][0].update(sha256='bad'),
    lambda p:p['source_refs'][0].update(observed_at='2099-01-01T00:00:00Z'),
    lambda p:p['source_refs'][0].update(observed_at='2026-01-01T00:00:00'),
    lambda p:p['gap_notes'][0].update(reason='已经核定停牌'),
    lambda p:p['gap_notes'][0].update(source_sha256='b'*64),
    lambda p:p['qfq_closes'].pop('2021-05-17'),
    lambda p:p['paths']['market'][1].update(level=0),
    lambda p:p['paths']['stocks']['002514.SZ']['points'][2].update(value=101,level=101),
])
def test_resealed_wrong_sources_units_gaps_and_prices_are_rejected(change):
    p=prices();change(p)
    with pytest.raises((ValueError,KeyError,TypeError)):
        question_period_paths(seal(p),symbol='002514.SZ',asked_on='2021-05-17')


def test_a_past_case_cannot_be_called_a_question_period():
    with pytest.raises(ValueError):question_period_paths(prices(),symbol='002514.SZ',asked_on='2026-06-01')


def test_resealed_foreign_period_is_hidden_without_reanchoring_original():
    r,a=setup();f=freeze_argument_timelines(r,**a);t=deepcopy(f['event_timelines']['002514.SZ'])
    t['question_period']['summary']='unbound change';seal(t['question_period']);seal(t)
    assert project_argument_timeline(t,record=a['record'],review=f,paths=a['paths'],symbol='002514.SZ') is None
    f['event_timelines']['002514.SZ']=t
    q=assemble([a['record']],a['paths'],reviews={a['record']['id']:f})['details']['002514.SZ']['questions'][0]
    assert q['anchor_date'] is None and 'question_chart_sources' not in q
    assert q['review']['event_timeline_status']=='needs_refresh'


@pytest.mark.parametrize('completed,expected',[('2021-05-18T08:00:00Z','2021-05-17'),('2021-05-19T08:00:00Z','2021-05-19')])
def test_answer_completion_after_close_controls_original_reference(completed,expected):
    r,a=setup();a['record']['answers'][0]['completed_at']=completed
    r=freeze_argument_review({'question_digest':question_digest(a['record']),'then_quote':'更像洗盘','focused_symbol':'002514.SZ','headline':'依据需修正'},a['record'])
    f=freeze_argument_timelines(r,**a)
    q=assemble([a['record']],a['paths'],reviews={a['record']['id']:f})['details']['002514.SZ']['questions'][0]
    assert q['anchor_date']==expected
