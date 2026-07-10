"""Local runtime paths for the read-only v8 consumer."""
from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("V8_DATA_ROOT", PROJECT_ROOT.parent)).expanduser().resolve()
