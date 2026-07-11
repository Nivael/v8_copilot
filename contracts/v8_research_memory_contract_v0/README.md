# v8 Research Memory Contract v0

本契约落实 D-053，只定义 Research Memory 的对象、身份、来源、状态与迁移语义。
P3.1 不包含 SQLite、repository、写 API、聊天持久化或 UI 写操作。

## 边界

- v5/v6 研究库、M6 episode index、v7.4 release library 永久只读。
- `QuestionCard`、`DataDebtCard`、`QueryTemplateRecord`、`ReviewItem`、
  `FeedbackEvent` 与 `MemoryLink` 是 Memory 持久对象，且恒为 `not_evidence=true`。
- `ResearchRunRef` 是来源身份，`SedimentationResult` 是操作结果；二者不是知识实体。
- 不产生 evidence/lens 身份，不提供 release-library 晋升路径。
- 不修改冻结的 AnswerCard v0、API v0/v1、QuestionCard v0 或 QueryTemplate v0。

## 身份规则

持久对象携带 `memory_id`、`canonical_key` 和 `dedupe_key`。调用方提交结构化语义，
由 `build_*` 工厂生成三者；LLM 不提交 ID、key 或 lifecycle `status`。

- `canonical_key` 只由对象类型、结构化 intent、scope、字段集合、时间语义或版本化
  registry identity 组成。
- `dedupe_key = sha256(canonical_key)`；`memory_id` 由对象前缀和该摘要生成。
- 自然语言问题、展示标题、run ID、AnswerCard ID 与 ResearchResponse ID 不进入目标对象 key。
- 不同来源使用 `MemoryLink` 多对一回链，不通过复制知识对象保存来源。
- 固定 `QC-20260710-*` 以 seed ID 锚定 canonical identity；`QC-CAND-*` 仅作来源候选，
  不会成为 Memory ID。

股票代码、数组顺序和重复项在 key 前规范化；时间窗口语义保留在 key 中。

## 生命周期

通用状态为 `candidate`、`accepted`、`ignored`、`merged`、`blocked`、`closed`。
合法 transition 表在 `fixtures/status_transitions.json`。`merged` 只能由人审明确指定
目标，禁止系统自动合并。Review queue 的 active 上限为 20；P3.1 只冻结这一语义，
P3.2 repository 负责原子容量检查。

QuestionCard 的 Memory lifecycle `status` 与原研究路由状态 `research_status` 分离。
这样可以无损保存 `answerable`、`needs_data`、`needs_review`，也可保留尚未分配
外部债卡编号的 `debt_ref_status=needs_assignment`。

## QueryTemplate

QT-001 到 QT-008 保留现有 ID 和 `not_evidence=true`。Memory record 保存 lifecycle、
来源、parameter/outcome semantics 与 caveat；`executor_ref` 只引用版本化 code registry。
草案只能是不可执行的 `candidate`。执行定义仍以
`contracts/v8_query_template_contract_v0/registry.json` 为真相源。

## Seed migration

`fixtures/seed_migration/` 固定 15 条 seed 的无损迁移结果：

- 输入 SHA-256 为 `d98583e8d651ce8cf4cae41e87cfca342142b814f675833e43c174f4964fd559`；
- 第一次导入 15 created；第二次导入 0 created / 15 existing；
- 保留组合 scope、旧 `debt_ref_status`、固定 QC ID、状态、view、source 和债卡引用；
- 用户问法通过 source alias/link 保存，不覆盖 seed canonical question。

## 消费与导出

运行导出：

```bash
python contracts/v8_research_memory_contract_v0/export_contract.py
```

W0/W2/W3 可调用 `consumer.validate_all()` 校验 schema、正负 fixtures、seed 幂等语义、
QT registry、route QC 覆盖和冻结契约 checksum。`schema.json` 只从 Python types 生成，
不得手写第二份定义。
