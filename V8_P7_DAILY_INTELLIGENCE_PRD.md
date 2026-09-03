# v8 P7 PRD：每日公告、异常量价与研究优先级

状态：approved for staged implementation；P7-0 contract frozen，尚未执行 provider probe
日期：2026-09-04
负责人：Codex commander window
实施基线：`codex/leibniz-portable-workspace` commit `130ca0d` 之上
依赖：P4 market context；P5-C14；P6B 已核证 valuation episode；现有公告与价格维护器
执行账：[.todos/004.md](.todos/004.md)
dry-plan 契约：[V8_P7_0_DRY_PLAN_CONTRACT.md](V8_P7_0_DRY_PLAN_CONTRACT.md)

## 1. 决策与目标

P7 把两个独立事实流接到同一条研究队列：

1. **P7A 每日公告地图**：按正式公告内容分组，识别会改变公司状态或研究判断的公告，
   并持续维护每只公司的程序状态；
2. **P7B 异常量价地图**：识别相对公司自身历史显著异常的自由流通换手和同期价格表现，
   但不把成交活跃解释成资金流入；
3. **P7C 研究优先级**：把公告、量价异常、市场语境、P6 资产/重整事实和证据缺口连接成
   待研究队列；
4. **P7D shadow validation**：验证异常是否在硬状态节点之前出现、是否只是交易所已经公开
   标记的波动，以及它能否稳定减少研究遗漏；
5. **P7E 后续估值联动**：只有 P6B/P6C 输入达到各自证据门时，才展示估值语境。P7 v1
   不产生买入、卖出、持有或仓位建议。

用户每天应先看到“发生了什么、哪些值得先查、为什么值得查、证据是否完整”，而不是一个
把公告、成交量和估值混成黑箱的股票评分。

## 2. 冻结边界

以下规则已经由 owner 确认，后续实现不能通过调参或改文案绕过：

1. **研究优先级不等于买入信号。** 排在前面只表示更值得先补证或跟踪，不表示预期收益更高。
2. **不使用“资金流入”“主力埋伏”等因果词。** 日线成交只能证明换手和价格发生异常；参与者
   身份、方向和动机未知。
3. **公告与量价先独立计算，再做时间连接。** 公告分类不能抬高此前的量价异常，量价异常也
   不能改变公告事实标签。
4. **shadow 先于发布。** P7B/P7C 先保存但不对用户生成行动性排序；P7A 的正式公告事实流可
   独立验收、独立发布。
5. **C14 复用、不重做。** P7 使用已有 `daily_basic` provider 和时点股本/市值能力，但连续
   每日活动事实进入新的 `market_activity_v1`，不扩写 C14 的估值锚点语义。
6. **主换手口径是 `turnover_rate_f`。** 普通 `turnover_rate` 和厂商 `volume_ratio` 仅作旁证；
   `volume_ratio` 不进入主异常判定。
7. **硬节点只认状态跃迁。** 普通进展公告可以提高阅读优先级，但不能作为 P7D 的成功结果。
8. **官方来源优先。** CNINFO/交易所公告是公司事实来源；雪球等第三方内容只可参考信息组织
   方式，不能进入正式事实层。

## 3. 用户每天得到什么

每日页按固定顺序显示：

1. **覆盖状态**：公告、价格、`daily_basic`、停复牌、涨跌停和 ST membership 是否到同一日期；
2. **硬状态变化**：法院受理/不受理、协议签约/终止、计划批准、控制权完成、摘帽/退市决定、
   审计意见类型变化；
3. **重点公告**：按类别列示，解释“为什么值得先读”，回链正式公告；
4. **异常量价**：只描述自由流通换手、价格、振幅、相对 ST/中证2000语境和排除状态；
5. **联动研究队列**：哪些公司同时出现新公告、此前量价异常或重大证据缺口；
6. **持续观察**：已有研究线程的新节点、未解决缺口和下一次检查条件。

页面必须始终显示：

> 异常量价只表示相对历史的交易活跃变化，不证明资金主体、方向、内幕信息或未来收益。

