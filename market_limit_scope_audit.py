"""Audit broad-market pairing against official dated identities, never prefix guesses."""
from pathlib import Path
from datetime import datetime,timezone
from hashlib import sha256
from decimal import Decimal as D
import json,gzip
from sse_history_archive import read_basis,body,parse_prices
from recent_breadth_inputs import verify_szse_capture
from canonical_json import digest

BASE=Path('/Volumes/Leibniz/dev/st_research/v8_copilot/wt/market-recent-breadth-20261121/out/market-recent-breadth-20261121')
STORE=Path('/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk/recovered_limit_cohorts/20261109-20261119')


def build():
    now=datetime.now(timezone.utc);capture=BASE/'sse-capture';basis=read_basis(capture,now);sz_control=verify_szse_capture(BASE/'szse-history',now=now)
    path=Path('ST_LIMIT_COHORT_EVIDENCE_2026_11_21.json');manifest=json.loads(path.read_text())['manifest'];tables={};refs=[]
    for ref in manifest['sources']:
        if ref['api_name'] not in ('daily','stk_limit'):continue
        raw=gzip.decompress((STORE/(ref['response_sha256']+'.json.gz')).read_bytes())
        if sha256(raw).hexdigest()!=ref['response_sha256']or len(raw)!=ref['bytes']:raise ValueError('provider original differs')
        p=json.loads(raw)
        if p['code']!=0 or p['data']['fields']!=ref['fields'].split(',')or len(p['data']['items'])>=6000:raise ValueError('provider failed or capped')
        rows=[dict(zip(p['data']['fields'],r,strict=True))for r in p['data']['items']];bycode={r['ts_code']:r for r in rows};compact=ref['params']['trade_date'];day=compact[:4]+'-'+compact[4:6]+'-'+compact[6:]
        if len(bycode)!=len(rows)or any(r['trade_date']!=compact for r in rows):raise ValueError('provider identity/date duplicate')
        tables[day,ref['api_name']]=bycode;refs.append(ref)
    dates=sorted({day for day,api in tables});official={day:{}for day in dates}
    for ref in json.loads((capture/'full_prices/complete.json').read_text())['source_refs']:
        rows=parse_prices(body(capture/'full_prices',ref,now),ref,basis,now)
        for day in dates:
            if day in rows and rows[day]['is_trading']:official[day][ref['code']+'.SH']=dict(close=rows[day]['last'],reference=rows[day]['prev_close'])
    breadth=json.loads(Path('LONG_MARKET_BREADTH_EVIDENCE_2026_11_21.json').read_text());controls={r['date']:r['all']for r in breadth['points']};days=[]
    for day in dates:
        for r in json.loads((BASE/'szse-history/days'/(day+'.json')).read_text())['block']['rows']:
            if r['is_trading']:official[day][r['ts_code']]=dict(close=str(r['last']),reference=str(r['prev_close']))
        expected=official[day];q=tables[day,'daily'];limits=tables[day,'stk_limit'];missing=[];conflicts=[];unpaired=[];hits=dict(close_at_down=0,touch_down=0,one_price_down=0);paired=0
        if len(expected)!=controls[day]['observed_trading_stocks']:raise ValueError('official activity denominator changed')
        for code,o in expected.items():
            if code not in q or D(str(q[code]['vol']))<=0:missing.append(code);continue
            r=q[code];p={k:D(str(r[k]))for k in ('open','high','low','close','pre_close')}
            if p['close']!=D(o['close'])or p['pre_close']!=D(o['reference']):conflicts.append(code)
            if code not in limits:unpaired.append(dict(code=code,reason='missing_limit'));continue
            l={k:D(str(limits[code][k]))for k in ('pre_close','up_limit','down_limit')}
            if min(p.values())<=0 or min(l.values())<=0 or not l['down_limit']<=p['low']<=min(p['open'],p['close'])<=max(p['open'],p['close'])<=p['high']<=l['up_limit']or p['pre_close']!=l['pre_close']:
                unpaired.append(dict(code=code,reason='bounds_or_reference'));continue
            paired+=1;hits['close_at_down']+=p['close']==l['down_limit'];hits['touch_down']+=p['low']==l['down_limit'];hits['one_price_down']+=all(p[k]==l['down_limit']for k in ('open','high','low','close'))
        days.append(dict(date=day,official_trading=len(expected),provider_trading_in_official_set=len(expected)-len(missing),paired=paired,missing=missing,official_close_or_reference_conflicts=conflicts,unpaired=unpaired,limit_counts_in_paired=hits,naive_prefix_omissions=sorted(c for c in expected if c[:3]not in ('000','001','002','003','600','601','603','605','688','689','300','301'))))
    e=dict(version='market_limit_scope_audit_v1',source_cohort_sha256=sha256(path.read_bytes()).hexdigest(),source_refs=refs,sse_basis_digest=basis['basis_capture_digest'],szse_control_digest=sz_control['source_digest'],breadth_sha256=sha256(Path('LONG_MARKET_BREADTH_EVIDENCE_2026_11_21.json').read_bytes()).hexdigest(),days=days,limits=['Coverage audit; price conflicts and unpaired securities remain unresolved','Official close/reference cross-check is not independent official limit certification','Provider actual limits, not percentage-inferred limits; no order-queue execution claim','Sources observed retrospectively; not proof of then-available data','Use official daily identities including 302132.SZ rather than hand-written prefixes'])
    e['content_digest']=digest(e);return e


if __name__=='__main__':
    e=build();Path('MARKET_LIMIT_SCOPE_AUDIT_2026_11_21.json').write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n');print([{k:d[k]for k in ('date','official_trading','paired','missing','official_close_or_reference_conflicts','unpaired','limit_counts_in_paired')}for d in e['days']])
