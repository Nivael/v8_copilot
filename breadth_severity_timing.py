"""Describe same-day tail breadth versus prefix-only three-day confirmation state."""
from pathlib import Path
from hashlib import sha256
import json
from build_long_breadth_replay import build


def summarize(rows, thresholds=(10,20,30)):
    if len(set(thresholds))!=len(thresholds) or any(not isinstance(t,int) or not 0<t<=100 for t in thresholds):raise ValueError('invalid severity examples')
    if [r['date'] for r in rows]!=sorted({r['date'] for r in rows}):raise ValueError('nonunique ordered dates required')
    days=[]
    for i,row in enumerate(rows):
        prior=rows[i-1] if i else None
        state='prior_unknown' if prior is None else 'confirmed_at_previous_close' if prior['streak']>=3 else 'first_confirmed_today' if row['streak']==3 else 'current_spell_not_confirmed'
        days.append(dict(date=row['date'],trading=row['trading'],tail=row['tail'],tail_pct=row['tail']/row['trading']*100,streak=row['streak'],weak_start=row['weak_start'],previous_close=prior['date'] if prior else None,previous_streak=prior['streak'] if prior else None,confirmation_state=state))
    cuts=[]
    for threshold in thresholds:
        chosen=[r for r in days if r['tail']*100>=threshold*r['trading']]
        counts={state:sum(r['confirmation_state']==state for r in chosen) for state in ('prior_unknown','confirmed_at_previous_close','first_confirmed_today','current_spell_not_confirmed')}
        if sum(counts.values())!=len(chosen):raise ValueError('state partition differs')
        cuts.append(dict(threshold_pct=threshold,threshold_label=str(threshold)+'%',days=len(chosen),counts=counts,dates=[r['date'] for r in chosen]))
    return dict(days=days,thresholds=cuts)


def analyze():
    source=Path('web/src/longBreadthReplay.json');saved=json.loads(source.read_text());rebuilt=build()
    if {k:saved[k] for k in ('evidence_sha256','start','through','rows')}!={k:rebuilt[k] for k in ('evidence_sha256','start','through','rows')}:raise ValueError('daily breadth replay differs')
    result=summarize(rebuilt['rows'])
    return dict(version='breadth_severity_timing_v1',breadth_sha256=rebuilt['evidence_sha256'],start=rebuilt['start'],through=rebuilt['through'],observations=len(result['days']),known_previous_closes=max(0,len(result['days'])-1),**result,limits=['10/20/30 percent tail breadth are illustrative cutoffs, not calibrated crisis thresholds', 'The tail counts daily declines of at least 5 percent, not actual limit-down events', 'Previous-close confirmation means the current covered weak spell was still at least three days at that close; it is not an armed trading policy', 'A previous episode may have signaled and reset; current spell not confirmed does not mean no earlier signal ever', 'First covered day has no previous-close state; coverage-start truncation is retained', 'Same-day closed breadth cannot be a prior-to-loss forecast; retrospective data are not certified realtime inputs', 'Severe days and adjacent thresholds overlap, not independent experiments or false-alarm calibration'])


if __name__=='__main__':
    e=analyze();Path('BREADTH_SEVERITY_TIMING_EVIDENCE_2026_11_21.json').write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n');print(json.dumps(e['thresholds'],ensure_ascii=False,indent=2))