## 4. 架构评审

### 4.1 当前架构

现有 v8 已有权威 ST membership、逐股 qfq 价格、CNINFO 公告索引及按需正文、三基准市场
语境、C14 时点市值、P6 valuation episode、EvidencePack、AnswerCard 和研究运行账本。

当前缺口是：普通价格刷新没有连续换手率/振幅；C14 `daily_basic` 快照只覆盖估值锚点且未取
`turnover_rate_f`、`volume_ratio`、`limit_status`；没有停复牌/涨跌停活动事实层；公告只有
逐条索引，没有跨公告的发行人状态机；也没有预注册的异常 episode 和 shadow ledger。

### 4.2 如果今天从零设计

仍会把系统拆成五层：

1. 原始公告与市场活动事实；
2. 可复算的公告分类、发行人状态和量价特征；
3. 不含未来事实的异常与联动 episode；
4. 独立 shadow 结果账；
5. 只读消费上述发布物的研究界面。

不会让 LLM 每天重新阅读全市场公告后直接打分，也不会把高频活动字段塞进估值快照库。

### 4.3 方案比较

| 方案 | 优点 | 风险 | 决定 |
| --- | --- | --- | --- |
| 在现有 `daily_prices` 增几列并直接排名 | 改动小 | 历史空值、停复牌和 provider 语义混杂 | 拒绝 |
| LLM 全量读公告并给“机会分” | 快速演示 | 不可复算、成本高、会滑向交易信号 | 拒绝 |
| 新建完整行情/公告平台 | 边界整齐 | 重复现有成熟底盘，迁移成本过高 | 拒绝 |
| 独立活动事实层 + 状态机 + shadow ledger，复用 v8 底盘 | 可审计、渐进发布、失败可降级 | 多一个版本化数据面 | 采用 |

这是 hybrid 扩展：保留现有事实底盘和答案主链，只新增 P7 特有的连续活动、状态机与验证层。

## 5. P7A：每日公告地图

### 5.1 分类词表

每条公告先进入以下稳定类别之一；附件和同日连续公告可以合并为同一个 evidence bundle，
但原始公告记录不得丢失：

- `restructuring_and_pre_restructuring`：预重整、重整、投资人、债权、计划及执行；
- `risk_warning_and_delisting`：风险警示、撤销风险警示、终止上市和退市整理；
- `control_and_ownership`：控制权、实际控制人、司法拍卖和权益变动；
- `litigation_guarantee_occupation`：诉讼、担保、资金占用和追偿；
- `audit_and_financial_reporting`：财报、业绩、审计意见和会计差错；
- `asset_and_major_transaction`：重大资产交易、出售、收购、重组和资产处置；
- `operations_and_production`：停产、复产、许可、重大合同和经营异常；
- `capital_structure_and_shareholder`：增减持、回购、解禁、股本和股份冻结；
- `regulatory_and_discipline`：立案、处罚、问询、纪律处分和整改；
- `routine_or_other`：不能进入上述类别的日常事项。

分类优先顺序固定为：CNINFO 元数据粗分 → 标题/正文确定性规则 → 发行人状态机 → 仅对入围或
冲突正文使用 LLM。LLM 输出是带来源的候选，不能覆盖公告原文或确定性事实。

### 5.2 发行人状态机

P7 不建立第二套重整阶段真值。重整维度复用 `valuation_episode_v1` 和 P6A/P6B 词表；
风险警示、控制权和审计意见使用各自独立维度。每个跃迁至少保存：

- `symbol`、`dimension`、`from_state`、`to_state`；
- `announced_at`、`effective_at`、`available_as_of`；
- 正式来源、公告 bundle 和抽取版本；
- `verified`、`provisional` 或 `conflicted`；
- 与旧状态不一致时的冲突原因。

P7D 主硬节点只包括：

- 法院受理、不受理、终止预重整/重整；
- 重整投资协议或正式投资人协议签约、解除或终止；
- 法院批准、不批准或终止重整计划；
- 控制权变更完成；
- 撤销风险警示、终止上市或退市决定；
- 审计意见类型发生变化。

