# v8 P9 PRD：标的追踪台与情景频率面板

状态：草案，待 owner 评审
日期：2026-09-10
负责人：owner 起草方向，Codex commander window 实施
基座：P8 current manifest `P8M-B3010C21F760B075CC71`（through 2026-09-03）
依赖：[V8_P8_RESEARCH_FUNNEL_PRD.md](V8_P8_RESEARCH_FUNNEL_PRD.md)、
[P7_DAILY_RUNBOOK.md](P7_DAILY_RUNBOOK.md)、[P8_DAILY_RUNBOOK.md](P8_DAILY_RUNBOOK.md)、
[DESIGN.md](DESIGN.md)、[P9_DATA_AVAILABILITY_AUDIT.md](P9_DATA_AVAILABILITY_AUDIT.md)
不改动：冻结的 AnswerCard / API v0 / v1 / QuestionCard / QueryTemplate / 研究记忆契约；
P6/P7/P8 事实库与 run 一律不回写

---

## 0. 一句话

v8 目前把研究能力做进了 **CLI + 静态 HTML**，但**没有一个能持续跟踪标的、并把历史频率讲清楚的
界面**：React 工作台的 `/daily` 只覆盖 P7，P8 漏斗是一个要手动双击的离线 `index.html`，
个股页只有单一标的证据。P9 把这些收进**一个只读、诚实分层的面板**：一个标的追踪台、
一个情景与频率视图、把离线漏斗搬进应用。**面板不产生新事实、不产生新结论，只消费 manifest
固定的既有产出，并把填不出来的字段画成可见缺口。**

## 1. 现状诊断：为什么现在做

### 1.1 现在已经存在四个互不相通的面

| 面 | 位置 | 问题 |
| --- | --- | --- |
| React 工作台 5 页 | `web/`（经验中心 / 兼容问答 / 个股证据 / 运行审计 / 每日观察） | `/daily` 只消费 P7，`/api/v1/p7/daily`；**完全没有 P8** |
| P8 漏斗审阅页 | `local_data/v8_copilot/p8_review/latest/index.html` | 静态文件，要手动双击；每日重新生成；不能跳转、不能按标的追踪 |
| P8C 网格探索页 | `p8_grid_v3_1/final/index.html` | 独立静态页，与生产漏斗无关联呈现 |
| P6/P7 审阅页 | `p6b*`、`p7_review/` | 一次性产物 |

### 1.2 三个真实痛点

1. **标的追踪没有载体。** 想持续跟一只票（阶段走到哪、下一个节点是什么、离退市线多远、
   筹码怎么变），只能每次重跑命令或翻 JSON。全库**没有自选股/持仓表**
   （迁移后 legacy watchlist/LHB 表为空，且按 P2 决定不填充）。
2. **“概率”被压成了单点结论。** 用户真正想知道的是“从 investor_recruitment 这个阶段出发，
   历史上类似的公司后来发生了什么、要等多久”。数据**已经够算**
   （1,773 事件 / 1,294 条带后继 / 2,233 条收益路径），但现在只以
   `scorecard` 形式存在 JSON 里，没有面向追问的视图。现有事件量只是候选样本规模，
   **不能直接证明观察到的后继转移和间隔足以估计频率**；P9D 须先完成转移队列审计。
3. **缺口不可见。** `p* = 0 条可算`、三类参考分布全空、80.3% 的当前成员没有事件前沿——
   这些如果不在界面上显式呈现，用户会默认“没显示 = 没发生”。

## 2. 两层边界与本面板的“概率”口径

沿用 P8 PRD §2 的冻结规则，P9 **不新增边界，只复用**：

- **研究层（owner 私有，允许）**：方向、收益、条件频率、情景权重、分位分布。
- **宣称层（写入 AnswerCard 的正式事实层，保留全部禁令）**：
  不使用“胜率 / 买入信号 / 目标价 / 资金流入 / 主力”；不输出买卖与仓位。
- **判定规则**：防自欺的（泄漏、幸存者、事后调参）两层都留；防误导读者的（措辞、因果、建议）
  只留在宣称层。

**本面板整体属于研究层**，因此允许显示条件频率与情景位置，但必须满足三条硬性约束：

1. **不得把频率称作“概率”**。统一措辞：`历史条件频率`（historical conditional frequency）、
   `情景插值权重`（`p*`）。禁止出现“成功概率”“上涨概率”“胜率”。
2. **样本门槛冻结**（与 P8 §3.3 一致）：N ≥ 8 例且 ≥ 5 家才出分布/分位；
   2–7 例**只列原始点**；0–1 例**明写“样本不足”**。样本门按每个实际展示的
   层键、证据等级、节点及收益窗口分别判定，门槛不因结果好看而放宽。
