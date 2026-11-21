"""Split existing signal follow-up at the next close; no execution assumption."""
from pathlib import Path
from hashlib import sha256
from decimal import Decimal as D
import json
from long_breadth_wait_comparison import analyze_wait


def analyze():
    path = Path('LONG_BREADTH_WAIT_EVIDENCE_2026_11_21.json')
    saved = json.loads(path.read_text())
    if analyze_wait() != saved:
        raise ValueError('waiting evidence replay differs')
    daily = {r['date']: r for r in saved['inputs']['daily']}
    signals = json.loads(Path('LONG_BREADTH_ST_ALIGNMENT_EVIDENCE_2026_11_21.json').read_text())['reading']['signals']
    from build_long_index_reading import reading as index_reading
    index = index_reading()
    closes = {r['date']: D(str(r['close'])) for r in index['rows']}
    rows = []
    for signal in signals:
        following = signal['following_dates']
        if not following:
            raise ValueError('no next-close observation')
        first, rest = following[0], following[1:]
        def compound(dates, key):
            if not dates:
                return None
            value = D(1)
            for date in dates:
                value *= 1 + D(str(daily[date][key])) / 100
            return (value - 1) * 100
        parts = {}
        for label, key in [('st', 'return_pct'), ('market', 'market_pct')]:
            a, b = compound([first], key), compound(rest, key)
            whole = compound(following, key)
            if b is not None and abs(((1+a/100)*(1+b/100)-1)*100-whole) > D('1e-20'):
                raise ValueError('split does not reconcile')
            if abs(whole-D(str(signal[label+'_pct']))) > D('1e-10'):
                raise ValueError('original outcome differs')
            parts[label] = dict(first_day_pct=float(a), remaining_pct=float(b) if b is not None else None, whole_pct=float(whole))
        for start, end, claimed in [(signal['date'], first, parts['market']['first_day_pct']), (first, signal['through'], parts['market']['remaining_pct'])]:
            if claimed is not None and abs(float((closes[end]/closes[start]-1)*100)-claimed) > .002:
                raise ValueError('official index endpoint conflict')
        rows.append(dict(signal_date=signal['date'], next_close=first, through=signal['through'], complete_five=signal['complete_five'], remaining_sessions=len(rest), **parts))
    return dict(index_evidence_sha256=index['evidence_sha256'], version='next_close_observation_split_v1', waiting_sha256=sha256(path.read_bytes()).hexdigest(), alignment_sha256=sha256(Path('LONG_BREADTH_ST_ALIGNMENT_EVIDENCE_2026_11_21.json').read_bytes()).hexdigest(), rows=rows, limits=['Next close is an observation boundary, not a feasible sale price', 'First day includes the overnight and full next session; not a measured overnight gap', 'Full 5-session windows split 1+4; the partial 3-session window splits 1+2', 'Dynamic ST reference is not a held or executable portfolio', 'No transaction cost, intraday queue or future threshold optimization'])


if __name__ == '__main__':
    result = analyze()
    Path('LONG_SIGNAL_NEXT_CLOSE_EVIDENCE_2026_11_21.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result['rows'], ensure_ascii=False, indent=2))
