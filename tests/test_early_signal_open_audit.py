from pathlib import Path
from decimal import Decimal as D
import json
import pytest
from early_signal_open_audit import analyze


def test_all_five_earlier_signal_dates_replay_25_raw_ohlc_positions():
    e=analyze()
    assert e==json.loads(Path('EARLY_SIGNAL_OPEN_AUDIT_EVIDENCE_2026_11_21.json').read_text())
    assert e['summary']==dict(signal_count=5,positions=25,matched=25,nontrading=0)
    assert len(e['raw_public_sources'])==len(e['primary_daily_sources'])==5
    assert {r['next_session'] for r in e['rows']}=={'2026-07-09','2026-07-21','2026-09-07','2026-09-14','2026-09-28'}
    assert len({(r['symbol'],r['next_session']) for r in e['rows']})==25
    for r in e['rows']:
        assert r['actual_limits_status']=='not_replayed_here'
        assert r['open_vs_reference_pct']==pytest.approx(float((D(r['open'])/D(r['pre_close'])-1)*100))
        assert r['status']=='two_channel_ohlc_match'
        assert not r['one_price_day']


def test_reading_projection_and_research_scope_are_bound():
    from build_early_signal_open_reading import reading
    e=reading()
    assert e==json.loads(Path('web/src/earlySignalOpenReading.json').read_text())
    proof=json.loads(Path('EARLY_SIGNAL_OPEN_RECORD_PROOF_2026_11_21.json').read_text())
    assert proof['old_runs_exact']==310 and proof['ledger_count']==311
    assert proof['methods_accepted_exact'] and proof['new_independent_validations']==0
