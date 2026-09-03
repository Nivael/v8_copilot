"""Versioned P7 daily run manifest with monotonic current pointer."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from data_refresh import atomic_write_json
from p7_anomalies import AnomalyRun
from p7_announcements import AnnouncementRun
from p7_daily import LinkageRun


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def build_p7_manifest(
    *, anomaly_run: AnomalyRun, announcement_run: AnnouncementRun,
    linkage_run: LinkageRun,
) -> dict[str, Any]:
    shadow_mode = str(linkage_run.shadow_summary.get("mode") or "historical_replay")
    payload = {
        "contract_version": "p7_daily_manifest_v1",
        "checked_through": linkage_run.through,
        "shadow_mode": shadow_mode,
        "runs": {
            "announcement": announcement_run.run_id,
            "activity_anomaly": anomaly_run.run_id,
            "linkage_shadow": linkage_run.run_id,
        },
        "release_status": {
            "p7a_announcements": "shadow_ready_for_review",
            "p7b_activity": "shadow",
            "p7c_linkage": "shadow",
        },
        "counts": {
            "announcements": announcement_run.announcement_count,
            "bundles": announcement_run.bundle_count,
            "priority_bundles": announcement_run.priority_bundle_count,
            "hard_transitions": announcement_run.hard_transition_count,
            "activity_facts": anomaly_run.fact_count,
            "balanced_hits": anomaly_run.balanced_hit_count,
            "balanced_5d_episodes": anomaly_run.episode_counts.get("balanced_5", 0),
            "research_queue_items": len(linkage_run.queue_items),
            "shadow_outcomes": len(linkage_run.shadow_outcomes),
        },
        "risk_notice": "异常量价只表示相对历史的交易活跃变化，不证明资金主体、方向、内幕信息或未来收益。",
        "blocking_gaps": [
            "P7B/P7C 未达到至少 60 个真实前瞻交易日发布门",
            "daily_basic 未返回显式 limit_status；当前以 raw OHLC + stk_limit 双源 fail-closed，仅用于 shadow",
        ],
    }
    digest = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
    return {**payload, "content_digest": digest, "manifest_id": f"P7M-{digest[:20].upper()}"}


def write_p7_manifest_set(
    payload: dict[str, Any], *, current_path: Path, manifest_directory: Path,
) -> Path:
    through = str(payload.get("checked_through") or "")
    if len(through) != 10:
        raise ValueError("P7 manifest 缺合法 checked_through")
    manifest_directory.mkdir(parents=True, exist_ok=True)
    mode = str(payload.get("shadow_mode") or "historical_replay")
    if mode not in {"historical_replay", "prospective"}:
        raise ValueError(f"P7 manifest shadow_mode 非法: {mode}")
    manifest_id = str(payload.get("manifest_id") or "")
    if not manifest_id.startswith("P7M-"):
        raise ValueError("P7 manifest 缺合法 manifest_id")
    dated = manifest_directory / f"{through}_{mode}_{manifest_id}.json"
    if not dated.exists():
        atomic_write_json(dated, payload)
    if current_path.exists():
        current = json.loads(current_path.read_text(encoding="utf-8"))
        current_date = str(current.get("checked_through") or "")
        if current_date > through:
            return dated
        if current_date == through and current.get("manifest_id") != payload.get("manifest_id"):
            current_mode = str(current.get("shadow_mode") or "historical_replay")
            # 同一截止日允许历史回放和前瞻账并存，但 current 永远优先指向前瞻账。
            if current_mode == "prospective" and mode == "historical_replay":
                return dated
    atomic_write_json(current_path, payload)
    return dated
