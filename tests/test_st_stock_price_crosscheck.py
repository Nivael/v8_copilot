from datetime import date
from hashlib import sha256
from copy import deepcopy
import json
import pytest
from canonical_json import digest
from market_calendar import sessions_2026
from st_stock_price_crosscheck import price_scope_digest,price_check_view,SUBJECTS


def fixture():
    cal=sessions_2026(date(2026,5,6),date(2026,11,6));i={'calendar':cal,'through':cal[-1],'fixed_prices':[],'benchmarks':[],'members':[]};companies=[];sources=[]
    for symbol in SUBJECTS:
        rows=[]
        for n,d in enumerate(cal):
            halted=symbol=='002667' and d in ('2026-09-30','2026-10-08','2026-10-09')
            close=round(10+n/100,2)
            rows.append({'date':d,'raw_close':close,'qfq_close':close,'volume':0 if halted else 100,'has_trade':not halted,'adj_factor':1,'suspension_records':[{'suspend_type':'S'}] if halted else []})
        companies.append({'symbol':symbol,'rows':rows,'qfq_normalization_date':cal[-1],'qfq_normalization_factor':1})
        for key in ('tencent_raw','tencent_qfq','eastmoney_qfq'):
            quotes=[[r['date'],'10',str(r['raw_close']),'12','9','100'] for r in rows if r['has_trade']]
            if key.startswith('tencent'):
                raw=json.dumps({'data':{('sh' if symbol.startswith('6') else 'sz')+symbol:{'qt':{('sh' if symbol.startswith('6') else 'sz')+symbol:['1','name',symbol]},'qfqday' if key.endswith('qfq') else 'day':quotes}}})
            else:raw=json.dumps({'data':{'code':symbol,'market':1 if symbol.startswith('6') else 0,'klines':[','.join(r) for r in quotes]}})
            sources.append({'symbol':symbol,'key':key,'raw_text':raw,'sha256':sha256(raw.encode()).hexdigest(),'url':'https://example.com/quotes','observed_at':'2026-11-09T00:00:00Z'})
    p={'price_scope_digest':price_scope_digest(i),'original_prices':{'calendar':cal,'through':cal[-1],'companies':companies},'sources':sources,'failed_requests':[]};p['content_digest']=digest(p);i['stock_price_crosscheck']=p
    daily=[{'date':d,'market_pct':-.1,'return_pct':-.2} for d in cal[1:]]
    return i,daily


def resign(i):
    p=i['stock_price_crosscheck'];p['content_digest']=digest({k:v for k,v in p.items() if k!='content_digest'})


def test_halted_common_anchor_is_not_an_actual_trade_and_alternative_keeps_longer_window():
    i,d=fixture();v=price_check_view(i,d);r=next(r for r in v['rows'] if r['symbol']=='002667');w=r['windows']['20']
    assert w['anchor']=='2026-10-09' and w['stock_pct'] is None and w['market_excess_pp'] is None
    assert w['reference_price_change_pct'] is not None
    assert w['alternative_actual_anchor']['anchor']=='2026-09-29'
    assert w['alternative_actual_anchor']['market_days']==23 and w['alternative_actual_anchor']['actual_trading_days']==20
    assert all(x is None for x in w['checked_returns'].values())


def test_source_and_scope_binding_reject_tampering():
    i,d=fixture();i['stock_price_crosscheck']['sources'][0]['raw_text']+=' ';resign(i)
    with pytest.raises(ValueError,match='original changed'):price_check_view(i,d)
    i,d=fixture();i['fixed_prices'].append({'symbol':'603398','close':10})
    with pytest.raises(ValueError,match='scope changed'):price_check_view(i,d)


def test_duplicate_channel_incomplete_research_set_and_factor_projection_rejected():
    for change in ('duplicate','subject','factor'):
        i,d=fixture();p=i['stock_price_crosscheck']
        if change=='duplicate':p['sources'].append(deepcopy(p['sources'][0]))
        elif change=='subject':p['original_prices']['companies'].pop()
        else:p['original_prices']['companies'][0]['rows'][0]['qfq_close']=99
        resign(i)
        with pytest.raises(ValueError):price_check_view(i,d)


def test_price_conflict_remains_visible_instead_of_replacing_original():
    i,d=fixture();before=deepcopy(i['stock_price_crosscheck']['original_prices']);s=i['stock_price_crosscheck']['sources'][0];x=json.loads(s['raw_text']);next(iter(x['data'].values()))['day'][0][2]='99';s['raw_text']=json.dumps(x);s['sha256']=sha256(s['raw_text'].encode()).hexdigest();resign(i)
    v=price_check_view(i,d);assert not v['all_available_prices_agree'];assert v['rows'][0]['channels'][0]['price_differences'];assert i['stock_price_crosscheck']['original_prices']==before


def test_star_subject_does_not_become_a_main_board_member_or_fabricate_adjustments():
    i,d=fixture();before=deepcopy(i['members']);v=price_check_view(i,d);r=next(r for r in v['rows'] if r['symbol']=='688053')
    assert r['scope']=='longitudinal_star' and i['members']==before
    assert r['factor_change_dates']==[] and r['raw_qfq_differ_days']==0


