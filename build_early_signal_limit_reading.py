from pathlib import Path
from hashlib import sha256
import json
from early_signal_limit_audit import analyze


def reading():
    p=Path('EARLY_SIGNAL_LIMIT_AUDIT_EVIDENCE_2026_11_21.json');e=json.loads(p.read_text())
    if analyze()!=e:raise ValueError('limit replay differs')
    old=json.loads(Path('web/src/earlySignalOpenReading.json').read_text())
    if old['evidence_sha256']!=e['early_ohlc_evidence_sha256'] or old['signal_evidence_sha256']!=e['signal_evidence_sha256']:raise ValueError('opening context differs')
    if any(r['limit_status']!='paired' for r in e['rows']):raise ValueError('unresolved limits remain')
    proof=json.loads(Path('EARLY_SIGNAL_LIMIT_RECORD_PROOF_2026_11_21.json').read_text())
    if not proof['methods_accepted_exact'] or proof['new_independent_validations']!=0:raise ValueError('record differs')
    return dict(evidence_sha256=sha256(p.read_bytes()).hexdigest(),research_run_id=proof['run_id'],**e)


if __name__=='__main__':
    Path('web/src/earlySignalLimitReading.json').write_text(json.dumps(reading(),ensure_ascii=False,indent=2)+'\n')
