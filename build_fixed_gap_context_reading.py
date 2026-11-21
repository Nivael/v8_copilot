from pathlib import Path
from hashlib import sha256
import json
from fixed_nov20_gap_context import reading as replay

def reading():
    path=Path('FIXED_NOV20_GAP_CONTEXT_2026_11_21.json');packet=json.loads(path.read_text())
    if replay()!=packet:raise ValueError('gap context replay differs')
    return dict(evidence_sha256=sha256(path.read_bytes()).hexdigest(),fixed_limit_audit_sha256=packet['fixed_limit_audit_sha256'],rows=[dict(code=r['code'],date=r['date'],classification=r['classification'],url=r['source']['url'],title=r['source']['title'],source_sha256=r['source']['sha256']) for r in packet['rows']])

if __name__=='__main__':
    Path('web/src/fixedGapContext.json').write_text(json.dumps(reading(),ensure_ascii=False,indent=2)+'\n')
