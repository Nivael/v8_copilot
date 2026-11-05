from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import sqlite3

import pytest

from canonical_json import digest
import node_market_audit as module
from node_market_audit import audit_status, collect_inputs, materialize, parent_issues, project, reviewed_dates, ro

NOW = datetime(2026,11,5,4,tzinfo=timezone.utc)


@pytest.fixture
def inputs():
    calendar=[]; current=date(2021,1,1)
    while current<=date(2026,3,1):
        if current.weekday()<5: calendar.append(current.isoformat())
        current+=timedelta(days=1)
    events=[]; parents=[]
    for n,(symbol,day) in enumerate([('000001','2022-05-25'),('000001','2022-12-20'),('000002','2023-06-01'),('000002','2025-12-30')],1):
        events.append({'event_id':f'E{n}','symbol':symbol,'event_type':'pre_restructuring_started','event_date':day,
                       'information_available_date':day,'source_kind':'p6a_verified_fact','source_ref':f'cninfo:D{n}','evidence_status':'verified_official_source'})
        parents.append({'event_id':f'P{n}','symbol':symbol,'event_type':'pre_restructuring_started','event_date':day,'information_available_date':day,
                        'source_document_id':f'cninfo:D{n}','document_id':f'cninfo:D{n}','document_symbol':symbol,'published_date':day,
                        'json_document_id':f'cninfo:D{n}','json_symbol':symbol,'json_published_date':day,'source_kind':'official_issuer_announcement',
                        'source_url':f'https://static.cninfo.com.cn/finalpage/{day}/D{n}.PDF','body_sha256':'a'*64,'quote_length':12})
    events.append({**events[0],'event_id':'T1','symbol':'000003','source_kind':'official_title_exact','source_ref':'cninfo:T1'})
    keys=[[symbol,day] for symbol in ('000001','000002') for day in calendar]
    return {'p6_run':{'run_id':'P6-new','as_of':'2026-07-20','verified_event_count':7},'event_table_rows':6,'events':events,'parents':parents,
            'p8_run':{'run_id':'P8-new','through':'2026-09-03','content_digest':'b'*64},
            'derived_events':[{'record_id':'C1','symbol':'000001','available_as_of':'2022-05-25','evidence_status':'deterministic_verified','node':'pre_restructuring_started','source_ids':['E1']},
                              {'record_id':'C2','symbol':'000003','available_as_of':'2022-05-25','evidence_status':'deterministic_verified','node':'pre_restructuring_started','source_ids':['T1']},
                              {'record_id':'C3','symbol':'000004','available_as_of':'2022-05-25','evidence_status':'deterministic_verified','node':'pre_restructuring_started','source_ids':['obsolete']}],
            'calendar':calendar,'membership':[[day,symbol] for day in calendar for symbol in ('000001','000002','000003')],
            'membership_through':calendar[-1],'price_sources':{name:{'through':calendar[-1],'keys':deepcopy(keys)} for name in module.PLAN['price_source_priority']},
            'date_reviews':[],'node_map':{'pre_restructuring_started':'pre_restructuring_started'}}


def test_titles_unbound_rows_and_repeated_run_labels_do_not_become_main_samples(inputs):
    data=project(inputs)
    assert data['active_run_linked_events']==5 and data['event_table_rows']==6 and data['unbound_table_rows']==1
    assert data['source_kind_counts']=={'p6a_verified_fact':4,'official_title_exact':1}
    assert data['deterministic_lineage_counts']=={'active_prior_fact':1,'active_title':1,'not_bound_to_active_run':1}
    assert data['main_window_nominations']==4 and len(data['candidate_rows'])==4
    assert data['test_capacity_events']==2 and data['test_capacity_companies']==1
    assert data['historical_capacity_pass'] is False
    assert data['outcomes_read'] is data['price_values_read'] is data['model_fitted'] is data['effect_measured'] is False


def test_training_purges_labels_that_would_reach_the_test_year(inputs):
    data=project(inputs);fold=data['folds'][0]
    assert fold['test_year']==2023 and fold['train_events']==1  # December 2022 exits in 2023.
    assert data['candidate_rows'][0]['entry_date']>'2022-05-25'


