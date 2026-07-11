# ST Research Copilot API Contract v2

This additive response contract keeps the v0 request and AnswerCard contracts frozen.
It adds two user-facing objects:

- `ResearchNarrative`: a backed direct answer, ordered reasoning steps, uncertainties,
  and observation items.
- `BoundaryRewrite`: an explicit refusal of action advice plus a safe research question.

Every narrative statement carries one or more references to an already validated
query row, Lens invocation, data debt, provenance record, or Lens gap. UI code may
change presentation but must not manufacture additional research claims.

Regenerate `schema.json` with:

```bash
uv run python contracts/v8_copilot_api_contract_v2/export_contract.py
```
