"""Unify verified document-clause scopes without certifying ETF cash flows or event absence."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
import etf_announcements as catalogs
import etf_document_capture as capture_tools
import etf_quarterly as quarterly
import etf_report_continuity as continuity
import etf_share_events as events
import etf_notice_review as notices
import etf_prospectus_rules as prospectuses
from settings import DATA_ROOT

VERSION = 'etf_selected_document_scoped_review_v1'
PROFILE_PATH = Path(__file__).with_name('etf_review_scope_v1.json')
PROFILE = json.loads(PROFILE_PATH.read_text())
ROOT = DATA_ROOT / 'local_data/v8_copilot/market_risk'
OUTPUT = ROOT / 'etf_review_scope'
DATE = r'(20\d{2})年(\d{1,2})月(\d{1,2})日'
SCOPE_LABELS = {
    'share_event_chain': '历史份额事项链', 'quarterly_share_table': '三季报份额表', 'midyear_share_table': '中报份额表',
    'notice_clause': '持仓证券及服务等条款', 'prospectus_business_clauses': '招募版本业务条款',
    'creation_unit_declaration': '历史每笔申赎单位公告', 'liquidity_service_end': '历史流动性服务终止',
    'creation_redemption_pause': '历史折算相关申赎暂停',
}


def processor_digest():
    return digest({'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                            (Path(__file__), PROFILE_PATH, Path(catalogs.__file__), Path(capture_tools.__file__))},
                   'quarterly': hashlib.sha256(Path(quarterly.__file__).read_bytes()).hexdigest(),
                   'continuity': continuity.parser_digest(), 'events': events.parser_digest(),
                   'notices': notices.parser_digest(), 'prospectuses': prospectuses.parser_digest()})


PROCESSOR = processor_digest()


def iso(text):
    return date(*map(int, re.fullmatch(DATE, text).groups())).isoformat()


def stamp(text, now):
    value = datetime.fromisoformat(text)
    if value.tzinfo is None or value > now: raise ValueError('invalid observation time')
    return value


def one(pattern, text):
    values = list(re.finditer(pattern, text))
    if len(values) != 1: raise ValueError('missing or ambiguous scoped clause')
    return values[0]


def parse_supplement(pages, case):
    normalized = [quarterly.compact(p) for p in pages]; text = ''.join(normalized)
    if (not re.search(r'(?<!\d)' + case['code'][:6] + r'(?!\d)', text)
        or case['fund_name'] not in text or case['issuer'] not in text):
        raise ValueError('wrong fund or issuer in supplemental document')
    for proof in case['proofs']:
        page = proof['page']
        if case['format'] == 'issuer_html':
            if page is not None or len(pages) != 1: raise ValueError('HTML has no physical PDF page')
            page = 1
        elif type(page) is not int or not 1 <= page <= len(pages): raise ValueError('invalid physical proof page')
        if not proof['text'] or proof['text'] != quarterly.compact(proof['text']) or normalized[page-1].count(proof['text']) != 1:
            raise ValueError('supplemental clause changed or is ambiguous')
    roles = [p['role'] for p in case['proofs']]; kind = case['kind']; facts = {}
    if kind == 'creation_unit_declaration':
        explicit = list(re.finditer(r'从(' + DATE + r')起,本基金最小申购、?赎回单位自(\d+)万份调整为(\d+)万份', text))
        if explicit:
            if len(explicit) != 1 or roles != ['dated_per_order_unit']: raise ValueError('ambiguous dated order-unit clause')
            m = explicit[0]; before, after = str(Decimal(m[5])*10000), str(Decimal(m[6])*10000); day = iso(m[1])
        else:
            if roles != ['business_effective_date', 'per_order_unit']: raise ValueError('wrong order-unit clause roles')
            day = iso(one(r'决定自(' + DATE + r')起', text)[1])
            after = str(Decimal(one(r'最小申购、赎回单位调整为(\d+)万份', text)[1])*10000); before = None
        if (case['unit_scope'] != 'minimum_shares_per_creation_redemption_order' or '整数倍' not in text
            or (day, before, after) != (case['announced_effective_on'], case['unit_before_shares'], case['unit_after_shares'])
            or Decimal(after) <= 0 or before is not None and (Decimal(before) <= 0 or before == after)):
            raise ValueError('per-order units cannot be rebound or inferred as fund-total conversion')
        facts.update(unit_before_shares=before, unit_after_shares=after, unit_scope=case['unit_scope'])
    elif kind == 'liquidity_service_end':
        if roles != ['business_effective_date', 'service_provider', 'service_role']: raise ValueError('wrong service roles')
        m = one(r'自(' + DATE + r')起,本公司终止(.+?)为' + re.escape(case['fund_name']), text)
        day, provider = iso(m[1]), m[5]
        if (day != case['announced_effective_on'] or provider != case['provider'] or '提供流动性服务' not in text
            or re.findall(r'(?<!\d)\d{6}(?!\d)', text) != [case['code'][:6]]):
            raise ValueError('service termination is not a different fund or fund termination')
        facts['provider'] = provider
    elif kind == 'creation_redemption_pause':
        if roles != ['creation_pause', 'redemption_pause', 'announced_resume', 'record_date', 'business_code']:
            raise ValueError('wrong pause/date roles')
        create = iso(one(r'暂停申购起始日(' + DATE + ')', text)[1]); redeem = iso(one(r'暂停赎回起始日(' + DATE + ')', text)[1])
        resume = iso(one(r'并于(' + DATE + r')起恢复办理申购和赎回业务', text)[1])
        record = iso(one(r'500ETF将以(' + DATE + r')为权益登记日进行基金份额折算', text)[1])
        business_code = one(r'申购赎回代码为(\d{6})', text)[1]
        if ((create, redeem, resume, record, business_code) != (case['announced_effective_on'], case['announced_effective_on'], case['announced_resume_on'], case['record_on'], case['creation_redemption_code'])
            or not create < resume or business_code == case['code'][:6]):
            raise ValueError('fund identity, business code, pause or resumption date role changed')
        day = create; facts.update(announced_resume_on=resume, record_on=record, creation_redemption_code=business_code, related_event_id=case['related_event_id'])
    else: raise ValueError('unknown supplemental scope')
    if case['published_on'] > day: raise ValueError('unexpected declaration chronology')
    return {**facts, 'announced_effective_on': day, 'implementation_verified': False, 'current_validity_verified': False,
            'fund_total_share_conversion': False, 'market_window_correction_applied': False, 'estimated_net_subscription_yuan': None}


def read_supplement(directory, selected, capture, now, *, full=False):
    rows = []; seen = set()
    for case in PROFILE['cases']:
        key = case['document_id']; doc = selected[key]; item = capture['documents'][key]
        if (key in seen or any(doc[k] != case[k] for k in ('code', 'published_on', 'title', 'url'))
            or item['format'] != case['format'] or item['page_count'] != case['page_count']
            or item['text_sha256'] != case['text_sha256'] or item['responses'][-1]['response_sha256'] != case['raw_sha256']
            or item['responses'][-1]['observed_at'] != case['observed_at']
            or not capture_tools.valid_ready(item, directory, doc, capture['catalog_digest'])):
            raise ValueError('supplemental document binding changed')
        seen.add(key); observed = stamp(case['observed_at'], now)
        if (doc['published_on'] > observed.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
            or observed > stamp(capture['completed_at'], now)):
            raise ValueError('supplemental source was not available when captured')
        payload = json.loads((directory/'document_text'/(item['text_sha256']+'.json')).read_text()); pages = payload['pages']
        if full:
            raw = (directory/'document_raw'/(case['raw_sha256']+'.raw')).read_bytes()
            if case['format'] == 'pdf':
                from pypdf import PdfReader
                if [p.extract_text() for p in PdfReader(BytesIO(raw)).pages] != pages: raise ValueError('PDF text differs from original')
            else:
                data = json.loads(raw); detail = data['results'][0]; ad = parse_qs(urlsplit(doc['url']).query)['adId'][0]
                if (str(data['error_no']) != '0' or len(data['results']) != 1 or detail['ad_id'] != ad
                    or detail['pub_date'] != doc['published_on'] or quarterly.compact(detail['title']) != quarterly.compact(doc['title'])
                    or detail.get('attachment_url') or ['\n'.join(capture_tools.DocumentHTML(detail['content']).parts)] != pages):
                    raise ValueError('issuer HTML identity or body differs from original response')
        facts = parse_supplement(pages, case)
        rows.append({**case, **facts, 'source_url': item['responses'][-1]['url'] if item['format'] == 'pdf' else doc['url']})
    return rows


def reviewed_scopes(views, selected):
    mapped = defaultdict(list)
    def add(row, scope):
        key = row['document_id']
        if key not in selected: raise ValueError('review refers to an unselected document')
        if scope in mapped[key]: raise ValueError('duplicate review scope')
        mapped[key].append(scope)
    q, c, e, n, p = (views[k] for k in ('quarterly', 'continuity', 'events', 'notices', 'prospectuses'))
    if (q['availability'] != 'observed' or c['availability'] != 'observed'
        or any(v['availability'] != 'partial' or v.get('failures') for v in (e,n,p))):
        raise ValueError('one or more declared review scopes are unavailable')
    for row in q['reports']:
        if row['availability'] != 'observed': raise ValueError('unverified quarterly report')
        add(row, 'quarterly_share_table')
    for row in c['reports']:
        if row['midyear_report']['availability'] != 'observed': raise ValueError('unverified midyear report')
        add(row['midyear_report'], 'midyear_share_table')
    for event in e['events']:
        for row in event['documents']: add(row, 'share_event_chain')
    for row in n['notices']: add(row, 'notice_clause')
    for row in p['versions']:
        if row['availability'] != 'observed': raise ValueError('unverified prospectus version')
        add(row, 'prospectus_business_clauses')
    return dict(mapped)


def collect_inputs(*, root=ROOT, now=None, full=False):
    now = now or datetime.now(timezone.utc); directory = root/'etf_announcements'
    a = catalogs.announcement_status(directory, now)
    if (a['availability'] != 'observed' or a.get('fulltext',{}).get('availability') != 'observed'
        or a['content_digest'] != PROFILE['catalog_digest'] or a['fulltext']['content_digest'] != PROFILE['capture_digest']
        or (a['window_start'], a['window_end']) != (PROFILE['window_start'], PROFILE['window_end'])):
        raise ValueError('catalog/capture source or window changed')
    capture, _ = quarterly.load_report_capture(directory, a, now)
    docs = [d for cat in a['catalogs'] for d in cat['required_documents']]; selected = {d['document_id']: d for d in docs}
    if len(selected) != len(docs): raise ValueError('duplicate selected document')
    for key, doc in selected.items():
        item = capture['documents'][key]
        if not capture_tools.valid_ready(item, directory, doc, a['content_digest']): raise ValueError('selected source bytes changed')
    q = quarterly.quarterly_status(directory, a, [], PROFILE['window_end'], now)
    views = {'quarterly': q, 'continuity': continuity.report_continuity_status(directory, a, q, now),
             'events': events.share_event_status(directory, a, now), 'notices': notices.notice_review_status(directory, a, now),
             'prospectuses': prospectuses.prospectus_rule_status(directory, a, now)}
    mapped = reviewed_scopes(views, selected)
    supplemental = read_supplement(directory, selected, capture, now, full=full)
    for item in supplemental:
        key = item['document_id']
        if key in mapped: raise ValueError('supplement is not a remaining document')
        mapped[key] = [item['kind']]
        if item['kind'] == 'creation_redemption_pause':
            linked = [r for r in views['events']['events'] if r['event_id'] == item['related_event_id']]
            if (len(linked) != 1 or linked[0]['code'] != item['code'] or linked[0]['record_date'] != item['record_on']
                or not item['announced_effective_on'] <= linked[0]['event_date'] < item['announced_resume_on']):
                raise ValueError('pause does not corroborate the existing conversion dates')
            item['related_event_date'] = linked[0]['event_date']
    if set(mapped) != set(selected): raise ValueError('a selected document still lacks a verified review scope')
    proof_pages = {}
    for row in q['reports']: proof_pages[row['document_id']] = [row['table_page']]
    for row in views['continuity']['reports']: proof_pages[row['midyear_report']['document_id']] = [row['midyear_report']['table_page']]
    for event in views['events']['events']:
        for row in event['documents']: proof_pages[row['document_id']] = row['pages']
    for row in views['notices']['notices']: proof_pages[row['document_id']] = row['evidence_pages']
    for row in views['prospectuses']['versions']: proof_pages[row['document_id']] = row['reviewed_pages']
    for row in supplemental: proof_pages[row['document_id']] = sorted({p['page'] for p in row['proofs'] if p['page'] is not None})
    for key, item in capture['documents'].items():
        if key not in selected: continue
        if item['format'] == 'issuer_html': proof_pages[key] = []
        elif (not proof_pages[key] or any(type(p) is not int or not 1 <= p <= item['page_count'] for p in proof_pages[key])):
            raise ValueError('review page is not a physical page in the bound PDF')
    sources = [{**doc, 'review_scopes': mapped[key], 'format': capture['documents'][key]['format'],
                'page_count': capture['documents'][key]['page_count'], 'raw_sha256': capture['documents'][key]['responses'][-1]['response_sha256'],
                'reviewed_pages': proof_pages[key], 'source_url': capture['documents'][key]['responses'][-1]['url'] if capture['documents'][key]['format']=='pdf' else doc['url'],
                'observed_at': capture['documents'][key]['responses'][-1]['observed_at']} for key,doc in selected.items()]
    return {'documents': sources, 'supplemental': supplemental, 'views': views, 'catalog_digest': a['content_digest'],
            'capture_digest': a['fulltext']['content_digest'], 'publication_cutoff': a['through'], 'capture_completed_at': capture['completed_at']}


def project(inputs):
    docs = inputs['documents']; supplemental = inputs['supplemental']; pdfs = [d for d in docs if d['format'] == 'pdf']
    originals = {d['raw_sha256']: d for d in pdfs}; groups = defaultdict(list)
    for d in supplemental:
        if d['kind'] == 'creation_unit_declaration': groups[(d['code'],d['announced_effective_on'],d['unit_before_shares'],d['unit_after_shares'])].append(d['document_id'])
    by_day = defaultdict(set)
    for code, day, before, after in groups: by_day[(code,day)].add((before,after))
    if any(len(values)>1 for values in by_day.values()): raise ValueError('conflicting per-order unit declarations for the same business date')
    counts = Counter(scope for d in docs for scope in d['review_scopes'])
    return {'availability': 'scoped_reviewed', 'window_start': PROFILE['window_start'], 'window_end': PROFILE['window_end'],
            'publication_cutoff': inputs['publication_cutoff'], 'catalog_digest': inputs['catalog_digest'], 'capture_digest': inputs['capture_digest'],
            'selected_document_items': len(docs), 'items_with_scoped_review': len(docs), 'items_without_scoped_review': 0,
            'all_selected_items_have_scoped_review': True, 'scope_counts': dict(counts), 'scope_labels': SCOPE_LABELS,
            'pdf_items': len(pdfs), 'distinct_pdf_originals': len(originals), 'pdf_pages_by_item': sum(d['page_count'] for d in pdfs),
            'distinct_pdf_pages': sum(d['page_count'] for d in originals.values()), 'issuer_html_items': len(docs)-len(pdfs),
            'documents': docs, 'supplemental_documents': supplemental, 'supplemental_items': len(supplemental),
            'supplemental_counts': dict(Counter(d['kind'] for d in supplemental)), 'creation_unit_groups': [
                {'code': key[0], 'announced_effective_on': key[1], 'unit_before_shares': key[2], 'unit_after_shares': key[3], 'document_ids': ids}
                for key,ids in sorted(groups.items())], 'distinct_creation_unit_declarations': len(groups),
            'duplicate_unit_reminders': sum(len(ids)-1 for ids in groups.values()),
            'full_document_semantics_checked': False, 'all_window_share_events_verified': False, 'corporate_actions_checked': False,
            'daily_share_scope_verified': False, 'share_precision_verified': False, 'final_revision_verified': False,
            'estimated_net_subscription_yuan': None, 'historical_PIT': False, 'effect_measured': False,
            'capture_completed_at': inputs['capture_completed_at'],
            'note': '每个选中文档项均有已列范围的原文依据，不代表通读全部正文或全窗份额事件已验收。历史每笔申赎单位、服务终止和申赎暂停分别核对；未知原单位不从旧文推算，重复提示不新增事项。日份额范围/精度、最新修订及全窗事件仍待核，净申赎金额保持未发布，不能识别资金身份。'}


def scope_status(directory=OUTPUT, *, root=ROOT, now=None):
    now = now or datetime.now(timezone.utc)
    base = {'version': VERSION, 'availability': 'missing', 'documents': [], 'supplemental_documents': [],
            'all_selected_items_have_scoped_review': False, 'full_document_semantics_checked': False,
            'all_window_share_events_verified': False, 'corporate_actions_checked': False, 'estimated_net_subscription_yuan': None,
            'daily_share_scope_verified': False, 'share_precision_verified': False, 'final_revision_verified': False,
            'historical_PIT': False, 'effect_measured': False}
    if processor_digest() != PROCESSOR: return {**base,'availability':'reload_required'}
    try:
        raw = json.loads((directory/'current.json').read_text()); then = stamp(raw['materialized_at'], now)
        if (raw['version'] != VERSION or raw['processor_digest'] != PROCESSOR
            or digest({k:v for k,v in raw.items() if k != 'content_digest'}) != raw['content_digest']):
            raise ValueError('review scope snapshot binding changed')
        inputs = collect_inputs(root=root, now=then)
        if digest(inputs) != raw['input_digest']: raise ValueError('review scope inputs changed')
        if processor_digest() != PROCESSOR: return {**base,'availability':'reload_required'}
        return {**base, **project(inputs), 'content_digest': raw['content_digest'], 'materialized_at': raw['materialized_at']}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, ArithmeticError):
        return {**base,'availability':'invalid' if (directory/'current.json').exists() else 'missing'}


def materialize(*, directory=OUTPUT, root=ROOT, now=None):
    now = now or datetime.now(timezone.utc)
    if processor_digest() != PROCESSOR: raise ValueError('reload changed code')
    path = directory/'current.json'
    if path.exists() and json.loads(path.read_text()).get('version') != VERSION: raise ValueError('foreign output')
    inputs = collect_inputs(root=root, now=now, full=True); report = project(inputs)
    raw = {'version':VERSION, 'processor_digest':PROCESSOR, 'input_digest':digest(inputs), 'materialized_at':now.isoformat()}
    rechecked = collect_inputs(root=root, now=now)
    if digest(rechecked) != raw['input_digest'] or processor_digest() != PROCESSOR: raise ValueError('review source or code changed')
    raw['content_digest'] = digest(raw); atomic_write_json(directory/'snapshots'/(raw['content_digest']+'.json'), raw); atomic_write_json(path, raw)
    return {k: report[k] for k in ('availability','selected_document_items','items_with_scoped_review','supplemental_items','scope_counts','distinct_creation_unit_declarations')}


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args(); print(json.dumps(materialize(),ensure_ascii=False))
