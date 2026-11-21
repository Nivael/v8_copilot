"""Project verified daily breadth, deriving each state from its prefix only."""
from pathlib import Path
from hashlib import sha256
import json
from canonical_json import digest


def project(points):
    rows=[];streak=0;start=None
    for p in points:
        a=p['all'];n=a['observed_trading_stocks']
        if n<=0 or a['advancing']+a['declining']+a['flat']!=n or n+a['nontrading_stocks']!=a['listed_source_stocks']:
            raise ValueError('daily denominator differs')
        if not 0<=a['declining_5pct_or_more']<=a['declining']:
            raise ValueError('tail count differs')
        weak=2*a['advancing']<n
        if weak:
            if streak==0:start=p['date']
            streak+=1
        else:streak=0;start=None
        rows.append(dict(date=p['date'],trading=n,nontrading=a['nontrading_stocks'],advancing=a['advancing'],advancing_pct=a['advancing']/n*100,declining=a['declining'],flat=a['flat'],median_return_pct=a['median_return_pct'],tail=a['declining_5pct_or_more'],tail_pct=a['declining_5pct_or_more']/n*100,streak=streak,weak_start=start,third_day_first_signal=streak==3))
    return rows


def build():
    path=Path('LONG_MARKET_BREADTH_EVIDENCE_2026_11_21.json');raw=path.read_bytes();e=json.loads(raw);coverage=json.loads(Path('web/src/longBreadthCoverage.json').read_text())
    content=dict(e);signature=content.pop('content_digest')
    if digest(content)!=signature or sha256(raw).hexdigest()!=coverage['evidence_sha256']:
        raise ValueError('verified breadth binding changed')
    if len(e['points'])!=e['sessions'] or e['sessions']!=coverage['sessions'] or [p['date']for p in e['points']]!=sorted(set(p['date']for p in e['points'])):
        raise ValueError('daily coverage changed')
    return dict(evidence_sha256=coverage['evidence_sha256'],start=e['start'],through=e['through'],rows=project(e['points']),historical_PIT=False)


if __name__=='__main__':
    Path('web/src/longBreadthReplay.json').write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n')
