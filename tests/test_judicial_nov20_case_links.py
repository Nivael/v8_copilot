from pathlib import Path
from hashlib import sha256
import json
from build_judicial_case_links import build


def test_reconstructed_old_cases_and_new_disclosures_bind_exactly():
    p=Path('JUDICIAL_NOV20_CASE_LINKS_EVIDENCE_2026_11_21.json');e=json.loads(p.read_text())
    assert build()==e
    assert json.loads(Path('web/src/judicialNov20CaseLinks.json').read_text())==dict(e,evidence_sha256=sha256(p.read_bytes()).hexdigest())
    assert {r['code']for r in e['links']}=={'600180','603008'}
    assert all(r['expected_context']['through']=='2026-11-19'for r in e['links'])
