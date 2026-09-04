# v8 P8 PRD：研究漏斗、分阶段成交情景参考与前哨链

状态：architecture frozen；P8-0 与首轮工程物化完成；正文 LLM 授权及 10/60 日真实前瞻门待完成
日期：2026-09-04
负责人：owner 起草，Codex commander window 实施
修订对象：[V8_P6B_PRD.md](V8_P6B_PRD.md) §1/§2.2/§11、[V8_P7_DAILY_INTELLIGENCE_PRD.md](V8_P7_DAILY_INTELLIGENCE_PRD.md) §2/§5.3/§8、[V8_P7_BACKTEST_CONTRACT.md](V8_P7_BACKTEST_CONTRACT.md) §4/§5
依赖：P6B-3 核证 valuation episode（912 个，460 个 verified 边界）；C14 时点市值；P7A 状态机（491 个标题规则硬跃迁）；`market_activity_v1`（373 个交易日）
不改动：P7 数据面、point-in-time 规则、防泄漏规则、fail-closed 规则

## 0. 一句话

P6B/P7 把"对外宣称的纪律"套在了"研究范围"上，结果是研究目标本身被禁令排除，
系统只能回答"没有预测力"。P8 把边界拆成两层：**研究层放开方向、收益、壳成交情景和
筹码代理；宣称层保留全部现有措辞纪律。** 然后用已有数据做三件 owner 真正要的事：
分阶段成交情景参考、前哨公告链、累积型量价与筹码代理，最后汇成每日候选漏斗。

## 1. 为什么修订

首轮 P7 回测（`P7BT-35434858D1CD7665038F`）工程质量高、防泄漏正确、结论保守，
但它验证的代理与 owner 的两个研究目标不对齐：

| owner 目标 | P6B/P7 现状 | 后果 |
| --- | --- | --- |
| 拣选短/中/长期有**正面**意义的公告及其前哨 | "重点关注不表示利好或利空"；非硬节点一律 `not_hard_outcome` | 结果变量把"批准重整计划"和"终止上市决定"算作同一种命中；预重整申请、招募投资人等前哨没有结构化后继关系 |
| 研究公告前的持续交易活跃形态与估值位置 | 禁词"主力/吸筹"；主 profile 只测单日换手尖峰；"不得根据收益调整阈值" | D4 留出命中率最低只能证明单日尖峰代理不稳定，不能据此判断参与者或断言追涨；价格结果没有进入主验证 |
| 有信号就去比较、去挖掘 | 发布门 precision-first：80% 对照、Wilson 区间分离、60 日前瞻 | 池子里出不来东西；研究漏斗没有候选可挖 |
| 壳成交情景 / 阶段性估值参照 | P6B §1 "不把资产底座与壳价值相加"、§2.2 "不输出底部、低估" | `p*` 公式已写在 P6 PRD §6.3，但成功、失败值尚未统一为同一老股东权益口径 |

这些禁令在 PRD 中标为"owner 确认"，owner 现在明确收回其中作用于**研究层**的部分。

## 2. 两层边界（本 PRD 的核心冻结规则）

### 2.1 研究层（owner 私有，允许）

- 为公告、硬节点、stage_event 分别标注程序方向与老股东经济影响；
- 以后续收益（相对 ST 等权、相对中证 2000）作为结果变量之一；
- 计算分阶段成交情景参考、市场情景插值权重 `p*`、当前老股东权益口径在同阶段分布中的位置；
- 使用累积型量价形态标签和筹码代理（股东户数、龙虎榜、大宗交易、融资余额）；
- 宽口径候选排序，允许弱证据叠加，每条给出确定性原因；
- 用"篓子回报分布"评价，不要求单个信号通过显著性门。

### 2.2 宣称层（任何面向外部或写入 AnswerCard 正式事实层的输出，保留）

- 不使用"资金流入""主力埋伏""内幕""买入信号""胜率""目标价"；
- 不输出买卖、仓位建议；
- 异常量价固定风险文案不变；
- 三类情景参考对外独立展示；`p*` 只称"市场情景插值权重"，不称真实概率、底部或低估。

