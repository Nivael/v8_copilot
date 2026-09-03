# v8 P7-0 dry-plan 契约

状态：frozen before implementation
日期：2026-09-04
契约版本：`v8_p7_0_dry_plan_v1`
父 PRD：[V8_P7_DAILY_INTELLIGENCE_PRD.md](V8_P7_DAILY_INTELLIGENCE_PRD.md)

## 1. 目的

在修改刷新服务、写 canonical 数据库或建立 UI 之前，回答 P7 的数据是否真实可用、历史范围
有多深、当前账号是否负担得起、候选阈值每天会产生多少条研究任务，以及哪些能力必须保持
shadow。

P7-0 不证明异常具有预测力，也不选择“回测最好”的阈值。它只冻结可得性、正确性和运营容量。

## 2. 两阶段运行边界

### 2.1 P7-0a：本地只读盘点

- 所有 SQLite 输入以 read-only URI 打开；
- 不刷新公告、价格、membership、market factors 或 valuation episode；
- 不调用 LLM，不生成生产分类；
- 只允许写入命令行显式指定的 JSON/Markdown 报告路径；
- 不修改 current manifest、checkpoint、registry 或任何 canonical pointer。

### 2.2 P7-0b：有界 provider probe

- 只有显式 `--probe-provider` 才联网；
- token 只从本地环境/secret loader 读取，报告和日志不得保存 token、请求 header 或完整错误体；
- 只请求冻结的日期和字段，不做历史全量回填；
- provider 返回只写显式 probe report，不写 canonical 数据库；
- 网络失败、权限不足或限流是结果，不触发自动更换供应商。

两个阶段分别生成内容摘要和 run ID；P7-0b 必须引用 P7-0a 的输入摘要，防止盘点范围漂移。

## 3. 输入与基线

报告必须登记：

- git commit、contract version、运行时间、时区和 `as_of`；
- base database、market context、market factors、valuation facts/episodes 的路径、大小和摘要；
- 采用的 ST membership snapshot/日期范围；
- qfq 价格、公告和各数据面的 checked-through；
- 最新完整交易日，不得把自然日或全库最大日期当成所有股票的新鲜度；
- 当前分支必须包含 `130ca0d`，否则停止并报告 `wrong_baseline`。

推荐主历史范围从连续 ST membership 与 ST 等权共同可用的 `2021-03-17` 开始；
`2016-08-09` 至 `2021-03-16` 只做可行性旁证，是否晋级由字段覆盖决定。

## 4. 本地库存盘点

P7-0a 必须输出：

1. `daily_prices` 总行数、股票数、日期范围及 `amplitude`/`turnover_rate` 非空率，按来源和年度分层；
2. C14 `market_cap_daily` 快照日期数、symbol-day 数、字段集合和连续性，明确其是估值锚点而
   非 P7 连续活动库；
3. 每个历史 ST symbol 的 qfq 价格、公告索引、正文、membership 和 valuation episode 覆盖；
4. 可从现有字段复算 `raw_pre_close`/振幅的记录数；无法无损复算的必须列为回填需求；
5. 已知停牌代理、一字板代理、退市状态和核证退市整理边界的库存；
6. 每日公告数量、类别候选、同日附件 bundle 数和硬节点标题候选；
7. 现有 P6 重整阶段真值中 `verified`、`provisional`、`conflicted` 的数量。

任何旧字段有部分非空都不能被描述成“连续可用”。

## 5. Provider 权限与字段 probe

### 5.1 必需接口

| 接口 | 显式请求字段 | P7 职责 | 阻塞性 |
| --- | --- | --- | --- |
| `daily_basic` | `ts_code,trade_date,close,turnover_rate,turnover_rate_f,volume_ratio,total_share,float_share,free_share,total_mv,circ_mv,limit_status` | 主换手、股本市值、一字板状态 | P7B hard |
| `suspend_d` | `ts_code,trade_date,suspend_timing,suspend_type` | 停复牌与日内停牌 | P7B publish hard |
| `stk_limit` | `trade_date,ts_code,pre_close,up_limit,down_limit` | 精确涨跌停价格及冲突复核 | P7B publish hard |
| `daily` | `ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount` | 原始振幅、价格和成交 | P7B hard |

`limit_status` 文档标记为非默认字段，必须显式请求。probe 必须验证返回 schema，而不是只验证
接口没有报错。`volume_ratio` 只登记完整率和厂商口径，不进入主异常计算。
`suspend_d` 只有在目标日期请求成功且返回未被截断时，缺少某股票记录才可作为“当日未停牌”
的负证据；否则其状态是 unknown。

