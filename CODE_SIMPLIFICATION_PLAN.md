# 代码解耦与精简方案 — 2026-09-09

范围：`wt/research-performance` 工作区全部 Python 源码（129 个非测试模块，约 46,000 行；测试 10,400 行）。
方法：静态 import 图 + AST 级重复检测 + 逐模块人工阅读。所有"未被引用"的判断都用 `grep` 跨 `tests/`、`evals/`、`contracts/`、`*.md` 复核过。
本文只提建议，未改动任何代码。

## 一句话诊断

这不是一个"写得啰嗦"的代码库，而是一个**没有公共层**的代码库。每个 `pN_*.py` 脚本都是自给自足的：自带 SQLite 连接、自带 digest、自带 env 加载、自带重试、自带 argparse/main。平均每个脚本重复了 40–80 行别处已有的代码，并且这些副本已经开始在语义上分叉。另外有约 7,400 行是**已完成阶段的遗留物或孤岛**，删掉不影响任何运行路径。

按 decoupling → concise → elegant 的顺序，建议分四批做，前三批风险低、可机械验证；第四批（叙事层）需要先补测试。

## 第一批：删除孤岛与遗留（约 7,400 行，零运行时风险）

| 目标 | 行数 | 证据 |
|---|---|---|
| `research_memory_contract.py` + `contracts/v8_research_memory_contract_v0/`（`export_contract.py`、`consumer.py`）+ `tests/test_research_memory_contract.py` | ~3,600 | 全仓库只有这四个文件互相引用，**没有任何生产模块 import 它**。`api_contract_v1.py:18` 的 `QuestionCard` 来自 `question_cards.py:40`，不是这里 —— 名字撞车让它看起来像活的。其中 24 个符号（`canonical_question_intent:165`、`question_card_key:847` 等）连 export/consumer 都不用。若 `schema.json` 是对外发布物，保留 JSON、删生成器。 |
| `p6b_asset_pilot.py`、`p6b_provider_probe.py`、`p6b_market_repricing.py`、`p6b_market_cap_backfill.py`、`p6b_market_map.py` 及其测试 → 归档 | ~3,300 | P6B 已完成（`OPERATING_MODEL.md:114`、五份 `P6B*_RESULT.md`）。唯一活的边是 `valuation_episodes.py:15 → p6b_dry_plan.build_p6b_dry_plan`，所以 `p6b_dry_plan.py` 留下，其余五个按 `AGENTS.md` 的归档约定移到 `_archive/`。 |
| `ui/build_dossier_spike.py` | 458 | 零引用，且 `ROOT = parents[2]`（:19）指向仓库之外，已经是坏的。 |
| `seed_experience_candidates.py` | 59 | 零引用（README/tests/runbook 都不调用）。 |
| `orchestrator.stream_events`（:337-368）、`orchestrator_v1.stream_events_v1`（:428-462）、`api_contract.ResearchStreamEvent`、`api_contract_v1.ResearchStreamEventV1` | ~70 | 只有测试引用；与活着的 `orchestrator_v2.stream_events_v2` 几乎逐字相同。 |
| `experience_contract.utc_now`（:107） | 2 | 零引用。 |

## 第二批：建立公共层，消灭副本（约 700 行，低风险，纯机械）

现状的副本数量（AST 级统计）：

| 原语 | 副本数 | 已有的正确家 |
|---|---|---|
| `_connect_ro` / `_connect_read_only` | 17 个具名 + 88 处内联 `sqlite3.connect(f"file:{...}?mode=ro", uri=True)` | 无 |
| `_canonical` + `_digest` | 20+ | `p8_research.py:126 canonical_json` / `:130 digest` —— **已导出，零调用者**，8 个 p8 脚本自己再写一遍 |
| `_load_env` / `_load_env_file` | 6（其中 6 份逐字节相同） | 无 |
| `_file_sha256` / `_file_digest` | 5 | 无 |
| 重试/限流循环 | 7 | 无 |
| `_prices` / `_benchmarks` | 4 / 5 | `p8_prices.qfq_series` |
| `_board` | 4（逐字节相同） | 无 |
| HTML 页面壳 | 6 | 无 |
| `_parse_args` + `main` + JSON 落盘 | 26 | 9 个模块用 `data_refresh.atomic_write_json`，其余 42 处手写 `mkdir + write_text` |