@pytest.mark.parametrize('source', ['membership', 'overlay', 'base'])
def test_future_source_cutoffs_cannot_enter_an_earlier_audit(inputs,source):
    if source=='membership': inputs['membership_through']='2026-11-06'
    else:
        name=module.PLAN['price_source_priority'][0 if source=='overlay' else 1]
        inputs['price_sources'][name]['through']='2026-11-06'
    with pytest.raises(ValueError,match='newer than audit'):
        module.validate_observation(inputs,NOW)


def test_sources_cannot_be_spliced_to_manufacture_a_complete_adjusted_price_path(inputs):
    original=project(inputs)['candidate_rows'][0]; path=[day for day in inputs['calendar'] if original['entry_date']<=day<=original['outcome_key_end']]
    keys={(original['symbol'],day) for day in path}
    for index,name in enumerate(module.PLAN['price_source_priority']):
        inputs['price_sources'][name]['keys']=[row for row in inputs['price_sources'][name]['keys'] if tuple(row) not in keys or row[1] in path[index::2]]
    row=project(inputs)['candidate_rows'][0]
    assert row['price_key_source'] is None and 'one_source_price_keys_incomplete' in row['issues']


def test_one_complete_source_is_selected_for_the_entire_window(inputs):
    inputs['price_sources'][module.PLAN['price_source_priority'][0]]['keys']=[]
    assert project(inputs)['candidate_rows'][0]['price_key_source']=='base_qfq_complete_window'


@pytest.mark.parametrize('bad', ['missing_parent','third_party','missing_digest','no_quote','wrong_symbol','wrong_event_date','date_hint','available_before_publication'])
def test_existing_verified_label_cannot_override_parent_source_or_date_problems(inputs,bad):
    event=inputs['events'][0];parent=inputs['parents'][0]
    if bad=='missing_parent': inputs['parents'].pop(0)
    elif bad=='third_party': parent['source_url']='https://data.eastmoney.com/notices/D1.html'
    elif bad=='missing_digest': parent['body_sha256']=''
    elif bad=='no_quote': parent['quote_length']=0
    elif bad=='wrong_symbol': parent['document_symbol']='000999'
    elif bad=='wrong_event_date': parent['event_date']='2022-05-24'
    elif bad=='date_hint': parent['source_url']=parent['source_url'].replace('2022-05-25','2022-05-26')
    else: parent['published_date']=parent['json_published_date']='2022-05-26'
    assert parent_issues(event,inputs['parents'])
    assert project(inputs)['candidate_rows'][0]['capacity_candidate'] is False


def date_review(parent, *, symbol=None):
    return {'document_id':parent['document_id'],'symbol':symbol or parent['symbol'],'signed_on':'2022-05-26',
            'source_url':parent['source_url'],'observed_at':'2026-11-05T02:00:00+00:00','availability':'observed'}


def test_reviewed_signature_day_is_conservative_and_preserves_original_event_date(inputs):
    inputs['parents'][0]['source_url']=inputs['parents'][0]['source_url'].replace('2022-05-25','2022-05-26')
    inputs['date_reviews']=[date_review(inputs['parents'][0])]
    row=project(inputs)['candidate_rows'][0]
    assert row['capacity_candidate'] is True
    assert row['original_information_date']=='2022-05-25' and row['information_available_date']=='2022-05-26'
    assert row['feature_through']=='2022-05-26' and row['entry_date']=='2022-05-27'
    assert inputs['events'][0]['event_date']=='2022-05-25'


def test_a_signature_earlier_than_the_archive_hint_does_not_resolve_publication_uncertainty(inputs):
    parent=inputs['parents'][0];parent['source_url']=parent['source_url'].replace('2022-05-25','2022-05-27')
    inputs['date_reviews']=[date_review(parent)]  # Signed May 26, archived May 27.
    row=project(inputs)['candidate_rows'][0]
    assert row['information_available_date']=='2022-05-26'
    assert row['capacity_candidate'] is False and 'publication_date_hint_conflict' in row['issues']


def publication_review(inputs):
    parent=inputs['parents'][0];parent['source_url']=parent['source_url'].replace('2022-05-25','2022-05-26')
    return {'document_id':parent['document_id'],'symbol':parent['symbol'],'source_url':parent['source_url'],
            'official_catalog_date':'2022-05-26','parent_published_dates':['2022-05-25'],'event_ids':['E1'],'availability':'observed','observed_at':'2026-11-05T02:00:00+00:00'}


