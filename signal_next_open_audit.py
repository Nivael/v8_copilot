"""Inspect saved next-session OHLC/limits, without inferring order execution."""
from pathlib import Path
from hashlib import sha256
from decimal import Decimal as D
import gzip,json
from st_limit_cohort_replay import replay
from market_limit_scope_audit import build as market_audit,STORE
FOCUS={'603398.SH':'沐邦','002514.SZ':'宝馨','600363.SH':'联光','002667.SZ':'威领','688053.SH':'思科瑞'}


def analyze():
    source=Path('ST_LIMIT_COHORT_EVIDENCE_2026_11_21.json');saved=json.loads(source.read_text())
    if replay(saved['manifest'],STORE)!=saved['reading']:
        raise ValueError('cohort originals differ')
    market=market_audit()
    if market!=json.loads(Path('MARKET_LIMIT_SCOPE_AUDIT_2026_11_21.json').read_text()):
        raise ValueError('official closing/reference audit differs')
    path=Path('LONG_SIGNAL_NEXT_CLOSE_EVIDENCE_2026_11_21.json');signal_evidence=json.loads(path.read_text())
    from long_signal_next_close import analyze as signal_replay
    if signal_replay()!=signal_evidence:raise ValueError('signal replay differs')
    signals=signal_evidence['rows']
    from long_breadth_st_alignment import INPUT,INPUT_SHA
    if sha256(INPUT.read_bytes()).hexdigest()!=INPUT_SHA:raise ValueError('frozen identity input differs')
    frozen=json.loads(gzip.decompress(INPUT.read_bytes()))
    if set(FOCUS)!=set(frozen['current_extension']['tracked_quotes']):raise ValueError('focus identity differs from tracked source')
    tables={};refs=[]
    for ref in saved['manifest']['sources']:
        if ref['params']['trade_date']!='20261117' or ref['api_name'] not in ('daily','stk_limit','stock_st'):continue
        raw=gzip.decompress((STORE/(ref['response_sha256']+'.json.gz')).read_bytes())
        if sha256(raw).hexdigest()!=ref['response_sha256']:raise ValueError('saved response differs')
        response=json.loads(raw)['data'];tables[ref['api_name']]={row[response['fields'].index('ts_code')]:dict(zip(response['fields'],row,strict=True)) for row in response['items']};refs.append(ref)
    if set(tables)!={'daily','stk_limit','stock_st'}:raise ValueError('required next-session tables absent')
    matched=next(row for row in signals if row['signal_date']=='2026-11-16')
    if matched['next_close']!='2026-11-17':raise ValueError('next-session date differs')
    verified=next(day for day in market['days'] if day['date']=='2026-11-17')
    if verified['unpaired'] or verified['missing'] or verified['official_close_or_reference_conflicts']:
        raise ValueError('next-session reference unresolved')
    def paired(code):
        q=tables['daily'].get(code);limit=tables['stk_limit'].get(code)
        if not q:return dict(symbol=code,status='missing_daily')
        if D(str(q['vol']))<=0:return dict(symbol=code,status='no_volume')
        if not limit:return dict(symbol=code,status='missing_limit')
        p={k:D(str(q[k])) for k in ('open','high','low','close','pre_close')};lo=D(str(limit['down_limit']));hi=D(str(limit['up_limit']))
        if min(p.values())<=0 or p['pre_close']!=D(str(limit['pre_close'])) or not lo<=p['low']<=min(p['open'],p['close'])<=max(p['open'],p['close'])<=p['high']<=hi:
            raise ValueError('unresolved OHLC or actual limit')
        return dict(symbol=code,status='paired',**{k:str(q[k]) for k in ('open','high','low','close','pre_close')},down_limit=str(limit['down_limit']),up_limit=str(limit['up_limit']),open_vs_reference_pct=float((p['open']/p['pre_close']-1)*100),open_at_lower=p['open']==lo,close_at_lower=p['close']==lo,touched_lower=p['low']==lo,one_price_lower=all(p[k]==lo for k in ('open','high','low','close')),volume_reported=str(q['vol']))
    focus=[dict(paired(code),label=label,in_saved_st_mainboard=code in tables['stock_st'] and not code.startswith('688')) for code,label in FOCUS.items()]
    groups=[]
    for g in saved['reading']['groups']:
        originals=[r for r in g['rows'] if r['date']=='2026-11-17'];rows=[paired(r['symbol']) for r in originals];valid=[r for r in rows if r['status']=='paired']
        groups.append(dict(key=g['key'],members=len(rows),paired=len(valid),open_at_lower=sum(r['open_at_lower'] for r in valid),close_at_lower=sum(r['close_at_lower'] for r in valid),one_price_lower=sum(r['one_price_lower'] for r in valid),unpaired=[r for r in rows if r['status']!='paired']))
    return dict(input_asset_sha256=INPUT_SHA,version='signal_next_open_audit_v1',signal_date='2026-11-16',next_session='2026-11-17',signal_evidence_sha256=sha256(path.read_bytes()).hexdigest(),cohort_evidence_sha256=sha256(source.read_bytes()).hexdigest(),market_scope_evidence_sha256=sha256(Path('MARKET_LIMIT_SCOPE_AUDIT_2026_11_21.json').read_bytes()).hexdigest(),sources=refs,focus=focus,groups=groups,coverage=[dict(signal_date=r['signal_date'],next_session=r['next_close'],available=r['signal_date']=='2026-11-16') for r in signals],limits=['Only the Nov16 signal has a next day in the saved nine-session OHLC/limit scope', 'Open is a reported opening price, not a certified executable order price', 'Open changes use the same-day pre-close reference; corporate-action adjustment is not original previous-close return', 'Official audit controls close and reference, not independently the open or actual lower limit', 'One-price lower and volume cannot establish any individual order fill or queue position', 'Five selected cases are not a representative portfolio or personal positions'])


if __name__=='__main__':
    e=analyze();Path('SIGNAL_NEXT_OPEN_AUDIT_EVIDENCE_2026_11_21.json').write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(focus=e['focus'],groups=e['groups']),ensure_ascii=False,indent=2))
