from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from canonical_json import digest
from data_refresh import atomic_write_json
from research_history import assemble,freeze_reviews,question_digest,review_anchor
from research_history_reviews import freeze_review
from test_research_history import sample


def fixture():
    paths,record=sample()
    paths=deepcopy(paths)
    review={'question_digest':question_digest(record),'price_digest':digest(paths),'then_quote':'更像洗盘',
            'headline':'需要纠正','reviewed_at':'2026-11-06T00:00:00Z','assessment':'短期方向有误','lessons':['少猜动机']}
    frozen=freeze_review(review,record,paths,review_anchor(record,review,paths))
    return paths,record,frozen


def row(paths,record,review,symbol='002514.SZ'):
    return assemble([record],paths,reviews={record['id']:review})['details'][symbol]['questions'][0]


def test_future_observations_preserve_assessed_window_but_extend_price_outcomes():
    paths,record,review=fixture();old=deepcopy(review)
    paths['calendar'].append('2026-06-10')
    for points in [paths['market'],paths['st'],paths['stocks']['002514.SZ']['points']]:
        # Shared fixture lists are cloned separately here to keep one row per day.
        if not any(p['date']=='2026-06-10' for p in points):points.append({'date':'2026-06-10','value':30,'level':30})
    result=row(paths,record,review)
    assert result['review']==old and result['review_status']=='new_observations'
    assert result['review']['price_through']=='2026-06-09'
    assert result['outcomes']['stock']['latest']['date']=='2026-06-10'
    assert result['outcomes']['stock']['latest']['change_pct']==pytest.approx((30/90-1)*100)


def test_unrelated_stock_names_and_source_fetch_metadata_do_not_revoke_review():
    paths,record,review=fixture()
    paths['stocks']['000001.SZ']={'name':'其他股票','points':[{'date':'2026-06-02','value':999,'level':999}]}
    paths['stocks']['002514.SZ']['name']='更新显示名';paths['checked_at']='later';paths['sources']={'new_fetch':'digest'}
    paths['market'][0]['value']=777  # Before this review's anchor.
    assert row(paths,record,review)['review_status']=='current'


@pytest.mark.parametrize('change',['stock','market','st','missing_row','missing_stock','gap','calendar','identity','basis'])
def test_changed_in_window_prices_gaps_calendar_and_benchmark_identity_withdraw_current_review(change):
    paths,record,review=fixture()
    if change in ['stock','market','st']:
        points=paths['stocks']['002514.SZ']['points'] if change=='stock' else paths[change]
        points[-1]['value']=39
    elif change=='missing_row':paths['stocks']['002514.SZ']['points'].pop()
    elif change=='missing_stock':
        record['symbols'].append('000001.SZ')
    elif change=='gap':paths['st'][-1]['level']=None
    elif change=='calendar':paths['calendar'].pop(-2)
    elif change=='identity':paths['st_source_url']='https://example.org/different-index'
    else:paths['stocks']['002514.SZ']['points'][-1]['basis']='corrected'
    result=row(paths,record,review)
    assert result['review'] is None and result['previous_review']==review
    assert result['review_status']=='price_changed'


def test_original_changes_withdraw_but_changed_prices_cannot_hide_forged_quote():
    paths,record,review=fixture();record['answers'][0]['text']='更正的回答'
    assert row(paths,record,review)['review_status']=='original_changed'
    paths,record,review=fixture();paths['st'][-1]['level']=0;review['then_quote']='原文没有的句子'
    with pytest.raises(ValueError,match='quote'):row(paths,record,review)


def test_review_uses_its_focused_stock_anchor_even_in_associated_stock_view():
    paths,record,review=fixture()
    second=deepcopy(paths['stocks']['002514.SZ']);second['points'][1]['level']=None
    paths['stocks']['000001.SZ']=second;record['symbols'].append('000001.SZ')
    review.update(question_digest=question_digest(record),focused_symbol='002514.SZ')
    review=freeze_review(review,record,paths,review_anchor(record,review,paths))
    result=row(paths,record,review,'000001.SZ')
    assert result['anchor_date']=='2026-06-01'
    assert result['review']['anchor_date']=='2026-06-02' and result['review_status']=='current'
    # Altering the previously valid focus baseline also invalidates the binding.
    paths['stocks']['002514.SZ']['points'][1]['level']=None
    assert row(paths,record,review,'000001.SZ')['review_status']=='price_changed'


def test_missing_associated_stock_or_assessed_endpoint_cannot_keep_a_review():
    paths,record,review=fixture()
    paths['stocks']['000001.SZ']=deepcopy(paths['stocks']['002514.SZ']);record['symbols'].append('000001.SZ')
    review['focused_symbol']='002514.SZ'
    review=freeze_review(review,record,paths,review_anchor(record,review,paths))
    del paths['stocks']['000001.SZ']
    assert row(paths,record,review)['review_status']=='price_changed'
    paths,record,review=fixture();paths['calendar'].pop()
    assert row(paths,record,review)['review_status']=='price_changed'


