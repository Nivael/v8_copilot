from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlencode

import pytest

from canonical_json import digest
from data_refresh import atomic_write_json
from market_calendar import sessions_2026
from research_history import assemble, question_digest, review_anchor
from research_history_reviews import freeze_review
import research_history_prefix as prefix


def seal(value):
    value['content_digest'] = digest({k: v for k, v in value.items() if k != 'content_digest'})
    return value


def fixture(root):
    import research_history_prices
    days = sessions_2026(date(2026, 3, 20), date(2026, 5, 15))
    join = '2026-03-25'; early = days[:days.index(join) + 1]; old_days = days[days.index(join):]
    prices = {d: Decimal(10) + Decimal(i) / 10 for i, d in enumerate(days)}
    def points(factor):
        return [{'date': d, 'value': float(prices[d] * factor), 'level': float(prices[d] / prices[join] * 100)} for d in old_days]
    stock = points(1)
    for p in stock:
        p['basis'] = 'historical_qfq'
    stock[8].update(value=None, level=None, basis='not_trading')
    data = {'calendar': old_days, 'stocks': {'002713.SZ': {'name': '示例甲', 'as_of': old_days[-1], 'points': stock},
            '000001.SZ': {'name': '示例乙', 'as_of': old_days[-1], 'points': deepcopy(stock)}},
            'market': points(100), 'st': points(50), 'st_name': 'ST板块（东财）',
            'st_source_url': 'https://quote.eastmoney.com/bk/90.BK0511.html', 'st_note': '独立板块参考',
            'source_digests': {'old': 'a' * 64}}
    base = seal({'version': 'research_history_paths_v1', 'processor_digest': sha256(Path(research_history_prices.__file__).read_bytes()).hexdigest(), 'data': data})
    atomic_write_json(root / 'price_paths/history' / (base['content_digest'] + '.json'), base)
    folder = root / 'inputs/calendar_prefix_v1'; folder.mkdir(parents=True)
    stamp = datetime.now(timezone.utc).isoformat()
    def raw(value, url=None):
        body = json.dumps(value, ensure_ascii=False).encode(); key = sha256(body).hexdigest()
        (folder / (key + '.json')).write_bytes(body)
        return {'sha256': key, 'bytes': len(body), 'observed_at': stamp, **({'url': url, 'response_url': url} if url else {})}
    market = {'code': '200', 'data': [{'tradeDate': d.replace('-', ''), 'indexCode': '000985',
              'close': float(prices[d] * 100), 'changePct': 0 if i == 0 else round(float((prices[d] / prices[early[i-1]] - 1) * 100), 2)} for i, d in enumerate(early)]}
    st = {'rc': 0, 'data': {'code': 'BK0511', 'name': 'ST股', 'klines': [
        ','.join([d, str(prices[d] * 50), str(prices[d] * 50), str(prices[d] * 50 + 1), str(prices[d] * 50 - 1), '100', '1000', '1',
                  '0' if i == 0 else str(round((prices[d] / prices[early[i-1]] - 1) * 100, 2)), '0', '1']) for i, d in enumerate(early)]}}
    stock_rows = [[d, str(prices[d]), str(prices[d]), str(prices[d] + 1), str(prices[d] - 1), '123.000'] for d in days if d != stock[8]['date']]
    quote = {'code': 0, 'data': {'sz002713': {'qt': {'sz002713': ['', '示例甲', '002713']}, 'qfqday': stock_rows}}}
    query = "select symbol,trade_date,close,volume,pct_change,source from daily_prices where adjust='qfq' and symbol in ('002713') and trade_date between '2026-03-20' and '2026-03-25' order by symbol,trade_date"
    sql = seal({'version': 'research_history_sql_selection_v1', 'source_file': 'source.sqlite3', 'query': query, 'observed_at': stamp,
                'rows': [{'symbol': '002713', 'trade_date': d, 'close': float(prices[d]), 'volume': 123.12, 'pct_change': 0,
                          'source': 'tushare:daily+adj_factor:qfq'} for d in early]})
    market_url = 'https://www.csindex.com.cn/csindex-home/perf/index-perf?' + urlencode({'indexCode': '000985', 'startDate': '20260320', 'endDate': '20260325'})
    st_url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get?' + urlencode({'secid': '90.BK0511', 'klt': '101', 'fqt': '0', 'beg': '20260320', 'end': '20260325', 'fields1': 'f1,f2,f3,f4,f5,f6', 'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61'})
    stock_url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?' + urlencode({'param': f'sz002713,day,2026-03-20,{old_days[-1]},640,qfq'})
    source = seal({'version': prefix.SOURCE_VERSION, 'start': days[0], 'join': join, 'through': old_days[-1], 'symbols': ['002713.SZ'],
                   'sources': {'market': raw(market, market_url), 'st': raw(st, st_url), '002713.SZ': raw(quote, stock_url), 'local_qfq': raw(sql)}})
    atomic_write_json(folder / (source['content_digest'] + '.json'), source)
    return base, source, folder


