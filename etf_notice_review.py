"""Read closed primary-source notice facts, preserving asset units and repeat disclosures."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from canonical_json import digest
from etf_document_capture import valid_ready
from etf_notice_profiles import NOTICE_CASES
from etf_quarterly import NUMBER, amount, compact, decimal_text, load_report_capture

VERSION = "etf_notice_fact_review_v1"
CATEGORIES = {'portfolio_allocation', 'private_placement', 'listing_valuation_risk', 'creation_redemption_agent', 'liquidity_provider'}
FUND_NAMES = {
    '510300.SH': '华泰柏瑞沪深300交易型开放式指数证券投资基金',
    '510310.SH': '易方达沪深300交易型开放式指数发起式证券投资基金',
    '510330.SH': '华夏沪深300交易型开放式指数证券投资基金',
    '510500.SH': '中证500交易型开放式指数证券投资基金',
    '512100.SH': '南方中证1000交易型开放式指数证券投资基金',
}


def parser_digest():
    root = Path(__file__).parent
    return digest({name: hashlib.sha256((root/name).read_bytes()).hexdigest()
                   for name in (Path(__file__).name, 'etf_notice_profiles.py', 'etf_quarterly.py')})


PARSER_DIGEST = parser_digest()


def evidence_pages(case):
    records = [case['purpose']]
    records += [case[key] for key in ('context', 'risk_evidence') if key in case]
    for row in case['allocations']: records += [row['unit_evidence'], row['row_evidence']]
    if case.get('service'):
        records.append(case['service']['row_evidence'])
        if case['service'].get('provider_evidence'): records.append(case['service']['provider_evidence'])
    return records


def iso(value):
    match = re.fullmatch(r'(\d{4})年(\d{1,2})月(\d{1,2})日', value)
    if not match: raise ValueError('invalid reviewed date')
    return date(*map(int, match.groups())).isoformat()


def parse_reviewed_notice(pages, case):
    """Return only listed, byte-bound clauses/rows; this is not an absence scan."""
    if case['category'] not in CATEGORIES or not pages or any(not isinstance(page, str) for page in pages):
        raise ValueError('unknown notice scope')
    normalized = [compact(page) for page in pages]
    for item in evidence_pages(case):
        page = item['page']
        if (type(page) is not int or not 1 <= page <= len(pages) or not item['text']
            or normalized[page-1].count(item['text']) != 1): raise ValueError('changed or ambiguous reviewed clause')
    allocations = []
    for row in case['allocations']:
        if row['asset_unit'] not in ('stock_share', 'bond_piece'): raise ValueError('not a portfolio security unit')
        expected_unit = '股' if row['asset_unit'] == 'stock_share' else '张'
        if (row['unit_evidence']['text'] not in (f'获配数量({expected_unit})', f'认购数量({expected_unit})')
            or row['unit_evidence']['page'] > row['row_evidence']['page']
            or row['fund_name'] != FUND_NAMES.get(case['code']) or row['fund_name'] not in row['row_prefix'] or '联接' in row['row_prefix']
            or row['row_evidence']['text'] != row['row_prefix']+row['quantity_source']+row['amount_source']+row['row_suffix']):
            raise ValueError('row identity, values or units differ')
        if row['issuer'].removesuffix('可转债') not in case['purpose']['text']+row['row_evidence']['text']:
            raise ValueError('unbound portfolio security issuer')
        if (not re.fullmatch(NUMBER, row['quantity_source']) or not re.fullmatch(NUMBER, row['amount_source'])
            or '.' in row['quantity_source'] or min(amount(row['quantity_source']), amount(row['amount_source'])) <= 0):
            raise ValueError('invalid portfolio allocation values')
        allocations.append({'issuer': row['issuer'], 'asset_unit': row['asset_unit'],
                            'quantity': decimal_text(amount(row['quantity_source'])),
                            'amount_yuan': decimal_text(amount(row['amount_source'])), 'table_page': row['row_evidence']['page']})
    result = {'category': case['category'], 'allocations': allocations, 'fund_share_change_verified': False,
              'full_document_semantics_checked': False, 'evidence_pages': sorted({item['page'] for item in evidence_pages(case)})}
    if case.get('context'):
        result['reference_description'] = case['context']['text']
    if case['category'] == 'listing_valuation_risk':
        if (len(allocations) != 1 or allocations[0]['asset_unit'] != 'stock_share'
            or case['listing_on'] not in case['purpose']['text'] or 'IOPV' not in case['risk_evidence']['text']
            or case['nav_reference_on'] not in case['context']['text']
            or not re.fullmatch(r'\d+\.\d{2}%', case['reported_weight_text'])
            or not case['allocations'][0]['row_suffix'].startswith(case['reported_weight_text'])):
            raise ValueError('unbound listing, valuation reference or rounded weight')
        result.update(listing_on=iso(case['listing_on']), nav_reference_on=iso(case['nav_reference_on']),
                      reported_weight_text=case['reported_weight_text'], risk_clause=case['risk_evidence']['text'])
    elif case['category'] in ('creation_redemption_agent', 'liquidity_provider'):
        service = case['service']
        provider_evidence = service.get('provider_evidence', service['row_evidence'])['text']
        if (allocations or service['provider'] not in provider_evidence or service['effective_on'] not in case['purpose']['text']
            or service['role'] not in case['purpose']['text'] or case['code'][:6] not in service['row_evidence']['text']):
            raise ValueError('unbound service provider or date')
        result['service'] = {key: service[key] for key in ('role', 'provider')}
        result['service']['effective_on'] = iso(service['effective_on'])
    elif not allocations: raise ValueError('missing reviewed allocation row')
    return result


def repeated_allocations(notices):
    groups = defaultdict(list)
    for notice in notices:
        for row in notice['allocations']:
            # Only a reviewed IPO allocation and its listing-day disclosure can
            # form a repeat group; placements, bonds and arbitrary equal amounts
            # do not establish the same issue or an additional cash flow.
            if notice['category'] not in ('portfolio_allocation', 'listing_valuation_risk') or row['asset_unit'] != 'stock_share': continue
            key = (notice['code'], row['issuer'], row['quantity'], row['amount_yuan'])
            groups[key].append(notice)
    return [{'code': key[0], 'issuer': key[1], 'quantity': key[2], 'amount_yuan': key[3],
             'document_ids': [row['document_id'] for row in rows], 'not_additional_subscription_flow': True}
            for key, rows in sorted(groups.items()) if len(rows) == 2
            and {row['category'] for row in rows} == {'portfolio_allocation', 'listing_valuation_risk'}]


def notice_review_status(directory: Path, announcements: dict, now: datetime) -> dict:
    base = {'version': VERSION, 'availability': 'missing', 'notices': [], 'reviewed_notices': 0, 'reviewed_funds': 0,
            'catalog_window_start': announcements.get('window_start'), 'catalog_window_end': announcements.get('window_end'),
            'window_selected_documents': None, 'window_documents_outside_this_review': None, 'repeat_disclosure_groups': [],
            'category_counts': {}, 'corporate_actions_checked': False, 'all_window_documents_reconciled': False,
            'note': '本项只核对所列正文段落、表头与目标基金行。持仓证券获配的股/张、服务安排及新股估值提示分开；不计作ETF份额申赎，也不证明整篇或整个公告筛选窗没有其他份额事项。'}
    if parser_digest() != PARSER_DIGEST: return {**base, 'availability': 'reload_required'}
    if announcements.get('availability') != 'observed' or announcements.get('fulltext', {}).get('availability') != 'observed': return base
    try:
        capture, capture_digest = load_report_capture(directory, announcements, now)
        docs = [doc for catalog in announcements['catalogs'] for doc in catalog['required_documents']]
        selected = {doc['document_id']: doc for doc in docs}
        if len(selected) != len(docs): raise ValueError('duplicate notice document')
        window = {key: doc for key, doc in selected.items() if announcements['window_start'] <= doc['published_on'] <= announcements['window_end']}
    except (OSError, ValueError, TypeError, KeyError): return {**base, 'availability': 'invalid'}
    notices, failures = [], []
    for case in NOTICE_CASES:
        try:
            document = window[case['document_id']]; result = capture['documents'][case['document_id']]
            observed = datetime.fromisoformat(result['responses'][-1]['observed_at'])
            if (document['code'] != case['code'] or document['published_on'] != case['published_on']
                or result['text_sha256'] != case['text_sha256'] or result['format'] != 'pdf'
                or result['responses'][-1]['response_sha256'] != case['raw_sha256']
                or not valid_ready(result, directory, document, capture['catalog_digest'])
                or observed.tzinfo is None or observed > datetime.fromisoformat(capture['completed_at'])
                or observed.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat() < document['published_on']):
                raise ValueError('notice bytes, identity or availability changed since review')
            pages = json.loads((directory/'document_text'/f"{result['text_sha256']}.json").read_text())['pages']
            notice = parse_reviewed_notice(pages, case)
            notice.update(document_id=document['document_id'], code=document['code'], title=document['title'],
                          published_on=document['published_on'], observed_at=result['responses'][-1]['observed_at'],
                          url=result['responses'][-1]['url'], raw_sha256=case['raw_sha256'], text_sha256=case['text_sha256'])
            notices.append(notice)
        except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError):
            failures.append({'document_id': case['document_id'], 'code': case['code'], 'reason': 'reviewed_source_or_facts_changed'})
    return {**base, 'availability': 'partial' if notices else 'invalid', 'notices': sorted(notices, key=lambda row: (row['published_on'], row['code'], row['document_id']), reverse=True),
            'reviewed_notices': len(notices), 'reviewed_funds': len({row['code'] for row in notices}),
            'distinct_original_pdfs': len({row['raw_sha256'] for row in notices}), 'category_counts': dict(Counter(row['category'] for row in notices)),
            'window_selected_documents': len(window), 'window_documents_outside_this_review': len(window)-len(notices),
            'repeat_disclosure_groups': repeated_allocations(notices), 'failures': failures,
            'catalog_digest': announcements['content_digest'], 'capture_digest': capture_digest, 'parser_digest': PARSER_DIGEST}
