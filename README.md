# v8_copilot — ST Research Codex Workbench

独立、只读的证据研究内核，以及由 Codex 主持的本地研究工作台。
产品定义由 D-052 和统一版 v8 PRD 管理；本仓只保留可执行实现、版本化契约和验收资产。

主交互入口是项目级 `st-research-codex` skill。旧问答 API 和 Web composer 保留为兼容、
fallback 与回归面，不再承担默认研究主持人职责。

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

Codex 工作台增量接口：

- `POST /api/v1/research/evidence` — 只读生成 EvidencePack；
- `GET /api/v1/research/evidence/{pack_id}` — 读取已随运行持久化的完整 EvidencePack；
- `POST /api/v1/research/validate` — 校验 Codex 结构化研究稿；
- `POST/GET /api/v1/research/runs` 与 `GET /api/v1/research/runs/{run_id}` — 写入或读取独立运行审计库；
- `POST /api/v1/research/runs/{run_id}/feedback` — 绑定反馈并按新颖性生成经验候选；
- `POST /api/v1/experiences/candidates` 与 `GET /api/v1/experiences` — 候选写入与经验检索；
- `POST /api/v1/experiences/{experience_id}/review` — 人工审阅状态转换。

Evidence Gateway 只读研究 SQLite 和本地材料化缓存，不联网、不写研究数据库。运行审计与
经验库分别使用 local-only SQLite；两者均不是研究证据库。`accepted` 经验仍标记
`not_evidence=true`，后续使用时必须重新查询最新事实。

## Codex 主路径

项目 skill 位于 `.codex/skills/st-research-codex/`。从仓库根目录运行工作台：

```bash
uv run python research_workbench.py experiences --status accepted
uv run python research_workbench.py evidence --question '研究问题' --output /tmp/st-pack.json
uv run python research_workbench.py validate --pack /tmp/st-pack.json --draft /tmp/st-draft.json --output /tmp/st-validation.json
uv run python research_workbench.py record --pack /tmp/st-pack.json --draft /tmp/st-draft.json --validation /tmp/st-validation.json
```

只有显式 `record`、`feedback`、`propose`、seed 或人工 review 会写独立本地库。普通成功回答
不会自动生成经验；Codex 和后台规则也不能把 candidate 升级为 accepted。

`/answers/stream` 使用 NDJSON，只发送完整、已验证的领域事件：`accepted`、
`interpreted`、`routed`、`answer_card`、`claim_block`、`degraded`、`completed`、
`error`。不转发模型 token delta。

`llm/` 提供 Fake provider、OpenAI Responses Structured Outputs adapter、问题解释和
claim backing 校验；`llm_adapter.py` 只负责把这套边界注入 W1 API。确定性 router
始终拥有最终路由；LLM 不接数据库，只接收问题/ResearchContext 或过滤后的 AnswerCard。

实时 OpenAI 模式要求本地环境提供 `OPENAI_API_KEY`、`V8_OPENAI_MODEL`，并在本地
虚拟环境安装 `openai>=2,<3`。未配置、超时或输出校验失败时仍返回确定性结果；
`llm_mode=off` 是纯确定性模式。

The current HTTP boundary accepts `v8_copilot_api_contract_v0` requests and
returns `v8_copilot_api_contract_v1` responses. This is an explicit request /
response split, not a claim that v1 responses validate as v0.

React 经验中心、兼容问答、运行审计和个股面板位于 `web/`：

```bash
cd web
npm install
npm run build
cd ..
uv run python run_api.py
```

打开 `http://127.0.0.1:8765`。首页只展示可复用经验；原始问题和回答仅在次级运行审计中
追溯。开发模式可运行 `npm run dev`，Vite 将 `/api` 代理到本地 FastAPI。旧问答位于
`/legacy`，个股节点通过 ResearchContext URL 回到该兼容入口继续提问。

固定的数据维护任务、研究任务和审计面板分工见 [OPERATING_MODEL.md](OPERATING_MODEL.md)。
选择性联网与离线机制的边界见 [SELECTIVE_EVIDENCE_ARCHITECTURE_2026_07_15.md](SELECTIVE_EVIDENCE_ARCHITECTURE_2026_07_15.md)。
全量 ST universe、市场基准和下一阶段能力差距见 [V8_NEXT_PRD.md](V8_NEXT_PRD.md)；
按阶段验收的执行账见 [V8_NEXT_TODO.md](V8_NEXT_TODO.md)。P6 的管理人模式、
重整前价值区间、方案价值重估及无专家人审校准机制见
[V8_P6_INSIGHTS_PRD.md](V8_P6_INSIGHTS_PRD.md) 和 [.todos/](.todos/)。
数据维护入口为 `data_maintenance.py`：价格固定使用 Tushare，公告固定使用 CNINFO；逐源逐股
checkpoint 控制重叠增量、去重和失败恢复，最后生成 `local_data/v8_copilot/freshness_manifest.json`。
维护器可将 Tushare `stock_st` 固化为 append-only 每日 universe，并用 current 或指定 snapshot
展开批量范围；中证全指和内部 ST 等权研究指数使用独立 market-context 数据面，不与个股基础库混表。
P2/P3/P4 已完成真实数据验收：209 只全量严格 manifest 为 `FM-D836EE706EAA2BDE08DC`；
market-context pool 包含 ST 等权、中证2000和中证全指；manifest 为
`MC-F15756CDF3490173508B`，最新区间 ready、历史区间 partial，三基准共同窗口从
2023-08-11 开始。
答案卡现在按 manifest 终点消费同窗个股、ST 等权、中证2000和中证全指，输出收益、
百分点差和归一化曲线；缺端点、低覆盖或 universe 日期错位时显式降级。另有独立
point-in-time 市值数据面：按收益窗口起点的历史 ST 名单与总市值划分微盘/普通 ST，
不使用当前市值倒推历史。`D-051C` 与 `C14` 已分别于 2026-07-21、2026-07-22 关闭。
P6A 的首个管理人闭环已实现：`restructuring_entities_v1.sqlite3` 使用 append-only
案件、组织、别名、任职、来源和关键节点；当前本地 pilot 覆盖 24 个上市公司案件、
23 个管理人组织、35 条任职事实和 119 条“管理人 × 案件节点”关系。节点价格严格从
披露后的首个交易日开始观察，并与 ST 等权、中证2000和中证全指同端点比较；同案重复
公告不重复计样本，单一管理人同类节点少于 8 案时只列逐案结果。
新 Codex 运行会把完整 EvidencePack、结构化 draft 和 ordinal 判断审计持久化；在 `/runs`
点击 Pack ID 可查看数据库行、Lens、联网事实、backing 与 coverage gap。经验治理入口为
`experience_governance.py`，负责 accepted registry 导出、到期复验、冲突检测和失败自动 blocked。