def test_catalog_date_basis_is_explicitly_versioned_without_tuning_other_study_choices():
    old=json.loads(module.PLAN_PATH.with_name('node_market_study_v1.json').read_text())
    assert old['version']=='node_market_study_v1' and module.PLAN['version']=='node_market_study_v2'
    assert {k:v for k,v in old.items() if k not in ('version','information_date_review')}=={k:v for k,v in module.PLAN.items() if k not in ('version','information_date_review')}


def test_official_catalog_day_corrects_only_information_alignment_and_keeps_original_events_and_source_pool(inputs):
    review=publication_review(inputs)
    inputs['publication_metadata']={'availability':'observed','reviews':[review],'captured_at':'2026-11-05T02:01:00+00:00'}
    result=project(inputs);row=result['candidate_rows'][0]
    assert row['capacity_candidate'] is True and row['original_information_date']=='2022-05-25'
    assert row['official_catalog_date']==row['information_available_date']==row['feature_through']=='2022-05-26'
    assert row['entry_date']=='2022-05-27' and inputs['events'][0]['event_date']=='2022-05-25'
    assert result['source_kind_counts']['official_title_exact']==1 and result['main_window_nominations']==4
    assert (result['source_pool_ceiling_events'],result['source_pool_ceiling_companies'])==(4,2)
    assert result['source_pool_can_reach_test_minimum'] is False and result['outcomes_read'] is result['price_values_read'] is result['model_fitted'] is False


@pytest.mark.parametrize('bad',['wrong_company','wrong_document','wrong_path','foreign_host','wrong_event','old_field_changed','unavailable'])
def test_catalog_cannot_override_the_current_parent_or_use_unverified_metadata(inputs,bad):
    review=publication_review(inputs);meta={'availability':'observed','reviews':[review]}
    if bad=='wrong_company':review['symbol']='999999'
    elif bad=='wrong_document':review['document_id']='cninfo:other'
    elif bad=='wrong_path':review['source_url']=review['source_url'].replace('D1.PDF','D2.PDF')
    elif bad=='foreign_host':review['source_url']=review['source_url'].replace('static.cninfo.com.cn','example.com')
    elif bad=='wrong_event':review['event_ids']=['E2']
    elif bad=='old_field_changed':review['parent_published_dates']=['2022-05-24']
    elif bad=='unavailable':meta['availability']='invalid'
    inputs['publication_metadata']=meta;row=project(inputs)['candidate_rows'][0]
    assert row['information_available_date']=='2022-05-25' and row['official_catalog_date'] is None
    assert row['capacity_candidate'] is False and 'publication_date_hint_conflict' in row['issues']


def test_catalog_dates_and_capture_time_must_be_observed_before_the_audit(inputs):
    inputs['publication_metadata']={'availability':'observed','captured_at':'2026-11-06T00:00:00+00:00','reviews':[]}
    with pytest.raises(ValueError,match='capture after audit'):module.validate_observation(inputs,NOW)


@pytest.mark.parametrize('text,expected',[
    ('二〇二三年七月二十五日','2023-07-25'),('二零二四年十月二十二日','2024-10-22'),
    ('二○二五年十一月十日','2025-11-10'),('二〇二四年十二月三十一日','2024-12-31'),
    ('二〇二四年二月二十九日','2024-02-29'),('2024年02月09日','2024-02-09'),
    ('2024年2月29日','2024-02-29'),('二〇〇一年一月一日','2001-01-01')])
def test_signature_dates_preserve_arabic_and_chinese_calendar_meaning(text,expected):
    assert module.signature_day(text)==expected


@pytest.mark.parametrize('text',['二〇二三年二月二十九日','二〇二四年十三月一日','二〇二四年十月三十二日',
    '二〇二四年二〇月一日','二〇二四年十一十月一日','二〇二四年十二月〇日','2024年01月日','签署日期待定'])
def test_invalid_or_ambiguous_signature_dates_are_not_guessed(text):
    with pytest.raises(ValueError): module.signature_day(text)


