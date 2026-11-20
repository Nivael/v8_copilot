from pathlib import Path
import json
from market_limit_scope_audit import build


def test_official_identity_audit_replays_all_nine_days_without_prefix_loss():
    e=build()
    assert e==json.loads(Path('MARKET_LIMIT_SCOPE_AUDIT_2026_11_21.json').read_text())
    assert len(e['days'])==9
    assert len(e['source_refs'])==18
    assert all(d['official_trading']==d['provider_trading_in_official_set']==d['paired']for d in e['days'])
    assert all(not d['missing'] and not d['unpaired'] and not d['official_close_or_reference_conflicts']for d in e['days'])
    assert all(d['naive_prefix_omissions']==['302132.SZ']for d in e['days'])
    assert sum(d['paired']for d in e['days'])==46957
    assert max(e['days'],key=lambda d:d['limit_counts_in_paired']['close_at_down'])['date']=='2026-11-17'
    assert max(e['days'],key=lambda d:d['limit_counts_in_paired']['one_price_down'])['date']=='2026-11-18'