## 契约与文件

- `lens_binding.py` — **脊梁**：LensRegistry（只读加载 pinned v1 库）+ candidate_lenses（按主题标签/cluster 精确匹配）+ LensInvocation + LensGap。
- `answer_engine.py` — AnswerCard、AnalysisClaim/backing、只读数据访问和 card builders。
- `market_comparison.py` — manifest 约束的只读同窗对齐器、相对收益和 evidence-gap 语义。
- `market_factors.py` — append-only 时点市值快照、覆盖门与 factor manifest。
- `microcap_comparison.py` — 窗口起点微盘/普通 ST 分组、收益分布和缺口语义。
- `restructuring_administrators.py` — P6A append-only 案件/管理人/别名/任职/关键节点事实层和保守物化器。
- `administrator_event_study.py` — 披露后首个交易日起算的管理人节点事件窗口、三基准相对收益和小样本门。
- `pilot_manifests/p6a_administrator_pilot_v1.json` — 可复现的 P6A 官方 PDF 缓存清单、预期计数和 fail-closed 样本。
- `contracts/v8_answer_contract_v0/` — W1 单写、W2/W3/LLM 只读的 JSON 契约。
- `contracts/v8_copilot_api_contract_v0/` — 冻结的 Batch 2 API v0 schema、manifest 和固定 fixtures。
- `contracts/v8_copilot_api_contract_v1/` — 增量 API v1：typed QuestionCard、QueryTemplate id 和证据导航。
- `contracts/v8_question_card_contract_v0/` — 问题卡对象、生命周期和固定 fixture。
- `contracts/v8_query_template_contract_v0/` — 九类可复用查询模板；全部标记 `not_evidence=true`。
- `api_contract.py` — ResearchRequest、RouteDecision、ResearchResponse、dossier 和 stream 类型。
- `core_router.py` / `orchestrator.py` — 确定性解释、最终路由和 AnswerCard 执行编排。
- `orchestrator_v1.py` — typed sedimentation、QueryTemplate 和七类证据导航增量层。
- `snapshot_metadata.py` — SQLite/episode freshness 读取与 fail-loudly 快照契约。
- `api.py` / `run_api.py` — FastAPI 接口和本机启动入口。
- `dossier_service.py` — 只读个股价格、状态、事件、时间线和 lens payload。
- `llm/` — Structured Outputs parser/composer、provider、schema 和 backing 门。
- `llm_adapter.py` — W1 API 与 W2 LLM 边界之间的薄集成层。
- `evidence_gateway.py` — AnswerCard 到 EvidencePack 的只读适配和 Codex draft 校验。
- `research_repository.py` — 独立 Research Run Ledger 与 Experience Repository。
- `experience_contract.py` / `experience_distiller.py` — 非证据经验契约、人工晋级闸门和候选提炼。
- `experience_governance.py` / `experience_registry/` — 去敏 registry、冲突检测和定期回归治理。
- `research_workbench.py` — 项目 skill 使用的本地 CLI。
- `data_maintenance.py` / `data_refresh.py` / `freshness_manifest.py` — Tushare/CNINFO 可恢复增量维护与统一 freshness manifest。
- `universe.py` — 权威每日 ST membership、append-only snapshot、digest/diff 与 current pointer。
- `maintenance_plan.py` — universe 对本地 holdings/checkpoint 的只读差集与 bootstrap 计划。
- `market_context.py` — benchmark registry、中证全指存储和逐日成分 ST 等权指数计算核。
- `V8_NEXT_PRD.md` / `V8_NEXT_TODO.md` — P0–P5 当前完成度与延续项。
- `V8_P6_INSIGHTS_PRD.md` / `.todos/` — P6 管理人、两类估值、客观校准与分项交付账。
- `web/` — React/Vite 经验中心、运行审计、兼容问答和个股面板。
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

## 兼容边界

冻结 AnswerCard、API、QuestionCard、QueryTemplate 和 Research Memory contracts 保持不变。
任何新事实字段仍先进入确定性 Core 和 AnswerCard。经验契约是消费侧增量对象；候选可持久化，
但只有 owner 的人工 review 才能接受，且接受后仍不是证据。
