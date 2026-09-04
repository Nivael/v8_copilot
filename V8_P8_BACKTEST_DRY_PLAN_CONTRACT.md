# v8 P8 回测 v2 dry-plan 契约

状态：**frozen before historical provider writes and before any v2 outcome is read**
冻结日期：2026-09-05
契约版本：`v8_p8_backtest_dry_plan_v1`
父契约：[V8_P8_BACKTEST_CONTRACT.md](V8_P8_BACKTEST_CONTRACT.md)

## 1. 目的

本 dry-plan 只回答：现有 point-in-time 数据是否足以执行同阶段排序和可交易篓子；还缺哪些
交易日、字段、事件真值与可交易状态；补齐需要多少请求、时间和磁盘。它不得回答任何信号是否
有效，也不得因为即将看到的结果修改 v2 契约。

运行分两步：先生成本地只读 inventory；只有 inventory 和请求预算落盘后，才允许在显式
`--allow-provider` 下按交易日回填已冻结的数据范围。dry-plan 本身不调用 OpenAI，也不改变
正文 LLM 的独立授权门。

## 2. 严禁读取和计算

dry-plan 不得读取预测日之后的个股/ST/中证 2000 收益，不得计算信号与收益、节点、退市之间的
相关、分档差、命中率、lift、p 值或置信区间，也不得生成候选“效果”排名。

它也不得：

- 根据结果改形态阈值、lane 配额、分层阶梯、最低样本、成本或 walk-forward 年；
- 把 title/provisional 节点升级为核证真值；
- 用当前 ST 名单重建历史 membership；
- 用未来披露日回填股东户数或事件阶段；
- 将缺失停牌、一字板、退市终点或股本状态解释为可成交。

## 3. 冻结范围与输入

容量主范围为 **2021-03-17 至 2025-12-31**；2026 只盘点 prospective shadow，不进入三个
开发期测试年。特征 warm-up 可以读取 2021-03-17 以前已经存在的 120 个合格交易日，但不得为
扩大测试结果擅自把主范围向前延伸。

只读输入及优先级：

1. point-in-time `st_membership_daily`、证券板块与历史风险警示状态；
2. qfq 日线、交易日历、ST 等权、中证 2000；
3. `market_activity_v1` 的 `daily_basic`、OHLC、`stk_limit`/`limit_status`、`suspend_d`；
4. P6 verified valuation episode；P8 body/deterministic verified 事件；
5. P8 情景参考、公开筹码代理、历史 funnel 版本与 typed contract；
6. 退市终点、股本变化和资本结构污染账。

每个输入保存路径或逻辑源、schema/version、checked-through、SHA-256/content digest 和最大
`available_as_of`。数据库以 read-only URI 打开；inventory 只写显式输出目录。

## 4. 逐交易日数据容量

对主范围内每个开市日输出：

- 当日历史 ST 成员数，以及 membership 是否 point-in-time 完整；
- qfq/OHLC、`turnover_rate_f`、`total_mv`、`circ_mv`、`limit_status`、涨跌停价和停牌状态的
  成员覆盖率；
- ST 等权和中证 2000 是否存在、是否同日；
- 可形成 120 日 lagged baseline 和 20 日形态窗的股票数；
- 字段缺失、端点冲突、重复键、陈旧价、股本跳变与 unknown 可交易状态数。

“当日完整”固定要求：point-in-time membership 可用；qfq、自由流通换手和主基准各覆盖至少
95% 的当日成员；交易状态字段对任何拟成交股票均不能 unknown。95% 只允许决定是否有完整
横截面，不能把缺字段的单股自动补成可交易。

历史回填按 `trade_date` 获取整市场截面，不按 symbol × date 请求。缺失计划分别列出
`daily`、`daily_basic`、`stk_limit`、`suspend_d` 的唯一日期；`daily_basic` 必须显式请求
`turnover_rate_f,total_mv,circ_mv,limit_status`。`volume_ratio` 只作旁证，不进入主分数。

## 5. 分层与样本容量（不读 outcome）

对 2023、2024、2025 三个测试年，按
`stage × calendar_half × board` 和唯一放宽后的 `stage × calendar_half` 仅统计：

