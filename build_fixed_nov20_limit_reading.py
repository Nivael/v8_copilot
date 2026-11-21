"""Project fixed-cohort actual limits with explicit retained gaps."""
from pathlib import Path
from hashlib import sha256
import json
from fixed_nov20_limit_audit import reading as replay

def reading():
    path=Path('FIXED_NOV20_LIMIT_AUDIT_2026_11_21.json');packet=json.loads(path.read_text())
    if replay()!=packet:raise ValueError('fixed limit replay differs')
    if packet['paired']+len(packet['gaps'])!=packet['members']:raise ValueError('fixed coverage differs')
    return {k:packet[k] for k in ('date','members','paired','gaps','hits','market_audit_sha256','cohort_evidence_sha256')} | dict(evidence_sha256=sha256(path.read_bytes()).hexdigest())

if __name__=='__main__':
    Path('web/src/fixedNov20Limits.json').write_text(json.dumps(reading(),ensure_ascii=False,indent=2)+'\n')
