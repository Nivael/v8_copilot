# ST Research 日常工作模式

日常固定为两个 Codex 任务和一个浏览器面板。三个窗口各做一件事，避免数据更新、回答和经验审阅互相污染。

在 Leibniz 出差工作区中，三个入口仍然不变，只是所有命令从
`/Volumes/Leibniz/STResearch/v8_copilot` 运行，并由 `portable/st-portable` 固定
`V8_DATA_ROOT`、机器专属 Python 环境和数据单写锁。GitHub 管代码，SSD 管唯一一份本地数据；
详见 [portable/README.md](portable/README.md)。

## 窗口一：数据更新

固定一个置顶 Codex 任务，开场指令：

> 使用 `$st-research-data-maintainer`。只负责更新我声明范围内的价格、CNINFO 公告和所需公告正文材料化，最后生成严格 freshness manifest。不要回答研究问题；任何失败或覆盖不全都必须列出。

每天先在这里声明：价格应到哪个已完成交易日、公告核查到哪一天，以及使用哪一个 universe snapshot。维护器固定使用 Tushare 前复权价格和 CNINFO 公告，按 source + symbol 保存成功游标；已核查到目标日时不会重复请求。价格默认回看 7 天并按交易日主键去重，CNINFO 默认回看 14 天并按公告 ID 合并。若最新复权因子变化，价格自动重建该股票完整 qfq 历史，不能用普通增量制造口径断层。

先固化当天权威 ST 名单，再以 snapshot 展开任务：

```bash
python data_maintenance.py sync-universe \
  --env-file <local-tushare-env> \
  --as-of <已完成交易日>

python data_maintenance.py show-universe

python data_maintenance.py plan \
  --universe-current \
  --price-through <YYYY-MM-DD> \
  --announcement-through <YYYY-MM-DD>
```

snapshot 是 append-only；`removed_symbols` 仅表示移出 ST 名单，不代表退市。首次全量执行必须先按
[V8_NEXT_TODO.md](V8_NEXT_TODO.md) 完成 dry plan 和无基线股票的独立 bootstrap 配置。

日常命令：

```bash
python data_maintenance.py refresh \
  --env-file <local-tushare-env> \
  --price-through <YYYY-MM-DD> \
  --announcement-through <YYYY-MM-DD> \
  --universe-current \
  --batch-size <N> \
  --request-delay-seconds <seconds> \
  --max-attempts 3
```

仍可重复 `--symbol` 只维护明确的小范围，也可用 `--universe-snapshot <path>` 固定重跑某一批。
`--batch-offset` 与 `--batch-size` 对排序后的 snapshot 做稳定切片；批次 manifest 不覆盖全量
manifest。失败项保留 checkpoint，可从相同 offset 或 plan 中列出的失败项继续。网络瞬时失败采用有界
指数退避，`--request-delay-seconds` 用于供应商节流。
`python data_maintenance.py checkpoints` 可审计每个来源和股票上次尝试、上次成功、已核查日期、写入行数和失败原因。数据更新后固定调用 `python experience_governance.py verify`；它只执行已到期的 accepted 经验回归。失败保留上次成功游标；`overall_status=ready` 才表示声明范围内达到目标，`gaps` 必须交给研究窗口作为明确数据缺口。

大盘方向基准单独维护，不写入个股价格表：

```bash
python data_maintenance.py refresh-benchmarks \
  --env-file <local-tushare-env> \
  --start-date <YYYY-MM-DD> \
  --through <YYYY-MM-DD>

python data_maintenance.py backfill-membership \
  --env-file <local-tushare-env> \
  --start-date <YYYY-MM-DD> \
  --through <YYYY-MM-DD>

python data_maintenance.py repair-membership-gaps \
  --env-file <local-tushare-env> \
  --start-date <YYYY-MM-DD> \
  --through <YYYY-MM-DD>

python data_maintenance.py materialize-st-index \
  --start-date <YYYY-MM-DD> \
  --through <YYYY-MM-DD>

python data_maintenance.py market-context-status \
  --coverage-threshold 0.95

python data_maintenance.py refresh-market-caps \
  --env-file <local-tushare-env> \
  --as-of <YYYY-MM-DD> \
  --coverage-threshold 0.95

python data_maintenance.py market-factor-status \
  --as-of <YYYY-MM-DD> \
  --coverage-threshold 0.95
```