建议新建三个小模块（合计不超过 150 行）：

`db.py` —— `connect_ro(path)`、`connect_rw(path)`，统一 `row_factory=sqlite3.Row`。目前 `market_factors.py:133`、`market_context.py:212`、`valuation_episodes.py:562`、`p7_daily.py:474`、`p7_announcements.py:433`、`p7_review.py:173` 六处写连接**没有**设 `row_factory`，读代码被迫用位置索引；`pragma foreign_keys=on` 全仓库只在 `market_activity.py:316` 出现一次。

`providers/retry.py` —— 一个 `with_retry(fn, *, attempts, backoff)`。现有七份重试逻辑互相不一致，这已经是 bug 而非风格问题：
- `p8_backfill_market_activity.py:44` 用 `backoff * 2**attempt`，其余用 `2**(attempt-1)`，首次等待时间是别处的两倍；
- `p8_qfq_backfill.py:91` 和 `p8_holder_history.py:97` 失败时**返回哨兵值而不抛异常**，上层静默吞掉；
- `p8_grid_price_coverage.py:88` 固定延迟、成功也 sleep；
- 限流异常的文本匹配规则在 `p7_provider_probe.py:86` 与 `p8_grid_price_coverage.py:100` 两处各写一套。

`common.py`（或 `p8/_common.py`）—— `load_provider_env`、`file_digest`、`board`、`benchmarks`，并 re-export `canonical_json`/`digest`/`atomic_write_json`。合并时必须**显式选一个语义**：
- `_file_digest` 缺文件时，`p8_backtest_v2_dry_plan.py:51` 返回 `""`，其余四处抛 `FileNotFoundError`。空字符串的 digest 会静默进入 provenance 记录。建议统一为抛异常，需要容忍的调用方传 `missing_ok=True`。
- `_benchmarks` 有三种返回形状：`p8_backtest_v2.py:526` 返回 `dict`（缺 key 报错），`p8_backtest.py`/`p8_portfolio.py`/`p8_returns.py` 返回 `defaultdict`（缺 key 静默给 `{}`），`p8_materialize_activity.py:73` 返回扁平 `(id, date) -> float`。
- `p8_backfill_market_activity.py:19` 的 `_load_env` **没有 key 白名单**，会把 env 文件里任何 `KEY=VALUE`（包括 `PATH=`、`HTTPS_PROXY=`）注入进程；其余五份限定 `{TUSHARE_TOKEN, TUSHARE_HTTP_URL}`。

`_prices` 的情况要单独决策：`p8_backtest_v2.py:509` 走 `p8_prices.qfq_series`（含 overlay 合并，也是上一轮性能 PR 优化过的流式读取器）；`p8_backtest.py:73`、`p8_portfolio.py:75`、`p8_returns.py:115` 各自对 base DB 裸写 SQL，看不到 `p8_qfq_backfill.py` 的 overlay。`p8_daily.py` 目前对这三个阶段也不传 overlay，所以这可能是有意为之——但如果是有意的，应该写成一个显式参数 `overlay_database=None` 走同一个读取器，而不是三份不同的 SQL。统一后这三个路径也自动拿到性能提升。改动会改变 digest，需要像 `benchmarks/grid_inventory.py` 那样做一次摘要对照。

## 第三批：修正分层错误（约 250 行，低–中风险）

这几处是真正的"耦合"问题——依赖方向反了，而不只是重复。

**生产代码依赖评测代码。** `core_router.py:10` 和 `llm/parser.py:10` 都 `from evals.deterministic_router_v0 import route_question`。这条链一路传到 `orchestrator → llm_adapter → api`，即 HTTP API 依赖 `evals/`。把 `evals/deterministic_router_v0.py`（438 行，它其实就是路由器本体）移到 `routing/`，让 evals 反过来 import 生产代码。约 10 处 import 修改。

