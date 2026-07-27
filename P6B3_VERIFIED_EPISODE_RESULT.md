# P6B-3 valuation episode 核证结果

- run：`P6B3R-2EEDD6679474DB3E72B6`
- 截止：2026-07-20
- 原始候选：1,118
- 核证后 episode：912
- 边界 verified：460
- 边界 provisional：452
- 自动合并 membership 假断点：206
- 当前 run 核证事件：685
- 人类必审 cluster：0

## 核心结果

逐日 membership 中存在短数据空洞。000525、600589 等公司的 `st_status_history` 明确覆盖
空洞前后，却被原候选错误切成多轮。v1 冻结规则为：空洞不超过 3 个交易日，且同一权威
ST 状态区间覆盖前后候选时自动合并。150 个最终 episode 命中该规则，共消除 206 个假
断点。真正摘帽/退出 ST 后再次进入仍开启新 episode。

核证后 460 个 episode 的当前阶段分布为：

| 阶段 | episode |
| --- | ---: |
| `st_distress_only` | 383 |
| `restructuring_application_disclosed` | 9 |
| `pre_restructuring_started` | 6 |
| `formal_restructuring_accepted` | 6 |
| `investor_recruitment` | 31 |
| `plan_key_terms_disclosed` | 25 |

452 个边界缺少 `st_status_history` 支持，统一保持 `provisional_boundary`，不进入上表和后续
同阶段统计。M6 `case_note_only` 只保留候选计数，不提供生产阶段标签。

## Pilot

| 股票 | 区间 | 当前阶段 | 最高阶段 | 程序状态 | P6C 边界 | 边界质量 |
| --- | --- | --- | --- | --- | --- | --- |
| 000004 | 2022-05-06..2023-06-27 | `st_distress_only` | `st_distress_only` | `none` | — | `verified` |
| 000004 | 2025-04-30..2026-06-22 | `st_distress_only` | `st_distress_only` | `none` | — | `provisional_boundary` |
| 000525 | 2021-05-06..2025-06-12 | `plan_key_terms_disclosed` | 同左 | `plan_boundary_reached` | 2024-10-07 | `verified` |
| 300108 | 2022-06-30..2025-05-28 | `st_distress_only` | `pre_restructuring_started` | `terminated` | — | `verified` |
| 300125 | 2024-04-30..2026-07-20 | `plan_key_terms_disclosed` | 同左 | `plan_boundary_reached` | 2025-12-03 | `verified` |
| 600165 | 2024-04-08..2026-07-20 | `plan_key_terms_disclosed` | 同左 | `plan_boundary_reached` | 2025-10-22 | `verified` |
| 600589 | 2021-05-06..2024-06-13 | `plan_key_terms_disclosed` | 同左 | `plan_boundary_reached` | 2023-12-05 | `verified` |

300108 证明“终止重整”只重置程序阶段，不拆分仍连续的 ST episode；最高曾到达阶段保留为
事实。000004 证明后一轮 ST 的事件不会泄漏到前一轮。

## P6B/P6C 边界修正

只有匹配上市公司当前/历史简称的实际方案文档、无其他主体名的通用方案文档，或明确的
出资人权益调整/经营方案才触发
`plan_key_terms_disclosed`。“延期提交重整计划草案”“提交期限不计入”等标题只是程序
期限，不代表条款已披露；上市公司公告库中的子公司/控股股东方案也不触发本公司边界。
真实回放发现并修掉了这两类假阳性。

方案关键条款披露日是 P6B 输入停止点。批准、执行完毕、再次招募或失败等后续事件保留为
结果事实，不回灌输入。联合管理人导致的同公司/同日/同节点重复行按里程碑去重。

## Review budget

本轮形成 5 个 decision family：短空洞合并、联合管理人事件去重、终止不拆 episode、
方案边界停止输入、缺边界证据保持 provisional。前四类由冻结规则自动处理，最后一类
fail closed，不要求 owner 补标签，因此人类必审为 0。

本地 `valuation_episode_v1` 使用 run → episode content digest 的版本关系。规则修正会
追加新版本，不覆盖原事实；只有指定 run 的成员才能被消费者读取。
