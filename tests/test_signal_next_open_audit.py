from pathlib import Path
from decimal import Decimal as D
import json
import pytest
from signal_next_open_audit import analyze


def test_saved_next_open_scope_identity_and_price_reference_are_not_execution():
    result=analyze()
    assert result==json.loads(Path('SIGNAL_NEXT_OPEN_AUDIT_EVIDENCE_2026_11_21.json').read_text())
    assert sum(r['available'] for r in result['coverage'])==1
    assert len(result['coverage'])==6
    assert result['signal_date']=='2026-11-16' and result['next_session']=='2026-11-17'
    assert {r['symbol'] for r in result['focus']}=={'603398.SH','002514.SZ','600363.SH','002667.SZ','688053.SH'}
    for row in result['focus']:
        assert row['status']=='paired'
        assert D(row['down_limit']) < D(row['low']) <= D(row['open']) <= D(row['high'])
        assert row['open_vs_reference_pct']==pytest.approx(float((D(row['open'])/D(row['pre_close'])-1)*100))
        assert not row['open_at_lower'] and not row['touched_lower']
    dynamic,fixed=result['groups']
    assert (dynamic['members'],dynamic['paired'],dynamic['open_at_lower'],dynamic['close_at_lower'])==(142,141,1,10)
    assert (fixed['members'],fixed['paired'],fixed['open_at_lower'],fixed['close_at_lower'])==(150,147,1,10)
    assert [len(r['unpaired']) for r in result['groups']]==[1,3]
    assert not result['focus'][-1]['in_saved_st_mainboard']


def test_published_projection_replays_and_has_no_promoted_experience():
    from build_signal_next_open_reading import reading
    assert reading()==json.loads(Path('web/src/signalNextOpenReading.json').read_text())
    p=json.loads(Path('SIGNAL_NEXT_OPEN_RECORD_PROOF_2026_11_21.json').read_text())
    assert p['old_runs_exact']==309 and p['ledger_count']==310
    assert p['methods_accepted_exact'] and p['new_independent_validations']==0
