# v8 P8-0 dry-plan 契约

状态：**frozen before P8 outcome analysis**
日期：2026-09-04
契约版本：`v8_p8_0_dry_plan_v1`
父 PRD：[V8_P8_RESEARCH_FUNNEL_PRD.md](V8_P8_RESEARCH_FUNNEL_PRD.md)

## 1. 目的

P8-0 先回答“现有数据能诚实做出什么”，再决定物化范围。它不证明壳价值、前哨公告或
量价形态有效，也不允许用未来硬节点或收益选择阈值。

本轮必须盘清五件事：三类成交情景参考是否有同口径样本；旧股东权益账能闭合到什么程度；
公告正文能否按内容摘要补齐和抽取；持续型量价特征有多少可计算观察；筹码代理的权限、语义
和覆盖是否足以进入研究层。

## 2. 运行边界

### 2.1 P8-0a：本地只读盘点

- 所有 P6/P7/基础 SQLite 输入以 read-only URI 打开；
- 不刷新公告、价格、membership、market factors 或 valuation episode；
- 不调用 LLM，不根据标题候选升级事实；
- 不写 `p8_research_v1.sqlite3`、current pointer、checkpoint 或生产 registry；
- 只允许写命令行显式指定的 JSON/Markdown/HTML 报告。

### 2.2 P8-0b：有界 provider probe

- 只有显式 `--probe-provider` 才联网；
- 只对冻结接口、固定日期和少量股票请求；不做历史回填；
- token、请求头和完整错误体不得进入报告；
- 返回只进入 probe 报告，不写 canonical 数据库；
- 无权限、空返回或限流是合法结果，不自动换源。

### 2.3 P8-0c：有界正文可得性 probe

- 只按公告 ID/content digest 选择固定样本；同一公告不得按 symbol-day 重复抓取；
- 样本分层固定为标题硬节点、一般重整进展、控制权、风险警示、审计五类；
- 先使用已有缓存；只有显式允许网络时才补原文；
- 只评价正文/PDF 是否可得、是否能抽取文字、页数/字符数和来源稳定性，不在本阶段读取
  后续结果评价抽取质量。

## 3. 冻结输入与来源优先级

报告必须登记 git commit、运行时间、时区、`as_of`、文件摘要和 checked-through。输入包括：

1. 基础库的 point-in-time ST membership、公告索引、正文缓存和 qfq 日线；
2. C14 point-in-time 总市值/股本快照；
3. `valuation_episode_v1`，P6 verified 边界优先，provisional 只作库存；
4. `p6b_asset_equity_v1` 或同等 P6B-2 资产/旧股东权益试点；
5. `p7_intelligence_v1` 的公告、bundle、状态候选和硬节点；
6. `market_activity_v1` 的原始活动事实、排除与覆盖；
7. ST 等权、中证 2000 和全指市场语境。

P8 不回写这些输入。P8B 正文核证形成的新派生事实只能进入 P8 独立 append-only 层。

## 4. P8A 成交情景参考盘点

三类参考必须分账盘点，不得先拼成“壳价值”样本：

- `strategic_entry_reference`：受让价、实际受让股份、转增后总股本、原股东保留股份、现金投入、
  锁定期、产业/清偿义务、`available_as_of`；
- `failure_exit_reference`：最后可观察交易日、最后可观察旧股东权益市值、停牌/陈旧价、退市
  终点和总损失压力口径；
- `public_node_reference`：法院受理、方案批准、执行完毕、撤销风险警示后首个可观察交易日的
  总市值与旧股东权益值，以及资本结构污染。

每类必须输出：候选条数、公司数、精确旧股东口径数、range-only 数、unknown 数、正文支持数、
资本结构污染数、可用时点完整率。P8-0 不填猜测值，不用账面净资产替代旧股东权益。

## 5. 分层容量与放宽路径

对滚动 12/18/24 月分别计算 `stage × delisting_risk_type × board × regime_version` cell
occupancy，并模拟唯一允许的放宽阶梯：

1. exact；
2. drop board；
3. frozen adjacent-stage group；
4. window 12→18→24 months；
5. raw points only。

所有输出同时给 `n` 和不同公司数。分位发布最低门固定为 8 个观察且 5 家公司；dry-plan 后
只许上调，不许因样本稀疏下调。`unknown` 不并入已知层。

相邻阶段组在读取 outcome 前冻结：

- `distress_entry`：`st_distress_only`、`restructuring_application_disclosed`；
- `pre_judicial`：`pre_restructuring_started`、`investor_recruitment`；
- `formal_process`：`formal_restructuring_accepted`、`investor_agreement_signed`；
- `plan_resolution`：`plan_key_terms_disclosed`、`plan_approved`；
- `execution_exit`：`plan_executed`、`risk_warning_removed`。

