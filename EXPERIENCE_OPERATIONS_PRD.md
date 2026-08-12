# v8 经验运营闭环 PRD

状态：implemented on `codex/experience-operations-loop`

版本：`v8_experience_batch_review_v1`

日期：2026-08-12

## 1. 人话目标

Codex 负责从研究运行里提出可复用的方法；owner 已预授权满足冻结门槛的方法自动晋级。
不新增第四个工作窗口，不把旧回答当事实，也不要求 owner 日常审卡。

目标不是把每次回答都存下来，而是把多次相似研究压缩成少量方法簇，让以后同类问题先得到
方法提示，再重新查询最新证据。

## 2. 产品面

### 2.1 运行审计 `/runs`

每条运行增加四个固定反馈动作：

- `沉淀这个方法`：按运行主题生成或合并 query-plan candidate；
- `记录错误模式`：生成 anti-pattern candidate；
- `只改表达`：合并到 presentation candidate；
- `不值得沉淀`：只记录反馈，不生成 candidate。

备注可选。相同运行、类别、反馈文本和提交人重复提交时返回同一 feedback id，不重复写入。

### 2.2 自动晋级

candidate 同时满足以下条件才自动写入 accepted：

- 至少 2 个本地真实 Research Run 支持；
- 所有 validation ref 都在允许执行的白名单中且本次回归实际通过；
- 与当前 accepted 库没有 blocking conflict；
- 通用性校验通过，不固化股票代码或日期事实。

单次方法保持 candidate 等待复现；回归失败、未知 validation ref 或 blocking conflict 自动
blocked。自动接受以 `owner_preapproved_replicated_v1` 写入 transition 和 registry，不能由外部
API 冒充。

### 2.3 经验中心 `/`

首页默认展示 accepted 库。candidate 标签改为“自动待验证”，人类无需处理；原批量决策面板
保留为异常人工覆盖工具，每轮仍最多 10 个方法簇。每张卡展示：

- 人话决策问题；
- 机器建议及理由；
- 影响的来源运行数；
- 3–5 条可用代表运行；
- 方法、输出要求、反模式和覆盖边界；
- 接受、补证、不沉淀、稍后再看四个结构化动作。

选择和备注自动保存在浏览器；提交前可以查看或下载完整 JSON。决定写入独立 review-decision
层，重复导入同一份 JSON 幂等；不同决定覆盖同一张卡会被拒绝。

### 2.4 检索

accepted experience 使用冻结的中文主题词表、触发词和适用范围做可解释整数评分。v1 不引入
embedding。每个返回项携带 `topic_tags`，仍标记 `not_evidence=true`。

## 3. 首轮库存启动

`experience_backfill.py` 将当前 24 条真实 Research Run（实施期间新增 1 条）压缩为 9 个方法簇：

1. 主回答先给判断；
2. 来源缺失只收窄到已覆盖来源；
3. 事件窗口连接真实时点与逐日价格；
4. 比较题统一主体和共同截止日；
5. 同日关联公告组成一套证据包；
6. 历史结果统计保留右删失、失败和退市；
7. 纪律处分按类型、对象和时间分层；
8. 全量 ST 扫描使用点时成员与共同截止日；
9. 当前硬节点与下一节点判断分开。

脚本默认 dry run；显式 `--apply` 写 candidate 和来源运行链接，并让满足冻结门槛的簇通过同一个
owner policy 自动晋级。首轮 9 个簇已由 owner 明确全部接受。

## 4. 人类实际要做什么

人类不需要逐条审核 Research Run，不需要判断数据库字段、编写经验规则或审经验卡。

日常最多只做一件小事：

1. 某次回答明显值得复用或明显有问题时，在 `/runs` 点一个按钮；普通回答不操作。

系统等待第二次真实复现并执行回归；达到门槛自动 accepted。经验中心用于查看库存和异常，
不是待办箱。

## 5. 冻结边界

- accepted 只能来自明确 human 决定或本地 `owner_policy`；公开 API 不能提交 owner_policy；
- 自动门固定要求 2 个真实运行、白名单回归通过、无 blocking conflict 和通用性校验；
- candidate、run、feedback 和 review decision 分库存储；
- 自动策略不覆盖历史人工决定；
- accepted registry 去掉原始运行内容，只保留通用方法，并继续做回归与冲突检查；
- 经验命中只改变查询计划和表达方式，不作为事实 backing；
- 不输出买卖、持有或仓位建议。

## 6. 架构决定

现状是 repository、反馈入口、回归执行器和 registry 已分别存在。自动化只补一层独立的
owner-policy service，由 API、CLI 和历史回填共同调用：

- 不把规则塞进 repository；repository 继续只负责状态机和审计记录；
- 不让浏览器直接自动接受；否则 CLI/回填路径会绕过门槛，浏览器也会伪装 owner；
- 选择独立 policy layer；它先核实真实运行数，再检查白名单、冲突、回归和通用性，最后调用
  repository 写入一次可追溯 transition；
- 批处理内相同 regression ref 只执行一次；执行器异常按 `unverified` fail closed，不因基础设施
  异常误接受经验。

迁移不改写既有人工决定。首轮 9 条按本次 owner 明确授权保留 human provenance；只有后续满足
冻结门槛的新方法才写 `owner_preapproved_replicated_v1`。

## 7. 验收

- 24 条历史运行全部被 9 个簇覆盖，review queue 不超过 10；
- 首轮 9 个簇全部 accepted；后续两次真实复现才触发自动回归和晋级；
- 反馈重复提交不新增记录；
- 决策 JSON 可见、可下载、可幂等导入；
- 每张卡有机器建议，真实来源可得时展示代表运行；
- 中文主题检索对公告证据包、主体边界、价格路径等典型问题有稳定回归；
- Python 聚焦测试、Web 测试、lint、build 和真实浏览器流程通过。
