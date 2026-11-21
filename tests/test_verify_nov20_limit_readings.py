import json
import pytest
from verify_nov20_limit_readings import check


def test_readonly_gate_rejects_stale_generated_values_and_preserves_bytes(tmp_path):
    path=tmp_path/'reading.json';path.write_text(json.dumps({'paired':146}))
    before=path.read_bytes()
    assert check(str(path),{'paired':146})['verified']
    with pytest.raises(ValueError,match='saved result differs'):
        check(str(path),{'paired':145})
    assert path.read_bytes()==before