### 2.3 两层都保留的纪律

point-in-time membership 与市值；当日不入自身基线；未来公告只作 outcome；退市与失败
样本必须保留；阈值和切分在读结果前冻结；数据不可判定时 fail closed；LLM 输出是带来源的
候选，不覆盖原文。

**判定规则**：一条限制如果是防止自欺（泄漏、幸存者、事后调参），两层都留；如果只是防止
误导读者（措辞、因果词、建议），只留在宣称层。

### 2.4 架构边界

P8 采用 hybrid，而不是改写 P6/P7：

- P6/P7 的事实、run、manifest 和历史判断保持不可变；
- 新建 append-only `p8_research_v1.sqlite3`，只保存带版本的派生事件、特征、情景参考、候选和
  结果；每条记录引用 P6/P7 source ID，不复制或覆盖旧真值；
- `p8_research_manifest_v1.json` 指向一次完整物化的 run 集；失败 run 不移动 current pointer；
- 研究层和宣称层使用不同的 typed view。宣称层只能消费已经通过语言与证据门的字段，不能靠
  前端隐藏研究字段来实现隔离；
- P8A 的情景参考计算模块不得 import P8C 量价或 P8D 排序模块；用 typed input contract 和
  dependency test 防止循环，字符串静态扫描只作辅助。

## 3. P8A：分阶段成交情景参考

### 3.1 经济对象

P8A 不声称存在一个可直接观察的统一“壳价值”。它保存三种不同经济对象，并尽量换算为
**原老股东对应权益价值**：战略投资人附条件交易、失败退出代理、公开市场节点估值。三类值
不得合并成一个分布，也不得取最小值/平均值制造统一锚点。

### 3.2 分层键与机械放宽阶梯

精确层键是 `stage × delisting_risk_type × board × regime_version`：

| 维度 | 取值 | 来源 |
| --- | --- | --- |
| `stage` | `st_distress_only` / `restructuring_application_disclosed` / `pre_restructuring_started` / `formal_restructuring_accepted` / `investor_recruitment` / `investor_agreement_signed` / `plan_key_terms_disclosed` / `plan_approved` / `plan_executed` / `risk_warning_removed` | P6B-3 verified 优先；其次是 P8B 正文核证派生；只按标题推出的 P7 状态不得冒充同等级真值 |
| `delisting_risk_type` | `financial` / `trading` / `normative` / `major_violation` / `none_identified` / `unknown` | 风险警示原因、审计事实、当日价格与市值；无证据时必须 unknown |
| `board` | 主板 / 创业板 / 科创板 / 北交所 | point-in-time universe |
| `regime_version` | 由上市/退市规则和实施日期登记的稳定版本 | 版本化规则 registry；不得仅用回测表现划分 |

十个阶段再交叉风险、板块和制度版本会产生大量空格。P8-0 必须先输出 cell occupancy；分位
不足时只按以下顺序机械放宽，不允许拧到出结果为止：

1. 精确层；
2. 同 `stage × risk × regime`，移除 board；
3. 使用预注册的相邻阶段组，仍保留 risk 与 regime；
4. 时间窗从 12 扩至 18、再到 24 个月；
5. 仍不足则只列原始点，不输出分位。

每一步必须显示 `relaxation_path`。`unknown` 不与任何已知风险或阶段合并。

### 3.3 三类参考独立成账

1. **战略投资人交易参考 `strategic_entry_reference`**
   - 原始交易对价：`受让价 × 投资人实际受让股份`；另列 headline post-money
     `受让价 × 转增后总股本`，两者不得混称；
   - 并列保存转增后总股本、原股东保留比例、债权人受偿股份、现金投入、产业承诺、锁定期和
     其他可量化/不可量化条件；
   - 只有受让股份、对价、总股本、老股东让渡和 `available_as_of` 全部核证时，才换算
     `old_equity_equivalent = 受让价 × 原老股东方案后实际保留股份`。附带义务未能拆分时固定
     标 `package_contaminated`；
   - 它证明一笔附条件交易，不称纯壳成交或公平价值。