3. **`p*` 永远不叫概率**，且只在公司自身同一 claim 的成功/失败老股东权益输入闭合时才计算；
   当前状态为不可用，面板必须显式说明原因。

## 3. 信息架构

四个视图，全部只读，全部共享同一个 `ResearchContext`：

```
/tracking            标的追踪台（新增）
/tracking/:symbol    单标的工作台（= 现有 /stocks/:symbol 增强，复用 dossier 通路）
/scenarios           情景与频率（新增）
/daily               每日漏斗（现有 P7 页 + 并入 P8 漏斗与候选通道）
```

导航在现有 `App.tsx` 的 5 项基础上增加 `标的追踪` 与 `情景频率`，`每日观察` 保持末位。

## 4. 视图一：标的追踪台 `/tracking`

### 4.1 定位

一屏看完“我关心的 ST 标的现在各处于什么状态”。**表格为主**（DESIGN.md §1：强表格 + 高信息密度），
每行可展开时间线条；不做卡片瀑布。

### 4.2 行字段（含数据来源与第一版可行性）

| 列 | 来源 | 第一版 |
| --- | --- | --- |
| 代码 / 名称 / 板块 | universe `SU-2D576193C2EA60A2299E` | ✅ |
| 入池日 / 连续 ST 天数 | universe snapshot 历史 + `st_membership_daily` | ✅ |
| 当前阶段 `stage` | `current_scenario_map.stage`（P6B3 verified 优先） | ⚠️ 57.1%，其余显 unknown |
| 阶段证据等级 / 来源 | `stage_source` + `evidence_status` | ✅ |
| 最近核证节点 + 距今天数 | `days_since_last_verified_node` | ⚠️ 9.9% |
| 下一可能节点 | `next_possible_successors` | ⚠️ 9.9% |
| 事件前沿（五轨） | `company_frontier.frontier_nodes` | ⚠️ 19.7%，163 只 `no_event_observed` |
| 退市风险类型 | `delisting_risk_type` | ⚠️ 40.4%，已知优先显示、unknown 显式 |
| 距 1 元面值 | `distance_to_par_delisting_pct` | ✅ 99.0% |
| 距市值退市线 | `distance_to_mv_delisting_pct` | ❌ 0%，恒显缺口 |
| 当前总市值 / 微盘分层 | `current_total_mv` + C14 point-in-time cohort | ✅ 99.0% |
| 活动形态标签 | `activity_feature.shape_label` | ⚠️ `unknown` 43.9% |
| 20 日换手累积超额 | `cum_turnover_log_excess_20` | ✅ |
| 振幅压缩 / 价格漂移 | `range_compression_20` / `price_drift_20` | ✅ |
| 股东户数变化 | `chip_proxy.holder_num` / `holder_change_pct` | ✅ 200/203 |
| 龙虎榜 / 大宗 / 融资 | `chip_proxy.*_status` | ⚠️ 前三者显示**完整截面状态**；融资全不覆盖，第一版不出现 |
| 数据缺口 / 风险旗 | `data_gaps[]` / `risk_flags[]` | ✅ |
| manifest / as_of | `P8M-...`、各源 as_of | ✅ 常显 |

**硬规则**：

- 每行的 `as_of` 按来源分开显示，**不得合并成单一 as_of**（DESIGN.md §6）。
- 排序默认按“有无最近新事实”（按该事实自身的 `available_as_of`，而非页面打开时间），可切换阶段/市值/股东户数变化；**不提供任何收益排序或综合打分**
  （P8 PRD §6.3 已否决未校准加权总分）。
- 自选标记是本地面，不参与排序权重。

### 4.3 自选股是新增的**本地非证据**资产

全库没有自选/持仓表，P9 新建，边界如下：

- 位置：`local_data/v8_copilot/panel_local_v1.sqlite3`，**独立于研究库与运行审计库**；
- 表：`watchlist(symbol, added_at, note, tags_json)`、`panel_views(...)`（保存筛选/列序）；
- 每条记录固定 `not_evidence = true`；**面板自选与点击永不进入 EvidencePack、AnswerCard、
  经验候选或任何研究结论**；
- owner 可增删改；系统不自动加入、不自动移除；
- 该库不进 Git；导出为 JSON 供备份。

## 5. 视图二：单标的工作台 `/tracking/:symbol`

复用并增强现有 `DossierPage.tsx`（价格图 + 事件 + lens），增加：

