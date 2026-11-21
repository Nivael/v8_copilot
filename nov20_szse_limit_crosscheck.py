"""Compare two saved quote channels in an explicitly dated official scope."""
from pathlib import Path
from hashlib import sha256
from decimal import Decimal as D
import json
from canonical_json import digest
from tencent_nov20_market_audit import build
from verify_szse_nov20_limit_candidates import verify

def reading():
    market_path=Path('TENCENT_NOV20_MARKET_AUDIT_2026_11_21.json')
    market=json.loads(market_path.read_text())
    if build()!=market: raise ValueError('market replay changed')
    partial_path=Path('SZSE_NOV20_LIMIT_EVIDENCE_2026_11_21.json');partial=json.loads(partial_path.read_text())
    prior=verify(partial)
    controls=json.loads(Path('SZSE_OHLC_FIELD_EVIDENCE_2026_11_21.json').read_text())['reading']
    quotes={r['code']:r for r in market['observations']};old={r['symbol']:r for r in partial['rows']}
    matched=[];recovered=[];excluded=[];unresolved=[];cross_channel=[]
    hits={key:[] for key in ('touch_lower','close_lower','one_price_lower')}
    for control in controls['rows']:
        code=control['symbol']
        if not control['is_trading']:
            if code in quotes: raise ValueError('official nontrading identity appeared in active market')
            excluded.append(code);continue
        row=quotes.get(code)
        if not row: unresolved.append(dict(code=code,reason='Tencent missing'));continue
        if any(D(row[k])!=D(control[k]) for k in ('open','high','low','close','reference')):
            raise ValueError('official OHLC conflict: '+code)
        previous=old[code]
        if previous['status']=='matched':
            data=previous['data'];fields={'open':'f46','high':'f44','low':'f45','close':'f43','reference':'f60','upper':'f51','lower':'f52'}
            if any(D(row[k])!=D(data[field])/100 for k,field in fields.items()):
                raise ValueError('cross-channel quote conflict: '+code)
            cross_channel.append(code)
        elif previous['status']=='unresolved': recovered.append(code)
        else: raise ValueError('unexpected prior active status')
        matched.append(code)
        lower=D(row['lower'])
        if D(row['low'])==lower: hits['touch_lower'].append(code)
        if D(row['close'])==lower: hits['close_lower'].append(code)
        if D(row['high'])==lower: hits['one_price_lower'].append(code)
    result=dict(version='nov20_szse_limit_crosscheck_v1',date='2026-11-20',market_audit_sha256=sha256(market_path.read_bytes()).hexdigest(),prior_partial_sha256=sha256(partial_path.read_bytes()).hexdigest(),official_control_sha256=partial['control_sha256'],members=len(controls['rows']),matched=matched,official_no_trade=excluded,unresolved=unresolved,recovered=recovered,cross_channel_agreement=cross_channel,hits=hits,prior_reading=prior,limits=['Explicitly dated SZSE mainboard risk-warning 74 only; not all ST or all exchanges','Two quote channels agreeing do not prove independent underlying feeds or exchange-certified limit prices','Old failed Eastmoney capture is retained; recovered observations use separately saved Tencent quotes','OHLC and limits do not prove queues, fills or executable exits','No new independent strategy validation'])
    result['content_digest']=digest(result);return result

if __name__=='__main__':
    result=reading();Path('NOV20_SZSE_LIMIT_CROSSCHECK_2026_11_21.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print({k:len(result[k]) for k in ('matched','official_no_trade','unresolved','recovered','cross_channel_agreement')},result['hits'])
