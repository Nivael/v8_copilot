from pathlib import Path
import json
import pytest
from long_signal_next_close import analyze


def test_next_close_split_retains_all_signals_fixed_endpoints_and_partial_window():
    result = analyze()
    assert result == json.loads(Path('LONG_SIGNAL_NEXT_CLOSE_EVIDENCE_2026_11_21.json').read_text())
    original = json.loads(Path('LONG_BREADTH_ST_ALIGNMENT_EVIDENCE_2026_11_21.json').read_text())['reading']['signals']
    assert len(result['rows']) == len(original) == 6
    for r, source in zip(result['rows'], original, strict=True):
        assert r['signal_date'] == source['date']
        assert r['next_close'] == source['following_dates'][0]
        assert r['through'] == source['through']
        assert r['remaining_sessions'] == source['observed_following_sessions']-1
        for label in ('st','market'):
            parts=r[label]
            assert ((1+parts['first_day_pct']/100)*(1+parts['remaining_pct']/100)-1)*100 == pytest.approx(source[label+'_pct'],abs=1e-10)
    july20 = next(r for r in result['rows'] if r['signal_date']=='2026-07-20')
    assert july20['market']['whole_pct'] > 0 > july20['market']['remaining_pct']
    assert july20['st']['first_day_pct'] < 0 < july20['st']['remaining_pct']
    assert result['rows'][-1]['remaining_sessions'] == 2
    assert result['rows'][-1]['complete_five'] is False


def test_reading_projection_matches_replay_and_record_proof():
    from build_long_next_close_reading import reading
    shown = json.loads(Path('web/src/longNextCloseReading.json').read_text())
    assert reading() == shown
    proof=json.loads(Path('LONG_SIGNAL_NEXT_CLOSE_RECORD_PROOF_2026_11_21.json').read_text())
    assert proof['old_runs_exact'] == 308 and proof['ledger_count'] == 309
    assert proof['new_independent_validations'] == 0 and proof['methods_accepted_exact']
