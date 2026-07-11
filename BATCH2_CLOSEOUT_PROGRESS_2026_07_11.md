# v8 Batch 2 Closeout Progress

Status: complete. Reviewed closeout commit `3c28002` is integrated into canonical
`master`, and canonical smoke QA has passed.

## Baseline

- Canonical repository: `v8_copilot/` under the `st_research` workspace.
- Closeout branch base: `master` at `34463db`.
- Frozen answer contract remains `v8_answer_contract_v0`.
- Additive public API contract is `v8_copilot_api_contract_v1`; v0 was not edited.

## P2 debt closure

### Evidence navigation

- API v1 returns typed navigation references for stock, date, announcement,
  episode, lens, provenance, and data debt.
- `QT-002` now executes a real selected-event window across price,
  announcements, and episode data.
- The Copilot renders all seven reference kinds as links; the evidence inspector
  also links lens and provenance rows.
- Stock dossier to Copilot context navigation remains intact.

### Question sedimentation

- `QuestionCard` is a versioned Pydantic/JSON Schema product object with lifecycle
  validation and stable candidate IDs.
- API v1 returns typed QuestionCards and data-debt candidates.
- Question Drawer is visible for both answered and fallback responses, including
  cases where an AnswerCard exists.
- This batch only previews candidates; it does not write to the evidence library.

### Query templates

- `v8_query_template_contract_v0` defines eight reusable query templates with
  required inputs, definition variants, caveats, debt fallbacks, and executor
  keys.
- Every template carries `not_evidence=true`.
- Existing deterministic builders dispatch through the registry; selected-event
  window execution is no longer a stub.

### Freshness and failure behavior

- Removed the hard-coded price snapshot date and sample counts.
- Answer builders read actual SQLite, episode manifest, and release-library
  metadata and declare only the sources they consume.
- Multi-source answers expose the oldest source `as_of` as the limiting boundary.
- A fixed 10-case fault-injection matrix fails loudly on missing tables/files,
  corrupt episode JSON, missing manifest metadata, freshness mismatch, broken
  release provenance, hanging claim backing, and missing debt identity.
- `QC-20260710-006` is now consistently bound to `D-021`.

## Automated QA completed

- Full Python test suite: `83 passed`.
- Seven deterministic seed AnswerCards: `7/7`.
- Golden facts: `20/20`.
- Final lawful routing set: `50/50`.
- Fault injection: `10/10`.
- Frontend unit tests: `9 passed`.
- Frontend lint: passed.
- Frontend production build: passed.
- Local HTTP event-window flow: API v1 / `QT-002` / validated AnswerCard and
  typed navigation returned successfully.
- Desktop browser (`1280x800`): body `scrollWidth == clientWidth`; wide evidence
  table scrolls only inside its container.
- Mobile browser (`390x844`): AnswerCard, side panel, and dossier remain within
  `390px`; chart and timeline scroll only inside their containers.
- Dossier/Copilot roundtrip preserves stock event, episode, date range, lens,
  object scope, and question. Announcement nodes activate with Enter.
- Provenance focus preserves the active answer and selects the matching source.
- Official announcement focus overrides URL title/date; unknown IDs do not render
  a false announcement.
- Visible-page taxonomy scan: zero raw identifiers from the acceptance list.
- Browser console: zero errors and zero warnings.
- Four read-only review rounds completed; all reported correctness and navigation
  findings were fixed and regression-tested.

## Closure

- Isolated branch committed and fast-forwarded into canonical `master`.
- Canonical Python suite, 50-question route eval, 10-case fault matrix, frontend
  tests, lint, and production build all passed after integration.
- Canonical worktree was clean after the final smoke run.

Batch 2 is closed. Batch 3 may start from canonical `master`.