2. **失败退出参考 `failure_exit_reference`**
   - 保存交易所最后可观察的老股东权益市值，以及 `total_loss_stress=-100%`；
   - 最后交易日停牌、陈旧价、老三板/清偿未知分别标记；两种口径不是数学上下界；
   - 失败退出参考只进入失败情景分布，不塞进每一个成功阶段分布。
3. **公开节点市场参考 `public_node_reference`**
   - 保存法院受理、方案批准、执行完毕和撤销风险警示在信息可得后的首个可观察交易日之
     `old_equity_market_value`；同时保存当日总市值和资本结构污染标记；
   - 有可靠公告时间时使用其后的首个可交易端点；只有日期时统一使用下一交易日，避免拿公告
     后事实配公告前价格；
   - 转增、让渡或新股登记跨越端点但老股东账不完整时，只显示总市值事实，老股东值 unknown。

每类参考分别报告样本数、公司数、中位、P25/P75、范围、实际窗口、层键、来源质量和
`relaxation_path`。样本数 < 8 或公司数 < 5 时只显示原始点。

### 3.4 窗口冻结

主窗口为滚动 12 个月。仅因样本不足，且不跨越 `regime_version` 时，按预注册阶梯扩为 18、
24 个月；24 个月是硬上限。24 个月仍不足时合法结果是空分位。2021 年以来逐年值只作并列
语境，不与滚动窗口混算。

### 3.5 市场情景插值权重

复用 P6 公式，但只有当前、成功和失败三者均为**同一原老股东权益口径、同一计价时点语义**
时才计算：

`p* = (当前老股东权益价值 − 失败情景老股东权益价值)
      / (成功情景老股东权益价值 − 失败情景老股东权益价值)`

- 优先使用公司自身已核证方案形成的成功/失败情景；跨公司参考只能作情景敏感性，不得自动
  替代公司特定值；
- 公司特定成功、失败值来自同一 claim 的已核证事实；§3.3 跨公司独立分布只能生成
  `cross_company_sensitivity_weight`，不因当前量价形态选择样本，也不得回填 `p*`；
- 分母 ≤ 0、资本结构污染、任一输入样本不足或口径不一致时 `p* = unknown`；
- `p* < 0` 或 `p* > 1` 不截断，标记 `outside_scenario_range`，用于暴露情景不完整；
- `p*` 不是客观成功概率，不与历史转移概率混用。

### 3.6 每只当前 ST 股的输出

`symbol, stage, stage_source, process_direction, old_equity_effect,
delisting_risk_type, board, regime_version, current_total_mv,
current_old_equity_value, reference_family, reference_layer, reference_n,
reference_company_n, reference_median, reference_window_months, relaxation_path[],
position_pct_in_layer, scenario_implied_weight, scenario_consistency_status,
distance_to_par_delisting_pct, distance_to_mv_delisting_pct,
days_since_last_verified_node, next_possible_successors[], data_gaps[]`

### 3.7 反循环与依赖测试

三类参考只能消费 P6/P8B 事件、资本结构、正式交易条款、退市终点和 C14 市值。量价、换手、
股东户数、漏斗点击和未来收益不得进入参考或样本选择。P8A 使用独立 typed input model；测试
必须验证 P8A 不 import P8C/P8D、payload 不含量价字段、改变 P8C 输入不会改变 P8A digest。

## 4. P8B：前哨链

### 4.1 多轨有向状态图

重整不是单线流程。P8B 使用可并行、可回退的显式图，至少拆成司法程序、投资人、方案表决/
批准、执行、风险警示五条 track。每个事件保存：

- `process_direction = advance / rollback / unchanged / unknown`；
- `old_equity_effect = supportive / adverse / mixed / unknown`；
- `possible_successors[]`、`failure_successors[]` 和 `prerequisite_nodes[]`；
- `available_as_of`、正文来源片段、抽取版本和 evidence status。

