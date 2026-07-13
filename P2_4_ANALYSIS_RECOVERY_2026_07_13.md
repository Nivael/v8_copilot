# P2.4 Analysis Recovery

Status: implementation, W0 closeout review, and isolated-branch QA are complete; canonical
integration and post-merge browser acceptance remain.

## Why this recovery exists

Batch 2 could return lawful fallback objects, but several ordinary research questions still
failed as products: announcement questions repeated the title, restructuring questions used
cohort timing without locating the current case, multi-stock questions fell back, and the LLM
generated audit claims without controlling the main narrative shown in the UI.

P2.4 treats the following questions as hard acceptance cases:

- What did the latest ST Nandu announcement actually say?
- How far has Mubang's restructuring process progressed, and what historically follows?
- How do Mubang and ST Nandu compare on the same evidence dimensions?
- Provide a multi-dimensional analysis of ST Wingtech.

## Implemented

- The Answer path reads announcement bodies only from read-only SQLite or an already validated
  local cache. Every Answer request sets `allow_network=False`; it neither downloads PDFs nor
  writes the research database or cache.
- Network PDF retrieval is confined to a separate materialization step. That step may fetch only
  validated CNINFO URLs, applies size/page/text bounds, and writes the extracted result to the
  local cache for later read-only Answer requests.
- Announcement AnswerCards include selected body evidence instead of treating title/date as the
  announcement's content.
- Restructuring progress separates the listed company from subsidiaries and controlling
  shareholders. The current public milestone is presented separately from two descriptive
  historical distributions: the next official announcement and the next distinct restructuring
  stage.
- Historical restructuring transitions use one `restructuring_path` episode as one case. Repeated
  disclosures at the same stage are deduplicated within the episode by selecting the latest
  same-stage disclosure; cases without an observed later announcement/stage remain in the
  denominator as right-censored observations instead of being silently dropped.
- Pair comparison resolves both stocks and uses a common announcement cutoff. Each row also keeps
  the stock's own latest announcement so newer asymmetric information remains visible.
- Generic stock analysis loads status, official announcements, classified episodes, prices,
  shareholder-count coverage, and equity coverage. A freshness boundary states whether each
  source reaches the ST start date.
- OpenAI Structured Outputs now produces the public `ResearchNarrative`, not only hidden claim
  blocks. Every statement must cite an existing query row or Lens invocation; unsupported
  numbers, forbidden wording, and missing backing are rejected statement by statement.
- The UI labels the answer as `LLM 综合分析` or `本地规则分析`. The deterministic narrative remains
  available when OpenAI is missing or rejected.

## Boundaries retained

- Research SQLite databases remain read-only. The Answer path is also cache-read-only.
- The separate materialization step is the only announcement-body write path; it writes the local
  cache and does not alter research data or the frozen Lens library.
- Historical transition shares remain descriptive queries, not prediction probabilities.
- Pair comparison does not produce a ranking or action recommendation.
- Frozen AnswerCard, API v0/v1/v2, QuestionCard, Research Memory, and QueryTemplate v0 contract
  artifacts are unchanged.
- P3.2 Research Memory storage/API remains frozen.

## Closeout review status

- W0 reviewed the API/stream path, deterministic routing, announcement-body read boundary,
  restructuring case construction, per-stock freshness, LLM statement validation, and UI analysis
  mode. No blocking correctness issue was found; frozen contracts remained out of scope and have
  zero diff.
- Added regression coverage for a stock with no episode (`000005`): its per-stock analysis boundary
  must keep `事件索引截至` empty and `事件覆盖ST后=false`, rather than inheriting the global episode
  index date.
- Current W0 rerun passed `uv lock --check`, the full Python suite, all 6 P2.4 focused tests, 7 seed
  AnswerCards, the 30-row question and 20-row rewrite validation sets, final routing 50/50, 20
  golden facts, fault injection 10/10, and real-question answerability 14/14.
- Frontend QA passed 5 test files / 23 tests, lint, and production build. `git diff --check`, frozen
  contract diff, secret scan, repository-document path scan, and trading-wording leakage review
  also passed.
- These are fresh W0 results from the isolated P2.4 worktree; earlier worker results were not used
  as the closeout verdict. Canonical rebuild/smoke and four-question live browser acceptance remain
  post-merge gates.
