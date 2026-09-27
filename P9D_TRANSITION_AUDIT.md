# P9D 前置：转移队列与统计粒度核对

日期：2026-09-10
性质：**只读实测**。方法、阈值与复算命令见 §6；结论全部由 manifest `P8M-B3010C21F760B075CC71`
的事件图 run `P8R-7CC0257555052AE82666` 与活动日历直接计算，未做任何人工挑选。
用途：关闭 [V8_P9_PANEL_PRD.md](V8_P9_PANEL_PRD.md) §6.1 的“待验证能力”状态，
决定 `/scenarios` 分区 A 第一版实际能开几行。
评审意见来源：owner 在 `8fb8562` 指出「已观察后继转移数 ≠ 节点事件数」，本文是该意见的实测。

## 0. 结论先行

**分区 A 在严格口径下只有 5 个后继单元可出频率，不是 16 个节点。**

- 按 `deterministic_verified` 起点、只认声明边、H=60 交易日、单元级门槛（N ≥ 8 且公司 ≥ 5），
  通过的是 **5 个 `起点节点 → 后继节点` 单元**（§4.2）。
- 16 个节点里 **11 个在 verified 等级下没有任何起点事件**：`creditor_claims`、
  `plan_key_terms_disclosed`、`investor_agreement_signed`、`creditor_meeting`、
  `formal_restructuring_accepted`、`plan_executed`、`investor_selected`、
  `delisting_decision`、`restructuring_rejected`、`investor_agreement_terminated`
  以及 `restructuring_terminated`（仅 2 条）。
- 我在此前盘点里写的「头部节点（≥100 条）可出频率」**不成立**，已作废：节点事件数与
  已观察转移数在 `risk_warning_removed` 上是 294 → 0，在 `delisting_decision` 上是 143 → 0。

## 1. 方法（可复算的六个决定）

| 决定 | 取值 | 理由 |
| --- | --- | --- |
| 起点事件去重 | 按 `(symbol, node, available_as_of)` 去重 | 1,773 → **1,547**（移除 226 条重复，12.7%） |
| 交易日历 | `market_activity_v1` 的 1,333 个交易日（2021-03-17 → 2026-09-03） | 间隔一律用**交易日**，不用自然日 |
| 观察期 | 固定 H = 60（并做 H = 120 敏感性） | 与 P8 PRD §4.4 的 20/60 日前瞻口径一致 |
| 右删失 | 起点事件后不足 H 个交易日的计入 `right_censored`，**排除出分母**，不得算作失败 | P8 PRD §4.4 |
| 转移判定 | 同 symbol、严格晚于起点日的**首个**该节点事件；**同日多节点不计为转移** | 同日多节点是共同披露，不是时序推进 |
| 后继合法性 | 只认起点事件自身的 `possible_successors`（声明边） | P8 PRD §4.4 用「图中合法直接前序」；`possible_successors` 是**允许边**，不是已发生事实 |

## 2. 三种“数”必须分开（本次核对的核心）

| 数 | 定义 | 本库值 |
| --- | --- | ---: |
| **节点事件数** | 该节点的去重事件条数 | 1,547（全部节点合计） |
| **带声明边的事件数** | 该节点事件中 `possible_successors` 非空的条数 | **1,088** |
| **已观察转移数** | 声明边条件下、观察期内真实发生的 `起点 → 后继` 对 | 见 §4.2，远小于上二者 |

`possible_successors` **不得**当作已发生转移——这是 owner 在 `8fb8562` 的直接修正，实测支持：
带声明边的 1,088 条事件里，绝大多数在观察期内**没有**对应后继事件发生。
另有 **459 条事件（1,547 − 1,088）根本没有声明边**，即图上的终结点或未登记节点。

### 2.1 逐节点三数对照（去重后）

