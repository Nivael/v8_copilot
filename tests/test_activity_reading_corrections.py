from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
import sqlite3
import unicodedata

import pytest

import activity_reading_corrections as arc
from canonical_json import digest, canonical_json
from data_refresh import atomic_write_json
from historical_code_gap_review import MAPPING_URL, SWITCH_URL
from market_activity import MarketActivityFact, MarketActivityRepository
from p8_grid_price_coverage import sha

DAY = "2025-09-15"
TEXT = "839680 深圳市广道数字技术股份有限公司 2025年9月12日 公司股票自2025年9月15日起停牌"
TABLE = b"<table><tr><td>174</td><td>Test</td><td>2021/11/15</td><td>839680</td><td>920680</td></tr></table>"
NOTICE = "关于北交所存量上市公司代码切换上线的通知 2025-09-12 自2025年10月9日起 新旧代码对应关系".encode()


def fact(symbol="839680", close=None, volume=None):
    return MarketActivityFact(symbol=symbol, ts_code=symbol + (".BJ" if symbol == "839680" else ".SZ"),
        name="Test", trade_date=DAY, risk_type="ST", close=close, volume=volume,
        suspension_status="trading", terminal_phase_status="not_terminal", one_price_limit=False,
        eligible_for_anomaly=close is not None, exclusion_reasons=["daily_missing"] if close is None else [])


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    # Parser is isolated here; the materialization/live smoke test uses real PDF
    # extraction against the retained official bytes and all original snapshots.
    monkeypatch.setattr(arc, "_notice_text", lambda raw: TEXT)
    db = tmp_path / "activity.sqlite3"; repo = MarketActivityRepository(db)
    original = fact(); other = fact("000001", 10, 1000)
    meta = repo.store_snapshot(trade_date=DAY, facts=[other, original], daily_row_count=1,
        daily_basic_row_count=1, suspend_row_count=0, limit_row_count=1,
        fetched_at="2026-09-06T10:00:00+00:00").model_dump(mode="json")
    root = tmp_path / "corrections"; (root / "assets").mkdir(parents=True)
    sources = {}
    for key, raw, url, suffix in [("mapping", TABLE, MAPPING_URL, ".html"),
            ("switch", NOTICE, SWITCH_URL, ".html"), ("notice", b"%PDF-1.4 fixture", arc.NOTICE_URL, ".pdf")]:
        code = sha256(raw).hexdigest(); asset = "assets/" + code + suffix; (root / asset).write_bytes(raw)
        sources[key] = dict(url=url, response_url=url, sha256=code, bytes=len(raw),
                            fetched_at="2026-11-01T00:00:00+00:00", asset=asset)
    sources["notice"].update(published_on="2025-09-12", normalized_text_sha256=sha256(re.sub(r"\s+", "", unicodedata.normalize("NFKC", TEXT)).encode()).hexdigest())
    rows = [dict(ts_code="920680.BJ", trade_date="20250915", suspend_type="S", suspend_timing=None)]
    day = dict(trade_date=DAY, rows=rows, rows_digest=sha(rows), source="tushare:suspend_d", fetched_at="2026-09-06T12:00:00+00:00")
    entry = dict(symbol="839680", trade_date=DAY, snapshot_id=meta["snapshot_id"], snapshot_digest=meta["content_digest"],
                 snapshot_metadata_digest=digest(meta), old_fact_digest=digest(original.model_dump(mode="json")), provider_day_digest=digest(day))
    entry["entry_id"] = "ASC-" + digest(entry)[:24].upper()
    body = dict(version=arc.REGISTRY_VERSION, created_at=datetime.now(timezone.utc).isoformat(),
                basis_study="RUN-" + "1" * 24, sources=sources, provider_days=[day], entries=[entry])
    path = root / "current.json"
    def save(value):
        value = deepcopy(value); value["content_digest"] = digest({k: v for k, v in value.items() if k != "content_digest"}); atomic_write_json(path, value); return value
    packet = save(body)
    return dict(database=db, repo=repo, original=original, other=other, meta=meta, root=root,
                path=path, packet=packet, save=save)


