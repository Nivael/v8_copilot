from pathlib import Path
import json
import pytest
from remaining_official_recovery_audit import audit

def test_all_seven_official_pdfs_replay_against_unchanged_mirror_bytes():
    r=audit()
    assert r==json.loads(Path('REMAINING_OFFICIAL_RECOVERY_AUDIT_2026_11_21.json').read_text())
    assert r['verified_count']==7 and len({x['mirror_id'] for x in r['verified']})==7
    assert r['new_independent_validations']==0

def test_wrong_attachment_binding_cannot_be_published(tmp_path):
    e=json.loads(Path('REMAINING_OFFICIAL_RECOVERY_CAPTURE_2026_11_21.json').read_text())
    e['rows'][0]['pdf']['url']='https://example.com/other.pdf'
    p=tmp_path/'changed.json';p.write_text(json.dumps(e,ensure_ascii=False))
    with pytest.raises(ValueError,match='PDF request differs'):audit(p)