`refresh-benchmarks` 默认同时刷新中证全指和中证2000；也可重复传
`--benchmark-id csi_all_share` / `--benchmark-id csi_2000` 做定向恢复。正式市场语境 pool 由
中证全指、中证2000和“逐日 ST membership + qfq 个股收益”物化的 `st_equal_weight_v1`
共同组成；不得用今天的成分股倒算历史，也不得把中证2000价格涨跌表述成资金净流入金额。截至 2026-07-20，market-context
当前状态 ready，但因源端早期日期空洞和历史价格覆盖不足，历史状态为 partial，连续区间从
2021-03-17 开始；包含中证2000的完整 pool 共同窗口从其正式发布日期 2023-08-11 开始。
日常增量不应覆盖或隐去这些历史边界。

`refresh-market-caps` 每个交易日只拉一次 `daily_basic` 横截面，并且只保留该日历史
ST membership；因此应在该日 membership 入库后运行。快照和市值行写入独立
`market_factors_v1.sqlite3`；每个交易日另存一份不可变 dated manifest，current pointer
只用于状态查看，manifest 覆盖不足 95% 时不 ready。为了让未来任意滚动窗口都能严格使用
窗口起点因子，需逐交易日留存快照，不能等到回答问题时用当前市值补历史。
当前真实验收快照为 `MFS-61A1FC03A4CD04164329`（2026-07-06，208/211，98.58%）。

P6B 历史锚点使用独立的内容寻址 plan 和可恢复运行器：

```bash
python p6b_market_cap_backfill.py run \
  --env-file <local-tushare-env> \
  --output <local-run-report.json>
```

运行器跳过已有 snapshot、只追加 dated manifest，并且只有 306 日完整闭环后才允许
current pointer 单向前进。2026-07-24 的 plan `P6B1P-C7B9FB39D9F73440A3E8` 已完成：
103 日 ready、203 日 coverage gap、0 缺失；见
[P6B1_MARKET_CAP_BACKFILL_RESULT.md](P6B1_MARKET_CAP_BACKFILL_RESULT.md)。

P6B-1b 只读消费这些快照、逐日 membership 和 qfq 价格。固定 12 个月比较日按中证全指
交易日历取周年日当日或之前最近交易日；同屏显示起止成员数和 Jaccard 换手，超过 30%
必须标记成分噪声。episode 相对重定价从入 ST 前最后共同有效端点开始，逐日重算排除
目标公司的 ST 等权财富路径。95% 在这里是覆盖警告线，不是把整条收益路径清空的市值
截面门；每天有效成员少于 20、共同端点缺失、2021-03-17 以前或资本结构无法排除污染时
仍然 fail closed。股本 guard 使用首个 ST 日到估值日，不能误用入 ST 前价格锚点，因为
ST-only factor snapshot 在入场前按设计不包含目标公司。真实双样本见
[P6B1B_MARKET_REPRICING_RESULT.md](P6B1B_MARKET_REPRICING_RESULT.md)。

P6B-2 使用独立的 append-only `valuation_facts_v1` 本地库。Tushare 财报、审计意见和
财务指标按实际披露日留痕，本地公告只先材料化风险披露存在性；二者都不能自动晋级为
可回收资产。冻结的 8 家 pilot 在缺少独立处置/评估和完整义务区间时全部保持
`unknown`。老股东权益账 0/8 精确闭环，因此后续全量固定以范围/unknown 为主，普通刷新
不要求 owner 逐案审核。见
[P6B2_ASSET_EQUITY_PILOT_RESULT.md](P6B2_ASSET_EQUITY_PILOT_RESULT.md)。

P6B-3 的 `valuation_episode_v1` 以逐日 membership 为候选、`st_status_history` 为边界
核证。≤3 个交易日的 membership 空洞只有在同一状态区间连续覆盖时才合并；程序失败或
重招募不拆 episode，摘帽后再入 ST 才开启新轮。阶段只使用官方精确标题或 P6A 核证
事实，M6 `case_note_only` 不晋级。方案关键条款披露后停止 P6B 输入；缺边界证据的记录
保持 provisional。见
[P6B3_VERIFIED_EPISODE_RESULT.md](P6B3_VERIFIED_EPISODE_RESULT.md)。

