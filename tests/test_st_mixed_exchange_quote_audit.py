from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import gzip,json
import pytest
from st_initial_four import quote_audit

def packet():
    return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-mixed-exchange-quote-audit.json.gz').read_bytes()))

def test_mixed_exchange_actual_endpoints_use_their_own_exchange():
    p=packet();codes=[c for c in p['codes']if c!='600079']
    sources=[s for s in p['sources']if s['key']!='sh600079']
    r=quote_audit(sources,p['market'],codes=codes)
    assert r['stock_endpoint_points']==9
    assert r['index_endpoint_points_at_official_precision']==6
    assert {s['key']for s in r['source_refs']}=={'sz002932','sh600053','sh600080','000985','932000'}

def test_renfu_rounded_quote_is_not_silently_accepted_as_exact():
    p=packet()
    with pytest.raises(ValueError,match='qfq endpoint conflict'):
        quote_audit(p['sources'],p['market'],codes=p['codes'])

def test_same_digits_with_wrong_exchange_do_not_pass_identity_check():
    p=packet();s=next(s for s in p['sources']if s['key']=='sh600053');s['url']=s['url'].replace('sh600053','sz600053')
    with pytest.raises(ValueError,match='identity changed'):
        quote_audit(p['sources'],p['market'],codes=p['codes'])


def test_review_retains_actual_prices_and_unresolved_precision_or_basis_difference():
    from st_quote_endpoint_review import review_stock_endpoints
    p=packet();before=deepcopy(p)
    r=review_stock_endpoints([s for s in p['sources']if s['key']not in ['000985','932000']],p['market']['fixed_prices'],p['codes'],['2026-07-03','2026-07-31','2026-11-19'])
    assert p==before
    renfu=next(v for v in r if v['symbol']=='600079')
    assert [v['status']for v in renfu['points']]==['price_basis_conflict','price_basis_conflict','matched']
    assert renfu['points'][0]['provider_close']==17.29380942981411
    assert renfu['points'][0]['cross_close']=='17.290'
    assert all(v['return_pct'] is None and v['gaps']for v in renfu['windows'])
    assert all(v['status']=='matched'for c in r if c['symbol']!='600079'for v in c['points'])
