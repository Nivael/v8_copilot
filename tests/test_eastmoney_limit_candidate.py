import copy
import json
from pathlib import Path

import pytest

from verify_eastmoney_limit_candidate import verify


def test_dated_quote_replay_and_tamper_rejection(tmp_path):
    pack = json.loads(Path('EASTMONEY_LIMIT_CANDIDATE_2026_11_21.json').read_text())
    official = json.loads(Path('QIHUAN_OHLC_CROSSCHECK_EVIDENCE_2026_11_21.json').read_text())
    root = Path(pack['source_store'])
    result = verify(root, pack, official)
    assert result['touched_lower'] and not result['closed_lower'] and not result['one_price']
    changed = copy.deepcopy(official)
    changed['official_text'] += ' '
    with pytest.raises(ValueError, match='control bytes'):
        verify(root, pack, changed)
    for ref in pack['source_refs']:
        (tmp_path / ref['sha256']).write_bytes((root / ref['sha256']).read_bytes())
    (tmp_path / pack['source_refs'][2]['sha256']).write_bytes(b'{}')
    with pytest.raises(ValueError, match='source bytes'):
        verify(tmp_path, pack, official)
