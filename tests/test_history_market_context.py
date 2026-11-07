from copy import deepcopy
import pytest
from research_history import assemble, question_digest
from research_history_reviews import freeze_argument_review
from research_history_market_context import market_period_paths, freeze_market_context, project_market_context, PERIOD_VERSION
from test_research_history import sample
from test_history_case_period import period
from test_argument_event_timelines import seal


def prices():
    p=period()
    return seal({'version':PERIOD_VERSION,'price_basis':'market_and_st_price_only','title':'原问时段','summary':'市场背景','source_note':'不代表钨行业或任何公司回报',
        'paths':{k:v for k,v in p['paths'].items() if k!='stocks'},'source_refs':[r for r in p['source_refs'] if r['key'] in {'market','st'}]})


def fixture():
    paths,record=sample();record.update(symbols=[],asked_at='2021-05-17T08:00:00Z',sources=[{'kind':'chatgpt','thread_id':'same-chat'}])
    target=deepcopy(record);target.update(id='related',question='重点看这家公司',symbols=['002514.SZ'])
    review=freeze_argument_review({'question_digest':question_digest(record),'then_quote':'更像洗盘','headline':'解释需要对齐窗口'},record)
    args={'record':record,'period':prices(),'related_records':[target],'source_run_id':'RUN-'+'A'*24,'source_pack_id':'EP-real-study'}
    return paths,record,target,review,args


def test_old_macro_original_gets_only_market_context_and_verified_bidirectional_links():
    paths,record,target,review,args=fixture();before=deepcopy((paths,record,target,review))
    result=freeze_market_context(review,**args)
    assembled=assemble([record,target],paths,reviews={record['id']:result})
    own=assembled['details']['market']['questions'][0];company=assembled['details']['002514.SZ']['questions'][0]
    assert own['anchor_date']=='2021-05-17' and set(own['question_chart_sources'])=={'market','st'}
    assert not {'market_context','market_context_trace'}.intersection(own['review'])
    assert set(own['outcomes'])=={'market','st'} and not {'price_digest','price_through'}.intersection(own['review'])
    assert own['related_questions']==[{'question_id':'related','symbol':'002514.SZ','name':paths['stocks']['002514.SZ']['name'],'question':target['question']}]
    assert company['related_questions'][0]['question_id']==record['id'] and company['related_questions'][0]['symbol']=='market'
    assert company['anchor_date'] is None and company['review'] is None
    assert (paths,record,target,review)==before


@pytest.mark.parametrize('change',[
    lambda p:p.update(price_basis='commodity_price'),
    lambda p:p['paths'].update(stocks={'002514.SZ':{}}),
    lambda p:p['paths']['market'][1].update(value=0),
    lambda p:p['paths']['market'][1].update(level=101),
    lambda p:p['paths']['st'][1].update(value=None,level=None),
    lambda p:p['source_refs'][0].update(url='https://example.com/other'),
    lambda p:p['source_refs'][0].update(sha256='bad'),
    lambda p:p['source_refs'][0].update(observed_at='2099-01-01T00:00:00Z'),
    lambda p:p['source_refs'][0].update(observed_at='2026-01-01T00:00:00'),
    lambda p:p['source_refs'].pop(),
])
def test_wrong_units_company_scope_quote_gaps_or_sources_cannot_be_resealed(change):
    p=prices();change(p)
    with pytest.raises((ValueError,KeyError,TypeError)):market_period_paths(seal(p),asked_on='2021-05-17')


@pytest.mark.parametrize('change',['original','related_answer','related_thread','period','study','review'])
def test_changed_basis_hides_old_context_and_both_link_directions(change):
    paths,record,target,review,args=fixture();result=freeze_market_context(review,**args)
    if change=='original':record['question']+='追加'
    elif change=='related_answer':target['answers'][0]['text']='另一份回答'
    elif change=='related_thread':target['sources'][0]['thread_id']='other-chat'
    elif change=='period':result['market_context']['period']['summary']='另一语义';seal(result['market_context']['period']);seal(result['market_context'])
    elif change=='study':result['market_context']['source_run_id']='RUN-'+'B'*24;seal(result['market_context'])
    else:result['headline']='重写结论'
    assert project_market_context(result,record=record,records={record['id']:record,target['id']:target}) is None
    assembled=assemble([record,target],paths,reviews={record['id']:result})
    for d in assembled['details'].values():
        for q in d['questions']:assert 'related_questions' not in q and 'question_chart_sources' not in q


@pytest.mark.parametrize('bad',['self','foreign_thread','duplicate','stock_scope'])
def test_related_question_must_be_an_original_in_the_same_conversation(bad):
    _,record,target,review,args=fixture()
    if bad=='self':args['related_records']=[record]
    elif bad=='foreign_thread':target['sources'][0]['thread_id']='other'
    elif bad=='duplicate':args['related_records']=[target,target]
    else:record['symbols']=['002514.SZ']
    with pytest.raises(ValueError):freeze_market_context(review,**args)


def test_unrelated_company_and_existing_price_paths_remain_unchanged():
    paths,record,target,review,args=fixture();third=deepcopy(target);third['id']='unrelated'
    result=freeze_market_context(review,**args)
    a=assemble([record,target,third],paths,reviews={record['id']:result})
    q=next(q for q in a['details']['002514.SZ']['questions'] if q['id']=='unrelated')
    assert 'related_questions' not in q and 'question_chart_sources' not in q
    assert a['details']['002514.SZ']['chart_sources']['stock']==paths['stocks']['002514.SZ']['points']
