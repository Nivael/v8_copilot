"""Load only provider credentials/configuration, preserving the process environment."""
from __future__ import annotations

import os
from pathlib import Path


def load_provider_env(path: Path | None) -> None:
    if path is None:
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in {"TUSHARE_TOKEN", "TUSHARE_HTTP_URL"}:
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))
