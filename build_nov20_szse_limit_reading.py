"""Expose only the fully replayed dated SZSE scope; preserve prior partial stage."""
from pathlib import Path
from hashlib import sha256
import json
from nov20_szse_limit_crosscheck import reading as replay

def reading():
    path=Path('NOV20_SZSE_LIMIT_CROSSCHECK_2026_11_21.json');packet=json.loads(path.read_text())
    if replay()!=packet: raise ValueError('SZSE cross-channel replay differs')
    if packet['unresolved'] or len(packet['matched'])+len(packet['official_no_trade'])!=packet['members']:
        raise ValueError('incomplete dated scope')
    return {k:packet[k] for k in ('date','members','matched','official_no_trade','recovered','cross_channel_agreement','hits','prior_partial_sha256')} | dict(evidence_sha256=sha256(path.read_bytes()).hexdigest(),market_audit_sha256=packet['market_audit_sha256'])

if __name__=='__main__':
    Path('web/src/nov20SzseLimitComplete.json').write_text(json.dumps(reading(),ensure_ascii=False,indent=2)+'\n')
