"""Verify security identity and member-status clauses for a fixed SSE notice catalog."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from settings import DATA_ROOT

VERSION = 'sse_ST_member_status_clause_review_v1'
PROFILE_PATH = Path(__file__).with_name('sse_st_notice_review_v1.json')
CATALOG_PATH = Path(__file__).with_name('sse_st_catalog_triage_v1.json')
TRANSITIONS_PATH = Path(__file__).with_name('sse_st_transitions_v1.json')
PROFILE = json.loads(PROFILE_PATH.read_text())
CATALOG = json.loads(CATALOG_PATH.read_text())
TRANSITIONS = json.loads(TRANSITIONS_PATH.read_text())['events']
OUTPUT = DATA_ROOT / 'local_data/v8_copilot/market_risk/sse_st_notice_review'
LOOKUP = 'https://www.cninfo.com.cn/new/information/topSearch/query'
QUERY = 'https://www.cninfo.com.cn/new/hisAnnouncement/query'
KINDS = ('warning_added', 'warning_removed', 'application_pending', 'layered_warning_existing_member', 'existing_warning_described')


def processor_digest():
    return digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                   (Path(__file__), PROFILE_PATH, CATALOG_PATH, TRANSITIONS_PATH)})


PROCESSOR = processor_digest()


def compact(value):
    return re.sub(r'\s+', '', value)


def stamp(value, now):
    observed = datetime.fromisoformat(value)
    if observed.tzinfo is None or observed > now:
        raise ValueError('missing timezone or future observation')
    return observed


def original(folder, ref, now):
    stamp(ref['observed_at'], now)
    raw = (folder / (ref['sha256'] + '.json')).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref['sha256'] or len(raw) != ref['bytes']:
        raise ValueError('original catalog bytes changed')
    return json.loads(raw)


def read_catalogs(folder, now):
    ref = CATALOG['source_ref']; source = original(folder, ref, now)
    if (ref['url'] != 'https://query.sse.com.cn/security/stock/queryCompanyBulletinNew.do'
        or ref['params']['TITLE'] != '风险警示' or ref['params']['SECURITY_CODE'] != ''
        or (ref['params']['START_DATE'], ref['params']['END_DATE']) != (PROFILE['scope_start'], PROFILE['through'])):
        raise ValueError('SSE catalog scope changed')
    rows = [row for group in source['result'] for row in group]
    if (source['pageHelp']['pageCount'] != 1 or source['pageHelp']['total'] != len(rows)
        or len(rows) != len(CATALOG['items']) or len(rows) != PROFILE['catalog_items']):
        raise ValueError('SSE catalog is incomplete')
    for raw, row in zip(rows, CATALOG['items'], strict=True):
        if (raw['SECURITY_CODE'], raw['SSEDATE'], raw['TITLE'], 'https://www.sse.com.cn' + raw['URL']) != (
            row['symbol'], row['published_on'], row['title'], row['catalog_url']):
            raise ValueError('SSE catalog row changed')
    codes = {r['symbol'] for r in CATALOG['items']}; lookups = {}; reports = {}
    for ref in PROFILE['metadata_refs']:
        data = original(folder, ref, now); params = ref['params']
        if ref['method'] != 'POST': raise ValueError('metadata request method changed')
        if ref['url'] == LOOKUP:
            code = params['keyWord']
            if params != {'keyWord': code, 'maxNum': '10'} or code not in codes or code in lookups:
                raise ValueError('lookup identity/scope changed')
            matches = [r for r in data if r['code'] == code]
            if len(matches) != 1: raise ValueError('ambiguous company lookup')
            lookups[code] = matches[0]['orgId']
        elif ref['url'] == QUERY:
            code, org = params['stock'].split(',')
            expected = {'pageNum': '1', 'pageSize': '100', 'column': 'sse', 'tabName': 'fulltext', 'plate': 'sh',
                        'stock': code + ',' + org, 'searchkey': '风险警示', 'secid': '', 'category': '', 'trade': '',
                        'seDate': PROFILE['scope_start'] + '~' + PROFILE['through'], 'sortName': '', 'sortType': '', 'isHLtitle': 'true'}
            records = data['announcements']
            if (params != expected or code not in codes or code in reports or data['hasMore'] is not False
                or data['totalAnnouncement'] != len(records) or any(r['secCode'] != code or r['orgId'] != org for r in records)):
                raise ValueError('CNINFO catalog scope, paging or identity changed')
            reports[code] = (org, records)
        else: raise ValueError('foreign metadata endpoint')
    if set(lookups) != codes or set(reports) != codes or any(lookups[c] != reports[c][0] for c in codes):
        raise ValueError('company-bound metadata catalogs are incomplete')
    records = [r for _, rows in reports.values() for r in rows]
    if len({str(r['announcementId']) for r in records}) != len(records): raise ValueError('duplicate catalog notice')
    return records


def verify_roles(item):
    kind = item['kind']; proofs = item['proofs']; roles = [p['role'] for p in proofs]
    warning_name = bool(re.fullmatch(r'S?\*?ST.+', item['name_as_reported'], re.I))
    if kind not in KINDS or not proofs or len({(p['page'], p['text']) for p in proofs}) != len(proofs):
        raise ValueError('unknown/duplicate member-status clause')
    if kind in ('warning_added', 'warning_removed'):
        matches = [e for e in TRANSITIONS if (e['symbol'], e['published_on']) == (item['symbol'], item['published_on'])]
        if len(matches) != 1 or roles != ['effective_date', 'name_direction']: raise ValueError('unbound effective transition')
        event = matches[0]
        for key in ('kind', 'effective_on', 'source_url', 'raw_sha256', 'text_sha256'):
            if item[key] != event[key]: raise ValueError('effective transition differs from reviewed original')
        d = date.fromisoformat(event['effective_on']); token = f'{d.year}年{d.month}月{d.day}日'
        direction = r'(?:股票|证券)简称[:：]?由[“"]?' + re.escape(event['old_name']) + r'[”"]?变更为[“"]?' + re.escape(event['new_name']) + r'[”"]?'
        if (proofs[0]['text'] != event['date_label'] + '：' + token or not re.fullmatch(direction, proofs[1]['text'])
            or warning_name != (kind == 'warning_removed') or item['name_as_reported'] != event['old_name']):
            raise ValueError('effective date role or name direction changed')
        return
    if not warning_name or item['effective_on'] is not None: raise ValueError('non-effective clause cannot change membership')
    if kind == 'application_pending':
        if roles != ['approval_pending'] or '撤销' not in proofs[0]['text'] or '不确定性' not in proofs[0]['text']:
            raise ValueError('approval application is not an effective removal')
    elif kind == 'layered_warning_existing_member':
        if roles != ['prior_warning', 'layered_warning'] or '叠加实施退市风险警示' not in proofs[1]['text']:
            raise ValueError('layered warning is not a new member')
    elif roles not in (['prior_warning'], ['continuation_statement']): raise ValueError('existing warning role changed')
    prior = next((p['text'] for p in proofs if p['role'] == 'prior_warning'), None)
    if prior and (any(t in prior for t in ('申请', '可能', '若', '拟', '披露的', '将')) or '实施' not in prior or '风险警示' not in prior):
        raise ValueError('a forecast or cited title is not a prior-warning statement')
    since = item['stated_since_on']
    if since:
        day = date.fromisoformat(since); token = f'{day.year}年{day.month}月{day.day}日'
        if not prior or since > item['published_on'] or not re.search(re.escape(token) + r'.{0,16}实施.{0,8}风险警示', prior):
            raise ValueError('historical warning date role changed')
    if roles == ['continuation_statement'] and not re.fullmatch(r'公司股票将继续被实施退市风险警示及其他风险警示', proofs[0]['text']):
        raise ValueError('continuation statement changed')


def collect_inputs(directory=OUTPUT, *, now=None, full=False):
    now = now or datetime.now(timezone.utc)
    records = read_catalogs(directory / 'catalogs', now)
    indexed = {(r['secCode'], r['adjunctUrl'].split('/')[1], str(r['announcementId'])): r for r in records}
    expected = {(r['symbol'], r['published_on'], str(r['announcement_id'])) for r in PROFILE['events']}
    if len(expected) != PROFILE['catalog_items'] or set(indexed) != expected:
        raise ValueError('review and CNINFO catalog do not cover the same notice set')
    if [(r['symbol'], r['published_on'], r['title'], r['catalog_url']) for r in PROFILE['events']] != [
        (r['symbol'], r['published_on'], r['title'], r['catalog_url']) for r in CATALOG['items']]:
        raise ValueError('review and SSE catalog mapping changed')
    result = []
    for item in PROFILE['events']:
        record = indexed[(item['symbol'], item['published_on'], str(item['announcement_id']))]
        if (re.sub('<[^>]+>', '', record['announcementTitle']) != item['cninfo_title']
            or record['orgId'] != item['org_id'] or 'https://static.cninfo.com.cn/' + record['adjunctUrl'] != item['source_url']):
            raise ValueError('primary-notice mapping changed')
        raw = (directory / 'documents' / (item['raw_sha256'] + '.pdf')).read_bytes()
        text = (directory / 'documents' / (item['text_sha256'] + '.json')).read_bytes()
        observed = stamp(item['observed_at'], now)
        if (not raw.startswith(b'%PDF-') or hashlib.sha256(raw).hexdigest() != item['raw_sha256']
            or hashlib.sha256(text).hexdigest() != item['text_sha256'] or len(raw) != item['raw_bytes'] or len(text) != item['text_bytes']
            or not re.fullmatch(r'https://static\.cninfo\.com\.cn/finalpage/' + item['published_on'] + r'/\d+\.PDF', item['source_url'])
            or date.fromisoformat(item['published_on']) > observed.astimezone(ZoneInfo('Asia/Shanghai')).date()):
            raise ValueError('notice original bytes or publication/observation chronology changed')
        pages = json.loads(text)['pages']
        if len(pages) != item['page_count'] or not pages or any(not isinstance(p, str) or not p.strip() for p in pages):
            raise ValueError('notice pages are incomplete')
        first = compact(pages[0]); codes = re.findall(r'(?:证券|股票)代码[:：](\d{6})', first)
        name = re.search(r'(?:证券|股票)简称[:：](.*?)(?:公告编号|编号|证券代码|股票代码|债券代码|转债代码)', first)
        if item['symbol'] not in codes or item['company'] not in first or not name or name[1] != item['name_as_reported']:
            raise ValueError('notice security/company/name identity changed')
        for proof in item['proofs']:
            page, clause = proof['page'], proof['text']
            if (type(page) is not int or not 1 <= page <= len(pages) or not clause or clause != compact(clause)
                or clause not in compact(pages[page-1])):
                raise ValueError('member-status clause or physical page changed')
        verify_roles(item)
        if full:
            from pypdf import PdfReader
            if [p.extract_text() for p in PdfReader(BytesIO(raw)).pages] != pages:
                raise ValueError('extracted text differs from original PDF')
        result.append(dict(item))
    return {'items': result, 'metadata_refs': PROFILE['metadata_refs'], 'sse_catalog_ref': CATALOG['source_ref']}


def project(inputs):
    items = inputs['items']; counts = Counter(r['kind'] for r in items)
    return {'availability': 'reviewed', 'review_scope': 'security_identity_and_member_status_clauses_only',
            'start': PROFILE['scope_start'], 'through': PROFILE['through'], 'latest_publication': max(r['published_on'] for r in items),
            'catalog_items': len(items), 'reviewed_items': len(items), 'distinct_companies': len({r['symbol'] for r in items}),
            'pdf_pages': sum(r['page_count'] for r in items), 'counts': {k: counts[k] for k in KINDS}, 'items': items,
            'newest_document_observed_at': max((r['observed_at'] for r in items), key=datetime.fromisoformat),
            'metadata_observed_at': max((r['observed_at'] for r in inputs['metadata_refs']), key=datetime.fromisoformat),
            'full_body_semantics_reviewed': False, 'full_window_membership_certificate': False,
            'historical_membership_verified': False, 'historical_PIT': False, 'combined_ST_ready': False, 'effect_measured': False,
            'note': '已对固定目录内各项的证券身份及成员状态条款核对原PDF、物理页和巨潮对应公告。申请仍待批准；既有警示/叠加原因不新增成员事件，实际生效沿用原依据。范围仅这些目录项及相关条款，未声称全文语义全部审阅、所有公司公告检索完整或逐日法定ST名单已核验；不提升历史当时可见、完整ST或风险效果门槛。'}


def review_status(directory=OUTPUT, *, now=None):
    now = now or datetime.now(timezone.utc)
    base = {'version': VERSION, 'availability': 'missing', 'items': [], 'full_body_semantics_reviewed': False,
            'full_window_membership_certificate': False, 'historical_membership_verified': False,
            'historical_PIT': False, 'combined_ST_ready': False, 'effect_measured': False}
    if processor_digest() != PROCESSOR: return {**base, 'availability': 'reload_required'}
    try:
        raw = json.loads((directory / 'current.json').read_text()); then = stamp(raw['materialized_at'], now)
        if (raw['version'] != VERSION or raw['processor_digest'] != PROCESSOR
            or digest({k:v for k,v in raw.items() if k != 'content_digest'}) != raw['content_digest']):
            raise ValueError('notice review snapshot changed')
        inputs = collect_inputs(directory, now=then)
        if digest(inputs) != raw['input_digest']: raise ValueError('notice review sources changed')
        if processor_digest() != PROCESSOR: return {**base, 'availability': 'reload_required'}
        return {**base, **project(inputs), 'content_digest': raw['content_digest'], 'materialized_at': raw['materialized_at']}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, ArithmeticError):
        return {**base, 'availability': 'invalid' if (directory / 'current.json').exists() else 'missing'}


def materialize(directory=OUTPUT, *, now=None):
    now = now or datetime.now(timezone.utc)
    if processor_digest() != PROCESSOR: raise ValueError('reload changed code')
    path = directory / 'current.json'
    if path.exists() and json.loads(path.read_text()).get('version') != VERSION: raise ValueError('foreign output')
    inputs = collect_inputs(directory, now=now, full=True); report = project(inputs)
    raw = {'version': VERSION, 'processor_digest': PROCESSOR, 'input_digest': digest(inputs), 'materialized_at': now.isoformat()}
    rechecked = collect_inputs(directory, now=now)
    if digest(rechecked) != raw['input_digest'] or processor_digest() != PROCESSOR:
        raise ValueError('notice sources or processor changed')
    raw['content_digest'] = digest(raw)
    atomic_write_json(directory / 'snapshots' / (raw['content_digest'] + '.json'), raw); atomic_write_json(path, raw)
    return {k:report[k] for k in ('availability', 'reviewed_items', 'distinct_companies', 'pdf_pages', 'counts')}


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args(); print(json.dumps(materialize(), ensure_ascii=False))
