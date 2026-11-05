from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
import json
from urllib.parse import unquote

import pytest

from canonical_json import digest
import etf_registration_rules as m

NOW=datetime(2026,11,5,13,tzinfo=timezone.utc)
TEXT={
 'sh_daily':'每日上交所闭市后,通过参与人远程操作平台(PROP)向基金管理人发送当日登记在册的ETF全体场内持有人名册',
 'sh_effective':'本业务指南自2026年5月25日起施行',
 'sz_route':'不通过代办证券公司经纪交易单元,而通过基金管理人直销申报跨市场股票ETF场外组合证券申购赎回申请',
 'sz_daily':'基金管理人可通过D-COM系统接受每日的ETF份额持有明细数据(详见GLRMX.DBF)',
 'sz_exchange':'其余数据文件均由本公司和基金管理人直接交换',
 'sz_effective':'本指南自2026年8月10日起施行',
 'central_permission':'完成相应系统测试,签订相关业务协议,并向本公司申请成为平台参与人',
 'central_backup_scope':'份额登记机构按照有关规定,向平台报送公募基金份额登记数据',
 'central_incremental':'于T+1日21:00前将T日数据报送;每日向平台报送增量备份数据;全量备份数据,原则上不得少于每年两次',
 'central_error':'备份数据格式检查不合格的反馈文件(ERR格式反馈),于T+1日21:00前完成错误修正',
 'central_exclusion':'ETF)等产品的证券交易所场内份额,相关业务开展不适用本指引',
 'central_effective':'本指引自2026年9月11日起施行'}


def test_roles_keep_exchange_registers_routes_incremental_backup_and_distinct_effective_dates_separate():
    result=m.parse_facts(TEXT)
    assert result['effective_dates']=={'sh-guide':'2026-05-25','sz-guide':'2026-08-10','central-exchange':'2026-09-11'}
    assert result['shanghai']['scope']=='全体场内持有人名册' and result['shanghai']['recipient']=='基金管理人'
    assert result['shenzhen']['file_name']=='GLRMX.DBF' and result['shenzhen']['off_exchange_share_class_inferred'] is False
    assert result['shenzhen']['actual_investor_identity_inferred'] is False
    central=result['central'];assert central['daily_backup_kind']=='incremental' and central['full_backup_min_per_year']==2
    assert central['exchange_ETF_share_business_excluded'] is True and central['deadline_is_exchange_ETF_revision_confirmation'] is False


@pytest.mark.parametrize('role,old,new',[
 ('sh_daily','全体场内','全体'),('sh_daily','向基金管理人','向公众'),('sh_daily','闭市后','开市前'),
 ('sz_daily','GLRMX.DBF','PUBLIC_TOTAL.CSV'),('sz_exchange','和基金管理人','和公众'),('sz_route','直销申报','登记场外份额'),
 ('central_permission','签订相关业务协议','无须协议'),('central_backup_scope','份额登记机构','公众用户'),
 ('central_incremental','增量','全量'),('central_incremental','每年两次','每日两次'),('central_incremental','21:00','09:00'),
 ('central_error','格式检查','数量确认'),('central_error','21:00','09:00'),('central_exclusion','不适用','适用'),('central_exclusion','场内份额','所有份额'),
 ('central_effective','起施行','起发布'),('sz_effective','8月10日','8月40日')])
def test_changed_actor_scope_time_or_data_kind_cannot_keep_the_old_explanation(role,old,new):
    blocks=dict(TEXT);blocks[role]=blocks[role].replace(old,new)
    with pytest.raises(ValueError):m.parse_facts(blocks)


@pytest.fixture
def capture(tmp_path,monkeypatch):
    profile=deepcopy(m.PROFILE);folder=tmp_path/'rules';folder.mkdir()
    rows=[]
    for doc in profile['documents']:
        ref=doc['source'];pages=['']*ref['pages'];pages[0]=doc['cover_title']+doc['document_number']
        doc['cover_sha256']=sha256(pages[0].encode()).hexdigest()
        for proof in doc['proofs']:
            role=proof['role'];proof.update(start='开始'+role,end='终止'+role)
            block=proof['start']+TEXT[role]+proof['end'];proof['sha256']=sha256(block.encode()).hexdigest();pages[proof['page']-1]+=block+'。'
        pdf=('%PDF-synthetic-'+ref['label']).encode();body=json.dumps({'pages':pages},ensure_ascii=False).encode()
        ref.update(raw_sha256=sha256(pdf).hexdigest(),text_sha256=sha256(body).hexdigest(),bytes=len(pdf))
        (folder/(ref['raw_sha256']+'.pdf')).write_bytes(pdf);(folder/(ref['text_sha256']+'.json')).write_bytes(body)
        (folder/(ref['label']+'.source.json')).write_text(json.dumps(ref))
        rows.append(f'<li><a class="title" href="{unquote(ref["url"])}">{doc["listed_title"]}</a><span class="date">{doc["published_on"]}</span></li>')
    index=(''.join(rows)).encode();profile['index']['sha256']=sha256(index).hexdigest()
    (folder/'index.html').write_bytes(index);(folder/'index.source.json').write_text(json.dumps(profile['index']))
    monkeypatch.setattr(m,'PROFILE',profile)
    return folder,profile


