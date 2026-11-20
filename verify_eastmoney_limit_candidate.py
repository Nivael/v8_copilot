"""Read-only replay of one dated quote; never executes publisher JavaScript."""
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo


def verify(root: Path, pack: dict, official: dict) -> dict:
    bodies = []
    for ref in pack['source_refs']:
        raw = (root / ref['sha256']).read_bytes()
        if len(raw) != ref['bytes'] or hashlib.sha256(raw).hexdigest() != ref['sha256']:
            raise ValueError('source bytes changed')
        bodies.append(raw)
    script = bodies[1].decode()
    for fragment in pack['field_mapping_excerpts'].values():
        if fragment not in script:
            raise ValueError('field mapping changed')
    for fragment in ['(e/Math.pow(10,t)).toFixed(t)', 'new Date(1e3*e)']:
        if fragment not in script:
            raise ValueError('formatter mapping missing')
    payload = json.loads(bodies[2])
    d = payload['data']
    if payload['rc'] != 0 or d != pack['returned_data'] or d['f57'] != '000826':
        raise ValueError('quote identity or contents changed')
    date = datetime.fromtimestamp(d['f86'], ZoneInfo('Asia/Shanghai')).date().isoformat()
    if date != '2026-11-20' or d['f59'] != 2:
        raise ValueError('unexpected quote date or precision')
    raw_official = official['official_text'].encode()
    if hashlib.sha256(raw_official).hexdigest() != official['official_source']['sha256']:
        raise ValueError('official control bytes changed')
    source = json.loads(raw_official)['data']
    if source['code'] != d['f57'] or source['name'] != d['f58']:
        raise ValueError('official security identity mismatch')
    row = next(r for r in source['picupdata'] if r[0] == date)
    previous = next(r for r in source['picupdata'] if r[0] == '2026-11-19')
    price = lambda key: Decimal(d[key]) / Decimal(100)
    if [price(k) for k in ['f46', 'f43', 'f45', 'f44']] != [Decimal(str(x)) for x in row[1:5]]:
        raise ValueError('official OHLC mismatch')
    if price('f60') != Decimal(str(previous[2])):
        raise ValueError('reference close mismatch')
    if not price('f52') <= price('f45') <= price('f43') <= price('f44') <= price('f51'):
        raise ValueError('OHLC outside reported bounds')
    return {'symbol': d['f57'], 'date': date, 'upper': str(price('f51')), 'lower': str(price('f52')), 'close': str(price('f43')), 'touched_lower': price('f45') == price('f52'), 'closed_lower': price('f43') == price('f52'), 'one_price': price('f44') == price('f45'), 'scope': 'one quote only; no executable fill inference'}


if __name__ == '__main__':
    pack = json.loads(Path('EASTMONEY_LIMIT_CANDIDATE_2026_11_21.json').read_text())
    official = json.loads(Path('QIHUAN_OHLC_CROSSCHECK_EVIDENCE_2026_11_21.json').read_text())
    print(json.dumps(verify(Path(pack['source_store']), pack, official), ensure_ascii=False, indent=2))
