"""Two-venue early breadth after dated listing, halt and raw-price reconciliation."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import json
from sse_history_archive import body,parse_prices
from early_sse_halt_reconciliation import reconcile
from recent_breadth_inputs import verify_szse_capture
from recent_breadth_projection import combine_day


def build(szse_folder):
    bp=Path('JULY_AUGUST_SSE_BASIS_EVIDENCE_2026_11_21.json');basis=json.loads(bp.read_text())
    hp=Path('EARLY_SSE_HALT_RECONCILIATION_EVIDENCE_2026_11_21.json');halts=json.loads(hp.read_text())
    if reconcile()!=halts or halts['unresolved']:raise ValueError('halt reconciliation changed')
    now=datetime.now(timezone.utc);sx=verify_szse_capture(Path(szse_folder),now=now)
    days=[r['date']for r in basis['controls']]
    if [r['date']for r in sx['points']]!=days:raise ValueError('two-venue calendars differ')
    pool=basis['pool'];pop={day:[c for c,r in pool.items()if r['listed']<=day and(r['ended']is None or r['ended']>day)]for day in days}
    parse_basis=dict(pool=pool,populations=pop,window=dict(start=days[0],end=days[-1]));pairs={(day,r['symbol'])for r in halts['intervals']for day in r['days']}
    root=Path('/Volumes/Leibniz/dev/st_research/v8_copilot/wt/market-recent-breadth-20261121/out/market-recent-breadth-20261121/sse-capture/full_prices');manifest=json.loads((root/'complete.json').read_text());refs={r['code']:(r,root)for r in manifest['source_refs']}
    ep=Path('EARLY_SSE_EXIT_PRICE_EVIDENCE_2026_11_21.json');extra=json.loads(ep.read_text());refs.update({r['code']:(r,Path(extra['source_store']))for r in extra['sources']})
    byday={d:{}for d in days}
    for code in sorted(pool):
        ref,folder=refs[code];records=parse_prices(body(folder,ref,now),ref,parse_basis,now)
        for day,record in records.items():byday[day][code]=record
    points=[]
    for day in days:
        packet=json.loads((Path(szse_folder)/'days'/(day+'.json')).read_text())
        points.append(combine_day(day,pop[day],byday[day],pairs,packet['block']['rows']))
    return dict(version='early_two_venue_breadth_v1',scope='SSE_SZSE_ordinary_A_shares',szse_source_folder=str(szse_folder),start=days[0],through=days[-1],sessions=len(days),basis_sha256=sha256(bp.read_bytes()).hexdigest(),halts_sha256=sha256(hp.read_bytes()).hexdigest(),extra_sha256=sha256(ep.read_bytes()).hexdigest(),szse_capture=sx,points=points,limits=['Retrospective source observation; no historical same-day execution claim','Fixed decline of 5 percent is not actual limit-down','Separate early window; Sep1-Sep3 bridge not included','No calibrated crisis score or independent strategy validation'])


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--szse-folder',type=Path,required=True);a=p.parse_args();e=build(a.szse_folder)
    Path('EARLY_MARKET_BREADTH_EVIDENCE_2026_11_21.json').write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n');print(dict(sessions=e['sessions'],start=e['start'],through=e['through']))
