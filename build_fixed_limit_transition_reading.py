from pathlib import Path
from hashlib import sha256
import json
from fixed_limit_transition import analyze

def reading():
    path=Path('FIXED_LIMIT_TRANSITION_2026_11_21.json');packet=json.loads(path.read_text())
    if analyze()!=packet:raise ValueError('transition replay differs')
    proof=json.loads(Path('FIXED_LIMIT_TRANSITION_RECORD_PROOF_2026_11_21.json').read_text())
    if not proof['methods_accepted_exact'] or proof['new_independent_validations']!=0:raise ValueError('registration invariant differs')
    return {k:packet[k] for k in ('start','through','paired','excluded','previous','current','up','down','flat','left_close_lower','closing_state_matrix','source_sha256','rows')} | dict(evidence_sha256=sha256(path.read_bytes()).hexdigest(),research_run_id=proof['run_id'])

if __name__=='__main__':
    Path('web/src/fixedLimitTransition.json').write_text(json.dumps(reading(),ensure_ascii=False,indent=2)+'\n')
