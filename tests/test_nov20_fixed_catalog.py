from pathlib import Path
import json
import pytest
from verify_nov20_fixed_catalog import verify


def data():
    return json.loads(Path('NOV20_FIXED_CATALOG_EVIDENCE_2026_11_21.json').read_text())


def test_full_fixed_group_preserves_title_only_scope():
    r = verify(data())
    assert r['requested_companies'] == r['captured_companies'] == 150
    assert r['title_sightings'] == r['unique_attachment_identities'] == 41
    assert r['nonempty_companies'] == 20 and not r['unresolved']
    assert r['positive_control_matched'] and r['body_reviewed'] == 0


def test_changed_query_date_and_missing_company_are_rejected():
    e = data()
    e['companies'][0]['pages'][0]['params']['seDate'] = '2026-11-19~2026-11-20'
    with pytest.raises(ValueError, match='query scope'):
        verify(e)
    e = data()
    e['companies'].pop()
    with pytest.raises(ValueError, match='fixed scope'):
        verify(e)
