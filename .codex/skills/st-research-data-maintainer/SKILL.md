---
name: st-research-data-maintainer
description: Use in the dedicated ST Research data-maintenance task to refresh price and official-announcement inputs outside the answer path, validate local materializations, and publish one strict freshness manifest before research begins.
---

# ST Research Data Maintainer

Operate the data supply window. Do not answer research questions in this task.

## Boundaries

- Network access and research-data writes belong only to this maintenance task and
  require the user's authorization when the environment asks for it.
- Never run a refresh from the research-answer task or API process.
- Preserve existing work in the upstream producer repository. Inspect status first;
  never reset, clean, or discard another agent's changes.
- Refresh only the explicitly declared research universe. Report partial coverage.
- Announcement metadata must come from CNINFO and be promoted through the v8
  validator. PDF bodies are separately materialized only when needed.
- Do not edit frozen contracts or Lens releases.

## Daily workflow

1. From `v8_copilot/`, inspect current observed state:

   `uv run python data_maintenance.py manifest`

2. Agree on two targets before writing anything:

   - latest completed A-share trading date for price;
   - announcement check date and the exact six-digit symbols to cover.

3. Refresh prices with the existing upstream producer in `../ST_invest_quant`.
   Use its `invest-st sync-daily` command for each declared symbol and write the
   canonical v5 SQLite selected by `--db ../shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3`.
   Use explicit `--start-date` and `--end-date`; do not run an unbounded rebuild.

4. Fetch each symbol's CNINFO metadata into a temporary JSON file with the upstream
   `invest-st fetch-company-announcements --source cninfo` command. Promote it only
   after validation:

   `uv run python data_maintenance.py promote-announcements --input <temp.json> --symbol <symbol>`

5. If a materialization request names an official PDF, fetch and validate that body
   through the existing bounded announcement materializer. Do not bulk-fetch bodies
   without a stated question or coverage task.

6. Publish the strict unified manifest:

   `uv run python data_maintenance.py manifest --expected-price-through <YYYY-MM-DD> --expected-announcement-checked-through <YYYY-MM-DD> --symbol <symbol> --require-ready`

   Repeat `--symbol` for every covered stock. Price and announcement freshness are
   checked stock by stock. A non-zero exit or
   `overall_status=gaps` means the research window must be told exactly which source
   or symbol is stale; never call the update successful.

7. Report only the manifest ID, source dates, covered symbols, failures and remaining
   gaps. Do not produce investment analysis here.

## Handoff to the research task

Provide the manifest ID and its declared coverage. The research task still reads the
actual SQLite/cache/Lens evidence and records its own EvidencePack; the manifest is
freshness evidence, not a substitute for query backing.
