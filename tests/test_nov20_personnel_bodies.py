from pathlib import Path
import json
from pypdf import PdfReader
from build_nov20_catalog_reading import NAMED_ATTACHMENTS


def test_actual_appointments_pending_election_and_image_only_declarations():
    body = json.loads(Path('NOV20_PERSONNEL_BODY_REVIEW_2026_11_21.json').read_text())
    docs = {s['announcement_id']: PdfReader(s['source_store']) for s in body['sources']}
    assert sum(len(doc.pages) for doc in docs.values()) == 26
    assert sum(bool(p.extract_text().strip()) for doc in docs.values() for p in doc.pages) == 20
    text = lambda i: ''.join(''.join(p.extract_text().split()) for p in docs[i].pages)
    assert '任期自职工代表大会表决通过之日起' in text('1225679022')
    assert '空缺期间' in text('1225679959') and '由杨' in text('1225679959')
    assert '自本次董事会审议通过之日起' in text('1225679993')
    assert '尚需提交公司2026年第六次临时股东会审议' in text('1225679989')
    assert '承诺将参加上海证券交易所培训' in text('1225679986')
    assert '2026年11月30日' in text('1225679985')
    for identity in ('1225679995','1225679984'):
        s = next(s for s in body['sources'] if s['announcement_id'] == identity)
        assert text(identity) == '' and len(docs[identity].pages) == 3
        assert s['text_physical_pages'] == []
        assert s['scanned_physical_pages'] == s['visual_physical_pages'] == [1,2,3]
        assert NAMED_ATTACHMENTS[identity]['sha256'] == s['sha256']
        assert NAMED_ATTACHMENTS[identity]['scanned'] is True
