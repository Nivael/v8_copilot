from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import shutil

import pandas as pd
import pytest

from canonical_json import digest
from data_refresh import atomic_write_json
import trader_swing_reading as s
from test_exchange_risk_membership import archive
from test_market_close_membership import admitted, closes, DAY


@pytest.fixture
def inputs(archive, monkeypatch, tmp_path_factory):
    risk = admitted(archive, monkeypatch)
    directory = tmp_path_factory.mktemp('swing-membership')
    (directory / 'risk/responses').mkdir(parents=True)
    shutil.copyfile(archive[0] / 'current.json', directory / 'risk/current.json')
    for ref in risk['responses']:
        name = ref['response_sha256'] + '.raw'
        shutil.copyfile(archive[0] / 'responses' / name, directory / 'risk/responses' / name)
    rows = [{'日期Date': '20261106', '指数代码 Index Code': '000688', '交易所Exchange': '上海证券交易所',
             '成份券代码Constituent Code': str(688100 + n), '成份券名称Constituent Name': f'样本{n}'} for n in range(50)]
    star = directory / 'star50'; star.mkdir()
    raw = b'fixture original'; key = sha256(raw).hexdigest(); (star / (key + '.xls')).write_bytes(raw)
    url = 'https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/cons/000688cons.xls'
    ref = {'sha256': key, 'bytes': len(raw), 'url': url, 'response_url': url, 'observed_at': '2026-11-06T17:00:00Z'}
    atomic_write_json(star / 'current.json', ref)
    monkeypatch.setattr(pd, 'read_excel', lambda *a, **k: pd.DataFrame(rows))
    fresh = closes(risk)
    fresh.update({row['成份券代码Constituent Code'] + '.SH': {'security_name': row['成份券名称Constituent Name'], 'trade_date': DAY} for row in rows})
    return directory, risk, rows, ref, fresh


def test_explicit_dated_membership_keeps_both_original_source_clocks(inputs):
    directory, risk, _, ref, fresh = inputs
    st, stars, risk_key, star_key, confirmation = s.closing_members(directory, DAY, fresh, inputs=directory)
    assert len(st) == 5 and len(stars) == 50
    assert risk_key == risk['content_digest'] and star_key == ref['sha256']
    assert confirmation['through'] == DAY and confirmation['observed_on'] == '2026-11-07'
    assert confirmation['historical_PIT'] is False
    files = s.membership_files(directory)
    assert 'risk/current.json' in files and 'star50/current.json' in files
    assert all('snapshots' not in name and 'candidate' not in name for name in files)


@pytest.mark.parametrize('bad', ['date', 'index', 'venue', 'incomplete', 'duplicate', 'code', 'empty_name',
                               'name_mismatch', 'missing_close', 'wrong_url', 'redirect', 'future', 'naive', 'bytes', 'size'])
def test_exact_official_star50_file_and_closing_identity_are_required(inputs, bad):
    directory, _, rows, ref, fresh = inputs
    if bad == 'date': rows[0]['日期Date'] = '20261105'
    elif bad == 'index': rows[0]['指数代码 Index Code'] = '000300'
    elif bad == 'venue': rows[0]['交易所Exchange'] = '深圳证券交易所'
    elif bad == 'incomplete': rows.pop()
    elif bad == 'duplicate': rows[-1] = deepcopy(rows[0])
    elif bad == 'code': rows[0]['成份券代码Constituent Code'] = '000688.SH'
    elif bad == 'empty_name': rows[0]['成份券名称Constituent Name'] = ' '
    elif bad == 'name_mismatch': fresh['688100.SH']['security_name'] = '另一家'
    elif bad == 'missing_close': fresh.pop('688100.SH')
    elif bad == 'wrong_url': ref['url'] = 'https://example.com/'
    elif bad == 'redirect': ref['response_url'] = 'https://example.com/'
    elif bad == 'future': ref['observed_at'] = '2099-11-07T00:00:00Z'
    elif bad == 'naive': ref['observed_at'] = '2026-11-07T00:00:00'
    elif bad == 'bytes': (directory / 'star50' / (ref['sha256'] + '.xls')).write_bytes(b'changed')
    else: ref['bytes'] += 1
    atomic_write_json(directory / 'star50/current.json', ref)
    with pytest.raises(ValueError): s.closing_members(directory, DAY, fresh, inputs=directory)


