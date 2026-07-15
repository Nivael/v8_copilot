# ST Research Codex Research Orchestrator 重构 PRD

状态：Approved；Phase 1–3 与经验治理增量已实现
日期：2026-07-14
目标版本：v8 后续增量重构
范围：研究入口、证据工具、回答校验、经验沉淀与经验面板

实施记录（2026-07-14）：

- 已增加项目级 Codex 研究 skill、只读 Evidence Gateway 和独立回答 validator；
- 已增加分离的 Research Run Ledger、Experience Repository、反馈提炼和人工晋级闸门；
- Web 首页已改为经验中心，旧问答移到兼容入口，原始问答只在次级运行审计显示；
- 核心五题已通过 EvidencePack → Codex 研究稿 → validator → run ledger 的真实闭环；
- 已增加 Tushare/CNINFO 可恢复增量维护、逐源逐股 checkpoint 和统一 freshness manifest；
- 已增加选择性联网 acquisition plan；联网当前事实必须先进入新的 EvidencePack，离线机制结果保持可复现；
- 已增加 accepted registry 去敏版本化导出、经验冲突检测、30 天到期复验和回归失败自动 blocked；
- Phase 4 Codex SDK 仍是质量对比 gate，未被提前设为默认；
- Phase 5 legacy 退役需经过连续稳定运行，当前保留一键回退面。

## 1. 决策摘要

本次重构不再把 Web 面板作为主要问答入口，也不再由一次性 LLM 调用承担完整研究判断。

新的产品边界如下：

1. Codex 成为面向用户的研究主持人，负责理解问题、选择研究路径、调用工具、形成判断并组织自然语言回答。
2. 现有 v8 引擎保留为只读证据与计算工具，负责股票解析、公告与正文读取、历史样本查询、价格计算、来源新鲜度和结论校验。
3. Web 面板改造为“研究经验中心”，只展示和管理可复用经验，不再承担主要问答职责。
4. 每次真实研究运行自动进入审计运行日志，但原始问题和一次性回答不会自动成为经验。
5. 只有经过抽象、可复现验证和人工接受的经验，才进入正式经验库并在面板中可见。
6. 研究数据库继续只读；经验、反馈和运行日志写入独立存储，不进入研究事实数据库。
7. API answer 路径继续不隐式联网或写研究数据库；Codex 研究窗口可按 acquisition plan 补查当前外部事实，但必须先材料化为带来源的 EvidencePack 项，不能直接流入回答。
8. 冻结 contracts 保持不变。新能力通过独立的经验契约和适配层增量实现。

## 2. 背景与问题

### 2.1 当前系统的有效资产

当前 v8 已经具备以下可继续复用的能力：

- 确定性股票解析和问题路由基础。
- 只读 SQLite、公告增量快照和公告正文缓存。
- 公告、ST 生命周期、episode、价格、股东人数和股权事件查询。
- 历史 episode 去重、右删失和来源新鲜度表达。
- AnswerCard、ResearchNarrative 和 backing 校验。
- 数字、日期、引用、禁用投资指令和来源覆盖边界校验。
- Research Memory 的候选、审阅、接受、合并和反馈契约基础。

这些能力应继续作为研究基础设施，而不是被新入口替换。

### 2.2 当前系统的核心失败

当前主要失败不是 JSON 结构不合法，而是研究主持能力不足：

- 一次性 LLM 调用容易接受错误路由，不能主动发现需要新的查询能力。
- 回答倾向堆叠精确字段，牺牲可读性、判断和重点。
- 面对资料覆盖缺口时过早降级，重复解释“不能确认”，而不是寻找可执行的本地替代路径。
- 对真实问题的修复容易退化成单题补丁，用户需要反复手工测试。
- 问题、答案、查询方法和可复用经验之间没有完成持久化闭环。
- 当前 Research Memory 只有契约，没有正式 repository 和产品化审阅流程。

### 2.3 本次需求的关键澄清

面板中需要沉淀的是“可用经验”，不是“问过哪些问题”。

原始问题、完整回答和工具轨迹只属于审计运行记录。面板中的经验必须能够回答：