**LLM 边界层依赖 2,530 行的答案引擎。** `llm/boundaries.py` 一共 16 行，为了拿一个字符串列表 `FORBIDDEN_WORDING` 而 import 整个 `answer_engine`（连带 sqlite 与六个领域模块）。把常量搬进 `llm/boundaries.py`，让 `answer_engine` 反向引用。零净行数，但切断 `llm/ → answer_engine` 这条边。`evidence_gateway.py:409` 在函数体内延迟 import `llm.boundaries`，正是在绕这个环。

**`freshness_manifest.py:20` 从 `answer_engine` 拿四个 DB 路径。** 每次新鲜度检查都要加载 pandas 重模块。改为参数传入（或从 `settings` 取），534 行模块立刻可单测。

**`answer_engine.py` 在 296 行处天然可切。** 82–295 是 `AnswerCard` 等数据类与 `validate/to_dict/to_markdown`；474–2530 是 14 个 `card_*` 构建器。把前者拆成 `answer_card.py`，`llm/composer.py`、`p6b_market_repricing.py`、`evals/run_fault_injection_eval.py` 就只需 import 一个 215 行的契约模块，而不是在 import 时打开 sqlite 的引擎。`card_stock_research_overview`（1395–1890，496 行）是单个最大函数，可作为后续按领域拆分的第一刀。

**三个 orchestrator 不是三个版本，是一条流水线。** `orchestrate_with_card → enrich_response_v1 → enrich_response_v2` 严格线性，没有任何开关。`ResearchResponseV2` 是 `V1` 的严格超集（多 `narrative`、`boundary_rewrite` 两个字段），V1 从未被序列化给任何客户端。这条链在 `api.py:114-120`、`api.py:123-130`、`evidence_gateway.py:172-177` 三处逐字重复。建议：
1. 收拢为一个 `pipeline.answer(request)`，删三处重复（~25 行），同时 `evidence_gateway` 不再需要 import 两个 orchestrator；
2. 把 70 行的 `orchestrator_v2.py` 折进 `enrich_response_v1`，直接返回 V2，删 `ResearchResponseV1`（注意 `api_contract_v2.py:77` 的 `narrative_backing_exists` 校验要挪到注入 narrative 之后）；
3. `llm_adapter.py` 162 行是围绕一个函数的四层包装（`orchestrate_with_provider` / `_result` / `orchestrate_optional_llm` / `_result`），`LLMOrchestrationResult` 这个两字段载体存在的唯一原因是 `ResearchResponse` 没有 `narrative` 字段——而 V2 有。合并后可砍掉一半。

**`experience_governance.py` 一个模块承担四层。** 策略（`detect_experience_conflicts:198`）、自己的 SQLite 持有者（`ExperienceGovernanceRepository:247`，绕开 `research_repository`）、子进程执行器（`PytestRegressionExecutor:310`，shell 出去跑 pytest）、CLI（`main:435`）。其余 `experience_*` 六个模块分层其实很干净（contract → repository → distiller/review → auto_accept → backfill，无环），只有它破了规矩。把 Repository 并入 `research_repository.py`，Executor 放到 `RegressionExecutor` Protocol（:118）后面单独成文件。

**`P8Run.run_kind` 是硬编码的 16 项 `Literal`（`p8_research.py:97-104`）。** 核心模块点名每一个叶子脚本（`"p8_backtest_v2_dry_plan"` 直接写在核心里），每加一个脚本就要改核心。换成脚本注册制，配启动期校验。这是 p8 层单点最大的耦合。

## 第四批：统一脚本形态（约 270 行，中风险）