1. **五轨阶段时间线**：司法程序 / 投资人 / 方案表决批准 / 执行 / 风险警示五条轨道并行展示，
   节点按 `process_direction`（advance / rollback / unchanged / unknown）着色，
   按 `old_equity_effect`（supportive / adverse / mixed / unknown）加标记——
   **两个维度不合并成一个正负号**（P8 PRD §4.1）。
2. **证据等级分色**：`deterministic_verified` / `provisional` / `title_derived` 三种视觉必须一眼可分；
   点开的节点显示 `source_spans` 原文片段与 `available_as_of`。
3. **前置条件面板**：显示 `unmet_prerequisites` 与 `typical_gap_days_by_successor`，
   用“已满足/未满足”表达距离，**不输出伪精确的 `steps_to_next`**。
4. **相对收益**：个股 vs ST 等权 vs 中证2000 vs 中证全指，同窗端点，缺端点显式 gap。
5. **缺口清单**：把 `data_gaps` 翻译成中文短语（复用 `p8_review_panel.py` 的 `GAP_LABELS`），
   按严重度分区。

## 6. 视图三：情景与频率 `/scenarios`

这是用户所说“各种概率预测”的合法落点。**三个分区分账，永不合并。**

### 6.1 分区 A：阶段后继频率（回答“接下来通常发生什么、等多久”）

- 交互：选一个起点节点（本次盘点列出 16 种）× 可选风险类型/板块/制度版本；
- 输出：**后继频率表** — 后继节点、观察到次数、占比、中位间隔交易日、P25/P75；
- **必须按证据等级拆开**（deterministic_verified / provisional / title_derived），不得合并；
- **必须显示 `relaxation_path`**（精确层 → 去板块 → 相邻阶段组 → 18 月 → 24 月 → 只列原始点）；
- 样本门：N ≥ 8 且 ≥ 5 家才给占比；否则只列原始事件点；
- 先以已观察的起点事件建立去重的公司／episode 风险集，限定观察起止与可得时间，核对
  实际后继事件、同日多节点及重复公告。`possible_successors` 只是图谱允许边，**不得当作已发生转移**。
- 右删失：尚未结束的必须计入 `right_censored`，**不得算作失败**；简单占比必须注明
  固定观察期限和该期限内可观察的分母。观察期不足时只列原始点与删失数，不报“后继频率”；
  间隔分位仅在口径一致且样本门通过时展示。
- 头部节点（≥100 条：`risk_warning_removed` 307、`restructuring_application_disclosed` 271、
  `plan_key_terms_disclosed` 181、`creditor_claims` 172、`delisting_decision` 148、
  `investor_agreement_signed` 126、`creditor_meeting` 118、`investor_recruitment` 111、
  `formal_restructuring_accepted` 103）**仅是优先审计候选**；逐层证据与已观察转移达门槛后
  才可出频率。尾部节点（≤25）也按实际风险集判定，通常降级为原始点列表。

### 6.2 分区 B：阶段条件收益路径分布（2,233 条路径）

- 按 `stage × calendar_half × board` 分层，展示 5/10/20/60 日：
  个股 qfq 收益、相对 ST 等权超额、相对中证2000 超额的中位与 P25/P75；
- **退市路径（448 条）必须留在分母**并单独标注；
- `capital_structure_status = changed`（汇总计数 958，粒度须由 P9E 核对）必须打
  `old_equity_return_contaminated`；不得把该计数直接作为 2,233 条路径的比例分子；
- **只出价格路径**：`exact_old_shareholder_path_count = 0`，面板不得出现“老股东权益回报”字样；
- 入场可交易性只有 489/2,233 核证，**不得宣称可交易**；`entry_tradeability_status` 必须随图显示。

### 6.3 分区 C：三类情景参考（801 条，**当前全为原始点**）

三类**永远分开展示**，每类独立报告 N、公司数、中位、P25/P75、范围、实际窗口、层键、
来源质量与 `relaxation_path`：

1. `strategic_entry_reference`（126）— 显示受让价、受让股份、转增后总股本；
   附带义务不能拆分时固定标 `package_contaminated`；
2. `failure_exit_reference`（164）— 交易所最后可观察老股东权益市值 + `total_loss_stress = -100%`；
   **只进失败情景，不塞进每个成功阶段分布**；
3. `public_node_reference`（511）— 四个公开节点在信息可得后首个可观察交易日的
   `old_equity_market_value` + 总市值 + 污染标记。

**当前 `distribution_count = 0`**，因此第一版这三类只能显示原始条款/事实点；
若该层只有 0–1 条，按样本门仅显示“样本不足”。页面顶部常驻说明“同口径分布不可用”。

