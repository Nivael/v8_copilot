from copy import deepcopy
from datetime import datetime,timezone
from urllib.parse import urlencode
import pytest
from canonical_json import digest
from research_history_case_period import case_period_paths
from research_history_events import freeze_argument_timelines,project_argument_timeline
from test_argument_event_timelines import fixture,seal

def period():
    days=['2021-05-14','2021-05-17','2021-05-18','2021-05-19','2021-05-20','2021-05-21','2021-05-24']
    def points(start,gap=False):
        return [{'date':d,'value':None if gap and i==2 else start+i,'level':None if gap and i==2 else (start+i)/start*100} for i,d in enumerate(days)]
    paths={'calendar':days,'stocks':{'002514.SZ':{'name':'案例公司','points':points(100,True)}},'market':points(200),'st':points(300),'st_name':'ST板块（东财）'}
    start,end=days[0],days[-1]
    urls={'tencent_qfq':'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?'+urlencode({'param':f'sz002514,day,{start},{end},640,qfq'}),
          'tencent_unadjusted':'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?'+urlencode({'param':f'sz002514,day,{start},{end},640,'}),
          'market':'https://www.csindex.com.cn/csindex-home/perf/index-perf?'+urlencode({'indexCode':'000985','startDate':'20210514','endDate':'20210524'})}
    for key,secid,fqt in [('st','90.BK0511','0'),('eastmoney_qfq','0.002514','1')]:
        urls[key]='https://push2his.eastmoney.com/api/qt/stock/kline/get?'+urlencode({'secid':secid,'klt':'101','fqt':fqt,'beg':'20210514','end':'20210524','fields1':'f1,f2,f3,f4,f5,f6','fields2':'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61'})
    return seal({'version':'history_case_period_sources_v1','price_basis':'unadjusted_price','symbol':'002514.SZ','title':'当年案例走势','summary':'先比较时间顺序','source_note':'供应商交叉核对，不是交易所验证','paths':paths,'source_refs':[{'key':k,'url':v,'title':k,'sha256':'a'*64,'observed_at':datetime.now(timezone.utc).isoformat()} for k,v in urls.items()],'gap_notes':[{'date':days[2],'reason':'公告停牌','announcement_id':'1209994983','url':'https://static.cninfo.com.cn/finalpage/2021-05-18/1209994983.PDF#page=1'}],'unadjusted_closes':{d:100+i for i,d in enumerate(days) if i!=2}})

def setup():
    review,args=fixture()
    event={**args['events'][0],'id':'old','published_on':'2021-05-17'}
    args['events'].insert(0,event)
    args['annotations']['old']=deepcopy(args['annotations']['0'])
    args['sources']['old']={**deepcopy(args['sources']['0']),'published_on':'2021-05-17'}
    args['case_periods']={'002514.SZ':period()}
    return review,args

def test_case_and_question_windows_use_separate_calendars_without_changing_original_anchor():
    review,args=setup();before=deepcopy((review,args));result=freeze_argument_timelines(review,**args)
    assert (review,args)==before
    value=result['event_timelines']['002514.SZ']
    assert value['version']=='history_event_timeline_v3'
    old,current=value['events']
    assert old['relation']=='before_question' and old['context_period']=='case_period'
    assert old['context']['reference_close']=='2021-05-17' and old['context']['windows']['5']['through']=='2021-05-24'
    assert current['context_period']=='question_period' and current['context']['reference_close']=='2026-06-03'
    assert result['event_timelines']['603272.SH']['version']=='history_event_timeline_v2'
    assert project_argument_timeline(value,record=args['record'],review=result,paths=args['paths'],symbol='002514.SZ')==value

@pytest.mark.parametrize('change',[
    lambda p:p.update(price_basis='qfq'),
    lambda p:p['unadjusted_closes'].update({'2021-05-17':999}),
    lambda p:p.update(symbol='600702.SH'),
    lambda p:p['paths']['calendar'].reverse(),
    lambda p:p['paths']['market'][0].update(value=0),
    lambda p:p['paths']['market'][1].update(value=None,level=None),
    lambda p:p['paths']['stocks']['002514.SZ']['points'][3].update(level=999),
    lambda p:p['paths']['stocks']['002514.SZ']['points'][3].update(value=float('nan')),
    lambda p:p['paths']['stocks']['002514.SZ']['points'][3].update(value=-1),
    lambda p:p['gap_notes'].clear(),
    lambda p:p['gap_notes'][0].update(url='https://example.com/other.pdf'),
    lambda p:p['unadjusted_closes'].pop('2021-05-17'),
    lambda p:p['source_refs'][0].update(url='https://example.com/unbound'),
    lambda p:p['source_refs'][0].update(sha256='invalid'),
    lambda p:p['source_refs'][0].update(observed_at='2099-01-01T00:00:00+00:00'),
    lambda p:p['source_refs'].pop(),
])
def test_resealed_bad_or_unbound_case_sources_cannot_be_frozen(change):
    value=period();change(value)
    with pytest.raises((ValueError,KeyError,TypeError)):
        case_period_paths(seal(value),symbol='002514.SZ',asked_on='2026-06-01',current_start='2026-05-29')

@pytest.mark.parametrize('edge',['asked_on','current_start'])
def test_case_window_cannot_reach_the_original_or_current_window(edge):
    kwargs=dict(symbol='002514.SZ',asked_on='2026-06-01',current_start='2026-05-29');kwargs[edge]='2021-05-24'
    with pytest.raises(ValueError):case_period_paths(period(),**kwargs)

def test_missing_historical_stock_quote_stays_missing_and_not_a_zero_return():
    review,args=setup();args['events'][0]['published_on']='2021-05-18';args['sources']['old']['published_on']='2021-05-18'
    value=freeze_argument_timelines(review,**args)['event_timelines']['002514.SZ']['events'][0]
    assert value['context']['reference_close']=='2021-05-18'
    assert value['context']['windows']['1']['change_pct']['stock'] is None
    assert value['context']['windows']['1']['change_pct']['market'] is not None

@pytest.mark.parametrize('change',[
    lambda t:t['case_period'].update(summary='different reading'),
    lambda t:t.update(version='history_event_timeline_v2'),
    lambda t:t['events'][0].update(context_period='question_period'),
    lambda t:t['events'][0]['context'].update(reference_close='2026-06-03'),
])
def test_resealed_case_or_context_changes_hide_only_the_timeline(change):
    review,args=setup();result=freeze_argument_timelines(review,**args);value=deepcopy(result['event_timelines']['002514.SZ']);change(value)
    if 'case_period' in value:seal(value['case_period'])
    assert project_argument_timeline(seal(value),record=args['record'],review=result,paths=args['paths'],symbol='002514.SZ') is None

def test_case_input_for_an_unrelated_company_is_rejected():
    review,args=setup();args['case_periods']['600702.SH']=args['case_periods'].pop('002514.SZ')
    with pytest.raises(ValueError):freeze_argument_timelines(review,**args)