def build(root):
    base, source, folder = fixture(root)
    return base, prefix.extension_packet(base, source['content_digest'], root=root), source, folder


def test_earlier_sessions_preserve_all_retained_points_and_leave_uncovered_subjects_missing(tmp_path):
    base, packet, _, _ = build(tmp_path)
    data = packet['data']; old = base['data']; n = 3
    assert data['calendar'][:4] == ['2026-03-20', '2026-03-23', '2026-03-24', '2026-03-25']
    assert data['stocks']['002713.SZ']['points'][0]['value'] == 10
    assert data['stocks']['002713.SZ']['points'][0]['level'] == pytest.approx(10 / 10.3 * 100)
    for key in ['market', 'st']:
        assert data[key][n:] == old[key]
    for key in old['stocks']:
        assert data['stocks'][key]['points'][n:] == old['stocks'][key]['points']
    assert all(p['value'] is None and p['level'] is None for p in data['stocks']['000001.SZ']['points'][:n])
    prefix.validate_price_packet(packet, root=tmp_path)


def test_earlier_context_preserves_an_assessed_window_and_recovers_an_earlier_question_anchor(tmp_path):
    base, packet, _, _ = build(tmp_path)
    record = {'id': 'q', 'kind': 'original_question', 'asked_at': '2026-03-26T08:00:00Z', 'question': '核对公告',
              'symbols': ['002713.SZ'], 'answers': [{'text': '先核正式受理'}], 'sources': []}
    review = freeze_review({'question_digest': question_digest(record), 'then_quote': '先核正式受理'}, record, base['data'], '2026-03-26')
    old = assemble([record], base['data'], reviews={'q': review})['details']['002713.SZ']['questions'][0]
    new = assemble([record], packet['data'], reviews={'q': review})['details']['002713.SZ']['questions'][0]
    assert new['review'] == old['review'] and new['review_status'] == 'current' and new['outcomes'] == old['outcomes']
    record['asked_at'] = '2026-03-22T11:00:00Z'
    assert review_anchor(record, {}, base['data']) is None
    assert review_anchor(record, {}, packet['data']) == '2026-03-20'


