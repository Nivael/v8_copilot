# v8_copilot — ST Research Copilot Core/API

独立、只读的证据化问答引擎。v8 消费层第一条腿（"回答问题"）的可运行骨架。
产品定义由 D-052 和统一版 v8 PRD 管理；本仓只保留可执行实现、版本化契约和验收资产。

## 脊梁（D-052 修正案）

最小闭环 = **QuestionCard → LensInvocation → AnswerCard → QuestionCard/DataDebt**。
lens invocation 才是 v8 的脊梁，AnswerCard 不是最终抽象。每张答案卡必须显式记录它
消费了哪些 **v7.4 release record**（`shared_data/v7/release_library_v1/`，9 条真实 record）、
各自 kind、贡献了哪个 answer section；**无可用 lens → 显式 lens_gap → 沉淀 question_card/data_debt**，
不得用 sqlite+手写逻辑冒充 lens 消费。

## 是什么

把 v7 学到的"证据菜单三段式"落成参数化的 answer-card 生成器：任何答案 =
**lens_invocations（脊梁）+ query/checklist 主体 + data_debt 缺口行 + 固定 caveat 块**，
每张卡必带 出处 / as_of / 样本范围 / 证据等级 / 缺口 / **lens_invocations 或 lens_gap /
库版本 / episode 版本 / 数据快照 as_of**。覆盖 D-050 五视图里的 query / checklist /
methodology / data_debt；evidence 视图已接 release_library_v1（RL-A-003 等）。

## 红线（硬编在 AnswerCard.validate）

- 不输出买卖/持有/仓位/交易信号/排序权重措辞——forbidden-wording guard 会拒绝出卡。
- data_debt 行必须挂既有债台账 id（不另起第二本账）。
- methodology/data_debt 视图不得携带 evidence/effect 结论式证据等级。
- 输出恒为历史路径描述，不表示可交易/可预测/可复现。

## 运行环境

W1 使用独立 `uv` 环境，Python 版本和依赖由 `.python-version`、`pyproject.toml`、
`uv.lock` 固定。不要再使用系统 `python3` 直接运行。

```bash
uv sync --group dev
uv run pytest
uv run python run_seeds.py
uv run python run_api.py
```

`run_api.py` 只绑定 `127.0.0.1`，默认端口 `8765`。canonical 目录布局无需额外配置；
若独立 worktree 不与 `shared_data/` 同级，使用 `V8_DATA_ROOT` 指向包含
`shared_data/` 的数据根目录。

## Batch 2 API

公开接口：

- `GET /api/v1/health`
- `POST /api/v1/route`
- `POST /api/v1/answers`
- `POST /api/v1/answers/stream`
- `GET /api/v1/stocks/{symbol}/dossier`

`/answers/stream` 使用 NDJSON，只发送完整、已验证的领域事件：`accepted`、
`interpreted`、`routed`、`answer_card`、`claim_block`、`degraded`、`completed`、
`error`。不转发模型 token delta。

`llm_adapter.py` 提供 Fake provider、OpenAI Responses Structured Outputs adapter、
问题解释和 claim backing 校验。确定性 router 始终拥有最终路由；LLM 不接数据库，
只接收问题/ResearchContext 或过滤后的 AnswerCard。

实时 OpenAI 模式要求本地环境提供 `OPENAI_API_KEY`、`V8_OPENAI_MODEL`，并在本地
虚拟环境安装 `openai>=2,<3`。未配置、超时或输出校验失败时仍返回确定性结果；
`llm_mode=off` 是纯确定性模式。

React 主面板和个股面板位于 `web/`：

```bash
cd web
npm install
npm run build
cd ..
uv run python run_api.py
```

打开 `http://127.0.0.1:8765`。开发模式可运行 `npm run dev`，Vite 将 `/api` 代理到
本地 FastAPI。个股节点通过 ResearchContext URL 回到主面板继续提问，聊天不持久化。

## 契约与文件

- `lens_binding.py` — **脊梁**：LensRegistry（只读加载 pinned v1 库）+ candidate_lenses（按主题标签/cluster 精确匹配）+ LensInvocation + LensGap。
- `answer_engine.py` — AnswerCard、AnalysisClaim/backing、只读数据访问和 card builders。
- `contracts/v8_answer_contract_v0/` — W1 单写、W2/W3/LLM 只读的 JSON 契约。
- `contracts/v8_copilot_api_contract_v0/` — Batch 2 API schema、manifest 和固定 fixtures。
- `api_contract.py` — ResearchRequest、RouteDecision、ResearchResponse、dossier 和 stream 类型。
- `core_router.py` / `orchestrator.py` — 确定性解释、最终路由和 AnswerCard 执行编排。
- `api.py` / `run_api.py` — FastAPI 接口和本机启动入口。
- `dossier_service.py` — 只读个股价格、状态、事件、时间线和 lens payload。
- `llm_adapter.py` — Structured Outputs parser/composer、Fake provider 和 backing 门。
- `web/` — React/Vite 主面板、个股面板和 ResearchContext 联动。
- `tests/` — validator、release reader 与真实数据集成测试。
- `run_seeds.py` — 生成七张 P1 seed card，产出 `out/answer_cards.{json,md}`。
- `out/` — 生成的答案卡（JSON + 人话 Markdown）。

## 治理

独立消费者：不 import forum_signals / v7 内部模块；只读
`shared_data/v5/.../st_stocks_v5_backup.sqlite3`（ro URI）+ M6 episode index。
本地原型，生成物只进 `out/`。

## 已验证

七张种子卡覆盖：

- query：重整节点 4/10/14 天、ST 两周分布、单票 ST 生命周期；
- checklist：沐邦观察窗口；
- evidence：RL-A-001、RL-A-002 的 N/effect digest/反例/wording；
- data_debt：D-051A 省份映射稳定出口；
- lens_gap：重整时点、两周横截面、ST 原因绑定等缺口。

所有卡必须同时通过 `AnswerCard.validate()` 和
`contracts/v8_answer_contract_v0/schema.json`。

Batch 2 W1 另验证：

- 六个 API 公开对象与提交的 JSON Schema 零漂移；
- 原有 30 题 deterministic route 和 20 个 golden fact 继续通过；
- 真实 HTTP 进程可返回 health、route、NDJSON 和 603398 dossier；
- dossier 读取 1982 个价格点、162 个去重事件、5 条时间线和 3 条 lens 摘要；
- API 和 dossier 不写研究数据库。

## Batch 2 边界

W1 单写共享契约和 Core/API。任何新事实字段先进入确定性 Core 和 AnswerCard，再暴露
给 LLM/UI；W2/W3 不直接修改 `contracts/`。问题卡和知识晋升本批次只生成候选，不持久化。
