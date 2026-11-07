from copy import deepcopy
import json

import pytest

from research_history import assemble,freeze_reviews,question_digest,review_anchor
from research_history_reviews import ARGUMENT_BASIS,ARGUMENT_VERSION,PRICE_FIELDS,freeze_argument_review,freeze_review,resolve_review
from test_research_history import sample
from test_research_history_reviews import fixture as window_fixture,write_migration_inputs


def argument_fixture(*,ranged=True):
    paths,record=sample();paths=deepcopy(paths)
    if ranged:record.update(asked_at=None,asked_on=None,time_precision='range',asked_from='2026-06-01',asked_through='2026-06-04')
    draft={'question_digest':question_digest(record),'then_quote':'更像洗盘','headline':'动机判断缺少证据',
           'assessment':'仅核对原答的推理边界','lessons':['不以熟悉一只股票代替证据'],
           'explanation':[],'reviewed_at':'2026-11-06T00:00:00Z'}
    return paths,record,freeze_argument_review(draft,record)


def current(paths,record,review):
    return assemble([record],paths,reviews={record['id']:review})['details']['002514.SZ']['questions'][0]


def test_range_can_have_a_substantive_argument_review_without_a_selected_return_window():
    paths,record,review=argument_fixture();row=current(paths,record,review)
    assert row['review']==review and row['review_status']=='argument_only'
    assert row['anchor_date'] is None and row['outcomes']=={}
    assert review['review_binding_version']==ARGUMENT_VERSION and review['assessment_basis']==ARGUMENT_BASIS
    assert not PRICE_FIELDS.intersection(review)
    assert review_anchor(record,review,{}) is None


def test_argument_validation_has_no_price_dependency_and_future_observations_are_not_new_assessed_results():
    _,record,review=argument_fixture()
    assert resolve_review(review,record,{},question_digest(record),None)=={'review':review,'review_status':'argument_only'}
    paths,record,review=argument_fixture();paths['market'][-1]['level']=999;paths['st_name']='更正板块'
    paths['calendar'].append('2026-06-10')
    row=current(paths,record,review)
    assert row['review']==review and row['review_status']=='argument_only' and row['outcomes']=={}


def test_a_dated_argument_review_keeps_price_observations_separate_from_assessment():
    paths,record,review=argument_fixture(ranged=False);row=current(paths,record,review)
    assert row['outcomes']['stock']['five_day']['change_pct'] is not None
    assert row['review_status']=='argument_only' and not PRICE_FIELDS.intersection(row['review'])


@pytest.mark.parametrize('field',['question','answer','date_range','date_resolution','background','visual'])
def test_original_text_date_context_or_image_corrections_withdraw_argument_review(field):
    paths,record,review=argument_fixture()
    if field=='question':record['question']='更正问题'
    elif field=='answer':record['answers'][0]['text']='更正回答'
    elif field=='date_range':record['asked_through']='2026-06-05'
    elif field=='date_resolution':record.update(time_precision='day',asked_on='2026-06-02')
    elif field=='background':record['question_context']={'version':'history_question_context_v1','question_id':'prior','question':'补回原问题','asked_on':'2026-06-01','source_url':'https://chatgpt.com/c/source'}
    else:record['question_visuals']=[{'kind':'rendered_capture','sha256':'a'*64,'source_thread_id':'source','source_message_id':'message'}]
    row=current(paths,record,review)
    assert row['review'] is None and row['previous_review']==review and row['review_status']=='original_changed'


@pytest.mark.parametrize('change',['record_id','scope','focus','kind','version','basis'])
def test_argument_review_cannot_move_to_another_original_or_claim_a_different_scope(change):
    paths,record,review=argument_fixture()
    if change=='record_id':record['id']='another-original'
    elif change=='scope':record['symbols'].append('000001.SZ')
    elif change=='focus':review['focused_symbol']='000001.SZ'
    elif change=='kind':record['kind']='saved_research'
    elif change=='version':review['review_binding_version']='unknown'
    else:review['assessment_basis']='other'
    row=current(paths,record,review)
    assert row['review'] is None and row['previous_review']==review and row['review_status']=='review_basis_changed'


@pytest.mark.parametrize('field',sorted(PRICE_FIELDS))
def test_price_metadata_cannot_be_mixed_into_an_argument_only_review_even_when_null(field):
    paths,record,review=argument_fixture();review[field]=None
    with pytest.raises(ValueError,match='price assessment'):freeze_argument_review(review,record)
    row=current(paths,record,review)
    assert row['review'] is None and row['review_status']=='review_basis_changed'


def test_forged_quote_cannot_hide_behind_argument_metadata_or_price_changes():
    paths,record,review=argument_fixture();review['then_quote']='原答没有这句话';review['price_through']=None
    with pytest.raises(ValueError,match='quote'):current(paths,record,review)


def test_factories_do_not_silently_convert_or_rebind_existing_assessments():
    paths,record,window=window_fixture()
    with pytest.raises(ValueError,match='price assessment'):freeze_argument_review(window,record)
    for field in PRICE_FIELDS:window.pop(field,None)
    with pytest.raises(ValueError,match='rebind'):freeze_argument_review(window,record)
    paths,record,argument=argument_fixture()
    with pytest.raises(ValueError,match='separate binding'):freeze_review(argument,record,paths,None)
    assert freeze_argument_review(argument,record)==argument
    record['kind']='saved_research'
    with pytest.raises(ValueError,match='original question'):freeze_argument_review(argument,record)


def test_argument_freeze_rejects_a_stale_original_or_conflicting_initial_metadata():
    _,record,review=argument_fixture();review.pop('review_binding_version')
    review['original_record_id']='wrong-original'
    with pytest.raises(ValueError,match='conflicts'):freeze_argument_review(review,record)
    _,record,review=argument_fixture();record['question']='新的原问'
    with pytest.raises(ValueError,match='original binding'):freeze_argument_review(review,record)


def test_adding_argument_label_cannot_reclassify_a_price_review():
    paths,record,review=window_fixture();review['assessment_basis']=ARGUMENT_BASIS
    row=current(paths,record,review)
    assert row['review'] is None and row['review_status']=='review_basis_changed'


def test_guarded_migration_preserves_argument_scope_text_and_writing_time(tmp_path):
    paths,record,review=argument_fixture();imported=write_migration_inputs(tmp_path,paths,record,review)
    before=(tmp_path/'reviews.json').read_bytes()
    assert freeze_reviews(imported,root=tmp_path)['frozen_reviews']==1
    assert (tmp_path/'reviews.json').read_bytes()==before
    assert json.loads(before)[record['id']]==review
    record['answers'][0]['text']='已更正的回答'
    with pytest.raises(ValueError,match='substantive'):freeze_reviews(imported,root=tmp_path)
    assert (tmp_path/'reviews.json').read_bytes()==before
