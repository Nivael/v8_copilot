from decimal import Decimal
from pathlib import Path
import json
from pypdf import PdfReader


def test_cash_and_valuation_arithmetic_and_scope_stay_separate():
    body = json.loads(Path('NOV20_CASH_VALUATION_BODY_REVIEW_2026_11_21.json').read_text())
    calc = body['calculation_checks']
    for parts, total in [('weiHai_unmatured_parts_wan', 'weiHai_unmatured_total_wan'), ('weiHai_reported_return_parts_wan', 'weiHai_reported_return_total_wan'), ('chunxing_liquidation_parts_wan', 'chunxing_liquidation_total_wan')]:
        assert sum(map(Decimal, calc[parts])) == Decimal(calc[total])
    cost, income = map(Decimal, calc['chunxing_market_methods_wan'])
    assert income - cost == Decimal(calc['chunxing_method_difference_wan'])
    assert (body['text_pages'], body['critical_visual_pages']) == (43, 11)
    by_id = {s['announcement_id']: s for s in body['sources']}
    report = PdfReader(by_id['1225679971']['source_store'])
    assert len(report.pages) == 39
    cover = report.pages[0].extract_text()
    assert '苏州春兴精工股份有限公司' in cover and '资产评估说明' in cover
    assert '002547' not in cover  # Catalog plus named report identity, not an invented cover ticker.
    deposit = PdfReader(by_id['1225679017']['source_store'])
    text = ''.join(p.extract_text() for p in deposit.pages)
    assert '38,000' in text and '13,000' in text
    assert '是否到期' in text.replace('\n', '').replace(' ', '')
    view = json.loads(Path('web/src/catalogNov20Fixed.json').read_text())
    latest = [f for f in view['findings'] if f['review_phase'] == 'NOV20_CASH_VALUATION_BODY_REVIEW_2026_11_21.json']
    assert len(latest) == 2
    assert '净回款' in latest[0]['answer'] or '净回款' in latest[1]['answer']
