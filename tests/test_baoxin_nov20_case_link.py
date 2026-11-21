from pathlib import Path
from hashlib import sha256
import json
from build_baoxin_nov20_case_link import build


def test_company_binding_retains_original_evidence_and_exact_new_disclosure():
    p=Path('BAOXIN_NOV20_CASE_LINK_EVIDENCE_2026_11_21.json');e=json.loads(p.read_text())
    assert build()==e
    view=json.loads(Path('web/src/baoxinNov20CaseLink.json').read_text())
    assert view==dict(e,evidence_sha256=sha256(p.read_bytes()).hexdigest())
    fixture=json.loads(Path('web/src/__fixtures__/baoxin-holding-bridge.json').read_text())
    assert all(fixture[k]==v for k,v in e['expected_context'].items())
    assert e['expected_context']['through']=='2026-11-06'
    assert e['finding']['announcement_id']=='1225679913'
