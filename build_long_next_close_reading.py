"""Publish the original-window next-close split after source replay."""
from pathlib import Path
from hashlib import sha256
import json
from long_signal_next_close import analyze


def reading():
    path=Path('LONG_SIGNAL_NEXT_CLOSE_EVIDENCE_2026_11_21.json')
    e=json.loads(path.read_text())
    if analyze()!=e:
        raise ValueError('next-close split replay differs')
    alignment=json.loads(Path('web/src/longBreadthSTAlignment.json').read_text())
    index=json.loads(Path('web/src/longIndexReading.json').read_text())
    if e['alignment_sha256']!=alignment['evidence_sha256'] or e['index_evidence_sha256']!=index['evidence_sha256']:
        raise ValueError('page evidence differs')
    record=json.loads(Path('LONG_SIGNAL_NEXT_CLOSE_RECORD_PROOF_2026_11_21.json').read_text())
    if not record['methods_accepted_exact'] or record['new_independent_validations']!=0:
        raise ValueError('record proof differs')
    return dict(evidence_sha256=sha256(path.read_bytes()).hexdigest(), research_run_id=record['run_id'], **e)


if __name__=='__main__':
    Path('web/src/longNextCloseReading.json').write_text(json.dumps(reading(),ensure_ascii=False,indent=2)+'\n')
