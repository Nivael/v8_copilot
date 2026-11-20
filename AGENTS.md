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

- `origin` is `github.com/Nivael/v8_copilot`; important changes should be
  pushed through scoped feature branches and draft PRs. The current PR stack
  and accepted data snapshots are summarized in the workspace-root
  `AGENTS.md`, `README.md`, and the relevant result note.
- Uses the same worktree pattern as `ST_invest_quant`: feature work happens
  under `wt/<name>` (see `git worktree list`), not on local `master` directly.
- Retained worktrees are traceability artifacts; do not delete them without
  owner confirmation.

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

最新期间复盘已发布：海钦旧处罚/新监管与现金、洲际补认/独立审计、中路798万元未收与司法、京化重述/非经常性损益分别核。6条问题链、四家同窗横向比较；期初仍126/150。见 [本轮结果](ST_TWENTYFIRST_PERIOD_FOLLOWUP_RESULT_2026_11_20.md)。

最新期初补证已发布：福成双审计、文峰部分回收和年份冲突、际华告知依据及审计分类、喜临门担保转占款与股东预重整分别核。覆盖130/150、剩20家。见 [本轮结果](ST_INITIAL_TWENTYSECOND_FOUR_RESULT_2026_11_20.md)。

最新期间复盘已发布：福成程序通过与鉴证、文峰新增本金/旧诉讼/新立案、际华最终处罚/非经常性收益及三项衔接差异、喜临门担保转占款分别核。期初仍130/150，见 [本轮结果](ST_TWENTYSECOND_PERIOD_FOLLOWUP_RESULT_2026_11_20.md)。

最新期初补证已发布：联翔双无保留与财务门槛、东珠更正与鉴证延期、东时旧审计消除与部分申请、亚士负净资产与受限资金分别核。覆盖134/150、剩16家。见 [本轮结果](ST_INITIAL_TWENTYTHIRD_FOUR_RESULT_2026_11_20.md)。
