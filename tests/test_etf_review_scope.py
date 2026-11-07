from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

import pytest

from canonical_json import digest
import etf_review_scope as m

NOW = datetime(2026, 11, 6, tzinfo=timezone.utc)


def pages_for(case):
    head = case['code'][:6] + case['fund_name'] + case['issuer'] + '。'
    if case['kind'] == 'liquidity_service_end':
        text = case['proofs'][0]['text'] + ',本公司终止' + case['provider'] + '为' + case['fund_name'] + '提供流动性服务。'
    else: text = '。'.join(p['text'] for p in case['proofs']) + '。投资者申赎的份数应为上述单位的整数倍。'
    pages = [head] * (case['page_count'] or 1)
    pages[(case['proofs'][0]['page'] or 1)-1] += text
    return pages


@pytest.mark.parametrize('case',m.PROFILE['cases'],ids=lambda c:c['code']+'-'+c['published_on'])
def test_positive_scoped_business_clauses_never_certify_total_share_or_cash_changes(case):
    facts = m.parse_supplement(pages_for(case), case)
    assert facts['announced_effective_on'] == case['announced_effective_on']
    assert all(facts[k] is False for k in ('implementation_verified','current_validity_verified','fund_total_share_conversion','market_window_correction_applied'))
    assert facts['estimated_net_subscription_yuan'] is None
    if case['kind'] == 'creation_unit_declaration':
        assert facts['unit_before_shares'] == case['unit_before_shares']
        assert facts['unit_after_shares'] == case['unit_after_shares']


@pytest.mark.parametrize('bad',['fund','issuer','code','proof_page','proof_text','ambiguous_clause','unit_before_inferred','unit_scope','effective_date','publication_after_effective','roles','provider','extra_fund','pause_code','pause_resume','pause_record','HTML_page'])
def test_changed_actor_quantity_scope_and_date_roles_are_rejected(bad):
    index = 0 if bad in ('provider','extra_fund') else 7 if bad.startswith('pause_') else 13 if bad=='HTML_page' else 14
    case=deepcopy(m.PROFILE['cases'][index]);pages=pages_for(case)
    if bad=='fund': pages[0]=pages[0].replace(case['fund_name'],'另一只基金')
    elif bad=='issuer': pages[0]=pages[0].replace(case['issuer'],'另一家管理公司')
    elif bad=='code': pages[0]=pages[0].replace(case['code'][:6],'999999')
    elif bad=='proof_page': case['proofs'][0]['page']=2
    elif bad=='proof_text': case['proofs'][0]['text']='未在原文出现的条款'
    elif bad=='ambiguous_clause': pages[0]+=case['proofs'][0]['text']
    elif bad=='unit_before_inferred': case['unit_before_shares']='2000000'
    elif bad=='unit_scope': case['unit_scope']='whole_fund_total'
    elif bad=='effective_date': case['announced_effective_on']='2026-07-17'
    elif bad=='publication_after_effective': case['published_on']='2026-07-21'
    elif bad=='roles': case['proofs'][0]['role']='publication_date'
    elif bad=='provider': case['provider']='另一家证券股份有限公司'
    elif bad=='extra_fund': pages[0]+='另一个基金代码159922'
    elif bad=='pause_code': case['creation_redemption_code']='510500'
    elif bad=='pause_resume': case['announced_resume_on']='2015-04-14'
    elif bad=='pause_record': case['record_on']='2015-04-14'
    else: case['proofs'][0]['page']=1
    with pytest.raises(ValueError):m.parse_supplement(pages,case)