申请、招募、风险提示和一般进展可以形成 `stage_event`，但固定标记 `not_hard_outcome=true`。

### 5.3 重点公告规则

“重点关注”只表示研究影响，不表示利好或利空。至少命中一项才能进入重点区：

- 形成上述硬状态跃迁；
- 新增会改变 P6 资产、偿债、股本或控制权判断的正式事实；
- 同一公告 bundle 内存在重要数值、主体或生效日冲突；
- 使既有研究结论过期，或关闭/新增一个 blocking evidence gap；
- 已进入跟踪线程且到达预先登记的复查条件。

## 6. P7B：异常量价地图

### 6.1 数据面

新增 append-only `market_activity_v1.sqlite3`，保存 provider 原始活动字段、派生值、覆盖和
内容摘要；不复制公告正文，不改变 `market_factors_v1`。每日活动最小字段为：

- 原始日线：`open`、`high`、`low`、`close`、`pre_close`、`pct_chg`、`vol`、`amount`；
- `daily_basic`：`turnover_rate_f`、`turnover_rate`、`volume_ratio`、`total_share`、
  `float_share`、`free_share`、`total_mv`、`circ_mv`、`limit_status`；
- `suspend_d`：停复牌类型和日内停牌时段；
- `stk_limit`：`pre_close`、`up_limit`、`down_limit`；
- 当日 ST membership、三基准 manifest、来源、抓取时间和字段覆盖。

`daily_basic` 必须显式请求 `limit_status`。一字板主识别使用 `limit_status in {3,6}`；
`stk_limit + raw OHLC` 用于复核和缺失回退。两者冲突时标记 `limit_state_conflict`，不进入
可发布异常列表。振幅固定使用原始未复权价格计算：

`amplitude_pct = (raw_high - raw_low) / raw_pre_close * 100`

`raw_pre_close <= 0` 或字段缺失时返回 unknown，不从厂商 `volume_ratio` 反推。
`suspend_d` 按日期成功返回后，某股票没有停牌记录才可解释为当日未停牌；请求失败或日期
覆盖未知时，记录必须保持 `suspension_status_unknown`，不能把“没抓到”解释成“没有停牌”。

### 6.2 主异常口径

对每个 symbol 使用当前日前 120 个合格交易日作为历史窗，至少需要 60 个有效观察；当前日
不得进入自己的基线。

主输入只有 `turnover_rate_f`：

`turnover_percentile_120 = 当前值在历史窗内的平均秩分位`

`turnover_robust_z_120 = 0.67448975 * (当前值 - median_120) / MAD_120`

P7-0 固定比较三个预注册 profile：

| Profile | 历史分位 | robust z | 用途 |
| --- | ---: | ---: | --- |
| `broad` | ≥ 95% | ≥ 3 | 保存宽口径候选 |
| `balanced` | ≥ 97.5% | ≥ 4 | P7-1 默认 shadow 口径 |
| `strict` | ≥ 99% | ≥ 5 | 高强度旁证 |

两项需同时满足。`MAD=0` 时 robust z 为 unknown，不人为加入极小分母；如果当前值高于全部
历史值，只登记 `zero_mad_breakout` shadow 候选，不进入默认 profile。

普通换手率、厂商量比、成交额、成交量、振幅、1/3/5 日 qfq 收益、相对排除目标后的 ST
等权收益和中证2000语境全部是描述字段，不进入 profile 判定。

### 6.3 合格交易日与排除

以下记录不生成默认异常：

- 当日不在 point-in-time ST membership；
- 停牌或缺少明确停复牌状态；
- 一字涨停或一字跌停；
- 已进入核证的退市整理期；
- 当前 `turnover_rate_f` 缺失，或历史窗不足 60 个有效观察；
- `daily_basic`、价格或日期发生主体/交易日冲突；
- limit 状态两来源冲突且无法确定。

复牌首日和长期停牌后的恢复期单列 `post_suspension`；P7-0 先报告数量和不同 guard 对覆盖的
影响，再冻结公开口径。未核证退市整理边界的公司不能静默混入，标记
`terminal_phase_unknown` 并排除公开队列。

