from copy import deepcopy
import pytest
from canonical_json import digest
from research_history import assemble, question_digest
from research_history_reviews import freeze_argument_review, PRICE_FIELDS
from research_history_events import freeze_argument_timelines, project_argument_timeline, project_review_events
from test_research_history import sample


def fixture():
    paths, record = sample()
    paths['stocks']['603272.SH'] = {**deepcopy(paths['stocks']['002514.SZ']), 'name': '另一公司'}
    record.update(symbols=['002514.SZ', '603272.SH'], market_scope=True)
    review = freeze_argument_review({'question_digest': question_digest(record), 'then_quote': '更像洗盘',
        'focused_symbol': 'market', 'scope_label': '两家公司原分组', 'headline': '需修正'}, record)
    events, annotations, sources = [], {}, {}
    for i, symbol in enumerate(record['symbols']):
        key = str(i)
        events.append({'id': key, 'symbol': symbol, 'published_on': '2026-06-03', 'publication_precision': 'day',
            'entity_scope': 'issuer', 'source_id': '122500000'+key, 'fact': '方案尚待落实',
            'state_before': 'none', 'state_after': 'proposal', 'change_kind': 'progress'})
        annotations[key] = {'title': '方案'+key, 'change': '新提出方案', 'interpretation': '不算交割',
            'watch': '查落实', 'lens_ids': ['RL-C-004'], 'page': 1}
        sources[key] = {'url': 'https://example.com/'+key+'.pdf', 'announcement_id': '122500000'+key,
            'published_on': '2026-06-03', 'sha256': 'a'*64, 'pages': 2, 'title': '原公告'}
    args = dict(record=record, paths=paths, source_run_id='RUN-'+'A'*24, source_pack_id='EP-real-study',
        events=events, annotations=annotations, sources=sources, applied_lens_ids=['RL-C-004'],
        learning={'lesson': '按真实阶段更新判断', 'next_check': '补失败与未完成对照'})
    return review, args


def seal(value):
    value['content_digest'] = digest({k:v for k,v in value.items() if k != 'content_digest'})
    return value


def test_argument_group_projects_only_its_company_without_a_trade_or_experience():
    review, args = fixture(); original = deepcopy((review,args))
    result = freeze_argument_timelines(review, **args)
    assert (review,args) == original and not PRICE_FIELDS.intersection(result)
    assembled = assemble([args['record']], args['paths'], reviews={args['record']['id']:result})
    for symbol in args['record']['symbols']:
        projected = assembled['details'][symbol]['questions'][0]['review']
        assert 'event_timelines' not in projected
        assert projected['event_timeline']['symbol'] == symbol
        assert len(projected['event_timeline']['events']) == 1
        assert 'experience_id' not in projected['event_timeline']
        assert projected['scope_label'] == '两家公司原分组'
    market = assembled['details']['market']['questions'][0]['review']
    assert not {'event_timeline','event_timelines','event_timeline_status'}.intersection(market)


@pytest.mark.parametrize('field,value', [('question_id','foreign'),('question_digest','changed'),('symbol','603272.SH'),
    ('source_run_id','RUN-'+'B'*24),('source_pack_id','other'),('source_events_digest','other'),
    ('review_basis_digest','other'),('reading_digest','other'),('causal_effect_identified',True),('experience_id','EXP-'+'B'*20)])
def test_resealed_foreign_study_or_false_experience_is_hidden(field,value):
    review,args=fixture(); result=freeze_argument_timelines(review,**args)
    value_to_test=deepcopy(result['event_timelines']['002514.SZ']); value_to_test[field]=value
    assert project_argument_timeline(seal(value_to_test),record=args['record'],review=result,paths=args['paths'],symbol='002514.SZ') is None


@pytest.mark.parametrize('field,value', [('interpretation','price proves acquisition'),('published_on','2026-06-04'),
    ('scheduled_for','2026-06-09'),('lens_ids',['RL-C-002']),('source',{'url':'https://other.com'})])
def test_resealed_event_reading_cannot_diverge_from_review_trace(field,value):
    review,args=fixture(); result=freeze_argument_timelines(review,**args)
    timeline=deepcopy(result['event_timelines']['002514.SZ']); timeline['events'][0][field]=value
    timeline['reading_digest']=digest([{k:v for k,v in e.items() if k!='context'} for e in timeline['events']])
    assert project_argument_timeline(seal(timeline),record=args['record'],review=result,paths=args['paths'],symbol='002514.SZ') is None


@pytest.mark.parametrize('changed', ['original','scope','review','study','prices','context'])
def test_changed_inputs_hide_only_event_context(changed):
    review,args=fixture(); result=freeze_argument_timelines(review,**args)
    if changed=='original':args['record']['question']+='new'
    elif changed=='scope':args['record']['symbols'].remove('002514.SZ')
    elif changed=='review':result['headline']='changed conclusion'
    elif changed=='study':result['event_trace']['source_run_id']='RUN-'+'C'*24
    elif changed=='prices':args['paths']['market'][-1]['level']=99
    else:
        t=result['event_timelines']['002514.SZ'];t['events'][0]['context']['windows']['1']['change_pct']['stock']='0';seal(t)
    projected=project_review_events(result,record=args['record'],paths=args['paths'],symbol='002514.SZ')
    assert projected['headline']==result['headline']
    assert projected['event_timeline_status']=='needs_refresh' and 'event_timelines' not in projected
    assert 'event_timeline' not in projected


def test_changed_argument_basis_does_not_leak_stale_maps_in_previous_review():
    review,args=fixture(); result=freeze_argument_timelines(review,**args)
    result['scope_symbols']=[]
    rows=assemble([args['record']],args['paths'],reviews={args['record']['id']:result})['details']
    assert rows['002514.SZ']['questions'][0]['review'] is None
    assert not {'event_timeline','event_timelines'}.intersection(rows['002514.SZ']['questions'][0]['previous_review'])


@pytest.mark.parametrize('kind',['foreign_event','uninvoked_lens','invented_candidate'])
def test_builder_rejects_foreign_scope_or_unapplied_lens(kind):
    review,args=fixture()
    if kind=='foreign_event':args['events'][0]['symbol']='688622.SH'
    elif kind=='uninvoked_lens':args['annotations']['0']['lens_ids']=['RL-C-002']
    else:args['learning']['experience_id']='EXP-'+'A'*20
    with pytest.raises(ValueError):freeze_argument_timelines(review,**args)


def test_scheduled_warning_local_date_and_missing_price_are_explicit():
    review,args=fixture()
    args['events'][0].update(state_after='scheduled',occurred_on='2026-06-09')
    args['annotations']['0']['scheduled_role']='warning_effective_date'
    args['events'][1]['occurred_on']='2026-06-01';args['annotations']['1']['occurred_date_qualifier']='local_time'
    args['paths']['stocks']['002514.SZ']['points'][2]['level']=None
    result=freeze_argument_timelines(review,**args)
    warning=result['event_timelines']['002514.SZ']['events'][0]
    assert warning['occurred_on'] is None and warning['scheduled_for']=='2026-06-09'
    assert warning['context']['windows']['1']['change_pct']['stock'] is None
    assert result['event_timelines']['603272.SH']['events'][0]['occurred_date_qualifier']=='local_time'
