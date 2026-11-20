"""Verify a separate three-day bridge before joining frozen windows."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import json
from verify_july_august_sse_basis import verify
from recent_breadth_inputs import verify_szse_capture
from recent_breadth_projection import verified_suspensions,halt_coverage,combine_day
from sse_history_archive import body,parse_prices


def build():
    path=Path('SEPTEMBER_BRIDGE_SSE_BASIS_EVIDENCE_2026_11_21.json');b=json.loads(path.read_text());verify(b,start='2026-09-01',through='2026-09-03')
    folder=Path(b['source_store'])/'szse-history';now=datetime.now(timezone.utc);sx=verify_szse_capture(folder,now=now);days=[p['date']for p in sx['points']]
    if days!=[r['date']for r in b['controls']]:raise ValueError('calendars differ')
    pool=b['pool'];pop={d:[c for c,r in pool.items()if r['listed']<=d and(r['ended']is None or r['ended']>d)]for d in days};basis=dict(pool=pool,populations=pop,window=dict(start=days[0],end=days[-1]))
    rawroot=Path('/Volumes/Leibniz/dev/st_research/v8_copilot/wt/market-recent-breadth-20261121/out/market-recent-breadth-20261121/sse-capture/full_prices');manifest=(rawroot/'complete.json').read_bytes();refs={r['code']:r for r in json.loads(manifest)['source_refs']};byday={d:{}for d in days}
    for code in sorted(pool):
        ref=refs[code];records=parse_prices(body(rawroot,ref,now),ref,basis,now)
        for d,r in records.items():byday[d][code]=r
    sf=Path('/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk/july_august_sse_basis/20261121/suspensions');s=verified_suspensions(sf,now);pairs,proofs=halt_coverage(s['rows'],pop,{},{});points=[]
    for day in days:
        packet=json.loads((folder/'days'/(day+'.json')).read_text());points.append(combine_day(day,pop[day],byday[day],pairs,packet['block']['rows']))
    return dict(version='september_breadth_bridge_v1',start=days[0],through=days[-1],sessions=len(days),basis_sha256=sha256(path.read_bytes()).hexdigest(),szse_source_digest=sx['source_digest'],sse_price_manifest_sha256=sha256(manifest).hexdigest(),suspension_digest=s['content_digest'],halt_intervals=proofs,points=points,limits=['Bridge source preparation, not independently validated trading rule','No index/ST alignment or whole-period publication yet'])


if __name__=='__main__':
    e=build();Path('SEPTEMBER_BREADTH_BRIDGE_EVIDENCE_2026_11_21.json').write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n');print(dict(days=e['sessions'],halts=sum(len(p['missing_prices_classified_as_halted'])for p in e['points'])))
