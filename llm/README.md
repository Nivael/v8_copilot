# W2 LLM boundary

This package keeps the LLM on two narrow edges of the deterministic research engine:

- `QuestionParser` sends only a question and the W1 `ResearchContext` payload to the provider. `ResearchRequest.object` remains outside the provider payload and is authoritative during deterministic routing.
- `NarrativeComposer` receives a filtered `AnswerCard`, an explicit backing catalog, and compact evidence summaries. It emits Pydantic `NarrativeDraft` claim blocks only.
- `OpenAIResponsesProvider` uses `client.responses.parse(..., text_format=PydanticModel)` and rejects missing `output_parsed`. It never parses free-text JSON.
- `FakeLLMProvider` runs the same schemas offline for tests and evals.

The composer accepts only claims backed by an existing `query_row` or `lens_invocation`. Rejected claims are retained for internal evaluation but are absent from `CompositionResult.public_payload()`.

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
