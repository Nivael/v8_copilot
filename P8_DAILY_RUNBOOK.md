# P8 日常研究漏斗运行手册

P8 只消费已经完成的 P6/P7 和公开市场数据，不回写它们。下面命令均从仓库根目录执行；
`V8_DATA_ROOT` 应指向共享 `st_research` 根，实际路径可由 portable 环境注入。

## 每个交易日的顺序

1. 先按 [P7_DAILY_RUNBOOK.md](P7_DAILY_RUNBOOK.md) 完成名单、公告、价格、市场活动和基准刷新；
2. 构建/更新五轨事件图；`event_frontier` 只接收正文核证或机械核证节点，标题节点只留在待补证探索层；正文 LLM 只有在 owner 明确允许公开公告正文发送到 OpenAI 后运行；
3. 物化持续型活动与 D0–D4 互斥箱；
4. 拉当日公开筹码旁证，股东户数请求按缓存只补当前成员；
5. 更新阶段回报、三类情景参考、四通道漏斗和真实日历 shadow 组合；
6. 更新回测成绩单和离线面板；
7. 所有 run 对齐同一 `as_of` 后显式移动 P8 current manifest。

## 核心命令

常规日更优先使用唯一入口。它会按固定顺序完成八类物化、离线面板和 current manifest；任一
步骤失败都不会发布半套结果：

```bash
python p8_daily.py \
  --as-of YYYY-MM-DD \
  --dry-plan-json <local_data>/p8_0_dry_plan_v1.json \
  --provider-env-file <local-tushare-env> \
  --allow-provider
```

只有取得下文的数据外发授权后，才在同一命令额外加 `--allow-llm`。各分步命令用于补跑、
排障和审计，不是日常首选入口。

形态 profile 来自冻结的 P8-0 JSON，不能用回测结果改：

```bash
python p8_materialize_activity.py \
  --start-date 2025-02-26 --through YYYY-MM-DD \
  --dry-plan-json <local_data>/p8_0_dry_plan_v1.json
```

没有正文外发授权时运行确定性事件图；这会保留 title/provisional 边界：

```bash
python p8_event_graph.py \
  --start-date 2021-03-17 --through YYYY-MM-DD
```

owner 已明确批准“把公开上市公司公告正文发送给 OpenAI API”后，才可运行。当前有 734 份
公开公告正文，共 803 个分块调用、约 650 万字符；API 明确使用 `store=false`。7,628 条缺正文
记录已经按公告 ID 输出到 `p8_body_missing_queue_v1.json`，不会在本步伪造补齐：

```bash
python p8_llm_extraction.py --allow-llm \
  --start-date 2021-03-17 --through YYYY-MM-DD \
  --workers 4
```

该命令以 `announcement_id + content digest + chunk index + extraction contract + model + prompt version`
缓存；规则/模型不一致、低置信、引用无法在正文定位都不会升级为事实。

筹码、回报、参照、漏斗和组合：

```bash
python p8_chip_proxies.py --allow-provider --as-of YYYY-MM-DD \
  --env-file <local-tushare-env>

python p8_returns.py --start-date 2021-03-17 --through YYYY-MM-DD
python p8_references.py --through YYYY-MM-DD
python p8_funnel.py --as-of YYYY-MM-DD
python p8_portfolio.py --start-date 2026-09-03 --through YYYY-MM-DD
python p8_backtest.py --start-date 2025-02-26 --through YYYY-MM-DD
```

生成静态面板：

```bash
python p8_review_panel.py \
  --funnel-json <local_data>/p8_funnel_YYYY-MM-DD.json \
  --backtest-json <local_data>/p8_backtest_v1.json \
  --dry-plan-json <local_data>/p8_0_dry_plan_v1.json \
  --chip-json <local_data>/p8_chip_proxies_YYYY-MM-DD.json \
  --base-database <shared_data>/v5/backup_universe/st_stocks_v5_backup.sqlite3 \
  --output-directory <local_data>/p8_review/latest
```

最后显式发布：

```bash
python p8_publish.py --publish-current --as-of YYYY-MM-DD \
  --status-json <local_data>/p8_status_v1.json
```

`p8_publish.py` 要求八类 run 全部对齐同一日，并要求事件 frontier 与三类 current scenario map
完整覆盖当日成员。正文核证、公司自身同口径成功/失败权益输入或组合观察天数不足是
能力级降级，不会被隐藏；某条流水线缺失或日期错位则拒绝移动 manifest。

## 日常人类动作

没有必审动作。双击 `p8_review/latest/index.html` 即可看当天候选；只有想继续深挖时才点
`keep`。`drop` 只跳过本轮，`unknown` 保留观察，不点击不会被解释成任何决定。导出 JSON
只写入 owner 主动点击的卡，不改源事实或阈值。
