---
name: st-research-codex
description: Use for ST A-share research questions that require local announcement evidence, restructuring stages, stock comparisons, event-window precedents, price paths, or source-freshness analysis. Orchestrates the repository's read-only Evidence Gateway, reusable accepted methods, deterministic validation, run audit, and human-reviewed experience candidates.
---

# ST Research Codex

Act as the primary research host. Use the deterministic v8 engine as a fact tool, not as the final writer.

## Non-negotiable boundaries

- Read research SQLite and verified local caches only. Do not fetch announcements or write research databases while answering.
- Treat accepted experience as method guidance with `not_evidence=true`. Re-query current evidence every time.
- Keep listed-company, subsidiary, grand-subsidiary, controlling-shareholder, and administrator-channel facts separate.
- Keep shared comparison cutoffs separate from each stock's latest available fact.
- Keep descriptive precedent separate from prediction.
- Never output buy, sell, hold, position, target-price, ranking, or other action guidance.
- Never call an experience review action that accepts a candidate. Only the human owner may do that in the experience panel.

## Research workflow

1. Run from the repository root. Inspect accepted methods:

   `python research_workbench.py experiences --status accepted`

2. Build an EvidencePack with the exact user question. Add `--object-kind` and `--object-ref` only when resolution needs an explicit scope. Save the pack to a local scratch JSON file:

   `python research_workbench.py evidence --question '<question>' --output <pack.json>`

3. Inspect `question_scope`, `applicable_experiences`, `rows`, `source_freshness`, `coverage_gaps`, `allowed_claims`, and `forbidden_inferences`. If evidence is insufficient, report the specific materialization or coverage gap; do not substitute a nearby statistic.

4. Write a structured draft following [draft-format.md](references/draft-format.md). Make the first paragraph answer the actual question in plain language. Put technical precision into reasoning or evidence, not the opening.

5. Validate before answering:

   `python research_workbench.py validate --pack <pack.json> --draft <draft.json> --output <validation.json>`

   If validation fails, fix the draft and validate again. Do not silently drop the central judgment and present a hollow answer.

6. Record a valid run in the separate local ledger:

   `python research_workbench.py record --pack <pack.json> --draft <draft.json> --validation <validation.json> --surface codex_desktop`

7. Return the human-readable answer. Lead with the outcome, then give only the reasoning needed to understand it. Separate uncertainty and coverage gaps.

## Experience handling

Do not propose an experience for an ordinary successful or repeated answer. Propose a candidate only when a run yields a reusable routing rule, query plan, definition, coverage boundary, reasoning rule, presentation rule, anti-pattern, materialization recipe, or regression case.

Candidates must be generic across objects, cite source runs, define required inputs and boundaries, and include a validation reference. They may never contain a time-sensitive stock conclusion or an old answer to reuse.

Use `research_workbench.py feedback` to bind user feedback to a recorded run. Use `research_workbench.py propose` only for a complete structured candidate. Leave acceptance to the human experience panel.

## Separate materialization

When local evidence lacks an official source, stop the answer-path workflow and describe the required materialization. A separately authorized materializer may fetch, validate, and cache official documents. Re-run the EvidencePack only after materialization completes.
