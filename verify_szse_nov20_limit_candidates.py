"""Replay partial coverage; unknowns never become negative limit observations."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal as D
import json
from szse_ohlc_field_review import analyze
from verify_eastmoney_limit_candidate import verify as mapping_verify


def verify(pack):
    path=Path('SZSE_OHLC_FIELD_EVIDENCE_2026_11_21.json');raw=path.read_bytes()
    if sha256(raw).hexdigest()!=pack['control_sha256']:raise ValueError('control changed')
    e=json.loads(raw)
    folder=Path('/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk/recent_breadth_history/sources/895130d3f8b80b5e2f8ef947dcb67a3d6a7c9bbe849b91dd2e3c7b62cda89f47/szse-history')
    controls=analyze(e,folder,json.loads(Path('RISK_LIST_NOV20_EVIDENCE_2026_11_21.json').read_text()))
    if controls!=e['reading']:raise ValueError('official replay changed')
    m=json.loads(Path('EASTMONEY_LIMIT_CANDIDATE_2026_11_21.json').read_text())
    mapping_verify(Path(m['source_store']),m,json.loads(Path('QIHUAN_OHLC_CROSSCHECK_EVIDENCE_2026_11_21.json').read_text()))
    expected={r['symbol']:r for r in controls['rows']};rows=pack['rows']
    if len(rows)!=len(expected) or {r['symbol']for r in rows}!=set(expected):raise ValueError('scope changed')
    counts=dict(matched=0,official_no_trade_excluded=0,unresolved=0)
    hits={k:[]for k in ['touch_lower','close_lower','one_price_lower','close_upper']}
    for r in rows:
        c=expected[r['symbol']]
        if r['official_trading']!=c['is_trading']:raise ValueError('trade status changed')
        if r['status']=='unresolved':
            if not r.get('error') or 'reading'in r:raise ValueError('unresolved must retain gap')
            counts['unresolved']+=1;continue
        raw=(Path(pack['source_store'])/r['sha256']).read_bytes()
        if sha256(raw).hexdigest()!=r['sha256'] or len(raw)!=r['bytes']:raise ValueError('quote bytes changed')
        body=json.loads(raw);d=body['data']
        if body['rc']!=0 or d!=r['data'] or d['f57']!=r['symbol'][:6] or d['f58']!=c['name']:raise ValueError('identity changed')
        if not c['is_trading']:
            if r['status']!='official_no_trade_excluded' or 'reading'in r:raise ValueError('no trade not excluded')
            counts['official_no_trade_excluded']+=1;continue
        if r['status']!='matched' or d['f59']!=2 or datetime.fromtimestamp(d['f86'],ZoneInfo('Asia/Shanghai')).date().isoformat()!='2026-11-20':raise ValueError('quote date/precision changed')
        price=lambda k:D(d[k])/100
        if [price(k)for k in ['f46','f44','f45','f43','f60']]!=[D(c[k])for k in ['open','high','low','close','reference']]:raise ValueError('OHLC differs')
        if not price('f52')<=price('f45')<=price('f43')<=price('f44')<=price('f51'):raise ValueError('bounds differ')
        value=dict(upper=str(price('f51')),lower=str(price('f52')),touch_lower=price('f45')==price('f52'),close_lower=price('f43')==price('f52'),one_price_lower=price('f44')==price('f45')==price('f52'),close_upper=price('f43')==price('f51'))
        if value!=r['reading']:raise ValueError('projection changed')
        counts['matched']+=1
        for k in hits:
            if value[k]:hits[k].append(r['symbol'])
    return dict(counts=counts,hits=hits,complete_trading_coverage=counts['matched']==controls['trading'])

if __name__=='__main__':
    print(json.dumps(verify(json.loads(Path('SZSE_NOV20_LIMIT_CANDIDATES_2026_11_21.json').read_text())),ensure_ascii=False,indent=2))