- 这类问题应如何识别？
- 需要哪些数据？
- 应执行什么查询或材料化步骤？
- 关键定义是什么？
- 常见错误路由或错误论证是什么？
- 输出怎样才算直接、清楚且有判断？
- 用哪些测试可以证明该经验仍然可用？

## 3. 产品目标

### 3.1 主要目标

1. 用户可以直接在 Codex 中提出自然语言研究问题，不需要先进入专用问答面板。
2. Codex 可以多轮调用本地只读工具，而不是一次性接收证据包后直接生成答案。
3. 最终回答优先给出直接结论和人话逻辑链，精确字段下沉到证据明细。
4. 每次研究运行都有完整审计记录，包括数据截止日、工具调用、证据引用、验证结果和用户反馈。
5. 系统能从真实成功或失败中提出可复用经验候选。
6. 经验中心支持人工接受、编辑后接受、拒绝、合并、阻塞和废止。
7. 已接受经验能够影响后续研究路径，但不能替代重新查询最新数据。

### 3.2 非目标

- 不把历史回答训练成自动事实来源。
- 不把用户问题列表包装成知识库。
- 不允许 Codex 或经验库直接修改研究数据库。
- 不让经验绕过证据校验或提升为验证型统计结论。
- 不在本阶段重新设计冻结 API、AnswerCard、QuestionCard 或 Research Memory contracts。
- 不要求保留当前面板作为主要问答产品。
- 不生成行动性投资指令。

## 4. 核心产品原则

### 4.1 主持人与工具分离

Codex 负责研究判断；v8 工具负责事实、计算和校验。任何一方都不能单独构成完整研究链路。

### 4.2 事实、回答与经验分层

- 事实：来自研究数据库、已验证公告正文、本地材料化产物和带来源的计算结果。
- 回答：某个时间点基于特定证据形成的用户可见叙述。
- 经验：可跨问题复用的路由、查询、定义、分析边界、表达规则或反模式。

三者必须独立存储和引用。回答不是事实，经验也不是事实。

### 4.3 自动记录，人工晋升

研究运行可以自动记录，经验候选也可以自动提出；但 Codex、普通 LLM 或后台规则均不能自行把候选升级为 accepted。

### 4.4 重新执行，不复读旧答案

后续问题命中已接受经验时，系统应复用查询计划、定义和表达规则，然后重新读取最新证据。不得直接返回历史答案正文。

### 4.5 精度下沉，判断前置

主回答首先回答用户真正关心的差异、阶段或先例。样本口径、完整日期、公告 ID 和详细统计进入依据或证据抽屉。

### 4.6 失败也是候选经验

错误路由、证据缺口、不可读回答和用户纠正都可以生成经验候选，但必须抽象为通用规则，不能只记录单个失败问题。

## 5. 用户与核心流程

### 5.1 主要用户

当前阶段主要用户为项目所有者本人。产品优先支持单用户、本地优先和高审计性，不为多租户协作增加额外复杂度。

### 5.2 直接研究流程

1. 用户在 Codex 任务中提出问题。
2. Codex 解析对象、意图、时间和所需维度。
3. Codex 检索适用的已接受经验，只读取方法，不读取旧答案作为事实。
4. Codex 调用只读研究工具获取证据包。
5. acquisition plan 判断是否需要补最新公告、当前公司资料、法院/管理人渠道或当天市场事实。
6. 如需联网，外部事实带 URL、发布时间、抓取时间和覆盖说明进入新的 EvidencePack；历史机制计算仍只读本地版本化数据。
7. Codex形成直接回答、判断依据、不确定性和后续观察项。
8. 校验器验证 backing、数字、日期、来源、新鲜度和边界措辞。
9. Codex向用户返回最终回答。
10. 系统自动写入 Research Run Ledger。
11. 只有发现可复用的新方法或失败模式时，系统才生成 Experience Candidate。

### 5.3 用户反馈流程

用户可以直接使用自然语言反馈，例如：

- “这版可以。”
- “结论太绕，重点应先说阶段差异。”
- “这个数据源没有覆盖管理人渠道。”
- “这不是下一节点问题，是事件窗口和价格路径问题。”

反馈首先绑定到 research run。随后由经验提炼器判断是否形成：

