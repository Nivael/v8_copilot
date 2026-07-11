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

- `canonical_key` 是字段排序固定的规范 JSON；数组先去重排序，股票代码和枚举先规范化。
- `dedupe_key = sha256(canonical_key)`；`memory_id` 由对象前缀和该摘要生成。
- 自然语言问题、展示标题、run ID、AnswerCard ID 与 ResearchResponse ID 不进入目标对象 key。
- 不同来源使用 `MemoryLink` 多对一回链，不通过复制知识对象保存来源。
- 固定 `QC-20260710-*` 保留为外部迁移身份，但不进入 canonical key；15 张 seed 通过
  `fixtures/seed_migration/semantic_mapping.json` 补齐 intent/dimensions 后，与在线问题
  使用同一语义公式。`QC-CAND-*` 仅作来源候选，不会成为 Memory ID。

`ResearchRunRef` 保存 route、snapshot/as-of、request/response/answer contract versions，
并用 `sha256-canonical-json-v1` 内容摘要固定当次来源上下文；run/AnswerCard identity
仍只进入 source link，不进入任何目标对象 key。

股票代码、数组顺序和重复项在 key 前规范化；时间窗口语义保留在 key 中。

冻结的实体 key 公式为：

- QuestionCard：`kind + object_scope + intent + dimensions + time_scope_semantics`；
  `view` 与 `needs_data` 仅描述当前回答能力，不进入 key。
- assigned DataDebt：`data_debt + external_debt_ref`；同一正式债号不会因字段描述变化而分裂。
- unassigned DataDebt：`data_debt + object_scope + missing_assets + missing_fields`。
- QueryTemplate：`query_template + executor_ref + parameter_schema + outcome_semantics`；
  草案使用显式 `proposed_executor_ref`。
- ReviewItem：`review + uncertainty_type + subject_ref + decision_unit`。

## 生命周期

通用状态为 `candidate`、`accepted`、`ignored`、`merged`、`blocked`、`closed`。
合法 transition 表在 `fixtures/status_transitions.json`。在线候选的 accepted/ignored 和
所有 merge 必须由人审决定；LLM 不能改变状态。冻结 seed 只通过显式
`actor_type=migration + context=seed_bootstrap` 路径进入 accepted。Review queue 的 active
上限为 20；P3.1 只冻结这一语义，P3.2 repository 负责原子容量检查。

QuestionCard 的 Memory lifecycle `status` 与原研究路由状态 `research_status` 分离。
这样可以无损保存 `answerable`、`needs_data`、`needs_review`，也可保留尚未分配
外部债卡编号的 `debt_ref_status=needs_assignment`。

## QueryTemplate

QT-001 到 QT-008 保留现有 ID 和 `not_evidence=true`。Memory record 保存 lifecycle、
来源、`parameter_schema`、outcome semantics 与 caveat；`executor_ref` 只引用版本化
code registry。草案必须提供 proposed executor identity，且只能是不可执行的
`candidate`。执行定义仍以
`contracts/v8_query_template_contract_v0/registry.json` 为真相源。

## Seed migration

`fixtures/seed_migration/` 固定 15 条 seed 的无损迁移结果：

- 输入 SHA-256 为 `d98583e8d651ce8cf4cae41e87cfca342142b814f675833e43c174f4964fd559`；
- 第一次导入 15 created；第二次导入 0 created / 15 existing；
- 保留组合 scope、旧 `debt_ref_status`、固定 QC ID、状态、view、source 和债卡引用；
- 用户问法通过 source alias/link 保存，不覆盖 seed canonical question。
- 每张 seed 与同 scope/intent/dimensions/time 的在线问题得到相同 dedupe key；15 张 seed
  自身的语义 key 保持唯一。

## FeedbackEvent

反馈类型固定为 `useful`、`not_useful`、`scope_error`、`missing_evidence`、
`wording_issue`、`other`；目标支持 ResearchRun、AnswerCard、ResearchResponse 和
QuestionCard。反馈只追加事件和回链，不改写历史回答。

## 消费与导出

运行导出：

```bash
python contracts/v8_research_memory_contract_v0/export_contract.py
```

W0/W2/W3 可调用 `consumer.validate_all()` 校验 schema、正负 fixtures、seed 幂等语义、
QT registry、route QC 覆盖和冻结契约 checksum。根 schema 是带 `record_type`
discriminator 的公共 union，拒绝空对象；每个 fixture 同时经过根 JSON Schema 和
Pydantic 语义校验。`schema.json` 只从 Python types 生成，不得手写第二份定义。
