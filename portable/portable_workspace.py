"""Prepare and validate a Git-on-SSD-data ST Research workspace."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_DATA_ROOT = Path("/Volumes/Leibniz/dev/st_research")
DEFAULT_WORKSPACE_ROOT = Path("/Volumes/Leibniz/STResearch")
V8_REMOTE = "https://github.com/Nivael/v8_copilot.git"
UPSTREAM_REMOTE = "https://github.com/byliu-labs/ST_invest_quant.git"
V8_REF = "codex/leibniz-portable-workspace"
UPSTREAM_REF = "master"
DATA_DIRS = ("shared_data", "local_data", "local_logs")


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def _run(command: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=check, text=True, capture_output=True)


def _git_clean(repository: Path) -> bool:
    return not _run(["git", "status", "--porcelain"], cwd=repository).stdout.strip()


def _clone_or_update(destination: Path, remote: str, ref: str) -> None:
    if not destination.exists():
        _run(["git", "clone", remote, str(destination)])
    if not (destination / ".git").is_dir():
        raise RuntimeError(f"不是 clean clone: {destination}")
    if not _git_clean(destination):
        raise RuntimeError(f"仓库有未提交改动，拒绝切换: {destination}")
    _run(["git", "remote", "set-url", "origin", remote], cwd=destination)
    _run(["git", "fetch", "origin", "--prune"], cwd=destination)
    remote_ref = f"origin/{ref}"
    _run(["git", "rev-parse", "--verify", remote_ref], cwd=destination)
    local = _run(["git", "branch", "--list", ref], cwd=destination).stdout.strip()
    if local:
        _run(["git", "checkout", ref], cwd=destination)
        _run(["git", "merge", "--ff-only", remote_ref], cwd=destination)
    else:
        _run(["git", "checkout", "-b", ref, "--track", remote_ref], cwd=destination)


def _write_workspace_instructions(workspace_root: Path, data_root: Path) -> None:
    content = f"""# Portable ST Research workspace

This is the travel workspace on Leibniz. Last generated: {datetime.now(timezone.utc).isoformat()}.

- Active product: `v8_copilot/`.
- Upstream ingestion code: `ST_invest_quant/`.
- Canonical local data root: `{data_root}` through the symlinked data directories here.
- Secrets stay on each Mac under `~/Library/Application Support/STResearch/secrets`.
- Run `v8_copilot/portable/st-portable doctor` before work.
- GitHub is authoritative for tracked code. Leibniz is authoritative for local/shared data.
- Never copy an internal-disk database over a newer SSD database.
- Never run research/API while the data-maintenance writer lock is active.
- Never use `rm`, reset, clean, or force checkout to resolve project state.
- Data window uses `$st-research-data-maintainer`; research window uses `$st-research-codex`.
- Browser `/runs` is an audit surface, not another research agent.