### 6.4 `p*` 槽位

panel 上保留 `p*`（市场情景插值权重）的位置，但当前值为
`unavailable_company_specific_inputs`、可算记录 0。
展示规则：

- 常显 **`情景插值权重：不可用`** + 原因（公司自身同一 claim 的成功/失败老股东权益输入未闭合）；
- `p* < 0` 或 `> 1` 不截断，标 `outside_scenario_range`；
- 跨公司中位数只作 `cross_company_sensitivity_weight`，**不得回填 `p*`**；
- 缺分母、口径不一致、任一输入样本不足 → `unknown`。

## 7. 视图四：把离线漏斗并入 `/daily`

现有 `/daily` 只消费 `/api/v1/p7/daily`（P7 五段：覆盖 / 硬节点 / 重点公告 / 异常活跃 / 联动队列）。
P9 在其后**追加 P8 候选漏斗段落**，并把静态 `p8_review_panel` 的五个固定检查搬进应用：

| 检查（P8 PRD §6.2） | 数据 |
| --- | --- |
| 1. 当前阶段与来源 | `company_frontier` + `current_scenario_map` |
| 2. 下一个正面硬节点、距离、同阶段历史中位间隔 | `next_possible_successors` + 分区 A |
| 3. 同口径老股东权益在情景参考中的位置、`p*`、退市线距离 | 分区 C（当前为缺口） |
| 4. 近 20 日量价形态标签与筹码变化 | `activity_feature` + `chip_proxy` |
| 5. 最近一条前哨公告日期与正文摘要 | `derived_event`（正文未授权时标 `body_missing`） |

**通道状态必须如实呈现**（后 BT2）：

| channel | 配额 | 当前 |
| --- | ---: | --- |
| `event_frontier` | 6 | unavailable（正文未核证） |
| `scenario_tension` | 5 | unavailable（公司自身同口径输入不足） |
| `persistent_activity` | 0 | 已被 BT2 判杀，只留诊断/overflow |
| `chip_or_exploration` | 4 | 4 条，唯一可用 |

第一版 `funnel_item` 只有 4 条——**页面必须显示“当日 4 条 + 另外 100 条在 overflow”，
不得为空虚的 20 条补数**。owner 的 keep/drop/unknown 写入本地库，
`owner_keep_is_market_truth = false`，不得回流成标签。

## 8. 诚实层（Honesty chrome）统一规格

DESIGN.md §2「诚实分层可见」的工程化落实，四个视图共用：

1. **证据徽章**：`evidence / weak / anecdotal / query / lens_gap / data_debt / unknown` 七色。
2. **每个统计数字带可展开的出处**：N、公司数、窗口、层键、`relaxation_path`、
   `evidence_status` 以及删失数（适用时）缺一不可；原始价格、日期等事实按自身来源
   与 `available_as_of` 标注。统计元数据缺失时隐藏该统计值并显示原因。
3. **分层 as_of**：每个来源独立显示 as_of 与 `checked_through`，禁止单一 as_of 掩盖不同步。
4. **缺口不美化**：C 类字段渲染成**明确的缺口块 + 原因**，不是空白、不是 0、不是灰色占位。
5. **manifest 常显**：页脚固定显示 `P8M-B3010C21F760B075CC71` 与入口 digest。
6. **措辞门**：复用 `validate_research_language` 全绿；面板文案纳入同一禁词测试。
7. **探索隔离**：P8C-v3.1 网格单独页签，常显 `exploratory_only`、窗口边界与缺失界
   （−12.52 ~ +52.25pp），**不与生产漏斗混排**。

## 9. 只读边界与契约

- 面板只读：`p8_research_v1.sqlite3`（按 manifest）、`p7_intelligence_v1.sqlite3`、
  `market_activity_v1.sqlite3`、`market_context_v1.sqlite3`、`market_factors_v1.sqlite3`、
  `valuation_episode_v1.sqlite3`、`p8_qfq_v1.sqlite3`、`st_universe/`、权威个股库（ro URI）。
- **不写研究数据库、不写 run ledger、不写经验库**；唯一可写的是独立 `panel_local_v1.sqlite3`。
- **不发布新的 AnswerCard / QuestionCard / QueryTemplate 契约版本**（沿用 P8 §10 决定）。
- API 以**增量只读端点**扩展（v1 风格），现有 v0/v1 消费者不迁移：
  - `GET /api/v1/p9/tracking?as_of=&symbols=&sort=`
  - `GET /api/v1/p9/tracking/{symbol}`
  - `GET /api/v1/p9/scenarios/successors?node=&risk=&board=&regime=`
  - `GET /api/v1/p9/scenarios/returns?stage=&horizon=`
  - `GET /api/v1/p9/scenarios/references?family=`
  - `GET /api/v1/p9/funnel?as_of=`
