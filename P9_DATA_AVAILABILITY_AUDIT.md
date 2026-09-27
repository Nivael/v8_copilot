# P9 数据可用性盘点：面板每个字段到底能不能填

日期：2026-09-10
性质：**只读实测**。所有数字由 `local_data/v8_copilot/` 现产物直接查询得到，不是设计意图。
用途：[V8_P9_PANEL_PRD.md](V8_P9_PANEL_PRD.md) 的输入；决定面板哪些字段上第一版、哪些只能显式留空。

## 0. 基准锚点（本次盘点固定引用）

| 锚点 | 值 |
| --- | --- |
| P8 current manifest | `P8M-B3010C21F760B075CC71`，through **2026-09-03** |
| ST universe current | `SU-2D576193C2EA60A2299E`，as_of **2026-09-07**，**203** 只 |
| 基准池 manifest | `MC-F15756CDF3490173508B` |
| 市场活动 | `market_activity_v1.sqlite3`，2021-03-17 → 2026-09-03，676 symbols，213,055 行 |
| 权威个股库 | `shared_data/v5/backup_universe/st_stocks_v5_backup.sqlite3`（2.2G，只读） |

**重要**：`p8_research_v1.sqlite3` 里同时存在 manifest 未收录的**更新 run**（2026-09-04 17:53–18:32 物化的
`p8_signal_rank_v2`、`p8_holder_history_v2`、`p8_terminal_history_v2`、`p8_backtest_v2_*`、
`p8_reference_backtest_v2`、`p8_walk_forward_basket_v2`，以及窗口只到 2025-12-31 的
`activity_features` / `scenario_references`）。**面板必须按 manifest id 消费，不能按“最新 run”消费**，
否则会读到比生产基线更短或更探索性的数据。本次盘点已按 manifest 固定 run。
“最新 run”与“manifest run”在 `activity_features` 上窗口不同（2025-12-31 vs 2026-09-03），这是
最容易踩的坑。

## 1. Manifest 收录 run 的产出规模

| record_type | 行数 | 说明 |
| --- | ---: | --- |
| `current_scenario_map` | 609 | 203 只 × 3 类情景参考 |
| `company_frontier` | 203 | 每只当前成员一条 |
| `derived_event` | 1,773 | 375 家公司 |
| `return_path` | 2,233 | 524 symbols |
| `scenario_reference` | 801 | 三类参考原始记录 |
| `activity_feature` | 68,738 | 203 只当前成员全覆盖，2025-02-26 → 2026-09-03 |
| `chip_proxy` | 203 | 203/203 |
| `funnel_item` | 4 | 4 只：000826 / 002634 / 600337 / 603959 |
| `shadow_position` | 4 | 与漏斗同源 |
| `portfolio_summary` | 1 | |
| `backtest_report` | 1 | |

## 2. 逐字段覆盖率（`current_scenario_map`，609 行）

| 字段 | 可填 | 覆盖率 | 结论 |
| --- | ---: | ---: | --- |
| `current_total_mv` | 603/609 | **99.0%** | ✅ 可用，按当前成员按日取 |
| `distance_to_par_delisting_pct` | 603/609 | **99.0%** | ✅ 可用（距 1 元面值） |
| `stage`（非 unknown） | 348/609 | **57.1%** | ⚠️ 用，但必须显示 unknown |
| `delisting_risk_type`（非 unknown） | 246/609 | **40.4%** | ⚠️ 多数 unknown，不能当已知 |
| `next_possible_successors` | 60/609 | **9.9%** | ⚠️ 极稀疏 |
| `days_since_last_verified_node` | 60/609 | **9.9%** | ⚠️ 极稀疏 |
| `distance_to_mv_delisting_pct` | 0/609 | **0%** | ❌ 市值退市门槛未登记，整列留空 |
| `current_old_equity_value` | 0/609 | **0%** | ❌ 老股东权益口径未闭合 |
| `scenario_implied_weight`（`p*`） | 0/609 | **0%** | ❌ 不可算 |
| `position_pct_in_layer` | 0/609 | **0%** | ❌ 依赖参考分布，分布为空 |
| `reference_median` | 0/609 | **0%** | ❌ 同上 |
| `reference_status` | — | **empty 609/609** | ❌ 三类参考分布**全空** |
| `available_as_of` | — | 全部 2026-09-03 | ✅ 单一 as_of |

`data_gaps` 出现频次（609 行内，实测）：

