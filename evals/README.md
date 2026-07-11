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
- `question_routing_paraphrases_v0.jsonl` - 20 个改写、未知与边界问题。
- `run_route_eval_50.py` - 30 个 canonical 问题加 20 个改写问题的最终合法路由门。

Run from `v8_copilot/`:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 run_seeds.py
PYTHONDONTWRITEBYTECODE=1 python3 evals/validate_w2_evals.py
PYTHONDONTWRITEBYTECODE=1 python3 evals/run_route_eval.py
PYTHONDONTWRITEBYTECODE=1 python3 evals/run_route_eval_50.py
PYTHONDONTWRITEBYTECODE=1 python3 evals/run_llm_eval.py
```

`validate_w2_evals.py` reads the generated `out/answer_cards.json`; a fresh
worktree must run `run_seeds.py` first.

Passing this gate means the acceptance artifacts are internally consistent, the
deterministic router remains stable, LLM route proposals are adjudicated, and
invalid composer claims cannot enter the public payload. Live provider quality
still requires a separately authorized API-key eval.

## Baseline 2026-07-10

- Routing set: 30 questions.
- Route coverage: query, evidence, checklist, methodology, data debt, lens gap,
  needs review, clarify, refusal/rewrite.
- QuestionCard seed audit: 15 seeds, status counts 7 answerable / 7 needs_data /
  1 needs_review.
- Known seed debt assignment gaps: `QC-20260710-003`, `QC-20260710-005`.
  `QC-20260710-006` is bound to the existing `D-021` debt card.

## Batch 2 closeout acceptance order

Generate the seven deterministic cards before running golden assertions, then run
the fixed routing and failure matrices:

```bash
uv run python run_seeds.py
uv run python evals/validate_w2_evals.py
uv run python evals/run_route_eval_50.py
uv run python evals/run_fault_injection_eval.py
```

The fault matrix is fixed at 10 cases and covers missing/corrupt snapshots,
freshness mismatch, incomplete provenance, hanging claim backing, and missing
data-debt identity.
- Golden assertions: 20 checks against the three original slice AnswerCards.
- Deterministic router v0: 30/30 route matches against
  `question_routing_set_v0.jsonl`.
- Fake LLM parser: 30/30 adjudicated route matches.
- Boundary rewrite set: 20/20 requests route to `refuse_or_rewrite` and receive
  a safe research-question fallback.
- Composer gate: only claim blocks with valid `query_row` or
  `lens_invocation` backing enter the public AnswerCard.
- W1 API contract consumer tests validate `QuestionInterpretation`,
  `RouteDecision`, and `VerifiedClaim` against the frozen v0 schema.

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

## LLM boundary v0

`llm/` contains the two allowed LLM roles:

- `QuestionParser` receives only the question and `ResearchContext`; its route
  proposal is always passed through `deterministic_router_v0.py`.
- `NarrativeComposer` receives a filtered AnswerCard and compact backing
  catalog. Its only output is a Pydantic list of claim blocks.

`OpenAIResponsesProvider` uses Responses API Structured Outputs through
`responses.parse(..., text_format=PydanticModel)`. It does not parse free-text
JSON and does not expose raw streaming deltas. `FakeLLMProvider` exercises the
same schemas without credentials.

After W1 contract merge, run the consumer test from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest evals/test_w1_contract_consumer_v0.py
```

The live smoke test makes two small calls (parser and composer), prints only
route/count/runtime metadata, and never prints the API key or raw database data:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 evals/run_live_openai_smoke.py
```