def read(p, **changes):
    return arc.read_activity(**{**dict(database=p["database"], symbol="839680", start=DAY, through=DAY,
                                   corrections=p["path"]), **changes})


def test_effective_fact_is_separate_and_original_snapshot_and_prices_stay_exact(prepared):
    p = prepared; before = p["database"].read_bytes(); result = read(p)
    row = result["rows"][0]
    assert row["stored_fact"] == p["original"].model_dump(mode="json")
    assert row["effective_fact"]["suspension_status"] == "suspended"
    assert row["effective_fact"]["suspend_type"] == "S" and not row["effective_fact"]["eligible_for_anomaly"]
    changed = {k for k, v in row["stored_fact"].items() if row["effective_fact"][k] != v}
    assert changed == {"suspension_status", "suspend_type", "exclusion_reasons"}
    assert result["reading_modes"] == {"official_suspension_correction": 1}
    assert row["effective_fact_digest"] != row["stored_fact_digest"]
    assert result["content_digest"] != p["meta"]["content_digest"] and p["database"].read_bytes() == before
    assert read(p) == result and p["repo"].latest_facts()[-1] == p["original"]
    assert all(v is False for v in result["boundaries"].values())


def test_non_target_stock_remains_stored_state(prepared):
    result = read(prepared, symbol="000001")
    row = result["rows"][0]
    assert row["reading_mode"] == "stored_state" and row["effective_fact"] == row["stored_fact"]
    assert row["correction_id"] is None


def test_no_registry_downgrades_missing_trade_data_without_inventing_suspension(prepared):
    p = prepared
    result = arc.read_activity(database=p["database"], symbol="839680", start=DAY, through=DAY)
    row = result["rows"][0]
    assert row["reading_mode"] == "missing_trade_data_state_unknown"
    assert row["stored_fact"]["suspension_status"] == "trading" and row["effective_fact"]["suspension_status"] == "unknown"
    assert row["effective_fact"]["suspend_type"] == "" and row["effective_fact"]["close"] is None


@pytest.mark.parametrize("field,value", [("close", 11), ("suspension_status", "unknown")])
def test_raw_fact_mutation_invalidates_source_before_correction(prepared, field, value):
    p = prepared
    with sqlite3.connect(p["database"]) as db:
        row = p["original"].model_dump(mode="json"); row[field] = value
        db.execute("update market_activity_daily set payload_json=? where symbol='839680'", (canonical_json(row),))
    with pytest.raises(ValueError, match="snapshot changed"): read(p)


def test_changed_snapshot_metadata_is_not_hidden_by_unchanged_content_hash(prepared):
    with sqlite3.connect(prepared["database"]) as db:
        db.execute("update activity_snapshots set fetched_at='2026-09-07T00:00:00+00:00'")
    with pytest.raises(ValueError, match="no longer matches"): read(prepared)


def test_new_latest_revision_does_not_rebind_correction_even_if_target_fact_same(prepared):
    p = prepared
    p["repo"].store_snapshot(trade_date=DAY, facts=[fact("000001", 11, 1000), p["original"]],
        daily_row_count=1, daily_basic_row_count=1, suspend_row_count=0, limit_row_count=1,
        fetched_at="2026-09-07T00:00:00+00:00")
    with pytest.raises(ValueError, match="no longer matches"): read(p)


@pytest.mark.parametrize("kind,timing", [("R", None), ("S", "09:30-10:00")])
def test_resume_or_intraday_evidence_cannot_authorize_full_day_suspension(prepared, kind, timing):
    p = prepared; value = deepcopy(p["packet"]); raw = value["provider_days"][0]
    raw["rows"][0].update(suspend_type=kind, suspend_timing=timing); raw["rows_digest"] = sha(raw["rows"])
    p["save"](value)
    with pytest.raises(ValueError, match="full-day suspension"): read(p)


