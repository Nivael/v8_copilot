# v8 Copilot API Contract v0

W1 单写的 Batch 2 跨窗口契约。它新增 API 包装对象，不修改
`../v8_answer_contract_v0/schema.json`。

公开对象：

- `ResearchRequest`
- `QuestionInterpretation`
- `RouteDecision`
- `ResearchResponse`
- `StockDossierPayload`
- `ResearchStreamEvent`

`ResearchResponse.answer_card` 继续遵守 `v8_answer_contract_v0`。NDJSON 流只发送完整、
已验证的领域事件，不发送模型 token delta。

重新生成 schema 和固定 fixtures：

```bash
uv run python contracts/v8_copilot_api_contract_v0/export_contract.py
```

W2/W3 可以复制 fixtures 做消费者测试，但不得直接修改本目录。