Read `v8_copilot/portable/README.md`, then the relevant prompt under
`v8_copilot/portable/prompts/`.
"""
    (workspace_root / "AGENTS.md").write_text(content, encoding="utf-8")
    (workspace_root / "CLAUDE.md").write_text(content, encoding="utf-8")


def _copy_prebuilt_web(destination_repository: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "web" / "dist"
    destination = destination_repository / "web" / "dist"
    if source.is_dir() and (source / "index.html").is_file() and source != destination:
        shutil.copytree(source, destination, dirs_exist_ok=True)


def install(data_root: Path, workspace_root: Path, *, v8_ref: str, upstream_ref: str) -> None:
    data_root = data_root.resolve()
    if not (data_root / "shared_data").is_dir():
        raise RuntimeError(f"canonical shared_data 不存在: {data_root}")
    workspace_root.mkdir(parents=True, exist_ok=True)
    legacy_secret_link = workspace_root / "local_secrets"
    if legacy_secret_link.is_symlink():
        archive = (
            data_root / "local_logs" / "portable_migration"
            / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            / "retired-workspace-local_secrets-link"
        )
        archive.parent.mkdir(parents=True, exist_ok=True)
        legacy_secret_link.replace(archive)
    elif legacy_secret_link.exists():
        raise RuntimeError(f"拒绝覆盖既有 local_secrets: {legacy_secret_link}")
    for name in DATA_DIRS:
        source = data_root / name
        source.mkdir(parents=True, exist_ok=True)
        link = workspace_root / name
        if link.is_symlink():
            if link.resolve() != source.resolve():
                raise RuntimeError(f"symlink 指向错误: {link} -> {link.resolve()}")
        elif link.exists():
            raise RuntimeError(f"拒绝覆盖既有非 symlink: {link}")
        else:
            link.symlink_to(source, target_is_directory=True)
    _clone_or_update(workspace_root / "v8_copilot", V8_REMOTE, v8_ref)
    _clone_or_update(workspace_root / "ST_invest_quant", UPSTREAM_REMOTE, upstream_ref)
    _copy_prebuilt_web(workspace_root / "v8_copilot")
    _write_workspace_instructions(workspace_root, data_root)
    print(json.dumps({
        "status": "installed",
        "workspace_root": str(workspace_root),
        "data_root": str(data_root),
        "v8_ref": v8_ref,
        "upstream_ref": upstream_ref,
    }, ensure_ascii=False, indent=2))


def _sqlite_paths(root: Path) -> Iterable[Path]:
    for area in (root / "local_data", root / "shared_data"):
        if area.exists():
            yield from sorted(area.rglob("*.sqlite3"))


def _quick_check(path: Path) -> str:
    uri = f"file:{path}?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=30) as connection:
        row = connection.execute("pragma quick_check").fetchone()
    return str(row[0]) if row else "missing-result"


def _is_newer(source: Path, destination: Path) -> bool:
    return destination.exists() and destination.stat().st_mtime_ns > source.stat().st_mtime_ns


def _archive_sidecars(destination: Path, archive_root: Path) -> None:
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{destination}{suffix}")
        if sidecar.exists():
            archive_root.mkdir(parents=True, exist_ok=True)
            sidecar.replace(archive_root / sidecar.name)


def _backup_sqlite(source: Path, destination: Path, archive_root: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.portable-tmp")
    if temporary.exists():
        archive_root.mkdir(parents=True, exist_ok=True)
        temporary.replace(archive_root / temporary.name)
    source_uri = f"file:{source}?mode=ro"
    with sqlite3.connect(source_uri, uri=True, timeout=60) as source_db:
        with sqlite3.connect(temporary) as destination_db:
            source_db.backup(destination_db, pages=4096)
    if _quick_check(temporary) != "ok":
        raise RuntimeError(f"SQLite backup quick_check 失败: {source}")
    _archive_sidecars(destination, archive_root)
    os.replace(temporary, destination)
    shutil.copystat(source, destination)


def _rsync_area(source: Path, destination: Path, *, apply: bool) -> list[str]:
    destination.mkdir(parents=True, exist_ok=True)
    command = [
        "rsync", "-a", "--update", "--itemize-changes",
        "--exclude", "*.sqlite3", "--exclude", "*.sqlite3-wal",
        "--exclude", "*.sqlite3-shm", "--exclude", ".DS_Store",
    ]
    if not apply:
        command.append("--dry-run")
    command.extend([f"{source}/", f"{destination}/"])
    output = _run(command).stdout.splitlines()
    return [line for line in output if line.strip() and not line.startswith(".d..t")]


def _is_leibniz_path(path: Path) -> bool:
    return path.parts[:3] == ("/", "Volumes", "Leibniz")


def _open_database_handles(paths: Iterable[Path]) -> list[str]:
    if shutil.which("lsof") is None:
        return []
    result = _run(["lsof", *map(str, paths)], check=False)
    return result.stdout.splitlines()[1:] if result.stdout.strip() else []


def sync(source_root: Path, data_root: Path, *, apply: bool) -> None:
    source_root = source_root.resolve()
    data_root = data_root.resolve()
    if source_root == data_root:
        raise RuntimeError("source 与 destination 相同")
    if not _is_leibniz_path(data_root):
        raise RuntimeError(f"destination 必须位于 /Volumes/Leibniz: {data_root}")
    if not data_root.exists():
        raise RuntimeError(f"Leibniz data root 不存在: {data_root}")
    archive_root = data_root / "local_logs" / "portable_migration" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sqlite_changes: list[tuple[Path, Path]] = []
    newer_destinations: list[str] = []
    for source in _sqlite_paths(source_root):
        relative = source.relative_to(source_root)
        destination = data_root / relative
        if _is_newer(source, destination):
            newer_destinations.append(str(relative))
            continue
        if destination.exists():
            same = (
                source.stat().st_size == destination.stat().st_size
                and source.stat().st_mtime_ns == destination.stat().st_mtime_ns
            )
            if same:
                continue
        sqlite_changes.append((source, destination))

    if newer_destinations:
        raise RuntimeError(
            "SSD 含更新数据库，拒绝用旧 source 覆盖: " + ", ".join(newer_destinations)
        )
    if apply:
        handles = _open_database_handles([
            path for pair in sqlite_changes for path in pair if path.exists()
        ])
        if handles:
            raise RuntimeError("数据库仍被进程打开，拒绝迁移:\n" + "\n".join(handles))

    rsync_changes: dict[str, list[str]] = {}
    for name in DATA_DIRS:
        source = source_root / name
        if source.exists():
            rsync_changes[name] = _rsync_area(source, data_root / name, apply=apply)
    if apply:
        for source, destination in sqlite_changes:
            print(f"SQLite backup: {source} -> {destination}", flush=True)
            _backup_sqlite(source, destination, archive_root)
    print(json.dumps({
        "mode": "apply" if apply else "dry_run",
        "source_root": str(source_root),
        "data_root": str(data_root),
        "non_sqlite_change_count": sum(map(len, rsync_changes.values())),
        "sqlite_change_count": len(sqlite_changes),
        "sqlite_changes": [str(source.relative_to(source_root)) for source, _ in sqlite_changes],
        "rollback_copy": str(source_root),
    }, ensure_ascii=False, indent=2))


def _manifest_detail(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    fields = []
    for key in ("manifest_id", "overall_status", "as_of", "price_through", "announcement_through"):
        if payload.get(key):
            fields.append(f"{key}={payload[key]}")
    return ", ".join(fields) or "valid JSON"


def doctor(workspace_root: Path) -> int:
    workspace_root = workspace_root.resolve()
    checks: list[Check] = []
    data_root = workspace_root
    for name in DATA_DIRS:
        path = workspace_root / name
        checks.append(Check(
            f"data_link:{name}",
            "pass" if path.exists() else "fail",
            str(path.resolve()) if path.exists() else "missing",
        ))
    usage = shutil.disk_usage(workspace_root)
    free_gib = usage.free / 1024**3
    checks.append(Check("disk_free", "pass" if free_gib >= 5 else "fail", f"{free_gib:.1f} GiB"))
    for command in ("git", "uv"):
        location = shutil.which(command)
        checks.append(Check(f"command:{command}", "pass" if location else "fail", location or "missing"))
    node = shutil.which("node")
    checks.append(Check("command:node", "pass" if node else "warn", node or "optional; only needed for Web development"))
    diskutil = shutil.which("diskutil")
    if diskutil:
        result = _run([diskutil, "info", str(workspace_root)], check=False)
        detail = result.stdout + result.stderr
        encrypted = re.search(r"(?:FileVault|Encrypted):\s+Yes", detail) is not None
        checks.append(Check(
            "ssd_encryption", "pass" if encrypted else "warn",
            "diskutil reports encryption" if encrypted else "encryption not confirmed; verify before carrying secrets",
        ))
    else:
        checks.append(Check("ssd_encryption", "warn", "diskutil unavailable; verify APFS encryption manually"))

    v8 = workspace_root / "v8_copilot"
    if (v8 / ".git").is_dir():
        branch = _run(["git", "branch", "--show-current"], cwd=v8).stdout.strip()
        head = _run(["git", "rev-parse", "--short", "HEAD"], cwd=v8).stdout.strip()
        clean = _git_clean(v8)
        checks.append(Check("git:v8", "pass" if clean else "warn", f"{branch}@{head}; clean={clean}"))
    else:
        checks.append(Check("git:v8", "fail", "clean clone missing"))

    lock = data_root / "local_data" / "v8_copilot" / ".portable_writer_lock"
    checks.append(Check("writer_lock", "warn" if lock.exists() else "pass", str(lock) if lock.exists() else "none"))
    main_db = data_root / "shared_data" / "v5" / "backup_universe" / "st_stocks_v5_backup.sqlite3"
    if main_db.is_file():
        result = _quick_check(main_db)
        checks.append(Check("sqlite:canonical", "pass" if result == "ok" else "fail", result))
    else:
        checks.append(Check("sqlite:canonical", "fail", "missing"))
    for relative in (
        "local_data/v8_copilot/research_run_ledger.sqlite3",
        "local_data/v8_copilot/experience_repository.sqlite3",
        "local_data/v8_copilot/data_maintenance.sqlite3",
    ):
        path = data_root / relative
        if path.is_file():
            result = _quick_check(path)
            checks.append(Check(f"sqlite:{path.name}", "pass" if result == "ok" else "fail", result))
        else:
            checks.append(Check(f"sqlite:{path.name}", "fail", "missing"))
    manifest = data_root / "local_data" / "v8_copilot" / "freshness_manifest.json"
    try:
        checks.append(Check("freshness_manifest", "pass", _manifest_detail(manifest)))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        checks.append(Check("freshness_manifest", "fail", f"{type(exc).__name__}: {exc}"))
    web_dist = v8 / "web" / "dist" / "index.html"
    checks.append(Check("web_dist", "pass" if web_dist.is_file() else "warn", str(web_dist) if web_dist.is_file() else "run build-web"))
    secrets = Path(os.environ.get(
        "V8_SECRET_ROOT",
        Path.home() / "Library" / "Application Support" / "STResearch" / "secrets",
    ))
    secret_files = [path for path in secrets.rglob("*.env") if path.is_file()] if secrets.exists() else []
    bad_modes = [str(path) for path in secret_files if path.stat().st_mode & 0o077]
    checks.append(Check(
        "secret_modes", "warn" if bad_modes else ("pass" if secret_files else "fail"),
        f"root={secrets}; env_files={len(secret_files)}; permissive={len(bad_modes)}",
    ))

    print(json.dumps({
        "workspace_root": str(workspace_root),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": [asdict(row) for row in checks],
        "summary": {
            status: sum(row.status == status for row in checks)
            for status in ("pass", "warn", "fail")
        },
    }, ensure_ascii=False, indent=2))
    return 1 if any(row.status == "fail" for row in checks) else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    install_parser = sub.add_parser("install")
    install_parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    install_parser.add_argument("--workspace-root", type=Path, default=DEFAULT_WORKSPACE_ROOT)
    install_parser.add_argument("--v8-ref", default=V8_REF)
    install_parser.add_argument("--upstream-ref", default=UPSTREAM_REF)
    sync_parser = sub.add_parser("sync")
    sync_parser.add_argument("--source-root", type=Path, required=True)
    sync_parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    sync_parser.add_argument("--apply", action="store_true")
    doctor_parser = sub.add_parser("doctor")
    doctor_parser.add_argument("--workspace-root", type=Path, default=DEFAULT_WORKSPACE_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "install":
            install(args.data_root, args.workspace_root, v8_ref=args.v8_ref, upstream_ref=args.upstream_ref)
            return 0
        if args.command == "sync":
            sync(args.source_root, args.data_root, apply=args.apply)
            return 0
        return doctor(args.workspace_root)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()[-4000:]
        print(json.dumps({
            "status": "error", "command": exc.cmd,
            "exit_code": exc.returncode, "error": detail,
        }, ensure_ascii=False), file=sys.stderr)
        return 2
    except (OSError, RuntimeError, sqlite3.Error) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
