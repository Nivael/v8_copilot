from copy import deepcopy
import pytest
from canonical_json import digest
from research_history_events import build_timeline, project_timeline


def fixture():
    dates=['2026-06-01','2026-06-02','2026-06-03','2026-06-04','2026-06-05','2026-06-08','2026-06-09']
    points=[{'date':day,'value':100-i,'level':100-i} for i,day in enumerate(dates)]
    paths={'calendar':dates,'stocks':{'002514.SZ':{'points':deepcopy(points)}},'market':deepcopy(points),'st':deepcopy(points)}
    event={'id':'auction','published_on':'2026-06-06','publication_precision':'day','occurred_on':'2026-06-05','entity_scope':'shareholder','source_id':'1225000001','fact':'竞拍成交，未过户','state_before':'scheduled','state_after':'bid_won','change_kind':'progress'}
    note={'title':'竞拍成交，交割待完成','change':'出现买方','interpretation':'不等于控制权变更','watch':'查付款与过户','lens_ids':['RL-C-002'],'page':2,'highlight':True}
    source={'url':'https://static.cninfo.com.cn/finalpage/2026-06-06/1225000001.PDF','announcement_id':'1225000001','published_on':'2026-06-06','sha256':'a'*64,'pages':3,'title':'竞拍进展'}
    args=dict(question_id='q',question_digest='question-hash',asked_on='2026-06-06',symbol='002514.SZ',review_window_digest='window-hash',experience_id='EXP-'+'A'*20,paths=paths,source_run_id='run',source_pack_id='pack',events=[event],annotations={'auction':note},sources={'auction':source},initial_event_id='auction')
    review={'question_digest':'question-hash','focused_symbol':'002514.SZ','price_window_digest':'window-hash','learning_trace':{'source_run_id':'run','source_pack_id':'pack','experience_candidate_id':args['experience_id']}}
    return args,review


def test_weekend_disclosure_keeps_actual_day_and_does_not_invent_completed_window():
    args,review=fixture();original=deepcopy(args);value=build_timeline(**args)
    assert args==original
    event=value['events'][0]
    assert event['published_on']=='2026-06-06' and event['occurred_on']=='2026-06-05'
    assert event['relation']=='same_day' and event['context']['reference_close']=='2026-06-05'
    assert event['context']['windows']['1']['through']=='2026-06-08'
    assert event['context']['windows']['5']['change_pct']['stock'] is None
    assert event['context']['windows']['5']['through'] is None
    assert project_timeline(value,record={'id':'q','asked_on':'2026-06-06','time_precision':'day'},review=review,paths=args['paths'],symbol='002514.SZ')==value


@pytest.mark.parametrize('day,relation',[('2026-06-05','after_question'),('2026-06-06','same_day'),('2026-06-07','before_question')])
def test_knowledge_relation_uses_disclosure_day_not_occurrence(day,relation):
    args,_=fixture();args['asked_on']=day
    assert build_timeline(**args)['events'][0]['relation']==relation


@pytest.mark.parametrize('mutation',[
    lambda a:a['sources']['auction'].update(announcement_id='1225000002'),
    lambda a:a['sources']['auction'].update(published_on='2026-06-05'),
    lambda a:a['sources']['auction'].update(sha256='wrong'),
    lambda a:a['sources']['auction'].update(url='javascript:alert(1)'),
    lambda a:a['annotations']['auction'].update(page=4),
    lambda a:a['annotations']['auction'].update(page=True),
    lambda a:a['annotations']['auction'].update(lens_ids=['invented-lens']),
    lambda a:a['annotations']['auction'].update(interpretation=''),
    lambda a:a.update(initial_event_id='foreign'),
    lambda a:a['annotations'].update(unrelated=deepcopy(a['annotations']['auction'])),
    lambda a:a['events'][0].update(occurred_on='2026-06-09'),
])
def test_rejects_unbound_sources_and_unreviewed_annotations(mutation):
    args,_=fixture();mutation(args)
    with pytest.raises(ValueError):build_timeline(**args)


@pytest.mark.parametrize('field,value',[('question_id','other'),('question_digest','other'),('symbol','603272.SH'),('review_window_digest','other'),('price_data_digest','other'),('source_run_id','other'),('source_pack_id','other'),('experience_id','EXP-'+'B'*20),('causal_effect_identified',True)])
def test_even_resealed_foreign_or_stale_payload_is_not_projected(field,value):
    args,review=fixture();timeline=build_timeline(**args);timeline[field]=value
    timeline['content_digest']=digest({k:v for k,v in timeline.items() if k!='content_digest'})
    assert project_timeline(timeline,record={'id':'q','asked_on':'2026-06-06','time_precision':'day'},review=review,paths=args['paths'],symbol='002514.SZ') is None


def test_rejects_bad_price_context_and_canonical_price_revision():
    args,review=fixture();value=build_timeline(**args)
    wrong=deepcopy(value);wrong['events'][0]['context']['windows']['1']['change_pct']['stock']='0'
    wrong['content_digest']=digest({k:v for k,v in wrong.items() if k!='content_digest'})
    assert project_timeline(wrong,record={'id':'q','asked_on':'2026-06-06','time_precision':'day'},review=review,paths=args['paths'],symbol='002514.SZ') is None
    revised=deepcopy(args['paths']);revised['stocks']['002514.SZ']['points'][-1]['level']=50
    assert project_timeline(value,record={'id':'q','asked_on':'2026-06-06','time_precision':'day'},review=review,paths=revised,symbol='002514.SZ') is None


def test_missing_stock_reference_stays_missing_while_common_benchmarks_remain():
    args,_=fixture();args['paths']['stocks']['002514.SZ']['points'][4]['level']=None
    value=build_timeline(**args)['events'][0]['context']['windows']['1']['change_pct']
    assert value['stock'] is None and value['market'] is not None and value['st'] is not None


def test_scheduled_future_meeting_is_not_an_actual_occurrence():
    args,_=fixture();args['events'][0].update(state_after='scheduled',occurred_on='2026-06-09')
    value=build_timeline(**args)['events'][0]
    assert value['occurred_on'] is None and value['scheduled_for']=='2026-06-09'


def test_financial_period_end_is_not_a_point_event_and_exact_fields_remain_separate():
    args,_=fixture();args['annotations']['auction']['date_role']='report_period_end'
    value=build_timeline(**args)['events'][0]
    assert value['occurred_on'] is None and value['report_period_end']=='2026-06-05'
    assert value['change']==args['annotations']['auction']['change']
    assert value['evidence_detail']==args['events'][0]['fact']
