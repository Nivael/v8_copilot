# v8 下一阶段 TODO

状态定义：`[x]` 已完成并有测试；`[~]` 代码基础已具备但尚未完成真实数据验收；`[ ]` 未完成。

## P0 — 架构与基础契约（本分支）

- [x] 区分 holdings、ST membership、maintenance plan、research scope。
- [x] 确认 Codex 是主 LLM；浏览器只做展示、审计与经验治理。
- [x] 选择 Tushare `stock_st` 作为 canonical 每日 ST membership。
- [x] 选择中证全指作为 broad-market reference。
- [x] 选择逐日成分 ST 等权指数作为 canonical ST-sector reference。
- [x] 新增 append-only universe snapshot、digest、diff、current pointer。
- [x] 新增 `sync-universe`、`show-universe` CLI。
- [x] 让 `refresh` 支持 `--universe-current` / `--universe-snapshot`。
- [x] 新增只读 `plan`，区分 current、stale、missing baseline 并估算最低请求数。
- [x] 新增 benchmark registry、独立 SQLite store 和中证全指刷新服务。
- [x] 新增 survivorship-safe ST 等权计算核与 coverage 字段。
- [x] 回归与本地提交完成：新增 18 项聚焦测试全绿；Python 全套 210 项中 207 项通过，3 个失败在 master 同样复现；Web 29 项全绿。既有真实数据/措辞断言已隔离为后续修复项。

验收：聚焦单元测试全绿；空 universe、错日响应、缺历史 membership 均 fail closed。

## P1 — 真实 universe 与维护计划

- [x] 将 2026-07-20 的 209 只名单 materialize 到默认本地 universe 目录（`SU-4228A7C5B06703A022EF`）。
- [x] 增加 `plan` 命令：只读比较 universe、价格、公告与 checkpoint。
- [x] 计划输出总数、current/stale/missing、预计 API 调用和 bootstrap 队列。
- [ ] 把 4 只无价格基线股票单独进入 bootstrap 配置，不给全部 209 只共用全局起始日。
- [ ] 把 7 只无基础公告股票单独进入 bootstrap 配置。
- [ ] 为退市/暂停上市股票记录 expected terminal date，避免假 freshness gap。
- [ ] freshness manifest v1 增加 universe snapshot ID、digest、member count。

验收：同一个 snapshot 重跑产生完全相同的任务范围；计划阶段不写生产库、不发网络请求。

## P2 — 全量增量维护

- [ ] 增加 batch size、速率限制、失败重试和 run summary。
- [ ] 先执行 209 只价格增量刷新到最近交易日。
- [ ] 核对 qfq basis change，必要时只对受影响股票 full rebase。
- [ ] 再执行 209 只 CNINFO 公告 checked-through 刷新。
- [ ] 单股失败后 resume，只重试失败项。
- [ ] 生成 strict full-universe manifest；保留原三只 research manifest 的独立含义。
- [ ] 定义日常调度：交易日收盘后 universe → prices/index → announcements → manifests。

验收：价格/公告分别报告 209 只逐股状态；任何全局 ready 都不能由全库最大日期冒充。

## P3 — 市场与 ST 板块基准

- [~] 已回填中证全指 2016-01-04 至 2026-07-20 共 2,560 点；增量 checkpoint/manifest 待补。
- [ ] 回填 2016 年以来每日 ST membership，或用 ST 状态事件优化请求量后再生成逐日快照。
- [ ] 用逐日 membership + qfq returns 物化 `st_equal_weight_v1`。
- [ ] 用真实结果校准并冻结 coverage ready 门槛（PRD 初值 95%）。
- [ ] 增加 benchmark freshness manifest 与方法版本 provenance。
- [ ] 选一个外部厂商 ST 指数做 shadow sanity check；标记 `context_only`。
- [ ] 检验停牌、上市首日、无前收盘、移入/移出 ST 当日的边界。

验收：不存在用当前 209 只倒算历史的路径；任意指数点都可追到当日名单和有效成员数。

## P4 — 答案卡与 dossier 消费

- [ ] 新增统一交易日窗口对齐器。
- [ ] 输出 stock、ST、market 三条窗口收益。
- [ ] 输出 stock−ST、stock−market、ST−market 三条百分点差。
- [ ] 图表同时显示个股、ST 指数和大盘归一化曲线。
- [ ] 缺端点或低 coverage 时降级为 evidence gap，不插值、不伪造 alpha。
- [ ] provenance 包含 universe snapshot、benchmark definition、series as-of。
- [ ] 增加 API contract 新版本（仅当现有 body rows 无法无损表达时）。
- [ ] 关闭 `D-051C` 并保留关闭证据。

验收：针对“最近两周为什么跌这么多”类问题，答案能区分个股问题、ST 风格下跌和全市场下跌。

## P5 — 其余 v8 能力缺口

- [ ] 补 `C14` 的 point-in-time 市值/微盘变量，不使用当前市值回填历史。
- [ ] 自动刷新 episode index、release lens 快照与相关 freshness。
- [ ] 增加 OpenAI SDK 真实调用质量门，覆盖 tool calling、schema failure 与 fallback。
- [ ] 将已接受经验的生产 registry 从 seed 状态推进到真实人工接受样本。
- [ ] 完成旧入口/旧 API 的退役检查，不重建 v7 worksite。
- [ ] 为公告正文和非 CNINFO 外部事实建立按问题触发的成本预算与覆盖报告。

验收：上述每项有独立 contract/test/rollback；不与 universe 全量刷新捆成一个不可回滚发布。

## 推荐执行顺序

1. 评审并合入 P0。
2. 做 P1 dry plan，确认 4 只价格 bootstrap、7 只公告 bootstrap 的边界。
3. 先跑价格与中证全指，再跑公告。
4. 历史 membership 与 ST 等权 shadow run。
5. 答案卡接入并关闭 `D-051C`。
6. 再进入 `C14`、SDK 质量门和旧入口退役。
