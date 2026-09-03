# P7 实施与真实数据验收结果

状态：**engineering complete；首轮历史回测完成；P7A 仅具描述性价值，P7B/P7C 正在真实前瞻 shadow**
数据截止：2026-09-03
运行日期：2026-09-04
PRD：[V8_P7_DAILY_INTELLIGENCE_PRD.md](V8_P7_DAILY_INTELLIGENCE_PRD.md)
前瞻门：[V8_P7D_FORWARD_GATE.md](V8_P7D_FORWARD_GATE.md)

## 一页结论

P7 的工程闭环和当前真实数据已经可运行：正式公告、硬状态跃迁、自由流通换手异常、
公告/活动时间关系、研究队列、持续观察、历史 shadow、真实前瞻账、每日 API/Web 页面、
发布状态和两张压缩人审卡均已落地。日常不需要逐股、逐公告或逐日人工审核。

P7A 可以由 owner 决定是否只发布描述事实。P7B/P7C 不能提前发布：真实前瞻起点是
2026-09-04，当前进度 0/60 个交易日；历史回放不能替代时间门。

周/月/年首轮回测 `P7BT-35434858D1CD7665038F` 进一步确认：公告结构在 P6 已核证重叠上
5/5 一致，但 priority 留出期没有比 routine 形成可用区分；放量 D1–D4 留出关系不单调且
D3 可比对照覆盖只有 54.23%。因此公告优先级和放量临近度都不升级，详见
[P7_BACKTEST_RESULT.md](P7_BACKTEST_RESULT.md)。

## 真实数据账

| 数据面 | 结果 |
| --- | --- |
| 当前 ST universe | 203 只；snapshot `SU-E6F695722FE67D90A1EC` |
| 当前价格/公告 freshness | ready；`FM-F4909E3687984315B5C8` |
| market activity | 373 个真实交易日、68,738 symbol-day；manifest `MAM-A9CADF021161E07D698B` |
| 2026-09-03 当前活动覆盖 | 203/203 行，自由流通换手 99.01% |
| 全窗自由流通换手覆盖 | `turnover_rate_f` 97.17%；异常计算仍逐日执行 95% 覆盖门和排除规则 |
| P7-0 final | `P7DP-3C961A361143D9F34C48` |
| 公告状态机 | 2021-03-17 至 2026-09-03，107,036 条公告、106,444 个 bundle、491 个硬跃迁 |
| P7A run | `P7AN-E6FC24874F1898B11A0C` |
| P7B run | `P7AR-5B2662C0065A4AC87BDF` |
| P7D 历史回放 | `P7LR-CA32E27B6C701A00AE68` |
| P7D prospective | `P7LR-700578C100E24BF380AB`，0 个真实前瞻交易日 |
| current P7 manifest | `P7M-25A95F7D138EB8AA1EC4`，指向 prospective ledger |
| C14 回归锚 | 2026-08-20，206/206；`MFS-E2AE3A0DBAE4E0B69EF1` / `MF-9F40E10C3C4EB90EAF3E` |

新入池且没有本地基线的 301117 已逐股 bootstrap：2026 年以来 163 个 qfq 价格行和 30 条
CNINFO 公告。最终全池 freshness 无阻塞缺口。为一年锚点回测另有界补齐 2025-02-26 至
2026-02-12 的 239 个历史交易日，239/239 成功；这不扩张为 2021 年起的无边界回填。

## 容量与冻结选择

P7-0 未读取未来公告或收益来挑阈值。134 个交易日的工作量为：

| profile | 日命中 | 日均 | 日 P95 | 单日最大 | 5 日合并 episode / 公司 |
| --- | ---: | ---: | ---: | ---: | ---: |
| broad | 150 | 1.12 | 4 | 6 | 82 / 63 |
| balanced | 73 | 0.54 | 2 | 4 | 42 / 35 |
| strict | 37 | 0.28 | 1 | 3 | 29 / 28 |

`balanced` 保持默认 shadow。另有 1,409 个 `post_suspension` symbol-day；容量盘点后冻结为：
任一已知停牌后的 5 个股票观察日不生成默认异常，也不进入后续历史基线，原始事实仍保留。

历史 42 个 balanced episode 中，26 个已有 20 日终点，硬节点率 7.69%；58 个对照观察的
硬节点率 1.72%。episode Wilson 95% 区间为 2.14%–24.14%，按公司聚类 bootstrap 区间为
0%–20%。这些只说明历史样本很少且不确定性很宽，不是预测力结论。

## Provider 结论

有界探针 `P7PP-B6115DEC14D29A4712C2` 的 production writes 为 0：

- `daily`、`daily_basic`、`suspend_d`、`stk_limit` 均可用；样本中的 `turnover_rate_f` 完整；
- `daily_basic` 在显式请求后仍未返回 `limit_status`；shadow 使用 raw OHLC 与官方
  `stk_limit` 双源复核，冲突或缺失 fail closed；这仍是 P7B 发布缺口；
- `stk_shock`、`stk_high_shock`、`stk_alert` 当前账号均无权限，只使交易所公开标签对照
  `unavailable`，不阻塞 P7A 或 shadow。

最初 provider `stock_st` 返回了周末日期。活动 bootstrap 已改为必须与中证全指交易日历求交；
5 个空周末快照只保留为审计记录，不进入 manifest、覆盖或异常计算。

## 产品与运行结果

- `/api/v1/p7/daily` 和 Web `/daily` 已接入；固定顺序为覆盖、硬节点、重点公告、异常交易
  活跃、联动队列、持续观察；
- Top-N 只限制页面，canonical queue 与 overflow 不删除；
- P6 已核证阶段以 point-in-time 方式接入队列；P6 资产/偿债试点尚无可发布底座，因此明确
  `withheld_until_p6_published`，不拿未知值填充；
- P7A 的 107,036 条公告由确定性规则处理；8,362 条非硬节点候选被机器路由为“正文可读”或
  “先补正文”，不转交 owner 逐条审核；
- 研究语言验证禁止资金流入、主力、内幕、买入信号、胜率和目标价。

## 只剩下什么

1. owner 在两张发布卡上决定：P7A 是否只发布描述事实；P7B/P7C 是否按建议继续 shadow；
2. 系统从 2026-09-04 起自然累计真实前瞻交易日；达到冻结的 60 日、20 episode、15 公司、
   80% 对照和覆盖稳定门后，才重新生成发布卡；
3. 在 P7B 时间门和研究增益门同时满足前，P7C 长期保持 shadow；
4. `daily_basic.limit_status` 或等价可靠字段得到解决前，P7B 不解除该发布缺口。
