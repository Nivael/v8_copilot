# v8 P6B PRD：重整前偿债压力与市场重定价地图

状态：approved for staged implementation
日期：2026-07-23
负责人：Codex commander window
依赖：P4 market context；P5-C14 point-in-time market-cap contract
执行账：[.todos/002.md](.todos/002.md)

## 1. 决策与目标

P6B v1 不承诺为多数 ST 公司计算传统“内在价值区间”。典型重整候选可能资不抵债、
无法启用收益法且存在未识别负债；此时诚实结果不是负的股权价值或强行估值，而是：

1. **资产与偿债地图**：可核验资产、明确负债、偿债缺口、未知项和证据边界；
2. **市场定价地图**：公司在同日 ST 群体中的规模位置，以及进入 ST episode 后相对
   ST 等权基准的重定价路径；
3. **验证状态**：哪些量只是描述、哪些经过历史回放、哪些仍未通过前瞻验证。

P6B 先说明“市场正在怎样定价”，证据足够时才允许研究“市场是否定错”。P6B 不把
资产底座与“壳价值”相加，不输出目标价、底部、买卖建议或困境股排序。

正式重整方案关键条款披露后，P6B 停止增加新的重整前输入；冻结估值日之后的投资结果
仍可继续观察，并把方案披露、失败、摘帽和退市作为结果标签。方案本身带来的价值变化
属于 P6C。

## 2. 用户能得到什么

### 2.1 正常输出

- 估值日和当时可见的信息边界；
- 资产、负债、担保、诉讼、资金占用等事实及缺口；
- 调整后净资产状态：`positive`、`negative` 或 `unknown`；
- 偿债缺口及其对缺失负债的敏感度；
- 当前总市值和同日 ST 市值分位；
- 自进入本轮 ST 状态以来的 episode 相对重定价；
- 当前重整阶段、市场语境、停牌/陈旧价格和股本变化警告；
- 历史回放、前瞻验证和可用样本量状态。

### 2.2 允许的判断

- `信息不足`；
- `资产支持明确`；
- `资不抵债，当前市值主要体现生存/重整期权`；
- `同日 ST 规模位置为第 X 分位`；
- `本轮 ST episode 相对 ST 组合重定价为 X%`；
- `应先排查新增负债、停产、监管或资本结构变化`。

同日 ST 分位是 **size position**，不是估值判断。界面必须显示：

> 低分位只表示公司在当日 ST 群体中市值较小；低尾不等于便宜，高尾不等于昂贵。

v1 不输出“异常低位”“阶段性底部”“低估”“高估”或“恐慌错杀”。自身历史分位变化
只显示数值、成员数和换手噪声，不使用“显著”一词。

## 3. 当前数据现实

现有底盘包括：

- 历史 ST membership、个股 qfq 价格、公告和生命周期记录；
- ST 等权、中证2000和中证全指市场语境；
- C14 的 append-only 时点总股本/总市值契约和覆盖门；
- 270 条 `restructuring_path` episode，可作候选索引，但均为 `case_note_only`，
  子类型和部分边界不能作为 P6B 生产真值。

当前关键缺口：

- C14 只有当前真实截面，P6B 尚无历史锚点市值回填；
- 没有版本化、point-in-time 核证的 `valuation_episode`；
- 没有 point-in-time 财务重述链、资产/负债风险事实和实际回收样本；
- qfq 价格不能单独证明重整转增后的老股东实际财富变化；
- 停牌、退市和历史股本跳变的可计算边界尚未盘点。

因此 P6B-0 必须先做 dry plan；不得先写综合估值器。

## 4. 架构与数据边界

P6B 采用 hybrid 扩展，不重写答案引擎：

1. **Market plane**：复用 `market_factors_v1` 和 market context，补历史锚点快照；
2. **Valuation fact plane**：新增 `valuation_facts_v1`，保存原始财务、风险、股本和
   处置事实；
3. **Episode plane**：新增 `valuation_episode_v1`，保存连续 ST 区间及核证后的程序节点；
4. **Calibration plane**：保存冻结输入、结果标签、代理口径和验证状态；
5. **Answer plane**：继续使用 AnswerCard v0 `body_rows`，只读消费已发布数据。

事实、模型假设、人类决定和结果标签必须分层保存。任何 review decision 不得覆盖原始事实。

### 4.1 `valuation_episode_v1`

