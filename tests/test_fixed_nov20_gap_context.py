import json
from pathlib import Path
from fixed_nov20_gap_context import reading


def test_exit_context_is_bound_to_prior_sources_and_does_not_rewrite_quote_status():
    p=Path('FIXED_NOV20_LIMIT_AUDIT_2026_11_21.json');before=p.read_bytes()
    result=reading()
    assert result==json.loads(Path('FIXED_NOV20_GAP_CONTEXT_2026_11_21.json').read_text())
    assert [(r['code'],r['date']) for r in result['rows']]==[('000016.SZ','2026-10-23'),('002731.SZ','2026-11-13')]
    assert p.read_bytes()==before
    assert len([r for r in json.loads(before)['gaps'] if r['status']=='missing_quote20'])==2


def test_published_context_matches_replayed_sources():
    from build_fixed_gap_context_reading import reading as projected
    assert projected()==json.loads(Path('web/src/fixedGapContext.json').read_text())
