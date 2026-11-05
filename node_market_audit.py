"""Outcome-blind eligibility and source-lineage audit for a separate market comparison."""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
from contextlib import closing
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from settings import BASE_DB, DATA_ROOT, MARKET_CONTEXT_DB, P8_QFQ_DB, P8_RESEARCH_DB, VALUATION_EPISODE_DB
from p8_event_graph import P6_EVENT_TO_NODE

VERSION = 'node_market_input_audit_v1'
PLAN_PATH = Path(__file__).with_name('node_market_study_v1.json')
PLAN = json.loads(PLAN_PATH.read_text())
PLAN_DIGEST = digest(PLAN)
DEFAULT_OUTPUT = DATA_ROOT/'local_data/v8_copilot/market_risk/node_market_audit'
P6A_DB = DATA_ROOT/'local_data/v8_copilot/restructuring_entities_v1.sqlite3'
DATE_PROFILE = Path(__file__).with_name('node_market_date_reviews_v1.json')
DATE_REVIEWS = json.loads(DATE_PROFILE.read_text())['reviews']


def processor_digest():
    root = Path(__file__).parent
    return digest({name: hashlib.sha256((root/name).read_bytes()).hexdigest()
                   for name in (Path(__file__).name, PLAN_PATH.name, DATE_PROFILE.name, 'canonical_json.py')})


PROCESSOR_DIGEST = processor_digest()


def ro(path):
    if not path.is_file(): raise FileNotFoundError(path.name)
    conn = sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    def authorize(action, table, column, *_):
        if action == sqlite3.SQLITE_READ and table in ('daily_prices', 'benchmark_daily'):
            if column not in ('symbol', 'trade_date', 'adjust', 'benchmark_id', ''): return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    conn.set_authorizer(authorize)
    return conn


def iso(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value): raise ValueError('invalid source date')
    return date.fromisoformat(value).isoformat()


def signature_day(value):
    """Parse a Gregorian issuer signature date, including 二〇二三年七月二十五日."""
    match = re.fullmatch(r'([0-9〇零○一二三四五六七八九十]+)年([0-9〇零○一二三四五六七八九十]+)月([0-9〇零○一二三四五六七八九十]+)日', value)
    if not match: raise ValueError('unsupported signature date')
    digits = dict(zip('〇零○一二三四五六七八九', (0,0,0,1,2,3,4,5,6,7,8,9)))
    year, month, day = match.groups()
    if re.fullmatch(r'20[0-9]{2}', year): year = int(year)
    elif re.fullmatch(r'[二][〇零○][〇零○一二三四五六七八九]{2}', year): year = int(''.join(str(digits[char]) for char in year))
    else: raise ValueError('unsupported signature year')
    def number(text):
        if re.fullmatch(r'[0-9]{1,2}', text): return int(text)
        if len(text) == 1 and text in digits: return digits[text]
        if text.count('十') == 1:
            left, right = text.split('十')
            if (not left or len(left) == 1 and digits.get(left, 0) > 0) and (not right or len(right) == 1 and digits.get(right, 0) > 0):
                return (digits[left] if left else 1)*10+(digits[right] if right else 0)
        raise ValueError('unsupported signature month/day')
    return date(year, number(month), number(day)).isoformat()


def reviewed_dates(directory):
    results = []
    for case in DATE_REVIEWS:
        try:
            raw = (directory/(case['raw_sha256']+'.pdf')).read_bytes()
            text = (directory/(case['text_sha256']+'.json')).read_bytes()
            pages = json.loads(text)['pages']
            compact = lambda value: re.sub(r'\s+', '', value)
            signatures = re.findall(re.escape(case['company']+'董事会')+r'([0-9〇零○一二三四五六七八九十]+年[0-9〇零○一二三四五六七八九十]+月[0-9〇零○一二三四五六七八九十]+日)', compact(pages[case['signature_page']-1]))
            if (hashlib.sha256(raw).hexdigest() != case['raw_sha256'] or not raw.startswith(b'%PDF-')
                or hashlib.sha256(text).hexdigest() != case['text_sha256'] or len(pages) != case['source_pages']
                or not re.search(r'证券代码[:：]'+case['symbol'], compact(pages[0]))
                or [signature_day(value) for value in signatures] != [iso(case['signed_on'])]): raise ValueError('reviewed document changed')
            results.append({**case,'availability':'observed','signature_date_text':signatures[0]})
        except (OSError, ValueError, KeyError, TypeError, IndexError): results.append({**case,'availability':'unavailable'})
    return results