| 节点 | 节点事件数 | 带声明边 | 公司数 | verified 起点 |
| --- | ---: | ---: | ---: | ---: |
| `risk_warning_removed` | 294 | **0** | 225 | 0 |
| `restructuring_application_disclosed` | 224 | 224 | 52 | 203 |
| `creditor_claims` | 144 | 144 | 80 | 0 |
| `delisting_decision` | 143 | **0** | 126 | 0 |
| `plan_key_terms_disclosed` | 133 | 133 | 64 | 0 |
| `investor_agreement_signed` | 115 | 115 | 67 | 0 |
| `investor_recruitment` | 99 | 99 | 61 | 84 |
| `creditor_meeting` | 96 | 96 | 44 | 0 |
| `formal_restructuring_accepted` | 88 | 88 | 47 | 0 |
| `pre_restructuring_started` | 74 | 74 | 38 | 39 |
| `plan_executed` | 45 | 45 | 26 | 0 |
| `plan_approved` | 44 | 44 | 22 | 8 |
| `investor_selected` | 23 | 23 | 13 | 0 |
| `restructuring_terminated` | 16 | **0** | 8 | 2 |
| `restructuring_rejected` | 6 | **0** | 6 | 0 |
| `investor_agreement_terminated` | 3 | 3 | 3 | 0 |

## 3. 三个结构性发现

### 3.1 终结点没有后继是**定义决定**，不是数据缺口

`risk_warning_removed`（294）、`delisting_decision`（143）、`restructuring_terminated`（16）、
`restructuring_rejected`（6）四类节点的 `possible_successors` **全部为空**——它们是注册表
`p8_precursor_registry_v1` 里的终结点。因此：

- 面板**不得**把这四类渲染成「观察到 0 次后继」或「后继频率 0%」；
- 正确文案是「该节点在事件图中为终结点，无声明后继」；
- 否则会把一个本体定义错误地展示成统计发现。

### 3.2 起点事件高度聚集于少数公司，`N` 不等于独立观察数

`deterministic_verified` 起点里：

| 起点节点 | 事件数 | 公司数 | 单公司最多 | 中位/公司 |
| --- | ---: | ---: | ---: | ---: |
| `restructuring_application_disclosed` | 203 | 49 | **23** | 2 |
| `investor_recruitment` | 84 | 58 | 4 | 1 |
| `pre_restructuring_started` | 39 | 33 | 4 | 1 |
| `plan_approved` | 8 | 8 | 1 | 1 |
| `restructuring_terminated` | 2 | 2 | 1 | 1 |

`restructuring_application_disclosed` 有**单个公司贡献 23 个起点事件**（203 条 / 49 家）。
因此「N = 203」不是 203 个独立观察；区间必须按公司聚类 bootstrap
（P8 已有该做法），面板也必须同时显示公司数，不能让 N 单独出现。

### 3.3 大量观察到的后继**不在声明边内**

去掉同节点重复后，仍有一批实际后续节点未登记为该起点的合法边，例如
（H=60，verified 起点）：`creditor_claims` 95、`investor_recruitment` 49、
`plan_key_terms_disclosed` 44、`creditor_meeting` 43、`investor_agreement_signed` 35。

这有两种解释，**本审计不下结论**：注册表边集不完整，或这些是同一 st 生命周期内的无关后续事件
（`unknown` 节点不得与已知节点合并，P8 PRD §3.2）。

设计后果：分区 A **只展示声明边内的转移**；未声明后继作为**独立诊断计数**呈现，
明确标注「不在声明边内，不计入频率」，不得混入同一张频率表。

## 4. 结果

### 4.1 起点层可用性（H=60）

| 口径 | 有起点事件的节点 | 其中有声明边的 | 通过起点门（N≥8 且公司≥5） |
| --- | ---: | ---: | ---: |
| `deterministic_verified` | **5** | 4 | 4 |
| `provisional` | 13 | 11 | 11 |
| `title_derived` | 13 | 12 | 12 |

verified 等级下 5 个起点节点为：`restructuring_application_disclosed`(202/49家)、
`investor_recruitment`(79/54家)、`pre_restructuring_started`(38/32家)、
`plan_approved`(8/8家)、`restructuring_terminated`(2/2家，无声明边)。

### 4.2 通过门槛的后继单元（verified 起点，H=60，门槛 N≥8 且公司≥5）