- 一段连续 ST 状态是一轮 valuation episode；
- 摘帽/退出 ST 后再次进入，开启新 episode；
- 同一连续区间内方案失败、重新招募或程序终结是状态变化，不自动拆成独立样本；
- 重整事件作为 episode 内节点，复用 M6/P6A 词汇和来源引用；
- M6 `case_note_only` 只能生成候选，生产阶段标签必须重新核证；
- 同一公司多轮 episode 可以保留，统计推断按公司聚类。

P6B 阶段词表：

1. `st_distress_only`；
2. `restructuring_application_disclosed`；
3. `pre_restructuring_started`；
4. `formal_restructuring_accepted`；
5. `investor_recruitment`；
6. `plan_key_terms_disclosed`，从此节点进入 P6C 输入边界。

## 5. 冻结指标与计算规则

### 5.1 同日 ST 市值位置

对估值日历史 ST membership 中有效总市值升序排列，使用平均秩处理并列：

`percentile = (average_rank - 1) / (valid_count - 1)`

输出绝对总市值、百分位、有效样本数、membership 数、覆盖率和价格陈旧状态。百分位只描述
规模位置，不进入“便宜/昂贵”结论。

冻结门：

- 总市值必须按交易日调用 `daily_basic` 整市场截面，再按当日 membership 过滤；
- 同一个锚点交易日只请求一次，不按股票逐只拉取；
- 有效样本至少 20 家；
- 有效市值覆盖率低于 95% 时不输出分位；
- 目标公司估值日停牌时不生成“当前分位”，只显示最后有效分位及距估值日交易日数；
- v1 初始发布不使用陈旧市值补足 cohort 覆盖；成员缺当日市值即进入 coverage gap。
  “不超过 5 个交易日且期间没有已知股本变化”保留为未来可晋级规则，只有独立
  point-in-time 资本结构 guard 完成后才能启用；
- P6B-0 另报告 0/5/20 个交易日陈旧容忍下的历史覆盖，但不得根据后续收益调整规则。

### 5.2 自身历史分位和 cohort 换手

v1 固定显示当前值与 12 个月前值，不做多窗口择优。同期 cohort 换手定义为：

`turnover = 1 - |members_start ∩ members_end| / |members_start ∪ members_end|`

必须同屏显示起止成员数和换手率。换手率高于 30% 时标记
`membership_composition_noise`；仍可展示数值，但不得把分位变化归因于公司重定价。

### 5.3 Episode 相对重定价

市值变化包含价格效应和股本效应，不能直接减去价格指数收益。主指标使用同口径财富指数：

`episode_relative_repricing`

`= (stock_qfq_end / stock_qfq_anchor)`

`  / (st_equal_weight_ex_target_end / st_equal_weight_ex_target_anchor) - 1`

冻结规则：

- v1 主锚点是本轮 `st_status_start` 前最后一个个股与 ST 指数共同有效交易日；
- 终点是估值日或估值日前最后一个共同有效交易日；
- ST 等权按历史 membership 逐日计算并排除目标公司，避免目标收益污染自身基准；
- ST 等权路径每日至少 20 个排除目标后的有效成员；95% 作为必须同屏展示的覆盖警告线，
  不与同日市值截面的 95% fail-closed 门混用；
- 缺端点不插值；
- 2021-03-17 之前 ST 等权不可用时返回 gap，不用中证全指替代；
- 中证2000和中证全指只作并列市场语境；
- 指标名称固定为“episode 相对重定价”，不称 alpha、资金流或最大回撤；
- 发生股本变化但缺少精确老股东权益账时，标记
  `capital_structure_contaminated`，不输出精确重定价；
- 价格锚点使用入 ST 前共同端点；资本结构和总市值拆分锚点使用首个 ST 日，避免在
  ST-only factor snapshot 中查找尚未入池的目标公司；
- 总市值变化另行拆成价格效应和股本效应，仅作描述。

### 5.4 同阶段历史描述

每个核证 episode 在其锚点日先计算“同日 ST 市值分位”和 episode 相对重定价，再跨年份
汇总相同阶段。不得拿不同年份的绝对亿元数直接比较。

上线门：

- 所用阶段标签 100% 来自 `valuation_episode_v1` 核证事实；
- 至少 20 个 episode 且至少 15 家不同公司；
- 门槛在 P6B-0 前冻结，之后只许上调、不许下调；
- 不满足门槛时只列案例，不输出分位；
- 输出必须携带 episode 数、公司数、年份范围、阶段口径和公司聚类说明；
- 经营状态、审计可信度、净资产正负和市场状态在 v1 只作描述字段，不交叉切格。