def collect_inputs(*, episodes=VALUATION_EPISODE_DB, facts=P6A_DB, research=P8_RESEARCH_DB,
                   market=MARKET_CONTEXT_DB, base=BASE_DB, overlay=P8_QFQ_DB, date_sources=DEFAULT_OUTPUT/'date_sources'):
    """Read identifiers, dates and keys only; price-value reads are denied by SQLite."""
    with closing(ro(episodes)) as conn:
        run = conn.execute('select run_id,as_of,payload_json from valuation_episode_runs order by rowid desc limit 1').fetchone()
        if not run: raise ValueError('no episode run')
        p6_run = json.loads(run['payload_json'])
        if p6_run['run_id'] != run['run_id'] or p6_run['as_of'] != run['as_of']: raise ValueError('P6 run identity mismatch')
        events = []
        for row in conn.execute('select e.event_id,e.symbol,e.information_available_date,e.payload_json from valuation_episode_events e '
                                'join valuation_episode_run_events x on x.event_id=e.event_id where x.run_id=? order by e.event_id', (run['run_id'],)):
            item = json.loads(row['payload_json'])
            if (item['event_id'], item['symbol'], item['information_available_date']) != (row['event_id'], row['symbol'], row['information_available_date']):
                raise ValueError('event metadata and payload differ')
            events.append({key: item[key] for key in ('event_id', 'symbol', 'event_type', 'event_date', 'information_available_date', 'source_kind', 'source_ref', 'evidence_status')})
        all_rows = conn.execute('select count(*) from valuation_episode_events').fetchone()[0]
    with closing(ro(facts)) as conn:
        parents = [dict(row) for row in conn.execute("""select e.event_id,c.symbol,e.event_type,e.event_date,e.information_available_date,e.source_document_id,
            d.document_id,d.symbol document_symbol,d.published_date,
            json_extract(d.payload_json,'$.document_id') json_document_id,json_extract(d.payload_json,'$.symbol') json_symbol,
            json_extract(d.payload_json,'$.published_date') json_published_date,json_extract(d.payload_json,'$.source_kind') source_kind,
            json_extract(d.payload_json,'$.source_url') source_url,json_extract(d.payload_json,'$.body_sha256') body_sha256,
            length(json_extract(d.payload_json,'$.evidence_quote')) quote_length
            from restructuring_events e join restructuring_cases c on c.case_id=e.case_id
            join source_documents d on d.document_id=e.source_document_id order by e.event_id""")]
    with closing(ro(research)) as conn:
        run = conn.execute("select run_id,through,content_digest from p8_runs where run_kind='event_graph' order by created_at desc,rowid desc limit 1").fetchone()
        if not run: raise ValueError('no event-graph run')
        p8_run = dict(run)
        p8 = [dict(row) for row in conn.execute("""select record_id,symbol,available_as_of,evidence_status,content_digest,
            json_extract(payload_json,'$.source_ids') source_ids,json_extract(payload_json,'$.node') node
            from p8_records where run_id=? and record_type='derived_event' order by record_id""", (run['run_id'],))]
        for item in p8: item['source_ids'] = json.loads(item['source_ids'])
    with closing(ro(market)) as conn:
        calendar = [row[0] for row in conn.execute("select trade_date from benchmark_daily where benchmark_id='csi_all_share' order by trade_date")]
        dates = set()
        for item in events:
            index = bisect_right(calendar, item['information_available_date'])-1
            if index >= 0: dates.add(calendar[index])
        # Reviewed document days can move a feature cutoff, including across a holiday.
        date_reviews = reviewed_dates(date_sources)
        for review in date_reviews:
            index = bisect_right(calendar, review['signed_on'])-1
            if index >= 0: dates.add(calendar[index])
        if not dates: raise ValueError('no historical benchmark dates')
        marks = ','.join('?' for _ in dates)
        membership = [list(row) for row in conn.execute(f'select trade_date,symbol from st_membership_daily where trade_date in ({marks}) order by trade_date,symbol', sorted(dates))]
        membership_through = conn.execute('select max(trade_date) from st_membership_daily').fetchone()[0]
    symbols = sorted({item['symbol'] for item in events if item['source_kind'] == 'p6a_verified_fact'})
    price_sources = {}
    for name, path in (('p8_qfq_complete_window', overlay), ('base_qfq_complete_window', base)):
        with closing(ro(path)) as conn:
            through = conn.execute("select max(trade_date) from daily_prices where adjust='qfq'").fetchone()[0]
            marks = ','.join('?' for _ in symbols)
            keys = [list(row) for row in conn.execute(f"select symbol,trade_date from daily_prices where adjust='qfq' and symbol in ({marks}) and trade_date>=? order by symbol,trade_date", [*symbols, PLAN['anchor_start']])] if symbols else []
            price_sources[name] = {'through': through, 'keys': keys}
    return {'p6_run': {key: p6_run.get(key) for key in ('run_id', 'as_of', 'verified_event_count')}, 'event_table_rows': all_rows,
            'events': events, 'parents': parents, 'p8_run': p8_run, 'derived_events': p8, 'calendar': calendar,
            'membership': membership, 'membership_through': membership_through, 'price_sources': price_sources,
            'date_reviews': date_reviews, 'node_map': dict(P6_EVENT_TO_NODE)}


