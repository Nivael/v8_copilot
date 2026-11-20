"""Publish a source-bound index reading alongside the existing daily breadth."""
from pathlib import Path
from hashlib import sha256
import json
from long_index_price_replay import build


def reading():
    p=Path('LONG_INDEX_PRICE_REPLAY_EVIDENCE_2026_11_21.json');e=json.loads(p.read_text())
    if build()!=e:raise ValueError('official index replay differs')
    b=json.loads(Path('web/src/longBreadthReplay.json').read_text())
    if e['breadth_sha256']!=b['evidence_sha256'] or [r['date']for r in e['rows']]!=[r['date']for r in b['rows']]:raise ValueError('breadth/index dates differ')
    return dict(evidence_sha256=sha256(p.read_bytes()).hexdigest(),breadth_sha256=e['breadth_sha256'],sources=e['sources'],rows=e['rows'])


if __name__=='__main__':
    Path('web/src/longIndexReading.json').write_text(json.dumps(reading(),ensure_ascii=False,indent=2)+'\n')