例如法院受理在司法程序上是 `advance`，但在方案尚未披露时对老股东影响仍为 `unknown`；
计划批准可能程序推进但因大幅让渡/稀释而为 `adverse` 或 `mixed`。不使用一个正负号覆盖两种
含义。

非硬节点保留 `not_hard_outcome=true` 作为结果账纪律，同时新增
`precursor_candidates_for[]`。它表示图上允许的后继，不宣称一定通向某个正面硬节点。

### 4.2 对每家公司输出

`current_nodes_by_track, frontier_nodes[], next_possible_successors[],
unmet_prerequisites[], last_precursor_date, days_since_last_precursor,
typical_gap_days_by_successor, process_direction, old_equity_effect,
failure_branch_risk_flags[], stage_source, evidence_status`

不输出伪精确的 `steps_to_next`；页面用“已满足/未满足的前置条件”和历史时间分布表达距离。

### 4.3 正文读取

P7A 的 `llm_route` 目前只是标签，LLM 从未运行；8,362 条入围公告中留出期 1,203 条无正文。
P8B 要求：

1. 先盘点正文实际位置、PDF 可提取率和请求成本，再按公告 ID/content digest 有界补齐；不得按
   symbol-day 重复抓同一公告；
2. 确定性规则先抽取明确标题/正文事实；所有进入 shortlist 且有正文的公告必须真实执行结构化
   LLM 抽取，不得只写 `llm_route`。缺正文的记录保持 `body_missing`；
3. LLM schema 抽取阶段节点、两轴方向、关键数值（受让价、转增/让渡比例、投资人、法院、
   日期）、后继候选和与前序节点冲突；每个字段必须带 source span；
4. 确定性结果与 LLM 一致时可自动接受为 derived；冲突、低置信和 source span 缺失保持
   `provisional`。owner 不逐条审核，只在规则冲突形成稳定 cluster 时看压缩样本。

"关于重整进展的公告"这种标题下的内容差异（投资人招募完成 vs 法院延期）只能靠正文区分。

### 4.4 评价方式（替代泛化 priority）

- **阶段特异 precursor recall**：每个 `process_direction=advance` 且
  `old_equity_effect in {supportive,mixed,unknown}` 的硬节点前 20/60 个交易日内，是否出现图中
  合法直接前序；按后继类型与老股东影响分别报告；
- **前哨→硬节点时间分布**：中位、P25/P75，用于 §4.2 的 `typical_gap_days`；
- **失败分支率与右删失**：每个前哨之后走向失败分支、推进分支或尚未结束的比例，按年份和
  stage source 报告；未结束不得记成功或失败。

不再用"priority 20 日硬节点率 vs routine"作为主指标。

## 5. P8C：累积型量价与筹码代理

### 5.1 保留 P7B，新增持续型特征

单日尖峰（D1–D4）保留为一组特征。新增（全部只用此前合格交易日，当日不入基线）：

| 特征 | 定义 |
| --- | --- |
| `cum_turnover_log_excess_10/20` | 对每个观察日使用该日前 120 日中位，累加 `log(turnover_rate_f / lagged_median_120)`；任一分母 ≤0 不补 epsilon，返回 unknown |
| `elevated_day_ratio_20` | 过去 20 个合格日中，当日相对此前历史换手分位 ≥75% 的天数占比 |
| `range_compression_20` | 过去 20 日振幅中位 ÷ 此前 120 日振幅中位；分母 ≤0 为 unknown |
| `price_drift_20` | 过去 20 日 qfq 收益，及相对 ST 等权、中证 2000 |
| `amount_weighted_log_price_slope_20` | 对 log(qfq close) 按交易日序号回归，以当日成交额占窗内成交额为权重；成交额覆盖不足为 unknown |
| `st_turnover_regime_20` | 同期全 ST 合格成员自由流通换手中位及其 20 日变化；区分个股积累与全板块活跃 |

10/20 日窗口均只包含截至当日可得的合格记录；形成候选时允许包含当日，但所有 lagged baseline
不得包含被评价日自身。