def parent_issues(event, parents, review=None):
    matching = [row for row in parents if (row['symbol'], row['event_type'], row['information_available_date'], row['source_document_id']) ==
                (event['symbol'], event['event_type'], event['information_available_date'], event['source_ref'])]
    if not matching: return ['parent_fact_missing']
    issues = set()
    for row in matching:
        if (row['document_id'] != row['json_document_id'] or row['document_symbol'] != event['symbol']
            or row['json_symbol'] != event['symbol'] or row['published_date'] != row['json_published_date']
            or row['event_date'] != event['event_date']): issues.add('parent_metadata_conflict')
        if row['source_kind'] != 'official_issuer_announcement' or urlparse(row['source_url'] or '').hostname not in {
                'static.cninfo.com.cn', 'www.sse.com.cn', 'www.szse.cn', 'docs.static.szse.cn'}: issues.add('primary_source_not_bound')
        if not re.fullmatch(r'[0-9a-f]{64}', row['body_sha256'] or '') or (row['quote_length'] or 0) <= 0:
            issues.add('prior_evidence_metadata_missing')
        published = iso(row['published_date'])
        if event['information_available_date'] < published: issues.add('available_before_source_publication')
        hint = re.search(r'/finalpage/(\d{4}-\d{2}-\d{2})/', row['source_url'] or '')
        matched_review = (review and review['symbol'] == event['symbol'] and
                          urlparse(review['source_url']).hostname == urlparse(row['source_url']).hostname and
                          urlparse(review['source_url']).path == urlparse(row['source_url']).path and
                          (not hint or iso(review['signed_on']) >= iso(hint[1])))
        if hint and iso(hint[1]) != published and not matched_review: issues.add('publication_date_hint_conflict')
    return sorted(issues)


