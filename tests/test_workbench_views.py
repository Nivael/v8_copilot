from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from threading import Event

import pytest

from canonical_json import digest
from data_refresh import atomic_write_json
from experience_contract import ExperienceCandidateInput
from research_repository import ExperienceRepository, ResearchRunCreate, ResearchRunLedger
import workbench_views as w


def market():
    dates = ['2026-11-02', '2026-11-03', '2026-11-04']
    return {'status': 'observed_snapshot', 'requested_through': dates[-1],
            'recent_window': {'availability': 'defined', 'start': dates[0], 'end': dates[-1], 'sessions': 2, 'calendar': dates},
            'indices': [{'code': '000985.CSI', 'through': dates[-1], 'return_20d_pct': -8, 'return_5d_pct': -1,
                         'source_url': 'https://www.csindex.com.cn/', 'path': [{'date': d, 'close': v} for d, v in zip(dates, [100, 90, 93])]}],
            'st_reconstruction': {'availability': 'reconstructed', 'points': [{'date': d, 'all': {'close': v}} for d, v in zip(dates, [100, 85, 86])]},
            'etfs': [{'code': code, 'group': '沪深300', 'windows': {'recent': {'window_start': dates[0], 'window_end': dates[-1],
                       'share_change_pct': i + 1, 'estimated_net_subscription_yuan': None, 'flow_estimate_ready': False}}} for i, code in enumerate(w.ETF_NAMES)],
            'parameter_version': 'test', 'snapshot_digest': 'f' * 64}


def packet():
    value = market()
    return {'market': w.market_view(value), 'watch_bases': [{'availability': 'available', 'symbol': '603398.SH', 'name': '*ST沐邦',
            'as_of': '2026-11-04', 'prices': [{'date': d, 'close': c, 'previous_close': prev, 'is_trading': True}
                                           for d, c, prev in [('2026-11-02', 10, 10), ('2026-11-03', 4, 5), ('2026-11-04', 3.5, 4)]]}]}


def test_conclusion_first_projection_keeps_st_and_does_not_invent_cash():
    result = w.market_view(market())
    assert result['headline'] == '大盘风险仍偏高，反弹尚未改变近月弱势'
    assert [line['key'] for line in result['chart']] == ['market', 'st']
    assert result['metrics']['period_change_pct'] == pytest.approx(-7)
    assert result['metrics']['st_change_pct'] == pytest.approx(-14)
    assert result['etf']['cash_estimate_yuan'] is None
    assert result['etf']['increasing'] == 8
    assert result['etf']['funds'][0]['name'] == '华泰柏瑞沪深300ETF'


def test_later_st_confirmation_displays_actual_reading_day_in_the_explanation():
    data = market()
    data['st_reconstruction']['daily_close_extension'] = {'membership_confirmation': {
        'observed_on': '2026-11-07', 'note': '2026-11-06收盘名称与2026-11-07实际读取名单一致。'}}
    view = w.market_view(data)
    assert '名单实际读取于2026-11-07' in view['reading_note']
    assert '当日名单' not in view['reading_note']
    assert view['why'][-1]['title'] == 'ST收盘分类已交叉核对'
    assert '2026-11-07' in view['why'][-1]['text']


def test_independent_index_judgment_does_not_change_the_stock_review_basis(tmp_path):
    data = packet()
    args = dict(experience_db=tmp_path/'none', ledger_db=tmp_path/'none')
    before = w.learning_view(data, **args)
    data['market']['latest_price'] = {'availability': 'available', 'as_of': '2026-11-05',
                                    'headline': '新指数判断', 'metrics': {'day_change_pct': -2}}
    after = w.learning_view(data, **args)
    assert after['cases'] == before['cases']
    assert after['market_context']['latest_price']['as_of'] == '2026-11-05'
    assert after['latest_price_as_of'] == before['latest_price_as_of'] == '2026-11-04'