@pytest.mark.parametrize('change', ['market_identity', 'market_return', 'st_identity', 'st_return', 'stock_identity', 'stock_gap', 'stock_order', 'stock_close', 'stock_metadata', 'sql_close', 'sql_volume', 'sql_identity', 'future', 'wrong_url', 'missing_raw'])
def test_even_rehashed_sources_require_identity_complete_sessions_consistent_returns_and_cross_source_agreement(tmp_path, change):
    base, source, folder = fixture(tmp_path)
    key = 'market' if change.startswith('market') else 'st' if change.startswith('st_') else 'local_qfq' if change.startswith('sql_') else '002713.SZ'
    ref = source['sources'][key]; path = folder / (ref['sha256'] + '.json'); value = json.loads(path.read_text())
    if change == 'market_identity': value['data'][0]['indexCode'] = '000300'
    elif change == 'market_return': value['data'][1]['changePct'] = 9
    elif change == 'st_identity': value['data']['code'] = 'BK0000'
    elif change == 'st_return': value['data']['klines'][1] = value['data']['klines'][1].replace(',1.00,', ',8.00,')
    elif change == 'stock_identity': value['data']['sz002713']['qt']['sz002713'][2] = '300472'
    elif change == 'stock_gap': value['data']['sz002713']['qfqday'].pop(1)
    elif change == 'stock_order': value['data']['sz002713']['qfqday'][1:3] = reversed(value['data']['sz002713']['qfqday'][1:3])
    elif change == 'stock_close': value['data']['sz002713']['qfqday'][0][2] = '10.1'
    elif change == 'stock_metadata': value['data']['sz002713']['qfqday'][0].append({'unreviewed': 'split'})
    elif change == 'sql_close': value['rows'][0]['close'] = 10.1; seal(value)
    elif change == 'sql_volume': value['rows'][0]['volume'] = 124.12; seal(value)
    elif change == 'sql_identity': value['rows'][0]['symbol'] = '300472'; seal(value)
    elif change == 'future': ref['observed_at'] = '2999-01-01T00:00:00Z'
    elif change == 'wrong_url': ref['url'] += '&identity=other'
    elif change == 'missing_raw': path.rename(path.with_suffix('.retained'))
    if change not in {'future', 'wrong_url', 'missing_raw'}:
        raw = json.dumps(value).encode(); ref['sha256'] = sha256(raw).hexdigest(); ref['bytes'] = len(raw)
        (folder / (ref['sha256'] + '.json')).write_bytes(raw)
    seal(source); atomic_write_json(folder / (source['content_digest'] + '.json'), source)
    with pytest.raises((ValueError, FileNotFoundError)):
        prefix.extension_packet(base, source['content_digest'], root=tmp_path)


@pytest.mark.parametrize('change', ['retained_stock', 'retained_market', 'earlier_stock', 'unknown_stock', 'calendar', 'source', 'processor', 'missing_base'])
def test_rehashed_packet_cannot_change_old_points_invent_prices_or_bypass_original_sources(tmp_path, monkeypatch, change):
    base, packet, _, _ = build(tmp_path)
    if change == 'retained_stock': packet['data']['stocks']['002713.SZ']['points'][-1]['level'] += 1
    elif change == 'retained_market': packet['data']['market'][-1]['value'] += 1
    elif change == 'earlier_stock': packet['data']['stocks']['002713.SZ']['points'][0]['value'] += 1
    elif change == 'unknown_stock': packet['data']['stocks']['000001.SZ']['points'][0].update(value=1, level=100)
    elif change == 'calendar': packet['data']['calendar'].pop(0)
    elif change == 'source': packet['calendar_extension']['source_digest'] = 'f' * 64; seal(packet['calendar_extension'])
    elif change == 'processor': monkeypatch.setattr(prefix, 'processor_digest', lambda: 'f' * 64)
    else: (tmp_path / 'price_paths/history' / (base['content_digest'] + '.json')).rename(tmp_path / 'retained-base.json')
    seal(packet)
    with pytest.raises((ValueError, FileNotFoundError)):
        prefix.validate_price_packet(packet, root=tmp_path)


def test_subject_addition_after_a_calendar_prefix_still_replays_the_calendar_ancestor(tmp_path):
    from research_history_subjects import extension_packet
    _, packet, _, folder = build(tmp_path)
    atomic_write_json(tmp_path / 'price_paths/history' / (packet['content_digest'] + '.json'), packet)
    added = deepcopy(packet['data']); added['stocks']['600549.SH'] = deepcopy(added['stocks']['002713.SZ'])
    added['source_digests']['new_subject'] = 'd' * 64
    later = extension_packet(packet, added, root=tmp_path)
    prefix.validate_price_packet(later, root=tmp_path)
    source = packet['calendar_extension']['source_digest']
    (folder / (source + '.json')).rename(folder / 'retained-source.json')
    with pytest.raises(FileNotFoundError):
        prefix.validate_price_packet(later, root=tmp_path)


def test_publisher_rejects_modified_prefix_before_writing_import_or_published_history(tmp_path):
    from research_history import publish
    _, packet, _, _ = build(tmp_path)
    packet['data']['st'][0]['level'] += 1; seal(packet)
    atomic_write_json(tmp_path / 'price_paths/current.json', packet)
    with pytest.raises(ValueError, match='calendar extension'):
        publish({'records': [], 'sources': []}, root=tmp_path)
    assert not (tmp_path / 'imports').exists() and not (tmp_path / 'current.json').exists()