| gap | 行数 |
| --- | ---: |
| `current_old_equity_claim_not_closed` | 609 |
| `market_value_delisting_threshold_not_registered` | 609 |
| `valuation_stage_checked_through_2026-07-20` | 609 |
| `delisting_risk_type_unknown` | 363 |
| `verified_current_episode_missing` | 273 |
| `current_stage_unknown` | 261 |
| `strategic_entry_reference_distribution_empty` | 203 |
| `public_node_reference_distribution_empty` | 203 |
| `failure_exit_reference_distribution_empty` | 203 |
| `current_total_market_value_missing` | 6 |

交叉核对：`current_stage_unknown` 261 与 stage 已知 348/609 一致；
`delisting_risk_type_unknown` 363 与已知 246/609（40.4%）一致；
`current_total_market_value_missing` 6 与 603/609 一致。
另外**全部 609 行的阶段真值都停在 2026-07-20**（`valuation_stage_checked_through_2026-07-20`），
比 manifest 的 2026-09-03 落后约 6 周——这是面板必须常显的分层 as_of 差异。

## 3. `company_frontier`（203 行，一只一条）

| 字段 | 可填 | 覆盖率 |
| --- | ---: | ---: |
| `frontier_nodes` | 40/203 | **19.7%** |
| `current_nodes_by_track` | 40/203 | **19.7%** |
| `last_precursor_date` | 40/203 | **19.7%** |
| `next_possible_successors` | 32/203 | **15.8%** |

`evidence_status` 分布：`no_event_observed` **163**、`title_derived` 24、
`deterministic_verified+title_derived` 13、`provisional` 1、其余混合 2。

**结论：203 只当前成员里，163 只（80.3%）在事件图上没有任何已观察节点。**
跟踪台的时间线列对大多数标的会是空的——这是真实状态，不是缺陷，必须空着而不是用公告标题填充。

## 4. 事件图节点规模（决定“阶段后继频率”能不能算）

`derived_event` 1,773 条 / 375 家；其中 **1,294 条带 `possible_successors`**。
证据等级：`deterministic_verified` **400**、`provisional` **486**、`title_derived` **887**。

| 节点 | 条数 | | 节点 | 条数 |
| --- | ---: | --- | --- | ---: |
| `risk_warning_removed` | 307 | | `pre_restructuring_started` | 83 |
| `restructuring_application_disclosed` | 271 | | `plan_executed` | 53 |
| `plan_key_terms_disclosed` | 181 | | `plan_approved` | 48 |
| `creditor_claims` | 172 | | `investor_selected` | 25 |
| `delisting_decision` | 148 | | `restructuring_terminated` | 17 |
| `investor_agreement_signed` | 126 | | `restructuring_rejected` | 7 |
| `creditor_meeting` | 118 | | `investor_agreement_terminated` | 3 |
| `investor_recruitment` | 111 | | | |
| `formal_restructuring_accepted` | 103 | | | |

**结论**：头部节点（≥100 条）有条件做“后继频率 + 中位间隔”；尾部节点（≤25 条）只能列原始点。
但 887/1773（50.0%）是 `title_derived`——**按 P8 纪律不得进入正文核证口径**，因此频率表必须
按证据等级拆开显示，不能合并成一个数。

## 5. `activity_feature`（当前成员 37,346 行）

窗口 2025-02-26 → 2026-09-03，203 只全覆盖。形态标签分布：

| shape_label | 行数 | 占比 |
| --- | ---: | ---: |
| `quiet` | 20,144 | 54.0% |
| `unknown` | 16,381 | 43.9% |
| `persistent_activity_price_down` | 469 | 1.3% |
| `persistent_activity_price_stable` | 338 | 0.9% |
| `single_day_activity_price_jump` | 14 | 0.04% |

**结论**：活动特征可填，但 `unknown` 占 43.9%，`persistent_*` 合计仅 807/37,346 = 2.2%。
面板可以做“形态标签”列，默认密度会很低；`unknown` 必须显示成 unknown，不能落进 `quiet`。

## 6. `chip_proxy`（203 行，203/203 覆盖）

| 字段 | 状态分布 |
| --- | --- |
| `holder_status` | `observed` **200** / `unknown` 3 |
| `top_list_status` | `not_triggered_in_complete_cross_section` 202 / `triggered` 1 |
| `block_trade_status` | `none_in_complete_cross_section` 202 / `reported` 1 |
| `margin_status` | `not_covered_or_missing` **203 / 203** |

**结论**：股东户数是最可用的筹码列（200/203）。龙虎榜/大宗交易是事件触发样本，
“当日没触发”不等于“没有机构交易”，必须显示完整截面状态而不是 0。融资余额对 ST
**全部不覆盖**，该列第一版应直接不出现或恒显 `not_covered`。

## 7. `return_path`（2,233 条 / 524 symbols）

