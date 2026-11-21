"""Replay saved public quotes against official active identities; never execute JS."""
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import re
from canonical_json import digest
from market_limit_scope_audit import BASE
from sse_history_archive import read_basis, body, parse_prices
from recent_breadth_inputs import verify_szse_capture

CAPTURE = Path('TENCENT_NOV20_MARKET_CAPTURE_2026_11_21.json')

def checked_digest(packet):
    if digest({k:v for k,v in packet.items() if k != 'content_digest'}) != packet['content_digest']:
        raise ValueError('content digest differs')

def raw_source(store, ref):
    raw = (store / (ref['sha256'] + '.bin')).read_bytes()
    if sha256(raw).hexdigest() != ref['sha256'] or len(raw) != ref['bytes']:
        raise ValueError('source bytes differ')
    return raw

def parse_quotes(raw):
    text = raw.decode('gb18030')
    pattern = re.compile(r'\s*v_((?:sh|sz)\d{6})="([^"\r\n]*)";')
    rows = {}; position = 0
    for match in pattern.finditer(text):
        if text[position:match.start()].strip(): raise ValueError('unexpected quote syntax')
        if match[1] in rows: raise ValueError('duplicate quote')
        rows[match[1]] = match[2].split('~'); position = match.end()
    if text[position:].strip(): raise ValueError('unexpected trailing syntax')
    return rows

def official_basis():
    now = datetime.now(timezone.utc); capture = BASE / 'sse-capture'
    basis = read_basis(capture, now); sz = verify_szse_capture(BASE / 'szse-history', now=now)
    official = {}
    for ref in json.loads((capture/'full_prices/complete.json').read_text())['source_refs']:
        row = parse_prices(body(capture/'full_prices',ref,now),ref,basis,now).get('2026-11-20')
        if row and row['is_trading']:
            official[ref['code']+'.SH'] = dict(close=str(row['last']),reference=str(row['prev_close']))
    for row in json.loads((BASE/'szse-history/days/2026-11-20.json').read_text())['block']['rows']:
        if row['is_trading']:
            official[row['ts_code']] = dict(close=str(row['last']),reference=str(row['prev_close']))
    return official,basis['basis_capture_digest'],sz['source_digest']

def build():
    packet = json.loads(CAPTURE.read_text()); checked_digest(packet)
    if packet['date'] != '2026-11-20': raise ValueError('capture date differs')
    basis = packet['official_basis']; checked_digest(basis)
    official,sse,sz = official_basis()
    if official != basis['official'] or sse != basis['sse_basis_digest'] or sz != basis['szse_control_digest']:
        raise ValueError('official source replay differs')
    breadth_path = Path('LONG_MARKET_BREADTH_EVIDENCE_2026_11_21.json')
    if sha256(breadth_path.read_bytes()).hexdigest() != basis['breadth_sha256']: raise ValueError('breadth binding differs')
    point = next(p for p in json.loads(breadth_path.read_text())['points'] if p['date']==packet['date'])
    if len(official) != point['all']['observed_trading_stocks']: raise ValueError('denominator differs')
    store = Path(packet['source_store']); publisher = {r['name']:r for r in packet['publisher_sources']}
    html = raw_source(store,publisher['qq-page']).decode('utf-8')
    script = raw_source(store,publisher['qq-bundle']).decode('utf-8')
    if publisher['qq-bundle']['url'] not in html: raise ValueError('publisher script link absent')
    start = script.index('adaptHS:function(t){var e='); end = script.index(',adaptPT:function',start)
    adapter = script[start:end]
    mapping = ['price_ceiling:t[47]','price_floor:t[48]','secu_code:t[2]','dqj:t[3]','jkj:t[5]','utime:ot(t[30])','zdj:t[34]','zgj:t[33]','zsj:t[4]','cjl:t[36]']
    if not all(item in adapter for item in mapping): raise ValueError('publisher mapping differs')
    seen=set(); observations=[]; unresolved=[]
    counts=dict(open_at_down=0,touch_down=0,close_at_down=0,one_price_down=0)
    for index,ref in enumerate(packet['quote_batches']):
        if ref['batch'] != index or ref.get('status') != 200: raise ValueError('batch failed or unordered')
        requested=ref['requested']; tickers=[('sh' if c.endswith('.SH') else 'sz')+c[:6] for c in requested]
        if ref['url'] != 'https://qt.gtimg.cn/q='+','.join(tickers): raise ValueError('request binding differs')
        if seen.intersection(requested) or len(set(requested))!=len(requested): raise ValueError('duplicate request')
        seen.update(requested); rows=parse_quotes(raw_source(store,ref))
        if set(rows)-set(tickers): raise ValueError('unexpected response identity')
        observed=datetime.fromisoformat(ref['observed_at'])
        if observed.tzinfo is None or observed < datetime(2026,11,20,7,tzinfo=timezone.utc): raise ValueError('observation before close')
        for code,ticker in zip(requested,tickers,strict=True):
            fields=rows.get(ticker)
            try:
                if not fields or len(fields)<49 or fields[2]!=code[:6]: raise ValueError('missing or wrong identity')
                stamp=datetime.strptime(fields[30],'%Y%m%d%H%M%S')
                if stamp.date().isoformat()!=packet['date'] or stamp.hour<15: raise ValueError('wrong date or pre-close quote')
                values=[Decimal(fields[i]) for i in (3,4,5,33,34,36,47,48)]
                if any(not v.is_finite() or v<=0 for v in values): raise ValueError('nonpositive or nonfinite field')
                close,reference,opening,high,low,volume,upper,lower=values
                control=official[code]
                if close!=Decimal(control['close']) or reference!=Decimal(control['reference']): raise ValueError('official close/reference conflict')
                if not lower<=low<=min(opening,close)<=max(opening,close)<=high<=upper: raise ValueError('bounds or OHLC conflict')
            except (ValueError,ArithmeticError,KeyError) as error:
                unresolved.append(dict(code=code,reason=str(error)));continue
            row=dict(code=code,timestamp=fields[30],close=str(close),reference=str(reference),open=str(opening),high=str(high),low=str(low),volume=str(volume),upper=str(upper),lower=str(lower))
            observations.append(row)
            counts['open_at_down']+=opening==lower;counts['touch_down']+=low==lower;counts['close_at_down']+=close==lower;counts['one_price_down']+=high==lower
    if seen!=set(official): raise ValueError('requested universe differs')
    result=dict(version='tencent_nov20_market_audit_v1',date=packet['date'],capture_sha256=sha256(CAPTURE.read_bytes()).hexdigest(),breadth_sha256=basis['breadth_sha256'],official_trading=len(official),paired=len(observations),unresolved=unresolved,limit_counts_in_paired=counts,publisher_adapter_sha256=sha256(adapter.encode()).hexdigest(),publisher_field_mapping=mapping,observations=observations,limits=['Active ordinary A shares on SSE and SZSE only; excludes nontrading securities, B shares and Beijing exchange','Official close/reference agreement does not independently certify Tencent limit prices or intraday OHLC','Retrospective capture, not proof of then-available data','Touch/close/one-price observations do not establish queues, fills or executable exits','No legal ST membership certification or new independent strategy validation'])
    result['content_digest']=digest(result);return result

if __name__=='__main__':
    result=build();Path('TENCENT_NOV20_MARKET_AUDIT_2026_11_21.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print({k:v for k,v in result.items() if k not in ('observations','publisher_field_mapping','limits')})
