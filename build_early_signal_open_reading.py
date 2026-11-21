from pathlib import Path
from hashlib import sha256
import json
from early_signal_open_audit import analyze


def reading():
    p=Path('EARLY_SIGNAL_OPEN_AUDIT_EVIDENCE_2026_11_21.json');e=json.loads(p.read_text())
    if analyze()!=e:raise ValueError('earlier OHLC replay differs')
    split=json.loads(Path('web/src/longNextCloseReading.json').read_text())
    latest=json.loads(Path('web/src/signalNextOpenReading.json').read_text())
    if e['signal_evidence_sha256']!=split['evidence_sha256'] or e['input_asset_sha256']!=latest['input_asset_sha256']:raise ValueError('reading scope differs')
    proof=json.loads(Path('EARLY_SIGNAL_OPEN_RECORD_PROOF_2026_11_21.json').read_text())
    if not proof['methods_accepted_exact'] or proof['new_independent_validations']!=0:raise ValueError('record differs')
    return dict(evidence_sha256=sha256(p.read_bytes()).hexdigest(),research_run_id=proof['run_id'],**e)


if __name__=='__main__':
    Path('web/src/earlySignalOpenReading.json').write_text(json.dumps(reading(),ensure_ascii=False,indent=2)+'\n')
