from copy import deepcopy
from datetime import datetime, timezone

import pytest

from canonical_json import digest
from data_refresh import atomic_write_json
import market_reading_updates as u


def inputs():
    rows = {s: {'security_name': name, 'trade_date': '2026-11-05', 'is_trading': True,
                'last': close, 'prev_close': 10} for s, name, close in
            [('600001.SH', '*ST甲', 11), ('000001.SZ', 'ST乙', 9), ('000002.SZ', 'ST丙', 9)]}
    risk = {'availability': 'observed', 'observed_on': '2026-11-05', 'content_digest': 'a' * 64,
            'rows': [{'ts_code': s, 'name': r['security_name'], 'kind': 'risk_warning', 'share_class': 'A'} for s, r in rows.items()]}
    metric = {'member_count': 3, 'observed_members': 3, 'coverage_ratio': 1, 'close': 1000}
    base = {'availability': 'reconstructed', 'through': '2026-11-04', 'start': '2026-11-03', 'coverage_threshold': .95,
            'historical_membership_verified': False, 'combined_ST_ready': False, 'historical_PIT': False,
            'content_digest': 'b' * 64, 'metrics': {},
            'points': [{'date': day, **{g: deepcopy(metric) for g in ('all', 'SSE', 'SZSE')}}
                       for day in ('2026-11-03', '2026-11-04')]}
    return base, rows, risk


def test_st_daily_mean_weights_members_not_the_two_venue_means():
    base, rows, risk = inputs(); before = deepcopy(base)
    result = u.extend_st(base, rows, risk, '2026-11-05', ['2026-11-03', '2026-11-04', '2026-11-05'])
    assert base == before
    assert result['points'][-1]['all']['daily_return_pct'] == pytest.approx(-10 / 3)
    assert result['points'][-1]['all']['close'] == pytest.approx(966.66666667)
    assert result['points'][-1]['SSE']['close'] == 1100
    assert result['points'][-1]['SZSE']['close'] == 900
    assert result['historical_membership_verified'] is False
    assert result['combined_ST_ready'] is False and result['historical_PIT'] is False
    assert result['base_reference_digest'] == before['content_digest']
    assert result['content_digest'] != before['content_digest']


@pytest.mark.parametrize('change', ['missing_member', 'wrong_name', 'wrong_day', 'undated_list', 'unavailable_list'])
def test_risk_membership_must_agree_with_complete_dated_closing_names(change):
    base, rows, risk = inputs()
    if change == 'missing_member': risk['rows'].pop()
    if change == 'wrong_name': risk['rows'][0]['name'] = '*ST另'
    if change == 'wrong_day': rows['600001.SH']['trade_date'] = '2026-11-04'
    if change == 'undated_list': risk['observed_on'] = '2026-11-04'
    if change == 'unavailable_list': risk['availability'] = 'invalid'
    with pytest.raises(ValueError):
        u.extend_st(base, rows, risk, '2026-11-05', ['2026-11-03', '2026-11-04', '2026-11-05'])


def test_nontrading_members_remain_missing_and_each_venue_keeps_the_coverage_gate():
    base, rows, risk = inputs()
    rows['600001.SH'].update(is_trading=False, last=None, prev_close=None)
    with pytest.raises(ValueError, match='coverage'):
        u.extend_st(base, rows, risk, '2026-11-05', ['2026-11-03', '2026-11-04', '2026-11-05'])


def test_missing_common_day_and_skipped_session_are_rejected():
    base, rows, risk = inputs()
    with pytest.raises(ValueError, match='missing common'):
        u.extend_st(base, rows, risk, '2026-11-05', ['2026-11-02', '2026-11-03', '2026-11-04', '2026-11-05'])
    with pytest.raises(ValueError, match='next trading'):
        u.next_session('2026-11-04', '2026-11-06')


def test_completed_close_update_rejects_today_before_reading_sources(tmp_path):
    with pytest.raises(ValueError, match='completed'):
        u.project_step({'requested_through': '2026-11-04'}, [], tmp_path, '2026-11-05',
                       now=datetime(2026, 11, 5, 8, tzinfo=timezone.utc))


