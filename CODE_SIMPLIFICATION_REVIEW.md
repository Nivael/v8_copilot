# 第二轮精简复核与实施 — 2026-09-10

基线：第一轮性能分支 `codex/research-performance`，`a56f1d6`。
复核输入：该 worktree 中的 `CODE_SIMPLIFICATION_PLAN.md`（2026-09-09，原为未提交的建议）；
原文已随本轮保留为 [CODE_SIMPLIFICATION_PLAN.md](CODE_SIMPLIFICATION_PLAN.md)，未改写原结论。
本轮目标是减少重复实现和启动依赖，同时保持可复现研究结果。

## 对原方案的判断

重复底层函数和不合理依赖方向的诊断成立，但“先删约 7,400 行、零运行风险”不成立。
缺少 Python importer，不能证明一个命令、冻结契约或历史复算工具已经没有消费者。

| 建议 | 复核结论 / 处理 |
| --- | --- |
| 删除五个 P6B 模块 | 保留。`OPERATING_MODEL.md` 仍直接调用 `p6b_market_cap_backfill.py run`；对应冻结 plan 的 README 也有命令。已完成一次数据回填不等于不再需要恢复或复算。 |
| 删除 research memory 孤岛 | 保留。确实不是当前主链的 Python 依赖，但冻结 manifest 显式指向 Python types，README 提供导出命令；删除生成器/consumer 会破坏契约复现。需要明确的契约退役范围，不能只按 import 图删除。 |
| 重试返回哨兵是静默吞错 | 不成立。QFQ 会写失败 checkpoint，holder 会统计失败股票；两者返回 `partial`，CLI 以非零状态结束。本轮新增测试验证失败后可以恢复，保留这套批处理语义。 |
| 重试首次等待翻倍 | 不能仅比较指数表达式：循环从 0 还是 1 开始必须一起计算。不同任务还有限流、缓存和分批失败语义，本轮不统一重试循环。 |
| provider env 缺白名单 | P8 活动回填处成立。现有 `setdefault` 不覆盖已有 PATH，但可以注入原本缺少的任意键。本轮只允许两个 Tushare 配置键。通用维护器的 env 文件用途不同，未强行纳入。 |
| 所有 digest/SQLite 都可以统一 | 仅合并语义相同的实现。严格 JSON 与 `default=str` 不同；optional source 的空文件摘要与 required source 的异常不同；tuple rows、`sqlite3.Row` 和写事务也不能全局换成一种策略。 |
| `p8_research.digest` 零调用者 | 不准确：`content_id` 和 run 构造等已有内部调用。本轮将算法下沉为无领域依赖的模块，原导出继续有效。 |
| 生产依赖 evals；leaf 为常量/路径加载答案引擎 | 成立并已修复。措辞常量进入已有 `trading_boundary.py`，路径进入 `settings.py`；未让答案引擎反向依赖 LLM 包。引擎导入会加载 Lens JSON，但“导入即打开 SQLite/pandas”并非这里的准确描述。 |
| 合并三个 orchestrator 并删除 V1 | 只统一调用流水线，保留类型、校验顺序、stream 兼容入口。删掉中间类型会扩大契约风险，不能把未直接序列化等同于没有语义作用。 |
| 将 run_kind Literal 改为注册制 | 暂不采用。它约束允许持久化的运行类型；封闭集合在当前规模下有价值，换成注册机制并不自动更简单。 |
| 归档 spike/seed、拆 AnswerCard/governance、改写叙事层与全部 CLI | 本轮不做。未导入的旧脚本不影响主路径耗时；AnswerCard 默认库版本在导入时绑定 Lens，不能按行号机械切开。治理存储搬家和中文输出重写应单独验收。 |

不以删除测试或契约来制造“代码减少 18%”。保留 P7、P8 v1 回测、P8 dry-plan、研究阈值和生产配额。
原建议中的临时源码快照和已有 worktree 也保留。

## 已实施

- 21 处同义 canonical JSON 和 22 处 digest 定义，改为共用 `canonical_json.py`。
  保留原模块的函数别名；严格 serializer 不变。
