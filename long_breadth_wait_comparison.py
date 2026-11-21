"""Reuse the existing waiting calculation on all long-window weak spells."""
from pathlib import Path
from hashlib import sha256
import gzip,json
from long_breadth_st_alignment import analyze,INPUT,INPUT_SHA
from st_regime_comparison import build
from st_breadth_alignment import analyze as align
from breadth_wait_comparison import compare
from breadth_common_end import compare_common_end


def analyze_wait():
    path=Path('LONG_BREADTH_ST_ALIGNMENT_EVIDENCE_2026_11_21.json');source=json.loads(path.read_text())
    if analyze()!=source:raise ValueError('long alignment differs')
    raw=INPUT.read_bytes()
    if sha256(raw).hexdigest()!=INPUT_SHA:raise ValueError('input changed')
    m=json.loads(gzip.decompress(raw))['current_extension']['market_inputs'];daily=build(m)['daily']
    fields=['date','return_pct','market_pct','missing','observed_count']
    daily=[{k:r[k]for k in fields}for r in daily]
    inputs=dict(daily=daily,extension_days=[],breadth_days=source['reading']['days'])
    alignment=align({'daily':daily,'themes':{'current_extension':{'days':[]}}},{'sequence':{'days':inputs['breadth_days']}})
    # All six first hits must match the earlier complete/partial follow-up observations.
    for previous in source['reading']['signals']:
        row=next(r for r in alignment['signals']if r['date']==previous['date'])
        if any(row[k]!=previous[k]for k in ['st_pct','market_pct','complete_five','observed_following_sessions']):raise ValueError('signal outcome differs')
    adapted=dict(inputs=inputs,reading=alignment)
    own=compare(adapted);common=compare_common_end(adapted)
    return dict(summary=dict(episode_count=len(common['episodes']),short_episode_count=sum(e['observed_weak_sessions']<3 for e in common['episodes'])),version='long_breadth_wait_comparison_v1',alignment_sha256=sha256(path.read_bytes()).hexdigest(),input_asset_sha256=INPUT_SHA,inputs=inputs,alignment=alignment,reading=common,own_five=own,limits=['Includes short one/two-day spells, not only successful third-day signals','July2 short spell uses primary-source returns; independent official index controls begin July3','Same endpoint does not equal same remaining duration or executable action comparison','Same-spell waits are not independent cases; no optimized waiting rule'])


if __name__=='__main__':
    e=analyze_wait();Path('LONG_BREADTH_WAIT_EVIDENCE_2026_11_21.json').write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n');p=e['reading']['episodes'];print(dict(start=e['reading']['start'],through=e['reading']['through'],episodes=len(p),short=sum(x['observed_weak_sessions']<3 for x in p),incomplete=sum(not x['complete']for x in p)));print(p[0])
