import pytest
from tencent_nov20_market_audit import parse_quotes, checked_digest, build
from canonical_json import digest


def test_parser_rejects_executable_and_duplicate_content():
    assert parse_quotes(b'v_sh600000="a~b";\n') == {'sh600000':['a','b']}
    for raw in (b'alert(1);v_sh600000="a";',b'v_sh600000="a";x()',b'v_sh600000="a";v_sh600000="b";'):
        with pytest.raises(ValueError): parse_quotes(raw)


def test_digest_rejects_changed_payload():
    value={'value':1};value['content_digest']=digest(value);checked_digest(value)
    value['value']=2
    with pytest.raises(ValueError): checked_digest(value)


def test_all_saved_quotes_replay_against_official_universe():
    result=build()
    assert result['official_trading']==result['paired']==5216
    assert result['unresolved']==[]
    assert result['limit_counts_in_paired']==dict(open_at_down=20,touch_down=107,close_at_down=68,one_price_down=3)
    assert len({r['code'] for r in result['observations']})==5216


def test_reading_matches_replayed_audit():
    import json
    from pathlib import Path
    from build_tencent_market_limit_reading import reading
    assert reading()==json.loads(Path('web/src/tencentMarketDailyLimits.json').read_text())
