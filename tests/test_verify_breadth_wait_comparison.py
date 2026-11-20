from hashlib import sha256
import json
from pathlib import Path
import shutil
import pytest
from verify_breadth_wait_comparison import verify

FILES = ['BREADTH_WAIT_COMPARISON_EVIDENCE_2026_11_21.json',
         'ST_BREADTH_ALIGNMENT_EVIDENCE_2026_11_21.json',
         'web/src/breadthWaitComparison.json', 'web/src/stBreadthAlignment.json',
         'breadth_wait_comparison.py', 'st_breadth_alignment.py']

@pytest.fixture
def root(tmp_path):
    for name in FILES:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(name, target)
    return tmp_path


def change_json(path, mutate):
    value = json.loads(path.read_text()); mutate(value)
    path.write_text(json.dumps(value, ensure_ascii=False))


def test_replays_without_mutating_any_input(root):
    before = {name: (root / name).read_bytes() for name in FILES}
    result = verify(root)
    assert (result['observed_sessions'], result['observed_spells']) == (49, 15)
    assert result['status'] == 'verified'
    assert all((root / name).read_bytes() == raw for name, raw in before.items())


def test_rejects_edited_output_and_unreviewed_source_bytes(root):
    change_json(root / 'web/src/breadthWaitComparison.json', lambda v: v['reading'].update(observed_sessions=48))
    with pytest.raises(ValueError, match='projection'): verify(root)


@pytest.mark.parametrize('name, message', [
    ('ST_BREADTH_ALIGNMENT_EVIDENCE_2026_11_21.json', 'source bytes'),
    ('BREADTH_WAIT_COMPARISON_EVIDENCE_2026_11_21.json', 'evidence bytes'),
    ('breadth_wait_comparison.py', 'processor changed'),
    ('st_breadth_alignment.py', 'processor changed'),
])
def test_rejects_changes_even_when_old_three_day_replay_might_still_match(root, name, message):
    with (root / name).open('ab') as f: f.write(b'\n')
    with pytest.raises(ValueError, match=message): verify(root)


def test_rejects_inconsistent_embedded_input_even_with_new_envelope_hash(root):
    p = root / 'BREADTH_WAIT_COMPARISON_EVIDENCE_2026_11_21.json'
    change_json(p, lambda v: v['inputs']['inputs']['daily'][0].update(return_pct=0.1))
    change_json(root / 'web/src/breadthWaitComparison.json', lambda v: v.update(evidence_sha256=sha256(p.read_bytes()).hexdigest()))
    with pytest.raises(ValueError, match='embedded'): verify(root)