def test_publisher_adds_independent_index_without_relabeling_the_common_basis(tmp_path, monkeypatch):
    import market_price_reading
    latest = {'availability': 'available', 'as_of': '2026-11-05', 'headline': '新指数判断'}
    monkeypatch.setattr(market_price_reading, 'newer_price', lambda base, **kwargs: latest)
    service = w.ReadingViews(tmp_path/'reading', builder=market, price_directory=tmp_path/'prices')
    published = service.publish()['market']
    original = w.market_view(market())
    for key in ('as_of', 'start', 'metrics', 'chart', 'etf', 'why'):
        assert published[key] == original[key]
    assert published['latest_price'] == latest


def test_cash_requires_all_declared_funds_and_strict_ready_flags():
    data = market()
    for fund in data['etfs']:
        fund['windows']['recent'].update(estimated_net_subscription_yuan=0, flow_estimate_ready=True)
    assert w.market_view(data)['etf']['cash_estimate_yuan'] == 0
    data['etfs'][0]['windows']['recent']['flow_estimate_ready'] = 'true'
    assert w.market_view(data)['etf']['cash_estimate_yuan'] is None
    data['etfs'] = data['etfs'][1:]
    assert w.market_view(data)['etf']['cash_estimate_yuan'] is None


def test_incomplete_calendar_rejects_market_but_does_not_splice_st():
    data = market(); data['indices'][0]['path'].pop(1)
    assert w.market_view(data)['availability'] == 'unavailable'
    data = market(); data['st_reconstruction']['points'][1]['date'] = '2026-10-30'
    result = w.market_view(data)
    assert [line['key'] for line in result['chart']] == ['market']
    assert result['metrics']['st_change_pct'] is None


def test_watch_quote_excludes_original_capture_intraday_and_verifies_bytes(tmp_path):
    ref = {'code': '603398', 'params': {'select': 'date,close,prevClose,chg_rate,volume,amount', 'begin': -126, 'end': -1, 'period': 'day'},
           'observed_at': '2026-11-05T05:10:55Z', 'url': 'https://yunhq.sse.com.cn:32042/v1/sh1/dayk/603398'}
    raw = json.dumps({'code': '603398', 'total': 3, 'begin': 0, 'end': 3,
                      'kline': [[20261103, 6.11, 6.1, .16, 10, 10], [20261104, 6.09, 6.11, -.33, 10, 10], [20261105, 6.26, 6.09, 2.79, 10, 10]]}).encode()
    ref.update(sha256=sha256(raw).hexdigest(), bytes=len(raw))
    root = tmp_path / 'sse_history_archive'; capture = root / 'sources/source/full_prices'
    capture.mkdir(parents=True); (capture / (ref['sha256'] + '.raw')).write_bytes(raw)
    atomic_write_json(capture / 'complete.json', {'source_refs': [ref]})
    pointer = {'input_digest': 'source'}; pointer['content_digest'] = digest(pointer)
    atomic_write_json(root / 'current.json', pointer)
    data = {'sse_history_archive': {'availability': 'observed', 'content_digest': pointer['content_digest']}, 'requested_through': '2026-11-04'}
    result = w.watch_basis(data, '603398.SH', root=tmp_path)
    assert result['prices'][-1]['date'] == '2026-11-04' and result['prices'][-1]['close'] == 6.09
    assert all(p['date'] != '2026-11-05' for p in result['prices'])
    (capture / (ref['sha256'] + '.raw')).write_bytes(raw + b' ')
    with pytest.raises(ValueError, match='original changed'):
        w.watch_basis(data, '603398.SH', root=tmp_path)


def record(ledger, answer, question='沐邦目前是什么情况？'):
    return ledger.record(ResearchRunCreate(request_id=answer, question_text=question, normalized_intent='comparison',
                         evidence_pack_ids=['EP-AAAAAAAAAAAAAAAAAAAA'], final_answer=answer,
                         validation_report={'valid': True}, source_freshness={}, agent_surface='test'))


