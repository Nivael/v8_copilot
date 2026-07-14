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
RECRUITMENT_DEADLINE_MATERIALIZATION = Path(os.environ.get(
    "V8_RECRUITMENT_DEADLINE_MATERIALIZATION",
    DATA_ROOT / "local_data" / "v8_copilot" / "recruitment_deadlines.json",
)).expanduser().resolve()
RESEARCH_RUN_LEDGER_DB = Path(os.environ.get(
    "V8_RESEARCH_RUN_LEDGER_DB",
    DATA_ROOT / "local_data" / "v8_copilot" / "research_run_ledger.sqlite3",
)).expanduser().resolve()
EXPERIENCE_REPOSITORY_DB = Path(os.environ.get(
    "V8_EXPERIENCE_REPOSITORY_DB",
    DATA_ROOT / "local_data" / "v8_copilot" / "experience_repository.sqlite3",
)).expanduser().resolve()
FRESHNESS_MANIFEST_PATH = Path(os.environ.get(
    "V8_FRESHNESS_MANIFEST_PATH",
    DATA_ROOT / "local_data" / "v8_copilot" / "freshness_manifest.json",
)).expanduser().resolve()