@pytest.fixture
def sources(tmp_path,monkeypatch):
    directory=tmp_path/'etf_announcements';(directory/'document_raw').mkdir(parents=True);(directory/'document_text').mkdir()
    cases=deepcopy([m.PROFILE['cases'][i] for i in (0,3,4,7,13,14)])
    profile=deepcopy(m.PROFILE);profile['cases']=cases;monkeypatch.setattr(m,'PROFILE',profile)
    documents={};selected={}
    for case in cases:
        pages=pages_for(case); payload={'format':case['format'],'page_count':case['page_count'],'pages':pages}
        text=json.dumps(payload,ensure_ascii=False).encode();case['text_sha256']=hashlib.sha256(text).hexdigest()
        (directory/'document_text'/(case['text_sha256']+'.json')).write_bytes(text)
        if case['format']=='issuer_html':
            raw=json.dumps({'error_no':0,'results':[{'ad_id':'99609','pub_date':case['published_on'],'title':case['title'],'content':pages[0],'attachment_url':''}]},ensure_ascii=False).encode()
            url='https://www.jsfund.cn/servlet/json';params={'funcNo':'741021','ad_id':'99609'}
        else:raw=b'%PDF-synthetic-test-'+case['document_id'].encode();url=m.capture_tools.allowed_url(case['url']);params={}
        case['raw_sha256']=hashlib.sha256(raw).hexdigest();(directory/'document_raw'/(case['raw_sha256']+'.raw')).write_bytes(raw)
        selected[case['document_id']]={k:case[k] for k in ('document_id','code','published_on','title','url')}
        selected[case['document_id']]['review_reason']='historical_share_title'
        documents[case['document_id']]={'status':'text_available','document_id':case['document_id'],'code':case['code'],'source_url':case['url'],
            'format':case['format'],'page_count':case['page_count'],'text_sha256':case['text_sha256'],'character_count':sum(map(len,pages)),
            'responses':[{'response_sha256':case['raw_sha256'],'url':url,'params':params,'observed_at':case['observed_at'],'catalog_digest':profile['catalog_digest']}]}
    old={'document_id':'old-result','code':'510500.SH','published_on':'2015-04-15','title':'已核折算结果','url':'https://www.sse.com.cn/result.pdf','review_reason':'historical_share_title'}
    selected['old-result']=old
    documents['old-result']={**deepcopy(next(iter(documents.values()))),'document_id':'old-result','code':old['code'],'source_url':old['url']}
    capture={'catalog_digest':profile['catalog_digest'],'completed_at':'2026-11-05T00:00:00+00:00','documents':documents}
    a={'availability':'observed','content_digest':profile['catalog_digest'],'fulltext':{'availability':'observed','content_digest':profile['capture_digest']},
       'window_start':profile['window_start'],'window_end':profile['window_end'],'through':'2026-11-05','catalogs':[{'required_documents':list(selected.values())}]}
    views={'quarterly':{'availability':'observed','reports':[]},'continuity':{'availability':'observed','reports':[]},
           'events':{'availability':'partial','failures':[],'events':[{'event_id':'510500-conversion-20150414','code':'510500.SH','record_date':'2015-04-13','event_date':'2015-04-14','documents':[{'document_id':'old-result','pages':[1]}]}]},
           'notices':{'availability':'partial','failures':[],'notices':[]},'prospectuses':{'availability':'partial','failures':[],'versions':[]}}
    monkeypatch.setattr(m.catalogs,'announcement_status',lambda *a,**k:deepcopy(a_source))
    a_source=a
    monkeypatch.setattr(m.quarterly,'load_report_capture',lambda *a,**k:(capture,{}))
    monkeypatch.setattr(m.quarterly,'quarterly_status',lambda *a,**k:deepcopy(views['quarterly']))
    monkeypatch.setattr(m.continuity,'report_continuity_status',lambda *a,**k:deepcopy(views['continuity']))
    monkeypatch.setattr(m.events,'share_event_status',lambda *a,**k:deepcopy(views['events']))
    monkeypatch.setattr(m.notices,'notice_review_status',lambda *a,**k:deepcopy(views['notices']))
    monkeypatch.setattr(m.prospectuses,'prospectus_rule_status',lambda *a,**k:deepcopy(views['prospectuses']))
    # The old parser's already-checked result is outside this synthetic capture fixture.
    original=m.capture_tools.valid_ready
    monkeypatch.setattr(m.capture_tools,'valid_ready',lambda item,*a,**k:True if item['document_id']=='old-result' else original(item,*a,**k))
    return tmp_path,directory,a,capture,selected,views