- 表达经验候选；
- 路由经验候选；
- 查询计划经验候选；
- 数据覆盖经验候选；
- 反模式经验候选；
- 不产生经验，只保留运行反馈。

### 5.4 经验审阅流程

1. 用户打开经验中心。
2. 默认看到待审阅的经验候选，而不是问题列表。
3. 用户查看经验摘要、适用条件、来源运行、测试和潜在冲突。
4. 用户选择接受、编辑后接受、拒绝、合并或阻塞。
5. accepted 经验进入正式 registry，并带版本和生效日期。
6. 后续 Codex 研究可检索并引用该经验。

## 6. 产品界面

### 6.1 Codex 作为主要研究入口

Codex 任务是默认交互界面。项目通过专用 skill/plugin 和只读 MCP 工具提供一致的研究流程、数据边界和验证要求。

第一阶段不要求构建新的聊天 UI。现有 Web 问答入口保留为兼容和回归测试入口，但不再是产品主路径。

### 6.2 Web 面板改造成经验中心

面板的一级导航建议调整为：

- 待审经验
- 已接受经验
- 已阻塞经验
- 已合并/废止
- 数据缺口
- 运行审计（次级入口）

面板首页不展示“最近提问”，也不以问题卡数量作为核心指标。

### 6.3 经验卡片

每张经验卡至少显示：

- 经验标题；
- 经验类型；
- 一句话价值；
- 触发条件；
- 适用对象与边界；
- 必需输入；
- 可执行查询计划或工具链；
- 输出要求；
- 反模式；
- 验证测试；
- 来源运行数量；
- 当前状态和版本；
- 最近审阅时间。

候选卡片支持以下操作：

- 接受；
- 编辑后接受；
- 拒绝；
- 合并到已有经验；
- 标记为需要更多证据；
- 转成数据缺口。

### 6.4 运行审计

运行审计仅用于追溯，不属于经验展示主界面。它可以查看：

- 原始问题；
- 最终回答；
- 数据截止日；
- 证据 manifest；
- 工具调用；
- 校验结果；
- agent/model/config 版本；
- 用户反馈；
- 由该运行产生的经验候选。

## 7. 目标架构

```text
User
  │
  ▼
Codex Research Orchestrator
  ├── Experience Retriever ───────► Accepted Experience Registry
  ├── Read-only Research Gateway ─► SQLite / local cache / episode / lens
  ├── Answer Validator
  └── Run Recorder ───────────────► Research Run Ledger
                                      │
                                      ▼
                               Experience Distiller
                                      │
                                      ▼
                               Experience Repository
                                      │
                                      ▼
                                Experience Panel

Separate Materializer ─────────────► verified local cache/artifacts
```

### 7.1 Codex Research Orchestrator

职责：

- 理解真实问题；
- 决定查询顺序；
- 多轮调用研究工具；
- 发现错误假设和覆盖缺口；
- 根据证据作出有限判断；
- 组织用户可读回答；
- 在结束前调用验证器和运行记录器。

Codex 不直接执行任意写 SQL，也不拥有研究数据库写权限。

### 7.2 Read-only Research Gateway

该网关由现有 v8 查询和 AnswerCard 代码逐步抽取而成。它输出 EvidencePack，不负责最终主回答。

首批工具建议：

- `resolve_research_object`
- `build_stock_evidence_pack`
- `build_comparison_evidence_pack`
- `build_restructuring_progress_pack`
- `build_event_window_precedent_pack`
- `read_official_announcement_body`
- `list_source_freshness`
- `validate_research_narrative`

禁止提供可写数据库的通用 SQL 工具。复杂查询应通过版本化 executor 实现。

### 7.3 EvidencePack

EvidencePack 是 Codex 和确定性研究层之间的新适配对象，至少包含：

- `pack_id`
- `question_scope`
- `query_plan_id`
- `rows`
- `lens_invocations`
- `external_evidence`
- `source_freshness`
- `provenance`
- `coverage_gaps`
- `definitions`
- `allowed_claims`
- `forbidden_inferences`
- `validation_refs`

EvidencePack 可以由现有 AnswerCard 适配产生。首阶段不删除 AnswerCard，也不修改其冻结契约。

