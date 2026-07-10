# v8_copilot — ST Research Copilot Core（P1）

独立、只读的证据化问答引擎。v8 消费层第一条腿（"回答问题"）的可运行骨架。
产品定义由 D-052 和统一版 v8 PRD 管理；本仓只保留可执行实现、版本化契约和验收资产。

## 脊梁（D-052 修正案）

最小闭环 = **QuestionCard → LensInvocation → AnswerCard → QuestionCard/DataDebt**。
lens invocation 才是 v8 的脊梁，AnswerCard 不是最终抽象。每张答案卡必须显式记录它
消费了哪些 **v7.4 release record**（`shared_data/v7/release_library_v1/`，9 条真实 record）、
各自 kind、贡献了哪个 answer section；**无可用 lens → 显式 lens_gap → 沉淀 question_card/data_debt**，
不得用 sqlite+手写逻辑冒充 lens 消费。

## 是什么

把 v7 学到的"证据菜单三段式"落成参数化的 answer-card 生成器：任何答案 =
**lens_invocations（脊梁）+ query/checklist 主体 + data_debt 缺口行 + 固定 caveat 块**，
每张卡必带 出处 / as_of / 样本范围 / 证据等级 / 缺口 / **lens_invocations 或 lens_gap /
库版本 / episode 版本 / 数据快照 as_of**。覆盖 D-050 五视图里的 query / checklist /
methodology / data_debt；evidence 视图已接 release_library_v1（RL-A-003 等）。

## 红线（硬编在 AnswerCard.validate）

- 不输出买卖/持有/仓位/交易信号/排序权重措辞——forbidden-wording guard 会拒绝出卡。
- data_debt 行必须挂既有债台账 id（不另起第二本账）。
- methodology/data_debt 视图不得携带 evidence/effect 结论式证据等级。
- 输出恒为历史路径描述，不表示可交易/可预测/可复现。

## 运行环境

W1 使用独立 `uv` 环境，Python 版本和依赖由 `.python-version`、`pyproject.toml`、
`uv.lock` 固定。不要再使用系统 `python3` 直接运行。

```bash
uv sync --group dev
uv run pytest
uv run python run_seeds.py
```

## 契约与文件

- `lens_binding.py` — **脊梁**：LensRegistry（只读加载 pinned v1 库）+ candidate_lenses（按主题标签/cluster 精确匹配）+ LensInvocation + LensGap。
- `answer_engine.py` — AnswerCard、AnalysisClaim/backing、只读数据访问和 card builders。
- `contracts/v8_answer_contract_v0/` — W1 单写、W2/W3/LLM 只读的 JSON 契约。
- `tests/` — validator、release reader 与真实数据集成测试。
- `run_seeds.py` — 生成七张 P1 seed card，产出 `out/answer_cards.{json,md}`。
- `out/` — 生成的答案卡（JSON + 人话 Markdown）。

## 治理

独立消费者：不 import forum_signals / v7 内部模块；只读
`shared_data/v5/.../st_stocks_v5_backup.sqlite3`（ro URI）+ M6 episode index。
本地原型，生成物只进 `out/`。

## 已验证（2026-07-10，W1）

七张种子卡覆盖：

- query：重整节点 4/10/14 天、ST 两周分布、单票 ST 生命周期；
- checklist：沐邦观察窗口；
- evidence：RL-A-001、RL-A-002 的 N/effect digest/反例/wording；
- data_debt：D-051A 省份映射稳定出口；
- lens_gap：重整时点、两周横截面、ST 原因绑定等缺口。

所有卡必须同时通过 `AnswerCard.validate()` 和
`contracts/v8_answer_contract_v0/schema.json`。

## W1 边界

W1 单写共享契约和 Core。Question routing/eval 属于 W2，UI 属于 W3，LLM 编排必须等
`v8_answer_contract_v0` 验收后接入。任何新事实字段先进入确定性 Core，再暴露给 LLM/UI。
