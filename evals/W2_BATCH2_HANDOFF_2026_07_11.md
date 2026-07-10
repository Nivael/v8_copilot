# W2 Batch 2 LLM/Eval handoff

Date: 2026-07-11
Baseline: `3f3feb7`
Status: implementation and offline acceptance complete; live model quality acceptance blocked by API quota

## Delivered

- `llm/parser.py`: question interpretation proposal, W1 `ResearchContext` input boundary,
  authoritative object preservation, deterministic route adjudication, compliant rewrite fallback.
- `llm/composer.py`: filtered AnswerCard input, explicit backing catalog, numeric/backing/trading-language
  claim gates, safe deterministic fallback.
- `llm/providers.py`: `FakeLLMProvider` and lazy `OpenAIResponsesProvider` using Responses API
  Pydantic Structured Outputs. No free-text JSON parsing and no raw token streaming.
- `llm/config.py`: external secret loading and required `V8_OPENAI_MODEL`; no model fallback is hard-coded.
- `evals/rewrite_routing_set_v0.jsonl`: 20 trading-style requests for compliant boundary routing.
- W1 contract consumers for `QuestionInterpretation`, `RouteDecision`, and `VerifiedClaim`.

## Data boundary

- Parser provider payload contains only `question` and W1 `ResearchContext`.
- `ResearchRequest.object` is not sent to the provider and remains authoritative in deterministic routing.
- Composer provider payload contains only a filtered AnswerCard, backing catalog, and compact evidence summaries.
- Raw SQLite data, full announcements, episode index, and full lens library are not sent.
- Public output contains only claims that passed backing and wording validation.

## Acceptance results

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests \
  evals/test_deterministic_router_v0.py \
  evals/test_llm_pipeline_v0.py \
  evals/test_rewrite_routing_v0.py \
  evals/test_w1_contract_consumer_v0.py \
  -p no:cacheprovider -o addopts=''

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python evals/validate_w2_evals.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python evals/run_llm_eval.py
```

Results:

- Python: 47 passed.
- Original routing set: 30/30.
- Boundary rewrite set: 20/20.
- Combined legal routing gate: 50/50.
- Golden facts: 20/20.
- Seed AnswerCards through composer backing gate: 7/7.
- W1 frozen contract consumer definitions: 3/3.
- Missing model, missing key, timeout/provider error, and schema error paths preserve deterministic output.

## Live OpenAI status

The two-call live smoke reached OpenAI but received `429 insufficient_quota` before a model response.
The same real failure was rerun through safe entry points and returned:

- deterministic `answer_checklist` routing;
- `llm_used=false`;
- no unvalidated claims;
- explicit degraded reasons;
- no exception or raw provider output in the product payload.

Therefore provider connectivity and degradation behavior are exercised, but Luna response quality is not yet
accepted. After API billing/quota is enabled, rerun:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python evals/run_live_openai_smoke.py
```

Live acceptance requires `live_validated=true` and at least one validated composer claim.

## W0 merge notes

1. Merge W1 contract commit `2c2784c` first. The consumer test then uses the default
   `contracts/v8_copilot_api_contract_v0/` path.
2. Run the W2 consumer tests against the merged contract. W2 does not modify the W1 schema.
3. Merge W1 Core/API commit `e1753bd`.
4. Apply W2 changes and perform API injection/integration verification.
5. Keep the local secret file outside the repository. Do not copy it into fixtures, docs, or UI config.
6. The existing seed ledger still reports known debt assignment gaps for QC-003, QC-005, and QC-006;
   W1's D-021 handling should be reconciled by W0 during integration.