## 6. P8B 正文与事件图盘点

必须报告：

- shortlist 公告总数、已有正文数、正文缺失数、正文内容摘要去重数；
- 按五类样本的 HTML/PDF/扫描 PDF 可得率、文本抽取率和重复附件率；
- P6 verified、P7 title-derived 与正文待核证事件的重叠；
- 五条 track 的候选节点数量、冲突和 unknown；
- 可自动核证的确定性标题/正文事实与必须走结构化 LLM 的数量；
- 按公告 ID 请求、正文抽取、LLM 抽取的请求量、预计时间、缓存与存储预算。

盘点不得把 P7 `llm_route` 当成已运行 LLM，也不得把 title-only 事件升级为 body-verified。

## 7. P8C 特征容量盘点与阈值冻结

只使用截至观察日可得的数据，统计以下特征的可计算率和横截面容量：

- `cum_turnover_log_excess_10/20`；
- `elevated_day_ratio_20`；
- `range_compression_20`；
- `price_drift_20` 及相对 ST 等权/中证 2000；
- `amount_weighted_log_price_slope_20`；
- `st_turnover_regime_20`。

只允许使用特征自身的历史分布和每天候选容量冻结形态阈值。禁止读取之后 5/10/20/60 日的
公告、硬节点或收益。报告 broad/base/strict 三组**容量候选**，并在进入实现前机械选择每天
中位不超过 20、P90 不超过 30 且覆盖最高的一组；并列时选择更严格的一组。后续回测不得
更换本轮选择，只能发布新 contract version。

## 8. 筹码代理 provider probe

| 接口 | 固定用途 | 语义门 |
| --- | --- | --- |
| `stk_holdernumber` | 持有人户数披露变化 | 必须使用公告可得日，不能按报告期提前 |
| `top_list` / `top_inst` | 公开龙虎榜与席位事实 | 缺失不等于没有机构交易 |
| `block_trade` | 大宗成交价、数量、营业部 | 只称公开大宗交易，不推断资金主体 |
| `margin_detail` | 融资余额变化 | 非两融标的缺失不作零值 |

每个接口记录权限、官方字段、实际字段、固定样本返回量、最早/最晚日期、重复键、可得日期
语义、请求限制和预计全量成本。不可用即 `unavailable`，不阻塞 P8A/P8B/P8C/P8E。

## 9. P8E 端点与回报可计算性

按 episode 报告：verified 起止边界、起点/节点后的下一个合格收盘、qfq 价格、ST 等权和中证
2000 同期基准、停牌/一字板、退市双终值、股本跳变和旧股东稀释字段覆盖。

必须分别给出：

- `observable_qfq_path` 可计算 episode 数；
- `old_shareholder_equity_path` exact/range/unknown 数；
- 因退市终值、资本结构或时点不可得而被截断的数量；
- 可组成真实同期日历组合的交易日和股票覆盖。

qfq 可算不得冒充旧股东权益账精确闭合。

## 10. 输出 schema

JSON 顶层至少包含：

- `contract_version`、`plan_id`、`content_digest`、`generated_at`、`as_of`；
- `git_provenance`、`input_inventory`、`source_boundaries`；
- `scenario_reference_inventory`、`cell_occupancy`、`relaxation_capacity`；
- `body_inventory`、`event_graph_inventory`、`llm_request_budget`；
- `activity_feature_capacity`、`frozen_shape_profile`；
- `chip_provider_probe`、`return_endpoint_inventory`；
- `request_budget`、`storage_budget`、`hard_blockers`、`non_blocking_gaps`；
- `safe_defaults`、`recommended_next_step`、`human_decisions_required`。

Markdown/HTML 报告必须结论在前，不把逐股阅读转交 owner。

## 11. 出口门与停止条件

进入 P8 实现至少要求：

1. 输入摘要和 point-in-time 边界可追溯；
2. P8B 能区分 body-verified、title-derived 和 missing；
3. P8C 至少有一组不看 outcome 冻结的可运营容量阈值；
4. P8E 明确区分 qfq 观察账与旧股东权益账；
5. production writes 仍为 0。

模块独立停止：P8A 样本不足时降级为原始点；P8B 正文不足时只物化已核证子集；筹码接口
不可用时 P8C 继续且代理显示 unavailable；P8E 旧股东账不闭合时保持 range/unknown。

默认 `human_decisions_required=[]`。只有新增付费数据源、改变 24 月上限、改变权益经济对象或
放宽 fail-closed 边界，才请求 owner 一次性决定。