- `GET/POST /api/v1/p9/watchlist`，`PATCH/DELETE /api/v1/p9/watchlist/{symbol}`
- 新增类型放 `api_contract_v3.py`（或 `panel_contract.py`），**不改动 `api_contract_v0/v1/v2.py`**。
- 后端新增模块建议：`panel_tracking.py`、`panel_scenarios.py`、`panel_funnel.py`、
  `panel_local_store.py`；**不得 import P8C 量价或 P8D 排序模块进 P8A 参考路径**（沿用 P8 §2.4 反循环）。

## 10. 非目标

- 不预测参与者身份；形态标签不译成“吸筹/出货”。
- 不输出买卖、仓位、目标价、胜率；不提供收益排序或综合打分。
- 不用 LLM 全量读公告打分；正文未获授权前不放行 `body_verified`。
- 不为凑样本把窗口拉过 24 个月、不跨制度 regime、不把 `unknown` 当同阶段。
- 不把 `title_derived` 节点混入正文核证口径的频率。
- 不回填伪历史漏斗；不把探索网格的 H2 结果当生产信号。
- 不做营销页、不做移动 App（DESIGN.md §1）。

## 11. 实施顺序与验收

| 步骤 | 内容 | 停止条件 |
| --- | --- | --- |
| P9-0 | 冻结字段清单、三档可行性（A/B/C）与缺口文案 | 本文档与盘点通过 owner 评审 |
| P9A | `panel_local_v1.sqlite3` + 自选股/视图本地库 + `not_evidence` 测试 | 自选写入不触碰任何研究库（集成测试证明） |
| P9B | `/api/v1/p9/tracking` + `/tracking` 表格 + 分层 as_of + 缺口块 | A 类字段 100% 可填；B 类显式 unknown；C 类显式缺口 |
| P9C | 单标的工作台五轨时间线 + 证据分色 + 相对收益 | 三个证据等级视觉可辨；无 `steps_to_next` |
| P9D | 先审计已观察转移与风险集，再做 `/scenarios` 分区 A | 样本门按展示层执行；频率按证据等级拆开；固定观察期限、`relaxation_path` 与右删失可复算；不达门槛则只列原始点 |
| P9E | `/scenarios` 分区 B/C + `p*` 槽位 | 退市路径留分母；污染标记；三类不合并；`p*` 显式不可用 |
| P9F | `/daily` 并入 P8 漏斗与四通道状态 | 4 条 + 100 overflow 如实显示；keep 不回流 |
| P9G | 探索页签（P8C-v3.1）+ 措辞门回归 | `validate_research_language` 全绿；exploratory 常显 |

**验收（可复算）**：

1. A 类字段在 203 只当前成员上覆盖率与
   [P9_DATA_AVAILABILITY_AUDIT.md](P9_DATA_AVAILABILITY_AUDIT.md) 一致，误差 0；
2. B 类字段的 unknown 不被静默填成默认值（专项测试：把 `unknown` 注入并断言渲染为 unknown）；
3. C 类推导值在界面上以缺口块出现，且**不渲染伪造的推导数字**；原始参考事实可带出处显示；
4. 面板全程只读：以只读 URI 打开研究库，任何写入尝试必须失败（fault injection）；
5. 禁词测试覆盖全部新增前端文案与后端 payload；
6. 前端测试 + lint + build 通过，后端全量 pytest 无新增失败；
7. 单票（如 603398 沐邦、600337、603959）走通“追踪台 → 单标的工作台 → 情景频率 → 提问”闭环。

## 12. 开放问题（需 owner 决定）

1. **自选股初始名单**：从零开始，还是导入现有观察清单？
2. **`/scenarios` 分区 A 的默认起点**：默认展示全部 16 节点的总览，还是进入具体标的时以其当前阶段为起点？
3. **C 类缺口的呈现强度**：缺口块是常驻可见，还是折叠在“证据与缺口”里（DESIGN.md §2 允许后者）？
4. **P8C-v3.1 探索页签**是否第一版就做，还是等正文授权后与 `body_verified` 一起上？
5. **正文 LLM 外发授权**是否在本轮内解决？它可能补足 `event_frontier` 所需的正文核证，
   但还需抽取质量、证据校验与通道门槛验收；`scenario_tension` 另需公司自身同 claim
   老股东权益输入闭合。授权也不保证 163 只无已观察节点的标的都会改善。