def test_watch_note_only_applies_to_same_cutoff_and_matching_reference_measure():
    from watch_price_window_notes import attach_price_window_notes
    i,d=fixture();check=price_check_view(i,d)
    ref=next(r for r in check['rows'] if r['symbol']=='002667')['windows']['20']['reference_price_change_pct']
    case={'symbol':'002667.SZ','latest_quote':{'as_of':'2026-11-06','twenty_day_change_pct':ref}}
    regime={'availability':'available','content_digest':'verified-snapshot','themes':{'stock_price_crosscheck':check}}
    result=attach_price_window_notes({'cases':[deepcopy(case)]},regime)
    assert '2026-10-09' in result['cases'][0]['price_window_note']['text'] and '23个市场交易日' in result['cases'][0]['price_window_note']['text']
    missing=deepcopy(case);missing['latest_quote']['twenty_day_change_pct']=None
    assert '近20日未计算' in attach_price_window_notes({'cases':[missing]},regime)['cases'][0]['price_window_note']['text']
    for change in ('date','value'):
        c=deepcopy(case)
        if change=='date':c['latest_quote']['as_of']='2026-11-09'
        else:c['latest_quote']['twenty_day_change_pct']=999
        assert 'price_window_note' not in attach_price_window_notes({'cases':[c]},regime)['cases'][0]


def test_learning_api_keeps_original_quote_and_adds_only_bound_display_note(monkeypatch):
    import api as api_module
    import st_regime_comparison
    i,d=fixture();check=price_check_view(i,d);ref=next(r for r in check['rows'] if r['symbol']=='002667')['windows']['20']['reference_price_change_pct']
    result={'availability':'available','data':{'cases':[{'symbol':'002667.SZ','latest_quote':{'as_of':'2026-11-06','twenty_day_change_pct':ref}}]}}
    monkeypatch.setattr(api_module,'get_reading_view',lambda *a,**kw:deepcopy(result))
    monkeypatch.setattr(st_regime_comparison,'load',lambda:{'availability':'available','content_digest':'source-snapshot','themes':{'stock_price_crosscheck':check}})
    response=api_module.get_learning_reading()
    assert response['data']['cases'][0]['latest_quote']==result['data']['cases'][0]['latest_quote']
    assert response['data']['cases'][0]['price_window_note']['source_snapshot']=='source-snapshot'
    monkeypatch.setattr(api_module,'get_reading_view',lambda *a,**kw:{'availability':'warming'})
    monkeypatch.setattr(st_regime_comparison,'load',lambda:pytest.fail('must not load while warming'))
    assert api_module.get_learning_reading()=={'availability':'warming'}


def halt_fixture():
    i,d=fixture();r=next(c for c in i['stock_price_crosscheck']['original_prices']['companies'] if c['symbol']=='002667');base={r['date']:r for r in r['rows']}
    row={'symbol':'002667','cause_key':'offer_result_confirmation','start':'2026-09-30','resume':'2026-10-12','halt_disclosed_on':'2026-09-30','resume_disclosed_on':'2026-10-12','facts':[{'published_on':'2026-09-30','source':{'title':'停牌原件','url':'https://example.com/halt.pdf','sha256':'a'*64,'page':1}}]}
    return i,d,row,base


def test_three_market_days_are_one_continuous_halt_with_matching_actual_resumption():
    from st_stock_price_crosscheck import halt_explanation
    i,d,row,base=halt_fixture();v=halt_explanation({'halt_explanations':[row]},'002667',i['calendar'],base,i['through'])
    assert v['market_halt_dates']==['2026-09-30','2026-10-08','2026-10-09'] and v['continuous_episode_count']==1
    assert v['previous_actual_close_date']=='2026-09-29' and v['first_actual_resume_date']=='2026-10-12' and v['schedule_matches_quotes']


def test_halt_quote_conflict_is_visible_without_overwriting_either_schedule_or_quotes():
    from st_stock_price_crosscheck import halt_explanation
    i,d,row,base=halt_fixture();base['2026-10-09']['has_trade']=True
    v=halt_explanation({'halt_explanations':[row]},'002667',i['calendar'],base,i['through'])
    assert not v['schedule_matches_quotes'] and v['resume']=='2026-10-12' and v['first_actual_resume_date']=='2026-10-09'


@pytest.mark.parametrize('change',['future','empty','late_disclosure','unknown_cause'])
def test_halt_source_and_timing_gates_reject_unsupported_explanations(change):
    from st_stock_price_crosscheck import halt_explanation
    i,d,row,base=halt_fixture()
    if change=='future':row['facts'][0]['published_on']='2026-11-09'
    elif change=='empty':row['facts']=[]
    elif change=='late_disclosure':row['halt_disclosed_on']='2026-10-12'
    else:row['cause_key']='everything_resolved'
    with pytest.raises(ValueError):halt_explanation({'halt_explanations':[row]},'002667',i['calendar'],base,i['through'])