def test_new_codex_record_appears_without_rebuilding_market_and_invalidates_case_review(tmp_path):
    repo = ExperienceRepository(tmp_path / 'experience.db'); ledger = ResearchRunLedger(tmp_path / 'runs.db')
    method = repo.propose(ExperienceCandidateInput(experience_type='query_plan', title='先看事实', value_summary='分清事实与预测',
        trigger_conditions=['比较'], scope=['comparison'], required_inputs=['scope'], answer_rubric=['日期'], anti_patterns=['混淆'],
        coverage_boundaries=['不推断'], validation_refs=['regression:entity_scope_boundary'], source_run_refs=['migration:test']))
    first = record(ledger, '签约不等于受理。')
    args = dict(experience_db=repo.path, ledger_db=ledger.path, reviews_dir=tmp_path / 'reviews')
    data = packet(); result = w.learning_view(data, **args); stock = result['cases'][0]
    # A split reference of 5 on the second day must not become a raw -65% period return.
    assert stock['period_change_pct'] == pytest.approx(-30)
    assert result['methods'][0]['id'] == method.experience_id
    assert result['methods'][0]['category'] == '待分类' and '待分类' in result['categories']
    review = {'version': 'workbench_case_review_v1', 'symbol': '603398.SH', 'basis_digest': stock['basis_digest'],
              'research_run_id': first.run_id, 'reviewed_at': datetime.now(timezone.utc).isoformat(), 'assessment': '保留提醒', 'takeaways': ['看后续']}
    review['content_digest'] = digest(review); atomic_write_json(tmp_path / 'reviews/603398.json', review)
    assert w.learning_view(data, **args)['cases'][0]['review']['assessment'] == '保留提醒'
    second = record(ledger, '新判断。')
    result = w.learning_view(data, **args)['cases'][0]
    assert result['history'][0]['run_id'] == second.run_id and result['research_count'] == 2
    assert result['review'] is None and result['previous_review']['assessment'] == '保留提醒'
    assert result['since_research_change_pct'] is None  # No post-research close exists.


def test_historical_check_does_not_replace_current_case_or_withdraw_its_review(tmp_path):
    from case_research_scopes import mark_historical_review
    ledger = ResearchRunLedger(tmp_path/'runs.db')
    first = record(ledger, '当前公司判断。')
    args = dict(experience_db=tmp_path/'none', ledger_db=ledger.path,
                reviews_dir=tmp_path/'reviews', run_scopes_path=tmp_path/'roles/current.json')
    data = packet(); original = w.learning_view(data, **args)['cases'][0]
    review = {'version':'workbench_case_review_v1','symbol':'603398.SH','basis_digest':original['basis_digest'],
              'research_run_id':first.run_id,'reviewed_at':datetime.now(timezone.utc).isoformat(),
              'assessment':'当前复盘','takeaways':['看公司现状']}
    review['content_digest'] = digest(review); atomic_write_json(tmp_path/'reviews/603398.json', review)
    before = w.learning_view(data, **args)['cases'][0]
    historical = record(ledger, '只核对五月交易规则。', question='复核沐邦五月原问中的规则。')
    assert w.learning_view(data, **args)['cases'][0]['review'] is None
    mark_historical_review(historical.run_id, '历史制度核查，不是今天的公司判断',
                           ledger_db=ledger.path, directory=tmp_path/'roles')
    assert w.learning_view(data, **args)['cases'][0] == before
    latest = record(ledger, '公司新增事实改变判断。')
    case = w.learning_view(data, **args)['cases'][0]
    assert case['history'][0]['run_id'] == latest.run_id and case['research_count'] == 2
    assert case['review'] is None and case['previous_review'] == review


def test_nontrading_day_is_a_gap_not_a_zero_return_and_missing_day_stays_unavailable(tmp_path):
    data = packet(); data['watch_bases'][0]['prices'][1].update(close=None, previous_close=None, is_trading=False)
    result = w.learning_view(data, experience_db=tmp_path/'missing', ledger_db=tmp_path/'none')['cases'][0]
    assert result['period_path'][1]['value'] is None and result['period_path'][1]['level'] is None
    assert result['period_change_pct'] == pytest.approx(-12.5)
    data['watch_bases'][0]['prices'].pop(1)
    result = w.learning_view(data, experience_db=tmp_path/'missing', ledger_db=tmp_path/'none')['cases'][0]
    assert result['period_change_pct'] is None and result['relative_to_st_pp'] is None and result['period_path'] == []


