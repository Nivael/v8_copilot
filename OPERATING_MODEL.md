# ST Research 日常工作模式

日常固定为两个 Codex 任务和一个浏览器面板。三个窗口各做一件事，避免数据更新、回答和经验审阅互相污染。

## 窗口一：数据更新

固定一个置顶 Codex 任务，开场指令：

> 使用 `$st-research-data-maintainer`。只负责更新我声明范围内的价格、CNINFO 公告和所需公告正文材料化，最后生成严格 freshness manifest。不要回答研究问题；任何失败或覆盖不全都必须列出。

每天先在这里声明：价格应到哪个已完成交易日、公告核查到哪一天、覆盖哪些股票。维护器固定使用 Tushare 前复权价格和 CNINFO 公告，按 source + symbol 保存成功游标；已核查到目标日时不会重复请求。价格默认回看 7 天并按交易日主键去重，CNINFO 默认回看 14 天并按公告 ID 合并。若最新复权因子变化，价格自动重建该股票完整 qfq 历史，不能用普通增量制造口径断层。

日常命令：

```bash
python data_maintenance.py refresh \
  --env-file <local-tushare-env> \
  --price-through <YYYY-MM-DD> \
  --announcement-through <YYYY-MM-DD> \
  --symbol <六位代码>
```

重复 `--symbol` 声明完整研究范围。`python data_maintenance.py checkpoints` 可审计每个来源和股票上次尝试、上次成功、已核查日期、写入行数和失败原因。数据更新后固定调用 `python experience_governance.py verify`；它只执行已到期的 accepted 经验回归。失败保留上次成功游标；`overall_status=ready` 才表示声明范围内达到目标，`gaps` 必须交给研究窗口作为明确数据缺口。

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
- `/`：审阅可复用经验候选，只有 owner 可以接受；
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

闭环已经具备四层保护：研究运行进入独立 ledger；用户反馈可提炼为通用候选；只有 owner 能把候选接受为经验；accepted 经验会去除来源运行后导出为带 digest 的版本化 registry。

经验治理窗口按默认 30 天 cadence 执行：

```bash
python experience_governance.py status
python experience_governance.py verify
python experience_governance.py export --registry-version v1
```

`status` 检查 active 经验的冲突；blocking conflict 会阻止接受，重叠策略会要求人工审阅。`verify` 只执行到期经验的白名单回归；回归失败会自动把 accepted 转为 `blocked` 并重新导出 registry，修复后仍需 owner 复审。未知 validation ref 记为 `unverified`，不会伪报通过，也不会在没有实际失败时误封。

普通成功回答仍不会自动生成经验。这是主动的污染防线，不是尚未实现的功能。
