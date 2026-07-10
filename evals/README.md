# W2 evals - question routing and stability gates

This directory is owned by W2. It tests whether an arbitrary ST research
question can be routed to a lawful, stable product output before any LLM wording
or UI polish is considered.

W2 does not calculate research facts and does not modify core schemas. Its job
is to define acceptance pressure for W1 and later LLM orchestration:

- `question_routing_set_v0.jsonl` - 30 user-style questions with expected legal
  route, required backing, required provenance, and forbidden claims.
- `question_card_seeds_v0.jsonl` - normalized copy of the current 15
  QuestionCard seeds, used for count/status drift checks.
- `golden_fact_assertions_v0.json` - fact assertions against the current seed
  AnswerCards. These are not standard prose answers.
- `validate_w2_evals.py` - stdlib validator for all W2 artifacts.

Run from `v8_copilot/`:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 evals/validate_w2_evals.py
PYTHONDONTWRITEBYTECODE=1 python3 evals/run_route_eval.py
```

Passing this gate means the acceptance artifacts are internally consistent and
the current three seed cards still expose the facts W2 expects. It does not mean
that a production router or LLM adapter exists yet.

## Baseline 2026-07-10

- Routing set: 30 questions.
- Route coverage: query, evidence, checklist, methodology, data debt, lens gap,
  needs review, clarify, refusal/rewrite.
- QuestionCard seed audit: 15 seeds, status counts 7 answerable / 7 needs_data /
  1 needs_review.
- Known seed debt assignment gaps: `QC-20260710-003`, `QC-20260710-005`,
  `QC-20260710-006`.
- Golden assertions: 20 checks against the three original slice AnswerCards.
- Deterministic router v0: 30/30 route matches against
  `question_routing_set_v0.jsonl`.

## Deterministic Router v0

`deterministic_router_v0.py` is the W2 fallback router. It maps a user question
and object scope to a lawful route only:

- answer query/evidence/checklist/methodology
- data debt
- lens gap
- needs review
- clarify
- refusal/rewrite for trading-advice boundaries

It does not compute facts and does not generate AnswerCards. The route eval
compares predicted route/status/view/lens behavior/data-debt refs/QuestionCard
refs against the 30-question acceptance set.
