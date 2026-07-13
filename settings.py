"""Local runtime paths for the read-only v8 consumer."""
from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("V8_DATA_ROOT", PROJECT_ROOT.parent)).expanduser().resolve()
ANNOUNCEMENT_REFRESH_DIR = Path(os.environ.get(
    "V8_ANNOUNCEMENT_REFRESH_DIR",
    DATA_ROOT / "local_data" / "v8_copilot" / "announcement_refresh",
)).expanduser().resolve()
ANNOUNCEMENT_BODY_CACHE_DIR = Path(os.environ.get(
    "V8_ANNOUNCEMENT_BODY_CACHE_DIR",
    DATA_ROOT / "local_data" / "v8_copilot" / "announcement_bodies",
)).expanduser().resolve()
