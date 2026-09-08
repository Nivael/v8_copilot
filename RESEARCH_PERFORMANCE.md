# Research script performance — 2026-09-08

Scope: the current P8C inventory path and the shared activity/price readers used
by P7/P8 research. Baseline: `19f3631` on `codex/p8c-volume-grid-v3`.
This is a measured, incremental optimization, not a claim that every research
command or provider backfill is faster.

A separate baseline profile of `research_workbench.py evidence` for
“沐邦的重整进展到哪一步了？” completed in 0.964 seconds, including imports.
That is one local query, not an end-to-end agent timing. The particular command
behind the owner's longer waits has not yet been identified.

## Findings and changes

- The first profiled inventory run spent 24.27 seconds importing pandas. Inventory
  does not export CSV. Load pandas only in the evaluation CSV export path. This
  first-load observation is not a repeatable 24-second saving: a subsequent
  baseline run imported its dependencies much faster.
- `latest_facts` fetched all JSON strings into a second list, decoded each into
  Python dictionaries, then validated them. Stream the cursor into Pydantic's
  JSON validator, retaining the same snapshot selection, field validation and
  ordering. No cache or stale-data behavior is introduced.
- The price reader materialized SQL rows, an overlay dictionary, and a globally
  sorted list of tuple keys. Stream SQL rows and overlay updates; sort dates
  within each symbol. Preserve positive-QFQ filtering and overlay priority.
- Grid construction rescanned the 250-day suspension window for every output
  row. Compute missing suspension dates once per symbol and use the existing
  binary-search window helper. Compute share-change indices once with NumPy.
  Price ranks, sample gates, stage timing, cooldowns and thresholds are unchanged.

## Verification

Three alternating, unprofiled real-data runs with the same Python 3.12 environment:

| Version | Run 1 | Run 2 | Run 3 | Median |
| --- | --- | --- | --- | --- |
| Baseline | 14.761 s | 13.645 s | 13.877 s | 13.877 s |
| Candidate | 12.032 s | 11.198 s | 11.739 s | 11.739 s |

Median wall time decreased **15.4%** (about 2.14 seconds per full inventory).
This measures local inventory computation, not network backfills, full return
evaluation, agent response latency, or a guaranteed cold-start improvement.

With the frozen v3.1 suspension evidence, both versions produce identical grid
and episode SHA-256 digests, all coverage counters and inventory results:
68,680 grid rows; 3,923 episodes; 163 low-flat active episodes / 100 companies;
2023/2024/2025 counts 64/80/19. The code hash and enclosing input digest change
intentionally, so evaluation requires a newly generated inventory.

Full Python suite: candidate 406 passed / 10 failed; baseline 405 passed / the
same 10 failed. Existing failures are in `test_api_contract_v2`,
`test_p2_4_analysis_engine`, `test_p4_market_context`, and
`test_real_question_recovery`: current local data no longer matches some frozen
answer expectations, and some market-context/factor outputs have coverage gaps.
They remain unresolved and the full suite is not green. The added price test
covers overlay precedence, ordering, invalid prices, date bounds and missing DBs.

## Repeat the comparison

From this worktree, after `uv sync --group dev`:

```bash
uv run python benchmarks/grid_inventory.py \
  --baseline ../p7-daily-intelligence \
  --data-root ../../.. \
  --suspension-evidence ../../../local_data/v8_copilot/p8_grid_v3_1/suspensions/evidence.json \
  --output out/performance --repeats 3
```

The harness uses the same interpreter, runs versions sequentially in alternating
order, compares every inventory field/input except the changed script hash, and
fails on any mismatch. `benchmark.json` contains individual timings and medians.
It reads local evidence and writes inventories to its output directory; it does
not request providers, copy databases or evaluate returns.

For a different slow script, first capture its profile with the same arguments
used in normal operation (profiling executes that script, including any writes):

```bash
V8_DATA_ROOT=../../.. uv run python -m cProfile -o /tmp/research.prof \
  p8_volume_grid.py --output /tmp/grid-profile \
  --suspension-evidence ../../../local_data/v8_copilot/p8_grid_v3_1/suspensions/evidence.json
uv run python -c 'import pstats; pstats.Stats("/tmp/research.prof").sort_stats("cumulative").print_stats(25)'
```

Use ordinary wall time to report speedups; profiler overhead is useful for
locating work, not for estimating a user's elapsed time. Do not compare a cold
baseline with a warmed candidate and report the entire difference as a code win.
