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
- [x] 4 只无价格基线股票已按各自上市日逐股 bootstrap；批次共用全局起始日会被 CLI 拒绝。
- [x] 7 只无基础公告股票已按各自上市日逐股 bootstrap（3 只北交所本轮官方查询为 0 行，但逐股 checked-through 已成功记录）。
- [ ] 为退市/暂停上市股票记录 expected terminal date，避免假 freshness gap。
- [x] freshness manifest v1 增加 universe snapshot ID、as-of、digest、member count，并兼容读取 v0。

验收：同一个 snapshot 重跑产生完全相同的任务范围；计划阶段不写生产库、不发网络请求。

## P2 — 全量增量维护

- [x] 增加稳定 batch offset/size、请求间隔、指数退避重试、逐项 progress 和 run summary。
- [x] 209 只价格已逐股核查到 2026-07-20；4 只新基线完成 bootstrap，暂停/无当日行股票由成功 checkpoint 表达 verified-through，不伪造价格。
- [x] 核对 qfq basis change；仅受影响股票由既有安全路径自动 full rebase。
- [x] 209 只 CNINFO 公告已逐股 checked-through 到 2026-07-21；7 只新基线完成独立 bootstrap。
- [x] 单股失败保留上次成功游标；同 snapshot 可按 batch 或 plan 的失败项 resume。
- [x] 生成 strict full-universe manifest `FM-D836EE706EAA2BDE08DC`：209/209 价格与公告均 current，且绑定 `SU-4228A7C5B06703A022EF`。
- [x] 定义日常顺序：交易日收盘后 universe → prices/benchmarks → announcements → manifests → experience verify。

验收：价格/公告分别报告 209 只逐股状态；任何全局 ready 都不能由全库最大日期冒充。

## P3 — 市场与 ST 板块基准

- [x] 中证全指已回填 2016-01-04 至 2026-07-20 共 2,560 点并进入 market-context manifest。
- [x] `stock_st` 历史 membership 已回填 333,858 行、2,399 个源日期；实际源起点为 2016-08-09。发现并复查 25 个源内交易日空洞，连续区间从 2021-03-17 开始，历史状态明确为 `partial`。
- [x] 用逐日 membership + qfq returns 物化 `st_equal_weight_v1`：2021-03-17 至 2026-07-20，共 1,295 个交易日。
- [x] 用真实结果冻结当前 ready 门槛为 95%；最近连续 13 个交易日达标，最近 10 日最低覆盖率 96.23%。低覆盖历史点保留但不得作为 ready 证据。
- [x] 增加 market-context manifest `MC-01868C4AD4FC1F0E9F95`、方法版本 provenance、当前/历史双层状态和缺口清单。
- [ ] 选一个外部厂商 ST 指数做 shadow sanity check；标记 `context_only`。
- [x] 检验停牌/缺价不填 0、无有效收益不伪造、按当日名单计算、周末名单不生成指数点等边界；上市首日和移入/移出语义由逐日 membership 自然落位。

外部旁证不阻塞 canonical 指数：东财公开行情端点本轮连续返回空响应，Tushare `ths_daily` 当前账号无权限；在拿到稳定授权接口前保持 pending，不能把网页展示值写成正式序列。

验证记录：P2/P3 相关 30 项聚焦测试全绿（含 universe 基础测试）；Python 全套仅有 5 个失败，已逐项在未改动的 master 复现，均为真实数据刷新后的硬编码日期/既有叙事断言；Web 29 项全绿。worktree 未安装独立 `node_modules`，Web 回归在同一提交基线的主工作树依赖环境执行。

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
3. P2 全量维护与 P3 canonical 基准已完成；日常按运行手册增量执行。
4. 下一步做 P4 答案卡接入并关闭 `D-051C`。
5. 厂商 ST 指数仅在取得稳定授权接口后补 context-only shadow check。
6. 再进入 `C14`、SDK 质量门和旧入口退役。
