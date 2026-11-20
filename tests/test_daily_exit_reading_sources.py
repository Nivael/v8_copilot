from pathlib import Path
from hashlib import sha256
import json
from st_limit_cohort_replay import replay
from verify_szse_nov20_limit_candidates import verify


def test_selected_day_reading_reuses_exact_verified_scopes():
    load=lambda p:json.loads(Path(p).read_text())
    p=Path('ST_LIMIT_COHORT_EVIDENCE_2026_11_21.json');e=load(p);v=load('web/src/stLimitCohorts.json')
    assert sha256(p.read_bytes()).hexdigest()==v['evidence_sha256']
    r=replay(e['manifest'],Path('/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk/recovered_limit_cohorts/20261109-20261119'))
    assert r==e['reading']
    assert [(g['key'],g['days'])for g in r['groups']]==[(g['key'],g['days'])for g in v['reading']['groups']]
    p=Path('SZSE_NOV20_LIMIT_EVIDENCE_2026_11_21.json');e=load(p);v=load('web/src/szseNov20Limits.json')
    assert sha256(p.read_bytes()).hexdigest()==v['evidence_sha256']
    assert verify(e)==v['reading']
