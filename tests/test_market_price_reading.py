from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from urllib.parse import urlencode

import pytest

from canonical_json import digest
from market_public_refresh import parse_index_perf
from market_risk import CSI_PERF_URL, INDEX_BASKET
import market_price_reading as m

NOW = datetime(2026, 11, 6, 11, 30, tzinfo=timezone.utc)


class Client:
    def __init__(self, directory, *, missing=False, future=False, before_close=False):
        self.directory = directory
        self.missing, self.future, self.before_close = missing, future, before_close
        self.calls = 0

    def get_index(self, code, calendar):
        self.calls += 1
        data = [{'indexCode': code[:6], 'tradeDate': day.replace('-', ''), 'close': 100 + i, 'tradingValue': 10}
                for i, day in enumerate(calendar) if not (self.missing and code == '000300.SH' and i == 12)]
        raw = json.dumps({'code': '200', 'data': data}).encode()
        key = sha256(raw).hexdigest()
        folder = self.directory / 'responses'; folder.mkdir(exist_ok=True, parents=True)
        (folder / (key + '.json')).write_bytes(raw)
        observed = NOW + timedelta(seconds=1) if self.future else NOW.replace(hour=6) if self.before_close else NOW
        url = CSI_PERF_URL + '?' + urlencode({'indexCode': code[:6], 'startDate': calendar[0].replace('-', ''), 'endDate': calendar[-1].replace('-', '')})
        return parse_index_perf(json.loads(raw), code, calendar), {'code': code, 'url': url, 'response_sha256': key,
                'observed_at': observed.isoformat(), 'reported_amount_unit': 'CNY100M', 'normalized_amount_unit': 'CNY'}


def base(packet):
    points = packet['indices']['000985.CSI'][-42:-1]
    return {'as_of': points[-1]['trade_date'], 'chart': [{'key': 'market', 'points': [{'date': p['trade_date'], 'value': p['close']} for p in points]}],
            'metrics': {'st_change_pct': -3}, 'headline': '旧判断', 'etf': {'as_of': '2026-11-05'}}


def ready(tmp_path):
    packet = m.publish(Client(tmp_path), through='2026-11-06', directory=tmp_path, now=NOW)
    return packet, base(packet)


def test_independent_post_close_prices_preserve_the_common_st_etf_basis(tmp_path):
    packet, current = ready(tmp_path); original = deepcopy(current)
    result = m.newer_price(current, directory=tmp_path, now=NOW)
    assert len(packet['indices']) == len(INDEX_BASKET) == 3
    assert result['as_of'] == '2026-11-06' and current['as_of'] == '2026-11-05'
    assert result['metrics']['day_change_pct'] == pytest.approx((160 / 159 - 1) * 100)
    assert result['metrics']['five_day_change_pct'] == pytest.approx((160 / 155 - 1) * 100)
    assert result['metrics']['twenty_day_change_pct'] == pytest.approx((160 / 140 - 1) * 100)
    assert result['headline'] == '短中期走势同向回升'
    assert current == original and 'st_change_pct' not in result['metrics']
    assert (tmp_path / 'snapshots' / (packet['content_digest'] + '.json')).is_file()


@pytest.mark.parametrize('through,now', [
    ('2026-11-06', NOW.replace(hour=7, minute=29)),
    ('2026-11-09', NOW),
    ('2026-11-07', NOW + timedelta(days=1)),
    ('2026-11-06', NOW.replace(tzinfo=None)),
])
def test_early_future_non_session_and_naive_publication_never_fetch(through, now, tmp_path):
    client = Client(tmp_path)
    with pytest.raises(ValueError): m.publish(client, through=through, directory=tmp_path, now=now)
    assert client.calls == 0 and not (tmp_path / 'current.json').exists()


@pytest.mark.parametrize('failure', ['missing', 'future', 'before_close'])
def test_incomplete_or_ineligible_sources_preserve_the_last_publication(failure, tmp_path):
    ready(tmp_path); before = (tmp_path / 'current.json').read_bytes()
    with pytest.raises(ValueError):
        m.publish(Client(tmp_path, **{failure: True}), through='2026-11-06', directory=tmp_path, now=NOW)
    assert (tmp_path / 'current.json').read_bytes() == before


@pytest.mark.parametrize('change', ['calendar', 'index_identity', 'duplicate_ref', 'url', 'units', 'future', 'intraday', 'rows', 'scope', 'sha_path'])
def test_edited_source_bindings_cannot_override_the_common_reading(change, tmp_path):
    packet, current = ready(tmp_path)
    if change == 'calendar': packet['calendar'].pop(1)
    elif change == 'index_identity': packet['responses'][0]['code'] = '123456.SH'
    elif change == 'duplicate_ref': packet['responses'][0] = packet['responses'][1]
    elif change == 'url': packet['responses'][0]['url'] += '&extra=1'
    elif change == 'units': packet['responses'][0]['normalized_amount_unit'] = 'CNY100M'
    elif change == 'future': packet['responses'][0]['observed_at'] = (NOW + timedelta(seconds=1)).isoformat()
    elif change == 'intraday': packet['responses'][0]['observed_at'] = NOW.replace(hour=6).isoformat()
    elif change == 'rows': packet['indices']['000985.CSI'][-1]['close'] += 1
    elif change == 'scope': packet['scope'] = 'entire_market'
    else: packet['responses'][0]['response_sha256'] = '../unknown'
    packet.pop('content_digest'); packet['content_digest'] = digest(packet)
    (tmp_path / 'current.json').write_text(json.dumps(packet))
    assert m.newer_price(current, directory=tmp_path, now=NOW) is None


def test_edited_raw_bytes_or_revised_common_history_do_not_enter_latest_judgment(tmp_path):
    packet, current = ready(tmp_path)
    changed = deepcopy(current); changed['chart'][0]['points'][-1]['value'] += 1
    assert m.newer_price(changed, directory=tmp_path, now=NOW) is None
    path = tmp_path / 'responses' / (packet['responses'][0]['response_sha256'] + '.json')
    path.write_bytes(path.read_bytes() + b' ')
    assert m.newer_price(current, directory=tmp_path, now=NOW) is None


def test_missing_equal_or_older_prices_do_not_change_the_base(tmp_path):
    assert m.newer_price({'as_of': '2026-11-05'}, directory=tmp_path, now=NOW) is None
    packet, current = ready(tmp_path); current['as_of'] = packet['through']
    assert m.newer_price(current, directory=tmp_path, now=NOW) is None
    current['as_of'] = '2026-11-09'
    assert m.newer_price(current, directory=tmp_path, now=NOW) is None


@pytest.mark.parametrize('day,week,month,headline', [
    (-1, -2, -3, '大盘风险仍偏高，短期压力尚在'),
    (1, -2, -3, '大盘风险仍偏高，反弹尚未改变近月弱势'),
    (-1, -2, 3, '近月回升，短线仍有反复'),
    (None, None, None, '方向仍不清晰，先看已有的价格变化'),
])
def test_price_judgment_separates_rebound_and_continuing_weakness(day, week, month, headline):
    assert m.price_judgment(day, week, month)[0] == headline
