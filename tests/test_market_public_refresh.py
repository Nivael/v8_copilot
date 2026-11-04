from copy import deepcopy
from datetime import date, datetime, timezone
import json

import pytest

from canonical_json import digest
from market_calendar import sessions_2026
from market_public_refresh import parse_index_perf, refresh_public_indices
from market_risk import INDEX_BASKET, build_market_risk_status

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)
CALENDAR = sessions_2026(date(2026, 8, 4), date(2026, 11, 4))


def payload(code="000985.CSI"):
    return {"code": "200", "data": [{"indexCode": code[:6], "tradeDate": day.replace("-", ""),
                                      "close": 100 + index, "tradingValue": 20} for index, day in enumerate(CALENDAR)]}


def test_official_amount_units_and_exact_session_window():
    rows = parse_index_perf(payload(), "000985.CSI", CALENDAR)
    assert len(rows) == 61
    assert rows[0] == {"ts_code": "000985.CSI", "trade_date": "2026-08-04", "close": 100, "amount": 2_000_000_000}
    assert rows[-1]["trade_date"] == "2026-11-04"


@pytest.mark.parametrize("alter", ["wrong_code", "weekend", "duplicate", "not_number", "negative_amount", "error"])
def test_inconsistent_official_rows_are_rejected(alter):
    value = payload()
    if alter == "wrong_code": value["data"][0]["indexCode"] = "000300"
    elif alter == "weekend": value["data"][0]["tradeDate"] = "20260801"
    elif alter == "duplicate": value["data"].append(deepcopy(value["data"][0]))
    elif alter == "not_number": value["data"][0]["close"] = "nan"
    elif alter == "negative_amount": value["data"][0]["tradingValue"] = -1
    else: value["code"] = "500"
    with pytest.raises(ValueError): parse_index_perf(value, "000985.CSI", CALENDAR)


class Client:
    def __init__(self, missing=None, failed=False): self.missing, self.failed = missing, failed
    def get_index(self, code, calendar):
        if self.failed: raise TimeoutError("arbitrary provider body")
        value = payload(code)
        if self.missing: value["data"] = [row for row in value["data"] if row["tradeDate"] != self.missing.replace("-", "")]
        return parse_index_perf(value, code, calendar), {"code": code}


def read(tmp_path):
    return build_market_risk_status(snapshot_dir=tmp_path, database=tmp_path / "missing.db",
                                    manifest_path=tmp_path / "missing.json", now=NOW)


def test_index_only_snapshot_does_not_invent_ST_breadth_ETF_or_risk_score(tmp_path):
    folder = tmp_path / "public_indices"
    report = refresh_public_indices(Client(), through="2026-11-04", output=folder, now=NOW)
    before = (folder / "current.json").read_bytes()
    result = read(tmp_path)
    assert report["status"] == "complete" and report["observations"] == 183
    assert result["public_index_snapshot"]["availability"] == "observed"
    assert result["market_coverage"] == {"indices_observed_at_target": 3, "declared_indices": 3,
                                         "breadth_at_target": False, "st_style_at_target": False,
                                         "historical_breadth_venues_at_target": 0}
    assert result["indices"][0]["return_60d_pct"] == 60
    assert result["indices"][0]["amount_5d_to_20d_ratio"] == 1
    assert result["status"] == "observed_snapshot"
    assert result["requested_through"] == "2026-11-04"
    assert result["current_risk_assessment"] == "not_calibrated"
    assert result["etfs"] == []
    assert before == (folder / "current.json").read_bytes()


def test_missing_day_does_not_shorten_sixty_day_window_and_failure_preserves_snapshot(tmp_path):
    folder = tmp_path / "public_indices"
    report = refresh_public_indices(Client(missing="2026-08-10"), through="2026-11-04", output=folder, now=NOW)
    assert report["status"] == "partial" and report["gap_count"] == 3
    result = read(tmp_path)
    assert result["indices"][0]["return_60d_pct"] is None
    assert result["indices"][0]["return_20d_pct"] is not None
    before = (folder / "current.json").read_bytes()
    report = refresh_public_indices(Client(failed=True), through="2026-11-04", output=folder, now=NOW)
    assert report["status"] == "failed" and report["current_snapshot_preserved"] is True
    assert before == (folder / "current.json").read_bytes()
    assert "arbitrary" not in (folder / "last_attempt.json").read_text()


@pytest.mark.parametrize("alter", ["amount_unit", "future", "scope", "wrong_code", "calendar"])
def test_reader_rechecks_source_metadata_and_rows(alter, tmp_path):
    folder = tmp_path / "public_indices"
    refresh_public_indices(Client(), through="2026-11-04", output=folder, now=NOW)
    path = folder / "current.json"
    raw = json.loads(path.read_text())
    if alter == "amount_unit": raw["amount_unit"] = "CNY100M"
    elif alter == "future": raw["fetched_at"] = "2026-12-01T00:00:00+00:00"
    elif alter == "scope": raw["scope"] = "entire_market"
    elif alter == "wrong_code": raw["indices"]["000985.CSI"][0]["ts_code"] = "000300.SH"
    else: raw["calendar"].pop(2)
    raw.pop("content_digest")
    raw["content_digest"] = digest(raw)
    path.write_text(json.dumps(raw))
    assert read(tmp_path)["public_index_snapshot"]["availability"] == "invalid"
    assert read(tmp_path)["indices"] == []