- 11 处具名、返回 `sqlite3.Row` 的只读连接定义，改为共用 `sqlite_access.connect_ro`。
  保留连接关闭/事务的调用方责任；URI 经过转义，包含 `?/#/%` 的真实文件名也能只读打开。
  不改写连接，不批量替换其余内联 SQL。
- 7 处 provider env loader 共用 `provider_env.py`，保留已有进程环境优先级。
- 将确定性路由本体移动到 `deterministic_router.py`；旧 eval import 保留薄兼容出口。
- `freshness_manifest` 和 `data_maintenance` 从 settings 取路径；LLM boundary 从中立模块取常量。
- `answer_pipeline.py` 统一 HTTP 和 EvidencePack 的编排，离线入口先复制请求并固定 `llm_mode=off`。
- 补齐 `P8_DAILY_RUNBOOK.md` 中冻结盘点文件的生产命令。

按 Git 基线逐文件计数，非测试、非 benchmark Python 从 45,587 行降为 45,353 行，
**净减少 234 行**（包含新公共模块和搬迁后的路由文件，未把移动算成删除）。
这轮的主要收益是移除重复来源和隐式依赖，而不是大幅减少总行数。

## 性能与结果验证

同一 Python 3.12 环境，独立进程交替导入各 5 次，中位耗时：

| 模块 | 基线 | 第二轮 | 说明 |
| --- | --- | --- | --- |
| `llm.boundaries` | 89.98 ms | 3.54 ms | 已加载模块数 421 → 71 |
| `freshness_manifest` | 91.19 ms | 45.42 ms | 不再加载答案引擎 |
| `llm.parser` | 97.76 ms | 48.78 ms | 不再加载答案引擎或 evals |
| `core_router` | 49.77 ms | 49.85 ms | 分层修复，未观察到提速 |

这些是模块导入数据，不能称为整个研究任务快 25 倍。
四个 leaf 在空数据目录下均可导入，也不加载 `answer_engine` 或 `evals`。

真实数据对照：

- 冻结停牌证据下 68,680 条网格记录、3,923 个事件段的摘要及全部库存字段一致；
  低位价稳活跃仍为 163 段 / 100 家，年度计数 64/80/19。
- 14 道真实研究问题使用相同 request ID 和离线模式，完整响应 JSON 逐项一致。
- 全套原有测试仍为 406 通过、相同的 10 个失败；新增 16 个测试通过，覆盖独立导入、
  只读连接、环境键限制、严格序列化、回填失败与恢复。既有失败清单见
  `RESEARCH_PERFORMANCE.md`；最终全套为 **422 通过 / 10 个既有失败**，没有改写旧断言来获得绿色结果。
- 单轮网格对照同时通过，但本轮不从单轮耗时波动推断稳定的全流程提速。

复测命令（从本 worktree，使用已安装依赖的同一个解释器）：

```bash
uv run python benchmarks/import_boundaries.py --baseline ../research-performance \
  --data-root ../../.. --output /tmp/import-boundaries.json
uv run python benchmarks/grid_inventory.py --baseline ../research-performance \
  --data-root ../../.. \
  --suspension-evidence ../../../local_data/v8_copilot/p8_grid_v3_1/suspensions/evidence.json \
  --output /tmp/round2-grid --repeats 3
V8_DATA_ROOT=../../.. uv run pytest
```

代码变更会改变代码指纹，正式 evaluate 前应先生成本版本的 inventory；不复用旧代码 inventory。
未更新研究数据库、未联网抓取、未外发公告正文、未移动任何生产 current manifest。

## 后续优化顺序

1. 对用户实际耗时长的整条命令做阶段计时，区分输入读取、文件摘要、计算、联网重试和输出。
   上一轮典型本地个股取证约 1 秒，不能用脚本数量解释用户的全部等待。
2. 需要退役历史 CLI 时，先列明文档命令、外部文件消费者、冻结版本重现方式，再单独归档。
3. 叙事层先补各路由 golden；回填重试与文件摘要先定义失败/缺失策略，再做第二批公共化。
   不添加跨运行的结果缓存来掩盖性能问题，以免把旧证据当成当前数据。
