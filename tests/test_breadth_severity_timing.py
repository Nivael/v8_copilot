from pathlib import Path
import json
from breadth_severity_timing import analyze,summarize
from build_long_breadth_replay import build


def test_all_days_and_example_cutoffs_keep_confirmation_timing_separate():
    e=analyze();assert e==json.loads(Path('BREADTH_SEVERITY_TIMING_EVIDENCE_2026_11_21.json').read_text())
    assert (e['observations'],e['known_previous_closes'])==(97,96)
    assert [t['days'] for t in e['thresholds']]==[24,6,4]
    mid=e['thresholds'][1]
    assert mid['counts']==dict(prior_unknown=0,confirmed_at_previous_close=1,first_confirmed_today=1,current_spell_not_confirmed=4)
    july13=next(r for r in e['days'] if r['date']=='2026-07-13')
    assert july13['streak']==1 and july13['previous_streak']==0 and july13['tail_pct']>39
    assert july13['confirmation_state']=='current_spell_not_confirmed'
    assert e['days'][0]['confirmation_state']=='prior_unknown'
    for t in e['thresholds']:
        assert sum(t['counts'].values())==t['days']
        assert t['dates']==[r['date'] for r in e['days'] if r['tail']*100>=t['threshold_pct']*r['trading']]


def test_each_daily_timing_state_uses_only_its_prefix():
    rows=build()['rows'];full=summarize(rows)
    for i in range(1,len(rows)+1):
        assert summarize(rows[:i])['days']==full['days'][:i]


def test_reading_projection_and_historical_record_keep_accepted_methods_unchanged():
    from build_breadth_severity_reading import reading
    assert reading()==json.loads(Path('web/src/breadthSeverityReading.json').read_text())
    p=json.loads(Path('BREADTH_SEVERITY_TIMING_RECORD_PROOF_2026_11_21.json').read_text())
    assert p['old_runs_exact']==312 and p['ledger_count']==313
    assert p['new_independent_validations']==0 and p['methods_accepted_exact']
