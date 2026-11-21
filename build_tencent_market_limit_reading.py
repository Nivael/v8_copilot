"""Project the replayed Nov20 source audit without changing older observations."""
from pathlib import Path
from hashlib import sha256
import json
from tencent_nov20_market_audit import build

def reading():
    path=Path('TENCENT_NOV20_MARKET_AUDIT_2026_11_21.json')
    audit=json.loads(path.read_text())
    if build()!=audit: raise ValueError('Nov20 source replay differs')
    if audit['unresolved'] or audit['paired']!=audit['official_trading']: raise ValueError('incomplete Nov20 coverage')
    return {k:audit[k] for k in ('date','breadth_sha256','official_trading','paired','limit_counts_in_paired')} | dict(evidence_sha256=sha256(path.read_bytes()).hexdigest(),source='Tencent public quote fields; official close/reference cross-check')

if __name__=='__main__':
    Path('web/src/tencentMarketDailyLimits.json').write_text(json.dumps(reading(),ensure_ascii=False,indent=2)+'\n')