`external_evidence` 只描述当前外部事实，必须标记 `not_mechanism_evidence=true`。它可以补充本地快照之后的新事实，但不能覆盖 episode、Lens、历史分布或事件窗口等本地计算结果。

### 7.4 Answer Validator

校验器继续确定性执行以下检查：

- 每个事实性结论有 backing；
- 日期和数字存在于证据包；
- 不混淆共同截止日与单股最新日期；
- 不混淆上市公司本体和关联主体；
- 不把描述性样本升级成验证型预测；
- 不使用旧回答作为事实来源；
- 不生成行动性投资指令；
- 证据覆盖不足时保留明确缺口。

校验失败后，Codex应重新组织答案；不得静默删除核心结论后继续输出看似完整的回答。

### 7.5 Research Run Ledger

这是独立的追加式审计库，不是研究事实库，也不是经验库。

建议字段：

- `run_id`
- `thread_id`
- `turn_id`
- `request_id`
- `question_text`
- `normalized_intent`
- `object_refs`
- `evidence_pack_ids`
- `final_answer`
- `validation_report`
- `source_freshness`
- `agent_surface`
- `model`
- `config_digest`
- `started_at`
- `completed_at`
- `user_feedback`
- `experience_candidate_ids`

Ledger 默认写入独立 local-only SQLite。任何导出到仓库的内容都必须删除原始问题、完整回答和本机信息，仅保留经过审阅的抽象经验。

### 7.6 Experience Distiller

经验提炼器读取研究运行和用户反馈，输出结构化 Experience Candidate。

它只在满足至少一个条件时产生候选：

- 发现了新的问题类型或路由规则；
- 形成了可复现的新查询计划；
- 明确了影响多个问题的数据覆盖边界；
- 用户指出了可泛化的表达问题；
- 发现了现有经验的反例或失效条件；
- 将一次失败转化为回归测试和通用反模式。

普通的成功回答、重复问题和仅更新日期的运行不应创建新经验候选。

### 7.7 Experience Repository

Experience Repository 与 Research Run Ledger 分开存储。候选和 accepted 经验都必须标记 `not_evidence=true`。

候选状态机：

```text
candidate ──► accepted
    ├──────► ignored
    ├──────► merged
    ├──────► blocked
    └──────► closed

accepted ──► superseded / merged / closed
```

从 candidate 到 accepted 必须由人工操作触发。Codex 可以推荐，但不能执行晋升。

### 7.8 Separate Materializer

材料化任务负责：

- 获取经过允许的外部官方材料；
- 校验域名、文档 ID、内容类型和大小；
- 提取正文或结构化字段；
- 写入本地缓存或独立材料化产物；
- 记录失败和来源。

Answer 和 Codex Research Orchestrator 只读取材料化结果，不在回答过程中下载或写缓存。

## 8. 可用经验模型

### 8.1 Experience 类型

首版支持以下类型：

- `routing_rule`：如何识别问题类型和避免错误路由；
- `query_plan`：所需数据、查询顺序和 executor；
- `definition`：关键事件、窗口、样本和计算口径；
- `coverage_boundary`：来源能确认什么、不能确认什么；
- `reasoning_rule`：如何从材料形成有限判断；
- `presentation_rule`：如何把复杂材料写成人话；
- `anti_pattern`：已知错误路径及其症状；
- `materialization_recipe`：需独立补齐的数据和校验步骤；
- `regression_case`：保护经验的最小真实或合成测试。

现有 QuestionCard 继续作为内部兼容对象，用于问题语义、路由引用和回归映射。它不进入经验中心首页，也不能仅因被问过或成功回答过就转换成 Experience。QuestionCard 与 Experience 之间只能通过带 provenance 的提炼结果建立关联。

### 8.2 Experience 核心字段

建议新增独立 `v8_research_experience_contract_v0`，不修改冻结 contracts。

字段至少包括：

- `experience_id`
- `experience_version`
- `status`
- `experience_type`
- `title`
- `value_summary`
- `trigger_conditions`
- `scope`
- `required_inputs`
- `query_plan`
- `definitions`
- `answer_rubric`
- `anti_patterns`
- `coverage_boundaries`
- `validation_refs`
- `source_run_refs`
- `supersedes`
- `created_at`
- `reviewed_at`
- `reviewed_by`
- `not_evidence=true`

