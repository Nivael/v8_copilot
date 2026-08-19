# Leibniz portable workspace

This directory makes the existing v8 workflow portable without copying the
research databases onto a Mac's internal disk.

## Frozen architecture

- GitHub is the source of truth for tracked code and documentation.
- Leibniz `shared_data/`, `local_data/`, `local_logs/`, and `local_secrets/`
  are the single local data source of truth for both Macs.
- A clean portable workspace lives at `/Volumes/Leibniz/STResearch`; its data
  directories are symlinks to `/Volumes/Leibniz/dev/st_research` and are not
  duplicate databases.
- Python, uv caches, and machine-specific virtual environments live under
  `/Volumes/Leibniz/STResearch/.runtime/<host>-<architecture>/`.
- Data maintenance is the only networked data writer. The wrapper creates an
  auditable writer lock and archives it after the command exits.

Do not use file sync, iCloud, Dropbox, or `rsync --delete` as a database
replication mechanism. After the initial handoff, operate directly on the SSD.

## One-time preparation on the current Mac

From this repository:

```bash
uv run python portable/portable_workspace.py sync \
  --source-root /Users/plato/dev/st_research \
  --data-root /Volumes/Leibniz/dev/st_research

# Review the dry-run, then:
uv run python portable/portable_workspace.py sync \
  --source-root /Users/plato/dev/st_research \
  --data-root /Volumes/Leibniz/dev/st_research \
  --apply

uv run python portable/portable_workspace.py install \
  --data-root /Volumes/Leibniz/dev/st_research \
  --workspace-root /Volumes/Leibniz/STResearch
```

`sync` uses SQLite's backup API and atomic replacement for databases. It
refuses to overwrite a newer SSD database. Non-database files use rsync
without deletion. The internal-disk source remains the rollback copy.

## First boot on the travel Mac

1. Attach Leibniz and confirm it is mounted exactly as
   `/Volumes/Leibniz`.
2. Grant Terminal, ChatGPT, Codex, and Claude access to removable volumes in
   macOS Privacy & Security if prompted.
3. Open `/Volumes/Leibniz/STResearch` as the project/environment in Codex and
   Claude.
4. In Terminal:

```bash
cd /Volumes/Leibniz/STResearch/v8_copilot
./portable/st-portable bootstrap
./portable/st-portable doctor
./portable/st-portable serve
```

If uv is missing, `bootstrap` prints a command that installs a machine-native
uv binary under the SSD runtime directory. It does not install Python or the
virtual environment onto the internal disk. The committed `uv.lock` selects
the correct wheels for Intel or Apple Silicon.

The existing prebuilt `web/dist` is enough to run the browser UI without
Node. Node/npm is only required if frontend source is changed; then run
`./portable/st-portable build-web`.

## Daily use

- Commander prompt: `portable/prompts/COMMANDER.md`
- Data task prompt: `portable/prompts/DATA_MAINTENANCE.md`
- Research task prompt: `portable/prompts/RESEARCH.md`
- Browser audit: run `./portable/st-portable serve`, then open
  `http://127.0.0.1:8765`

Useful commands:

```bash
./portable/st-portable doctor
./portable/st-portable data show-universe
./portable/st-portable data plan --universe-current \
  --price-through YYYY-MM-DD --announcement-through YYYY-MM-DD
./portable/st-portable research experiences --status accepted
./portable/st-portable test
```

The data task should use the detailed sequence in `OPERATING_MODEL.md`. Do not
run a data refresh while the browser/API or research task is active.

## End of trip

1. Finish and push tracked code changes from both repositories.
2. Stop the API with `Ctrl-C` and ensure no refresh is running.
3. Run `./portable/st-portable doctor` and save its summary in the commander
   task.
4. Eject Leibniz normally.
5. Back on the main Mac, continue to use the SSD data root. Pull GitHub code;
   do not copy the stale internal `local_data` back over the SSD.

## Security boundary

The SSD currently mounts with ownership disabled, so Unix mode bits alone are
not a sufficient secret boundary. Verify in Disk Utility/Finder that Leibniz
is APFS encrypted before travel. If it is not encrypted, move API tokens to
the travel Mac's Keychain or an encrypted secrets store and leave only a
non-secret env template on the SSD.