def project(inputs):
    events = inputs['events']; calendar = inputs['calendar']
    if not calendar or calendar != sorted(set(calendar)): raise ValueError('invalid benchmark date keys')
    if len({row['event_id'] for row in events}) != len(events): raise ValueError('duplicate active event ID')
    members = defaultdict(set)
    for day, symbol in inputs['membership']: members[day].add(symbol)
    prices = {}
    for name, source in inputs['price_sources'].items():
        keys = [tuple(row) for row in source['keys']]
        if len(keys) != len(set(keys)): raise ValueError('duplicate qfq price key')
        prices[name] = set(keys)
    cohorts = []; seen = set(); revised_keys = set(); issues_count = Counter(); origins = Counter()
    by_id = {row['event_id']: row for row in events}
    date_reviews = {row['document_id']: row for row in inputs['date_reviews'] if row['availability'] == 'observed'}
    for event in events:
        iso(event['event_date']); available = iso(event['information_available_date'])
        if not re.fullmatch(r'\d{6}', event['symbol']) or event['source_kind'] not in ('p6a_verified_fact', 'official_title_exact'):
            raise ValueError('undeclared event origin/identity')
        origins[event['source_kind']] += 1
        if event['source_kind'] != 'p6a_verified_fact' or not PLAN['anchor_start'] <= available <= PLAN['anchor_end']: continue
        key = (event['symbol'], available, event['event_type'])
        if key in seen: raise ValueError('duplicate canonical node observation')
        seen.add(key)
        review = date_reviews.get(event['source_ref'])
        if review and (review['symbol'] != event['symbol'] or not any(
            row['source_document_id'] == event['source_ref'] and row['symbol'] == event['symbol']
            and urlparse(row['source_url'] or '').hostname == urlparse(review['source_url']).hostname
            and urlparse(row['source_url'] or '').path == urlparse(review['source_url']).path for row in inputs['parents'])):
            review = None
        issues = parent_issues(event, inputs['parents'], review)
        original_available = available
        if review: available = max(available, review['signed_on'])
        revised_key = (event['symbol'], available, event['event_type'])
        if revised_key in revised_keys: raise ValueError('reviewed dates collapse duplicate observations')
        revised_keys.add(revised_key)
        if event['event_type'] not in PLAN['node_types'] or event['evidence_status'] != 'verified_official_source': issues.append('node_definition_not_admitted')
        index = bisect_right(calendar, available)
        feature_date = calendar[index-1] if index else None
        if not feature_date or feature_date not in members: issues.append('historical_membership_missing')
        elif event['symbol'] not in members[feature_date]: issues.append('not_in_source_historical_st_membership')
        path = calendar[index:index+PLAN['horizon_sessions']+1]
        source = next((name for name in PLAN['price_source_priority'] if len(path) == PLAN['horizon_sessions']+1
                       and all((event['symbol'], day) in prices[name] for day in path)), None)
        if not source: issues.append('one_source_price_keys_incomplete')
        if index < 61: issues.append('market_warmup_keys_incomplete')
        issues_count.update(set(issues))
        cohorts.append({'event_id': event['event_id'], 'symbol': event['symbol'], 'event_type': event['event_type'],
                        'information_available_date': available, 'original_information_date': original_available,
                        'reviewed_document_day': review['signed_on'] if review else None, 'feature_through': feature_date,
                        'entry_date': path[0] if path else None, 'outcome_key_end': path[-1] if len(path) == PLAN['horizon_sessions']+1 else None,
                        'price_key_source': source, 'source_ref': event['source_ref'], 'capacity_candidate': not issues, 'issues': sorted(set(issues))})
    lineage = Counter()
    deterministic = [row for row in inputs['derived_events'] if row['evidence_status'] == 'deterministic_verified']
    for row in deterministic:
        parents = [by_id[key] for key in row['source_ids'] if key in by_id and by_id[key]['symbol'] == row['symbol']
                   and by_id[key]['information_available_date'] == row['available_as_of']
                   and inputs['node_map'].get(by_id[key]['event_type']) == row['node']]
        origin = {parent['source_kind'] for parent in parents}
        lineage['active_prior_fact' if 'p6a_verified_fact' in origin else 'active_title' if 'official_title_exact' in origin else 'not_bound_to_active_run'] += 1
    folds = []
    for year in PLAN['test_years']:
        selected = [row for row in cohorts if row['capacity_candidate']]
        test = [row for row in selected if row['information_available_date'].startswith(str(year))]
        train = [row for row in selected if row['information_available_date'] < f'{year}-01-01'
                 and row['outcome_key_end'] and row['outcome_key_end'] < f'{year}-01-01']
        folds.append({'test_year': year, 'train_events': len(train), 'train_companies': len({row['symbol'] for row in train}),
                      'test_events': len(test), 'test_companies': len({row['symbol'] for row in test}),
                      'train_capacity_pass': len(train) >= PLAN['minimum_train_events'] and len({row['symbol'] for row in train}) >= PLAN['minimum_train_companies']})
    test_rows = [row for row in cohorts if row['capacity_candidate'] and int(row['information_available_date'][:4]) in PLAN['test_years']]
    n, companies = len(test_rows), len({row['symbol'] for row in test_rows})
    passed = n >= PLAN['minimum_test_events'] and companies >= PLAN['minimum_test_companies'] and all(fold['train_capacity_pass'] for fold in folds)
    return {'status': 'capacity_only_value_checks_pending' if passed else 'insufficient_source_linked_capacity',
            'outcomes_read': False, 'price_values_read': False, 'effect_measured': False, 'model_fitted': False,
            'p6_run': inputs['p6_run'], 'event_table_rows': inputs['event_table_rows'], 'active_run_linked_events': len(events),
            'unbound_table_rows': inputs['event_table_rows']-len(events), 'source_kind_counts': dict(origins),
            'p8_run': inputs['p8_run'], 'latest_deterministic_events': len(deterministic), 'deterministic_lineage_counts': dict(lineage),
            'main_window_nominations': len(cohorts), 'test_capacity_events': n, 'test_capacity_companies': companies,
            'historical_capacity_pass': passed, 'issues': dict(issues_count), 'folds': folds, 'candidate_rows': cohorts,
            'date_reviews': inputs['date_reviews'],
            'conservative_date_shifts': sum(row['information_available_date'] != row['original_information_date'] for row in cohorts),
            'source_dates': {'benchmark_keys_through': calendar[-1], 'historical_membership_through': inputs['membership_through'],
                             'node_information_through': max((row['information_available_date'] for row in events), default=None),
                             'price_keys_through': {key: value['through'] for key, value in inputs['price_sources'].items()}},
            'notice': '只盘点来源血缘、日期和键覆盖，未读取价格值或效果标签。标题与既有事实链分开；事实链对齐不等于本轮重审原文。日期线索冲突待核，不按文件路径直接改发布日期。'}