市场语境按可用版本明确显示：

- 2016-01-04 起：中证全指；
- 2021-03-17 起：增加 ST 等权；
- 2023-08-11 起：增加中证2000；
- 缺失基准标记 unavailable，不倒算、不替代。

### 5.5 资产、偿债缺口与目标公司残差

`adjusted_net_assets = verified_recoverable_assets - known_obligations`

`equity_asset_backing = max(adjusted_net_assets, 0)`

`solvency_gap = max(-adjusted_net_assets, 0)`

资产状态必须是：

- `positive`：证据满足门槛且区间为正；
- `negative`：证据满足门槛且区间为负；
- `unknown`：关键资产、负债或权利状态不足。

折价率没有独立回收样本时，合法输出是逐项列示和 `uncalibrated`，不得强行形成资产区间。
缺失负债敏感度挂在 `solvency_gap` 上，不挂在市场残差上。

仅当资产状态为 `positive` 或 `negative` 时，目标公司可展示：

`market_pricing_residual = current_market_cap - equity_asset_backing`

该残差不与历史样本横向比较，不等同壳价值，也不与资产底座相加。资产状态为 `unknown`
时残差必须为 `not_calculable`，禁止默认底座为零。

## 6. 结果观察与验证

### 6.1 两条独立验证线

**资产事实线**：

- 使用后续评估、处置、回收和真实偿付验证资产/负债组件；
- 区分当时可见事实、后来新披露事实和模型错误；
- 样本不足时保持 `uncalibrated`，不以同一批案例训练并验证。

**市场结果线**：

- 输入冻结在估值日，不使用未来方案事实；
- 12 个月为主观察窗，6/24 个月为辅助；
- 正式方案、失败、摘帽、再次 ST 和退市作为结果标签，不因结构事件删除成功或失败样本；
- 历史回放与上线后的前瞻样本分开报告；
- v1 只做 shadow 验证，不向用户发布“估值偏离”标签。

### 6.2 老股东权益与退市

qfq 价格不能单独证明转增、受让和稀释后的老股东财富。P6B-2 先在 5–10 家试点建立最小账：

- 每股权益调整/稀释系数；
- 转增股份中原股东、投资人、债权人的归属；
- 受让对价；
- 事件前后总股本和老股东实际保留权益；
- 来源及 `available_as_of`。

试点中超过一半无法精确闭环时，全量主口径直接采用范围输出，不追求假精确。

退市但缺少可靠老三板/最终清偿数据时同时报告：

- `total_loss_stress`：按 -100% 的压力情景；
- `last_exchange_observable`：按交易所最后可观察价格的退出代理。

二者不是数学上下界。若结论随代理口径翻转，标记 `terminal_value_unstable`。

### 6.3 验证状态

- `descriptive_only`：只有可复算描述，不作价格判断；
- `historical_backtest_only`：完成历史回放，尚无前瞻样本；
- `forward_observation`：显示已完成样本数和观察窗；
- `unvalidated`：样本或结果不足，允许长期保持；
- `validated`：只能由未来独立 PR 在预注册门槛满足后发布。

“永远未验证”是合法产品状态，不能靠降低样本门槛消除。

## 7. AnswerCard 与用户界面

复用 AnswerCard v0 `body_rows`，稳定行类型：

- `P6B信息边界`；
- `P6B资产负债事实`；
- `P6B偿债压力`；
- `P6B同日ST规模位置`；
- `P6Bepisode相对重定价`；
- `P6B资本结构警告`；
- `P6B同阶段案例`；
- `P6B证据缺口`；
- `P6B验证状态`。

默认顺序是：

1. 信息覆盖和新增不利事实；
2. 资产状态、偿债缺口和资本结构；
3. 市场规模位置与相对重定价；
4. 历史案例和验证状态。

即使价格落入低分位或相对重定价很差，第一解释也必须是“市场可能掌握了系统尚未覆盖的
不利信息”，完成缺口排查后才能讨论其他可能性。

## 8. 人类参与：最小化、批量化、只审决策

### 8.1 人类不需要做

用户不需要：

