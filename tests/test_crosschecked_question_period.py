from copy import deepcopy
from urllib.parse import urlencode
import pytest
from research_history_question_period import question_period_paths,CROSSCHECK_VERSION
from test_history_question_period import prices,setup
from test_argument_event_timelines import seal
from research_history import assemble,question_digest
from research_history_reviews import freeze_question_followthrough
from research_history_events import freeze_argument_timelines,project_argument_timeline


def checked():
    p=prices();p['version']=CROSSCHECK_VERSION
    start,end=p['paths']['calendar'][0],p['paths']['calendar'][-1]
    code='sz002514';urls={
        'tencent_unadjusted':'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?'+urlencode({'param':f'{code},day,{start},{end},640,'}),
        'sina_unadjusted':'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?'+urlencode({'symbol':code,'scale':'240','ma':'no','datalen':'1023'})}
    for key,fqt in [('eastmoney_qfq','1'),('eastmoney_unadjusted','0')]:
        urls[key]='https://push2his.eastmoney.com/api/qt/stock/kline/get?'+urlencode({'secid':'0.002514','klt':'101','fqt':fqt,'beg':start.replace('-',''),'end':end.replace('-',''),'fields1':'f1,f2,f3,f4,f5,f6','fields2':'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61'})
    p['crosscheck_closes']={}
    for key,url in urls.items():
        p['source_refs'].append({'key':key,'url':url,'sha256':'a'*64,'observed_at':'2026-11-07T00:00:00+00:00','title':key})
        p['crosscheck_closes'][key]={'source_sha256':'a'*64,'values':deepcopy(p['qfq_closes'])}
    return seal(p)


def verified_gap(p):
    p['gap_notes'][0]={'date':'2021-05-18','reason':'公告安排停牌一天，保留空档。','support_kind':'verified_suspension',
        'symbol':'002514.SZ','announcement_id':'1220000001','published_on':'2021-05-18','resume_on':'2021-05-19',
        'source_sha256':'a'*64,'url':'https://static.cninfo.com.cn/finalpage/2021-05-18/1220000001.PDF#page=1',
        'excerpt':'证券代码002514，2021年5月18日停牌一天，2021年5月19日复牌。'}
    return seal(p)


def test_unknown_and_verified_gaps_remain_missing_without_changing_legacy_prices():
    p=checked();before=deepcopy(p['paths']);assert question_period_paths(p,symbol='002514.SZ',asked_on='2021-05-17')==before
    verified_gap(p);assert question_period_paths(p,symbol='002514.SZ',asked_on='2021-05-17')==before
    assert p['paths']['stocks']['002514.SZ']['points'][2]['value'] is None
    legacy=prices();assert question_period_paths(legacy,symbol='002514.SZ',asked_on='2021-05-17')==legacy['paths']


def test_raw_sources_may_match_each_other_without_equalling_adjusted_prices():
    p=checked()
    for key in ['tencent_unadjusted','eastmoney_unadjusted','sina_unadjusted']:
        p['crosscheck_closes'][key]['values']={d:v*2 for d,v in p['qfq_closes'].items()}
    assert question_period_paths(seal(p),symbol='002514.SZ',asked_on='2021-05-17')==p['paths']


@pytest.mark.parametrize('change',[
    lambda p:p['crosscheck_closes']['sina_unadjusted']['values'].update({'2021-05-17':999}),
    lambda p:p['crosscheck_closes']['eastmoney_qfq']['values'].update({'2021-05-17':999}),
    lambda p:p['crosscheck_closes']['sina_unadjusted']['values'].pop('2021-05-17'),
    lambda p:p['crosscheck_closes']['sina_unadjusted']['values'].update({'2021-05-18':100}),
    lambda p:p['crosscheck_closes']['eastmoney_unadjusted'].update(source_sha256='b'*64),
    lambda p:p['crosscheck_closes'].pop('sina_unadjusted'),
    lambda p:p['source_refs'][-1].update(url='https://example.com/not-the-requested-stock'),
])
def test_resealed_crosscheck_conflicts_and_source_scope_changes_are_rejected(change):
    p=checked();change(p)
    with pytest.raises((ValueError,KeyError,TypeError)):question_period_paths(seal(p),symbol='002514.SZ',asked_on='2021-05-17')


@pytest.mark.parametrize('field,value',[
    ('symbol','002124.SZ'),('announcement_id','1220000002'),('source_sha256','bad'),
    ('published_on','2021-05-19'),('resume_on','2021-05-18'),('excerpt','证券002514停牌，没有核到日期'),
    ('url','https://example.com/mirror.pdf'),('support_kind','assumed_suspension')])
