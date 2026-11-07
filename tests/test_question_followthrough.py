"""A missing answer can have a later event study, never a fabricated old verdict."""
from copy import deepcopy
import pytest
from canonical_json import digest
from research_history import question_digest
from research_history_reviews import (freeze_question_followthrough, freeze_argument_review,
    freeze_review, resolve_review, context_binding_matches)
from research_history_events import freeze_argument_timelines, project_argument_timeline


def fixture():
    record={'id':'q','kind':'original_question','asked_on':'2026-06-02','time_precision':'day',
            'question':'有动力压价吗','symbols':['002856.SZ'],'answers':[],'sources':[]}
    review=freeze_question_followthrough({'question_digest':question_digest(record),'then_quote':'',
        'headline':'先核定价和履约，不由跌幅猜动机','assessment':'本次补做事件复盘，原答待恢复。'},record)
    return record,review


def resolve(record,review):
    return resolve_review(review,record,{},question_digest(record),None)


def test_missing_answer_stays_missing_and_gets_separate_status():
    record,review=fixture();before=deepcopy(record)
    assert resolve(record,review)['review_status']=='question_followthrough'
    assert record==before and context_binding_matches(review,record)
    assert 'price_through' not in review and review['then_quote']==''


@pytest.mark.parametrize('field,value', [('then_quote','相邻问答的回答'),('price_through','2026-06-03'),
    ('review_binding_version','history_review_window_v1'),('assessment_basis','original_argument_only'),
    ('focused_symbol','603398.SH'),('scope_symbols',['603398.SH']),('original_record_id','other')])
def test_cannot_relabel_a_trade_or_other_answer_as_followthrough(field,value):
    record,review=fixture();review[field]=value
    with pytest.raises(ValueError):freeze_question_followthrough(review,record)
    assert resolve(record,review)['review'] is None


def test_answer_recovery_withdraws_old_followthrough_instead_of_grading_it():
    record,review=fixture();record['answers']=[{'text':'真正找回的原答'}]
    assert resolve(record,review)['review_status']=='original_changed'
    with pytest.raises(ValueError):freeze_question_followthrough({**review,'question_digest':question_digest(record)},record)
    forged={**review,'question_digest':question_digest(record)}
    assert resolve(record,forged)['review_status']=='review_basis_changed'


def test_legacy_quote_guards_still_reject_an_unanswered_original():
    record,review=fixture()
    with pytest.raises(ValueError):freeze_argument_review(review,record)
    with pytest.raises(ValueError):freeze_review(review,record,{},None)


def context():
    record,review=fixture();days=['2026-06-01','2026-06-02','2026-06-03','2026-06-04']
    points=[{'date':d,'value':10+i,'level':100+i} for i,d in enumerate(days)]
    paths={'calendar':days,'stocks':{'002856.SZ':{'points':points}},'market':points,'st':points}
    event={'id':'e','symbol':'002856.SZ','published_on':'2026-06-03','publication_precision':'day',
        'entity_scope':'issuer','source_id':'1225577942','fact':'后续有条件签约',
        'state_before':'pending','state_after':'conditional_agreement','change_kind':'progress'}
    args=dict(record=record,paths=paths,source_run_id='RUN-'+'A'*24,source_pack_id='EP-REAL',
        events=[event],annotations={'e':{'title':'签约','change':'新增协议','interpretation':'仍核付款',
        'watch':'追履约','lens_ids':['RL-C-004'],'page':1}},
        sources={'e':{'announcement_id':'1225577942','published_on':'2026-06-03','sha256':'a'*64,
        'url':'https://static.cninfo.com.cn/a.PDF','title':'协议','pages':2}},
        applied_lens_ids=['RL-C-004'],learning={'lesson':'签约与付款分开','next_check':'保留失败分支'})
    frozen=freeze_argument_timelines(review,**args)
    return record,frozen,args


def test_real_event_projection_preserves_unanswered_scope_and_context():
    record,review,args=context();value=review['event_timelines']['002856.SZ']
    assert value['version']=='history_event_timeline_v5' and value['assessment_basis']=='question_followthrough'
    assert project_argument_timeline(value,record=record,review=review,paths=args['paths'],symbol='002856.SZ')==value
    assert value['events'][0]['relation']=='after_question' and not value['causal_effect_identified']


@pytest.mark.parametrize('change',['answer','question','price','basis','version','reading','stock','run'])
def test_changed_or_relabelled_context_is_hidden_even_if_resealed(change):
    record,review,args=context();value=deepcopy(review['event_timelines']['002856.SZ']);paths=deepcopy(args['paths'])
    if change=='answer':record['answers']=[{'text':'找回原答'}]
    if change=='question':record['question']='另一条问题'
    if change=='price':paths['market'][0]['value']=2
    if change=='basis':value['assessment_basis']='original_argument_only'
    if change=='version':value['version']='history_event_timeline_v2'
    if change=='reading':value['events'][0]['interpretation']='已完成'
    if change=='stock':value['symbol']='603398.SH'
    if change=='run':value['source_run_id']='RUN-'+'B'*24
    value['content_digest']=digest({k:v for k,v in value.items() if k!='content_digest'})
    assert project_argument_timeline(value,record=record,review=review,paths=paths,symbol='002856.SZ') is None


def test_followthrough_cannot_borrow_a_different_historical_case_period():
    record,review,args=context();args['case_periods']={'002856.SZ':{'unverified':'case'}}
    with pytest.raises(ValueError):freeze_argument_timelines(review,**args)