### 5.2 形态标签（描述性，研究层）

| 标签 | 条件（冻结前用 P7-0 同样的容量盘点定阈值） |
| --- | --- |
| `persistent_activity_price_stable` | 换手持续温和抬升 + 价格横盘 + 振幅收窄 |
| `single_day_activity_price_jump` | 单日尖峰 + 当日大涨 + 振幅放大 |
| `persistent_activity_price_down` | 换手抬升 + 价格下行 |
| `quiet` | 其余 |

标签只描述可观察形态，不推断参与者；宣称层不得译成"吸筹""出货"。阈值只能由 P8-0 的
容量与覆盖冻结，不能看后续公告或收益后选择。

### 5.3 筹码代理（需先做有界 provider probe）

| 数据 | Tushare 接口 | 用途 |
| --- | --- | --- |
| 股东户数 | `stk_holdernumber` | 季度/不定期；按公告可得日记录户数变化，只称持有人结构变化，不解释资金身份 |
| 龙虎榜 | `top_list` / `top_inst` | 席位类型、机构买卖净额 |
| 大宗交易 | `block_trade` | 折价率、买卖营业部 |
| 融资余额 | `margin_detail` | 杠杆资金变化（多数 ST 非两融标的，缺失即缺失） |

probe 规则同 P7-0：小样本、零生产写入、先报权限/积分/字段连续性，不可用就标 `unavailable`
不阻塞。

龙虎榜属于事件触发样本，缺失不等于没有机构交易；融资余额对非两融 ST 的缺失不作零值；股东
户数使用披露日而不是报告期末日。所有代理必须保存 coverage denominator。

### 5.4 结果变量（两条并列）

- 后续 20/60 日相对排除目标后的 ST 等权、中证 2000 的 qfq 超额收益；发生资本结构变化时
  标 `old_equity_return_contaminated`，不能冒充精确老股东回报；
- 后续 20/60 日按 `process_direction` 与 `old_equity_effect` 分开的硬节点；失败节点单列；
- 信号与公告的 `before / same_day / after / no_covered_announcement` 四类关系分开报告。D4 较低
  不能事后解释为追涨，只有这些时间分层可以检验公开信息后的反应假设。

## 6. P8D：每日候选漏斗

### 6.1 目标

每个交易日给 owner **最多 20 个候选**，软目标为 10 个；安静日允许 0 个，禁止为通过验收填充
垃圾候选。每个候选带固定 5 项检查，recall-first；不要求单个信号先通过显著性门，但必须满足
至少一条通道的冻结准入条件。

### 6.2 五项固定检查（每个候选必须全部填出或标 unknown）

1. 当前阶段与来源（P8B）；
2. 下一个正面硬节点是什么、离多远、同阶段历史中位间隔（P8B）；
3. 同口径老股东权益在对应情景参考中的位置、`p*`、退市线距离（P8A）；
4. 近 20 日量价形态标签与筹码代理变化（P8C）；
5. 最近一条前哨公告日期与正文摘要（P8B）。

### 6.3 通道配额与排序（代替未校准加权总分）

P8 v1 不把不同单位、不同可靠度的弱证据强行加成一个总分。冻结四条候选通道：

| 通道 | 准入 | 每日展示上限 |
| --- | --- | ---: |
| `event_frontier` | 出现新核证前哨，或已满足某合法后继的关键前置条件 | 6 |
| `scenario_tension` | 同口径公开节点/情景参考位置进入预注册观察尾部，且无资本结构阻塞 | 5 |
| `persistent_activity` | 命中 P8C 持续型形态，且不是公告后单日反应 | 5 |
| `chip_or_exploration` | 筹码代理形成新公开事实，或为避免只看已知模式而保留的探索样本 | 4 |

