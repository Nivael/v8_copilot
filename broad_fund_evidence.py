"""Supplementary issuer NAVs and explicitly disclosed holders, with separate dates."""
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re

from broad_etf_reading import NAMES, positive
from canonical_json import digest
from etf_announcements import announcement_status
from etf_issuer_nav import NAV_DEFINITIONS, BROAD_NAV_DEFINITIONS, load_issuer_navs
from etf_quarterly import compact, load_report_capture, parse_report, read_bound_report
from settings import DATA_ROOT

ROOT = DATA_ROOT / 'local_data/v8_copilot/market_risk'
OUTPUT = ROOT / 'trader_observations/broad_fund_evidence'
VERSION = 'broad_fund_holder_review_v1'


def number(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d{2}', value):
        raise ValueError('holder shares must retain source decimals')
    return Decimal(value)


def holder_row(entry, pages, report):
    code = entry['code']
    if (code not in NAV_DEFINITIONS or entry['period_start'] != report['period_start']
            or entry['period_end'] != report['period_end'] or report['code'] != code
            or not entry['proof_pages'] or len(set(entry['proof_pages'])) != len(entry['proof_pages'])):
        raise ValueError('holder identity, period or pages changed')
    texts = []
    for page in entry['proof_pages']:
        if (type(page) is not int or not 1 <= page <= len(pages)
                or sha256(pages[page-1].encode()).hexdigest() != entry['page_sha256'].get(str(page))):
            raise ValueError('holder proof page changed')
        texts.append(pages[page-1])
    text = compact(''.join(texts))
    if '报告期内单一投资者持有基金份额比例达到或超过20%的情况' not in text:
        raise ValueError('not the disclosed investor-threshold table')
    base = {'code': code, 'name': NAMES[code], 'kind': entry['holder_kind'],
            'period_start': report['period_start'], 'period_end': report['period_end'],
            'published_on': report['publication_date'],
            'sources': [{'label': f'{NAMES[code]}三季报 · 第{page}页',
                         'url': report['pdf_url'] + '#page=' + str(page)} for page in entry['proof_pages']]}
    if entry['holder_kind'] == 'no_20pct_holder_reported':
        if not any(phrase in text for phrase in ('未有单一投资者持有基金份额比例达到或超过20%',
                    '不存在达到或超过20%的情况', '无需要披露的单一投资者持有基金份额比例达到或超过20%')):
            raise ValueError('missing explicit threshold non-occurrence statement')
        return base
    if entry['holder_kind'] != 'feeder_fund' or '联接' not in entry['holder_label'] or compact(entry['holder_label']) not in text:
        raise ValueError('holder is not the explicitly disclosed feeder')
    fields = ('opening_shares', 'increased_shares', 'decreased_shares', 'closing_shares')
    values = [number(entry[key]) for key in fields]
    if values[0] + values[1] - values[2] != values[3] or values[3] > positive(report['closing_shares']):
        raise ValueError('holder share balance or fund total mismatch')
    at = text.index('报告期内单一投资者持有基金份额比例达到或超过20%的情况')
    at = text.index(compact(entry['holder_label']), at) + len(compact(entry['holder_label']))
    for value in values:
        found = text.find(format(value, ',.2f'), at)
        if found < 0:
            raise ValueError('holder shares absent from source table')
        at = found + len(format(value, ',.2f'))
    pct = number(entry['closing_share_pct'])
    if not 0 < pct <= 100 or text.find(format(pct, '.2f'), at) < 0:
        raise ValueError('holder percentage absent from source table')
    if abs(values[3] / positive(report['closing_shares']) * 100 - pct) > Decimal('0.005'):
        raise ValueError('holder percentage does not match the fund total')
    return {**base, **{key: entry[key] for key in fields}, 'holder_label': entry['holder_label'],
            'closing_share_pct': entry['closing_share_pct'], 'holding_change_shares': str(values[3]-values[0])}


def holders(directory=OUTPUT, *, announcement_root=ROOT/'etf_announcements', now=None):
    now = now or datetime.now(timezone.utc)
    try:
        review = json.loads((directory/'holder_review.json').read_text())
        if (review['version'] != VERSION or digest({k:v for k,v in review.items() if k!='content_digest'}) != review['content_digest']
                or not isinstance(review['entries'], list) or len(review['entries']) != len(NAV_DEFINITIONS)
                or {r['code'] for r in review['entries']} != set(NAV_DEFINITIONS)):
            raise ValueError('holder review changed or incomplete')
        stamp = datetime.fromisoformat(review['reviewed_at'])
        if stamp.tzinfo is None or stamp > now:
            raise ValueError('invalid holder review time')
        announcements = announcement_status(announcement_root, now)
        capture, key = load_report_capture(announcement_root, announcements, now)
        if key != review['capture_digest'] or announcements['content_digest'] != review['catalog_digest']:
            raise ValueError('holder source inventory changed')
        docs = {d['document_id']:d for c in announcements['catalogs'] for d in c['required_documents']}
        rows = []
        for entry in review['entries']:
            doc = docs[entry['document']['document_id']]
            if doc != entry['document'] or capture['documents'][doc['document_id']] != entry['source']:
                raise ValueError('holder document binding changed')
            end = date.fromisoformat(entry['period_end'])
            report = read_bound_report(announcement_root, capture, doc, entry['period_end'],
                                       now.date().isoformat(), lambda pages: parse_report(pages, entry['code'], end.year, (end.month+2)//3))
            pages = json.loads((announcement_root/'document_text'/(report['text_sha256']+'.json')).read_text())['pages']
            rows.append(holder_row(entry, pages, report))
        periods = {(row['period_start'], row['period_end']) for row in rows}
        if len(periods) != 1:
            raise ValueError('holder reports do not share a period')
        start, end = next(iter(periods))
        count = sum(row['kind']=='feeder_fund' and Decimal(row['holding_change_shares'])>0 for row in rows)
        return {'availability':'available', 'period_start':start, 'period_end':end, 'rows':rows,
                'reviewed_at':review['reviewed_at'], 'source_digest':review['content_digest'],
                'headline':f'三季报中，{count}只样本披露联接基金持有份额增加',
                'interpretation':'持有变化依据联接基金季度披露，近期份额按交易日观察。',
                'scope_note':'表格覆盖报告期内达到20%披露阈值的单一投资者，持有变化可包含买卖、转换等。'}
    except (OSError, KeyError, ValueError, TypeError, IndexError):
        return {'availability':'unavailable'}


def navs(broad, *, directory=OUTPUT/'issuer_nav', now=None):
    now = now or datetime.now(timezone.utc)
    meta, source = load_issuer_navs(directory, now)
    if meta['availability'] != 'observed' or meta['through'] != broad['as_of']:
        return {'availability':'unavailable'}
    funds = {fund['code']: fund for group in broad['groups'] for fund in group['funds']}
    try:
        rows = []
        reconciled = {fund['code']: fund for fund in meta['raw_reconciliation']['funds']}
        if set(source) not in (set(NAV_DEFINITIONS),set(BROAD_NAV_DEFINITIONS)):
            raise ValueError('unsupported broad NAV scope')
        for code in source:
            if code not in funds:
                raise ValueError('NAV outside current broad sample')
            points = source[code]
            values = {r['date']: Decimal(r['source_value']) for r in reconciled[code]['records']}
            latest = positive(values[meta['through']])
            shares = funds[code]['five_day_share_change_pct']
            if isinstance(shares,bool) or not Decimal(str(shares)).is_finite():
                raise ValueError('invalid share comparison')
            row = {'code':code, 'name':NAMES[code], 'as_of':meta['through'],
                   'unit_nav':str(latest), 'five_day_share_change_pct':shares,
                   'source_url':BROAD_NAV_DEFINITIONS[code]['url'], 'source_label':BROAD_NAV_DEFINITIONS[code]['label']}
            for days, key in [(5,'five_day_nav_change_pct'), (20,'twenty_day_nav_change_pct')]:
                anchor = points[-days-1]['nav_date']
                row[key] = float((latest/values[anchor]-1)*100)
                row[key.replace('_change_pct','_anchor')] = anchor
            rows.append(row)
        n=len(rows);share_up=sum(r['five_day_share_change_pct']>0 for r in rows);share_down=sum(r['five_day_share_change_pct']<0 for r in rows)
        nav_up=sum(r['five_day_nav_change_pct']>0 for r in rows);nav_down=sum(r['five_day_nav_change_pct']<0 for r in rows)
        longer_down=sum(r['twenty_day_nav_change_pct']<0 for r in rows)
        if share_up==n and nav_up==n:
            headline=f'{n}只样本近5日份额和净值都回升'
            interpretation='份额扩张与价格修复同向，短线承接出现改善。'
        elif share_up==n and nav_down==n:
            headline=f'{n}只样本份额都增加，净值却仍下跌'
            interpretation='有承接迹象，但尚未转成价格修复。'
        elif share_down==n and nav_down==n:
            headline=f'{n}只样本份额与净值同步回落'
            interpretation='样本份额收缩与净值下跌同向，近期都在承压。'
        else:
            headline=f'近5日：{share_up}只份额增加、{share_down}只减少，{nav_up}只净值回升'
            interpretation='份额与价格的方向仍有分化，需逐组看强弱。'
        if longer_down:
            interpretation+=f'{longer_down}只近20日净值仍下跌，'+('短线修复与近月弱势并存。' if nav_up else '较长窗口也仍承压。')
        else:
            interpretation+='近20日净值均未下跌，'+('继续观察修复能否延续。' if nav_up else '仍需观察近期是否转弱。')
        return {'availability':'available', 'as_of':meta['through'], 'fetched_at':meta['fetched_at'],
                'sample_funds':len(funds), 'observed_funds':len(rows), 'sessions':len(meta['calendar']),
                'source_digest':meta['content_digest'], 'rows':rows,'headline':headline,'interpretation':interpretation,
                'basis_note':'单位净值反映每份基金资产的价格，份额反映发行份数。表中比较同窗变化，单位净值按公布值计算。'}
    except (KeyError, ValueError, TypeError, IndexError, InvalidOperation):
        return {'availability':'unavailable'}


def reading(broad, *, directory=OUTPUT, announcement_root=ROOT/'etf_announcements', now=None):
    disclosed = holders(directory,announcement_root=announcement_root,now=now)
    if disclosed['availability']=='available' and any(row['published_on']>broad['as_of'] for row in disclosed['rows']):
        disclosed = {'availability':'unavailable'}
    return {'unit_nav':navs(broad,directory=directory/'issuer_nav',now=now), 'holders':disclosed}