@pytest.mark.parametrize('bad', ['wrong_company','wrong_url','unavailable'])
def test_unmatched_or_unavailable_document_review_does_not_move_an_event_date(inputs,bad):
    parent=inputs['parents'][0];parent['source_url']=parent['source_url'].replace('2022-05-25','2022-05-26')
    review=date_review(parent)
    if bad=='wrong_company': review['symbol']='999999'
    elif bad=='wrong_url': review['source_url']=review['source_url'].replace('D1.PDF','D999.PDF')
    else: review['availability']='unavailable'
    inputs['date_reviews']=[review];row=project(inputs)['candidate_rows'][0]
    assert row['information_available_date']=='2022-05-25' and row['capacity_candidate'] is False


@pytest.mark.parametrize('bad', ['duplicate_id','duplicate_canonical','duplicate_price','bad_calendar'])
def test_duplicate_or_unordered_metadata_cannot_inflate_capacity(inputs,bad):
    if bad=='duplicate_id': inputs['events'].append(deepcopy(inputs['events'][0]))
    elif bad=='duplicate_canonical': inputs['events'].append({**inputs['events'][0],'event_id':'new-id'})
    elif bad=='duplicate_price': inputs['price_sources']['base_qfq_complete_window']['keys'].append(inputs['price_sources']['base_qfq_complete_window']['keys'][0])
    else: inputs['calendar'][1]=inputs['calendar'][0]
    with pytest.raises(ValueError): project(inputs)


def test_frozen_gate_cannot_be_relaxed_by_a_saved_report(inputs,tmp_path,monkeypatch):
    monkeypatch.setattr(module,'collect_inputs',lambda **_:deepcopy(inputs))
    materialize(output=tmp_path,now=NOW)
    path=tmp_path/'current.json';raw=json.loads(path.read_text());raw['report']['historical_capacity_pass']=True;raw['report']['outcomes_read']=True
    raw['content_digest']=digest({key:value for key,value in raw.items() if key!='content_digest'});path.write_text(json.dumps(raw))
    data=audit_status(tmp_path,now=NOW)
    assert data['historical_capacity_pass'] is False and data['outcomes_read'] is False and data['plan']['minimum_test_events']==100


def test_source_change_invalidates_the_old_audit_without_silent_rematerialization(inputs,tmp_path,monkeypatch):
    monkeypatch.setattr(module,'collect_inputs',lambda **_:deepcopy(inputs));materialize(output=tmp_path,now=NOW)
    before=(tmp_path/'current.json').read_bytes();inputs['p8_run']['run_id']='another-run'
    assert audit_status(tmp_path,now=NOW)['availability']=='source_changed'
    assert (tmp_path/'current.json').read_bytes()==before


def test_source_values_are_not_read_by_capacity_connections(tmp_path):
    path=tmp_path/'prices.db'
    with sqlite3.connect(path) as conn: conn.execute('create table daily_prices(symbol text,trade_date text,adjust text,close real)');conn.execute("insert into daily_prices values('000001','2023-01-03','qfq',12345)")
    conn=ro(path)
    try:
        assert conn.execute('select symbol,trade_date from daily_prices').fetchall()
        with pytest.raises(sqlite3.DatabaseError): conn.execute('select close from daily_prices').fetchall()
        with pytest.raises(sqlite3.DatabaseError): conn.execute('select max(close) from daily_prices').fetchall()
        with pytest.raises(sqlite3.DatabaseError): conn.execute('update daily_prices set close=1')
    finally: conn.close()


def test_unobserved_or_future_source_review_cannot_be_backdated(inputs,tmp_path,monkeypatch):
    inputs['date_reviews']=[{'availability':'observed','observed_at':'2026-11-06T00:00:00+00:00'}]
    monkeypatch.setattr(module,'collect_inputs',lambda **_:deepcopy(inputs))
    with pytest.raises(ValueError,match='after audit'): materialize(output=tmp_path,now=NOW)
    assert not (tmp_path/'current.json').exists()