def test_old_same_day_membership_is_not_inferred_from_a_later_confirmation(inputs, monkeypatch):
    import exchange_risk_membership
    monkeypatch.setattr(exchange_risk_membership, 'list_status', lambda *a, **k: {'availability': 'observed', 'observed_on': '2026-11-05'})
    with pytest.raises(ValueError, match='not independently observed'):
        s.closing_members(inputs[0], DAY, inputs[-1])


@pytest.mark.parametrize('bad', ['risk_name', 'risk_page', 'raw_file', 'intervening_day'])
def test_risk_confirmation_reuses_original_exact_source_gate(inputs, bad):
    directory, _, _, _, fresh = inputs
    if bad == 'risk_name': fresh['600001.SH']['security_name'] = 'ST不同'
    elif bad == 'risk_page':
        raw = json.loads((directory / 'risk/current.json').read_text()); raw['responses'].pop()
        raw['content_digest'] = digest({k: v for k, v in raw.items() if k != 'content_digest'})
        atomic_write_json(directory / 'risk/current.json', raw)
    elif bad == 'raw_file': next((directory / 'risk/responses').iterdir()).write_bytes(b'changed')
    through = '2026-11-05' if bad == 'intervening_day' else DAY
    with pytest.raises(ValueError): s.closing_members(directory, through, fresh, inputs=directory)


@pytest.mark.parametrize('bad', ['star_key', 'risk_key', 'symlink', 'missing_file'])
def test_input_copy_only_accepts_bound_regular_files(inputs, bad):
    directory, _, _, ref, _ = inputs
    if bad == 'star_key':
        ref['sha256'] = '../outside'; atomic_write_json(directory / 'star50/current.json', ref)
    elif bad == 'risk_key':
        raw = json.loads((directory / 'risk/current.json').read_text()); raw['responses'][0]['response_sha256'] = '../outside'
        atomic_write_json(directory / 'risk/current.json', raw)
    else:
        original = directory / 'star50' / (ref['sha256'] + '.xls')
        moved = directory / 'old.xls'; original.rename(moved)
        if bad == 'symlink': original.symlink_to(moved)
    with pytest.raises(ValueError): s.membership_files(directory)


def test_materializer_freezes_exact_sources_and_preserves_old_pointer_on_failure(inputs, tmp_path, monkeypatch):
    directory = inputs[0]
    before = s.membership_files(directory)
    def build(data, *, through, root, membership_inputs):
        assert membership_inputs != directory and s.membership_files(membership_inputs) == before
        return {'as_of': through, 'source_digests': {'membership_inputs': digest(before)},
                'membership_confirmation': {'through': through}}
    monkeypatch.setattr(s, 'build', build)
    value = s.materialize({}, DAY, membership_inputs=directory, output=tmp_path)
    assert value['version'] == s.DATED_VERSION and value['membership_input_digest'] == digest(before)
    assert s.load(tmp_path)['as_of'] == DAY
    path = tmp_path / 'current.json'; old = path.read_bytes()
    def fail(*a, **k): raise ValueError('source cannot be replayed')
    monkeypatch.setattr(s, 'build', fail)
    with pytest.raises(ValueError, match='cannot be replayed'): s.materialize({}, DAY, membership_inputs=directory, output=tmp_path)
    assert path.read_bytes() == old


@pytest.mark.parametrize('bad', ['missing_binding', 'mismatch', 'legacy_mode'])
def test_new_packet_cannot_hide_its_dated_membership_mode(tmp_path, bad):
    value = {'version': s.DATED_VERSION, 'processor_digest': s.processor_digest(), 'membership_input_digest': 'a' * 64,
             'data': {'as_of': DAY, 'source_digests': {'membership_inputs': 'a' * 64}, 'membership_confirmation': {'through': DAY}}}
    if bad == 'missing_binding': value.pop('membership_input_digest')
    elif bad == 'mismatch': value['data']['source_digests']['membership_inputs'] = 'b' * 64
    else: value['version'] = s.VERSION
    value['content_digest'] = digest(value); atomic_write_json(tmp_path / 'current.json', value)
    assert s.load(tmp_path) == {'availability': 'updating'}
