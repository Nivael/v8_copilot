# v8 Answer Contract v0

`schema.json` 是 W1 发布的首个跨窗口只读契约。W2、W3 和后续 LLM 编排层只消费该版本；缺字段时提交缺口，不直接修改 schema。

核心约束：

- 每张 AnswerCard 必须声明 `contract_version=v8_answer_contract_v0`；
- `lens_invocations[]` 或 `lens_gap[]` 至少一个非空；
- 每个 `body_rows[]` 元素必须有稳定 `row_id`；
- 每个 `analysis_claim` 必须有合法 backing；
- data debt 必须引用统一台账 id；
- evidence 视图的额外语义约束由 Python validator 执行。

JSON Schema 负责跨语言结构校验；`AnswerCard.validate()` 负责交叉引用、证据身份、固定 caveat 和禁用措辞等语义校验。两层都必须通过。