def test_reviewed_document_identity_signature_and_both_byte_hashes_are_bound(tmp_path,monkeypatch):
    raw=b'%PDF-synthetic-reviewed-fixture';pages={'pages':['证券代码：000001','示例公司董事会2022年5月26日']};text=json.dumps(pages,ensure_ascii=False).encode()
    case={'document_id':'D1','symbol':'000001','company':'示例公司','signed_on':'2022-05-26','source_pages':2,'signature_page':2,
          'raw_sha256':hashlib.sha256(raw).hexdigest(),'text_sha256':hashlib.sha256(text).hexdigest()}
    monkeypatch.setattr(module,'DATE_REVIEWS',[case]);(tmp_path/(case['raw_sha256']+'.pdf')).write_bytes(raw);(tmp_path/(case['text_sha256']+'.json')).write_bytes(text)
    assert reviewed_dates(tmp_path)[0]['availability']=='observed'
    (tmp_path/(case['raw_sha256']+'.pdf')).write_bytes(raw+b'changed')
    assert reviewed_dates(tmp_path)[0]['availability']=='unavailable'


@pytest.mark.parametrize('kind',['chinese_board','lawyer_signature','plan_without_board','unsigned_form','different_company','missing_security_code','duplicate_board','wrong_date'])
def test_only_one_identified_issuer_board_signature_can_support_a_review(tmp_path,monkeypatch,kind):
    raw=b'%PDF-synthetic-signature-scope-fixture'
    signature='示例公司董事会二〇二三年七月二十五日'
    code='证券代码：000001'
    if kind=='lawyer_signature': signature='示例公司重整计划执行完毕法律意见书示例律师事务所二〇二三年七月二十五日'
    elif kind=='plan_without_board': signature='示例公司2023年7月25日'
    elif kind=='unsigned_form': signature='示例公司董事会年月日'
    elif kind=='different_company': signature='其他公司董事会二〇二三年七月二十五日'
    elif kind=='missing_security_code': code='某附件'
    elif kind=='duplicate_board': signature=signature+'\n'+signature
    elif kind=='wrong_date': signature=signature.replace('二十五','二十六')
    pages={'pages':[code,signature]};text=json.dumps(pages,ensure_ascii=False).encode()
    case={'document_id':'D1','symbol':'000001','company':'示例公司','signed_on':'2023-07-25','source_pages':2,'signature_page':2,
          'raw_sha256':hashlib.sha256(raw).hexdigest(),'text_sha256':hashlib.sha256(text).hexdigest()}
    monkeypatch.setattr(module,'DATE_REVIEWS',[case]);(tmp_path/(case['raw_sha256']+'.pdf')).write_bytes(raw);(tmp_path/(case['text_sha256']+'.json')).write_bytes(text)
    actual=reviewed_dates(tmp_path)[0]
    assert actual['availability']==('observed' if kind=='chinese_board' else 'unavailable')
    if kind=='chinese_board': assert actual['signature_date_text']=='二〇二三年七月二十五日'


def test_foreign_output_is_preserved(tmp_path):
    path=tmp_path/'current.json';path.write_text('{"version":"another-source"}')
    with pytest.raises(ValueError,match='another source'): materialize(output=tmp_path,now=NOW)
    assert path.read_text()=='{"version":"another-source"}'


@pytest.mark.parametrize('field,value',[('processor_digest','0'*64),('plan_digest','1'*64),('observed_at','2026-11-06T00:00:00+00:00'),('observed_at','2026-11-05T04:00:00')])
def test_rehashed_snapshot_cannot_change_the_plan_processor_or_observation(inputs,tmp_path,monkeypatch,field,value):
    monkeypatch.setattr(module,'collect_inputs',lambda **_:deepcopy(inputs));materialize(output=tmp_path,now=NOW)
    path=tmp_path/'current.json';raw=json.loads(path.read_text());raw[field]=value
    raw['content_digest']=digest({key:value for key,value in raw.items() if key!='content_digest'});path.write_text(json.dumps(raw))
    assert audit_status(tmp_path,now=NOW)['availability']=='invalid'


def test_mid_audit_source_change_preserves_the_last_snapshot(inputs,tmp_path,monkeypatch):
    monkeypatch.setattr(module,'collect_inputs',lambda **_:deepcopy(inputs));materialize(output=tmp_path,now=NOW)
    before=(tmp_path/'current.json').read_bytes();changed=deepcopy(inputs);changed['p8_run']['run_id']='new-run'
    sequence=iter([deepcopy(inputs),changed]);monkeypatch.setattr(module,'collect_inputs',lambda **_:next(sequence))
    with pytest.raises(ValueError,match='changed during audit'): materialize(output=tmp_path,now=NOW)
    assert (tmp_path/'current.json').read_bytes()==before


