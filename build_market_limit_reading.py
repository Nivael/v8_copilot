"""Publish only fully reconciled daily limit observations; keep absent dates absent."""
from pathlib import Path
from hashlib import sha256
import json
from market_limit_scope_audit import build


def reading():
    path=Path('MARKET_LIMIT_SCOPE_AUDIT_2026_11_21.json');e=json.loads(path.read_text())
    if build()!=e:raise ValueError('market scope replay differs')
    for d in e['days']:
        if d['missing']or d['unpaired']or d['official_close_or_reference_conflicts']or d['paired']!=d['official_trading']:raise ValueError('unresolved market coverage')
    return dict(evidence_sha256=sha256(path.read_bytes()).hexdigest(),breadth_sha256=e['breadth_sha256'],source_cohort_sha256=e['source_cohort_sha256'],days=e['days'])


if __name__=='__main__':
    Path('web/src/marketDailyLimits.json').write_text(json.dumps(reading(),ensure_ascii=False,indent=2)+'\n')