26 个 p8 脚本已经有 90% 一致的形态：`_parse_args → main → build_* → persist → 可选 --output-json → print(summary) → return 0`（对照 `p8_funnel.py:549`、`p8_references.py:1020`、`p8_walk_forward_basket.py:588`，几乎逐字相同）。剩下 10% 的偏差全是无意的：`p8_grid_price_coverage.py:121`、`p8_volume_grid.py:313` 把 argparse 内联进 `main`；六个脚本没有 `_parse_args`；输出落盘一半用 `atomic_write_json`、一半手写。

把这个形态显式化为 `run(settings, **opts) -> Result` + `build_parser()` + 通用 `main()` 之后，`p8_daily.py` 不必再重新声明 14 个子脚本的全部 20 个 `add_argument`（:46-65）、不必手工穿 5–8 个路径参数（:70-160）、不必自带 `_write`（:37-41），`:164` 处的 `chip.model_dump() if hasattr(chip, "model_dump")` 多态补丁也随之消失。192 行降到约 70 行，编排本身变成一张阶段表。

## 明确不建议做的

- **不要删 `p8_backtest.py`（v1）。** `p8_publish.py:15` 的 `REQUIRED_KINDS` 要求 `"backtest"` 这个 run_kind；v1 与 v2 写的是不同的 run_kind、喂不同的 gate。合并意味着改发布 manifest 契约，不是重构。
- **不要归档 P7。** `P7_DAILY_RUNBOOK.md` 仍是每日流程，`P8_DAILY_RUNBOOK.md:7` 明确要求先跑完 P7。P8 对 P7 的真实依赖面很小——`p7_daily.load_valuation_stage_map`（:434-465，32 行）被 4 个 p8 模块用；`p7_announcements.classify_announcement/load_announcements` 被 `p8_volume_grid` 用。可以把这两块提到一个小的 `stage_map.py`，切断 p8 → p7 八条边中的四条，但 P7 本身留着。
- **不要删 `p8_dry_plan.py`。** 它没有 import 方也没有 runbook 提到，看起来像孤儿，但它生产的 `p8_0_dry_plan_v1.json` 被 `p8_daily.py:50` 通过 `--dry-plan-json` 当外部文件消费。该修的是 runbook 漏写了这一步。
- **`narrative_builder.py`（1,182 行）暂缓。** 九个手写中文叙事渲染器，`_stock_overview_narrative` 一个函数 370 行，逻辑核心是对 `记录类型` 魔法列名的反复 `next((row for row in rows if ...), None)` 查找（:196-230 连续 8 次）。它可以数据驱动化并砍掉 500–600 行，但输出是面向用户的中文文案、只有 2 个测试覆盖。先给九条路由补 golden 测试，再动。
- **provider fetch 不需要重写。** `fetch_daily_basic` 等在 7 个模块里"出现"，但只有 `data_refresh.py:255 TushareHttpClient` 一份实现，其余全是 `Protocol` 桩（DI 接缝）。这部分已经是对的。
- **`settings.py` 不是 god module。** 120 行、28 个路径常量、只有一个行为值 `P7_FORWARD_SHADOW_START`（:98）。52 个 importer 里大多数只拿它当默认值，`data_refresh`、`market_*`、`valuation_episodes`、全部 `p7_*` 一次都没 import 它。真正硬耦合的只有 `freshness_manifest.py` 和 `stock_resolver.py`。

## 预期收益

前三批合计可删约 8,300 行（非测试代码的 18%），全部可用现有 406 项测试 + digest 对照验证，不改任何对外契约。更重要的是切断四条方向错误的依赖边（evals→prod、llm→answer_engine、freshness→answer_engine、governance 私有 sqlite），以及把 20 处 digest、17 处连接、7 处重试收成各一处——后者本身就修掉了三个潜在 bug（env 无白名单、重试哨兵吞异常、digest 缺文件返回空串）。

建议执行顺序就是批次顺序：先删（不引入任何新抽象），再收公共层（此时每个副本的差异都已经暴露，选语义时有依据），再修分层，最后统一形态。每批一个 PR，沿用 `RESEARCH_PERFORMANCE.md` 的对照方法。
