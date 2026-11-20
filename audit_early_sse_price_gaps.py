"""Reconcile date coverage against the reconstructed early universe; no halt inference."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import json
from sse_history_archive import body,parse_prices
from verify_july_august_sse_basis import verify


def audit():
    basispath=Path('JULY_AUGUST_SSE_BASIS_EVIDENCE_2026_11_21.json');source=json.loads(basispath.read_text());verify(source)
    extra_path=Path('EARLY_SSE_EXIT_PRICE_EVIDENCE_2026_11_21.json');extra=json.loads(extra_path.read_text())
    if extra['basis_sha256']!=sha256(basispath.read_bytes()).hexdigest():raise ValueError('basis changed')
    root=Path('/Volumes/Leibniz/dev/st_research/v8_copilot/wt/market-recent-breadth-20261121/out/market-recent-breadth-20261121/sse-capture/full_prices')
    manifest=(root/'complete.json').read_bytes();refs={r['code']:(r,root)for r in json.loads(manifest)['source_refs']}
    for r in extra['sources']:
        if r['status']!='captured':raise ValueError('exit price unavailable')
        if r['code']in refs:raise ValueError('duplicate price source')
        refs[r['code']]=(r,Path(extra['source_store']))
    days=[r['date']for r in source['controls']];pool=source['pool'];populations={day:[code for code,r in pool.items()if r['listed']<=day and(r['ended']is None or r['ended']>day)]for day in days}
    basis=dict(pool=pool,populations=populations,window=dict(start=days[0],end=days[-1]));missing=[];zero=[];counts={day:0 for day in days};now=datetime.now(timezone.utc);selected_refs=[]
    for code in sorted(pool):
        ref,folder=refs[code];records=parse_prices(body(folder,ref,now),ref,basis,now);selected_refs.append(ref)
        for day in days:
            if code not in populations[day]:continue
            if day not in records:missing.append(dict(code=code,date=day))
            elif not records[day]['is_trading']:zero.append(dict(code=code,date=day))
            else:counts[day]+=1
    return dict(basis_sha256=sha256(basispath.read_bytes()).hexdigest(),price_manifest_sha256=sha256(manifest).hexdigest(),extra_sha256=sha256(extra_path.read_bytes()).hexdigest(),selected_price_sources=len(selected_refs),daily_trading_rows=counts,missing_active_days=missing,zero_volume_days=zero,limits=['Missing active days are unresolved until halt/exit controls are checked','Trading counts are source audit only, not published full-market breadth'])


if __name__=='__main__':
    e=audit();Path('EARLY_SSE_PRICE_GAP_AUDIT_2026_11_21.json').write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n');print(dict(sources=e['selected_price_sources'],missing_days=len(e['missing_active_days']),missing_symbols=sorted({r['code']for r in e['missing_active_days']}),zero_volume_days=len(e['zero_volume_days'])))
