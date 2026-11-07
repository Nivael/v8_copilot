from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json

import pytest

import node_public_court_pool as m

NOW = datetime(2026, 11, 5, 14, tzinfo=timezone.utc)


@pytest.fixture
def capture(tmp_path, monkeypatch):
    folder = tmp_path / 'raw'; folder.mkdir(); (folder / 'metadata').mkdir()
    code, org, aid = '000001', 'gssz0000001', '1234567890'
    stamp = int(datetime(2023, 3, 1, 16, tzinfo=timezone.utc).timestamp()) * 1000
    text = '证券代码:000001测试股份有限公司2023年3月1日收到测试市中级人民法院送达的(2023)测01破申1号《民事裁定书》,裁定受理公司重整申请。'
    pdfs = {aid: b'%PDF-1.7\ncontrolled primary', '1234567891': b'%PDF-1.7\ncontrolled subsidiary'}
    pages = {aid: [text], '1234567891': ['证券代码:000001测试股份有限公司关于子公司重整的公告']}
    title = '关于法院裁定受理公司重整的公告'
    url = 'https://static.cninfo.com.cn/finalpage/2023-03-02/' + aid + '.PDF'
    docs = []
    records = []
    for identifier in pdfs:
        u = url.replace(aid, identifier)
        t = title if identifier == aid else '关于法院裁定受理子公司重整的公告'
        source = {'url': u, 'response_url': u, 'observed_at': '2026-11-05T13:10:00+00:00'}
        docs.append({'announcement_id': identifier, 'symbol': code, 'title': t, 'catalog_date': '2023-03-02',
                     'org_id': org, 'announcement_time_raw_ms': stamp, 'primary_url': u,
                     'source': source, 'pages': 1, 'status': 'new_public_attachment_archived',
                     'existing_local_body_id_match': False, 'existing_local_body_text_match': False,
                     'independent_engine_texts_match': True, 'discovery_event_ids': ['E1']})
        records.append({'announcementId': identifier, 'announcementTitle': t, 'announcementTime': stamp,
                        'secCode': code, 'orgId': org, 'adjunctUrl': u.removeprefix('https://static.cninfo.com.cn/')})
    params = {'pageNum': '1', 'pageSize': '100', 'column': 'szse', 'tabName': 'fulltext', 'plate': 'sz',
              'stock': code + ',' + org, 'searchkey': '', 'secid': '', 'category': '', 'trade': '',
              'seDate': '2023-03-01~2023-03-04', 'sortName': '', 'sortType': '', 'isHLtitle': 'true'}
    refs = [{'label': 'lookup-' + code, 'url': m.LOOKUP, 'params': {'keyWord': code, 'maxNum': '10'}},
            {'label': 'query-E1', 'url': m.QUERY, 'params': params}]
    for r in refs:
        r.update(response_url=r['url'], method='POST', observed_at='2026-11-05T12:59:00+00:00')
    responses = {'lookup-' + code: [{'code': code, 'orgId': org}],
                 'query-E1': {'hasMore': False, 'totalAnnouncement': 2, 'announcements': records}}
    reviews = [{'announcement_id': d['announcement_id'], 'symbol': code, 'catalog_date': d['catalog_date'], 'source': d['source'],
                'stage': 'formal_restructuring_accepted' if d['announcement_id'] == aid else None,
                'scope': 'listed_company_court_stage_and_stated_dates_only', 'whole_body_semantics_checked': False,
                'proofs': {'identity': 1, 'receipt_and_acceptance': 1}, 'reviewed_at': '2026-11-05T13:20:00+00:00',
                'subject': '测试股份有限公司', 'court': '测试市中级人民法院', 'decision_date': None,
                'receipt_date': '2023-03-01', 'court_case': '（2023）测01破申1号'} for d in docs]
    p6 = {'run_id': 'active', 'as_of': '2026-07-20', 'verified_event_count': 1}
    events = [{'event_id': 'E1', 'source_kind': 'official_title_exact', 'symbol': code,
               'event_type': 'formal_restructuring_accepted', 'source_ref': 'cninfo:AN1'}]
    review = {'version': 'node_public_court_review_v1', 'p6_run': p6, 'metadata_refs': refs, 'documents': docs, 'reviews': reviews,
              'metadata_captured_at': '2026-11-05T13:00:00+00:00', 'archive_completed_at': '2026-11-05T13:11:00+00:00',
              'review_completed_at': '2026-11-05T13:25:00+00:00',
              'selection': [{'event_id': 'E1', 'symbol': code, 'original_event_type': 'formal_restructuring_accepted',
                             'original_source_ref': 'cninfo:AN1', 'selected_public_announcement_id': aid}],
              'counts': {'new_public_PDFs_archived': 2, 'PDF_pages_archived': 2, 'selected_candidates': 1,
                         'documents_with_scoped_review': 2, 'positive_scoped_stage_clauses': 1}}
    fields = {k: reviews[0][k] for k in ('subject', 'court', 'decision_date', 'receipt_date', 'court_case')}
    admission = {'version': 'node_public_court_admission_v1', 'policy': 'independent_court_stage_clauses_v1',
                 'scope': 'listed_company_court_stage_and_stated_dates_only', 'reviewed_at': '2026-11-05T13:30:00+00:00',
                 'full_body_semantics_checked': False, 'P8_gold_validation_completed': False, 'historical_PIT': False,
                 'institutional_or_market_effect_claim': False,
                 'items': [{'announcement_id': aid, 'symbol': code, 'event_type': 'formal_restructuring_accepted',
                            'information_available_date': '2023-03-02', 'discovery_event_id': 'E1', 'original_discovery_source_ref': 'cninfo:AN1',
                            'primary_source_identity': 'independent_canonical_CNINFO_attachment', 'original_discovery_alias_identity_asserted': False,
                            'stated_fields': fields, 'refined_since_initial_review': [], 'reviewed_pages': [1],
                            'stage_proof': {'page': 1, 'text': text}}]}
    rp, ap = tmp_path / 'review.json', tmp_path / 'admission.json'
    monkeypatch.setattr(m, 'REVIEW_PATH', rp); monkeypatch.setattr(m, 'ADMISSION_PATH', ap)
    monkeypatch.setattr(m, 'REVIEW', review); monkeypatch.setattr(m, 'ADMISSION', admission)
    exclusions = {'ids': ['protected-existing-id'], 'texts': ['a' * 64]}

    def bind():
        ids = json.dumps(exclusions['ids']).encode(); ts = json.dumps({'hashes': exclusions['texts']}).encode()
        (folder / 'exclusion_ids.json').write_bytes(ids); (folder / 'exclusion_text_digests.json').write_bytes(ts)
        review['local_body_exclusion'] = {'protected_ID_snapshot_sha256': sha256(ids).hexdigest(),
                                        'protected_text_snapshot_sha256': sha256(ts).hexdigest(),
                                        'protected_id_count': len(exclusions['ids']), 'protected_normalized_text_count': len(exclusions['texts'])}
        for ref in refs:
            raw = json.dumps(responses[ref['label']], ensure_ascii=False).encode()
            ref.update(sha256=sha256(raw).hexdigest(), bytes=len(raw)); (folder / 'metadata' / (ref['sha256'] + '.json')).write_bytes(raw)
        for d in docs:
            identifier = d['announcement_id']; raw = pdfs[identifier]; source = d['source']
            source.update(raw_sha256=sha256(raw).hexdigest(), bytes=len(raw)); (folder / (source['raw_sha256'] + '.pdf')).write_bytes(raw)
            encoded = json.dumps({'pages': pages[identifier]}, ensure_ascii=False).encode(); h = sha256(encoded).hexdigest()
            (folder / (h + '.json')).write_bytes(encoded)
            d.update(text_sha256=h, secondary_text_sha256=h,
                     normalized_text_digests=[sha256(m.compact(''.join(pages[identifier])).encode()).hexdigest()] * 2)
            r = next(r for r in reviews if r['announcement_id'] == identifier)
            r.update(text_sha256=h, secondary_text_sha256=h)
        rp.write_text(json.dumps(review, ensure_ascii=False)); rh = sha256(rp.read_bytes()).hexdigest()
        admission['source_review_profile_sha256'] = rh
        ap.write_text(json.dumps(admission, ensure_ascii=False))
        monkeypatch.setattr(m, 'REVIEW_SHA', rh); monkeypatch.setattr(m, 'ADMISSION_SHA', sha256(ap.read_bytes()).hexdigest())
    bind()
    return folder, events, p6, review, admission, responses, pages, exclusions, bind