def test_mixed_market_question_is_shared_across_market_and_stock_with_one_focused_review():
    paths,record,_=fixture();record['market_scope']=True
    review=freeze_review({'question_digest':question_digest(record),'then_quote':'更像洗盘','headline':'大盘与个股分开检验'},
                         record,paths,review_anchor(record,{},paths))
    result=assemble([record],paths,reviews={record['id']:review})
    assert set(result['details'])=={'market','002514.SZ'} and len(result['unique'])==1
    for detail in result['details'].values():
        q=detail['questions'][0]
        assert q['id']==record['id'] and q['review']==review and q['review_status']=='current'
        assert q['review_focused_name']=='大盘与ST' and q['review']['focused_symbol']=='market'
    assert 'stock' not in result['details']['market']['chart_sources']
    paths['stocks']['002514.SZ']['points'][-1]['value']=19
    assert row(paths,record,review)['review_status']=='price_changed'


def test_market_scope_change_withdraws_review_and_cannot_be_inferred_from_a_stock_scope():
    paths,record,review=fixture();before=question_digest(record)
    with pytest.raises(ValueError,match='focused stock'):
        freeze_review({**review,'focused_symbol':'market'},record,paths,review_anchor(record,review,paths))
    record['market_scope']=False;assert question_digest(record)==before
    record['market_scope']=True
    assert row(paths,record,review)['review_status']=='original_changed'
    record['market_scope']='true'
    with pytest.raises(ValueError,match='market scope'):question_digest(record)


def test_mixed_market_argument_review_has_no_return_binding_and_withdraws_when_scope_changes():
    from research_history_reviews import freeze_argument_review
    paths,record,_=fixture();record['market_scope']=True
    review=freeze_argument_review({'question_digest':question_digest(record),'then_quote':'更像洗盘','headline':'只核逻辑'},record)
    q=row(paths,record,review,'market')
    assert q['review_status']=='argument_only' and q['review']['focused_symbol']=='market'
    assert 'price_through' not in q['review']
    record['market_scope']=False
    assert row(paths,record,review)['review_status']=='original_changed'


@pytest.mark.parametrize('through',['2026-06-11','2026-05-29','invalid'])
def test_cannot_freeze_future_or_out_of_range_window(through):
    paths,record,review=fixture()
    with pytest.raises(ValueError,match='window'):freeze_review(review,record,paths,'2026-06-02',through=through)


def write_migration_inputs(root,paths,record,review):
    import research_history_prices
    packet={'data':paths,'processor_digest':sha256(Path(research_history_prices.__file__).read_bytes()).hexdigest()}
    packet['content_digest']=digest(packet);atomic_write_json(root/'price_paths/current.json',packet)
    atomic_write_json(root/'reviews.json',{record['id']:review})
    return {'records':[record],'sources':[]}


def test_guarded_migration_is_idempotent_and_preserves_assessment_date_and_text(tmp_path):
    paths,record,review=fixture()
    for field in ['review_binding_version','price_through','scope_symbols','focused_symbol','anchor_date','price_window_digest']:review.pop(field)
    imported=write_migration_inputs(tmp_path,paths,record,review)
    assert freeze_reviews(imported,root=tmp_path)['frozen_reviews']==1
    frozen=json.loads((tmp_path/'reviews.json').read_text())[record['id']]
    for key,value in review.items():assert frozen[key]==value
    assert frozen['price_through']=='2026-06-09'
    before=(tmp_path/'reviews.json').read_bytes();freeze_reviews(imported,root=tmp_path)
    assert (tmp_path/'reviews.json').read_bytes()==before


def test_repeated_migration_never_extends_a_deliberately_shorter_assessment(tmp_path):
    paths,record,review=fixture()
    review=freeze_review(review,record,paths,review_anchor(record,review,paths),through='2026-06-05')
    imported=write_migration_inputs(tmp_path,paths,record,review)
    freeze_reviews(imported,root=tmp_path)
    assert json.loads((tmp_path/'reviews.json').read_text())[record['id']]==review


@pytest.mark.parametrize('change',['prices','original','missing_original'])
def test_migration_refuses_to_rebind_stale_legacy_review_and_leaves_file_unchanged(tmp_path,change):
    paths,record,review=fixture()
    for field in ['review_binding_version','price_through','scope_symbols','focused_symbol','anchor_date','price_window_digest']:review.pop(field)
    if change=='prices':paths['st'][-1]['level']=38
    if change=='original':record['question']='不同问题'
    imported=write_migration_inputs(tmp_path,paths,record,review)
    if change=='missing_original':imported['records']=[]
    before=(tmp_path/'reviews.json').read_bytes()
    with pytest.raises(ValueError):freeze_reviews(imported,root=tmp_path)
    assert (tmp_path/'reviews.json').read_bytes()==before
