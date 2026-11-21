"""Attach previously verified issuer exit dates to quote gaps, never infer from absence."""
from pathlib import Path
from hashlib import sha256
import gzip,json
from canonical_json import digest

ASSET=Path('/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk/st_regime_comparison/inputs-93929179971e89fd4787986afd0d891bfde54971c7a31faa33aa3cc2b22c57f9.json.gz')

def reading():
    raw=ASSET.read_bytes()
    if sha256(raw).hexdigest()!='77ece10df1b70da14007a415b6564bc70c4628d413c8be116771b8c41b5ca292':raise ValueError('frozen asset changed')
    inputs=json.loads(gzip.decompress(raw));packet=inputs['endpoint_reasons']
    if packet['content_digest']!=digest({k:v for k,v in packet.items() if k!='content_digest'}):raise ValueError('prior context changed')
    known={s['announcement_id']:s for s in inputs['sample_integrity']['primary_sources']+inputs['halt_stages']['sources']+inputs['current_extension']['sources']}
    sources={s['announcement_id']:s for s in packet['sources']};rows=[]
    config=[('000016','1225615607','2026-10-23','主动终止上市后摘牌',['2026年10月23日','主动终止上市']),('002731','1225669888','2026-11-13','退市整理期结束后摘牌',['2026年11月12日','2026年11月13日','摘牌'])]
    for code,aid,date,label,clauses in config:
        source=sources[aid];original=known[aid]
        if source['symbol']!=code or any(source[k]!=original[k] for k in ('sha256','title','url')) or not source['protected_gate_passed']:raise ValueError('source identity changed')
        for page,text in source['selected_pages'].items():
            if sha256(text.encode()).hexdigest()!=source['page_hashes'][int(page)-1]:raise ValueError('source text changed')
        if any(t not in source['selected_pages']['1'] for t in clauses):raise ValueError('exit clause changed')
        rows.append(dict(code=code+'.SZ',date=date,classification=label,source=source))
    fixed_path=Path('FIXED_NOV20_LIMIT_AUDIT_2026_11_21.json');fixed=json.loads(fixed_path.read_text())
    missing={r['code'] for r in fixed['gaps'] if r['status']=='missing_quote20'}
    if missing!={r['code'] for r in rows}:raise ValueError('quote gap identity differs')
    result=dict(version='fixed_nov20_gap_context_v1',fixed_limit_audit_sha256=sha256(fixed_path.read_bytes()).hexdigest(),frozen_asset=str(ASSET),frozen_asset_sha256=sha256(raw).hexdigest(),rows=rows,limits=['Reuses prior issuer announcement evidence; no new download or independent case','Quote absence alone does not establish delisting; exit classification comes from named issuer announcements','Does not certify subsequent off-exchange trading, transfer registration or account cash proceeds','Keep original missing_quote20 data status and statistical denominator; attach legal context separately'])
    result['content_digest']=digest(result);return result

if __name__=='__main__':
    result=reading();Path('FIXED_NOV20_GAP_CONTEXT_2026_11_21.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print([(r['code'],r['date'],r['classification']) for r in result['rows']])
