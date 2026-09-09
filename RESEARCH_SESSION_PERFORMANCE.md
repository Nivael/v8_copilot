# Compound research session: measured costs and recoverable work

2026-09-10. Follow-up to `RESEARCH_PERFORMANCE.md` and `CODE_SIMPLIFICATION_REVIEW.md`.
The live task joined Mubang financing, Zhengbang court chronology, Dongyi repricing,
role allocations, and historical price windows. Private research output is in ignored
`out/mubang_20260910/`; no investor holdings or announcement bodies belong in this change.

## Findings

The complete question previously crashed: `resolve_stocks` resolved three companies,
`core_router` created a comparison cohort, but `card_stock_comparison` only supports
two distinct stocks. The route now returns an explicit decomposition requirement,
retaining all object identifiers. It does not claim to have answered the compound
question or silently discard a comparator. The research host continues with scoped
subquestions, as in this session. Supported two-stock routes and contracts are unchanged.

The initial 1.23 s pack timing used a question file that omitted the leading Mubang
sentence, and therefore measured a two-company comparison. It is **not** the timing
of the full task. After correcting the input, the error reproduced in about 0.25 s;
the fixed full-question pack returns its decomposition requirement in about 0.32 s.
A separate explicit Mubang scope took about 0.78 s.

Other measured stages in this session:

| Stage | Observed wall time | Scope |
|---|---:|---|
| Accepted methods CLI | 0.39 s | Local experience lookup |
| Acquisition decision CLI | 0.16 s | Local pack plan |
| Candidate agreement SQL | about 1.5 s | 60 titles / 21 issuers |
| Official body acquisition | 10.55 s | 47 documents: 10 existing SQLite bodies, 37 downloaded/extracted; 6 workers |
| Same bodies, offline cache verification | median 0.033 s | Three runs; all 47 texts equal the first result |
| Scoped reviewed body verification | 0.020 s | 24 documents; all expected text digests match |
| Indexed price read and event study | about 0.06–0.07 s | 12 paired cases, 5/20/60-session windows and sensitivity |
| Current CNINFO metadata check | 0.58 s | One company, recent three-day range |
| PDF download / parse, separate spot check | 0.079 / 0.108 s; 0.114 / 0.632 s | 7-page Mubang and 60-page Bangjie documents; no retries |
| PDF JSON serialization, spot check | under 0.001 s each | The same two documents; excludes authored prose |
| Fact draft construction and validation | 0.006 s | 11 statements / 39 references; excludes writing the narrative |
| Full regression suite | 51.29 s | 433 passed / same 10 baseline failures |

The first sandboxed PDF requests failed immediately with network errors; the authorized
network run succeeded without retry loops. The original 50-minute wait was not
reproduced as a slow SQL calculation or a network retry loop. These stage durations
are **not** a complete wall-time decomposition: web tool round trips, selecting and
reading text, research synthesis, coding, tests, and communication also consume time.
No overall speedup percentage is justified against the owner's uninstrumented run.

The expensive human/host work was reconstructing the intended questions and reviewing
contract versions, roles, units, disclosure dates, and missing data. A generic comparison
pack does not answer an investor-agreement sequence question. Reading every replacement
agreement before choosing the cohort also led to unnecessary text review.

## Changes for reuse

- `deterministic_router.py` guards unsupported comparison cardinality before execution.
- `benchmarks/fixtures/investor_agreements_20260910.json` stores a reviewed public
  casebook, distinct inventory/disclosure dates, exclusions, role prices and text hashes.
  This is exploratory case material, not a new released Lens or universal sample.
- `benchmarks/cache_agreement_bodies.py` reuses the existing bounded official PDF reader,
  fetches only the selected documents with at most six workers, requires an explicit
  cache directory, defaults to offline, checks text hashes and surfaces individual
  failures. Network requires the explicit `--allow-network` flag. No SQLite writes.
- `benchmarks/agreement_event_study.py` reads only indexed symbol price histories,
  preserves missing horizons, flags unverified long entry gaps, and always emits the
  next-session sensitivity alongside the main descriptive result. This turns later
  recalculation into a subsecond local operation; it does not automate contract judgment.

Run from the worktree root with the project's Python environment and configured data root:

```sh
python benchmarks/cache_agreement_bodies.py --cache-dir out/agreement-cache --output out/body-check.json --allow-network
python benchmarks/agreement_event_study.py --output out/agreement-study.json
python -m pytest tests/test_comparison_scope.py tests/test_agreement_event_study.py
```

With the 24 required bodies cached, omit `--allow-network`. Cached body dates use the
inventory date; event windows use the separately reviewed disclosure date. Changing
one into the other fails the cache identity check, correctly requiring a review.

## Evidence limits discovered in the session

Among 12 selected pairs, 11 financial agreements were later and one same-day. Nine of
the 11 later contracts had a higher financial price, two lower. This is not a population
estimate. Some industrial contracts already set the financial price before financial
parties signed, so later signature is not necessarily later price discovery.

The 20-session median changes sign when entry moves to the next session. Therefore
there is no robust positive/negative event effect to claim. The output preserves that
sensitivity and the missing 60-session horizons, rather than interpreting missing
prices as successful exits, failures, or flat returns. Main-source historical gaps and
new-vs-old regulatory regimes still need explicit treatment before a released mechanism.

The next useful automation is host-level subquestion coverage and a reviewed materialized
agreement table. It should preserve first selection, first binding contract, supplements,
repricing, first/full financial funding, court acceptance, and approval as separate events.
A further blanket code deletion would not address this measured workflow cost.
