from pathlib import Path
import json
import pytest
from long_breadth_wait_comparison import analyze_wait


def test_all_short_spells_and_same_endpoint_compound_identity_are_retained():
    e=analyze_wait();assert e==json.loads(Path('LONG_BREADTH_WAIT_EVIDENCE_2026_11_21.json').read_text())
    assert e['summary']==dict(episode_count=27,short_episode_count=21)
    episodes=e['reading']['episodes'];assert episodes[0]['first']=='2026-07-02'
    assert [c['formed']for c in episodes[0]['checks']]==[True,False,False]
    latest=episodes[-1];assert latest['target_end']=='2026-11-19'
    assert [c['remaining_sessions']for c in latest['checks']]==[5,4,3]
    for episode in episodes:
        for c in episode['checks']:
            if not c['formed']:continue
            for key in ['st','market']:
                whole=((1+c[f'already_{key}_pct']/100)*(1+c[f'remaining_{key}_pct']/100)-1)*100
                assert whole==pytest.approx(episode[f'total_{key}_pct'],abs=1e-10)
