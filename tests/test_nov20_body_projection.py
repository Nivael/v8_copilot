from pathlib import Path
from hashlib import sha256
import json
from pypdf import PdfReader


def test_body_sources_and_reading_projection_match_saved_evidence():
    load = lambda p: json.loads(Path(p).read_text())
    digest = lambda p: sha256(Path(p).read_bytes()).hexdigest()
    body = load('NOV20_PRIORITY_BODY_REVIEW_2026_11_21.json')
    view = load('web/src/catalogNov20Fixed.json')
    review = load('NOV20_FIXED_CATALOG_REVIEW_2026_11_21.json')
    assert view['body_phases'][0]['sha256'] == digest('NOV20_PRIORITY_BODY_REVIEW_2026_11_21.json')
    assert view['catalog_review_sha256'] == body['catalog_review_sha256'] == digest('NOV20_FIXED_CATALOG_REVIEW_2026_11_21.json')
    assert view['catalog_evidence_sha256'] == digest('NOV20_FIXED_CATALOG_EVIDENCE_2026_11_21.json')
    assert view['titles'] == review['titles']
    assert view['counts'] == {k: review[k] for k in view['counts']}
    pages = images = 0
    for finding, shown in zip(body['findings'], view['findings'][:4], strict=True):
        source = next(s for s in body['sources'] if s['announcement_id'] == finding['announcement_id'])
        assert {k:v for k,v in shown.items() if k not in ('label','review_phase')} == dict(finding, source=source)
        p = Path(source['source_store'])
        assert digest(p) == source['sha256'] and p.stat().st_size == source['bytes']
        doc = PdfReader(p)
        pages += len(doc.pages)
        text = ''.join(page.extract_text() for page in doc.pages)
        assert source['codes'][0] in text
        assert all(1 <= page <= len(doc.pages) for page in finding['pages'])
        for page, signature in source['visual_image_sha256'].items():
            assert int(page) in source['visual_physical_pages']
            assert digest(p.parent / (signature + '.png')) == signature
            images += 1
    assert (pages, images) == (16, 10)
    assert body['remaining_catalog_attachments_unreviewed'] == len(view['titles']) - len(body['findings']) == 37


def test_all_phases_rebuild_the_current_projection():
    from build_nov20_catalog_reading import build
    view = json.loads(Path('web/src/catalogNov20Fixed.json').read_text())
    assert build() == view
    assert (view['reviewed_count'], view['remaining_count'], view['text_pages'], view['visual_pages']) == (13, 28, 52, 37)
    assert len({f['announcement_id'] for f in view['findings']}) == 13
