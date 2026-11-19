from pathlib import Path
import gzip
import json
from hashlib import sha256
import pytest
from st_quote_endpoint_review import review_stock_endpoints


def fixture():
    return json.loads(gzip.decompress((Path(__file__).parent / 'fixtures/st-tenth-endpoint-review.json.gz').read_bytes()))


def test_real_missing_and_conflicting_prices_never_become_zero_returns():
    rows = review_stock_endpoints(**fixture())
    cuihua = next(r for r in rows if r['symbol'] == '002731')
    assert [p['status'] for p in cuihua['points']] == ['no_actual_trade_endpoint', 'price_basis_conflict', 'no_actual_trade_endpoint']
    assert all(w['return_pct'] is None and w['gaps'] for w in cuihua['windows'])
    other = [r for r in rows if r['symbol'] != '002731']
    assert all(p['status'] == 'matched' for r in other for p in r['points'])
    assert other[0]['windows'][0]['return_pct'] == pytest.approx((2.17 / 1.34 - 1) * 100)


def test_cross_channel_actual_trade_cannot_rescue_missing_provider():
    data = fixture()
    data['prices'] = [r for r in data['prices'] if (r['symbol'], r['trade_date']) != ('002726', '2026-07-03')]
    row = review_stock_endpoints(**data)[0]
    assert row['points'][0]['status'] == 'availability_conflict'
    assert all(w['return_pct'] is None for w in row['windows'])


def test_reference_close_does_not_count_as_a_trade():
    data = fixture()
    next(r for r in data['prices'] if r['symbol'] == '002726')['has_trade'] = False
    assert review_stock_endpoints(**data)[0]['points'][0]['status'] == 'availability_conflict'


@pytest.mark.parametrize('bad', ['bytes', 'identity', 'scope', 'duplicate', 'future'])
def test_invalid_sources_fail_even_when_resealed(bad):
    data = fixture()
    s = data['sources'][0]
    raw = json.loads(s['text'])
    block = raw['data'][s['key']]
    if bad == 'bytes':
        s['sha256'] = 'wrong'
    elif bad == 'scope':
        data['sources'].pop()
    else:
        rows = block.get('qfqday') or block['day']
        if bad == 'identity':
            block['qt'][s['key']][2] = '999999'
        elif bad == 'duplicate':
            rows.append(rows[0])
        elif bad == 'future':
            rows[-1][0] = '2026-11-20'
        s['text'] = json.dumps(raw)
        s['sha256'] = sha256(s['text'].encode()).hexdigest()
    with pytest.raises(ValueError):
        review_stock_endpoints(**data)