def test_watch_append_preserves_suspension_gap_and_never_duplicates_the_old_day():
    base, rows, _ = inputs()
    bases = [{'availability': 'available', 'symbol': '600001.SH', 'as_of': base['through'],
              'prices': [{'date': '2026-11-04', 'close': 10, 'previous_close': 10, 'is_trading': True}]}]
    before = deepcopy(bases)
    rows['600001.SH']['is_trading'] = False
    result = u.extend_watch(bases, rows, '2026-11-04', '2026-11-05')
    assert bases == before and len(result[0]['prices']) == 2
    assert result[0]['prices'][-1] == {'date': '2026-11-05', 'close': None, 'previous_close': None, 'is_trading': False}
    with pytest.raises(ValueError, match='follow'):
        u.extend_watch(result, rows, '2026-11-04', '2026-11-05')


def test_update_pointer_is_bound_to_base_and_cannot_select_an_arbitrary_source_path(tmp_path):
    data = {'requested_through': '2026-11-04', 'snapshot_digest': 'c' * 64}
    raw = {'version': u.VERSION, 'processor_digest': u.processor_digest(), 'base_binding': u.base_binding(data),
           'checked_at':'2026-11-06T00:00:00Z', 'through': '2026-11-05', 'steps': [{'through': '2026-11-05', 'source_digest': '../other'}]}
    raw['content_digest'] = digest(raw); atomic_write_json(tmp_path / 'current.json', raw)
    with pytest.raises(ValueError, match='source identity'):
        u.load_update(data, [], output=tmp_path)
    data['snapshot_digest'] = 'd' * 64
    with pytest.raises(ValueError, match='base or implementation'):
        u.load_update(data, [], output=tmp_path)


def test_source_corrections_are_detected_even_if_the_pointer_is_rehashed(tmp_path):
    data = {'requested_through': '2026-11-04', 'snapshot_digest': 'c' * 64}
    folder = tmp_path / 'sources' / ('e' * 64)
    for name in u.SOURCE_FOLDERS:
        (folder / name).mkdir(parents=True)
        (folder / name / 'current.json').write_text('{}')
    raw = {'version': u.VERSION, 'processor_digest': u.processor_digest(), 'base_binding': u.base_binding(data),
           'checked_at':'2026-11-06T00:00:00Z', 'through': '2026-11-05', 'steps': [{'through': '2026-11-05', 'source_digest': 'e' * 64}]}
    raw['content_digest'] = digest(raw); atomic_write_json(tmp_path / 'current.json', raw)
    with pytest.raises(ValueError, match='source bytes changed'):
        u.load_update(data, [], output=tmp_path)


def test_no_update_is_an_explicit_base_reading(tmp_path):
    assert u.load_update({}, [], output=tmp_path) is None


def test_revalidation_cannot_bless_changed_source_bytes(tmp_path):
    data = {'requested_through': '2026-11-04', 'snapshot_digest': 'c' * 64}
    raw = {'version': u.VERSION, 'processor_digest': 'old implementation', 'base_binding': u.base_binding(data),
           'checked_at':'2026-11-06T00:00:00Z', 'through':'2026-11-05',
           'steps':[{'through':'2026-11-05','source_digest':'e'*64}]}
    raw['content_digest']=digest(raw);atomic_write_json(tmp_path/'current.json',raw)
    with pytest.raises(ValueError,match='explicit revalidation'):
        u.load_update(data,[],output=tmp_path)
    folder=tmp_path/'sources'/('e'*64)
    for name in u.SOURCE_FOLDERS:
        (folder/name).mkdir(parents=True);(folder/name/'current.json').write_text('{}')
    with pytest.raises(ValueError,match='source bytes changed'):
        u.revalidate(data,[],output=tmp_path)
    assert (tmp_path/'current.json').read_text()==json_text(raw)


def json_text(value):
    import json
    return json.dumps(value,ensure_ascii=False,indent=2)+'\n'


def test_future_publication_clock_is_rejected_before_sources(tmp_path):
    data={'requested_through':'2026-11-04','snapshot_digest':'c'*64}
    raw={'version':u.VERSION,'processor_digest':u.processor_digest(),'base_binding':u.base_binding(data),
         'checked_at':'2099-01-01T00:00:00Z','through':'2026-11-05','steps':[]}
    raw['content_digest']=digest(raw);atomic_write_json(tmp_path/'current.json',raw)
    with pytest.raises(ValueError,match='publication time'):
        u.load_update(data,[],output=tmp_path)