def test_primary_binding_is_independent_of_original_an_alias_and_retains_unknown_court_date(capture):
    folder, events, p6, *_ = capture
    data = m.pool_status(events, p6, folder, NOW)
    assert data['availability'] == 'observed' and data['primary_bound_clauses'] == 1
    assert data['archived_PDFs'] == data['archived_pages'] == data['scoped_review_documents'] == 2
    assert data['extra_related_entity_exclusions'] == 1 and data['unknown_decision_dates'] == 1
    fact, = data['facts']
    assert fact['source_ref'] == 'cninfo:1234567890' and fact['original_discovery_source_ref'] == 'cninfo:AN1'
    assert fact['event_date'] is None and fact['information_available_date'] == '2023-03-02'
    assert fact['receipt_date'] == '2023-03-01' and fact['original_alias_asserted'] is False
    assert data['historical_PIT'] is data['full_body_semantics_checked'] is data['P8_gold_validation_completed'] is False


@pytest.mark.parametrize('bad', ['company', 'org', 'id', 'attachment', 'title', 'millis', 'paging', 'total', 'duplicate',
                                'query_company', 'query_future', 'method', 'redirect', 'header', 'proof', 'proof_page',
                                'stage', 'discovery', 'alias', 'guessed_court_date', 'wrong_receipt', 'wrong_case', 'foreign_scope',
                                'whole_body_claim', 'future_review', 'naive_review', 'review_before_capture', 'archive_order',
                                'protected_id', 'protected_text', 'duplicate_fact', 'positive_frame', 'archive_count'])
