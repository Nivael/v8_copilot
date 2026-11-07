from copy import deepcopy

import pytest

from research_history import assemble,question_digest,range_chart_context
from research_history_reviews import PRICE_FIELDS,freeze_argument_review
from test_research_history import sample


def fixture():
    paths,record=sample()
    paths['market']=deepcopy(paths['market']);paths['st']=deepcopy(paths['st'])
    paths['stocks']['002514.SZ']['points']=deepcopy(paths['stocks']['002514.SZ']['points'])
    record.update(asked_at=None,asked_on=None,time_precision='range',asked_from='2026-06-03',asked_through='2026-06-04')
    return paths,record


def test_visual_reference_is_common_and_before_the_range_without_becoming_a_return_anchor():
    paths,record=fixture();original=deepcopy(record);key=question_digest(record)
    row=assemble([record],paths)['details']['002514.SZ']['questions'][0]
    assert row['range_context']=={'kind':'pre_range_common_close','reference_date':'2026-06-02'}
    assert row['anchor_date'] is None and row['outcomes']=={} and row['asked_at'] is None and row['asked_on'] is None
    assert question_digest(record)==key and record==original


@pytest.mark.parametrize('kind',['stock','market','st'])
@pytest.mark.parametrize('invalid',[None,0,float('nan')])
def test_a_missing_or_invalid_close_in_any_line_requires_an_earlier_common_reference(kind,invalid):
    paths,record=fixture()
    points=paths['stocks']['002514.SZ']['points'] if kind=='stock' else paths[kind]
    points[1]['level']=invalid
    assert range_chart_context(record,paths,'002514.SZ')['reference_date']=='2026-06-01'


def test_no_reference_is_inferred_from_an_in_range_or_later_close():
    paths,record=fixture();record.update(asked_from='2026-05-30',asked_through='2026-06-02')
    row=assemble([record],paths)['details']['002514.SZ']['questions'][0]
    assert row['range_context'] is None and row['anchor_date'] is None and row['outcomes']=={}


def test_no_context_is_published_when_market_observations_have_not_reached_the_range():
    paths,record=fixture();record.update(asked_from='2026-06-10',asked_through='2026-06-11')
    assert range_chart_context(record,paths,'002514.SZ') is None


def test_weekend_bounds_use_the_prior_common_friday_and_do_not_invent_weekend_closes():
    paths,record=fixture();record.update(asked_from='2026-06-06',asked_through='2026-06-07')
    row=assemble([record],paths)['details']['002514.SZ']['questions'][0]
    assert row['range_context']['reference_date']=='2026-06-05'
    assert row['anchor_date'] is None and row['outcomes']=={}
    assert not any(p['date'] in ['2026-06-06','2026-06-07'] for p in paths['market'])


def test_no_common_valid_prior_close_leaves_the_context_unavailable():
    paths,record=fixture()
    paths['market'][0]['level']=None;paths['st'][1]['level']=None
    assert range_chart_context(record,paths,'002514.SZ') is None


def test_unresolved_security_context_uses_only_the_market_and_st_without_guessing_a_stock():
    paths,record=fixture();record['symbols']=[]
    paths['stocks']['002514.SZ']['points'][1]['level']=None
    detail=assemble([record],paths)['details']['market'];row=detail['questions'][0]
    assert row['range_context']['reference_date']=='2026-06-02'
    assert set(detail['chart_sources'])=={'market','st'}


@pytest.mark.parametrize('ranged',[True,False])
def test_imported_context_annotations_are_not_trusted_or_carried_into_precise_questions(ranged):
    paths,record=fixture();record['range_context']={'kind':'pre_range_common_close','reference_date':'2099-01-01'}
    if not ranged:record.update(asked_at='2026-06-03T08:00:00Z',asked_on='2026-06-03',time_precision='instant')
    row=assemble([record],paths)['details']['002514.SZ']['questions'][0]
    if ranged:assert row['range_context']['reference_date']=='2026-06-02'
    else:assert 'range_context' not in row
    assert record['range_context']['reference_date']=='2099-01-01'


def test_context_observations_do_not_upgrade_an_argument_review_into_a_price_assessment():
    paths,record=fixture()
    review=freeze_argument_review({'question_digest':question_digest(record),'then_quote':'更像洗盘','headline':'只评推理'},record)
    row=assemble([record],paths,reviews={record['id']:review})['details']['002514.SZ']['questions'][0]
    assert row['range_context']['reference_date']=='2026-06-02'
    assert row['review']==review and row['review_status']=='argument_only'
    assert row['anchor_date'] is None and row['outcomes']=={} and not PRICE_FIELDS.intersection(review)
