from pathlib import Path
from hashlib import sha256
import json
from breadth_severity_timing import analyze


def reading():
    path=Path('BREADTH_SEVERITY_TIMING_EVIDENCE_2026_11_21.json');e=json.loads(path.read_text())
    if analyze()!=e:raise ValueError('severity timing replay differs')
    coverage=json.loads(Path('web/src/longBreadthCoverage.json').read_text())
    if coverage['evidence_sha256']!=e['breadth_sha256'] or coverage['sessions']!=e['observations']:raise ValueError('breadth context differs')
    proof=json.loads(Path('BREADTH_SEVERITY_TIMING_RECORD_PROOF_2026_11_21.json').read_text())
    if not proof['methods_accepted_exact'] or proof['new_independent_validations']!=0:raise ValueError('record differs')
    return dict(evidence_sha256=sha256(path.read_bytes()).hexdigest(),research_run_id=proof['run_id'],**e)


if __name__=='__main__':
    Path('web/src/breadthSeverityReading.json').write_text(json.dumps(reading(),ensure_ascii=False,indent=2)+'\n')
