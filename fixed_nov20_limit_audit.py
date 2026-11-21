"""Pair actual Nov20 limits in the retained fixed cohort; retain unresolved exits."""
from pathlib import Path
from hashlib import sha256
from decimal import Decimal as D
import json
from canonical_json import digest
from st_fixed_nov20 import analyze
from tencent_nov20_market_audit import build

FOLDER=Path('/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk/recent_breadth_history/sources/895130d3f8b80b5e2f8ef947dcb67a3d6a7c9bbe849b91dd2e3c7b62cda89f47/szse-history')

def reading():
    fixed_path=Path('ST_FIXED_NOV20_EVIDENCE_2026_11_21.json');e=json.loads(fixed_path.read_text())
    prior=analyze(e,FOLDER)
    if prior!=e['reading']:raise ValueError('fixed official replay differs')
    cohort_path=Path('ST_LIMIT_COHORT_EVIDENCE_2026_11_21.json');cohort=json.loads(cohort_path.read_text())
    if e['fixed_symbols']!=cohort['manifest']['fixed_symbols']:raise ValueError('fixed limit cohort differs')
    market_path=Path('TENCENT_NOV20_MARKET_AUDIT_2026_11_21.json');market=json.loads(market_path.read_text())
    if build()!=market:raise ValueError('market source replay differs')
    quotes={r['code']:r for r in market['observations']};rows=[];gaps=[]
    hits={key:[] for key in ('open_lower','touch_lower','close_lower','one_price_lower')}
    for old in prior['rows']:
        code=old['symbol'];quote=quotes.get(code)
        if old['status']!='paired':
            if quote:raise ValueError('new active quote contradicts old missing/nontrading scope')
            gaps.append(dict(code=code,status=old['status']));continue
        if not quote:raise ValueError('previous active identity lacks limits')
        if D(quote['close'])!=D(old['close20']) or D(quote['reference'])!=D(old['reference20']):raise ValueError('official fixed price conflict')
        lower=D(quote['lower']);row=dict(quote);row['change_pct']=old['change_pct'];rows.append(row)
        checks=dict(open_lower=D(quote['open'])==lower,touch_lower=D(quote['low'])==lower,close_lower=D(quote['close'])==lower,one_price_lower=D(quote['high'])==lower)
        for key,value in checks.items():
            if value:hits[key].append(code)
    result=dict(version='fixed_nov20_limit_audit_v1',date='2026-11-20',fixed_evidence_sha256=sha256(fixed_path.read_bytes()).hexdigest(),cohort_evidence_sha256=sha256(cohort_path.read_bytes()).hexdigest(),market_audit_sha256=sha256(market_path.read_bytes()).hexdigest(),members=150,paired=len(rows),rows=rows,gaps=gaps,hits=hits,limits=['Fixed July3 historical cohort, including later removals; not current legal ST membership','146 paired limits do not resolve two missing official quotes or two nontrading securities','No limit inferred from uniform percentage change','Official close/reference cross-check does not independently certify Tencent intraday OHLC or actual limits','Retrospective data, no queue/fill/executable-exit or new strategy validation'])
    result['content_digest']=digest(result);return result

if __name__=='__main__':
    result=reading();Path('FIXED_NOV20_LIMIT_AUDIT_2026_11_21.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(result['paired'],result['gaps'],result['hits'])