`p8_return_paths_v1.json` 汇总：episode anchor 460、event anchor 1,773；
证据 `verified` 460 / `deterministic_verified` 400 / `provisional` 486 / `title_derived` 887；
完成窗口 5 日 2,130、10 日 2,119、20 日 2,003、60 日 1,928；
`delisted_path_count` **448**；`exact_old_shareholder_path_count` **0**；
资本结构状态 `changed` 958 / `unchanged_observed` 7,218 / `unknown` 756；
入场可交易性 `eligible_verified` 489 / `price_observed_but_tradeability_unknown` 1,648 / `unavailable` 96。

**结论**：这是面板里**最强的“概率”底座**——阶段条件收益分布真能算。但：
- `exact_old_shareholder_path_count = 0` → 只能出**价格路径**，不能出“老股东权益回报”；
- 958 条跨资本结构变化 → 必须标 `old_equity_return_contaminated`；
- 448 条退市路径 → **必须留在分母**，不能剔除（幸存者偏差）；
- 入场可交易性只有 489/2,233 核证 → 不得宣称“可交易收益”。

## 8. 三类情景参考（801 条）

`p8_scenario_references_v1.json`：`failure_exit_reference` 164、`public_node_reference` 511、
`strategic_entry_reference` 126；值状态 `raw_terms_only` 126、`total_mv_fact_only` 35、
`unknown` **640**；`exact_old_equity_count` **0**；`distribution_count` **0**；
`p_star_calculable_count` **0**；`current_member_count` 203、`current_map_count` 609、
`current_market_value_count` 201、`current_known_stage_count` **116**。

**结论**：三类参考**一条分布都没有**。面板只能显示原始条款点（受让价、总市值事实），
且必须永不合并三类。`p*` 面板位置第一版应当是**显式不可用 + 原因**，而不是 0 或估算值。

## 9. 已发布状态自述（`p8_status_v1.json`，交叉核对用）

```
p_star:                          unavailable_company_specific_inputs (0 条可算)
body_llm_extraction:             authorization_pending
body_verified_events:            0
current_member_frontiers:        203
current_scenario_map_records:    609
observable_return_paths:         2233
exact_old_equity_references:     0
daily_funnel_items:              4
concurrent_portfolio:            unavailable
forward_shadow_days:             1
operational_10_day_gate:         accumulating
validation_60_day_gate:          accumulating
human_actions_required:          0
publishable:                     true
```

正文补齐待办：734 份公开公告正文已就绪（约 803 个分块调用），7,628 条缺正文记录已在
`p8_body_missing_queue_v1.json`。**在 owner 明确批准正文外发前，这一路保持 0。**

## 10. P8C-v3.1 网格（**不在 manifest 内**，独立探索轨）

窗口 signal 2023-01-01 → 2025-12-31，outcome through 2026-09-03；focus 163 段 / 100 家；
`status = exploratory_only`；生产配额 0。

| 检验 | 处理组 | 对照组 | 差值 | 95% 聚类区间 | Holm p |
| --- | --- | --- | ---: | --- | ---: |
| H1 后 120 日 ST 超额 | 73 段/48 家 | 330 段/98 家 | +2.82pp | −8.02 ~ +12.96pp | 0.5664 |
| H2 后 60 日转持续活跃且向上 | 48 段/34 家 | 89 段/54 家 | +27.60pp | +13.72 ~ +41.68pp | 0.0040 |

H2 缺失结果最不利/最有利分配后区间为 **−12.52 ~ +52.25pp**（仍跨零）。

**结论**：这个网格可以作为面板的**独立“探索”页签**，但必须常显 `exploratory_only`、
窗口边界和缺失界，且**不得与生产漏斗混排**。

## 11. 直接结论：面板字段可行性三分

**A. 第一版可填（有真实覆盖）**
当前总市值、距 1 元面值距离、股东户数与变化、活动特征（换手累积超额、振幅压缩、价格漂移）、
阶段条件价格路径分布（含退市路径）、事件节点频率与中位间隔（分证据等级）、
公告硬跃迁与重点公告（P7）、价格/相对收益曲线。

**B. 可填但稀疏，必须显示 unknown**
当前阶段（57.1%）、退市风险类型（40.4%）、后继节点（9.9%）、
事件前沿（19.7%）、形态标签（`unknown` 43.9%）。

**C. 第一版填不了，只能显式留空 + 原因**
`p*` 情景插值权重、三类参考分布、老股东权益价值、市值退市距离、
老股东权益回报路径、组合/前瞻表现、正文核证节点。

> C 类不是“以后再说”，而是**面板必须把它们画成可见的缺口**——这正是本项目的核心设计主张
> （DESIGN.md §2「诚实分层可见」）。一个只有 A 类字段的面板会看起来比实际更确定。
