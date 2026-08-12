# 选择性联网证据架构决策

状态：Accepted

## 当前架构

v8 已有只读 SQLite、公告缓存、episode、Lens、确定性计算、EvidencePack validator、Research Run Ledger 和独立 Experience Repository。API answer 路径不隐式联网，也不写研究数据库。独立数据维护窗口可以更新 canonical 输入。

## 绿地方案

如果从零建设，会把系统拆成三种职责，而不是简单分成“联网回答”和“离线回答”：

1. 当前事实获取：官方公告、交易所/监管、法院/管理人、公司资料和声明的数据提供方；
2. 可复现机制计算：数据库查询、episode/case 去重、Lens、历史分布、事件窗口和价格路径；
3. 证据合成与校验：把前两类证据放进同一个内容寻址 EvidencePack，再形成回答和判断审计。

## 比较过的方案

- 全离线：可复现性最好，但本地快照之后的新公告和管理人渠道会形成系统性盲点。
- 回答时自由联网：时效性好，但网页摘要会绕过本地定义、统计口径和 backing，审计无法闭环。
- 混合证据网关：先运行本地机制，再按 acquisition plan 补当前事实；外部事实只有进入新 EvidencePack 后才能引用。

选择混合证据网关。它复用现有 v8 的 load-bearing contracts，不修改冻结 AnswerCard/API contracts，也不引入第二套研究计算引擎。

## 边界

- 外部事实必须记录 source kind、source mode、URL、发布时间、抓取时间、coverage note 和原子 fact；
- 外部事实标记 `not_mechanism_evidence=true`，只使用 `provenance_ref` backing；
- 本地历史统计和 Lens 不接受网页摘要作为替代输入；
- 外部当前事实与本地快照冲突时并列展示时点和来源，不静默覆盖；
- 需要 PDF 正文、批量覆盖或可重复机制输入时，转入独立材料化，不把临时浏览结果伪装成数据库覆盖。

## 数据维护与治理

维护窗口固定使用 Tushare qfq 和 CNINFO，并用独立 checkpoint SQLite 保存每个来源、每只股票的上次尝试和上次成功游标。价格复权因子变化触发单票完整重建；公告用重叠窗口和 announcement ID 合并。

经验继续是方法而非事实。普通成功回答不自动沉淀；明确反馈形成的 candidate 至少被两个真实
运行复现、白名单回归实际通过、无 blocking conflict 且通用性校验通过后，才由 owner 冻结的
本地策略自动进入去敏 registry。accepted 经验按 cadence 复验，实际失败自动转为 blocked。

## 风险与迁移

- 在线来源可能暂时不可用：保留本地 Pack，显式报告 coverage gap；
- Tushare 凭据可能失效：失败 checkpoint 不推进成功游标，也不切换到未声明价格源；
- 旧 EvidencePack 没有 external evidence：运行审计保持兼容，新运行使用 v2 Pack；
- 选择性联网可能过度触发：acquisition plan 只针对当前事实关键词和明确 coverage gap，机制问题默认离线；
- 经验回归引用可能尚未绑定：标记 unverified，不伪报通过，也不在没有失败时自动封禁。
