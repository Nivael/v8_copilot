"""Offline primary-source binding for explicitly reviewed court-stage clauses."""
from collections import Counter
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata
from zoneinfo import ZoneInfo

from canonical_json import digest
from node_publication_metadata import LOOKUP, QUERY, catalog_day, stamp
from settings import DATA_ROOT

VERSION = 'node_public_court_pool_v1'
REVIEW_PATH = Path(__file__).with_name('node_public_court_review_v1.json')
ADMISSION_PATH = Path(__file__).with_name('node_public_court_admission_v1.json')
REVIEW = json.loads(REVIEW_PATH.read_text())
ADMISSION = json.loads(ADMISSION_PATH.read_text())
REVIEW_SHA = sha256(REVIEW_PATH.read_bytes()).hexdigest()
ADMISSION_SHA = sha256(ADMISSION_PATH.read_bytes()).hexdigest()
OUTPUT = DATA_ROOT / 'local_data/v8_copilot/market_risk/node_public_notice_candidates'
STAGES = {'formal_restructuring_accepted', 'restructuring_plan_approved'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def compact(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value))


def iso(value):
    require(isinstance(value, str) and bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', value)), 'invalid court-source date')
    return date.fromisoformat(value).isoformat()


def original(folder, name, expected, size=None):
    require(bool(re.fullmatch(r'[0-9a-f]{64}', expected)), 'invalid source digest')
    raw = (folder / name).read_bytes()
    require(sha256(raw).hexdigest() == expected and (size is None or len(raw) == size), 'source bytes changed')
    return raw


def collect(directory, events, p6_run, now):
    require(sha256(REVIEW_PATH.read_bytes()).hexdigest() == REVIEW_SHA and
            sha256(ADMISSION_PATH.read_bytes()).hexdigest() == ADMISSION_SHA, 'reload changed court profiles')
    require(REVIEW['version'] == 'node_public_court_review_v1' and ADMISSION['version'] == 'node_public_court_admission_v1'
            and ADMISSION['source_review_profile_sha256'] == REVIEW_SHA, 'unbound review profile')
    require(p6_run == REVIEW['p6_run'], 'discovery source frame changed')
    require(ADMISSION['policy'] == 'independent_court_stage_clauses_v1' and
            ADMISSION['scope'] == 'listed_company_court_stage_and_stated_dates_only', 'unknown admission scope')
    for key in ('full_body_semantics_checked', 'P8_gold_validation_completed', 'historical_PIT', 'institutional_or_market_effect_claim'):
        require(ADMISSION[key] is False, 'unsupported admission claim')
    completed = stamp(ADMISSION['reviewed_at'], now)
    captured = stamp(REVIEW['metadata_captured_at'], completed)
    archived = stamp(REVIEW['archive_completed_at'], completed)
    initial_review = stamp(REVIEW['review_completed_at'], completed)
    require(captured <= archived <= initial_review, 'capture/archive/review order changed')
    exclusion = REVIEW['local_body_exclusion']
    ids = json.loads(original(directory, 'exclusion_ids.json', exclusion['protected_ID_snapshot_sha256']))
    text_exclusion = json.loads(original(directory, 'exclusion_text_digests.json', exclusion['protected_text_snapshot_sha256']))['hashes']
    require(len(set(ids)) == len(ids) == exclusion['protected_id_count'] and
            len(set(text_exclusion)) == len(text_exclusion) == exclusion['protected_normalized_text_count'] and
            all(isinstance(v,str) for v in ids) and all(re.fullmatch(r'[0-9a-f]{64}',v) for v in text_exclusion), 'exclusion frame changed')
    ids, text_exclusion = set(ids), set(text_exclusion)

    active = {r['event_id']: r for r in events}
    require(len(active) == len(events), 'duplicate active discovery event')
    selected = {}
    for item in REVIEW['selection']:
        event = active.get(item['event_id'])
        require(event is not None and event['source_kind'] == 'official_title_exact' and
                (event['symbol'], event['event_type'], event['source_ref']) ==
                (item['symbol'], item['original_event_type'], item['original_source_ref']), 'discovery identity changed')
        aid = item['selected_public_announcement_id']
        require(aid not in selected, 'duplicate selected attachment')
        selected[aid] = item

    lookups, queries, refs = {}, {}, {}
    for ref in REVIEW['metadata_refs']:
        label = ref['label']; params = ref['params']
        require(label not in refs and ref['url'] == ref['response_url'] and ref['method'] == 'POST', 'metadata request identity changed')
        observed = stamp(ref['observed_at'], captured)
        data = json.loads(original(directory / 'metadata', ref['sha256'] + '.json', ref['sha256'], ref['bytes']))
        refs[label] = ref
        if ref['url'] == LOOKUP:
            code = params['keyWord']
            require(bool(re.fullmatch(r'\d{6}', code)) and label == 'lookup-' + code and
                    params == {'keyWord': code, 'maxNum': '10'} and code not in lookups, 'company lookup scope changed')
            matches = [r for r in data if r['code'] == code]
            require(len(matches) == 1 and bool(matches[0]['orgId']), 'ambiguous company lookup')
            lookups[code] = matches[0]['orgId']
        elif ref['url'] == QUERY:
            event_id = label.removeprefix('query-'); event = active.get(event_id)
            code, org = params['stock'].split(','); start, end = params['seDate'].split('~')
            expected = {'pageNum': '1', 'pageSize': '100', 'column': 'sse' if code.startswith('6') else 'szse',
                        'tabName': 'fulltext', 'plate': 'sh' if code.startswith('6') else 'sz', 'stock': code + ',' + org,
                        'searchkey': '', 'secid': '', 'category': '', 'trade': '', 'seDate': start + '~' + end,
                        'sortName': '', 'sortType': '', 'isHLtitle': 'true'}
            rows = data['announcements'] or []
            require(event is not None and event['symbol'] == code and params == expected and
                    iso(start) <= iso(end) <= observed.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat() and lookups.get(code) == org and data['hasMore'] is False and
                    data['totalAnnouncement'] == len(rows) and len({str(r['announcementId']) for r in rows}) == len(rows),
                    'metadata query frame or paging changed')
            require(all(r['secCode'] == code and r['orgId'] == org and start <= catalog_day(r['announcementTime']) <= end
                        for r in rows), 'metadata company or date changed')
            queries[event_id] = rows
        else:
            raise ValueError('foreign metadata endpoint')
    require(set(queries) == {r['event_id'] for r in selected.values()} and
            set(lookups) == {r['symbol'] for r in selected.values()}, 'incomplete discovery metadata frame')

    documents, texts = {}, {}
    for item in REVIEW['documents']:
        aid = item['announcement_id']; source = item['source']; code = item['symbol']
        require(aid not in documents and aid not in ids and item['status'] == 'new_public_attachment_archived' and
                item['existing_local_body_id_match'] is False and item['existing_local_body_text_match'] is False, 'non-fresh or duplicate attachment')
        require(source['url'] == source['response_url'] == item['primary_url'] and
                bool(re.fullmatch(r'https://static\.cninfo\.com\.cn/finalpage/' + iso(item['catalog_date']) + '/' + re.escape(aid) + r'\.pdf', source['url'], re.I)),
                'primary attachment identity changed')
        require(catalog_day(item['announcement_time_raw_ms']) == item['catalog_date'], 'catalog day changed')
        fetched = stamp(source['observed_at'], archived)
        require(item['catalog_date'] <= fetched.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat(), 'future catalog date')
        require(type(source['bytes']) is int and 0 < source['bytes'] <= 12 * 1024 * 1024, 'unbounded original PDF')
        raw = original(directory, source['raw_sha256'] + '.pdf', source['raw_sha256'], source['bytes'])
        require(raw.startswith(b'%PDF-'), 'not an original PDF')
        extracted, normalized = [], []
        for key in ('text_sha256', 'secondary_text_sha256'):
            payload = json.loads(original(directory, item[key] + '.json', item[key]))
            pages = payload['pages']
            require(type(item['pages']) is int and 1 <= item['pages'] <= 80 and len(pages) == item['pages'] and
                    all(isinstance(p, str) for p in pages), 'invalid extracted PDF pages')
            norm = sha256(compact(''.join(pages)).encode()).hexdigest()
            require(norm not in text_exclusion, 'existing local body text excluded')
            extracted.append(pages); normalized.append(norm)
        require(normalized == item['normalized_text_digests'] and normalized[0] == normalized[1] and
                item['independent_engine_texts_match'] is True and
                bool(re.search(r'(?:证券代码|股票代码)[:：]?' + re.escape(code), compact(extracted[0][0]))), 'PDF identity or extraction changed')
        matches = [r for eid in item['discovery_event_ids'] for r in queries[eid] if str(r['announcementId']) == aid]
        require(matches and all(r['secCode'] == code and r['orgId'] == item['org_id'] == lookups[code] and
                r['announcementTime'] == item['announcement_time_raw_ms'] and re.sub('<[^>]+>', '', r['announcementTitle']) == item['title'] and
                'https://static.cninfo.com.cn/' + r['adjunctUrl'] == source['url'] for r in matches), 'PDF not bound to official company catalog')
        documents[aid] = item; texts[aid] = extracted[0]

    reviews = {r['announcement_id']: r for r in REVIEW['reviews']}
    require(len(reviews) == len(REVIEW['reviews']) and set(selected) <= reviews.keys(), 'incomplete scoped review frame')
    counts = REVIEW['counts']
    require(len(documents) == counts['new_public_PDFs_archived'] and sum(d['pages'] for d in documents.values()) == counts['PDF_pages_archived'] and
            len(refs) == len(REVIEW['metadata_refs']) and len(selected) == counts['selected_candidates'] and len(reviews) == counts['documents_with_scoped_review'],
            'archive or scoped review counts changed')
    facts, seen = [], set()
    for item in ADMISSION['items']:
        aid = item['announcement_id']; review = reviews[aid]; doc = documents[aid]; selection = selected[aid]; fields = item['stated_fields']
        require(aid not in seen and review['stage'] in STAGES and item['event_type'] == review['stage'] and
                item['symbol'] == review['symbol'] == doc['symbol'] == selection['symbol'] and
                item['information_available_date'] == review['catalog_date'] == doc['catalog_date'] and
                item['discovery_event_id'] == selection['event_id'] and item['original_discovery_source_ref'] == selection['original_source_ref'] and
                item['primary_source_identity'] == 'independent_canonical_CNINFO_attachment' and item['original_discovery_alias_identity_asserted'] is False,
                'admission is not the reviewed independent court clause')
        require(review['scope'] == ADMISSION['scope'] and review['whole_body_semantics_checked'] is False and
                review['source'] == doc['source'] and review['text_sha256'] == doc['text_sha256'] and
                review['secondary_text_sha256'] == doc['secondary_text_sha256'], 'scoped review source changed')
        require(stamp(doc['source']['observed_at'], completed) <= stamp(review['reviewed_at'], completed), 'review predates original capture')
        pages = texts[aid]; proof = item['stage_proof']; reviewed_pages = item['reviewed_pages']
        require(reviewed_pages == sorted(set(reviewed_pages)) and set(review['proofs'].values()) <= set(reviewed_pages) and
                all(type(n) is int and 1 <= n <= len(pages) for n in reviewed_pages) and proof['page'] in reviewed_pages and
                isinstance(proof['text'], str) and len(proof['text']) >= 20 and compact(proof['text']) in compact(pages[proof['page'] - 1]), 'stage proof changed')
        require(('裁定受理' in proof['text'] or '受理申请人' in proof['text']) if item['event_type'] == 'formal_restructuring_accepted'
                else '裁定批准' in proof['text'], 'stage proof role changed')
        joined = compact(''.join(pages[n - 1] for n in reviewed_pages))
        require(compact(fields['subject']) in compact(pages[0]) and fields['court'] and
                set(item['refined_since_initial_review']) <= {'receipt_date', 'court_case'}, 'company identity or unreviewed refinement')
        for key in ('subject', 'court', 'decision_date', 'receipt_date', 'court_case'):
            require(key in item['refined_since_initial_review'] or fields[key] == review[key], 'unreviewed field override')
        for key in ('decision_date', 'receipt_date'):
            if fields[key] is not None:
                day = date.fromisoformat(iso(fields[key])); token = rf'{day.year}年0?{day.month}月0?{day.day}日'
                require(fields[key] <= item['information_available_date'] and bool(re.search(token, joined)), 'stated date not in reviewed pages')
                if key in item['refined_since_initial_review']:
                    require(bool(re.search(token, proof['text'])) and '收到' in proof['text'], 'refined receipt lacks explicit proof')
        if fields['court_case'] is not None:
            require(compact(fields['court_case']) in joined, 'court case not in reviewed pages')
            if 'court_case' in item['refined_since_initial_review']:
                require(compact(fields['court_case']) in compact(proof['text']), 'refined case lacks explicit proof')
        seen.add(aid)
        facts.append({'event_id': 'NCP-' + digest([doc['source']['raw_sha256'], item['event_type']])[:24].upper(),
                      'symbol': item['symbol'], 'event_type': item['event_type'], 'event_date': fields['decision_date'],
                      'information_available_date': item['information_available_date'], 'source_kind': 'public_reviewed_court_clause',
                      'source_ref': 'cninfo:' + aid, 'evidence_status': 'scoped_primary_clause_reviewed', 'announcement_id': aid,
                      **fields, 'title': doc['title'], 'source_url': doc['source']['url'], 'source_observed_at': doc['source']['observed_at'],
                      'raw_sha256': doc['source']['raw_sha256'], 'text_sha256': doc['text_sha256'], 'source_pages': doc['pages'],
                      'stage_proof': proof, 'reviewed_pages': reviewed_pages, 'discovery_event_id': item['discovery_event_id'],
                      'original_discovery_source_ref': item['original_discovery_source_ref'], 'original_alias_asserted': False})
    positive = {aid for aid, r in reviews.items() if r['stage'] is not None}
    require(seen == positive and len(seen) == counts['positive_scoped_stage_clauses'] and
            len({(r['symbol'], r['event_type']) for r in facts}) == len(facts), 'positive clause frame incomplete or duplicate company stage')
    return {'version': VERSION, 'availability': 'observed', 'facts': facts, 'primary_bound_clauses': len(facts),
            'companies': len({r['symbol'] for r in facts}), 'metadata_responses': len(refs), 'archived_PDFs': len(documents),
            'archived_pages': sum(d['pages'] for d in documents.values()), 'scoped_review_documents': len(reviews),
            'selected_candidates': len(selected), 'selected_rejections': len(set(selected) - seen),
            'extra_related_entity_exclusions': len(set(reviews) - set(selected)), 'unreviewed_extra_attachments': len(set(documents) - set(reviews)),
            'unknown_decision_dates': sum(r['decision_date'] is None for r in facts), 'unknown_receipt_dates': sum(r['receipt_date'] is None for r in facts),
            'stage_counts': dict(Counter(r['event_type'] for r in facts)), 'reviewed_at': ADMISSION['reviewed_at'],
            'profile_sha256': REVIEW_SHA, 'admission_sha256': ADMISSION_SHA, 'historical_PIT': False,
            'full_body_semantics_checked': False, 'P8_gold_validation_completed': False, 'original_alias_identity_asserted': False}


def pool_status(events, p6_run, directory=OUTPUT, now=None):
    base = {'version': VERSION, 'availability': 'missing', 'facts': [], 'historical_PIT': False,
            'full_body_semantics_checked': False, 'P8_gold_validation_completed': False, 'original_alias_identity_asserted': False}
    try:
        return collect(directory, events, p6_run, now or datetime.now(timezone.utc))
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError):
        return {**base, 'availability': 'invalid' if directory.exists() else 'missing'}
