"""Verify saved later issuer confirmation without replacing the original notice."""
from pathlib import Path
from hashlib import sha256
import json,gzip


def reading(path=Path('TIANZE_OFFICIAL_REPORT_CONFIRMATION_2026_11_21.json')):
    path=Path(path);e=json.loads(path.read_text());s=e['source'];store=Path(s['source_store']);raw=(store/(s['sha256']+'.pdf')).read_bytes()
    if sha256(raw).hexdigest()!=s['sha256'] or len(raw)!=s['bytes'] or not raw.startswith(b'%PDF-'):raise ValueError('official PDF bytes differ')
    if s['symbol']!='603721' or s['announcement_id']!='1225508648' or s['url']!='https://static.cninfo.com.cn/finalpage/2026-08-27/1225508648.PDF' or s['published_on']!='2026-08-27':raise ValueError('report identity differs')
    if e['confirmation']['effective_on']!='2026-06-02' or e['confirmation']['reported_on']!=s['published_on']:raise ValueError('confirmation dates differ from reviewed clause')
    if s.get('final_url')!=s['url'] or s.get('status')!=200:raise ValueError('official response identity differs')
    if e['original_mirror_id']!='SINA-12361633':raise ValueError('mirror event identity differs')
    text=e['selected_page_text'];image=(store/(e['selected_page_image_sha256']+'.png')).read_bytes()
    if sha256(text.encode()).hexdigest()!=e['selected_page_text_sha256'] or sha256(image).hexdigest()!=e['selected_page_image_sha256']:raise ValueError('saved page differs')
    compact=''.join(text.split())
    if e['selected_page']!=19 or e['total_pages']!=176 or e['visually_reviewed_pages']!=[19] or '2026年6月2日起正式复牌并撤销退市风险警示' not in compact:raise ValueError('reviewed clause differs')
    if e['original_announcement_official_bytes_recovered'] or e['official_mirror_gaps_remaining']!=8:raise ValueError('original notice debt must remain')
    queue=json.loads(Path('OFFICIAL_MIRROR_RECOVERY_QUEUE_2026_11_21.json').read_text());old=next(r for r in queue['rows'] if r['announcement_id']==e['original_mirror_id'])
    if old['symbol']!='603721':raise ValueError('mirror event identity differs')
    from fixed_nov20_gap_context import ASSET
    frozen=ASSET.read_bytes()
    if sha256(frozen).hexdigest()!=queue['frozen_asset_sha256']:raise ValueError('frozen input differs')
    matches=[]
    def visit(value):
        if isinstance(value,dict):
            if value.get('announcement_id')==old['announcement_id'] and value.get('sha256')==old['sha256']:matches.append(value)
            for item in value.values():visit(item)
        elif isinstance(value,list):
            for item in value:visit(item)
    visit(json.loads(gzip.decompress(frozen)))
    if not any('2026年6月2日' in ''.join(json.dumps(m,ensure_ascii=False).split()) for m in matches):raise ValueError('original effective date not backed')

    return dict(evidence_sha256=sha256(path.read_bytes()).hexdigest(),original_mirror_id=old['announcement_id'],original_mirror_sha256=old['sha256'],source_url=s['url'],source_sha256=s['sha256'],published_on=s['published_on'],effective_on=e['confirmation']['effective_on'],page=e['selected_page'],total_pages=e['total_pages'],original_official_bytes_recovered=False)

if __name__=='__main__':
    Path('web/src/tianzeReportConfirmation.json').write_text(json.dumps(reading(),ensure_ascii=False,indent=2)+'\n')