答案路径只读消费该 pool：以 ready manifest 的终点为边界，并要求 current universe 的
as-of 同日；最近 10 个交易日用 11 个共同端点计算。任一序列缺端点或 ST 覆盖率低于
95% 时返回市场对比缺口，不插值。网页端同时展示绝对收益、相对百分点差和起点归一为
100 的曲线；百分点差不解释为 alpha 或资金净流入。

涉及微盘的问题还要求 market-factor manifest 的日期严格等于收益窗口起点，并分别检查
微盘/普通 ST 的收益端点覆盖率均不低于 95%。网页展示两组分布与相对百分点差；任一条件
不满足时输出市值分层缺口，不插值，也不把运行缺口重新包装成已关闭的 `C14`。

## 窗口二：研究问答

固定另一个置顶 Codex 任务，开场指令：

> 使用 `$st-research-codex` 回答我的 ST 研究问题。先生成本地只读 EvidencePack，再按 acquisition plan 判断是否需要联网补当前事实；联网事实也必须先合入新的 EvidencePack。先给人话判断，再给必要逻辑链。每个判断都要有 backing，保留 freshness 与 coverage gap，提交结构化判断权重审计，通过 validator 后记录运行。不要写研究数据库，不要输出交易建议。

这个窗口每次都重新查数据库、缓存和 Lens，不把旧回答当事实。accepted experience 只提供方法提示，并始终标记 `not_evidence=true`。

联网与否不按整道题一刀切，而按证据职责切分：

- 最新公告、当前公司资料、法院/管理人渠道和题面当天市场事实，可以补查官方或明确的数据提供方；
- episode 去重、历史分布、Lens、事件窗口、价格路径等机制结果必须由本地版本化数据计算，网页摘要不能替代；
- 联网材料必须记录 source kind、URL、发布时间、抓取时间、覆盖说明和逐条 fact；只有进入同一个内容寻址 EvidencePack 后才能作为 `provenance_ref` backing；
- 外部当前事实与本地快照冲突时，回答应并列说明时点和来源。它可以更新“现在发生了什么”，但不能改写本地历史统计或 Lens 结论。

所以这个假设的核心是对的，但正确的分界不是“哪些问题联网”，而是“哪些事实需要联网获取、哪些判断必须离线计算”。二者在合成前统一过 EvidencePack 和 validator，才比单纯联网或单纯离线更可靠。

## 窗口三：浏览器审计与经验中心

浏览器只用于审阅，不作为主问答入口：

- `/runs`：查看每次回答、完整 EvidencePack、数据库行、Lens 调用、联网事实、statement backing、coverage gap、validator 结果和判断权重审计；
- `/`：查看 accepted 方法库存和自动待验证/blocked 异常；人工审阅只作兜底；
- `/legacy`：旧问答兼容和回归，不承担日常主持。

## 怎样确认回答真的基于数据库和 Lens

一条可审计回答应形成这条链：

`问题 → 本地 EvidencePack → acquisition plan → 可选联网事实 → 新 EvidencePack → 结构化回答 → validator → Research Run`

在 `/runs` 点击 Pack ID 后检查：

1. 数据库行是不是本题实际对象和正确日期；
2. Lens 是否真的适用。`0 条 Lens` 可以是正确结果，不能为了显得完整硬套 Lens；
3. 若使用联网事实，是否单独列出来源、抓取时间、coverage note，且标记为 `not_mechanism_evidence=true`；
4. 回答中的每条事实是否引用 Pack 内 backing；
5. 是否把未覆盖来源单独列成 coverage gap；
6. validator 是否通过，pack digest 是否与记录一致。

## 怎样审计 Codex 的判断和权重

新运行必须保存 `decision_audit`。它不展示模型不可验证的隐藏思维过程，而展示足够复核结论的结构化依据：

- 最终判断及其 backing；
- 每个因素是支持、削弱、限制还是背景；
- 因素的重要性为决定性、高、中、低；
- 被排除或仍未解决的备选解释；
- 整体置信度和证据覆盖边界。

这里故意不用 37%、0.72 之类数字权重。除非有正式统计模型，否则这些数字是假精确；ordinal 等级加具体 backing 更容易人工质疑和复核。

## 知识沉淀循环目前到哪一步