同一股票命中两条以上通道时跨通道晋级，但只占一个展示位。探索通道内冻结排序为：命中通道
数 → 龙虎榜/机构席位/大宗等同日公开事实数 → 最近披露日 → 股东户数变化幅度 → symbol；
不读取后续收益，也不再按股票代码截取前 N。其他通道按证据质量、最近新事实日期、命中通道数
和 symbol 确定性排序。`provisional`、`unknown`、退市风险和负面分支不通过扣分偷偷
抵消，必须作为显式字段或阻塞门。overflow 与各通道未展示候选全部保留在 canonical ledger。

只有积累了独立前瞻样本后，才可另开契约比较加权方案；不能用 owner keep 或历史收益回调本版
通道准入。

### 6.4 漏斗指标（替代 lift / Wilson 作为验收）

| 指标 | 定义 |
| --- | --- |
| 候选数/日 | 软目标约 10、硬上限 20；同时报告 0 候选日和 overflow |
| 挖掘率 | owner 打开过详情的候选占比 |
| 保留率 | owner 标为"继续跟"的候选占比 |
| 研究转化率 | 保留候选中 60 日内出现推进节点/有利老股东节点的比例；两者分开 |
| 使用转化率 | owner 后续是否加入自有观察/持仓；只衡量工具使用，不作为模型正确性或调参标签 |
| 漏检 | 出现正面硬节点但此前 60 日未进过候选的公司数 |

owner 不承担逐候选审核义务。主动 `keep` 是唯一必要动作；未点击固定为 `unreviewed`，不得自动
解释为 drop。`drop`/`unknown` 可选，每日目标人工决定 ≤5 次，系统从打开详情自动记录挖掘率。

## 7. P8E：阶段回报表（篓子视角）

P8E 不假设 912 个 episode 都具备可交易边界或精确老股东权益。先分两张表：

1. **可观察价格路径**：只对 verified 边界且有共同交易端点的 episode，计算 qfq 价格及相对
   排除目标后的 ST 等权回报；跨越资本结构事件者标 `old_equity_return_contaminated`；
2. **老股东权益路径**：只有转增、让渡、受让、前后股本和可得日完整核证时给 exact，否则给
   range/unknown，不拿 qfq 替代。

冻结端点：事件只有日期时，进入价使用信息可得后的首个合格交易日收盘，退出价使用退出事件
可得后的首个合格交易日收盘；停牌、连续一字板和无可交易端点分别报告，不能假设公告日收盘
可成交。退市同时报告 `total_loss_stress` 与 `last_exchange_observable`，二者不是上下界。

输出包括：

- 从阶段 X 进入、持有到阶段 Y、失败、退市或 N 日的两张回报分布；
- 分年份、分 risk、stage source 和资本结构质量；
- 失败、终止、退市和右删失全部留在分母/风险集；
- 篓子回报使用真实日历同期形成组合，不能把不同年份 episode 当独立资产随机拼篮子；置信区间
  同时按公司聚类和日历月份 block bootstrap。

这张表回答"这个游戏历史上单票与同期篓子的分布有什么差别"。它是研究层描述统计，不因
样本不足停止，但 coverage 不足时必须输出空表/unknown，不能写成已精确包含稀释。

## 8. 回测方法修正

以下修正写入新版 `V8_P8_BACKTEST_CONTRACT.md`，在读结果前冻结：

1. **切分**：不再按单次中点切。首选逐自然年 walk-forward；历史长度不足时使用多个滚动
   origin，并确保每个训练/留出比较都对齐同一日历季。年报季（4 月初至 6 月底）单独分层；
   “首轮基础率翻倍由季节导致”只作为待验证假设，不预写成结论。
2. **结果变量分方向**：`process_direction`、`old_equity_effect`、失败退出和超额收益分账，不把
   advance 与 supportive、rollback 与 adverse 互相代替。
3. **对照阶段来源**：P6B-3 verified → P8B 正文核证 derived → 明确覆盖完整且未观察到重整
   程序的 `no_known_restructuring` cohort。仅标题规则的 P7 状态只作敏感度层；完全 unknown
   不能默认成 `st_distress_only`。另报不要求阶段一致、只匹配 risk/board/市值的 fallback
   对照，不能冒充同阶段。80% 是覆盖目标，不是降低证据标准的理由。
