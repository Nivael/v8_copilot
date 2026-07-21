# AGENTS.md

This repo had no AGENTS.md/CLAUDE.md despite being the active version as of
2026-07-20 — added as part of ST_invest_quant `.todos/018.md` (cross-repo
documentation cleanup). Keep this short; it's an index, not a duplicate of
the docs it points to.

## What this is

ST Research Codex Workbench — a read-only evidence research core plus a
Codex-hosted local research workbench. Full product definition lives in
`README.md` (spine: QuestionCard → LensInvocation → AnswerCard →
QuestionCard/DataDebt) and `OPERATING_MODEL.md` (the daily three-window
routine: data maintenance / research Q&A / browser audit). Visual/product
design principles are in `DESIGN.md`.

**Read `README.md` first, always.** It is the canonical current-state doc and
is kept up to date; this file is only a pointer.

## Repo state

- No `origin` remote configured — local-only as of 2026-07-20. Confirm with
  the owner before assuming this should be pushed anywhere.
- Uses the same worktree pattern as `ST_invest_quant`: feature work happens
  under `wt/<name>` (see `git worktree list`), not on local `master` directly.
- Sibling directory `v8_copilot_batch2_closeout/` is itself a worktree of a
  `codex/v8-batch2-closeout` branch off this repo, not a separate project.

## Documentation hygiene

- `README.md`, `OPERATING_MODEL.md`, `DESIGN.md`, `SELECTIVE_EVIDENCE_ARCHITECTURE_2026_07_15.md`,
  `V8_NEXT_PRD.md`, and `V8_NEXT_TODO.md`
  are the living reference docs — check for cross-references (`grep -rl
  <filename>`) before assuming any of them is safe to touch or archive.
- Point-in-time handoff/closeout/PRD-recovery notes (named with a date, e.g.
  `*_HANDOFF_YYYY_MM_DD.md`) are working notes, not living docs. Once their
  content is folded into `README.md`/`OPERATING_MODEL.md` and nothing else
  references them, archive them to `_archive/cleanup_YYYYMMDD/` at the
  `st_research/` workspace root with a manifest (see that directory for the
  convention) — do not `rm`. Six such docs were archived on 2026-07-20; see
  `_archive/cleanup_20260720/v8_copilot_dated_docs/MANIFEST.md`.

## Contracts

`contracts/` holds frozen, versioned JSON contracts (`v8_answer_contract_v0`,
`v8_copilot_api_contract_v0`/`v1`, `v8_question_card_contract_v0`,
`v8_query_template_contract_v0`). Treat these like the "contract" concept in
`ST_invest_quant/AGENTS.md` — do not edit without the change being an
explicit, versioned, reversible decision; a new contract version, not an
in-place edit, is the default way to change one.
