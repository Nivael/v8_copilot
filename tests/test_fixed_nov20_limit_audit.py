import json
from pathlib import Path
from fixed_nov20_limit_audit import reading


def test_full_saved_source_replay_preserves_all_members_and_unresolved_categories():
    prior_path=Path('ST_FIXED_NOV20_EVIDENCE_2026_11_21.json');before=prior_path.read_bytes()
    result=reading()
    assert result==json.loads(Path('FIXED_NOV20_LIMIT_AUDIT_2026_11_21.json').read_text())
    assert result['members']==150 and result['paired']==146
    assert {r['code']:r['status'] for r in result['gaps']}=={
        '000016.SZ':'missing_quote20','002731.SZ':'missing_quote20',
        '002122.SZ':'nontrading20','002717.SZ':'nontrading20'}
    assert len({r['code'] for r in result['rows']})==146
    assert len(result['hits']['touch_lower'])==8
    assert result['hits']['close_lower']==['600180.SH','600238.SH']
    assert result['hits']['open_lower']==['000826.SZ']
    assert result['hits']['one_price_lower']==[]
    assert prior_path.read_bytes()==before
