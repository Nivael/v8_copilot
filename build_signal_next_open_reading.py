from pathlib import Path
from hashlib import sha256
import json
from signal_next_open_audit import analyze


def reading():
    p=Path('SIGNAL_NEXT_OPEN_AUDIT_EVIDENCE_2026_11_21.json');e=json.loads(p.read_text())
    if analyze()!=e:raise ValueError('next-open source replay differs')
    for name,field in [('web/src/longNextCloseReading.json','signal_evidence_sha256'),('web/src/stLimitCohorts.json','cohort_evidence_sha256'),('web/src/marketDailyLimits.json','market_scope_evidence_sha256')]:
        if json.loads(Path(name).read_text())['evidence_sha256']!=e[field]:raise ValueError('reading source differs')
    proof=json.loads(Path('SIGNAL_NEXT_OPEN_RECORD_PROOF_2026_11_21.json').read_text())
    if not proof['methods_accepted_exact'] or proof['new_independent_validations']!=0:raise ValueError('record changed')
    return dict(evidence_sha256=sha256(p.read_bytes()).hexdigest(),research_run_id=proof['run_id'],**e)


if __name__=='__main__':
    Path('web/src/signalNextOpenReading.json').write_text(json.dumps(reading(),ensure_ascii=False,indent=2)+'\n')
