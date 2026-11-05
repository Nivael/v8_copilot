"""Primary issuer distribution/split tables, with errors and empty tables kept unknown."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
import gzip
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from etf_issuer_nav import NAV_DEFINITIONS
from etf_nav_refresh import NAVTable
from etf_szse_history import archive_response
from settings import DATA_ROOT

VERSION = 'issuer_etf_action_tables_v1'
DEFAULT_OUTPUT = DATA_ROOT/'local_data/v8_copilot/market_risk/issuer_action_history'
EF_API = 'https://api.efunds.com.cn/xcowch/front/fundShareBonus/list'
NF_API = 'https://www.nffund.com/nfwebApi/fund/dividends'
JS_API = 'https://www.jsfund.cn/servlet/json'
EF_DIVIDEND_GRAMMAR_SHA256 = '98400360f83d8e4bf1e63335a8ca9a80f4714c10b642e8779cef3ab7ea6806fa'
PROOFS = {
    'efunds_page': ('https://www.efunds.com.cn/fund/510310.shtml', None),
    'nf_page': ('https://www.nffund.com/main/nffund/personal-financing/detail.shtml?fundCode=510500', None),
    'nf_html': ('https://www.nffund.com/main/nffund/js/personal-financing/html.js', 'be483e83a579440479b09e73b899c708beaa74f8894928efbcf9e854a5335108'),
    'nf_request': ('https://www.nffund.com/main/nffund/js/personal-financing/detail.js', '2a1eae803324c811d46e76e33a80c5850ae6e1cd79252acff93fdd412baae99d'),
    'js_request': ('https://www.jsfund.cn/ws/scripts/service/ws/wsService.js?v=1.0.0.202609152313', 'e6d4d6df3b028368d281d7ff4375b81a5e7f55ead6a9130056f3dab2a866c397'),
}
NOTE = '只核对发行人当前返回的分红/拆分历史表；查询失败、空表与已列记录分开。按登记日统计的分红不是除息或现金发放，完整表未列窗口内事项也不证明所有份额事件已核验，不用于净申赎校正或识别资金身份。'


def processor_digest():
    root = Path(__file__).parent
    return digest({name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
                   (Path(__file__).name, 'etf_nav_refresh.py', 'etf_issuer_nav.py', 'etf_szse_history.py', 'canonical_json.py')})


PROCESSOR_DIGEST = processor_digest()


def decimal_value(value):
    if not re.fullmatch(r'\d+(?:\.\d+)?', str(value)): raise ValueError('invalid monetary value')
    return Decimal(str(value))


def decimal_text(value):
    value = decimal_value(value)
    text = format(value, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def day(value):
    if not isinstance(value, str): raise ValueError('invalid source date')
    if re.fullmatch(r'\d{8}', value): value = f'{value[:4]}-{value[4:6]}-{value[6:]}'
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value): raise ValueError('invalid source date')
    return date.fromisoformat(value).isoformat()


def stamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None: raise ValueError('observation timezone missing')
    return parsed


def json_payload(text):
    return json.loads(text, parse_float=Decimal)


def text_body(raw, encoding=''):
    if encoding.lower() not in ('', 'identity', 'gzip'): raise ValueError('unsupported content encoding')
    if encoding.lower() == 'gzip' or raw.startswith(b'\x1f\x8b'):
        with gzip.GzipFile(fileobj=BytesIO(raw)) as stream: raw = stream.read(8_000_001)
    if len(raw) > 8_000_000: raise ValueError('expanded source too large')
    return raw.decode('utf-8')


def query(code, cutoff, page=1):
    if code not in NAV_DEFINITIONS or type(page) is not int or page < 1: raise ValueError('undeclared fund/query')
    provider = NAV_DEFINITIONS[code]['provider']
    if provider == 'huatai_pb': return NAV_DEFINITIONS[code]['url'], 'GET', None, None
    if provider == 'chinaamc':
        return 'https://www.chinaamc.com/product/fundLishifenhong.do', 'POST', {'fundcode': code[:6], 'pageIndex': page}, 'form'
    if provider == 'efunds':
        return EF_API, 'POST', {'fundCode': code[:6], 'pageIndex': page-1, 'pageSize': 10,
                               'startDate': '2013-03-06', 'endDate': cutoff}, 'json'
    if provider == 'nffund':
        return NF_API, 'POST', {'fundCode': code[:6], 'startDate': '', 'endDate': '', 'curPage': page, 'pageSize': 10}, 'form'
    return JS_API, 'POST', {'funcNo': '741016', 'fundcode': code[:6], 'type': '2'}, 'form'


def distribution(*, register, pay, amount, per=1, ex=None, off_register=None, off_pay=None, reference=None):
    result = {'record_on': day(register), 'cash_paid_on': day(pay), 'ex_dividend_on': day(ex) if ex else None,
              'off_exchange_record_on': day(off_register) if off_register else None,
              'off_exchange_cash_paid_on': day(off_pay) if off_pay else None,
              'evaluation_reference_on': day(reference) if reference else None,
              'source_amount_text': str(amount), 'source_unit_shares': per,
              'amount_yuan_per_share': decimal_text(decimal_value(amount)/per)}
    if (Decimal(result['amount_yuan_per_share']) <= 0 or result['record_on'] > result['cash_paid_on']
        or result['ex_dividend_on'] and not result['record_on'] <= result['ex_dividend_on'] <= result['cash_paid_on']
        or result['off_exchange_record_on'] and (not result['off_exchange_cash_paid_on']
              or result['off_exchange_record_on'] > result['off_exchange_cash_paid_on'])):
        raise ValueError('invalid distribution amount/date order')
    return result


def finish(rows, splits=None, *, state='observed', split_state='not_checked'):
    dates = [row['record_on'] for row in rows]
    if len(dates) != len(set(dates)): raise ValueError('duplicate distribution date')
    if splits is not None and len({row['effective_on'] for row in splits}) != len(splits): raise ValueError('duplicate split date')
    return {'availability': state, 'distributions': sorted(rows, key=lambda row: row['record_on'], reverse=True),
            'split_table_status': split_state, 'splits': sorted(splits or [], key=lambda row: row['effective_on'], reverse=True)}


def parse_huatai(text, code):
    header = text[:text.index('<tbody id="fhTbody">')].rsplit('<table', 1)[-1] if '<tbody id="fhTbody">' in text else ''
    if (not re.search(r'</html>\s*$', text, re.I) or code != '510300.SH'
        or re.findall(r"var\s+project\s*=\s*seekProject\('([0-9]{6})'\)", text) != [code[:6]]
        or '每10份基金份额分红（元）' not in header or '红利发放日/再投资日' not in header
        or '$("#fhTbody>tr").length/10' not in text or 'showFhTable(1,allPage,10,"fenhong-page")' not in text):
        raise ValueError('unbound Huatai fund/unit/local pagination')
    fragments = re.findall(r'<tbody\s+id="fhTbody">(.*?)</tbody>', text, re.S)
    if len(fragments) != 1: raise ValueError('ambiguous Huatai history')
    source = NAVTable('<html><table>'+fragments[0]+'</table></html>').table_rows()
    rows = []
    for row in source:
        if len(row) != 4 or row[0] != day(row[1])[:4]: raise ValueError('invalid Huatai year/table')
        rows.append(distribution(register=row[1], pay=row[2], amount=row[3], per=10))
    return finish(rows, state='observed' if rows else 'empty_table_unconfirmed')


def parse_china(text, code):
    parsed = NAVTable(text)
    if (parsed.inputs.get('fundcode') != code[:6]
        or set(re.findall(r"let\s+currentPage\s*=\s*'(\d+)'", text)) != {'1'}
        or set(re.findall(r"let\s+totalPage\s*=\s*'(\d+)'", text)) != {'1'}
        or parsed.table_rows(identifier='hoverBox1') != [['年份', '权益登记日', '每份分红（元）', '分红发放日']]):
        raise ValueError('changed ChinaAMC identity/units or unsupported pagination')
    source = parsed.table_rows(identifier='hoverBox1_1')
    if not source or source[-1][:2] != ['', ''] or len(source[-1]) != 4 or source[-1][-1] != '' or not source[-1][2].startswith('合计:'):
        raise ValueError('missing distribution total')
    total = source[-1][2].removeprefix('合计:'); rows = []
    for row in source[:-1]:
        if len(row) != 4 or row[0] != day(row[1])[:4]: raise ValueError('invalid ChinaAMC year/table')
        rows.append(distribution(register=row[1], amount=row[2], pay=row[3]))
    if not rows:
        if total not in ('', '0', '0.0000'): raise ValueError('nonzero total with empty table')
        return finish([], state='empty_table_unconfirmed')
    if decimal_value(total) != sum(Decimal(row['amount_yuan_per_share']) for row in rows): raise ValueError('distribution sum mismatch')
    return finish(rows)


def parse_efunds(pages):
    if not pages: raise ValueError('missing Efunds pages')
    total = None; rows = []
    for page, payload in enumerate(pages):
        if (type(payload.get('status')) is not int or payload['status'] != 1 or payload.get('moneyType') != '元'
            or payload.get('showRecordDate') is not True or payload.get('showPayDate') is not True
            or type(payload.get('total')) is not int or payload['total'] < 0
            or total is not None and payload['total'] != total): raise ValueError('invalid Efunds response status/units/count')
        total = payload['total']
        if len(payload['data']) != min(10, max(0, total-page*10)):
            raise ValueError('unexpected Efunds page size')
        for row in payload['data']:
            if row['amtSplitType'] != 'BONUS' or row['recordDate'] != row['outRecordDate']:
                raise ValueError('different bonus kind or record scope')
            rows.append(distribution(register=row['inRecordDate'], pay=row['inpayDate'], off_register=row['outRecordDate'],
                                     off_pay=row['payDate'], reference=row['bchDate'], amount=row['unitProfit']))
    if total != len(rows) or len(pages) != max(1, (total+9)//10): raise ValueError('incomplete Efunds pagination')
    return finish(rows, state='observed' if rows else 'empty_table_unconfirmed')


def full_nf_block(payload, key):
    block = payload['data'][key]
    if (any(type(block.get(name)) is not int for name in ('total', 'pageNum', 'pageSize', 'size', 'pages', 'nextPage'))
        or block['pageNum'] != 1 or block['pageSize'] != 10 or block['size'] != len(block['list'])
        or not 0 <= block['total'] <= 10
        or block['total'] != len(block['list']) or block['pages'] != (1 if block['total'] else 0)
        or block['hasNextPage'] is not False or block['nextPage'] != 0):
        raise ValueError('incomplete NF table or unsupported pagination')
    return block['list']


def parse_nf(payload, code):
    if payload['code'] != 'ETS-5BP00000': raise ValueError('NF query failed')
    rows, splits = [], []
    for row in full_nf_block(payload, 'jjfhlist'):
        if row['f1'] != code[:6] or row['securitiesBo']['f16'] != code[:6] or decimal_value(row['f6']) != 1:
            raise ValueError('wrong NF product or amount denominator')
        if decimal_value(row['f7f6']) != decimal_value(row['f7'])/decimal_value(row['f6']):
            raise ValueError('NF normalized amount differs')
        # The official display maps f8/f10, but does not label f9 as ex-dividend.
        rows.append(distribution(register=row['f8'], pay=row['f10'], amount=row['f7f6']))
    if decimal_value(payload['data']['sum_f7f6']) != sum(Decimal(row['amount_yuan_per_share']) for row in rows):
        raise ValueError('NF dividend sum mismatch')
    for row in full_nf_block(payload, 'splitlist'):
        if row['fundCode'] != code[:6] or decimal_value(row['denominator']) != 1 or decimal_value(row['molecular']) <= 0:
            raise ValueError('wrong split fund or ratio denominator')
        splits.append({'effective_on': day(row['splitDate']), 'ratio': decimal_text(row['molecular']),
                       'source_classification': 'issuer_split_table_row', 'not_historical_PIT': True})
    return finish(rows, splits, state='observed' if rows else 'empty_table_unconfirmed', split_state='observed')


def parse_js_failure(payload):
    # The live official UI maps both errors and successful empty results to the
    # same empty label. Success grammar has not been reviewed, so never infer zero.
    value = payload.get('error_no')
    if isinstance(value, bool) or not re.fullmatch(r'-?\d+', str(value)) or int(value) == 0:
        raise ValueError('unreviewed JS success schema')
    return finish([], state='query_failed')


def read_response(ref, directory, *, expected, started, completed):
    url, method, params, encoding = expected
    if ((ref['url'], ref['method'], ref['request_encoding']) != (url, method, encoding) or digest(ref['params']) != digest(params)
        or ref['final_url'] != url or not started <= stamp(ref['observed_at']) <= completed
        or type(ref['bytes']) is not int or not re.fullmatch(r'[0-9a-f]{64}', ref['response_sha256'])): raise ValueError('source query/time/identity mismatch')
    raw = (directory/f"{ref['response_sha256']}.raw").read_bytes()
    if len(raw) != ref['bytes'] or len(raw) > 8_000_000 or hashlib.sha256(raw).hexdigest() != ref['response_sha256']:
        raise ValueError('source bytes mismatch')
    return text_body(raw, ref['content_encoding'])


def project(raw, directory, now):
    unsigned = {key: value for key, value in raw.items() if key != 'content_digest'}
    started, completed = stamp(raw['started_at']), stamp(raw['completed_at'])
    start, end, cutoff = map(day, (raw['window_start'], raw['through'], raw['query_cutoff']))
    if (raw['contract_version'] != VERSION or raw['processor_digest'] != PROCESSOR_DIGEST or digest(unsigned) != raw['content_digest']
        or raw['availability_basis'] != 'first_observed_not_historical_PIT' or not started <= completed <= now
        or not start <= end < cutoff or cutoff != started.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
        or set(raw['funds']) != set(NAV_DEFINITIONS) or set(raw['proofs']) != set(PROOFS)):
        raise ValueError('invalid history snapshot definition, scope or dates')
    if raw.get('reparsed_at') and not completed <= stamp(raw['reparsed_at']) <= now: raise ValueError('invalid reparse time')
    proof_text = {}
    for key, (url, expected_hash) in PROOFS.items():
        text = read_response(raw['proofs'][key], directory, expected=(url, 'GET', None, None), started=started, completed=completed)
        if expected_hash and hashlib.sha256(text.encode()).hexdigest() != expected_hash: raise ValueError('source schema requires review')
        proof_text[key] = text
    ef = proof_text['efunds_page']; nf = proof_text['nf_page']
    first, last = 'function devidend_queryData(){', "$('.devidend_page').on("
    if (ef.count(first) != 1 or ef.count(last) != 1 or ef.index(first) >= ef.index(last)
        or hashlib.sha256(ef[ef.index(first):ef.index(last)].encode()).hexdigest() != EF_DIVIDEND_GRAMMAR_SHA256):
        raise ValueError('Efunds distribution display/query grammar requires review')
    if ("fundCode:'510310'" not in ef or EF_API not in ef or '每份红利(元)' not in ef
        or not all(key in ef for key in ('unitProfit', 'inRecordDate', 'outRecordDate', 'inpayDate', 'bchDate'))
        or '每单位基金派息(元)' not in nf or '权益登记日' not in nf or '红利发放日' not in nf):
        raise ValueError('unverified primary units/field mapping')
    funds = []
    for code in NAV_DEFINITIONS:
        refs = raw['funds'][code]
        if not 1 <= len(refs) <= 10: raise ValueError('incomplete/unbounded history pages')
        pages = [read_response(ref, directory, expected=query(code, cutoff, page), started=started, completed=completed)
                 for page, ref in enumerate(refs, 1)]
        provider = NAV_DEFINITIONS[code]['provider']
        if provider != 'efunds' and len(pages) != 1: raise ValueError('unsupported history pagination')
        parsed = (parse_huatai(pages[0], code) if provider == 'huatai_pb' else parse_china(pages[0], code) if provider == 'chinaamc'
                  else parse_efunds([json_payload(page) for page in pages]) if provider == 'efunds'
                  else parse_nf(json_payload(pages[0]), code) if provider == 'nffund' else parse_js_failure(json_payload(pages[0])))
        rows = parsed['distributions']
        if any(row['record_on'] > cutoff for row in rows): raise ValueError('future record date outside observed scope')
        if provider == 'efunds' and any(any(value and not '2013-03-06' <= value <= cutoff
                  for value in (row['record_on'], row['off_exchange_record_on'])) for row in rows):
            raise ValueError('bonus record date outside explicit query')
        record_dates = lambda row: [row['record_on']]+([row['off_exchange_record_on']] if row['off_exchange_record_on'] else [])
        in_window = [row for row in rows if any(start <= value <= end for value in record_dates(row))]
        paid_window = [row for row in rows if any(start <= value <= end for value in
                       [row['cash_paid_on']]+([row['off_exchange_cash_paid_on']] if row['off_exchange_cash_paid_on'] else []))]
        observed = parsed['availability'] == 'observed'
        funds.append({**parsed, 'code': code, 'issuer': NAV_DEFINITIONS[code]['label'], 'provider': provider,
                      'source_url': NAV_DEFINITIONS[code]['url'] if provider not in ('chinaamc', 'jsfund') else
                          (f'https://www.chinaamc.com/fund/{code[:6]}/lishifenhong.shtml' if provider == 'chinaamc' else f'https://www.jsfund.cn/main/fund/{code[:6]}/fundNav.shtml'),
                      'observed_at': max((ref['observed_at'] for ref in refs), key=stamp), 'responses': refs,
                      'table_records': len(rows) if observed else None, 'latest_listed_distribution': rows[0] if rows else None,
                      'window_record_date_count': len(in_window) if observed else None,
                      'window_cash_paid_date_count': len(paid_window) if observed else None,
                      'window_split_count': sum(start <= row['effective_on'] <= end for row in parsed['splits']) if parsed['split_table_status'] == 'observed' else None,
                      'window_ex_dividend_count': None, 'corporate_actions_checked': False})
    return {'version': VERSION, 'availability': 'partial', 'funds': funds, 'declared_etfs': len(NAV_DEFINITIONS),
            'history_tables_observed': sum(fund['availability'] == 'observed' for fund in funds),
            'empty_tables_unconfirmed': sum(fund['availability'] == 'empty_table_unconfirmed' for fund in funds),
            'query_failed_etfs': sum(fund['availability'] == 'query_failed' for fund in funds),
            'window_start': start, 'through': end, 'query_cutoff': cutoff, 'started_at': raw['started_at'], 'completed_at': raw['completed_at'],
            'content_digest': raw['content_digest'], 'processor_digest': PROCESSOR_DIGEST, 'proofs': raw['proofs'],
            'reparsed_at': raw.get('reparsed_at'),
            'corporate_actions_checked': False, 'estimated_net_subscription_yuan': None, 'note': NOTE}


def history_status(directory, now):
    base = {'version': VERSION, 'availability': 'missing', 'funds': [], 'declared_etfs': len(NAV_DEFINITIONS),
            'history_tables_observed': 0, 'empty_tables_unconfirmed': 0, 'query_failed_etfs': 0,
            'corporate_actions_checked': False, 'estimated_net_subscription_yuan': None, 'note': NOTE}
    if processor_digest() != PROCESSOR_DIGEST: return {**base, 'availability': 'reload_required'}
    try: return project(json.loads((directory/'current.json').read_text()), directory/'responses', now)
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError, EOFError):
        return {**base, 'availability': 'invalid' if (directory/'current.json').exists() else 'missing'}


class HistoryClient:
    def __init__(self, response_dir): self.response_dir = response_dir

    def request(self, url, method='GET', params=None, encoding=None):
        if url not in {value[0] for value in PROOFS.values()} | {query(code, '2026-11-05')[0] for code in NAV_DEFINITIONS}:
            raise ValueError('undeclared issuer endpoint')
        data = (json.dumps(params).encode() if encoding == 'json' else urlencode(params).encode()) if params is not None else None
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'identity'}
        if data is not None: headers['Content-Type'] = 'application/json' if encoding == 'json' else 'application/x-www-form-urlencoded'
        with urlopen(Request(url, data=data, method=method, headers=headers), timeout=20) as response:
            if response.geturl() != url: raise ValueError('unexpected issuer redirect')
            body = response.read(8_000_001); content_encoding = response.headers.get('Content-Encoding', '')
        if len(body) > 8_000_000: raise ValueError('source response too large')
        sha = hashlib.sha256(body).hexdigest(); archive_response(self.response_dir/f'{sha}.raw', body)
        return {'url': url, 'final_url': url, 'method': method, 'params': params, 'request_encoding': encoding,
                'content_encoding': content_encoding, 'response_sha256': sha, 'bytes': len(body), 'observed_at': datetime.now(timezone.utc).isoformat()}


def refresh_history(client, *, start, through, output, now=None):
    if processor_digest() != PROCESSOR_DIGEST: raise ValueError('reload processor before collecting')
    if (output/'current.json').exists() and json.loads((output/'current.json').read_text()).get('contract_version') != VERSION:
        raise ValueError('output belongs to another source')
    started = now or datetime.now(timezone.utc)
    cutoff = started.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
    if not day(start) <= day(through) < cutoff: raise ValueError('completed review window required')
    try:
        raw = {'contract_version': VERSION, 'processor_digest': PROCESSOR_DIGEST, 'window_start': start, 'through': through,
               'query_cutoff': cutoff, 'started_at': started.isoformat(), 'availability_basis': 'first_observed_not_historical_PIT',
               'proofs': {}, 'funds': {}}
        for key, (url, _) in PROOFS.items(): raw['proofs'][key] = client.request(url)
        for code in NAV_DEFINITIONS:
            refs = [client.request(*query(code, cutoff))]
            if NAV_DEFINITIONS[code]['provider'] == 'efunds':
                ref = refs[0]; text = read_response(ref, client.response_dir, expected=query(code, cutoff), started=started, completed=now or datetime.now(timezone.utc))
                total = json_payload(text)['total']
                if type(total) is not int or not 0 <= total <= 100: raise ValueError('unbounded bonus pages')
                for page in range(2, (total+9)//10+1): refs.append(client.request(*query(code, cutoff, page)))
            raw['funds'][code] = refs
        raw['completed_at'] = (now or datetime.now(timezone.utc)).isoformat(); raw['content_digest'] = digest(raw)
        result = project(raw, client.response_dir, now or datetime.now(timezone.utc))
        previous = history_status(output, now or datetime.now(timezone.utc))
        if previous['availability'] == 'partial':
            states = {fund['code']: fund['availability'] for fund in result['funds']}
            if any(fund['availability'] == 'observed' and states[fund['code']] != 'observed' for fund in previous['funds']):
                raise ValueError('observed table regressed to an unknown result')
        (output/'responses').mkdir(parents=True, exist_ok=True)
        for ref in list(raw['proofs'].values())+[ref for refs in raw['funds'].values() for ref in refs]:
            name = f"{ref['response_sha256']}.raw"; archive_response(output/'responses'/name, (client.response_dir/name).read_bytes())
        project(raw, output/'responses', now or datetime.now(timezone.utc))
        atomic_write_json(output/'snapshots'/f"{raw['content_digest']}.json", raw); atomic_write_json(output/'current.json', raw)
        report = {key: result[key] for key in ('availability', 'content_digest', 'history_tables_observed', 'empty_tables_unconfirmed', 'query_failed_etfs')}
        report['status'] = 'partial'
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError, EOFError) as exc:
        report = {'status': 'failed', 'reason': type(exc).__name__, 'current_snapshot_preserved': True}
    atomic_write_json(output/'last_attempt.json', report)
    return report


def reparse_history(*, output, start, through, now=None):
    """Explicitly revalidate archived bytes after code changes; do not refresh fetch times."""
    now = now or datetime.now(timezone.utc)
    try:
        if processor_digest() != PROCESSOR_DIGEST: raise ValueError('reload processor before reparsing')
        before = (output/'current.json').read_bytes(); raw = json.loads(before)
        if (raw['contract_version'] != VERSION or raw['window_start'] != start or raw['through'] != through
            or raw['content_digest'] != digest({key: value for key, value in raw.items() if key != 'content_digest'})):
            raise ValueError('archive scope/digest mismatch')
        raw['processor_digest'] = PROCESSOR_DIGEST; raw['reparsed_at'] = now.isoformat()
        raw['content_digest'] = digest({key: value for key, value in raw.items() if key != 'content_digest'})
        result = project(raw, output/'responses', now)
        if (output/'current.json').read_bytes() != before: raise ValueError('current archive changed during reparse')
        atomic_write_json(output/'snapshots'/f"{raw['content_digest']}.json", raw); atomic_write_json(output/'current.json', raw)
        report = {key: result[key] for key in ('availability', 'content_digest', 'history_tables_observed', 'empty_tables_unconfirmed', 'query_failed_etfs')}
        report.update(status='partial', mode='reparsed_archived_responses', fetched_times_preserved=True)
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError, EOFError) as exc:
        report = {'status': 'failed', 'reason': type(exc).__name__, 'current_snapshot_preserved': True}
    atomic_write_json(output/'last_attempt.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', required=True); parser.add_argument('--through', required=True)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--reparse', action='store_true', help='recheck same-window archived responses without a network request')
    args = parser.parse_args()
    report = (reparse_history(output=args.output, start=args.start, through=args.through) if args.reparse else
              refresh_history(HistoryClient(args.output/'responses'), start=args.start, through=args.through, output=args.output))
    print(json.dumps(report, ensure_ascii=False)); return 2 if report['status'] == 'failed' else 0


if __name__ == '__main__': raise SystemExit(main())
