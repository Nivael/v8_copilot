from pathlib import Path
from decimal import Decimal as D
import json
from early_signal_limit_audit import analyze


def test_all_25_actual_limits_replay_and_keep_intraday_vs_closing_hits_separate():
    e=analyze()
    assert e==json.loads(Path('EARLY_SIGNAL_LIMIT_AUDIT_EVIDENCE_2026_11_21.json').read_text())
    assert e['summary']==dict(positions=25,paired=25,unresolved=0,open_at_lower=0,touched_lower=2,close_at_lower=1,one_price_lower=0)
    assert len(e['sources'])==5
    assert len({(r['symbol'],r['next_session']) for r in e['rows']})==25
    for r in e['rows']:
        assert r['actual_limits_status']==r['limit_status']=='paired'
        assert D(r['down_limit'])<=D(r['low'])<=D(r['open'])<=D(r['high'])<=D(r['up_limit'])
    mubang=next(r for r in e['rows'] if r['symbol']=='603398.SH' and r['next_session']=='2026-07-21')
    baoxin=next(r for r in e['rows'] if r['symbol']=='002514.SZ' and r['next_session']=='2026-07-21')
    assert mubang['open']=='9.36' and mubang['down_limit']=='9.15'
    assert mubang['touched_lower'] and mubang['close_at_lower'] and not mubang['open_at_lower']
    assert baoxin['touched_lower'] and not baoxin['close_at_lower']


def test_projection_binds_old_opening_context_and_preserves_method_registry():
    from build_early_signal_limit_reading import reading
    assert reading()==json.loads(Path('web/src/earlySignalLimitReading.json').read_text())
    p=json.loads(Path('EARLY_SIGNAL_LIMIT_RECORD_PROOF_2026_11_21.json').read_text())
    assert p['old_runs_exact']==311 and p['ledger_count']==312
    assert p['new_independent_validations']==0 and p['methods_accepted_exact']