### 5.2 交易所参考接口

| 接口 | 预期最低积分 | 用途 | 阻塞性 |
| --- | ---: | --- | --- |
| `stk_shock` | 6000 | 已公开异常波动及领先天数对照 | non-blocking |
| `stk_high_shock` | 6000 | 已公开严重异常波动对照 | non-blocking |
| `stk_alert` | 6000 | 交易所重点提示期间对照 | non-blocking |

不可把这些接口描述成免费数据。不可用时登记 `pending_provider_permission`，P7A/P7B 继续；
P7D 的交易所对照保持 unavailable。

### 5.3 账号积分与实际配额

每个接口同时记录：

- 官方声明的最低积分、单次行数和总量限制；
- 当前账号实际 `success`、`permission_denied`、`rate_limited`、`empty_valid` 或
  `provider_error`；
- 返回行数、字段完整率、响应时间和观察到的安全请求间隔；
- 当前账号精确积分（仅在 provider 有机器可读元数据时记录）；否则写 `unknown`，不得由一次
  成功调用伪造具体积分；
- 以观察到的配额估算历史回填和每日增量的请求数、最短/保守耗时。

`daily_basic` 官方门槛至少 2000 积分，5000 积分才声明无总量限制；成本结论必须以当前账号
probe 为准，不能只按“一个交易日一次请求”计算。

### 5.4 冻结 probe 日期

对 date-based 接口使用以下固定日期；非交易日或 provider 明确无数据时不得临时挑一个“能出
结果”的日期，必须按交易日历机械回退并记录：

- `2016-08-09`：历史 ST membership 候选起点；
- `2021-03-17`：连续 ST 等权与主 shadow 候选起点；
- `2023-08-11`：中证2000共同语境起点；
- `as_of` 前最后完整交易日；
- 由本地数据机械选择的最近一个已知长停牌样本和最近一个一字板样本。

停牌和一字板样本选择算法只看当日/此前事实，不看后续公告、收益或硬节点。

## 6. 覆盖与资格盘点

按年度、交易所板块和 ST 阶段报告：

- membership symbol-day；
- `turnover_rate_f` 当前值有效数；
- 前 120 个合格交易日中至少 60 个有效观察的数量；
- 原始价格、停复牌和 limit 状态可判定数；
- 一字板、停牌、复牌恢复期、退市整理期和终端状态未知的排除数；
- 可生成 profile 的 symbol-day 数及覆盖率；
- 当日全体 ST 活动覆盖率的平均、中位、P10 和最差日期。

日常 manifest 的 full-universe ready 门暂定 95%；低于 95% 时仍保存逐股事实，但不得把排名
称为“全体 ST 异常榜”。P7-0 必须报告 90%/95%/98% 三个门的可用日期比例，不得根据未来
硬节点或收益选择门槛。

## 7. 候选异常预算

### 7.1 冻结计算

历史窗固定使用当前日前 120 个合格交易日，最少 60 个观察；当前日不进入基线。对每个
symbol-day 计算平均秩分位、median、MAD 和 robust z，运行以下三套 profile：

- `broad`：percentile ≥ 95%，robust z ≥ 3；
- `balanced`：percentile ≥ 97.5%，robust z ≥ 4；
- `strict`：percentile ≥ 99%，robust z ≥ 5。

P7-1 默认 shadow profile 预注册为 `balanced`。P7-0 可以因数据不可计算而否决它，但不得查看
硬节点、交易所标签或未来收益后改选 profile。

### 7.2 必须输出的容量指标

每个 profile 分别报告：

- 原始日命中总数；
- 每日平均、中位、P90、P95 和最大命中数；
- 命中为 0、1–5、6–10、11–20、21–30、>30 的交易日比例；
- 3/5/10 个合格交易日合并间隔下的独立 activity episode 数；
- 每个 episode 的持续日数、峰值和重复命中数分布；
- 年度、ST 阶段、ST/中证2000市场语境分层；
- Top 10 股票占全部命中的比例和最高单股命中数；
- `zero_mad_breakout` 数量，独立列示、不混入默认 profile。

页面未来可设置 Top-N 展示，但 dry plan 不丢弃 overflow，也不通过调阈值把数量硬凑到页面
容量。是否值得建设 P7C，由完整容量分布和信息覆盖共同决定，不由一个平均数决定。

