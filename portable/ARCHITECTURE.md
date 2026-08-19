# Portable workspace architecture decision

Date: 2026-08-19

## Requirement

Use an older travel Mac with almost no free internal storage while preserving
the full v8 data-maintenance, Codex-led research, browser audit, experience,
Git, and Claude workflows. The same work must return to the main Mac without
reconciling two independently changed databases.

## Current architecture

v8 is already split in the right places: tracked Python/React code in Git;
large versioned research inputs under `shared_data`; mutable maintenance,
manifest, Research Run, and experience stores under `local_data`; tiny local
tokens under `local_secrets`. `V8_DATA_ROOT` is the existing seam between code
and data. The old SSD copy cannot itself be treated as a clean Git workspace:
its copied worktree metadata contains absolute paths to the main Mac.

## Greenfield alternative

A hosted database and object store would make multi-device access natural,
but would introduce authentication, migrations, network dependency, write
coordination, and a service boundary that the private single-user product
does not otherwise need. It would weaken offline research and greatly expand
the migration surface.

## Options considered

1. Copy everything to each Mac. Rejected: exceeds internal storage and creates
   two mutable SQLite histories.
2. Keep Git code internally and only data on SSD. Feasible, but creates path
   configuration on every app and still consumes scarce disk with runtimes.
3. Put clean Git clones and per-machine runtimes on SSD, with one symlinked
   canonical data root. Selected: smallest change, no database bridge, offline
   capable, and directly uses the existing `V8_DATA_ROOT` boundary.
4. Move to hosted storage. Deferred: disproportionate complexity for one
   owner and a temporary travel machine.

## Decision

`/Volumes/Leibniz/STResearch` is the portable app workspace. GitHub owns code;
`/Volumes/Leibniz/dev/st_research/{shared_data,local_data,local_logs,local_secrets}`
owns data. The workspace symlinks those four directories and contains clean
clones. Machine-native Python, virtualenvs, and caches live in `.runtime` on
the SSD. A data-writer guard prevents research/API overlap and leaves an audit
trail instead of silently deleting locks.

## Migration and rollback

The initial handoff is dry-run first. SQLite uses the backup API, `quick_check`,
and same-directory atomic replacement; other files use rsync without delete.
Any destination database newer than its source aborts the whole handoff before
writes. The main Mac's original data remains the rollback copy until the SSD
workspace is accepted. After acceptance, the SSD becomes canonical and the
old internal copy must never be pushed back over it.

## Risks

- SSD loss is now the main local-data risk: keep it encrypted and backed up.
- Surprise unplug during a write can leave a stale lock; archive it only after
  verifying no maintenance process runs, then run doctor/SQLite checks.
- Intel and Apple Silicon cannot share a virtualenv. Per-machine runtime paths
  avoid that; the universal uv lock resolves platform wheels.
- Git can still diverge if work is left uncommitted. Every machine handoff ends
  with a clean status and pushed branch.
- External-volume permissions for Codex/Claude are a macOS UI setting and
  cannot be provisioned by repository code.
