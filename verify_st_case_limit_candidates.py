"""Replay selected Nov20 quote candidates against frozen OHLC controls."""
import hashlib
import json
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path
from zoneinfo import ZoneInfo
from st_case_ohlc_crosscheck import crosscheck


def verify():
    pack = json.loads(Path('ST_CASE_LIMIT_CANDIDATES_2026_11_21.json').read_text())
    from verify_eastmoney_limit_candidate import verify as verify_mapping
    mapping = json.loads(Path(pack['field_mapping_evidence']).read_text())
    verify_mapping(Path(mapping['source_store']), mapping, json.loads(Path('QIHUAN_OHLC_CROSSCHECK_EVIDENCE_2026_11_21.json').read_text()))
    raw = Path('ST_CASE_OHLC_CROSSCHECK_EVIDENCE_2026_11_21.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != pack['ohlc_evidence_sha256']:
        raise ValueError('OHLC evidence changed')
    control = json.loads(raw)
    replay = crosscheck(control, '/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk/recovered_limit_cohorts/20261109-20261119')
    if replay != control['reading']:
        raise ValueError('OHLC replay changed')
    cases = {c['symbol']: c for c in replay['cases']}
    if len(pack['rows']) != 3 or {r['symbol'] for r in pack['rows']} != set(cases):
        raise ValueError('selected scope changed')
    result = []
    for r in pack['rows']:
        raw = (Path(pack['source_store']) / r['sha256']).read_bytes()
        if len(raw) != r['bytes'] or hashlib.sha256(raw).hexdigest() != r['sha256']:
            raise ValueError('quote bytes changed')
        body = json.loads(raw)
        d = body['data']; c = cases[r['symbol']]; n = c['new_day']
        if body['rc'] != 0 or d != r['data'] or d['f57'] != r['symbol'][:6] or d['f58'] != c['name'] or d['f59'] != 2:
            raise ValueError('quote identity changed')
        time = datetime.fromtimestamp(d['f86'], ZoneInfo('Asia/Shanghai'))
        if time.date().isoformat() != '2026-11-20':
            raise ValueError('quote date changed')
        price = lambda k: D(d[k])/D(100)
        if [price(k) for k in ['f46','f43','f44','f45','f60']] != [D(n[k]) for k in ['open','close','high','low','previous_observed_close']]:
            raise ValueError('OHLC mismatch')
        if not price('f52') <= price('f45') <= price('f43') <= price('f44') <= price('f51'):
            raise ValueError('quote outside limits')
        reading = dict(trade_time=time.isoformat(), upper=str(price('f51')), lower=str(price('f52')), close=str(price('f43')), touch_lower=price('f45')==price('f52'), close_lower=price('f43')==price('f52'), one_price=price('f44')==price('f45'))
        if reading != r['reading']:
            raise ValueError('projection changed')
        result.append(dict(symbol=r['symbol'], **reading))
    return result


if __name__ == '__main__':
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
