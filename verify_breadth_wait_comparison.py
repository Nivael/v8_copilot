"""Read-only replay gate for the frozen waiting-time study and its web projection.

Run from any directory; paths default to this checkout. A changed source or
processor requires a reviewed new packet rather than silently rewriting it.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from breadth_wait_comparison import compare


def verify(root):
    root = Path(root)
    def read(name):
        raw = (root / name).read_bytes()
        return raw, json.loads(raw)

    raw, evidence = read('BREADTH_WAIT_COMPARISON_EVIDENCE_2026_11_21.json')
    _, web = read('web/src/breadthWaitComparison.json')
    if sha256(raw).hexdigest() != web['evidence_sha256']:
        raise ValueError('study evidence bytes changed; reviewed packet required')
    source_raw, source = read('ST_BREADTH_ALIGNMENT_EVIDENCE_2026_11_21.json')
    if sha256(source_raw).hexdigest() != evidence['alignment_evidence_sha256']:
        raise ValueError('alignment source bytes changed; reviewed packet required')
    if evidence['inputs'] != source:
        raise ValueError('embedded alignment source differs from original')
    for name, expected in (
        ('breadth_wait_comparison.py', evidence['processor_sha256']),
        ('st_breadth_alignment.py', source['processor_sha256']),
    ):
        if sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'processor changed: {name}; reviewed replay required')
    _, alignment_web = read('web/src/stBreadthAlignment.json')
    if alignment_web['evidence_sha256'] != evidence['alignment_evidence_sha256']:
        raise ValueError('web alignment binding changed')
    expected_web = {k: v for k, v in evidence.items() if k != 'inputs'}
    actual_web = {k: v for k, v in web.items() if k not in ('evidence_sha256', 'research_run_id')}
    if expected_web != actual_web:
        raise ValueError('web study projection differs from evidence')
    if compare(source) != evidence['reading']:
        raise ValueError('study computation differs from frozen reading')
    run_id = web.get('research_run_id')
    if not isinstance(run_id, str) or not run_id.startswith('RUN-'):
        raise ValueError('research identity missing')
    return {'status': 'verified', 'evidence_sha256': sha256(raw).hexdigest(),
            'research_run_id': run_id,
            'observed_sessions': evidence['reading']['observed_sessions'],
            'observed_spells': len(evidence['reading']['episodes']),
            'limits': 'Frozen-source replay only; not independent market validation, live freshness or ledger identity verification.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    try:
        result = verify(args.root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Waiting-time study verification stopped: {exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
