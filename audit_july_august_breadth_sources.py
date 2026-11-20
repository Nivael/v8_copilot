from pathlib import Path
from hashlib import sha256
from collections import Counter
import json
root=Path('/Volumes/Leibniz/dev/st_research/v8_copilot/wt/market-recent-breadth-20261121/out/market-recent-breadth-20261121/sse-capture/full_prices')
manifest=(root/'complete.json').read_bytes();e=json.loads(manifest);counts=Counter();rows=[]
for ref in e['source_refs']:
 raw=(root/(ref['sha256']+'.raw')).read_bytes()
 assert sha256(raw).hexdigest()==ref['sha256'] and len(raw)==ref['bytes']
 p=json.loads(raw);assert str(p['code'])==str(ref['code'])
 data=p['kline'];days=[str(r[0])for r in data];assert len(days)==len(set(days))
 selected=[r for r in data if '20260701'<=str(r[0])<='20260831']
 for r in selected:counts[str(r[0])]+=1
 rows.append({'symbol':str(p['code']),'rows_july_august':len(selected),'first':min(days)if days else None,'last':max(days)if days else None,'sha256':ref['sha256']})
report={'status':'price_archive_audit_not_breadth_publication','manifest_sha256':sha256(manifest).hexdigest(),'source_count':len(rows),'source_fields':'date,close,prevClose,chg_rate,volume,amount','daily_returned_rows':dict(sorted(counts.items())),'symbols_with_no_july_august_rows':[r['symbol']for r in rows if not r['rows_july_august']],'rows':rows,'limits':['Archive security pool was constructed for Sep18-Nov20, not certified as July-Aug universe','July-Aug historical listings/exits/daily totals and missing-row/suspension controls must be reconstructed','No corresponding July-Aug full SZSE day exports are bound to this audit','No full-market breadth, crisis score or independent strategy validation inferred']}
Path('JULY_AUGUST_BREADTH_SOURCE_AUDIT_2026_11_21.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print({'source_count':len(rows),'dates':len(counts),'first':min(counts),'last':max(counts),'min_rows':min(counts.values()),'max_rows':max(counts.values()),'no_period_rows':len(report['symbols_with_no_july_august_rows'])})
