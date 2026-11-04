# W2 LLM boundary

This package keeps the LLM on two narrow edges of the deterministic research engine:

- `QuestionParser` sends only a question and the W1 `ResearchContext` payload to the provider. `ResearchRequest.object` remains outside the provider payload and is authoritative during deterministic routing.
- `NarrativeComposer` receives a filtered `AnswerCard`, an explicit backing catalog, and compact evidence summaries. It emits Pydantic `NarrativeDraft` claim blocks only.
- `OpenAIResponsesProvider` uses `client.responses.parse(..., text_format=PydanticModel)` and rejects missing `output_parsed`. It never parses free-text JSON.
- `FakeLLMProvider` runs the same schemas offline for tests and evals.

The composer accepts only claims referring to an entry in its explicit backing
catalog (`query_row`, `lens_invocation`, `provenance_ref`, `data_debt` or `lens_gap`).
A provenance URL alone does not attest the contents of a document. Rejected
claims are retained for internal evaluation but absent from
`CompositionResult.public_payload()`.

Discipline-related statements have an interim literal-fact gate shared with the
Codex draft validator. Only explicitly cited `fact` text carrying a declared
official source kind and an HTTPS SSE/SZSE/CSRC/CNINFO domain can support these
clauses. Titles, coverage notes, URLs alone, or pooled words do not establish an
attribution. Preserve complete facts, including negation and later qualifications;
do not turn a fragment of a qualified fact into an unconditional statement.
The gate covers narrative text, factual headings, claims and decision-audit text.
It can reject valid paraphrases and does not verify extraction against the original
document, resolve aliases, infer chronology, or decide financing eligibility. A
legacy card lacking these facts must retain its gap/degraded result. Partial
tests execute in experience audits while the wider discipline method remains
unverified and ineligible for automatic promotion on that reference.

Local credentials live outside the repository in
`<workspace>/local_secrets/v8_copilot.env` and must never be committed:

```dotenv
OPENAI_API_KEY=your-project-key
V8_OPENAI_MODEL=gpt-5.6-luna
```

`OpenAIResponsesProvider` loads this file without overriding process
environment variables. There is no hard-coded model fallback: missing
`V8_OPENAI_MODEL` produces a configuration error and the safe parser/composer
entry points return deterministic degraded output.
