"""Synthetic announcement clauses exercise semantics; no private/account sources."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

import pytest

from canonical_json import digest
from etf_share_events import parse_document, reconcile_case, share_event_status

NOW=datetime(2026,11,5,tzinfo=timezone.utc)


def plan(code='510310.SH',kind='merge',ratio=None):
    action='合并' if kind=='merge' else '拆分'
    ratio=ratio or ('0.49977589' if code=='510310.SH' else '0.36555' if kind=='merge' else '1.46301')
    if code=='510310.SH':
        dates='1、权益登记日：2024年9月20日。2、除权日：2024年9月23日。'
        same='于份额合并日（权益登记日当日）进行变更登记'
    else:
        dates=f'1、权益登记日：2022年{9 if kind=="merge" else 8}月{1 if kind=="merge" else 2}日。2、份额{action}日：2022年{9 if kind=="merge" else 8}月{2 if kind=="merge" else 3}日。'
        same=''
    return [f'基金代码：{code[:6]}。{dates}本基金本次基金份额{action}比例为{ratio}。{same}']


def result(code='510310.SH'):
    if code=='510310.SH':
        return ['基金代码：510310。登记结算机构已分别按照上述合并比例。'
            '本基金本次基金份额合并比例为0.49977589。'
            '份额合并日（权益登记日当日，即2024年9月20日），本基金合并前，场内基金份额总额为20.00份，场外基金份额总额为10.00份；'
            '本基金合并后，场内基金份额总额为10.00份，场外基金份额总额为5.00份。',
            '小数点后基金份额均进位为1份。']
    return ['基金代码：512100。本基金管理人已按照上述合并比例对权益登记日（2022年9月1日）登记在册的份额进行了合并。'
        '本基金本次基金份额合并比例为0.36555。小数点后基金份额均进位为1份。'
        '在份额合并日（2022年9月2日）本基金合并前的基金份额总额为10,000份；'
        '在份额合并日（2022年9月2日）本基金合并后的基金份额总额为3,656份。']


def cancel():
    return ['基金代码：512100。本基金原定于2022年8月2日为权益登记日、2022年8月3日为份额拆分日实施的基金份额拆分将取消。']


def unit():
    return ['基金代码：“512100”。从2024年2月21日起，本基金最小申购、赎回单位自100万份调整为200万份。']


def chain(code='510310.SH',kind='merge',resolution='implemented'):
    terminal={'implemented':'result','cancelled':'cancellation','announced_effective':'unit_notice'}[resolution]
    if kind=='creation_unit':
        return {'id':'unit','code':code,'kind':kind,'resolution':resolution}, [
            ({'document_id':'unit','published_on':'2024-02-21'},terminal,parse_document(unit(),code,kind,terminal))]
    docs=[({'document_id':'plan','published_on':'2024-09-13' if code=='510310.SH' else '2022-08-24' if kind=='merge' else '2022-07-25'},'plan',parse_document(plan(code,kind),code,kind,'plan'))]
    docs.append(({'document_id':'terminal','published_on':'2024-09-23' if code=='510310.SH' else '2022-09-05' if kind=='merge' else '2022-07-30'},terminal,
                 parse_document(cancel() if resolution=='cancelled' else result(code),code,kind,terminal)))
    return {'id':'synthetic','code':code,'kind':kind,'resolution':resolution},docs


def test_plan_cancellation_reminders_and_later_merge_are_distinct_events():
    case,docs=chain('512100.SH','split','cancelled')
    docs.insert(1,({'document_id':'reminder','published_on':'2022-07-27'},'reminder',deepcopy(docs[0][2])))
    cancelled=reconcile_case(case,docs)
    assert cancelled['resolution']=='cancelled' and cancelled['effective_ratio'] is None
    assert cancelled['planned_ratio']=='1.46301' and cancelled['event_date']=='2022-08-03'
    implemented=reconcile_case(*chain('512100.SH'))
    assert implemented['effective_ratio']=='0.36555' and implemented['event_date']=='2022-09-02'
    assert implemented['reported_totals']==[{'scope':'fund_total','before_shares':'10000','after_shares':'3656','after_minus_simple_ratio_shares':'0.50000'}]


def test_merge_preserves_exact_ratio_record_date_and_both_share_scopes():
    event=reconcile_case(*chain())
    assert event['event_date']==event['record_date']=='2024-09-20'  # Ex-right is September 23, not the share merger date.
    assert event['effective_ratio']=='0.49977589' and event['holder_rounding']=='ceil_to_whole_share'
    assert [row['scope'] for row in event['reported_totals']]==['exchange','off_exchange']
    assert event['reported_totals'][0]['after_minus_simple_ratio_shares']=='0.0044822000'
    assert event['not_a_subscription_flow'] is True


def test_creation_unit_change_does_not_become_a_split_or_a_total_share_multiplier():
    event=reconcile_case(*chain('512100.SH','creation_unit','announced_effective'))
    assert event['kind']=='creation_unit' and event['effective_ratio'] is None and event['planned_ratio'] is None
    assert event['unit_before_shares']=='1000000' and event['unit_after_shares']=='2000000'
    assert 'reported_totals' not in event


@pytest.mark.parametrize('change',['identity','future_wording','missing_rounding','ambiguous_ratio','different_after_day','wrong_factor_direction'])
def test_result_requires_implemented_whole_clauses_and_matching_dates(change):
    pages=result('512100.SH')
    if change=='identity':pages[0]=pages[0].replace('基金代码：512100','基金代码：510310')
    elif change=='future_wording':pages[0]=pages[0].replace('本基金管理人已按照','本基金管理人将按照')
    elif change=='missing_rounding':pages[0]=pages[0].replace('小数点后基金份额均进位为1份。','')
    elif change=='ambiguous_ratio':pages[0]+='本基金本次基金份额合并比例为0.4998。'
    elif change=='different_after_day':pages[0]=pages[0].replace('（2022年9月2日）本基金合并后','（2022年9月3日）本基金合并后')
    else:pages[0]=pages[0].replace('0.36555','1.36555')
    with pytest.raises(ValueError):parse_document(pages,'512100.SH','merge','result')


@pytest.mark.parametrize('change',['ratio','record_date','reminder','late_cancellation','early_result','duplicate','wrong_role'])
def test_chain_rejects_contradictory_or_misordered_resolutions(change):
    case,docs=chain('512100.SH','split','cancelled') if change=='late_cancellation' else chain()
    if change=='ratio':docs[-1][2]['ratio']='0.4998'
    elif change=='record_date':docs[-1][2]['record_date']='2024-09-21'
    elif change=='reminder':
        altered=deepcopy(docs[0][2]);altered['event_date']='2024-09-23'
        docs.insert(1,({'document_id':'reminder','published_on':'2024-09-14'},'reminder',altered))
    elif change=='late_cancellation':docs[-1][0]['published_on']='2022-08-04'
    elif change=='early_result':docs[-1][0]['published_on']='2024-09-19'
    elif change=='duplicate':docs.insert(1,deepcopy(docs[0]))
    else:case['resolution']='announced_effective'
    with pytest.raises(ValueError):reconcile_case(case,docs)


def setup_reader(folder,monkeypatch):
    case,docs=chain();case['documents']=[('plan','plan'),('terminal','result')]
    monkeypatch.setattr('etf_share_events.CASES',[case])
    # Raw byte/hash validation has dedicated capture tests. Here it is isolated
    # to exercise chain parsing, capture binding, dates and original-text reads.
    monkeypatch.setattr('etf_share_events.valid_ready',lambda *args:True)
    records=[];captured={};(folder/'document_text').mkdir()
    for (doc,role,_),pages in zip(docs,[plan(),result()],strict=True):
        body=json.dumps({'pages':pages}).encode();key=hashlib.sha256(body).hexdigest()
        (folder/'document_text'/f'{key}.json').write_bytes(body)
        source={**doc,'code':case['code'],'url':f'https://www.sse.com.cn/{doc["document_id"]}.pdf',
                'title':'基金份额合并结果的公告' if role=='result' else '实施基金份额合并业务的公告'}
        records.append(source)
        captured[doc['document_id']]={'text_sha256':key,'responses':[{'url':source['url'],'observed_at':NOW.isoformat()}]}
    capture={'catalog_digest':'catalog','completed_at':NOW.isoformat(),'documents':captured}
    capture['content_digest']=digest(capture)
    (folder/'document_capture.json').write_text(json.dumps(capture))
    announcements={'availability':'observed','through':'2026-11-05','window_start':'2026-08-04','window_end':'2026-11-04',
        'content_digest':'catalog','review_required_count':2,'fulltext':{'availability':'observed','content_digest':capture['content_digest']},
        'catalogs':[{'required_documents':records}]}
    return announcements,capture


def test_source_bound_partial_review_never_unlocks_whole_window_or_flow_correction(tmp_path,monkeypatch):
    announcements,_=setup_reader(tmp_path,monkeypatch)
    result=share_event_status(tmp_path,announcements,NOW)
    assert result['availability']=='partial' and result['reviewed_events']==1 and result['reconciled_documents']==2
    assert result['pending_documents']==0 and result['all_selected_documents_reconciled'] is False
    assert result['corporate_actions_checked'] is False and result['events'][0]['within_catalog_window'] is False
    assert result['events'][0]['documents'][1]['pages']==[1,2]


@pytest.mark.parametrize('change',['catalog','capture','source','role_title','future_capture','naive_observed','text_bytes','future_publication','unloaded_code'])
def test_reader_rejects_rebound_changed_or_unavailable_evidence(tmp_path,monkeypatch,change):
    announcements,capture=setup_reader(tmp_path,monkeypatch)
    if change=='catalog':announcements['content_digest']='different'
    elif change=='capture':announcements['fulltext']['content_digest']='different'
    elif change=='source':monkeypatch.setattr('etf_share_events.valid_ready',lambda *args:False)
    elif change=='role_title':announcements['catalogs'][0]['required_documents'][1]['title']='实施基金份额合并业务的公告'
    elif change=='future_publication':announcements['catalogs'][0]['required_documents'][1]['published_on']='2026-11-06'
    elif change=='text_bytes':
        key=capture['documents']['terminal']['text_sha256'];(tmp_path/'document_text'/f'{key}.json').write_text('changed')
    elif change=='unloaded_code':monkeypatch.setattr('etf_share_events.PARSER_DIGEST','not_loaded')
    else:
        capture.pop('content_digest')
        if change=='future_capture':capture['completed_at']='2026-11-06T00:00:00+00:00'
        else:capture['documents']['terminal']['responses'][0]['observed_at']='2026-11-05T00:00:00'
        capture['content_digest']=digest(capture);announcements['fulltext']['content_digest']=capture['content_digest']
        (tmp_path/'document_capture.json').write_text(json.dumps(capture))
    result=share_event_status(tmp_path,announcements,NOW)
    assert result['reviewed_events']==0 and result['corporate_actions_checked'] is False
