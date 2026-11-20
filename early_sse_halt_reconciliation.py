"""Match all early absent quotes to closed official full-day halt intervals."""
from pathlib import Path
from datetime import datetime,timezone
from hashlib import sha256
import json
from recent_breadth_projection import verified_suspensions,halt_coverage
from audit_early_sse_price_gaps import audit
from verify_july_august_sse_basis import verify


def reconcile():
    bp=Path('JULY_AUGUST_SSE_BASIS_EVIDENCE_2026_11_21.json');basis=json.loads(bp.read_text());verify(basis)
    gp=Path('EARLY_SSE_PRICE_GAP_AUDIT_2026_11_21.json');gap=json.loads(gp.read_text())
    if audit()!=gap:raise ValueError('gap audit differs')
    folder=Path('/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk/july_august_sse_basis/20261121/suspensions');s=verified_suspensions(folder,datetime.now(timezone.utc))
    populations={r['date']:[c for c,p in basis['pool'].items()if p['listed']<=r['date']and(p['ended']is None or p['ended']>r['date'])]for r in basis['controls']}
    pairs,proofs=halt_coverage(s['rows'],populations,{}, {})
    missing={(r['date'],r['code'])for r in gap['missing_active_days']}
    if pairs-missing:raise ValueError('halt interval contradicts returned positive trading row')
    return dict(basis_sha256=sha256(bp.read_bytes()).hexdigest(),gap_sha256=sha256(gp.read_bytes()).hexdigest(),suspension_content_digest=s['content_digest'],suspension_source_refs=s['source_refs'],source_query_start=s['start_query'],source_query_through=s['through_query'],query_rows=len(s['rows']),matched_days=len(pairs&missing),unresolved=[dict(date=d,code=c)for d,c in sorted(missing-pairs)],intervals=proofs,limits=['Exchange closed halt intervals explain missing trading days; not independent announcement-body/legal-exit review','Names from source observation, not a historical ST membership classification','SSE-only source preparation; no full-market breadth or independent strategy validation'])


if __name__=='__main__':
    e=reconcile();Path('EARLY_SSE_HALT_RECONCILIATION_EVIDENCE_2026_11_21.json').write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n');print(dict(matched=e['matched_days'],unresolved=e['unresolved'],intervals=len(e['intervals'])))
