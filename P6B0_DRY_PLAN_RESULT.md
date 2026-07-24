# P6B-0 真实数据盘点结果

状态：dry plan complete；P6B-1 historical backfill paused

盘点日期：2026-07-24

数据截止：2026-07-20

计划 ID：`P6B0-BE1B382B7CF794EBAECA`

契约：`v8_p6b_dry_plan_v1`

## 一句话结论

连续 ST 候选 episode 和 date-only 请求范围可以可靠列出，但当前本地价格与历史股本证据
不能支持一条连续通过 95% 覆盖门的市场地图历史区间。因此不进入全量回填，先做 11 个
交易日的只读 provider probe。

## 盘点结果

| 项目 | 结果 | 含义 |
| --- | ---: | --- |
| 候选 episode | 1,118 | 只作候选，不自动成为生产阶段真值 |
| 覆盖股票 | 782 | 其中 226 只股票有重复 ST episode |
| 开放 episode | 209 | 截止日仍在 ST membership |
| 候选历史起点 | 2016-08-09 | 只适用于 candidate inventory |
| 唯一入场锚点日 | 306 | `daily_basic` 按 date-only 请求，不按股票逐只请求 |
| membership 日历空洞 | 25 日 | 空洞不解释为退出 ST |
| 邻近空洞的候选边界 | 9 轮 | 后续保持 candidate，必须核证 |
| 命中 M6 重整候选 | 196 轮 | M6 全部仍为 `case_note_only` |
| M6 精确资本结构 adjuster | 0 | qfq 不得替代老股东权益账 |
| 本地 market-factor snapshot | 1 | 尚无历史 market-cap 回填 |
| 有退市状态且有任意 qfq 价格 | 161 / 161 | 不代表已有可靠退市终值 |

市场语境的实际边界是：中证全指 2016-01-04 起、ST 等权 2021-03-17 起、中证2000
2023-08-11 起，均截至 2026-07-20。缺失区间保持 `unavailable`，不倒算或替代。

本地 qfq 可用性只能充当价格缺口代理。2016–2021 年的 5 日内覆盖远低于 95%；2022–2025
虽有大量日期过门，但不是连续区间；2026 年截至数据日也没有连续达标。这个代理不包含
历史股本变化 guard，不能直接晋级为 point-in-time market cap。

## 冻结的下一步 probe

只读抽查以下 11 个交易日的全市场 `daily_basic`、目标 membership 和转增附近股本字段：

`2016-08-09`、`2019-04-04`、`2021-03-09`、`2021-03-25`、`2022-04-20`、
`2023-07-19`、`2023-10-12`、`2024-04-29`、`2025-04-30`、`2026-01-15`、
`2026-07-17`。

probe 只读、不写 canonical 数据，回答三件事：

1. 各年代历史总市值和总股本是否可得；
2. 停牌时的最近有效市值能否在 5 个交易日内安全沿用；
3. 转增前后厂商股本跳变是否能与 M6/P6A 事件日期对齐。

## 人类需要做什么

P6B-0 不需要逐公司、逐公告或逐数字审核。系统先采用以下安全默认：

1. 连续 episode 以逐日 `st_membership_daily` 为主，稀疏 `st_status_history` 只交叉核查；
2. candidate inventory 与可发布市场地图使用不同历史边界；
3. 5 日陈旧规则在 provider probe 完成前保持 shadow，不生成生产分位。

owner 只需要在下一份一页 probe 摘要上作一次发布范围决定：接受系统建议的历史起点，
或让能力保持更短历史 / `unavailable`。如果证据仍不足，系统 fail closed，不扩大成人工
标注任务。

## 复现

在数据根目录配置正确的环境中运行：

```bash
python p6b_dry_plan.py \
  --output-json /tmp/p6b0-dry-plan.json \
  --output-markdown /tmp/p6b0-dry-plan.md
```

命令只以只读方式打开源数据库；只有显式指定的报告路径会被写入。
