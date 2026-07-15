---
name: st-research-data-maintainer
description: Use in the dedicated ST Research data-maintenance task to refresh price and official-announcement inputs outside the answer path, validate local materializations, and publish one strict freshness manifest before research begins.
---

# ST Research Data Maintainer

Operate the data supply window. Do not answer research questions in this task.

## Boundaries

- Network access and canonical price/announcement writes belong only to this
  maintenance task and require the user's authorization when the environment asks.
- Never run a refresh from the research-answer task or API process.
- Preserve existing work in the upstream producer repository. Inspect status first;
  never reset, clean, or discard another agent's changes.
- Refresh only the explicitly declared research universe. Report partial coverage.
- Prices must come from Tushare `daily + adj_factor` and be stored as qfq.
  Announcement metadata must come from CNINFO. PDF bodies are separately
  materialized only when needed.
- Do not edit frozen contracts or Lens releases.

## Daily workflow

1. From `v8_copilot/`, inspect current observed state:

   `uv run python data_maintenance.py manifest`

2. Agree on two targets before writing anything:

   - latest completed A-share trading date for price;
   - announcement check date and the exact six-digit symbols to cover.

3. Run the bounded refresh once for the full declared scope:

   `python data_maintenance.py refresh --env-file <local-tushare-env> --price-through <YYYY-MM-DD> --announcement-through <YYYY-MM-DD> --symbol <symbol>`

   Repeat `--symbol`. The command stores source+symbol checkpoints in the dedicated
   maintenance database, skips an already completed target, overlaps recent dates,
   deduplicates prices by trade date and announcements by announcement ID, and
   publishes the manifest. It never prints the Tushare token.

4. Inspect `python data_maintenance.py checkpoints`. A failed attempt must preserve
   the last successful cursor. Tushare token expiry, CNINFO failure, or partial stock
   coverage remains a named gap; never fall back to a different provider. If the
   latest Tushare adjustment factor changed, allow the maintainer to rebuild that
   symbol's complete qfq history instead of mixing adjustment bases.

5. If a materialization request names an official PDF, fetch and validate that body
   through the existing bounded announcement materializer. Do not bulk-fetch bodies
   without a stated question or coverage task.

6. If metadata was fetched by another authorized bounded tool, merge it through:

   `python data_maintenance.py promote-announcements --input <temp.json> --symbol <symbol> --checked-through <YYYY-MM-DD>`

7. A standalone manifest can be republished with:

   `uv run python data_maintenance.py manifest --expected-price-through <YYYY-MM-DD> --expected-announcement-checked-through <YYYY-MM-DD> --symbol <symbol> --require-ready`

   Repeat `--symbol` for every covered stock. Price and announcement freshness are
   checked stock by stock. A non-zero exit or
   `overall_status=gaps` means the research window must be told exactly which source
   or symbol is stale; never call the update successful.

8. Run `python experience_governance.py verify`. It is due-aware, so invoking it in
   every maintenance window does not repeat checks before their cadence. A failed
   accepted-method regression automatically moves that experience to `blocked` and
   refreshes the accepted registry; it does not rewrite research evidence.

9. Report only the manifest ID, source dates, covered symbols, failures and remaining
   gaps. Do not produce investment analysis here.

## Handoff to the research task

Provide the manifest ID and its declared coverage. The research task still reads the
actual SQLite/cache/Lens evidence and records its own EvidencePack; the manifest is
freshness evidence, not a substitute for query backing.