4. **分箱**：D0、D1-only、D2-only、D3-only、D4 为互斥分箱，同时保留连续 percentile、
   robust z 和持续型特征；n < 30 的箱不参与趋势判断。趋势使用带不确定性的有序检验或回归，
   不能要求四个点估计机械递增，也不能因一次不单调单独否定。
5. **季节控制**：所有硬节点率并列报告"同期全 ST 池基础率"，lift 相对同期基础率计算。
6. **重复计功**：同一后继硬节点对同一家公司同一 precursor family 只计一次主命中；重复
   episode 保留在 ledger，推断按公司聚类。
7. 保留：point-in-time、右删失、公司聚类 bootstrap、退市样本保留、阈值先冻结。收益主表
   同时做日历月份 block bootstrap，避免把同一市场阶段的股票当独立样本。

## 9. 实施顺序与停止条件

| 步骤 | 内容 | 停止条件 |
| --- | --- | --- |
| P8-0 | 只读盘点：精确/放宽层 cell occupancy；三类参考同口径率；verified 可交易端点与老股东账覆盖；公告正文/PDF 可提取率；四个筹码接口 probe | 输出不得预设“零新数据”；每项给出请求、时间和磁盘预算 |
| P8B-0 | 冻结多轨图、两轴方向、后继/失败分支和 typed event schema；用既有 verified 事件物化最小图 | 本体未通过代表例/反例前，P8A/E 不使用“正面/下一节点” |
| P8E-0 | verified 子集的可观察价格路径与 coverage 表 | 精确老股东账不足时只发价格路径和 contamination，不阻塞空表发布 |
| P8A | 三类独立情景参考 + 可用时的 `scenario_implied_weight` | 受让条款可抽取率 <50% 时战略投资人参考降为 `company_specific_only`；任一层不足只列点 |
| P8B | 前哨链 + 正文补齐 + 真实 LLM 抽取 | 正文补齐配额不足时先覆盖 2024 年以来，并保留全量缺口 denominator |
| P8C | 持续型特征 + 形态标签 + 筹码代理 | 接口不可用标 `unavailable` |
| P8D | 四通道漏斗页 + owner 可选 keep/drop 记录 | P8B-0 必须完成；P8A/B/C 至少两条通道可用；无候选允许输出 0 |
| P8-BT | 按 §8 重跑回测 | 契约先冻结 |

P8A/P8E 不一定需要新 provider，但需要大量既有文书抽取、端点核验和可能的有界回填；只有
P8-0 能决定真实成本。P8B-0 是它们共同的语义前置。

## 10. 明确不做

- 不预测参与者身份；形态标签不译成资金意图；
- 不自动下单、不输出仓位；
- 不用 LLM 全量读公告打分；LLM 只处理入围正文并带来源；
- 不为凑样本把滚动窗口拉过 24 个月、不跨制度 regime、不把 `unknown` 阶段当同阶段；
- 不因本 PRD 放开研究层而修改 AnswerCard 契约版本；宣称层输出继续走现有契约。

## 11. 验收

- P8A：每只当前 ST 股都有 §3.6 全字段或 unknown；失败退出只进入失败参考；三类参考不混算；
  typed dependency、import graph、digest invariance 与静态扫描共同证明 P8C/P8D 不影响参考；
- P8B：阶段图为显式多轨数据结构；每个后继硬节点能回溯合法前序或标
  `no_precursor_observed`；程序方向和老股东影响不合并；
- P8C：所有特征只用此前合格交易日（复用 P7 泄漏测试）；
- P8D：连续 10 个交易日每日候选 ≤20，0 候选日与 overflow 可见；不得为达到软目标补候选；
  owner 每日必要操作为 0，主动决定目标 ≤5 次；
- P8E：价格路径与老股东权益路径分账；失败/右删失和 coverage 分母可复算；同期篓子不由跨年
  episode 随机拼接；
- 宣称层禁词测试（`validate_research_language`）继续全绿。