### 6.4 异常 episode

原始每日命中必须保留。为了避免连续放量被当成多个独立发现，P7-0 比较 3/5/10 个合格交易日
的合并间隔，只能按研究队列负荷冻结，不得查看后续硬节点后择优。P7-1 默认使用 5 日间隔，
以首次命中作为 episode 起点，并保留峰值和全部成员日。

## 7. P7C：公告与量价联动

P7C 只做时间连接，不把两个弱证据相乘成强结论：

- `activity_before_announcement`：异常 episode 在公告/节点前已经开始；
- `same_day_activity`：异常与公告同日，不能声称领先；
- `activity_after_announcement`：更可能是公开信息后的交易反应；
- `announcement_without_activity`：公告重要但未见合格量价异常；
- `activity_without_announcement`：只说明暂未覆盖到对应正式公告，优先做信息缺口排查。

研究队列可以使用 `investigate_now`、`monitor`、`context_only` 三档，但每条必须显示确定性
原因；不得输出综合机会分、胜率、目标价或预期收益。P6B/P6C 只作为并列估值语境，不改变
P7B 原始异常是否成立。

## 8. P7D：shadow validation

### 8.1 两条主验证线

**方法正确性线**：字段覆盖、point-in-time membership、停复牌/一字板排除、基线不含当前日、
异常 episode 去重和公告状态机均可复算。

**研究价值线**：预注册主结果为异常 episode 起点后 20 个交易日内是否出现硬状态节点；
5/10/60 日为辅助窗。对照从同日合格但未触发的 ST 股票中匹配，不使用未来事实，至少并列
报告当日市值规模位置、重整阶段和市场语境；推断按公司聚类。

交易所公开标签另设一条不与硬节点混算的对照：

- `stk_shock`：个股异常波动；
- `stk_high_shock`：严重异常波动；
- `stk_alert`：重点提示证券。

如果接口可用，异常日前或同日已经被交易所公开标记，记为 `already_publicly_flagged`，降低
新颖性但不删除事实；异常后才出现标记时记录领先交易日数。接口不可用则保持 pending，
不阻塞 P7A/P7B 的事实与 shadow 建设。

后续收益只作描述性安全检查，不是 P7 是否成功的主指标。不得根据收益调整 P7B 阈值。

### 8.2 分层发布门

- **P7A 公告事实流**：分类和状态机通过来源、冲突与覆盖测试后可独立发布；
- **P7B 描述性异常**：完成历史回放和至少 60 个交易日前瞻 shadow 后，才能考虑发布；60 日
  只是最短观察期，不代替独立 anomaly episode 样本门；即使发布，也只能称“异常交易活跃”；
- **P7C 联动优先级**：只有硬节点对照和研究工作量均有稳定报告后才可发布。P7D 实现前必须
  另行冻结最小 episode/公司数、对照可用率和不确定性报告规则；没有增益时长期保持 shadow；
- **交易或估值偏离标签**：不属于 P7 v1，不能通过改文案提前上线。

## 9. P7-0 必须先回答的问题

P7-0 是只读盘点加有界 provider probe，不能先写生产库。必须回答：

1. 当前账号是否真实可调用 `daily_basic`、`suspend_d`、`stk_limit`，以及实际频率/积分边界；
2. `turnover_rate_f`、显式请求的 `limit_status` 和其他必需字段在各年代是否连续；
3. 最新已核证 ST universe（现有基线快照为 209 只）和历史 membership 中有多少
   symbol-day 能满足 60/120 日基线；
4. 停牌、一字板、复牌恢复期和退市整理期各排除多少记录；
5. 三个 profile 每日触发数的平均、中位、P90、最大值及跨年份/市场阶段分布；
6. 异常是否集中在少数股票，以及 3/5/10 日合并后独立 episode 数；
7. 三个交易所参考接口是否有权限、覆盖何时开始；
8. 需要多少 date-only 请求、当前账号完成一次历史回填和每日增量的实际预算；
9. P7A 可以独立开工还是被公告/状态边界阻塞；P7B/P7C 应继续、缩窗还是保持 shadow。

