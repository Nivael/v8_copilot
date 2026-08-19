from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import portable.portable_workspace as portable
from portable.with_secrets import secret_environment


def _database(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("create table sample(value text not null)")
        connection.execute("insert into sample values (?)", (value,))


def test_sqlite_backup_is_valid_and_archives_sidecars(tmp_path) -> None:
    source = tmp_path / "source.sqlite3"
    destination = tmp_path / "destination.sqlite3"
    archive = tmp_path / "archive"
    _database(source, "new")
    _database(destination, "old")
    Path(f"{destination}-wal").write_text("stale")

    portable._backup_sqlite(source, destination, archive)

    assert portable._quick_check(destination) == "ok"
    with sqlite3.connect(destination) as connection:
        assert connection.execute("select value from sample").fetchone()[0] == "new"
    assert (archive / f"{destination.name}-wal").read_text() == "stale"


def test_sync_dry_run_does_not_mutate_destination(monkeypatch, tmp_path, capsys) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source_db = source / "local_data" / "v8_copilot" / "runs.sqlite3"
    destination_db = destination / "local_data" / "v8_copilot" / "runs.sqlite3"
    _database(source_db, "new")
    _database(destination_db, "old")
    os.utime(destination_db, (1, 1))
    os.utime(source_db, (2, 2))
    (source / "shared_data").mkdir(parents=True)
    (source / "local_logs").mkdir()
    (source / "local_secrets").mkdir()
    destination.joinpath("shared_data").mkdir(parents=True)
    monkeypatch.setattr(portable, "_run", lambda *args, **kwargs: type("Result", (), {"stdout": ""})())
    monkeypatch.setattr(portable, "_is_leibniz_path", lambda path: True)

    portable.sync(source, destination, apply=False)

    with sqlite3.connect(destination_db) as connection:
        assert connection.execute("select value from sample").fetchone()[0] == "old"
    assert json.loads(capsys.readouterr().out)["mode"] == "dry_run"


def test_newer_destination_is_rejected(monkeypatch, tmp_path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source_db = source / "local_data" / "runs.sqlite3"
    destination_db = destination / "local_data" / "runs.sqlite3"
    _database(source_db, "old")
    _database(destination_db, "new")
    os.utime(source_db, (1, 1))
    os.utime(destination_db, (2, 2))
    for name in ("shared_data", "local_logs", "local_secrets"):
        (source / name).mkdir(parents=True)
        (destination / name).mkdir(parents=True)
    monkeypatch.setattr(portable, "_run", lambda *args, **kwargs: type("Result", (), {"stdout": ""})())
    monkeypatch.setattr(portable, "_is_leibniz_path", lambda path: True)

    try:
        portable.sync(source, destination, apply=False)
    except RuntimeError as exc:
        assert "SSD 含更新数据库" in str(exc)
    else:
        raise AssertionError("newer SSD database must be rejected")


def test_install_creates_data_links_and_workspace_instructions(monkeypatch, tmp_path) -> None:
    data_root = tmp_path / "canonical"
    workspace = tmp_path / "workspace"
    for name in portable.DATA_DIRS:
        (data_root / name).mkdir(parents=True)
    monkeypatch.setattr(portable, "_clone_or_update", lambda destination, remote, ref: destination.mkdir())
    monkeypatch.setattr(portable, "_copy_prebuilt_web", lambda destination: None)

    portable.install(data_root, workspace, v8_ref="branch", upstream_ref="master")

    for name in portable.DATA_DIRS:
        assert (workspace / name).is_symlink()
        assert (workspace / name).resolve() == (data_root / name).resolve()
    assert "Leibniz is authoritative" in (workspace / "AGENTS.md").read_text()
    assert (workspace / "CLAUDE.md").read_text() == (workspace / "AGENTS.md").read_text()


def test_secret_loader_preserves_shell_metacharacters(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EXISTING_VALUE", "kept")
    secrets = tmp_path / "local_secrets"
    secrets.mkdir()
    (secrets / "st_invest_quant.env").write_text(
        "TUSHARE_TOKEN=abc(123); .thumbcache=value/with+symbols%3D\n",
        encoding="utf-8",
    )

    environment = secret_environment(tmp_path)

    assert environment["EXISTING_VALUE"] == "kept"
    assert environment["TUSHARE_TOKEN"] == "abc(123); .thumbcache=value/with+symbols%3D"