| 起点 → 后继 | N | 公司 | 门槛 | 中位间隔（P25–P75，交易日） |
| --- | ---: | ---: | --- | --- |
| `investor_recruitment → investor_agreement_signed` | 30 | 20 | ✅ PASS | 27（12–39） |
| `restructuring_application_disclosed → formal_restructuring_accepted` | 29 | 13 | ✅ PASS | 31（16–46） |
| `restructuring_application_disclosed → pre_restructuring_started` | 26 | 16 | ✅ PASS | 10（4–28） |
| `pre_restructuring_started → investor_recruitment` | 16 | 14 | ✅ PASS | 14（6–25） |
| `investor_recruitment → investor_selected` | 11 | 5 | ✅ PASS | 22（12–28） |
| `pre_restructuring_started → formal_restructuring_accepted` | 2 | 2 | ⚠️ 仅原始点 | 23 |
| `plan_approved → plan_executed` | 1 | 1 | ⚠️ 仅原始点 | 13 |

**H=120 敏感性**（verified）：单元结构相同，`restructuring_application_disclosed →
formal_restructuring_accepted` 升至 N=54、中位 54 交易日；`investor_recruitment →
investor_agreement_signed` 升至 N=42、中位 40 交易日。删失从 0–2 增至 4–8，仍很小。

### 4.3 关键反例：起点门通过 ≠ 单元门通过

`plan_approved` 起点满足 N=8、公司=8，看起来过门，但它的唯一后继单元
`plan_approved → plan_executed` 只有 **N=1、1 家**，只能列原始点。
**门槛必须施加在单元上，不能只施加在起点上**——这正是 owner 在 `8fb8562` 要求的
「样本门按每个实际展示的层键分别判定」。若只查起点风险集，会错误地把 N=1 渲染成频率。

## 5. 对 P9 的设计后果

1. **分区 A 第一版只开 5 个单元**（§4.2 上表前五行），verdict 直接落地为「已观察转移频率」
   与「中位间隔分位」；其余全部只列原始点。
2. **verdict 三态**：`frequency`（过单元门）/ `raw_points_only`（N=2–7）/ `sample_insufficient`（N≤1）。
   起点风险集不足时不进入分区 A。
3. **终结点单独文案**（§3.1），不参与频率，也不显示 0%。
4. **未声明后继独立诊断区**（§3.3），不计入频率。
5. **每个数字同时带 N、公司数、删失数、观察期 H、`evidence_status`**；
   公司数缺失则隐藏该频率并显示原因（PRD §8.2）。
6. **`provisional` 与 `title_derived` 作为独立分组**展示，不得与 verified 合并成一张表；
   provisional 覆盖明显更宽（11 个起点节点），但仍受同一单元门约束。
7. **H 必须显示**：同一单元在 H=60 与 H=120 下 N 与中位间隔都不同（§4.2），
   不标 H 的频率不可解释。

**因此 P9D 的验收应改为**：`/scenarios` 分区 A 展示的每个频率单元都能回溯到
「起点事件集合 + 声明边 + 固定 H + 右删失数 + 公司数 + 单元门判定」，
且 verified / provisional / title_derived 分组、终结点与未声明后继各自独立呈现；
不达单元门的层只出现原始点，不出现任何百分比。已过 P9D 前置核对（本文）。

## 6. 复算方式

输入固定为：manifest `P8M-B3010C21F760B075CC71` 的 `event_graph` run
`P8R-7CC0257555052AE82666`（1,773 条 `derived_event`）、`market_activity_v1` 的交易日历
（1,333 日）、去重键 `(symbol, node, available_as_of)`。计算步骤即 §1 的六项决定。

复算时须先重跑 §2.1 与 §4.2 两张表；若 manifest 移动，本报告的结论**不自动继承**，
必须按新 manifest 重算。

## 7. 未决

- §3.3 未声明后继的成因（注册表边集不全 vs 无关后续事件）需要 P8B-0 本体评审，本审计不裁定；
- 单元格级**同阶段/同风险/同板块**细分尚未做（当前先做全层）；P8 PRD §3.2 的放宽阶梯
  应在实现时按单元门逐层判定，本审计的 5 个单元是全层结果，细分后单元数只会更少；
- `title_derived` 分组起点虽多，但按纪律不得进入正文核证口径，本审计仅记录其规模。
