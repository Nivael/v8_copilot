# P6B market-cap backfill v1

`plan.json` 是 P6B-1a 的不可变锚点计划，来源：

- dry plan `P6B0-BE1B382B7CF794EBAECA`；
- provider probe `P6BP-574C9D1EEA97E0DF953B`；
- 中证全指交易日历。

每个原始 episode start 映射到同日或下一个中证全指交易日。plan 内容寻址、日期严格升序
且不重复。运行器只向 `market_factors_v1` 追加 snapshot 和 dated manifest；中断后按已有
snapshot 恢复，完成前不移动 current pointer，历史运行不得使 current 倒退。

生成：

```bash
python p6b_market_cap_backfill.py plan \
  --dry-plan-json <p6b0-dry-plan.json> \
  --market-context-database <market-context.sqlite3>
```

执行：

```bash
python p6b_market_cap_backfill.py run \
  --env-file <local-tushare-env> \
  --output <local-run-report.json>
```