- 审核估值数字是否“专业”；
- 逐公司选择折价率；
- 阅读全部公告或 270 条 episode；
- 给每个经营状态、审计意见或重整节点手工贴标签；
- 每日批准数据刷新；
- 判断统计显著性或手工挑可比公司；
- 为模型结果背书。

这些工作由确定性规则、来源回链、覆盖门、自动测试和 fail-closed 承担。

### 8.2 人类只做四类高杠杆决定

1. **一次性规则确认**：查看 P6B-0 的覆盖报告，确认历史起始边界和停牌陈旧规则；
2. **pilot 例外批审**：只看会改变资产状态、episode 边界或老股东权益的冲突簇；
3. **词表边界确认**：对 3–5 个代表例和 1–2 个反例作 cluster 级决定，不逐条审核；
4. **发布门选择**：根据自动验收报告选择 `继续 shadow`、`发布描述能力` 或 `退回补数据`。

### 8.3 Review budget 与固定选项

每一批 review 最多 10 个 decision cluster、每簇显示 3–5 个代表例。超过预算时不扩大人审，
而是退回改抽取规则、缩小 pilot 或保持 unknown。

每张 review card 必须包含：

- 需要决定什么；
- 为什么被提出；
- 系统推荐及原因；
- 代表例、反例、来源指针；
- 接受该决定会一次解决多少条记录。

固定选项优先使用：

- `accept_suggested`；
- `accept_current`；
- `mark_boundary`；
- `need_more_evidence`；
- `reject`。

自由文本只作备注，不驱动机器行为。决定写入独立、幂等的 review-decision 层，不覆盖事实。
已解决的 decision family 从下一批队列消失；只有新冲突和新边界再次出现。

### 8.4 日常人类工作量

- P6B-0：一次规则摘要确认；
- P6B-2/3 pilot：各最多一批例外 review；
- 发布前：一次验收摘要确认；
- 日常刷新和普通问答：默认零人审；
- 新证据产生高影响冲突时：只把对应 decision cluster 放入下一批。

系统无法在 review budget 内收敛时，产品应缩小结论或返回 unknown，不能把自动化缺口转成
持续的人肉标注工作。

## 9. 分阶段实施与停止条件

### P6B-0 — 只读 dry plan

- 以 `st_membership_daily` 构造连续候选 valuation episode；`st_status_history`
  只作来源交叉核查；
- 计算唯一锚点交易日、按交易日整市场请求量和本地已有覆盖；
- 按年代盘点目标/成员停牌率、0/5/20 日陈旧覆盖和 95% 门通过率；
- 盘点股本跳变、退市终点、市场基准版本和 M6 候选阶段覆盖；
- 输出 source-probe 样本计划，不写生产库、不请求网络。

随后单独执行小规模 read-only provider probe，验证历史 `daily_basic` 和转增附近股本可得性。
probe 不写 canonical 数据。

停止条件：没有可支持的历史区间、请求量不可控或股本事实无法闭环时，先缩小历史范围，
不得进入综合实现。

2026-07-24 的真实只读盘点已完成，结果见
[P6B0_DRY_PLAN_RESULT.md](P6B0_DRY_PLAN_RESULT.md)。候选 inventory 可从
2016-08-09 开始，但本地 qfq 代理没有形成连续通过 95% 门的区间，且历史股本变化 guard
尚不可用。

随后完成的 [P6B0_PROVIDER_PROBE_RESULT.md](P6B0_PROVIDER_PROBE_RESULT.md) 证明
Tushare `daily_basic` 从 2016-08-09 起具备历史 `total_share` / `total_mv` 字段能力，
可以启动 306 个锚点日的 scoped backfill。但 11 个冻结截面仅 3 个通过 95% 门，失败日期
跨年份非单调，因此不再声称存在单一连续“可发布历史边界”：每个锚点日独立过门，失败
日期返回 `unavailable`。陈旧市值保持关闭，老股东权益 guard 继续留在 P6B-2。

### P6B-1 — 市场地图

- 历史锚点 market-cap 快照；
- 同日 ST 规模位置、12 个月自身变化和 cohort 换手；
- episode 相对重定价、基准缺口和资本结构污染门；
- 仅发布 `descriptive_only`。

