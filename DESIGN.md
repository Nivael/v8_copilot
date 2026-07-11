# v8_copilot DESIGN.md — ST Research Copilot 界面设计原则

日期：2026-07-12
状态：P2 可读研究工作台设计基线。
定位：v8 不是普通 dashboard，核心是 **问答 + 证据链 + 时间线**。不做营销页。

## 1. 设计北极星

Vercel / Geist / shadcn 那种：**克制、清晰、高信息密度**。黑白灰为主，少量状态色，
强表格与 timeline，留白充足，字体层级强。产品气质 = 一个诚实的研究工作台，不是投顾 App。

## 2. 独有原则：诚实分层可见（Honesty made visible）

这是 v8 区别于普通 dashboard 的核心视觉主张，落 D-008「证据 100% 可见」。
“可见”指一键可达、可完整审阅，不等于把内部 ID 和原始表格塞进主分析：

- **证据等级一眼可辨**：evidence-backed 的答案、case-note、lens_gap 的答案*长得就不一样*。
  用徽章区分 `evidence / weak / anecdotal / query / lens_gap / data_debt`。
- **主分析先讲人话**：正文只保留可连续阅读的事实、推断、不确定性和下一步核查，不显示 backing ID。
- **证据独立审阅**：Lens invocation、查询行、出处、新鲜度、data debt 和 backing 全部进入“证据与来源”模块，一次操作即可打开。
- **缺口不美化**：正文说明它如何限制分析；工程 ID 和完整台账信息留在证据模块。
- **新鲜度分层**：主答案常显回答 as-of；各 source 的 freshness 在证据模块完整展示。
- **Lens 不为填充而调用**：冻结 v1 只有 9 条记录。没有适用 Lens 时明确写 0 命中，不把通用数据查询包装成 Lens 结论。

## 3. 视觉 token

- 底色 `#ffffff`；正文 `#0a0a0a`；次要文字 `#6b7280`；边框 `#e5e7eb`；分隔 `#f3f4f6`。
- 强调（交互/选中）：Vercel 蓝 `#0070f3`。
- 状态色（timeline lane，克制使用）：
  重整 `#b45309` · ST/退市风险 `#dc2626` · 控制权/股东 `#7c3aed` · 监管 `#475569` · 财报/资金 `#0d9488`。
- 字体：`ui-sans-serif, -apple-system, "Geist", "Inter", "PingFang SC"`；数据/代号用 `ui-monospace, "Geist Mono"`。
- 圆角小（6px）、边框细（1px）、阴影几乎不用；层级靠留白和边框，不靠投影。

## 4. 两个核心页面（frame）

### 4.1 主面板 / Copilot
- 顶部：股票/问题输入框，像大模型网站一样直接问。
- 中间：人话回答，按“直接回答 / 判断依据 / 不确定性 / 接下来观察什么”组织；正文 16-17px、行高不低于 1.7。
- Narrative v2 的每一句都必须回链到已验证 query row、Lens、data debt、provenance 或 Lens gap；前端只负责排版，不拼研究逻辑。
- 右侧或移动端全屏：Evidence Inspector —— backing、查询行、lens invocation、source freshness、data debt、原文回链。
- 底部折叠区：自动沉淀的 QuestionCards，不与主答案争夺第一屏。

### 4.2 个股面板 / Stock Dossier
- 顶部：股票状态、ST 生命周期、最新 as-of、library 版本。
- 主区：**股价图为主角**，支持滚轮/触控缩放、拖动平移和 3月/6月/1年/3年/全部区间预设。
- 正式公告全集与 M6 已分类节点同时存在，计数和标签必须分开；“未被 M6 分类”不得显示成“没有公告”。
- 未分类公告可以按标题辅助分组以控制图表密度，但必须标注“尚未纳入 M6”，不得因此触发 Lens 或升级证据等级。
- 公告节点按当前可见时间窗同步，默认只显示重点节点；可按重整、ST 风险、控制权、监管、财报筛选。
- 缩远时限制图上 marker 数量，完整节点保留在当前窗口事件列表，避免公告盖住价格走势。
- 右侧：点任意节点 → 打开节点详情、provenance、相关 lens，并可一键"围绕此节点提问"。

## 5. 联动：共享 ResearchContext

```
ResearchContext = symbol + date_range + selected_event + selected_lenses + active_question
```

主面板问沐邦 → 生成 `ResearchContext(symbol=603398)`；点答案里的某节点 → 个股页定位到该节点；
个股页点节点 → 回主面板继续问。个股面板与 AnswerCard 是**同一套证据的两个视图**
（共享 object + 节点时间线 + as-of + provenance），这也是"面板不是凭空设计，而是从证据面板自然长出来"的原因。

## 6. 交互参考与实现边界

- 图表交互采用 TradingView Lightweight Charts，使用其可见时间范围、缩放/平移和 series marker API。
- 只读研究库边界不变；图表筛选和问答展示不写研究数据库。
- 事件“重点”和标题辅助分组只影响默认展示密度，不改变 episode 分类、不生成研究结论；用户可以关闭筛选查看当前窗全部正式公告。
- 个股页常显价格、正式公告、M6 索引各自的 freshness；不能用单一 `as_of` 掩盖来源不同步。
