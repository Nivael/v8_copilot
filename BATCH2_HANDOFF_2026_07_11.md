# v8 Batch 2 集成交接

Batch 2 在 W1 正式契约/Core/API 基线上接入 W2 LLM adapter 与 W3 React 产品界面。

## 已完成

- API Contract v0、五个只读端点和 NDJSON 领域事件。
- 任意问题的确定性路由与合法 fallback；50 题稳定性门。
- OpenAI Structured Outputs adapter 与 Fake provider；claim 必须回链 backing。
- 主面板、个股面板、真实价格/episode 时间线和 ResearchContext 双向导航。
- OpenAI 不可用或输出被拒绝时保留确定性 AnswerCard。

## 边界

- 不输出买卖、持有、仓位、目标价或交易信号。
- LLM 不读取原始数据库、完整公告库或完整 release library。
- 问题卡和数据债只生成候选，本批次不持久化。
- 本批次仅本机 `127.0.0.1`，无登录、部署和多端同步。

## 验收命令

```bash
uv run python run_seeds.py
uv run pytest tests evals/test_deterministic_router_v0.py
uv run pytest evals/test_llm_pipeline_v0.py evals/test_rewrite_routing_v0.py evals/test_w1_contract_consumer_v0.py
uv run python evals/validate_w2_evals.py
uv run python evals/run_route_eval_50.py
uv run python evals/run_llm_eval.py
cd web && npm test && npm run lint && npm run build
```
