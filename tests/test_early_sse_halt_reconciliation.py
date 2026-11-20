import json
from pathlib import Path
from early_sse_halt_reconciliation import reconcile


def test_every_early_gap_matches_closed_full_day_record():
    r=reconcile()
    assert r==json.loads(Path('EARLY_SSE_HALT_RECONCILIATION_EVIDENCE_2026_11_21.json').read_text())
    assert r['matched_days']==90 and r['unresolved']==[]
    assert len(r['intervals'])==27 and all(p['last_suspended_on'] for p in r['intervals'])
    assert sum(len(p['days'])for p in r['intervals'])==90
    assert {p['symbol']for p in r['intervals']} >= {'600193','600608','605081'}