def test_verified_suspension_cannot_borrow_another_stock_date_or_unchecked_passage(field,value):
    p=verified_gap(checked());p['gap_notes'][0][field]=value
    with pytest.raises((ValueError,KeyError,TypeError)):question_period_paths(seal(p),symbol='002514.SZ',asked_on='2021-05-17')


def followthrough():
    _,a=setup();a['record']['answers']=[]
    r=freeze_question_followthrough({'question_digest':question_digest(a['record']),'then_quote':'','headline':'后来补做，原答留空'},a['record'])
    a['question_periods']={'002514.SZ':checked()}
    return r,a


def test_unanswered_original_gets_a_full_period_without_a_fabricated_answer_or_changed_global_chart():
    r,a=followthrough();before=deepcopy(a['paths']);f=freeze_argument_timelines(r,**a)
    q=assemble([a['record']],a['paths'],reviews={a['record']['id']:f})['details']['002514.SZ']['questions'][0]
    assert q['answers']==[] and q['review']['then_quote']=='' and q['review_status']=='question_followthrough'
    assert q['anchor_date']=='2021-05-17' and q['review']['event_timeline']['version']=='history_event_timeline_v6'
    assert q['question_chart_sources']['stock'][2]['value'] is None and a['paths']==before


@pytest.mark.parametrize('kind',['answer','source','period','version','interpretation'])
def test_recovered_answer_or_changed_full_period_is_hidden_even_after_resealing(kind):
    r,a=followthrough();f=freeze_argument_timelines(r,**a);v=deepcopy(f['event_timelines']['002514.SZ'])
    if kind=='answer':a['record']['answers']=[{'text':'真正恢复的原答'}]
    if kind=='source':v['question_period']['source_refs'][0]['sha256']='b'*64;seal(v['question_period'])
    if kind=='period':v['question_period']['summary']='changed';seal(v['question_period'])
    if kind=='version':v['version']='history_event_timeline_v4'
    if kind=='interpretation':v['events'][0]['interpretation']='已完成'
    seal(v)
    assert project_argument_timeline(v,record=a['record'],review=f,paths=a['paths'],symbol='002514.SZ') is None


def price_assessed():
    import json
    from test_research_history_events import fixture
    from research_history_events import build_timeline
    a,r=fixture();text=json.dumps(checked())
    old=['2021-05-14','2021-05-17','2021-05-18','2021-05-19','2021-05-20','2021-05-21','2021-05-24']
    new=['2026-05-29','2026-06-01','2026-06-02','2026-06-03','2026-06-04','2026-06-05','2026-06-08']
    for before,after in zip(old,new):text=text.replace(before,after).replace(before.replace('-',''),after.replace('-',''))
    a['question_period']=seal(json.loads(text));v=build_timeline(**a)
    r['learning_trace'].update(question_period_digest=v['question_period_digest'],
        question_period_reading_digest=v['reading_digest'],question_period_events_digest=v['source_events_digest'])
    return a,r,v,{'id':'q','asked_on':'2026-06-06','time_precision':'day'}


def test_price_assessed_review_retains_its_original_window_while_early_event_uses_independent_prices():
    from research_history_events import project_timeline
    a,r,v,record=price_assessed();before=deepcopy(a['paths'])
    assert v['version']=='history_event_timeline_v7' and v['review_window_digest']=='window-hash'
    assert v['events'][0]['context']['reference_close']=='2026-06-05'
    assert float(v['events'][0]['context']['windows']['1']['change_pct']['stock'])==pytest.approx((106/105-1)*100)
    assert project_timeline(v,record=record,review=r,paths=a['paths'],symbol='002514.SZ')==v
    assert a['paths']==before and r['price_window_digest']=='window-hash'


@pytest.mark.parametrize('kind',['period','reading','source_events','window','global_prices','foreign_scope','downgrade'])
def test_price_review_rejects_resealed_independent_period_or_binding_changes(kind):
    from research_history_events import project_timeline
    a,r,v,record=price_assessed()
    if kind=='period':v['question_period']['summary']='different';seal(v['question_period']);v['question_period_digest']=v['question_period']['content_digest']
    if kind=='reading':v['events'][0]['interpretation']='unsupported change'
    if kind=='source_events':v['source_events_digest']='b'*64
    if kind=='window':v['review_window_digest']='new-window'
    if kind=='global_prices':a['paths']['market'][-1]['level']=12
    if kind=='foreign_scope':v['symbol']='002124.SZ'
    if kind=='downgrade':v['version']='history_event_timeline_v1'
    assert project_timeline(seal(v),record=record,review=r,paths=a['paths'],symbol='002514.SZ') is None