## 8. 公告与硬节点 dry inventory

P7-0a 只用公告元数据、标题和现有已核证 P6 事实生成候选库存，不运行新的全量 LLM 分类。
必须报告：

- 每日公告总数及十类候选分布；
- 同日同主题 bundle 压缩前后数量；
- 六类硬状态节点候选及已被 P6 verified 支持的比例；
- 一般“进展公告”误命中硬节点的反例数量；
- 每个状态维度可确定、冲突和 unknown 的发行人数；
- 退市整理起止边界 verified/provisional/unknown 数量。

标题候选不是生产真值；报告必须显式写 `candidate_only`。

## 9. 请求计划

请求量优先按交易日估算：

- `daily_basic`、`stk_limit`：每个目标交易日一次全市场截面，再按当日 membership 过滤；
- `suspend_d`：按日期或有界区间请求，选择实际请求更少且不触发行数截断的方式；
- `daily`：已有 qfq 价格只用于收益；缺原始 `pre_close`/振幅的范围单独列出，不能默认全量逐股
  重拉；
- 三个交易所参考接口：先做权限 probe，再根据单次 1000 行限制估算；不可用时请求量为 pending。

报告分别给出：主历史范围、探索历史范围、最新已核证 universe（现有基线快照为 209 只）
近 120 日 bootstrap、每日增量四种计划。推荐顺序必须先交付满足最新已核证 universe 的最小
bootstrap，再决定是否历史全量回填。

## 10. 防泄漏规则

- 阈值、窗口、排除和合并间隔的选择不能读取未来公告、硬节点、交易所标签或收益；
- 当前日不进入自己的 median/MAD/percentile；
- 历史 universe 必须使用 point-in-time membership，禁止用最新名单倒算；
- 公告使用 `available_as_of`，不能按事后生效日提前出现；
- provider 当下修订的历史字段必须保存 fetched-at 和内容摘要；
- P7-0 报告不得包含“命中率最高”“最赚钱 profile”等结果优化语言。

## 11. 输出 schema

JSON 顶层至少包含：

- `contract_version`、`plan_id`、`content_digest`、`generated_at`、`as_of`；
- `git_provenance`、`input_inventory`、`source_boundaries`；
- `provider_permission_matrix`、`field_coverage`、`request_budget`；
- `eligibility_summary`、`exclusion_summary`；
- `trigger_budget_by_profile`、`activity_episode_budget`；
- `announcement_inventory`、`hard_node_candidate_inventory`；
- `terminal_phase_inventory`、`exchange_reference_status`；
- `hard_blockers`、`non_blocking_gaps`、`safe_defaults`；
- `recommended_next_step`、`human_decisions_required`。

Markdown 报告必须是一页结论在前、详细表在后；不能要求 owner 阅读逐股清单才能作决定。

## 12. 出口门与停止条件

P7-0 完成不等于 P7 可发布。进入 P7-1 至少要求：

1. `daily_basic` 当前账号可返回显式 `turnover_rate_f` 和 `limit_status`；
2. 主 bootstrap 范围的原始日线、停复牌和涨跌停状态有可执行补齐方案；
3. 最新已核证 universe 的 120 日 bootstrap 请求预算在观察到的配额内可完成；
4. `balanced` profile 可机械计算，或报告明确证明需要发布 contract v2；
5. 退市整理边界 unknown 有 fail-closed 排除路径；
6. 所有 production writes 仍为 0。

以下情况停止 P7B 进入 P7-1，但不阻塞 P7A：

- 当前账号无法取得 `turnover_rate_f`；
- 停复牌和一字板状态都无法可靠判定；
- 主范围多数股票无法形成 60/120 日基线；
- provider 配额无法支持最小 bootstrap 且没有 owner 授权的新数据来源；
- 需要使用未来硬节点或收益才能选出可运行阈值。

三个交易所参考接口无权限只产生 non-blocking gap。

## 13. 人类 review budget

默认 `human_decisions_required=[]`。只有以下情况可请求 owner 一次性决定：

- provider 权限不足，需要付费/换源等新授权；
- 主历史起点存在两个都可行但产品含义不同的选择；
- 退市整理期数据缺口使 fail-closed 排除掉过多当前股票；
- 三个 profile 均产生无法运营的容量，需重新定义产品范围。

报告固定建议选项为 `accept_safe_default`、`keep_p7b_shadow`、`stop_p7b_continue_p7a`。
不得把逐公告、逐股票或逐日审核转交给 owner。
