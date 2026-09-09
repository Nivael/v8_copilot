import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("module", ["llm.boundaries", "freshness_manifest", "core_router", "llm.parser"])
def test_leaf_imports_need_neither_evaluation_code_nor_research_assets(tmp_path, module):
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}; import sys; "
         "assert 'answer_engine' not in sys.modules; "
         "assert not any(m == 'evals' or m.startswith('evals.') for m in sys.modules)"],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, V8_DATA_ROOT=str(tmp_path)),
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
