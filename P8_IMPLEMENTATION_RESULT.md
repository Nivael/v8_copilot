# P8 首轮实施与真实运行结果

日期：2026-09-04；P8-BT2 更新于 2026-09-05

数据截止：2026-09-03

PRD：[V8_P8_RESEARCH_FUNNEL_PRD.md](V8_P8_RESEARCH_FUNNEL_PRD.md)

dry-plan：`P8DP-6753F0D179CF4A1B1C96`

current manifest：`P8M-B3010C21F760B075CC71`

## 1. 结论

P8 的无需人审工程闭环已真实运行：独立追加式派生库、五轨前哨图、持续型与单日量价分账、
公开筹码旁证、阶段回报、三类互不混合的情景参考、四通道研究漏斗、真实日历组合账、五张
回测成绩单和离线面板均已物化。P6/P7 输入保持只读。

当前结果不是交易信号。系统在三处主动留空：公告正文尚未获准发送给外部 LLM，因此
`body_verified=0`；公司自身同一 claim 的成功/失败旧股东权益输入没有闭合，因此 `p*=unknown`；
真实前瞻只有 1 个交易日，因此 10/60 日门仍在积累。

2026-09-05 已完成新的同阶段排序与可交易篓子验证。旧首轮 20 日 hard-node 回测只保留为
历史诊断；正式结论见 [P8_BACKTEST_V2_RESULT.md](P8_BACKTEST_V2_RESULT.md)。P8-BT2 判定持续
量价与旧四 lane 篓子为 killed、股东户数为 weak；后 BT2 漏斗因此不再让持续量价单独晋级，
真实 10/60 日门从 `p8_research_funnel_v2` 首日重新累计。

## 2. 当前运行账

| 模块 | run / 结果 | 当前事实 |
| --- | --- | --- |
| 事件图 | `P8R-7CC0257555052AE82666` | 1,773 个候选事件；400 deterministic verified、486 provisional、887 title-derived；203/203 当前成员均有 frontier；正文 LLM 完成 0 |
| 累积活动 | `P8R-C1F1F0F63E261162DA3A` | 68,738 条观察，40,080 条完整可算；冻结 `broad` profile；27,272 条有 point-in-time 市值 |
| 单日偏离箱 | 同上 | D0 9,092、D1-only 188、D2-only 77、D3-only 36、D4 37；严格 P7 输入 37 条，最终 broad 单日跳升形态 18 条 |
| 回报路径 | `P8R-92C4BD73B869ADABF61D` | 2,233 条；20 日完成 2,003；489 条入场可交易性核实，1,648 条只有价格可观察，96 条无端点 |
| 情景参考 | `P8R-B88B0AECE436274613F4` | 战略投资 126、失败退出 164、公开节点 511；203 只当前股票 × 3 类 = 609 条地图；201 只有当日市值，116 只有核证阶段；公司特定 `p*` 0 |
| 筹码旁证 | `P8R-559F5406224D81FF5E85` | 203 个当前成员；200 个有近一年股东户数披露；龙虎榜/机构席位/大宗各命中 1；融资融券命中 0 |
| 每日漏斗 | `P8R-ECAE67A323CB1F012286` | 4 个候选，全部为公告待核证节点 + 股东户数公开变化的多通道重合；事件栏只收核证节点，本日为 0；100 个未入选股票保留为 overflow；必审 0 |
| 日历组合 | `P8R-B04018422C284C442242` | 仅 1 个真实 shadow 日；4 个候选都尚无下一交易日，状态 unavailable/right-censored |
| 回测 | `P8R-EE1E151F7B753A4AA5FF` | 303 个去重活动 episode；按方向、年份、年报季和右删失分账；硬结果只认 10 个已核证节点 |

筹码首次真实运行因供应商要求 gzip 多线程头而有 60 个失败；客户端补齐
`Accept-Encoding: gzip` 后只重试失败项，最终 207 个请求中 147 个命中缓存、60 个真实重试、
0 失败。更早一次传错 secrets 文件的失败 run 也按 append-only 保留，不覆盖成功记录。

