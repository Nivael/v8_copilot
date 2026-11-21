import json
from pathlib import Path
from pypdf import PdfReader


def test_future_meetings_and_recusal_conflict_are_retained_from_originals():
    body = json.loads(Path('NOV20_MEETING_BODY_REVIEW_2026_11_21.json').read_text())
    docs = {s['announcement_id']: PdfReader(s['source_store']) for s in body['sources']}
    assert sum(len(d.pages) for d in docs.values()) == body['text_pages'] == 20
    assert sum(len(s['visual_physical_pages']) for s in body['sources']) == body['critical_visual_pages'] == 11
    text = lambda i, p: ''.join(docs[i].pages[p-1].extract_text().split())
    assert '全体董事对该议案予以回避表决' in text('1225679976', 1)
    assert '直接提交股东会审议' in text('1225679976', 1)
    assert '上述议案已经公司第六届董事会第三十八次会议审议通过' in text('1225679973', 2)
    assert '2026年12月07日14:00' in text('1225679973', 1)
    assert '2026年12月7日14点00分' in text('1225679624', 1)
    assert '股东会补选产生新任非独立董事之日起生效' in text('1225679385', 4)
    assert '2026年11月25日' in text('1225679385', 3)
    assert '2026年11月27日' in text('1225679216', 1)
    view = json.loads(Path('web/src/catalogNov20Fixed.json').read_text())
    f = next(f for f in view['findings'] if f['announcement_id'] == '1225679973')
    assert '表述不同' in f['boundary'] and '不是结果公告' in f['answer']