def test_bound_catalog_dates_originals_and_scoped_clauses_collect_without_promoting_daily_data(capture):
    folder,_=capture;inputs=m.collect(folder,NOW);result=m.project(inputs)
    assert (result['reviewed_versions'],result['reviewed_clauses'],result['source_pages'],result['identity_and_proof_pages'])==(3,12,134,14)
    assert [(d['published_on'],d['effective_on']) for d in result['documents']]==[('2026-05-22','2026-05-25'),('2026-08-07','2026-08-10'),('2026-09-11','2026-09-11')]
    assert all(result[k] is False for k in ('daily_registration_data_acquired','full_document_semantics_checked','full_window_versions_checked',
        'whole_fund_daily_scope_verified','share_precision_verified','final_revision_verified','corporate_actions_checked','historical_PIT','effect_measured'))
    assert result['estimated_net_subscription_yuan'] is None


@pytest.mark.parametrize('bad',['index_bytes','index_metadata','document_bytes','text_bytes','source_metadata','future_observation','naive_observation','index_date','index_link','cover','proof'])
def test_raw_metadata_index_identity_date_and_passage_bindings_are_required(capture,bad):
    folder,profile=capture;doc=profile['documents'][0];ref=doc['source']
    if bad=='index_bytes':(folder/'index.html').write_text('changed')
    elif bad=='index_metadata':(folder/'index.source.json').write_text('{}')
    elif bad=='document_bytes':(folder/(ref['raw_sha256']+'.pdf')).write_bytes(b'changed')
    elif bad=='text_bytes':(folder/(ref['text_sha256']+'.json')).write_text('{}')
    elif bad=='source_metadata':(folder/(ref['label']+'.source.json')).write_text('{}')
    elif bad in ('future_observation','naive_observation'):
        ref['observed_at']='2026-11-06T00:00:00+00:00' if bad=='future_observation' else '2026-11-05T12:30:00'
        (folder/(ref['label']+'.source.json')).write_text(json.dumps(ref))
    elif bad in ('index_date','index_link'):
        index=(folder/'index.html').read_text().replace('2026-05-22','2026-05-25') if bad=='index_date' else (folder/'index.html').read_text().replace('84689a86','wrong')
        profile['index']['sha256']=sha256(index.encode()).hexdigest();(folder/'index.html').write_text(index);(folder/'index.source.json').write_text(json.dumps(profile['index']))
    else:
        pages=json.loads((folder/(ref['text_sha256']+'.json')).read_text())['pages']
        if bad=='cover':pages[0]='另一机构的指南'
        else:pages[16]=pages[16].replace('场内','全部')
        body=json.dumps({'pages':pages},ensure_ascii=False).encode();ref['text_sha256']=sha256(body).hexdigest();(folder/(ref['text_sha256']+'.json')).write_bytes(body)
        (folder/(ref['label']+'.source.json')).write_text(json.dumps(ref))
    with pytest.raises((ValueError,KeyError)):m.collect(folder,NOW)


def test_changed_code_sources_foreign_output_and_injected_report_cannot_replace_or_promote_current(capture,monkeypatch):
    folder,_=capture;inputs=m.collect(folder,NOW);monkeypatch.setattr(m,'collect',lambda *a,**k:deepcopy(inputs));m.materialize(folder,NOW)
    path=folder/'current.json';raw=json.loads(path.read_text());raw['report']={'daily_registration_data_acquired':True,'whole_fund_daily_scope_verified':True,'estimated_net_subscription_yuan':99}
    raw['content_digest']=digest({k:v for k,v in raw.items() if k!='content_digest'});path.write_text(json.dumps(raw));before=path.read_bytes()
    status=m.rules_status(folder,NOW);assert status['reviewed_clauses']==12 and status['daily_registration_data_acquired'] is False and status['estimated_net_subscription_yuan'] is None
    assert path.read_bytes()==before
    changed=deepcopy(inputs);changed['documents'][0]['published_on']='2026-05-25';sequence=iter([inputs,changed]);monkeypatch.setattr(m,'collect',lambda *a,**k:next(sequence))
    with pytest.raises(ValueError,match='sources or processor'):m.materialize(folder,NOW)
    assert path.read_bytes()==before
    monkeypatch.setattr(m,'processor_digest',lambda:'changed');assert m.rules_status(folder,NOW)['availability']=='reload_required'
    with pytest.raises(ValueError,match='reload changed'):m.materialize(folder,NOW)
    assert path.read_bytes()==before
    monkeypatch.setattr(m,'processor_digest',lambda:m.PROCESSOR);path.write_text('{"version":"foreign"}');before=path.read_bytes()
    with pytest.raises(ValueError,match='foreign output'):m.materialize(folder,NOW)
    assert path.read_bytes()==before


def test_API_counts_documents_and_clauses_separately_from_ETF_daily_coverage(tmp_path,monkeypatch):
    import market_risk
    fake={'availability':'scoped_rules_reviewed','documents':[{'published_on':'2026-05-22'},{'published_on':'2026-08-07'},{'published_on':'2026-09-11'}],
          'reviewed_versions':3,'reviewed_clauses':12,'index':{'observed_at':NOW.isoformat()}}
    monkeypatch.setattr(market_risk,'registration_rules_status',lambda *a:deepcopy(fake))
    row=next(r for r in market_risk.market_update_status(snapshot_dir=tmp_path,now=NOW) if r['source_id']=='etf_registration_rules')
    assert row['observation_count']==3 and row['observation_unit']=='机构文件版本' and row['observed_source_groups']==row['declared_series']==12
    assert row['observed_through_min']=='2026-05-22' and row['observed_through_max']=='2026-09-11'
    assert row['series_at_target'] is row['requested_through'] is None and row['date_basis']=='regulation_publication'
