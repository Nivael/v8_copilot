# W1 Batch 2 Core/API handoff

日期：2026-07-11
基线：`3f3feb7`
分支：`codex/v8-w1-api-contract-v0`
状态：W1 实现与自测通过，等待 W0 集成

## 契约冻结产物

- `api_contract.py`
- `contracts/v8_copilot_api_contract_v0/schema.json`
- `contracts/v8_copilot_api_contract_v0/manifest.json`
- `contracts/v8_copilot_api_contract_v0/fixtures/`

新增契约不修改 `v8_answer_contract_v0`。`ResearchResponse.answer_card` 通过外部 `$ref`
继续指向旧 AnswerCard schema。

公开对象：ResearchRequest、QuestionInterpretation、RouteDecision、ResearchResponse、
StockDossierPayload、ResearchStreamEvent。

## Core/API 产物

- FastAPI 五个端点；
- 确定性 interpretation + final router；
- 现有 AnswerCard executor 编排；
- 已登记 data debt 通用出卡；
- 未覆盖问题稳定降级；
- 只读 stock dossier payload；
- 只输出验证领域事件的 NDJSON stream；
- `V8_DATA_ROOT` worktree 运行配置。

## 验证结果

```bash
V8_DATA_ROOT=<data-root> uv run pytest tests evals/test_deterministic_router_v0.py -q
V8_DATA_ROOT=<data-root> uv run python run_seeds.py
V8_DATA_ROOT=<data-root> uv run python -B evals/validate_w2_evals.py
V8_DATA_ROOT=<data-root> uv run python run_api.py
```

结果：

- 全量 Python：56 passed；
- API/contract 聚焦：30 passed；
- W2 路由：30/30；
- W2 golden facts：20/20；
- 七张 seed AnswerCard：7/7；
- 真实 HTTP：health/route/stream/dossier 全部 200；
- NDJSON 无 token/delta 事件；
- 603398 dossier：1982 prices / 162 events / 5 lanes / 3 lenses；
- 原始 SQLite、episode index、release library mtime 不变。

## 合并顺序

W0 应先合入 API contract commit，让 W2/W3 pin schema 和 fixtures；消费者测试通过后，
再合入 Core/API commit。W2/W3 不应复制研究计算或修改 W1 schema。

## 已知边界

- W1 尚未注入 W2 LLM adapter，`auto|required` 会返回确定性结果并标 degraded；
- 尚无 executor 的合法 route 返回 `answer_card=null` + gap/candidate，不伪造卡；
- `core_router.py` 当前封装已冻结的 `evals/deterministic_router_v0.py`；
- W2 的 QC-006 seed ledger 仍标 debt assignment gap，但 API 已根据既有 D-021 决策补入
  `D-021`，该账务口径由 W0/W2 在集成时同步；
- W3 consumer test 尚未在本分支执行，需在 contract commit 合入后完成。
