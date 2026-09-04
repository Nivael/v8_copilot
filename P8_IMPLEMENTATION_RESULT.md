# P8 首轮实施与真实运行结果

日期：2026-09-04
数据截止：2026-09-03
PRD：[V8_P8_RESEARCH_FUNNEL_PRD.md](V8_P8_RESEARCH_FUNNEL_PRD.md)
dry-plan：`P8DP-074B0131FFD695C379F8`
current manifest：`P8M-5B8B3E105A7F306C81C2`

## 1. 结论

P8 的工程闭环已能真实运行：独立追加式派生库、五轨前哨图、持续型量价、公开筹码旁证、
阶段回报、三类互不混合的情景参考、四通道研究漏斗、真实日历组合账、五张回测成绩单和
离线校验面板均已物化。P6/P7 输入保持只读。

当前不是“发现了交易信号”，而是形成了一套不会把弱证据包装成结论的研究漏斗。两个关键
能力按契约保持不可用：正文尚未获准发送到外部 LLM，因此 `body_verified=0`；P6B-2 没有任何
精确旧股东权益账，因此情景分布和 `p*` 都不计算。

## 2. 当前运行账

| 模块 | run / 结果 | 当前事实 |
| --- | --- | --- |
| 事件图 | `P8R-28BDDCD5F32FC76F2E8C` | 1,773 个候选事件；400 deterministic verified、486 provisional、887 title-derived；正文 LLM 完成 0 |
| 累积活动 | `P8R-9D1E137ED30C337C13AE` | 68,738 条观察，40,080 条完整可算；冻结 `broad` profile；27,272 条带 point-in-time 市值 |
| 单日偏离箱 | 同上 | D0 9,092、D1-only 188、D2-only 77、D3-only 36、D4 37；其余因 P7 历史基线/覆盖不足为 unknown |
| 回报路径 | `P8R-9259392CBF295659CA16` | 2,233 条；20 日完成 2,003；489 条入场可交易性核实，1,648 条只有价格可观察，96 条无端点 |
| 情景参考 | `P8R-8DB495A1B90A18B4FC8E` | 战略投资 126、失败退出 164、公开节点 511；35 个 point-in-time 总市值事实，旧股东 exact 0 |
| 筹码旁证 | `P8R-559F5406224D81FF5E85` | 203 个当前成员；200 个有近一年股东户数披露；龙虎榜/机构席位/大宗各命中 1；融资融券命中 0 |
| 每日漏斗 | `P8R-D86AC9EF1186FE387353` | 10 个候选，6 个事件前沿、4 个筹码/探索；96 个未入选的唯一股票；必审 0 |
| 日历组合 | `P8R-C1C79D5061BBCFE1A6F9` | 仅 1 个真实 shadow 日；10 个候选都尚无下一交易日，状态 unavailable/right-censored |
| 回测 | `P8R-A2C09F4AE6F4ACB0575E` | 300 个去重活动 episode；按方向、年份、年报季和右删失分账 |

筹码第一次真实运行因供应商要求 gzip 多线程头而有 60 个失败；客户端补齐
`Accept-Encoding: gzip` 后只重试失败项，最终 207 个请求中 147 个命中缓存、60 个真实重试、
0 失败。更早一次传错 secrets 文件的失败 run 也按 append-only 保留，不覆盖成功记录。

## 3. 回测怎么解读

三个 point-in-time 回放锚点分别是：

- 一周前 2026-08-27：2 个候选；
- 一个月前 2026-08-05：1 个候选；
- 一年前 2025-08-20：1 个候选。

完整历史合并连续命中后得到 300 个活动 episode。按 P6/body-verified 阶段优先、同日同板块、
有 point-in-time 市值时近市值的 quiet 对照可匹配 227 个（75.7%）；活动组相对 ST 等权的
均值差为 -1.42 个百分点。公司聚类 95% 区间为 [-4.08%, 1.46%]，日历月 block 区间为
[-3.40%, 1.05%]，两者都跨 0。P7 title-derived 阶段只另作 sensitivity，也不改变结论。因此首轮结果是
`descriptive_only`：没有证据支持“持续放量稳定领先消息”或“可据此择时”。

这不是阈值失败后再调参。`broad` profile 在读取任何未来节点和收益前，仅按日均候选容量和
公司覆盖冻结；回测不会反向改写它。真正发布仍需至少 60 个真实交易日 shadow。

## 4. 人类需要做什么

日常必要人审为 0。系统自动保留 unknown/provisional、冲突 cluster、overflow 和未点击候选。
owner 只在愿意时对最多 20 个候选点 `keep / drop / unknown`；不点击仍是 `unreviewed`。

目前唯一需要 owner 明确授权的不是内容判断，而是数据出境边界：是否允许把本地缓存的公开
上市公司公告正文发送给 OpenAI API 做结构化抽取。没有授权时，734 份已有正文不会外发，
`llm_route` 也不会冒充已经运行。授权后仍只有规则与 LLM 节点一致且原文引用可定位的记录能
升级为 `body_verified`。

## 5. 本地交付物

- 校验面板：`local_data/v8_copilot/p8_review/latest/index.html`
- 面板队列：`local_data/v8_copilot/p8_review/latest/review_queue.json`
- 面板截图：`local_data/v8_copilot/p8_review/latest/p8-review-panel.png`
- 当前状态：`local_data/v8_copilot/p8_status_v1.json`
- current manifest：`local_data/v8_copilot/p8_research_manifest_v1.json`

这些是本机生成物，不提交 Git。面板已用真实浏览器验证 10 张卡、按钮状态、localStorage、
JSON 预览和导出结构；不需要启动服务或联网。
