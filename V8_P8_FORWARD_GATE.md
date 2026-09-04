# P8 真实前瞻门

状态：**reset for post-BT2 funnel v2**
契约版本：`v8_p8_forward_gate_v1`
起始交易日：2026-09-07（首个实际发布日若更晚，以实际日为准）

## 为什么不能回填

P8 漏斗会消费当日可得的公告、阶段、情景参考、量价和筹码旁证。用今天的完整库存倒造过去
的“每日候选”会把后来补齐的正文、阶段和名单带回历史，违反 point-in-time。因此历史
episode 只进入预注册回测；真实漏斗、owner 使用和并发组合只从上线日起逐日累积。

## 两道互不替代的门

1. **10 个真实交易日运营门**：每天成功发布同日 manifest，候选数在 0–20，overflow 可见，
   无候选时不补数。达到 10 日只证明漏斗可以稳定工作，不证明信号有效。
2. **60 个真实交易日验证观察门**：达到 60 日才允许首次评价真实漏斗的研究转化和同期组合；
   仍须保留右删失、失败样本和置信区间，不自动升级为交易信号。

`p8_status_v1.json` 自动输出 `forward_shadow_days`、`operational_10_day_gate` 和
`validation_60_day_gate`。计数来自 append-only portfolio 所引用的不同 funnel run，不使用
日历天或重复复跑充数。

## 当前状态

- 已观察真实交易日：0；旧 `p8_research_funnel_v1` 的 2026-09-03 单日保留审计，但不与 v2 混算；
- 10 日运营门：`accumulating`；
- 60 日验证观察门：`accumulating`；
- owner 必审：0。

P8-BT2 已把 `persistent_activity` 主 lane 判定为 killed。后续真实门只累计
`p8_research_funnel_v2`：持续量价仍保留为诊断/overflow，但晋级配额为 0；股东户数只作
不加权弱旁证。改变这个安排必须开新的预注册版本，不能沿用本门。

每个新交易日先完成 P7，再运行 `p8_daily.py`。任一步失败或来源日期不一致，current manifest
不移动，该日不计入前瞻分母。
