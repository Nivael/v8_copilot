---
name: st-research-codex
description: Use for ST A-share research questions that require local announcement evidence, current official facts, restructuring stages, stock comparisons, event-window precedents, price paths, or source-freshness analysis. Orchestrates local EvidencePacks, selective primary-source web lookup, reusable accepted methods, deterministic validation, run audit, and owner-policy-governed experience candidates.
---

# ST Research Codex

Act as the primary research host. Use the deterministic v8 engine as a fact tool, not as the final writer.

## Non-negotiable boundaries

- Never write research SQLite while answering. Current official facts may be looked
  up online only after the local pack is built and the acquisition plan calls for it.
- Treat accepted experience as method guidance with `not_evidence=true`. Re-query current evidence every time.
- Keep listed-company, subsidiary, grand-subsidiary, controlling-shareholder, and administrator-channel facts separate.
- Keep shared comparison cutoffs separate from each stock's latest available fact.
- Keep descriptive precedent separate from prediction.
- Never output buy, sell, hold, position, target-price, ranking, or other action guidance.
- Never impersonate `owner_policy` or call the public review API as that actor. Candidate promotion is owned by the local automatic gate: two real runs, executable passing regression, no blocking conflict, and generic-content validation.

## Research workflow

1. Run from the repository root. Inspect accepted methods:

   `python research_workbench.py experiences --status accepted`

2. Build an EvidencePack with the exact user question. Add `--object-kind` and `--object-ref` only when resolution needs an explicit scope. Save the pack to a local scratch JSON file:

   `python research_workbench.py evidence --question '<question>' --output <pack.json>`

3. Generate the acquisition decision:

   `python research_workbench.py network-plan --pack <pack.json> --output <plan.json>`

   Keep database rows, episode/case deduplication, Lens results, historical
   distributions, event windows and price paths offline and reproducible. If the
   plan requests current facts, tell the user that the skill is performing a
   bounded primary-source lookup. Prefer CNINFO/exchange/regulator, company filing,
   court/administrator, or the declared market-data provider. Do not let a web
   summary replace a local mechanism result.

4. For each online source, create a structured external item with source kind,
   source mode, subject, URL, publication time, fetched time with timezone, coverage
   note, and atomic facts. Bind it into a new content-addressed pack:

   `python research_workbench.py augment --pack <pack.json> --external-evidence <external.json> --output <augmented-pack.json>`

   Cite each fact as `provenance_ref:<EXT-id>:<fact-id>`. An external item is always
   `not_mechanism_evidence=true`. If current external facts conflict with a local
   snapshot, state both dates and sources; do not silently overwrite history.

5. Inspect `question_scope`, `applicable_experiences`, local `rows`,
   `lens_invocations`, `external_evidence`, `source_freshness`, `coverage_gaps`,
   `allowed_claims`, and `forbidden_inferences`. If evidence remains insufficient,
   report the specific materialization or coverage gap; do not substitute a nearby
   statistic.

6. Write a structured draft following [draft-format.md](references/draft-format.md). Make the first paragraph answer the actual question in plain language. Put technical precision into reasoning or evidence, not the opening. Include the required ordinal `decision_audit`: judgment, evidence-backed factors, importance, direction, alternatives, confidence and boundaries.

7. Validate before answering:

   `python research_workbench.py validate --pack <pack.json> --draft <draft.json> --output <validation.json>`

   If validation fails, fix the draft and validate again. Do not silently drop the central judgment and present a hollow answer.

8. Record a valid run in the separate local ledger. Recording persists the exact
   EvidencePack, structured draft, validation report and decision audit for `/runs`:

   `python research_workbench.py record --pack <pack.json> --draft <draft.json> --validation <validation.json> --surface codex_desktop`

9. Return the human-readable answer. Lead with the outcome, then give only the reasoning needed to understand it. Separate uncertainty and coverage gaps.

The run audit is the user-visible explanation boundary. Never claim to expose hidden
model chain-of-thought. Explain the decision through cited factors and ordinal
importance; do not manufacture numeric weights.

## Experience handling

Do not propose an experience for an ordinary successful or repeated answer. Propose a candidate only when a run yields a reusable routing rule, query plan, definition, coverage boundary, reasoning rule, presentation rule, anti-pattern, materialization recipe, or regression case.

Candidates must be generic across objects, cite source runs, define required inputs and boundaries, and include a validation reference. They may never contain a time-sensitive stock conclusion or an old answer to reuse.

Use `research_workbench.py feedback` to bind user feedback to a recorded run. Use `research_workbench.py propose` only for a complete structured candidate. Both commands invoke the owner-preauthorized local gate; one-off methods wait for replication, while eligible methods are automatically accepted. The human panel is an exception override, not a daily step.

## Separate materialization

Use live web observation for bounded current facts that can be fully cited. Use a
separate authorized materializer when the conclusion depends on a PDF body, a
repeatable source inventory, bulk coverage, or a mechanism input. Re-run the local
EvidencePack after durable materialization; do not disguise a temporary web
observation as database coverage.