## 3. 这次修正了哪些容易自欺的地方

- 当前公司只使用本轮 ST membership 内的事件，不让旧一轮 ST 的前哨污染今天。
- 终止重整、不予受理、退市决定会清空旧成功轨迹，不会在失败后继续显示伪后继。
- 标题/临时事件不得进入 `event_frontier`；它们只能在多通道重合时进入待补证探索。
- 探索栏不再按股票代码截前 N；排序固定为多通道重合、同日公开筹码事实、最近披露日、
  股东户数变化幅度、symbol，不读取未来收益。
- 单日尖峰必须有真实当日相对 ST 回报和振幅，且不得占据“持续活动”通道；同日公告反应也
  从持续活动通道排除。
- 横截面参考采用 leave-one-out，目标公司不参与自己的分布；跨公司中位数不会自动写成
  `p*`，只有公司自身同一 claim 的成功/失败输入可以形成 `p*`。
- 回测结果只把核证且确属 hard outcome 的节点当结果，不再把普通进展或 title-only 当命中。
- 日历组合基准与股票使用完全相同的持有日区间，不漏掉第一个区间。

## 4. 回测怎么解读

三个 point-in-time 回放锚点分别是：

- 一周前 2026-08-27：2 个候选，均为单日跳升；
- 一个月前 2026-08-05：1 个持续活动且价格下行候选；
- 一年前 2025-08-20：1 个持续活动且价格平稳候选。

完整历史合并连续命中后得到 303 个活动 episode。20 日窗口完成并匹配 quiet 对照 231 个
（76.2%）；活动组相对 ST 等权的均值差为 -1.44 个百分点。公司聚类 95% 区间为
[-3.89%, 0.94%]，日历月 block 区间为 [-3.36%, 0.98%]，两者均跨 0。当前已核证 hard
outcome 库只有 10 个，活动 episode 的后续方向命中不足以评价前哨能力。首轮结果因此仍是
`descriptive_only`，没有证据支持“持续放量稳定领先消息”或“可据此择时”。

这不是阈值失败后再调参。`broad` profile 在读取任何未来节点和收益前，仅按每日容量与覆盖
冻结；单日宽/中/严三档也只用于容量盘点。真正发布仍需至少 60 个真实交易日 shadow。

## 5. 人类需要做什么

日常必要人审为 0。系统自动保留 unknown/provisional、冲突 cluster、overflow 和未点击候选。
owner 只有愿意时才对最多 20 个候选点 `keep / drop / unknown`；不点击仍是 `unreviewed`。

目前唯一需要 owner 明确授权的不是内容判断，而是数据出境边界：是否允许把本地缓存的 734
份公开上市公司公告正文发送给 OpenAI API 做结构化抽取。实际预算是 803 个分块调用、约 650
万字符；请求固定 `store=false`，不包含私有笔记或密钥。没有授权时不会外发。授权后也只有
规则与 LLM 节点一致且原文引用可定位的记录能升级为 `body_verified`。

## 6. 本地交付物

- 校验面板：`local_data/v8_copilot/p8_review/latest/index.html`
- 面板队列：`local_data/v8_copilot/p8_review/latest/review_queue.json`
- 面板截图：`local_data/v8_copilot/p8_review/latest/p8-review-panel.png`
- dry-plan：`local_data/v8_copilot/p8_0_dry_plan_v1.{json,md,html}`
- 正文缺口队列：`local_data/v8_copilot/p8_body_missing_queue_v1.json`
- 当前状态：`local_data/v8_copilot/p8_status_v1.json`
- current manifest：`local_data/v8_copilot/p8_research_manifest_v1.json`

这些是本机生成物，不提交 Git。全库 363 项测试通过。面板已用真实 Chrome 验证 4 张卡、
按钮状态、备注自动保存、localStorage、JSON 预览和导出结构；不需要启动服务或联网。
