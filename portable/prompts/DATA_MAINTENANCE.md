# Data-maintenance task prompt

使用 `$st-research-data-maintainer`。工作区是 `/Volumes/Leibniz/STResearch`，先运行：

```bash
cd /Volumes/Leibniz/STResearch/v8_copilot
./portable/st-portable doctor
```

只负责更新我声明范围内的 Tushare qfq 价格、CNINFO 公告、ST universe、ST 等权、
中证2000、中证全指、point-in-time 市值和到期经验回归，不回答研究问题。

我每次会给价格目标交易日和公告核查日。先按 `OPERATING_MODEL.md` 固化 universe 并 dry plan；
全量刷新用 current snapshot 和稳定批次，不再默认只跑三只。所有写命令通过：

```bash
./portable/st-portable data <data_maintenance.py 的子命令与参数>
```

wrapper 会加载 SSD secrets 并取得单写锁。失败必须保留 checkpoint；不得换数据供应商或把
partial 说成 ready。结束后运行 governance verify，报告 manifest id、各来源日期、覆盖数、
失败和 gaps。不要在 API/研究任务仍运行时刷新；不要把数据库复制回出差机内置盘。
