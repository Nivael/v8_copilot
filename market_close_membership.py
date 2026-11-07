"""Source-dated risk lists and explicit corroboration of a completed closing group.

Observation time is never rewritten as the market date. A later list can only
confirm the immediately preceding close on a nontrading day, with SZSE itself
declaring that closing date and every independent A-share name agreeing.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
import exchange_risk_membership as legacy
from market_calendar import CALENDAR_SOURCE, CALENDAR_VERSION, sessions_2026
from market_breadth import st_name

VERSION = 'exchange_risk_list_source_dates_v2'
RULE = 'declared_day_and_nontrading_confirmation_v1'
SAME_DAY = 'same_day_observation_v1'


def processor_digest():
    return digest({name: sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                   for name in (Path(__file__).name, 'exchange_risk_membership.py',
                                'market_calendar.py', 'market_breadth.py', 'canonical_json.py')})


def project(raw, directory, now):
    if raw.get('version') != VERSION or raw.get('processor_digest') != processor_digest():
        raise ValueError('risk source-date implementation changed')
    started = datetime.fromisoformat(raw['started_at'])
    completed = datetime.fromisoformat(raw['completed_at'])
    checked = datetime.fromisoformat(raw['checked_at'])
    if (any(t.tzinfo is None for t in (started, completed, checked, now))
            or not started <= completed <= checked <= now
            or legacy.local_day(started) != legacy.local_day(completed)
            or raw['observed_on'] != legacy.local_day(started)):
        raise ValueError('invalid actual risk-list observation times')
    refs = raw['responses']; used = set(); rows = []; groups = []

    def body(key, url, params):
        matches = [(i, ref) for i, ref in enumerate(refs) if ref['key'] == key]
        if len(matches) != 1:
            raise ValueError('missing or duplicate independent risk page')
        i, ref = matches[0]; used.add(i)
        return legacy.read_response(directory, ref, url=url, params=params, started=started, completed=completed)

    for key, (url, expected) in legacy.PROOFS.items():
        fragment = legacy.definition_fragment(key, body(key, url, {}))
        if sha256(fragment.encode()).hexdigest() != expected:
            raise ValueError('unreviewed risk-list source definition')
    for key, item in legacy.GROUPS.items():
        if item['venue'] == 'SSE':
            records = legacy.sse_table(key, json.loads(body(key, legacy.SSE_API, legacy.parameters(key))))
            pages, source_day = 1, None
        else:
            payload = json.loads(body(key + ':1', legacy.SZSE_API, legacy.parameters(key)))
            selected = [table for table in payload if table['metadata']['tabkey'] == item['tab']]
            if len(selected) != 1:
                raise ValueError('independent SZSE tab missing or duplicated')
            source_day = selected[0]['metadata']['subname'].strip()
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', source_day) or date.fromisoformat(source_day).isoformat() != source_day:
                raise ValueError('SZSE did not declare an exact data date')
            if source_day > raw['observed_on']:
                raise ValueError('SZSE data date is later than the actual observation')
            records, meta = legacy.szse_table(key, payload, 1, source_day)
            for page in range(2, meta[1] + 1):
                extra, next_meta = legacy.szse_table(key, json.loads(body(key + ':' + str(page), legacy.SZSE_API,
                                                                         legacy.parameters(key, page))), page, source_day)
                if next_meta != meta:
                    raise ValueError('independent risk-list pages changed')
                records.extend(extra)
            if len(records) != meta[0]:
                raise ValueError('incomplete independent risk-list total')
            pages = max(1, meta[1])
        rows.extend(records)
        groups.append({'group': key, 'venue': item['venue'], 'board': item['board'], 'kind': item['kind'],
                       'source_url': item['url'], 'source_as_of': source_day, 'source_rows': len(records),
                       'pages_read': pages, 'a_shares': sum(r['share_class'] == 'A' for r in records),
                       'b_shares': sum(r['share_class'] == 'B' for r in records)})
    if len(used) != len(refs) or len({r['ts_code'] for r in rows}) != len(rows):
        raise ValueError('extra page or duplicate independent membership')
    if not any(r['share_class'] == 'A' and r['kind'] == 'risk_warning' for r in rows):
        raise ValueError('empty independent risk-warning universe')
    return {'version': VERSION, 'availability': 'observed', 'observed_on': raw['observed_on'],
            'started_at': raw['started_at'], 'completed_at': raw['completed_at'], 'groups': groups,
            'rows': rows, 'responses': refs, 'common_source_as_of': None,
            'historical_membership_ready': False, 'historical_first_observation': False,
            'risk_warning_a_shares': sum(r['kind'] == 'risk_warning' and r['share_class'] == 'A' for r in rows),
            'delisting_a_shares': sum(r['kind'] == 'delisting' and r['share_class'] == 'A' for r in rows),
            'excluded_b_shares': sum(r['share_class'] == 'B' for r in rows),
            'note': '保留名单实际读取日和表内数据日；沪市未声明数据日，不据此回填盘中可得性。'}


def load(directory, *, now=None):
    now = now or datetime.now(timezone.utc)
    raw = json.loads((directory / 'current.json').read_text())
    if raw.get('version') == legacy.VERSION:
        result = legacy.list_status(directory, now=now)
        if result['availability'] != 'observed':
            raise ValueError('invalid legacy independent risk list')
        return result
    if digest({k: v for k, v in raw.items() if k != 'content_digest'}) != raw.get('content_digest'):
        raise ValueError('independent risk source bytes changed')
    return {**project(raw, directory, now), 'content_digest': raw['content_digest']}


def materialize_candidate(directory, *, now=None):
    """Admit acquired originals only after replay; retain all actual source times."""
    now = now or datetime.now(timezone.utc)
    candidate = json.loads((directory / 'candidate.json').read_text())
    if (candidate.get('version') != 'exchange_risk_observation_candidate_v2'
            or digest({k: v for k, v in candidate.items() if k != 'content_digest'}) != candidate.get('content_digest')):
        raise ValueError('unbound risk observation candidate')
    raw = {'version': VERSION, 'processor_digest': processor_digest(),
           'observed_on': legacy.local_day(datetime.fromisoformat(candidate['started_at'])),
           'started_at': candidate['started_at'], 'completed_at': candidate['completed_at'],
           'checked_at': now.isoformat(), 'responses': candidate['responses']}
    project(raw, directory, now)
    raw['content_digest'] = digest(raw)
    atomic_write_json(directory / 'snapshots' / (raw['content_digest'] + '.json'), raw)
    atomic_write_json(directory / 'current.json', raw)
    return load(directory, now=now)


def confirm_close(risk, rows, through, *, now=None):
    """Corroborate a closing classification; never claim an earlier observation."""
    now = now or datetime.now(timezone.utc)
    target = date.fromisoformat(through); observed = date.fromisoformat(risk['observed_on'])
    if (risk.get('version') != VERSION or risk.get('availability') != 'observed'
            or sessions_2026(target, target) != [through] or observed <= target
            or sessions_2026(target + timedelta(days=1), observed)):
        raise ValueError('later confirmation requires a nontrading day immediately after the close')
    started = datetime.fromisoformat(risk['started_at']); completed = datetime.fromisoformat(risk['completed_at'])
    buffer = datetime.combine(target, time(15, 30), ZoneInfo('Asia/Shanghai'))
    if (started.tzinfo is None or completed.tzinfo is None or now.tzinfo is None or not buffer < started <= completed <= now
            or legacy.local_day(started) != risk['observed_on'] or legacy.local_day(completed) != risk['observed_on']):
        raise ValueError('confirmation observation times changed')
    groups = risk['groups']
    if (len(groups) != len(legacy.GROUPS) or {g['group'] for g in groups} != set(legacy.GROUPS)
            or any(g['venue'] != legacy.GROUPS[g['group']]['venue'] for g in groups)
            or any(g['source_as_of'] != through for g in groups if g['venue'] == 'SZSE')
            or any(g['source_as_of'] is not None for g in groups if g['venue'] == 'SSE')):
        raise ValueError('independent source dates do not support this completed close')
    if not rows or any(r['trade_date'] != through for r in rows.values()):
        raise ValueError('mixed or empty closing day')
    members = {r['ts_code']: r['name'] for r in risk['rows'] if r['kind'] == 'risk_warning' and r['share_class'] == 'A'}
    flagged = {s: r['security_name'] for s, r in rows.items() if st_name(r['security_name'])}
    if (not members or set(members) != set(flagged)
            or any(re.sub(r'\s+', '', name) != re.sub(r'\s+', '', flagged[s]) for s, name in members.items())):
        raise ValueError('independent list and complete closing-name group differ')
    return {'version': RULE, 'through': through, 'observed_on': risk['observed_on'],
            'started_at': risk['started_at'], 'completed_at': risk['completed_at'],
            'risk_source_digest': risk['content_digest'], 'calendar_version': CALENDAR_VERSION,
            'calendar_source': CALENDAR_SOURCE,
            'source_dates': [{'group': g['group'], 'source_as_of': g['source_as_of']} for g in groups],
            'closing_names_digest': digest([{'symbol': s, 'name': flagged[s], 'date': through} for s in sorted(flagged)]),
            'member_count': len(members), 'historical_first_observation': False, 'historical_PIT': False,
            'note': through + '收盘名称与' + risk['observed_on'] + '实际读取的独立名单一致；深市表内日期为' + through +
                    '，沪市未声明数据日。用于收盘价格参考，不认定当日盘中已可取得名单。'}