### 8.3 不得作为经验的内容

以下内容只能留在 Research Run Ledger：

- 某只股票在某日的事实性结论；
- 某份公告的摘要正文；
- 某次回答的完整自然语言文本；
- 单次模型生成的主观推测；
- 没有可复现查询计划的“感觉”；
- 未验证的用户前提；
- 仅因日期变化产生的新答案。

### 8.4 经验晋升闸门

Experience Candidate 只有同时满足以下条件才可 accepted：

1. 已从个案抽象为可识别的问题类或研究规则；
2. 适用范围和不适用范围明确；
3. 必需输入和来源边界明确；
4. 查询或判断过程可以复现；
5. 至少有一个回归测试或验证引用；
6. 不包含时间敏感事实作为通用结论；
7. 不把回答或经验升级为证据；
8. 人工审阅通过。

## 9. 示例经验

### 9.1 招募截止日前连续跌停先例

该经验应沉淀为：

- 类型：`routing_rule + query_plan + definition + anti_pattern`
- 触发：问题同时包含重整投资人招募、截止日前、连续价格状态和历史先例。
- 必需输入：已验证报名截止日、逐交易日价格、ST 状态区间。
- 定义：招募公告日至报名截止日之间，至少两个相邻交易日收盘达到跌停状态。
- 正确查询：事件窗口与价格路径配对，并报告截止日和价格完整覆盖样本。
- 反模式：路由到 M6 下一个公告节点等待期。
- 输出要求：先回答是否存在，再列代表案例；样本口径和当前个案未核验部分单列。
- 回归测试：真实问题和至少两个合成案例。

面板不应把“沐邦今天是否跌停”或某次统计结果本身显示为经验。

### 9.2 可读性与判断前置

该经验应沉淀为：

- 类型：`presentation_rule + anti_pattern`
- 触发：比较、阶段判断或公告摘要问题。
- 规则：主回答先给最重要的实质差异，精确统计下沉到依据。
- 反模式：在总览中堆叠公告数量、多个截止日和价格窗口，却不回答真正差异。
- 校验：总览必须能脱离证据明细单独读懂；不能出现自相矛盾的阶段排序。

## 10. Codex 工作方式

### 10.1 Skill/Plugin

创建项目级 ST Research skill/plugin，持久化以下工作规则：

- 先直接理解问题，再决定工具调用；
- 优先复用 accepted experience；
- 研究事实只来自 EvidencePack；
- 缺口不足以阻止有价值回答时，先回答可确认部分；
- 需要新材料时产生 materialization request，不在 Answer 路径联网；
- 回答先给判断，再给逻辑链；
- 完成前调用 validator 和 run recorder；
- 仅在发现可复用增量时提出 experience candidate。

### 10.2 Thread 策略

- 同一股票或同一研究主题可以在同一 thread 中连续追问。
- 不使用一个无限增长的全局 thread 承载所有股票和所有问题。
- 新 thread 通过 accepted experience 和明确研究上下文恢复能力，而不是依赖历史对话记忆。
- 每次运行都记录 thread/turn 标识，便于审计和复现。

### 10.3 Codex SDK 决策门

Codex SDK 可以在后续作为无专用面板的轻量研究入口和精确运行捕获器，但不能直接假设 SDK 运行与当前 Codex 任务具有完全相同的质量。

在切换正式入口前，对不少于 20 个真实问题比较：

- 当前 Codex 任务；
- Codex SDK pilot；
- legacy API 路径。

比较维度：直接性、判断质量、证据有效性、遗漏、可读性、延迟和成本。只有 SDK pilot 达到验收线后才进入默认路径。

## 11. 数据与权限边界

### 11.1 研究数据

- SQLite 使用只读 URI，并启用 query-only 防护。
- 公告正文只从 SQLite 或已验证本地缓存读取。
- 研究工具不得修改研究表、刷新表或缓存。
- 不向 Codex 暴露研究数据库写权限。

### 11.2 运行和经验数据

