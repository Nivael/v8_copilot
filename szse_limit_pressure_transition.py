"""Same successful-quote subset across two days; no full-universe inference."""
from pathlib import Path
from hashlib import sha256
from decimal import Decimal as D
from statistics import median
import json
from verify_szse_nov20_limit_candidates import verify
from st_limit_cohort_replay import replay


def analyze():
    paths=['SZSE_NOV20_LIMIT_EVIDENCE_2026_11_21.json','ST_LIMIT_COHORT_EVIDENCE_2026_11_21.json','SZSE_OHLC_FIELD_EVIDENCE_2026_11_21.json']
    evidence=[json.loads(Path(p).read_text())for p in paths]
    new,old,official=evidence
    verified=verify(new)
    r=replay(old['manifest'],Path('/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk/recovered_limit_cohorts/20261109-20261119'))
    if r!=old['reading']:raise ValueError('old cohort changed')
    chosen={x['symbol']:x for x in new['rows']if x['status']=='matched'}
    prior={x['symbol']:x for x in r['groups'][0]['rows']if x['date']=='2026-11-19'and x['symbol']in chosen}
    quotes={x['symbol']:x for x in official['reading']['rows']}
    if set(prior)!=set(chosen) or any(x['status']!='paired'for x in prior.values()):raise ValueError('common pair missing')
    rows=[]
    for symbol,newrow in chosen.items():
        q=quotes[symbol];prev=prior[symbol]
        if D(q['reference'])!=D(prev['close']):raise ValueError('previous close differs')
        ret=(D(q['close'])/D(prev['close'])-1)*100
        rows.append(dict(symbol=symbol,name=q['name'],return_pct=float(ret),previous_touch=prev['touch_down'],previous_close_lower=prev['close_at_down'],previous_one_price=prev['one_price_down'],**newrow['reading']))
    returns=[x['return_pct']for x in rows]
    return dict(source_sha256={p:sha256(Path(p).read_bytes()).hexdigest()for p in paths},reading=dict(start='2026-11-19',through='2026-11-20',paired=len(rows),excluded=[dict(symbol=x['symbol'],status=x['status'])for x in new['rows']if x['status']!='matched'],previous=dict(touch=sum(x['previous_touch']for x in rows),close_lower=sum(x['previous_close_lower']for x in rows),one_price=sum(x['previous_one_price']for x in rows)),current=dict(touch=sum(x['touch_lower']for x in rows),close_lower=sum(x['close_lower']for x in rows),one_price=sum(x['one_price_lower']for x in rows)),mean_pct=sum(returns)/len(returns),median_pct=median(returns),median_display=f"{median(returns):.2f}%",up=sum(x>0 for x in returns),down=sum(x<0 for x in returns),flat=sum(x==0 for x in returns),complete_coverage=verified['complete_trading_coverage'],rows=rows))


if __name__=='__main__':
    result=analyze();Path('SZSE_LIMIT_PRESSURE_TRANSITION_EVIDENCE_2026_11_21.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result['reading'].items()if k!='rows'},ensure_ascii=False,indent=2))