闭环已经具备四层保护：研究运行进入独立 ledger；用户反馈可提炼为通用候选；owner 冻结的
自动门要求两次真实复现、白名单回归、无 blocking conflict 和通用性校验；accepted 经验会
去除来源运行后导出为带 digest 的版本化 registry。

经验治理窗口按默认 30 天 cadence 执行：

```bash
python experience_governance.py status
python experience_governance.py verify
python experience_governance.py export --registry-version v1
```

`status` 检查 active 经验的冲突；blocking conflict 会阻止接受。`verify` 只执行到期经验的
白名单回归；回归失败会自动把 accepted 转为 `blocked` 并重新导出 registry。修复后可由同一
owner policy 重新跑自动门；未知 validation ref 保持 blocked，不伪报通过。

普通成功回答仍不会自动生成经验。这是主动的污染防线，不是尚未实现的功能。

经验运营不新增浏览器窗口：`/runs` 每条运行只有四个固定反馈按钮；同类方法达到两次真实复现
后自动执行回归与冲突门并写入。`/` 默认展示 accepted 库，candidate 只是自动待验证状态；
批量审阅、决定 JSON 和幂等导入保留为异常兜底，不再构成人类日常待办。完整契约见
[EXPERIENCE_OPERATIONS_PRD.md](EXPERIENCE_OPERATIONS_PRD.md)。

## P8 研究漏斗如何运行

P8 是独立 append-only 派生层，不是新的真值源。它只读 P6/P7、市场活动、市场因子和官方
公告，保存 source ID、available-as-of、版本和 digest；失败 run 不移动 current manifest。

研究层允许计算方向、收益、情景敏感性和公开筹码代理；宣称层仍禁止把它们表述为资金身份、
内幕、买卖信号、底部或目标价。三类情景参考永不混成一个“壳价值”；只有公司自身、同一
claim 的成功/失败旧股东权益输入闭合时才可算 `p*`，跨公司分层中位数只能作为敏感性。
P8B 只有“确定性规则 + 结构化 LLM + 可定位原文”一致才生成 `body_verified`；title-only
只可进入待补证探索或 sensitivity，不能进入已核证事件前沿。

日常只显示最多 20 个研究候选，lane quota 为 6/5/5/4，安静日允许 0。owner 无必审任务；
未点击保持 `unreviewed`。真实并发日历组合只从上线后每日漏斗累积，不用历史 episode 拼接。
操作顺序和降级状态见 [P8_DAILY_RUNBOOK.md](P8_DAILY_RUNBOOK.md)。

历史研究验证另行遵守 [V8_P8_BACKTEST_CONTRACT.md](V8_P8_BACKTEST_CONTRACT.md)：连续 120 日
ST 超额排序与三年可交易篓子是决定性测试，稀有硬节点率只是辅助。补历史数据前先执行
[V8_P8_BACKTEST_DRY_PLAN_CONTRACT.md](V8_P8_BACKTEST_DRY_PLAN_CONTRACT.md)；dry-plan 禁止读取
收益或命中率，避免用结果决定尺子。

P8-BT2 正式结果见 [P8_BACKTEST_V2_RESULT.md](P8_BACKTEST_V2_RESULT.md)：补回 191 家历史退市
终点并执行 -100%/最后可观察价双口径后，持续量价和旧前 20 篓子均被判杀，股东户数只保留
为不加权弱旁证。后 BT2 漏斗使用 `p8_research_funnel_v2`，持续量价晋级配额为 0；改变该结论
必须开新的预注册版本，不能在日常窗口里手调阈值。

2026-09-06 解释修正：上述判杀仅指未区分价格位置的通用持续活跃因子。双轴网格首次进入
研究见 [P8C_GRID_V3_RESULT.md](P8C_GRID_V3_RESULT.md)，低位价稳活跃82段/47家，匹配后
H1/H2均未通过40段/25家门。保留为探索性描述，生产配额不变。

2026-09-07 数据语义修正：上述82段是旧v3基线，不再代表当前覆盖。
[P8C_GRID_V3_1_RESULT.md](P8C_GRID_V3_1_RESULT.md) 只豁免已证全天停牌，不放宽量价参数，
恢复为163段/100家（2025为19段）；两项已达样本门。H1收益区间跨零，H2可观察样本有
接续差但删失敏感度跨零；仍不恢复配额。新复算必须传入冻结停牌证据并先生成无收益库存。
