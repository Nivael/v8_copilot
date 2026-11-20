import json
from pathlib import Path
import pytest
from verify_july_august_sse_basis import verify


def data():return json.loads(Path('JULY_AUGUST_SSE_BASIS_EVIDENCE_2026_11_21.json').read_text())


def test_early_registry_matches_all_daily_counts_and_retains_exits():
    e=data();assert verify(e)==dict(pool=2318,days=44,all_days_matched=True)
    assert e['pool']['600193']['ended']=='2026-07-06'
    assert e['pool']['600608']['ended']==e['pool']['605081']['ended']=='2026-07-03'


def test_omitting_exit_or_daily_control_is_rejected():
    e=data();del e['pool']['600193']
    with pytest.raises(ValueError,match='pool'):verify(e)
    e=data();e['overview_refs'].pop()
    with pytest.raises(ValueError,match='calendar'):verify(e)