def test_real_sql_collector_selects_one_run_and_reads_price_keys_only(inputs,tmp_path,monkeypatch):
    monkeypatch.setattr(module,'DATE_REVIEWS',[])
    paths={name:tmp_path/(name+'.db') for name in ('episodes','facts','research','market','base','overlay')}
    event=inputs['events'][0];inactive={**event,'event_id':'inactive','symbol':'999999'};parent=inputs['parents'][0]
    with sqlite3.connect(paths['episodes']) as conn:
        conn.executescript('create table valuation_episode_runs(run_id text,as_of text,payload_json text);create table valuation_episode_events(event_id text,symbol text,information_available_date text,payload_json text);create table valuation_episode_run_events(run_id text,event_id text);')
        for name in ('old','new'):
            value={'run_id':name,'as_of':'2026-07-20','verified_event_count':1};conn.execute('insert into valuation_episode_runs values(?,?,?)',(name,value['as_of'],json.dumps(value)))
        for value in (inactive,event):conn.execute('insert into valuation_episode_events values(?,?,?,?)',(value['event_id'],value['symbol'],value['information_available_date'],json.dumps(value)))
        conn.executemany('insert into valuation_episode_run_events values(?,?)',[('old','inactive'),('new',event['event_id'])])
    with sqlite3.connect(paths['facts']) as conn:
        conn.executescript('create table restructuring_cases(case_id text,symbol text);create table restructuring_events(event_id text,case_id text,event_type text,event_date text,information_available_date text,source_document_id text);create table source_documents(document_id text,symbol text,published_date text,payload_json text);')
        conn.execute('insert into restructuring_cases values(?,?)',('case',event['symbol']))
        conn.execute('insert into restructuring_events values(?,?,?,?,?,?)',('parent','case',event['event_type'],event['event_date'],event['information_available_date'],event['source_ref']))
        doc={**parent,'symbol':event['symbol'],'evidence_quote':'local synthetic proof'}
        conn.execute('insert into source_documents values(?,?,?,?)',(doc['document_id'],doc['symbol'],doc['published_date'],json.dumps(doc)))
    with sqlite3.connect(paths['research']) as conn:
        conn.executescript('create table p8_runs(run_id text,through text,content_digest text,run_kind text,created_at text);create table p8_records(run_id text,record_type text,record_id text,symbol text,available_as_of text,evidence_status text,content_digest text,payload_json text);')
        for name,when in [('old','2026-07-01'),('new','2026-07-02')]:
            conn.execute('insert into p8_runs values(?,?,?,?,?)',(name,'2026-09-03','b'*64,'event_graph',when))
            row={**inputs['derived_events'][0],'source_ids':[event['event_id']] if name=='new' else ['inactive']}
            conn.execute('insert into p8_records values(?,?,?,?,?,?,?,?)',(name,'derived_event',name,row['symbol'],row['available_as_of'],row['evidence_status'],'c'*64,json.dumps(row)))
    with sqlite3.connect(paths['market']) as conn:
        conn.executescript('create table benchmark_daily(benchmark_id text,trade_date text,close real);create table st_membership_daily(trade_date text,symbol text);')
        conn.executemany('insert into benchmark_daily values(?,?,?)',[('csi_all_share',day,987654) for day in inputs['calendar']])
        conn.executemany('insert into st_membership_daily values(?,?)',[(day,event['symbol']) for day in inputs['calendar']])
    for name in ('base','overlay'):
        with sqlite3.connect(paths[name]) as conn:
            conn.execute('create table daily_prices(symbol text,trade_date text,adjust text,close real)')
            conn.executemany('insert into daily_prices values(?,?,?,?)',[(event['symbol'],day,'qfq',None) for day in inputs['calendar']])
    data=collect_inputs(**paths,date_sources=tmp_path/'absent')
    assert data['event_table_rows']==2 and [row['event_id'] for row in data['events']]==[event['event_id']]
    assert data['p6_run']['run_id']==data['p8_run']['run_id']=='new'
    assert len(data['derived_events'])==1
    report=project(data)
    # Null price values are deliberately unread: this is a key-capacity audit.
    assert report['candidate_rows'][0]['capacity_candidate'] is True and report['price_values_read'] is False