P6B-1a 已于 2026-07-24 完成锚点回填与同日规模位置计算，结果见
[P6B1_MARKET_CAP_BACKFILL_RESULT.md](P6B1_MARKET_CAP_BACKFILL_RESULT.md)：
306/306 个交易日锚点均有 append-only snapshot 和 dated manifest，103 日通过 95% 门，
203 日 fail closed。原始 episode 起点若不是交易日，固定映射到下一个中证全指交易日并
在 plan 中记录调整；当前唯一调整是 2026-07-12 → 2026-07-13。

P6B-1a 只完成“同日是谁”：总市值、平均秩分位、样本和覆盖。固定 12 个月自身变化、
cohort 换手、episode 相对重定价、价格/股本效应及 AnswerCard 接入属于 P6B-1b，不得把
本阶段模块冒充完整 P6B-1。

P6B-1b 已于 2026-07-24 完成，结果见
[P6B1B_MARKET_REPRICING_RESULT.md](P6B1B_MARKET_REPRICING_RESULT.md)。实现包括：
停牌目标最后有效位置与交易日距离、固定 12 个月位置变化和成分换手、排除目标的 ST
等权相对重定价、中证2000/中证全指语境、首个 ST 日至估值日的股本污染门、总市值的
价格/股本乘法分解，以及 AnswerCard v0 `descriptive_only` 行。比较日 2025-07-17
补充 snapshot `MFS-1179A0B220A7445A687F` 通过 95% 门，历史写入没有倒退 current
pointer。P6B-1 只交付市场地图；资产、核证阶段分布与 UI 路由仍属于 P6B-2 以后。

### P6B-2 — 资产与老股东权益 pilot

- 选择 5–10 家资产结构和结果不同的公司；
- 材料化 point-in-time 资产、负债、担保、诉讼、资金占用及重述；
- 建立最小老股东权益账；
- 无校准样本时只列示，不启用收益法或综合估值。

2026-07-27 pilot 已完成：8 家当前开放 episode 的财务和风险披露事实可自动
point-in-time 留痕，但 8/8 都缺独立核证的可回收资产和完整义务区间，因此资产状态保持
`unknown`，市场残差保持 `not_calculable`。老股东权益账 0/8 精确闭环，超过预注册门槛，
后续全量主口径固定为范围/unknown。历史程序结果和退市终值样本留给 P6B-4，不作为本轮
输入；详见 `P6B2_ASSET_EQUITY_PILOT_RESULT.md`。

### P6B-3 — 核证 valuation episode

- 复用 M6/P6A 词表和来源索引；
- 以 cluster 级规则核证阶段，旧 `case_note_only` 不自动晋级；
- 处理重复 ST、连续区间、方案失败和 P6B/P6C 边界。

### P6B-4 — 同阶段描述与 shadow validation

- 满足 20 episode / 15 公司门后才输出阶段分布；
- 运行历史回放、退市双代理和公司聚类统计；
- 独立记录上线后的前瞻样本；
- 仍不发布“估值偏离”或交易标签。

### P6B-5 — Answer/UI integration

- 只接入达到对应验证状态的行类型；
- 缺口、陈旧、样本量和验证状态与数字同屏；
- 不发布不必要的新顶层 AnswerCard contract。

P6B 各阶段独立提交、独立回滚；不得与 P6C 混在一个 PR。

## 10. 测试与验收

- point-in-time 泄漏：重述、方案和后来发现的负债不得进入历史输入；
- membership：禁止用当前 ST 名单倒算历史；
- market cap：同日截面、并列秩、95% 覆盖、停牌陈旧和股本变化；
- episode：重复 ST、连续区间、失败后继续、方案边界和公司聚类；
- relative repricing：共同端点、2021-03-17 历史边界、无插值和资本结构污染；
- assets：会计恒等、单位、来源、positive/negative/unknown 三态传导；
- residual：unknown 时必须 `not_calculable`；
- terminal value：-100% 压力情景、最后交易所代理及翻转警告；
- review：cluster 去重、固定选择、幂等导入和 review budget；
- AnswerCard：低分位不生成便宜/低估/底部叙事；
- regression：P4、C14、P6A 和冻结 AnswerCard v0 契约继续通过。

## 11. 明确不做

- 固定壳价值；
- 资产价值加壳价值；
- 用历史样本账面净资产冒充统一资产底座；
- v1 收益法；
- 六维交叉匹配或调到有结果为止的放宽；
- 依靠同日规模分位判断便宜/昂贵；
- 只回测存活、摘帽或成功案例；
- 用 qfq 或市值变化偷换老股东真实回报；
- 让人类逐条审核自动抽取结果。
