from pathlib import Path
import gzip
import json
import pytest
from canonical_json import digest
from st_initial_tenth_four import initial_tenth_four


def fixture():
    return json.loads(gzip.decompress((Path(__file__).parent / 'fixtures/st-initial-tenth-four.json.gz').read_bytes()))


def test_selection_coverage_and_unavailable_comparisons_remain_visible():
    data = fixture()
    result = initial_tenth_four(data, data['test_prior'], data['test_current'])
    assert result['counts']['after'] == 82
    assert [r['symbol'] for r in result['rows']] == ['002726', '002731', '002789', '002816']
    cuihua = result['rows'][1]
    assert all(c['stock_pct'] is None and c['gap'] for c in cuihua['comparisons'].values())
    assert '其他ST' in result['rows'][2]['known_at_anchor']
    assert all(w['return_pct'] is None for w in result['quote_audit']['stock_reviews'][1]['windows'])


@pytest.mark.parametrize('bad', ['history', 'order', 'date', 'text', 'file', 'review', 'market', 'audit'])
def test_resealed_packet_cannot_change_sources_or_comparison_basis(bad):
    data = fixture()
    p = data['initial_tenth_four']
    if bad == 'history':
        data['test_prior']['inventory'][0]['name'] = 'changed'
    elif bad == 'order':
        p['selection'].reverse()
    elif bad == 'date':
        p['sources'][0]['published_on'] = '2026-07-04'
    elif bad == 'text':
        p['sources'][0]['selected_pages']['1'] = 'changed'
    elif bad == 'file':
        p['sources'][0]['sha256'] = 'changed'
    elif bad == 'review':
        p['visual_read'].pop()
    elif bad == 'market':
        data['current_extension']['market_inputs']['through'] = '2026-11-20'
    elif bad == 'audit':
        p['endpoint_review_digest'] = 'changed'
    p['content_digest'] = digest({k: v for k, v in p.items() if k != 'content_digest'})
    with pytest.raises(ValueError):
        initial_tenth_four(data, data['test_prior'], data['test_current'])


def test_absent_packet_preserves_old_reader():
    assert initial_tenth_four({}, None, None) is None