def test_latest_stock_close_does_not_extend_the_older_shared_market_comparison(tmp_path):
    ledger=ResearchRunLedger(tmp_path/'runs.db');record(ledger,'按新材料判断。')
    args=dict(experience_db=tmp_path/'none',ledger_db=ledger.path)
    data=packet()
    latest={'symbol':'603398.SH','name':'最新名称','availability':'available','as_of':'2026-11-05','close':4.2,'previous_close':3.5,
            'day_change_pct':20,'five_day_change_pct':2,'twenty_day_change_pct':-30,'stage':'early_repair','note':{'judgment':'新的观察'}}
    before=w.learning_view(data,**args)['cases'][0]
    result=w.learning_view(data,latest_quotes=[latest],**args);case=result['cases'][0]
    assert result['latest_price_as_of']=='2026-11-05' and case['name']=='最新名称'
    assert case['last_close']==4.2 and case['day_change_pct']==pytest.approx(20)
    assert case['as_of']=='2026-11-04' and case['period_path']==before['period_path']
    assert case['period_change_pct']==before['period_change_pct']
    assert case['basis_digest']!=before['basis_digest']
    assert case['last_research_anchor']['date']=='2026-11-05'
    assert case['since_research_change_pct'] is None
    latest['as_of']='2026-11-03'
    assert w.learning_view(data,latest_quotes=[latest],**args)['cases'][0]['last_close']==3.5


def test_same_day_note_survives_aligned_bases_without_duplicating_the_close(tmp_path):
    data=packet(); basis=data['watch_bases'][0]
    latest={'symbol':basis['symbol'],'name':basis['name'],'availability':'available','as_of':'2026-11-04',
            'close':3.5,'previous_close':4,'day_change_pct':-12.5,'five_day_change_pct':2,
            'twenty_day_change_pct':-30,'stage':'early_repair','note':{'judgment':'同日已核公司判断'}}
    args=dict(experience_db=tmp_path/'none',ledger_db=tmp_path/'none')
    before=w.learning_view(data,**args)['cases'][0]
    result=w.learning_view(data,latest_quotes=[latest],**args)['cases'][0]
    assert result['current_observation']==latest['note'] and result['latest_quote']['as_of']==basis['as_of']
    assert result['period_path']==before['period_path'] and len(result['period_path'])==3
    latest['previous_close']=5
    mismatch=w.learning_view(data,latest_quotes=[latest],**args)['cases'][0]
    assert mismatch.get('current_observation') is None and mismatch['last_close']==3.5


def test_published_read_is_fast_and_single_flight_failure_preserves_previous(tmp_path, monkeypatch):
    gate = Event(); entered = Event(); calls = []
    def builder():
        calls.append(1); entered.set(); assert gate.wait(5); raise ValueError('secret must not leak')
    service = w.ReadingViews(tmp_path, builder=builder, ttl_seconds=0)
    monkeypatch.setattr(w, 'watch_basis', lambda *a: {'symbol': '603398.SH', 'availability': 'unavailable'})
    service.builder = market; saved = service.publish(); service.builder = builder
    service.schedule(force=True); assert entered.wait(2)
    service.schedule(force=True)
    assert service.read() == saved and len(calls) == 1
    gate.set(); service.future.result(timeout=3)
    assert service.read() == saved and service.status()['last_error'] == 'ValueError'
    corrupted = deepcopy(saved); corrupted['market']['headline'] = 'tampered'
    atomic_write_json(tmp_path/'current.json', corrupted)
    assert service.read() is None
    atomic_write_json(tmp_path/'current.json', saved)
    monkeypatch.setattr(w, 'processor_digest', lambda: 'changed')
    assert service.read() is None
    service.schedule(force=True)
    assert service.status()['last_error'] == 'reload_required'
    service.executor.shutdown()