- Research Run Ledger 与 Experience Repository 使用独立数据库。
- 只允许专用 repository API 写入。
- 运行日志不可被查询层当作事实证据。
- accepted experience 可导出为版本化 registry；原始问题和回答不进入 registry。

### 11.3 网络

- 默认研究回答完全离线。
- 外部官方材料获取必须走材料化任务。
- 需要把问题和证据发送到外部模型时，遵循明确授权和最小必要原则。

### 11.4 敏感信息

- 不在仓库中写入 secret、本机绝对路径或认证信息。
- 运行日志默认 local-only。
- 导出经验前执行隐私和路径扫描。

## 12. 兼容与迁移策略

### Phase 0：冻结基线与验收集

目标：在重构前保留当前可工作的确定性能力。

交付：

- 保存现有真实问题 golden set；
- 记录 legacy 路径质量和延迟基线；
- 保持当前未完成修复可回溯；
- 冻结 contracts diff 为 0。

退出条件：所有现有测试和真实问题基线可重复运行。

### Phase 1：抽取只读 Research Gateway

目标：把现有回答执行器拆成可供 Codex 调用的 EvidencePack 工具。

交付：

- AnswerCard 到 EvidencePack 的兼容适配器；
- 首批 bounded research tools；
- query-only 数据库连接；
- validator 独立入口；
- 工具级合成与真实数据测试。

退出条件：legacy API 与新 gateway 对同一查询返回一致事实和 freshness。

### Phase 2：Codex Research Workbench

目标：用户可以直接通过 Codex 完成真实研究。

交付：

- ST Research skill/plugin；
- Research Gateway MCP 接入；
- 多轮查询和校验闭环；
- 运行日志写入；
- legacy 面板继续可用作回归入口。

退出条件：核心真实问题无需用户手工迭代即可达到可读性和证据验收要求。

### Phase 3：Experience Repository 与经验中心

目标：把可复用经验而非问题历史沉淀为产品能力。

交付：

- 新增经验 contract；
- Research Run Ledger repository；
- Experience Candidate distiller；
- 人工 review 状态机；
- 经验中心前端；
- accepted experience 检索器。

退出条件：经验候选可从真实反馈产生，人工接受后能影响后续查询计划，同时不复读旧答案。

### Phase 4：Codex SDK Pilot

目标：评估是否需要把 Codex 从桌面任务入口产品化为本地 host。

交付：

- 线程启动、续接和精确 final response 捕获；
- 与 Research Run Ledger 自动关联；
- 20 题对比评测；
- 延迟、成本和失败恢复报告。

退出条件：pilot 质量不低于当前 Codex 任务，且运行稳定性满足日常使用。

### Phase 5：Legacy 主回答路径退役

目标：移除一次性 LLM composer 的主路径职责。

交付：

- legacy 路径改为 fallback 或回归测试；
- 面板问答入口降为兼容入口；
- 清理重复提示词和只为旧 composer 服务的逻辑；
- 完成回滚开关和迁移说明。

退出条件：Codex 主路径和经验闭环连续稳定运行，且可一键回退 legacy。

## 13. 验收标准

### 13.1 研究质量

- 主回答第一段直接回答问题，不以系统口径或数据表说明开头。
- 比较问题给出最重要的实质差异，不只是并列字段。
- 有材料时组织材料，不因单一来源缺失而无价值降级。
- 不确定性与数据缺口单列，不吞掉可确认结论。
- 每条事实性结论均有有效 backing。
- 描述性样本不升级为确定性未来判断。

### 13.2 经验质量

- 面板首页不展示原始问题流。
- 每张 accepted 经验都有触发条件、必需输入、边界、反模式和测试。
- 普通重复回答不会产生新候选。
- 单票事实和时间敏感结论不能通过晋升闸门。
- Codex/LLM 不能自行执行 accepted 状态转换。
- accepted 经验被使用时仍重新查询最新数据。

### 13.3 数据安全

- Answer 路径研究数据库写入次数为 0。
- Answer 路径网络请求次数为 0。
- 材料化任务与 Answer 进程可独立启动和审计。
- 冻结 contracts diff 为 0。
- 仓库文档无 secret、本机绝对路径或无效内部链接。

### 13.4 回归问题

至少覆盖：