def test_exact_document_union_reminder_grouping_physical_pages_and_pause_link(sources):
    root,*_=sources;data=m.project(m.collect_inputs(root=root,now=NOW))
    assert data['selected_document_items']==data['items_with_scoped_review']==7 and data['items_without_scoped_review']==0
    assert data['distinct_creation_unit_declarations']==3 and data['duplicate_unit_reminders']==1
    html=next(d for d in data['documents'] if d['format']=='issuer_html');assert html['reviewed_pages']==[] and html['page_count'] is None
    pause=next(d for d in data['supplemental_documents'] if d['kind']=='creation_redemption_pause')
    assert (pause['record_on'],pause['related_event_date'],pause['announced_resume_on'])==('2015-04-13','2015-04-14','2015-04-15')
    assert next(d for d in data['documents'] if d['document_id']==pause['document_id'])['reviewed_pages']==[2]
    assert data['pdf_items']==6 and data['distinct_pdf_originals']==5 and data['pdf_pages_by_item']==7 and data['distinct_pdf_pages']==6


@pytest.mark.parametrize('bad',['raw_bytes','text_bytes','source_metadata','time','missing_review','foreign_review','duplicate_scope','duplicate_catalog','unavailable_old_review','pause_crosslink','PDF_page','window','capture_digest'])
def test_corrupted_source_or_review_union_cannot_be_counted_as_covered(sources,bad):
    root,directory,a,capture,selected,views=sources;case=m.PROFILE['cases'][0]
    if bad=='raw_bytes':(directory/'document_raw'/(case['raw_sha256']+'.raw')).write_bytes(b'changed')
    elif bad=='text_bytes':(directory/'document_text'/(case['text_sha256']+'.json')).write_text('{}')
    elif bad=='source_metadata':a['catalogs'][0]['required_documents'][0]['title']='另一篇公告'
    elif bad=='time':case['observed_at']='2026-11-07T00:00:00+00:00'
    elif bad=='missing_review':m.PROFILE['cases'].pop()
    elif bad=='foreign_review':views['events']['events'][0]['documents'][0]['document_id']='foreign'
    elif bad=='duplicate_scope':views['events']['events'][0]['documents']*=2
    elif bad=='duplicate_catalog':a['catalogs'][0]['required_documents']*=2
    elif bad=='unavailable_old_review':views['notices']['failures']=['source changed']
    elif bad=='pause_crosslink':views['events']['events'][0]['event_date']='2015-04-15'
    elif bad=='PDF_page':views['events']['events'][0]['documents'][0]['pages']=[2]
    elif bad=='window':a['window_end']='2026-10-31'
    else:a['fulltext']['content_digest']='changed'
    with pytest.raises((ValueError,KeyError)):m.collect_inputs(root=root,now=NOW)


def test_unknown_old_unit_cannot_merge_with_a_conflicting_same_day_declaration(sources):
    inputs=m.collect_inputs(root=sources[0],now=NOW);changed=deepcopy(inputs['supplemental'][-1]);changed['unit_before_shares']='2000000'
    inputs['supplemental'].append(changed)
    with pytest.raises(ValueError,match='conflicting'):m.project(inputs)


def test_HTML_original_is_rebuilt_without_inventing_a_PDF_page(sources,monkeypatch):
    _,directory,_,capture,selected,_=sources;html=deepcopy(m.PROFILE['cases'][4]);monkeypatch.setitem(m.PROFILE,'cases',[html])
    assert m.read_supplement(directory,selected,capture,NOW,full=True)[0]['unit_before_shares']=='900000'
    payload=json.loads((directory/'document_raw'/(html['raw_sha256']+'.raw')).read_text());payload['results'][0]['attachment_url']='unexpected.pdf'
    raw=json.dumps(payload,ensure_ascii=False).encode();new=hashlib.sha256(raw).hexdigest();(directory/'document_raw'/(new+'.raw')).write_bytes(raw)
    html['raw_sha256']=new;capture['documents'][html['document_id']]['responses'][0]['response_sha256']=new
    with pytest.raises(ValueError,match='HTML identity'):m.read_supplement(directory,selected,capture,NOW,full=True)


