# v8 Copilot API Contract v0

`v8_copilot_api_contract_v0` 是 W1 单写、W2/W3 只读的本地服务契约。它包装但不修改
`v8_answer_contract_v0`：`ResearchResponse.answer_card` 必须另外通过既有 AnswerCard schema。

## 公共对象

- `ResearchRequest` / `ResearchContext`：用户问题及可选股票、事件、时间范围。
- `QuestionInterpretation`：只描述对象、意图和歧义，不携带研究事实。
- `RouteDecision`：确定性 router 的最终判定。
- `ResearchResponse`：必须且只能带真实 `answer_card` 或无事实 `fallback` 之一。
- `StockDossierPayload`：只读价格、状态、episode 节点和 lens 摘要。
- `ResearchStreamEvent`：NDJSON 领域事件；事件名仅允许契约列出的八种。

## 不变量

1. LLM 不得修改路由、数字、日期、N、证据等级或 provenance。
2. `claim_block` 只能承载已验证、可回链的 `ValidatedClaim`。
3. 未实现的问题返回 `lens_gap` / `data_debt` / `clarify` / `needs_review` /
   `refuse` fallback，不构造伪 AnswerCard。
4. `degraded` 只表示 LLM 叙述层不可用；确定性结果仍然有效。
5. API 不写研究数据库，也不持久化聊天。

## Schema 与 fixtures

`schema.json` 由 `models.public_contract_schema()` 生成。`fixtures/` 为 W2/W3 的固定消费者样本，
测试会同时检查 Pydantic 模型、JSON Schema 和 checked-in schema 无漂移。