平均触发数不是唯一容量指标。页面未来可以只显示 Top-N，但 canonical ledger 必须保存所有
合格异常和 overflow 数，不能让展示上限改变历史真值。

## 10. 人类参与

owner 不需要逐公告分类、逐股票确认异常、猜测资金身份、选择历史窗口或每天批准刷新。
系统承担确定性分类、来源回链、覆盖检查、异常计算、去重、对照和 fail-closed。

人类只保留两个发布级决定：

1. P7-0 完成后查看一页摘要；只有 provider 权限或历史边界存在实质取舍时才需要决定，
   否则自动采用 safe default；
2. shadow 达到预注册观察期后选择 `keep_shadow`、`publish_descriptive_only` 或
   `return_to_data_gap`。

任何需要持续逐条人工标注才能运行的方案均视为 P7 设计失败，应改规则或保持 unknown。

## 11. 实施顺序

1. **P7-0a local inventory**：只读盘点本地活动字段、membership、停牌代理、公告类别、
   硬节点候选、退市边界和请求量；
2. **P7-0b provider probe**：小样本核验当前账号权限、显式字段、历史覆盖和速率；
3. **P7A announcement state machine**：P7-0a 公告库存确认后即可独立实施；
4. **P7-1 market activity plane**：通过 provider 出口门后扩展 provider，建立 append-only
   活动快照、manifest、checkpoint 和每日增量；P7A 与本步骤可以并行；
5. **P7B anomaly engine**：只在 P7-1 数据契约稳定后实施；
6. **P7C linkage queue**：只消费 P7A/P7B 发布物，不回写事实；
7. **P7D shadow ledger**：历史回放与前瞻观察分开；
8. **P7E Answer/UI/operations**：按分层发布门接入，未过门能力保持隐藏或明确 shadow。

P7A 不因交易所参考接口无权限而阻塞。P7B 发布依赖可靠的换手、停复牌和一字板状态；
P7C 依赖 P7A/P7B，但不依赖 P6B-4/5 完成。估值联动只能消费已发布的 P6 能力。

## 12. 主要风险与止损点

- **provider 配额不足**：缩小历史回放，不自动换供应商或逐股爆破请求；
- **自由流通股本口径跳变**：保存原始股本字段和变动警告，不能把口径变化解释成真实放量；
- **MAD 退化**：返回 unknown/zero-MAD 候选，不塞极小分母制造大 z-score；
- **公告过度命中**：硬节点只认状态跃迁，一般进展不进入主验证；
- **重复报警膨胀**：原始日命中与合并 episode 分开保存；
- **交易所标签反向泄漏**：阈值冻结不读取未来交易所标签或硬节点结果；
- **幸存者偏差**：使用 point-in-time membership，保留退市、失败和没有后续节点的样本；
- **研究优先级被误读**：界面不显示机会分和预期收益，固定风险文案；
- **两套状态真值**：重整阶段必须引用 P6 valuation episode，不在 P7 中另造；
- **人工审核膨胀**：超过自动规则能力时保持 conflict/unknown，不转成人工流水线。

## 13. 外部接口依据

- [Tushare 每日指标 `daily_basic`](https://tushare.pro/document/2?doc_id=32)
- [Tushare 每日涨跌停价格 `stk_limit`](https://tushare.pro/document/2?doc_id=183)
- [Tushare 每日停复牌信息 `suspend_d`](https://tushare.pro/document/2?doc_id=214)
- [Tushare 个股异常波动 `stk_shock`](https://tushare.pro/document/2?doc_id=451)
- [Tushare 个股严重异常波动 `stk_high_shock`](https://tushare.pro/document/2?doc_id=452)
- [Tushare 交易所重点提示证券 `stk_alert`](https://tushare.pro/document/2?doc_id=453)

接口文档只证明声明能力和积分要求；P7 是否可用必须由当前账号的有界 probe 和真实字段覆盖
决定，不能用文档替代验收。