def test_GET_recomputes_scope_without_trusting_report_injection_or_writing(sources,tmp_path,monkeypatch):
    inputs=m.collect_inputs(root=sources[0],now=NOW);monkeypatch.setattr(m,'collect_inputs',lambda **k:deepcopy(inputs))
    output=tmp_path/'published';m.materialize(directory=output,now=NOW);path=output/'current.json'
    raw=json.loads(path.read_text());raw['report']={'estimated_net_subscription_yuan':123,'all_window_share_events_verified':True,'items_with_scoped_review':999}
    raw['content_digest']=digest({k:v for k,v in raw.items() if k!='content_digest'});path.write_text(json.dumps(raw));before=path.read_bytes()
    report=m.scope_status(output,now=NOW)
    assert report['items_with_scoped_review']==7 and report['estimated_net_subscription_yuan'] is None
    assert all(report[k] is False for k in ('full_document_semantics_checked','all_window_share_events_verified','corporate_actions_checked','daily_share_scope_verified','share_precision_verified','final_revision_verified','historical_PIT','effect_measured'))
    assert path.read_bytes()==before
    inputs['documents'][0]['title']='changed';invalid=m.scope_status(output,now=NOW)
    assert invalid['availability']=='invalid' and invalid['documents']==[] and 'items_with_scoped_review' not in invalid and path.read_bytes()==before


def test_source_or_code_race_and_foreign_output_preserve_current(sources,tmp_path,monkeypatch):
    inputs=m.collect_inputs(root=sources[0],now=NOW);monkeypatch.setattr(m,'collect_inputs',lambda **k:deepcopy(inputs))
    output=tmp_path/'published';m.materialize(directory=output,now=NOW);path=output/'current.json';before=path.read_bytes()
    changed=deepcopy(inputs);changed['documents'].pop();seq=iter([inputs,changed]);monkeypatch.setattr(m,'collect_inputs',lambda **k:next(seq))
    with pytest.raises(ValueError,match='source or code'):m.materialize(directory=output,now=NOW)
    assert path.read_bytes()==before
    def read(**kw):
        if not kw.get('full'):monkeypatch.setattr(m,'processor_digest',lambda:'changed')
        return deepcopy(inputs)
    monkeypatch.setattr(m,'collect_inputs',read)
    with pytest.raises(ValueError,match='source or code'):m.materialize(directory=output,now=NOW)
    assert path.read_bytes()==before and m.scope_status(output,now=NOW)['availability']=='reload_required'
    monkeypatch.setattr(m,'processor_digest',lambda:m.PROCESSOR);path.write_text('{"version":"foreign"}');before=path.read_bytes()
    with pytest.raises(ValueError,match='foreign'):m.materialize(directory=output,now=NOW)
    assert path.read_bytes()==before


def test_scope_item_coverage_does_not_become_market_or_cash_validation(tmp_path,monkeypatch):
    import market_risk
    fake={'availability':'scoped_reviewed','window_end':'2026-11-04','publication_cutoff':'2026-11-05','selected_document_items':105,'items_with_scoped_review':105}
    monkeypatch.setattr(market_risk,'etf_scope_status',lambda *a,**k:deepcopy(fake))
    status=market_risk.build_market_risk_status(snapshot_dir=tmp_path,database=tmp_path/'missing.db',manifest_path=tmp_path/'missing.json',now=NOW)
    assert status['parameters']['risk_weights'] is None and status['market_coverage']['st_style_at_target'] is False
    assert all(d['estimated_net_subscription_yuan'] is None for d in status['etf_aggregate'].values())
    row=next(r for r in market_risk.market_update_status(snapshot_dir=tmp_path,now=NOW) if r['source_id']=='etf_document_scope')
    assert row['observed_source_groups']==row['declared_series']==105 and row['series_at_target'] is None
    assert row['coverage_basis']=='ETF_scoped_review' and row['observation_unit']=='基金文档项' and row['observed_through_min']=='2026-11-05'
