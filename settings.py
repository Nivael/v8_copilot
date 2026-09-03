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
DATA_MAINTENANCE_DB = Path(os.environ.get(
    "V8_DATA_MAINTENANCE_DB",
    DATA_ROOT / "local_data" / "v8_copilot" / "data_maintenance.sqlite3",
)).expanduser().resolve()
ST_UNIVERSE_DIR = Path(os.environ.get(
    "V8_ST_UNIVERSE_DIR",
    DATA_ROOT / "local_data" / "v8_copilot" / "st_universe",
)).expanduser().resolve()
MARKET_CONTEXT_DB = Path(os.environ.get(
    "V8_MARKET_CONTEXT_DB",
    DATA_ROOT / "local_data" / "v8_copilot" / "market_context_v1.sqlite3",
)).expanduser().resolve()
MARKET_CONTEXT_MANIFEST_PATH = Path(os.environ.get(
    "V8_MARKET_CONTEXT_MANIFEST_PATH",
    DATA_ROOT / "local_data" / "v8_copilot" / "market_context_manifest_v1.json",
)).expanduser().resolve()
MARKET_FACTOR_DB = Path(os.environ.get(
    "V8_MARKET_FACTOR_DB",
    DATA_ROOT / "local_data" / "v8_copilot" / "market_factors_v1.sqlite3",
)).expanduser().resolve()
MARKET_FACTOR_MANIFEST_PATH = Path(os.environ.get(
    "V8_MARKET_FACTOR_MANIFEST_PATH",
    DATA_ROOT / "local_data" / "v8_copilot" / "market_factor_manifest_v1.json",
)).expanduser().resolve()
MARKET_FACTOR_MANIFEST_DIR = Path(os.environ.get(
    "V8_MARKET_FACTOR_MANIFEST_DIR",
    DATA_ROOT / "local_data" / "v8_copilot" / "market_factor_manifests",
)).expanduser().resolve()
MARKET_ACTIVITY_DB = Path(os.environ.get(
    "V8_MARKET_ACTIVITY_DB",
    DATA_ROOT / "local_data" / "v8_copilot" / "market_activity_v1.sqlite3",
)).expanduser().resolve()
MARKET_ACTIVITY_MANIFEST_PATH = Path(os.environ.get(
    "V8_MARKET_ACTIVITY_MANIFEST_PATH",
    DATA_ROOT / "local_data" / "v8_copilot" / "market_activity_manifest_v1.json",
)).expanduser().resolve()
MARKET_ACTIVITY_MANIFEST_DIR = Path(os.environ.get(
    "V8_MARKET_ACTIVITY_MANIFEST_DIR",
    DATA_ROOT / "local_data" / "v8_copilot" / "market_activity_manifests",
)).expanduser().resolve()
P7_INTELLIGENCE_DB = Path(os.environ.get(
    "V8_P7_INTELLIGENCE_DB",
    DATA_ROOT / "local_data" / "v8_copilot" / "p7_intelligence_v1.sqlite3",
)).expanduser().resolve()
VALUATION_FACTS_DB = Path(os.environ.get(
    "V8_VALUATION_FACTS_DB",
    DATA_ROOT / "local_data" / "v8_copilot" / "valuation_facts_v1.sqlite3",
)).expanduser().resolve()
VALUATION_EPISODE_DB = Path(os.environ.get(
    "V8_VALUATION_EPISODE_DB",
    DATA_ROOT / "local_data" / "v8_copilot" / "valuation_episode_v1.sqlite3",
)).expanduser().resolve()
P7_FORWARD_SHADOW_START = os.environ.get(
    "V8_P7_FORWARD_SHADOW_START", "2026-09-04"
)
P7_REVIEW_DIR = Path(os.environ.get(
    "V8_P7_REVIEW_DIR",
    DATA_ROOT / "local_data" / "v8_copilot" / "p7_review",
)).expanduser().resolve()
P7_DAILY_MANIFEST_PATH = Path(os.environ.get(
    "V8_P7_DAILY_MANIFEST_PATH",
    DATA_ROOT / "local_data" / "v8_copilot" / "p7_daily_manifest_v1.json",
)).expanduser().resolve()
P7_DAILY_MANIFEST_DIR = Path(os.environ.get(
    "V8_P7_DAILY_MANIFEST_DIR",
    DATA_ROOT / "local_data" / "v8_copilot" / "p7_daily_manifests",
)).expanduser().resolve()
EXPERIENCE_GOVERNANCE_DB = Path(os.environ.get(
    "V8_EXPERIENCE_GOVERNANCE_DB",
    DATA_ROOT / "local_data" / "v8_copilot" / "experience_governance.sqlite3",
)).expanduser().resolve()
ACCEPTED_EXPERIENCE_REGISTRY_PATH = Path(os.environ.get(
    "V8_ACCEPTED_EXPERIENCE_REGISTRY_PATH",
    PROJECT_ROOT / "experience_registry" / "accepted_experiences_v1.json",
)).expanduser().resolve()
