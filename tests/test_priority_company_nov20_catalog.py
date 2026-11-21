from pathlib import Path
import json
import pytest
from verify_priority_company_nov20_catalog import verify


def data():return json.loads(Path('PRIORITY_COMPANY_NOV20_CATALOG_EVIDENCE_2026_11_21.json').read_text())


def test_identical_empty_bodies_are_queries_not_four_independent_legal_facts():
    r=verify(data())
    assert r['query_count']==4 and r['unique_empty_response_bodies']==1
    assert r['new_body_candidates']==0 and not r['legal_or_financial_status_changed']
    assert all(x['source_data_date']is None for x in r['companies'])


def test_changed_date_or_identity_is_rejected():
    e=data();e['companies'][0]['pages'][0]['params']['seDate']='2026-07-04~2026-11-19'
    with pytest.raises(ValueError,match='query'):verify(e)
    e=data();e['companies'][0]['org_id']='different'
    with pytest.raises(ValueError,match='identity'):verify(e)
