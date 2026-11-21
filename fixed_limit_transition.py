"""Compare fixed-cohort limit states on the same paired identities, not totals."""
from pathlib import Path
from hashlib import sha256
from decimal import Decimal as D
from statistics import median
import json
from canonical_json import digest
from fixed_nov20_limit_audit import reading as current_replay
from st_limit_cohort_replay import replay

STORE=Path('/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk/recovered_limit_cohorts/20261109-20261119')

def analyze():
    old_path=Path('ST_LIMIT_COHORT_EVIDENCE_2026_11_21.json');old=json.loads(old_path.read_text())
    prior=replay(old['manifest'],STORE)
    if prior!=old['reading']:raise ValueError('old source replay differs')
    new_path=Path('FIXED_NOV20_LIMIT_AUDIT_2026_11_21.json');new=json.loads(new_path.read_text())
    if current_replay()!=new:raise ValueError('new source replay differs')
    before={r['symbol']:r for r in next(g for g in prior['groups'] if g['key']=='fixed150')['rows'] if r['date']=='2026-11-19'}
    after={r['code']:r for r in new['rows']};rows=[];excluded=[]
    for code in old['manifest']['fixed_symbols']:
        a=before[code];b=after.get(code)
        if a['status']!='paired' or b is None:
            gap=next((r['status'] for r in new['gaps'] if r['code']==code),None)
            excluded.append(dict(code=code,previous_status=a['status'],current_status=gap or 'paired'));continue
        if D(a['close'])!=D(b['reference']):raise ValueError('previous close/reference conflict')
        change=(D(b['close'])/D(a['close'])-1)*100;lower=D(b['lower'])
        rows.append(dict(code=code,previous_close=a['close'],current_close=b['close'],change_pct=str(change),previous_touch=a['touch_down'],previous_close_lower=a['close_at_down'],previous_one_price=a['one_price_down'],current_touch=D(b['low'])==lower,current_close_lower=D(b['close'])==lower,current_one_price=D(b['high'])==lower))
    previous_closed=[r for r in rows if r['previous_close_lower']]
    left=[r for r in previous_closed if not r['current_close_lower']]
    returns=[D(r['change_pct']) for r in rows]
    result=dict(version='fixed_limit_transition_v1',start='2026-11-19',through='2026-11-20',source_sha256={str(p):sha256(p.read_bytes()).hexdigest() for p in (old_path,new_path)},members=150,paired=len(rows),excluded=excluded,previous={k:sum(r['previous_'+k] for r in rows) for k in ('touch','close_lower','one_price')},current={k:sum(r['current_'+k] for r in rows) for k in ('touch','close_lower','one_price')},up=sum(x>0 for x in returns),down=sum(x<0 for x in returns),flat=sum(x==0 for x in returns),median_pct=str(median(returns)),left_close_lower=dict(count=len(left),up=sum(D(r['change_pct'])>0 for r in left),down=sum(D(r['change_pct'])<0 for r in left),flat=sum(D(r['change_pct'])==0 for r in left),codes=[r['code'] for r in left]),rows=rows,limits=['Same retrospectively paired identities, not all150 or complete current ST','Nov19 provider archive and Nov20 Tencent source differ; official close/reference cross-check retained','Leaving the closing lower bound does not mean daily price recovery or executable exit','Not an independent strategy validation or causal effect estimate'])
    result['closing_state_matrix']={key:sum((r['previous_close_lower'],r['current_close_lower'])==state for r in rows) for key,state in {'stayed_lower':(True,True),'left_lower':(True,False),'new_lower':(False,True),'neither_lower':(False,False)}.items()}
    result['content_digest']=digest(result);return result

if __name__=='__main__':
    result=analyze();Path('FIXED_LIMIT_TRANSITION_2026_11_21.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print({k:v for k,v in result.items() if k not in ('rows','limits')})
