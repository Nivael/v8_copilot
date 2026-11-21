import json
from hashlib import sha256
from pathlib import Path
import pytest
pytest.importorskip('pypdfium2')
from verify_tianze_pdf_page import verify


def test_selected_pdf_page_reextracts_and_renders_exactly():
    result=verify()
    assert result['reviewed_page']==19 and result['total_pages']==176
    assert result['text_exact'] and result['image_exact']
    assert result['original_notice_debt_closed'] is False


def test_resealed_extracted_text_cannot_replace_actual_pdf_text(tmp_path):
    e=json.loads(Path('TIANZE_OFFICIAL_REPORT_CONFIRMATION_2026_11_21.json').read_text())
    e['selected_page_text']=e['selected_page_text'].replace('6 月 2 日','6 月 3 日')+'changed'
    e['selected_page_text_sha256']=sha256(e['selected_page_text'].encode()).hexdigest()
    path=tmp_path/'changed.json';path.write_text(json.dumps(e,ensure_ascii=False))
    with pytest.raises(ValueError,match='extracted page text differs'):verify(path)
