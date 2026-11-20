"""Rebuild the Nov20 reading projection from retained review phases."""
from pathlib import Path
from hashlib import sha256
import json
from pypdf import PdfReader
from verify_nov20_fixed_catalog import verify

PHASES = ['NOV20_PRIORITY_BODY_REVIEW_2026_11_21.json', 'NOV20_CHUNXING_BODY_REVIEW_2026_11_21.json', 'NOV20_JUDICIAL_BODY_REVIEW_2026_11_21.json']
LABELS = {'1225679977':'汇洲：获批与生效', '1225679819':'美丽：执行与回款', '1225679944':'惠程：零元收购', '1225679946':'惠程：关联合作', '1225679975':'春兴：无条件利息豁免', '1225679974':'春兴：先付款才可豁免', '1225679970':'春兴：拟售资产', '1225679913':'宝馨：本笔流拍与后续预告', '1225679789':'瑞茂：旧案进展与拟执行', '1225679623':'喜临门：拍卖公示与股东预重整'}


def build():
    load = lambda f: json.loads(Path(f).read_text())
    digest = lambda f: sha256(Path(f).read_bytes()).hexdigest()
    review = load('NOV20_FIXED_CATALOG_REVIEW_2026_11_21.json')
    if verify(load('NOV20_FIXED_CATALOG_EVIDENCE_2026_11_21.json')) != review:
        raise ValueError('catalog replay differs')
    titles = {t['announcement_id']:t for t in review['titles']}
    full = load('web/src/catalogFullCoverage.json')
    findings, phases = [], []
    total_pages = total_images = 0
    seen = set()
    for name in PHASES:
        body = load(name)
        if body['catalog_review_sha256'] != digest('NOV20_FIXED_CATALOG_REVIEW_2026_11_21.json'):
            raise ValueError('body catalog binding differs')
        sources = {s['announcement_id']:s for s in body['sources']}
        if len(sources) != len(body['sources']):
            raise ValueError('duplicate body source')
        for finding in body['findings']:
            identity = finding['announcement_id']
            if identity in seen or identity not in titles:
                raise ValueError('duplicate or foreign finding')
            seen.add(identity)
            source = sources[identity]
            code = finding.get('code', body.get('code'))
            if source['adjunct_url'] != titles[identity]['adjunct_url'] or source['codes'] != titles[identity]['codes'] or code not in source['codes']:
                raise ValueError('body security or attachment differs')
            p = Path(source['source_store'])
            if digest(p) != source['sha256'] or p.stat().st_size != source['bytes']:
                raise ValueError('body bytes differ')
            doc = PdfReader(p)
            if code not in doc.pages[0].extract_text() or any(page<1 or page>len(doc.pages) for page in finding['pages']):
                raise ValueError('body code or page differs')
            total_pages += len(doc.pages)
            for page, signature in source['visual_image_sha256'].items():
                if int(page) not in source['visual_physical_pages'] or digest(p.parent/(signature+'.png')) != signature:
                    raise ValueError('visual source differs')
                total_images += 1
            findings.append(dict(finding, code=code, label=LABELS[identity], source=source))
        phases.append(dict(file=name, sha256=digest(name), catalog_review_sha256=body['catalog_review_sha256']))
    return dict(baseline_snapshot_digest=full['baseline_snapshot_digest'], full_catalog_evidence_sha256=full['evidence_sha256'], catalog_evidence_sha256=digest('NOV20_FIXED_CATALOG_EVIDENCE_2026_11_21.json'), catalog_review_sha256=digest('NOV20_FIXED_CATALOG_REVIEW_2026_11_21.json'), body_phases=phases, counts={k:review[k] for k in ['requested_companies','captured_companies','title_sightings','unique_attachment_identities','nonempty_companies']}, reviewed_count=len(seen), remaining_count=len(titles)-len(seen), text_pages=total_pages, visual_pages=total_images, findings=findings, titles=review['titles'])


if __name__ == '__main__':
    Path('web/src/catalogNov20Fixed.json').write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n')