def validate_observation(inputs, observed):
    today = observed.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
    source_days = [inputs['p6_run']['as_of'], inputs['p8_run']['through'], inputs['calendar'][-1],
                   inputs['membership_through'], *(source['through'] for source in inputs['price_sources'].values())]
    if any(day is not None and iso(day) > today for day in source_days):
        raise ValueError('source metadata is newer than audit observation')
    for review in inputs['date_reviews']:
        if review['availability'] != 'observed': continue
        fetched = datetime.fromisoformat(review['observed_at'])
        if fetched.tzinfo is None or fetched > observed: raise ValueError('date review observed after audit')


def audit_status(directory=DEFAULT_OUTPUT, *, now=None, paths=None):
    now = now or datetime.now(timezone.utc)
    base = {'version': VERSION, 'availability': 'missing', 'outcomes_read': False, 'effect_measured': False, 'plan': PLAN, 'plan_digest': PLAN_DIGEST}
    if processor_digest() != PROCESSOR_DIGEST or digest(json.loads(PLAN_PATH.read_text())) != PLAN_DIGEST:
        return {**base, 'availability': 'reload_required'}
    try:
        raw = json.loads((directory/'current.json').read_text()); unsigned = {key: value for key, value in raw.items() if key != 'content_digest'}
        observed = datetime.fromisoformat(raw['observed_at'])
        if (raw['version'] != VERSION or digest(unsigned) != raw['content_digest'] or raw['processor_digest'] != PROCESSOR_DIGEST
            or raw['plan_digest'] != PLAN_DIGEST or observed.tzinfo is None or observed > now): raise ValueError('invalid input audit binding')
        current = collect_inputs(**(paths or {}))
        validate_observation(current, observed)
        if digest(current) != raw['input_digest']: return {**base, 'availability': 'source_changed'}
        return {**base, 'availability': 'observed', 'observed_at': raw['observed_at'], 'content_digest': raw['content_digest'],
                'input_digest': raw['input_digest'], 'processor_digest': PROCESSOR_DIGEST, **project(current)}
    except (OSError, ValueError, TypeError, KeyError, IndexError, sqlite3.Error):
        return {**base, 'availability': 'invalid' if (directory/'current.json').exists() else 'missing'}


def materialize(*, output=DEFAULT_OUTPUT, paths=None, now=None):
    now = now or datetime.now(timezone.utc)
    if processor_digest() != PROCESSOR_DIGEST: raise ValueError('reload before audit')
    if (output/'current.json').exists() and json.loads((output/'current.json').read_text()).get('version') != VERSION:
        raise ValueError('output belongs to another source')
    inputs = collect_inputs(**(paths or {})); validate_observation(inputs, now); result = project(inputs)
    raw = {'version': VERSION, 'observed_at': now.isoformat(), 'plan_digest': PLAN_DIGEST,
           'processor_digest': PROCESSOR_DIGEST, 'input_digest': digest(inputs), 'report': result}
    raw['content_digest'] = digest(raw)
    if digest(collect_inputs(**(paths or {}))) != raw['input_digest']: raise ValueError('inputs changed during audit')
    atomic_write_json(output/'snapshots'/f"{raw['content_digest']}.json", raw); atomic_write_json(output/'current.json', raw)
    return {'content_digest': raw['content_digest'], 'status': result['status'], 'test_capacity_events': result['test_capacity_events'],
            'test_capacity_companies': result['test_capacity_companies'], 'outcomes_read': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(); print(json.dumps(materialize(output=args.output), ensure_ascii=False)); return 0


if __name__ == '__main__': raise SystemExit(main())
