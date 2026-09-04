# v8 P8 回测与验证契约

状态：**frozen before P8 outcomes are read**
日期：2026-09-04
契约版本：`v8_p8_backtest_v1`
父 PRD：[V8_P8_RESEARCH_FUNNEL_PRD.md](V8_P8_RESEARCH_FUNNEL_PRD.md)

## 1. 五张独立成绩单

P8 不输出一个“总有效率”。验证固定拆为：

1. 正文抽取正确性与来源覆盖；
2. 合法前哨对下一程序节点的 recall、gap 和失败/右删失分布；
3. 累积型活动特征对后续方向节点与相对收益分布的描述性区分；
4. 三类情景参考的同口径覆盖、稳定性和事后包含关系；
5. 每日漏斗的研究转化与真实同期组合回报。

前四张不因 owner 点击而改变；第五张不把 `keep` 当成市场真值。

## 2. 不可回写的冻结输入

每次报告登记 P6/P7/P8 run ID、manifest digest、membership 版本、事件词表、LLM prompt/model、
形态 profile、基准序列和代码 commit。历史输入之后被修订时生成新版本，不覆盖旧报告。

当前观察日不进入自己的 lagged baseline；公告使用 `available_as_of`；结果节点和收益只能在
预测时点之后进入 outcome。失败、退市和未完成 episode 必须保留。

## 3. 时间切分

- 主验证使用 expanding walk-forward：训练只用于估计已经冻结口径的历史分布，下一自然年为
  留出；不使用留出结果改阈值；
- 数据不足以形成完整年度时使用季度 rolling origin，但各 origin 必须覆盖相同日历季节；
- 4 月初至 6 月底年报/摘帽季单独报告，同季同比，不再用任意时间中点切分；
- 所有同时影响多只股票的市场日按日历月保留相关性。

## 4. 方向与结果变量

硬节点至少分为：

- `process_advance`、`process_rollback`；
- `old_equity_supportive`、`old_equity_adverse`、`old_equity_mixed_or_unknown`。

禁止把法院受理、计划批准、终止重整和终止上市合成一个 True。一般进展不是硬 outcome。

收益窗口固定为 5/10/20/60 个合格交易日：

- 个股 qfq 收益；
- 相对同期 ST 等权收益；
- 相对同期中证 2000 收益；
- 退市同时报告总损失压力与最后交易所可观察值；
- 跨越转增/让渡而旧股东账不完整的窗口标 `capital_structure_contaminated`，不能进入精确
  old-shareholder return。

未观察满窗口为 right-censored，不记失败或零收益。

## 5. 前哨链验证

- 反向 recall：每种已核证推进/回退节点前 20/60 个交易日，是否存在其图中合法直接前序；
- 正向路径：每种前哨后走向合法推进、失败分支或仍未完成的 cumulative incidence；
- 同一家公司、同一 precursor family、同一 successor 只记最近一次合格前哨，避免重复公告
  堆高命中；
- `body_verified` 为主结果；P6 verified 交叉结果单列；title-only 只作 sensitivity；
- 公司内多 episode 用 company-cluster，不假设独立。

## 6. 量价与筹码验证

单日 D0–D4 使用互斥箱：`D0`、`D1_only`、`D2_only`、`D3_only`、`D4`。持续型特征保留连续值，
形态标签只是冻结阈值后的描述层。

主比较同时报告：

- 后续 20/60 日各方向硬节点率与相对收益分布；
- 同期全 ST 基础率；
- 匹配对照，优先级固定为 P6 verified stage → P8 body-verified stage → 明确无已知重整程序；
- P7 title-derived stage 只作 sensitivity；stage unknown 不默认等于 `distress_only`；
- 无法达到匹配门时另报 stage-free 同日近市值结果，不冒充同阶段对照。

趋势判断使用不确定性区间，不因 D3/D4 点估计差一两个样本宣称不单调。任一箱少于 30 个
已完成观察，只列点与区间，不进入趋势结论。标准误按公司聚类，并以日历月 block bootstrap
补充市场共同冲击。

## 7. 情景参考验证

三类参考分别验证，不计算混合平均：

- coverage：exact/range/unknown、样本数、公司数和 relaxation path；
- stability：滚动窗口前后中位/P25/P75 变化，不以稳定性反向选择窗口；
- containment：公司后续已实现旧股东权益结果是否落在当时可得参考分布内；
- interval score：同时惩罚未覆盖和区间宽度，禁止靠无限宽区间获得 100% coverage；
- `p*` 只在同旧股东权益口径子集评价校准，样本不足时长期保持 unvalidated。

`p*` 只使用公司自身、同一 claim 的成功/失败旧股东权益输入。跨公司分层中位数只形成
`cross_company_sensitivity_weight`，不得命名或回填为 `p*`，也不与客观转移概率比较。

## 8. 漏斗和同期组合

每日漏斗分四 lane，保留 overflow。运营指标分账：

- 可研究性：证据可打开率、数据缺口率、进入深挖的比例；
- owner 使用：`keep` 数、无动作数和明确 `drop`，无动作保持 unreviewed；
- 研究转化：补正文/补资本结构后结论是否改变、是否形成可复用经验；
- 市场观察：候选形成后的真实同期等权组合及相对 ST 等权/中证 2000 回报。

组合必须是按交易日实际可持有的 concurrent calendar portfolio，不把不同年份 episode 当成
同时投资的独立彩票。公司多次入选按预注册持有期去重。结果用 company cluster + calendar-
month block bootstrap；不输出胜率、目标价或仓位建议。

## 9. 发布与失败状态

历史回测不能替代真实前瞻。每个输出显示完成样本数、右删失数、覆盖、版本和
`validated / descriptive_only / unvalidated / unavailable`。

以下情况不得发布强解释：方向未分开；对照覆盖不足；正文只是 title-only；资本结构污染；
样本/公司门不足；结论只在调参后的同一数据成立。无法证伪不是通过验证。