def test_rehashed_metadata_text_or_admission_errors_never_keep_old_fact_counts(capture, bad):
    folder, events, p6, review, admission, responses, pages, exclusions, bind = capture
    rows = responses['query-E1']['announcements']; row = rows[0]; item = admission['items'][0]
    if bad == 'company': row['secCode'] = '999999'
    elif bad == 'org': responses['lookup-000001'][0]['orgId'] = 'other'
    elif bad == 'id': row['announcementId'] = '9999999999'
    elif bad == 'attachment': row['adjunctUrl'] = row['adjunctUrl'].replace('1234567890', '9999999999')
    elif bad == 'title': row['announcementTitle'] = 'different title'
    elif bad == 'millis': row['announcementTime'] -= 86400000
    elif bad == 'paging': responses['query-E1']['hasMore'] = True
    elif bad == 'total': responses['query-E1']['totalAnnouncement'] = 3
    elif bad == 'duplicate': rows.append(deepcopy(row)); responses['query-E1']['totalAnnouncement'] = 3
    elif bad == 'query_company': review['metadata_refs'][1]['params']['stock'] = '999999,other'
    elif bad == 'query_future': review['metadata_refs'][1]['params']['seDate'] = '2023-03-01~2027-03-01'
    elif bad == 'method': review['metadata_refs'][1]['method'] = 'GET'
    elif bad == 'redirect': review['documents'][0]['source']['response_url'] = 'https://example.com/notice.pdf'
    elif bad == 'header': pages['1234567890'][0] = pages['1234567890'][0].replace('000001', '999999')
    elif bad == 'proof': item['stage_proof']['text'] = 'a different court proof with more than twenty letters'
    elif bad == 'proof_page': item['stage_proof']['page'] = 2
    elif bad == 'stage': review['reviews'][0]['stage'] = None
    elif bad == 'discovery': events[0]['source_ref'] = 'cninfo:AN2'
    elif bad == 'alias': item['original_discovery_alias_identity_asserted'] = True
    elif bad == 'guessed_court_date': item['stated_fields']['decision_date'] = item['stated_fields']['receipt_date']
    elif bad == 'wrong_receipt': item['stated_fields']['receipt_date'] = '2023-03-02'
    elif bad == 'wrong_case': item['stated_fields']['court_case'] = '（2023）测01破申99号'
    elif bad == 'foreign_scope': admission['scope'] = 'whole_body'
    elif bad == 'whole_body_claim': admission['full_body_semantics_checked'] = True
    elif bad == 'future_review': admission['reviewed_at'] = '2026-11-06T00:00:00+00:00'
    elif bad == 'naive_review': admission['reviewed_at'] = '2026-11-05T13:30:00'
    elif bad == 'review_before_capture': review['reviews'][0]['reviewed_at'] = '2026-11-05T13:05:00+00:00'
    elif bad == 'archive_order': review['archive_completed_at'] = '2026-11-05T12:00:00+00:00'
    elif bad == 'protected_id': exclusions['ids'].append('1234567890')
    elif bad == 'protected_text': exclusions['texts'].append(sha256(m.compact(pages['1234567890'][0]).encode()).hexdigest())
    elif bad == 'duplicate_fact': admission['items'].append(deepcopy(item))
    elif bad == 'positive_frame': admission['items'] = []
    elif bad == 'archive_count': review['counts']['PDF_pages_archived'] = 3
    bind(); data = m.pool_status(events, p6, folder, NOW)
    assert data['availability'] == 'invalid' and data['facts'] == []
    assert 'primary_bound_clauses' not in data


def test_missing_changed_originals_profiles_or_p6_frame_cannot_reuse_previous_counts(capture):
    folder, events, p6, review, _, _, _, _, _ = capture
    path = folder / (review['documents'][0]['source']['raw_sha256'] + '.pdf')
    before = path.read_bytes(); path.write_bytes(before + b'changed')
    assert m.pool_status(events, p6, folder, NOW)['availability'] == 'invalid'
    path.write_bytes(before)
    assert m.pool_status(events, {**p6, 'run_id': 'changed'}, folder, NOW)['facts'] == []
    m.ADMISSION_PATH.write_text('{}')
    assert m.pool_status(events, p6, folder, NOW)['availability'] == 'invalid'
    assert m.pool_status(events, p6, folder / 'absent', NOW)['availability'] == 'missing'
