# Validated research draft format

Create JSON with one `narrative` object:

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
  }
}
```

Allowed backing kinds are `query_row`, `lens_invocation`, `provenance_ref`, `data_debt`, and `lens_gap`. Every reference must exist in `validation_catalog`.

Rules:

- Give the conclusion before the data plumbing.
- Use only numbers and dates contained in the statement's cited backing.
- A statement may cite multiple backings when it joins facts.
- Put source coverage gaps in `uncertainties`; do not turn them into factual absence.
- For comparisons, make one coherent single-dimension judgment when supported, then explain entity and cutoff boundaries.
- `basis_note` is explanatory metadata; it must not add facts.