- 观察数、公司数、有效交易日数；
- 能否形成 P8A `p_star_opportunity_score`、P8B precursor score 输入、P8C accumulation score、
  P8C holder score；
- 达到 100 个观察/40 家公司的 signal family 数；
- cell 是否达到 12 个观察/8 家公司。

不计算三档，不读取 60/120 日结果。P8B 只统计训练期 precursor family 的输入容量；不得在
dry-plan 中计算其转化率或 Beta-binomial 分数。

制度字段同时物化：全局 `regime_version` 在 2024-04-30 切换；
`market_cap_rule_effective` 自 2024-10-30 为 true；`annual_report_season` 与 H1/H2 按契约固定。

## 6. 事件真值与金标容量

只报告事件数量，不报告事件率：按年份、公司、track、节点、程序方向、老股东影响和
`verified/body_verified/deterministic_verified/title_derived/provisional` 计数；另列每个测试年
能够完成 60/120 日观察的核证事件数和右删失数。

LLM 200 条金标门只准备分层抽样框：五 track、正/负/unknown、三个年份与两个制度期。输出首批
60 条、可扩至 120/200 条的去重容量和正文/source-span 覆盖，不预填人类答案，不计算准确率。
若外部正文抽取仍未获授权，状态保持 `unavailable_pending_explicit_egress_consent`。

## 7. 历史漏斗与可交易篓子容量

逐测试年盘点能否 point-in-time 回放四 lane：当日 event frontier、情景参考版本、持续型特征、
筹码可得日、lane 排序字段和 overflow 是否齐全。当前版本的实时候选不得倒填到历史日期；若某
日无法由当时输入和冻结代码重建，该日必须 excluded 并给原因。

交易容量至少输出：

- 每周决策日、下一可交易收盘、ST 基准端点覆盖；
- 停牌、一字涨停不可买、一字跌停不可卖和 unknown 状态次数；
- 退市且无退出端点、锁仓跨周、现金日、资本结构污染次数；
- 在不看回报数值的前提下，可执行周数、可执行订单数和无法执行原因。

dry-plan 不生成净值、胜率、回撤、股票贡献或基准差。

## 8. Provider 权限、成本和写入边界

先复用既有 P7/P8 provider probe 的账号积分、权限、每次返回上限与速率事实；过期或不明确才
允许一个固定日期、零 canonical 写入的小 probe。正式回填必须：

- 明示 `--allow-provider`，按 endpoint/date checkpoint，可恢复且幂等；
- 先写 staging run，完成覆盖、重复键、schema 与 digest 验证后再移动 current pointer；
- 保存请求成功/空返回/限流/重试数，不保存 token、请求头或完整敏感错误体；
- 报告预计与实际请求数、耗时、下载字节、SQLite 增量和失败日期；
- 不改基础生产库，不覆盖 P7 的历史 snapshot；新增 append-only activity snapshot/run。

## 9. 输出与停止条件

JSON 顶层至少包含：

`contract_version, plan_id, content_digest, generated_at, as_of, git_provenance,
input_inventory, date_coverage, endpoint_request_plan, feature_capacity,
stratum_capacity, event_truth_inventory, gold_queue_capacity,
historical_funnel_capacity, basket_execution_capacity, regime_boundaries,
request_budget, storage_budget, hard_blockers, non_blocking_gaps,
recommended_next_step, human_decisions_required`

同时生成结论在前的 Markdown 和离线 HTML；HTML 只展示容量、缺口与下一步，不展示任何效果
图。默认 `human_decisions_required=[]`。

出现以下任一情况就停止正式 v2 回测，但仍发布 dry-plan：

1. 任一测试年没有足够完整日期形成 point-in-time 120 日主结果；
2. 历史 funnel 不能按当时版本重建，且无法从冻结输入确定性重放；
3. 可交易状态或 ST 主基准对拟成交端点不完整；
4. 所有 signal family 都达不到 100 个观察/40 家公司；
5. 回填需要新付费源、改变经济对象或放宽 fail-closed 边界。

前四项由系统自动降级和报告，不要求 owner 逐条判断；第五项才请求一次性决定。