- 最新公告正文摘要；
- 重整/招募当前阶段与下一可核查节点；
- 双股实质比较；
- 单股开放分析及来源 freshness；
- 招募截止日前连续价格状态的历史先例；
- 非公司公告渠道覆盖缺口；
- 当前日期晚于本地价格快照；
- 无 episode 股票不得继承全局日期；
- 回答校验失败后的重试与确定性 fallback。

## 14. 可观测性

每次运行至少记录：

- route/experience 命中；
- 工具调用序列和耗时；
- EvidencePack 数量；
- 各来源 freshness；
- validator 失败原因；
- 回答是否重试；
- 是否产生 experience candidate；
- 用户反馈类别；
- 最终人工 review 结果。

核心质量指标：

- 首次回答人工接受率；
- 每题平均人工重试次数；
- 无效或重复经验候选率；
- accepted 经验后续复用次数；
- 经验命中后仍发生同类错误的比例；
- 证据校验失败率；
- 本地完全可答问题的端到端延迟。

## 15. 风险与缓解

### 15.1 Codex 质量无法在 SDK 中完全复现

缓解：先以当前 Codex 任务作为主入口；SDK 只做 pilot，经过真实问题对比后再切换。

### 15.2 Agent 延迟和成本高于一次性调用

缓解：限定工具集合、复用 EvidencePack、并行只读查询、缓存 accepted experience 检索，不缓存最终事实答案。

### 15.3 自动沉淀导致错误放大

缓解：自动产生 candidate，但 accepted 必须人工触发；所有经验保留来源运行和测试。

### 15.4 面板候选堆积

缓解：设置 novelty gate、语义去重、相似候选合并和待审上限；重复运行只增加 provenance，不新建经验。

### 15.5 经验过度贴合单票

缓解：晋升时强制检查触发条件是否可跨对象复用；单票事实只能作为测试或来源运行。

### 15.6 accepted 经验过期

缓解：经验带版本、验证日期和 supersedes；回归失败后自动标记 blocked，等待人工修订。

### 15.7 新旧路径长期并存形成双重逻辑

缓解：每个 phase 都设退出条件；Phase 5 明确 legacy 只保留 fallback 和回归职责。

## 16. 回滚策略

- 使用配置开关在 `codex_orchestrator` 与 `legacy_composer` 之间切换。
- Research Gateway 首阶段只做适配，不删除旧 executor。
- Experience Repository 独立，不影响研究数据库和 legacy API。
- 新面板路由可单独关闭。
- 任何阶段失败均可停止新入口，同时保留已记录运行和候选经验。

## 17. 实施优先级

P0：

- Research Gateway 与 query-only 防护；
- Codex ST Research skill；
- Answer Validator 独立工具；
- Research Run Ledger；
- 真实问题自动验收脚本。

P1：

- Experience contract 与 repository；
- Experience Distiller；
- 经验中心候选审阅；
- accepted experience 检索与引用。

P2（已实现基础治理）：

- Codex SDK pilot；
- 自动线程恢复；
- 经验冲突检测；
- accepted registry 导出和跨环境同步。

当前已完成冲突检测、去敏 registry 导出、定期复验和失败自动 blocked；跨环境自动同步仍不在本地单用户版本的必需范围。

## 18. 已确定的运行决策

1. 当前 Codex 任务继续作为默认研究入口，SDK 只保留为后续质量 gate；
2. local-only SQLite 保存运行、候选与治理状态，accepted experience 另导出为去敏、内容寻址的 v1 registry；
3. 接受仍只允许 owner 在面板明确操作；blocking conflict 会阻止接受；
4. accepted experience 默认每 30 天复验一次；回归失败自动 blocked；
5. 普通成功回答不自动沉淀为经验。

## 19. Done 定义

本重构只有在以下条件同时成立时才算完成：

- 用户日常研究不再依赖专用问答面板；
- Codex 可以稳定调用只读证据工具并输出经校验的人话回答；
- 每次运行可审计但不会污染研究事实库；
- 面板展示的是可复用经验，而不是提问历史；
- accepted 经验必须人工晋升并带测试；
- 后续相似问题会复用方法、重新查询数据，而不是复读旧答案；
- legacy 主回答路径可以安全退役或一键回滚。
