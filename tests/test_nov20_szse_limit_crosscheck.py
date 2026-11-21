from pathlib import Path
from hashlib import sha256
import json
from nov20_szse_limit_crosscheck import reading


def test_recovers_only_prior_missing_active_stock_and_preserves_prior_evidence():
    path=Path('SZSE_NOV20_LIMIT_EVIDENCE_2026_11_21.json');before=path.read_bytes()
    result=reading()
    assert result['members']==74
    assert len(result['matched'])==72
    assert len(result['cross_channel_agreement'])==71
    assert result['recovered']==['000010.SZ']
    assert len(result['official_no_trade'])==2
    assert result['unresolved']==[]
    assert len(result['hits']['touch_lower'])==2
    assert result['hits']['close_lower']==result['hits']['one_price_lower']==[]
    assert path.read_bytes()==before
    assert result['prior_partial_sha256']==sha256(before).hexdigest()
    assert json.loads(before)['rows'][0]['status']=='unresolved'


def test_published_reading_replays_and_retains_scope():
    from build_nov20_szse_limit_reading import reading as projected
    assert projected()==json.loads(Path('web/src/nov20SzseLimitComplete.json').read_text())
