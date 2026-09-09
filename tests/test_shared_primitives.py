import importlib
import sqlite3
from contextlib import closing
from datetime import date

import pytest

from canonical_json import canonical_json, digest
from provider_env import load_provider_env
from sqlite_access import connect_ro


def test_canonical_identity_preserves_unicode_order_and_fallback():
    value = {"z": [None, -0.0, True], "日期": date(2026, 9, 10), "a": "重整"}
    expected = '{"a":"重整","z":[null,-0.0,true],"日期":"2026-09-10"}'
    assert canonical_json(value) == expected
    assert digest(value) == digest(dict(reversed(list(value.items()))))
    assert canonical_json(float("nan")) == "NaN"
    # Existing strict serializers must continue rejecting non-JSON inputs.
    from p6b_market_cap_backfill import _canonical as strict_canonical
    with pytest.raises(TypeError):
        strict_canonical(value)


def test_read_only_connection_handles_uri_characters_and_cannot_create_or_write(tmp_path):
    path = tmp_path / "行情 ?#%.sqlite3"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("create table facts(value text)")
        connection.execute("insert into facts values ('原始证据')")
        connection.commit()
    with closing(connect_ro(path)) as connection:
        assert connection.execute("select value from facts").fetchone()["value"] == "原始证据"
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("delete from facts")
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(FileNotFoundError):
        connect_ro(missing)
    assert not missing.exists()


@pytest.mark.parametrize("module,name", [
    ("p7_provider_probe", "_load_env_file"),
    ("p8_provider_probe", "_load_env_file"),
    ("p8_chip_proxies", "_load_env_file"),
    ("p8_backfill_market_activity", "_load_env"),
    ("p8_holder_history", "_load_env"),
    ("p8_qfq_backfill", "_load_env"),
    ("p8_terminal_history", "_load_env"),
])
def test_provider_env_entrypoints_preserve_environment_and_allow_only_provider_keys(tmp_path, monkeypatch, module, name):
    monkeypatch.setenv("TUSHARE_TOKEN", "already-set")
    monkeypatch.delenv("TUSHARE_HTTP_URL", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.setenv("PATH", "existing-path")
    path = tmp_path / "provider.env"
    path.write_text("# comment\nTUSHARE_TOKEN='file-token'\nTUSHARE_HTTP_URL=\"https://example.invalid?a=b\"\n"
                    "HTTPS_PROXY=https://proxy.invalid\nPATH=replaced\nnot-an-assignment\n")
    loader = getattr(importlib.import_module(module), name)
    assert loader is load_provider_env
    loader(path)
    import os
    assert os.environ["TUSHARE_TOKEN"] == "already-set"
    assert os.environ["TUSHARE_HTTP_URL"] == "https://example.invalid?a=b"
    assert os.environ["PATH"] == "existing-path"
    assert "HTTPS_PROXY" not in os.environ


def test_provider_env_missing_file_is_not_silently_accepted(tmp_path):
    load_provider_env(None)
    with pytest.raises(FileNotFoundError):
        load_provider_env(tmp_path / "missing.env")