@pytest.mark.parametrize("change", ["duplicate", "wrong_subject", "wrong_fact", "wrong_day_binding", "before_sources"])
def test_registry_entry_and_source_clocks_fail_closed(prepared, change):
    p = prepared; value = deepcopy(p["packet"]); entry = value["entries"][0]
    if change == "duplicate": value["entries"].append(deepcopy(entry))
    if change == "wrong_subject": entry["symbol"] = "000001"
    if change == "wrong_fact": entry["old_fact_digest"] = "0" * 64
    if change == "wrong_day_binding": entry["provider_day_digest"] = "0" * 64
    if change == "before_sources": value["created_at"] = "2026-10-01T00:00:00+00:00"
    p["save"](value)
    with pytest.raises(ValueError): read(p)


def test_changed_registry_digest_or_missing_explicit_file_has_no_raw_fallback(prepared):
    p = prepared; value = deepcopy(p["packet"]); value["basis_study"] = "RUN-" + "2" * 24
    atomic_write_json(p["path"], value)
    with pytest.raises(ValueError, match="registry changed"): read(p)
    with pytest.raises(FileNotFoundError): read(p, corrections=p["root"] / "missing.json")


@pytest.mark.parametrize("source", ["mapping", "switch", "notice"])
def test_changed_official_bytes_cannot_keep_a_valid_correction(prepared, source):
    p = prepared; (p["root"] / p["packet"]["sources"][source]["asset"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="asset bytes changed"): read(p)


def test_changed_notice_text_fails_even_when_asset_ref_is_intact(prepared, monkeypatch):
    monkeypatch.setattr(arc, "_notice_text", lambda raw: TEXT.replace("9月15日", "9月16日"))
    with pytest.raises(ValueError, match="notice content changed"): read(prepared)


@pytest.mark.parametrize("symbol,start,through", [("839680.BJ", DAY, DAY), ("83968", DAY, DAY),
    ("839680", "2025-09-16", DAY), ("839680", "2024-01-01", DAY)])
def test_exact_scope_and_bounded_window_required(prepared, symbol, start, through):
    with pytest.raises(ValueError): read(prepared, symbol=symbol, start=start, through=through)


def test_empty_other_stock_window_is_unavailable_not_trading(prepared):
    result = read(prepared, symbol="000002")
    assert result["availability"] == "unavailable" and result["rows"] == []


def test_existing_pack_flow_registers_original_effective_data_and_keeps_lens_gap(prepared):
    from api_contract import ResearchRequest
    from evidence_gateway import build_evidence_pack
    pack = build_evidence_pack(ResearchRequest(question="历史活动状态的数据更正如何核实？", llm_mode="off"))
    reading = read(prepared); augmented = arc.augment_activity_reading(pack, reading)
    assert augmented.pack_digest != pack.pack_digest and augmented.rows[:-1] == pack.rows
    row = augmented.rows[-1]
    assert row["activity_reading"] == reading and row["not_mechanism_lens"]
    assert json.loads(augmented.validation_catalog["query_row:" + row["row_id"]])["activity_reading"] == reading
    assert augmented.lens_invocations == pack.lens_invocations
    assert arc.augment_activity_reading(augmented, reading) == augmented
    bad = deepcopy(reading); bad["rows"][0]["effective_fact"]["close"] = 0
    with pytest.raises(ValueError): arc.augment_activity_reading(pack, bad)


def test_explicit_reading_does_not_bypass_action_or_subject_boundaries(prepared):
    from api_contract import ResearchObject, ResearchRequest
    from evidence_gateway import build_evidence_pack
    reading = read(prepared)
    refused = build_evidence_pack(ResearchRequest(question="可以买沐邦吗？", llm_mode="off"))
    assert refused.question_scope["route"] == "refuse_or_rewrite"
    assert arc.augment_activity_reading(refused, reading) == refused
    other = build_evidence_pack(ResearchRequest(question="核对历史活动状态", object=ResearchObject(kind="stock", ref="603398"), llm_mode="off"))
    with pytest.raises(ValueError, match="research subject"): arc.augment_activity_reading(other, reading)


def test_cli_requires_all_activity_scope_arguments(monkeypatch):
    import research_workbench
    monkeypatch.setattr("sys.argv", ["research_workbench.py", "evidence", "--question", "历史活动状态", "--activity-symbol", "839680"])
    with pytest.raises(SystemExit) as error: research_workbench.main()
    assert error.value.code == 2
