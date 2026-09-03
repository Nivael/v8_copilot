# P7 日常运行手册

P7 使用现有 v8 数据维护边界；联网写入只在 data-maintenance task 中执行。所有命令都从仓库
根目录运行。移动硬盘环境中，`data_maintenance.py` 子命令通过
`./portable/st-portable data <子命令>` 运行，状态与审阅脚本继续使用 portable runtime。

## 每个交易日收盘后的顺序

1. 同步当天 ST 名单、三基准和 point-in-time membership；
2. 刷新当前 ST universe 的 qfq 价格与 CNINFO 公告；新入池且没有基线的股票逐股传明确起点；
3. 按交易日写入 `market_activity_v1` 的 `daily`、`daily_basic`、`suspend_d`、`stk_limit`；
4. 更新内部 ST 等权指数；
5. 先生成历史回放快照，再生成从 2026-09-04 起的 prospective shadow ledger；
6. 检查 P7 status 和每日页。任何一步失败都保留 checkpoint，不把失败源冒充 checked-through。

核心命令：

```bash
uv run python data_maintenance.py bootstrap-market-activity \
  --start-date YYYY-MM-DD --through YYYY-MM-DD --env-file /path/to/tushare.env

uv run python data_maintenance.py materialize-p7 \
  --start-date 2026-02-13 --announcement-start-date 2021-03-17 \
  --through YYYY-MM-DD --shadow-mode historical_replay

uv run python data_maintenance.py materialize-p7 \
  --start-date 2026-02-13 --announcement-start-date 2021-03-17 \
  --through YYYY-MM-DD --shadow-mode prospective --shadow-start-date 2026-09-04

uv run python p7_status.py --provider-probe /path/to/provider-probe.json \
  --output /path/to/p7-status.json
```

浏览器页面为 `/daily`。它固定按覆盖、硬节点、重点公告、异常交易活跃、联动研究队列的顺序
展示；`shadow` 不是买入信号。

## 发布校验

日常运行不需要逐股或逐公告人工审核。只有发布状态变化时构建两张压缩决策卡：

```bash
uv run python p7_review.py build --metrics /path/to/p7-status.json \
  --output-directory /path/to/p7-review
```

owner 在静态 `index.html` 中选择后下载 JSON；导入命令可重复执行，重复决定不会二次写入：

```bash
uv run python p7_review.py import --queue /path/to/review_queue.json \
  --decisions /path/to/downloaded-decisions.json
```

## 周/月/年回测复算

回测使用独立 materialization 数据库，不能覆盖日常 prospective ledger。先按
`V8_P7_BACKTEST_CONTRACT.md` 补齐冻结的最小基线，再运行：

```bash
uv run python data_maintenance.py materialize-p7 \
  --start-date 2025-02-26 --announcement-start-date 2021-03-17 \
  --through 2026-09-03 --shadow-mode historical_replay \
  --output-database /path/to/p7_backtest_materialization.sqlite3 \
  --manifest /path/to/p7_backtest_manifest.json \
  --manifest-directory /path/to/p7_backtest_manifests

uv run python p7_backtest.py --through 2026-09-03 \
  --intelligence-database /path/to/p7_backtest_materialization.sqlite3 \
  --output-directory /path/to/p7_backtest_report
```

输出包含 `report.json` 和可直接双击的 `index.html`。周/月锚点的未完成窗口必须保留为
右删失；不得用历史结果解除 P7D 的真实前瞻发布门。首轮结果和解释边界见
`P7_BACKTEST_RESULT.md`。
