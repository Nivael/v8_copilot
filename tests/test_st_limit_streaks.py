from pathlib import Path
import json
import pytest
from st_limit_streaks import analyze

def source():return json.loads(Path('ST_LIMIT_COHORT_EVIDENCE_2026_11_21.json').read_text())['reading']

def test_closing_and_single_price_runs_are_distinct_and_not_double_counted_across_groups():
    r=analyze(source());a,b=r['groups']
    assert a['metrics'][0]['observed_hit_sessions']==27
    assert b['metrics'][0]['observed_hit_sessions']==30
    for g in r['groups']:
        assert g['metrics'][0]['continuous_companies']==5
        assert g['metrics'][0]['longest_observed_sessions']==4
        assert g['metrics'][1]['continuous_companies']==1
        assert g['metrics'][1]['longest_observed_sessions']==2
        q=[r for r in g['runs']if r['symbol']=='000826.SZ']
        assert [(x['metric'],x['observed_sessions'])for x in q]==[('close_at_down',4),('one_price_down',2)]
        assert all(x['ongoing_at_cutoff']and x['right_boundary_unknown']for x in q)
        assert all(len(x['dates'])==1 for x in g['runs']if x['symbol']=='000632.SZ')


def test_unknown_observation_breaks_run_and_marks_neighbors_unknown():
    s=source();g=s['groups'][0]
    row=next(r for r in g['rows']if r['symbol']=='000826.SZ'and r['date']=='2026-11-18');row['status']='missing_limit'
    out=analyze(s)['groups'][0]
    q=[r for r in out['runs']if r['symbol']=='000826.SZ'and r['metric']=='close_at_down']
    assert [x['observed_sessions']for x in q]==[2,1]
    assert q[0]['right_reason']=='missing_limit'and q[0]['right_boundary_unknown']
    assert q[1]['left_reason']=='missing_limit'and q[1]['left_boundary_unknown']


def test_nonmember_day_and_window_edges_never_become_known_nonhits():
    s=source();g=s['groups'][0]
    g['rows']=[r for r in g['rows']if not(r['symbol']=='000826.SZ'and r['date']=='2026-11-18')]
    next(r for r in g['days']if r['date']=='2026-11-18')['members']-=1
    runs=[r for r in analyze(s)['groups'][0]['runs']if r['symbol']=='000826.SZ'and r['metric']=='close_at_down']
    assert runs[0]['right_reason']==runs[1]['left_reason']=='not_member'
    s=source();row=next(r for r in s['groups'][0]['rows']if r['date']=='2026-11-09'and r['status']=='paired');row['close_at_down']=True
    run=next(r for r in analyze(s)['groups'][0]['runs']if r['symbol']==row['symbol']and r['dates'][0]=='2026-11-09'and r['metric']=='close_at_down')
    assert run['left_boundary_unknown']and run['left_reason']=='window_edge'


def test_rejects_duplicate_rows_calendar_gaps_and_contradictory_states():
    s=source();s['groups'][0]['rows'].append(s['groups'][0]['rows'][0])
    with pytest.raises(ValueError,match='duplicate'):analyze(s)
    s=source();s['groups'][0]['days'].pop()
    with pytest.raises(ValueError,match='calendar'):analyze(s)
    s=source();r=next(r for r in s['groups'][0]['rows']if r['status']=='paired');r.update(one_price_down=True,close_at_down=False)
    with pytest.raises(ValueError,match='inconsistent'):analyze(s)
