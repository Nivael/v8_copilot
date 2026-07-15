# Validated research draft format

Create JSON with a `narrative` and a structured `decision_audit`:

```json
{
  "narrative": {
    "direct_answer": {
      "text": "Direct, plain-language answer.",
      "backing": [{"kind": "query_row", "ref": "row-id"}]
    },
    "reasoning_steps": [
      {
        "title": "Short reason",
        "text": "How the evidence supports the answer.",
        "backing": [{"kind": "query_row", "ref": "row-id"}]
      }
    ],
    "uncertainties": [
      {
        "text": "Specific fact, source, or time boundary that remains unknown.",
        "backing": [{"kind": "lens_gap", "ref": "gap-id"}]
      }
    ],
    "watch_items": [],
    "basis_note": "One sentence describing the evidence basis."
  },
  "decision_audit": {
    "weighting_method": "ordinal_evidence_weighting_v0",
    "judgment": "The exact judgment made in the answer.",
    "judgment_backing": [{"kind": "query_row", "ref": "row-id"}],
    "confidence": "medium",
    "factors": [
      {
        "factor_id": "current_stage",
        "label": "Current disclosed stage",
        "direction": "supports",
        "importance": "decisive",
        "rationale": "Why this factor controls or limits the judgment.",
        "backing": [{"kind": "query_row", "ref": "row-id"}]
      }
    ],
    "alternatives": [
      {
        "label": "A competing interpretation",
        "disposition": "rejected",
        "reason": "Why the evidence does not support it.",
        "backing": [{"kind": "lens_gap", "ref": "gap-id"}]
      }
    ],
    "not_hidden_chain_of_thought": true
  }
}
```

Allowed backing kinds are `query_row`, `lens_invocation`, `provenance_ref`, `data_debt`, and `lens_gap`. Every reference must exist in `validation_catalog`.

For an external fact, use `{"kind":"provenance_ref","ref":"<EXT-id>:<fact-id>"}`.
External facts may establish current published facts only; they cannot back a local
historical distribution, Lens result, episode calculation, or price-path calculation.

Rules:

- Give the conclusion before the data plumbing.
- Use only numbers and dates contained in the statement's cited backing.
- A statement may cite multiple backings when it joins facts.
- Put source coverage gaps in `uncertainties`; do not turn them into factual absence.
- For comparisons, make one coherent single-dimension judgment when supported, then explain entity and cutoff boundaries.
- `basis_note` is explanatory metadata; it must not add facts.
- `decision_audit` is mandatory for newly recorded Codex runs. It is a concise,
  evidence-backed audit rationale, not hidden chain-of-thought.
- Weighting is ordinal only: `decisive`, `high`, `medium`, or `low`. Do not invent
  percentages or pseudo-probabilities.
- Every judgment, factor, and alternative must cite a real EvidencePack backing.
