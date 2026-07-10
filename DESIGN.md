# v8_copilot DESIGN.md — ST Research Copilot 界面设计原则

日期：2026-07-10
状态：P1.5 spike 设计依据（配合 D-053 候选）。
定位：v8 不是普通 dashboard，核心是 **问答 + 证据链 + 时间线**。不做营销页。

## 1. 设计北极星

Vercel / Geist / shadcn 那种：**克制、清晰、高信息密度**。黑白灰为主，少量状态色，
强表格与 timeline，留白充足，字体层级强。产品气质 = 一个诚实的研究工作台，不是投顾 App。

## 2. 独有原则：诚实分层可见（Honesty made visible）

这是 v8 区别于普通 dashboard 的核心视觉主张，落 D-008「证据 100% 可见」：

- **证据等级一眼可辨**：evidence-backed 的答案、case-note、lens_gap 的答案*长得就不一样*。
  用徽章区分 `evidence / weak / anecdotal / query / lens_gap / data_debt`。
- **lens invocation 是明面元数据**，不藏在点击后面：每张卡显示它调用了哪些 RL-* record、各自 kind、贡献了哪节。
- **缺口不美化**：data_debt / lens_gap 用专门 callout 样式，不用顺滑 prose 糊过去。
- **新鲜度常驻**：library version、episode 版本、data as-of 作为角标常显。

## 3. 视觉 token

- 底色 `#ffffff`；正文 `#0a0a0a`；次要文字 `#6b7280`；边框 `#e5e7eb`；分隔 `#f3f4f6`。
- 强调（交互/选中）：Vercel 蓝 `#0070f3`。
- 状态色（timeline lane，克制使用）：
  重整 `#b45309` · ST/退市风险 `#dc2626` · 控制权/股东 `#7c3aed` · 监管 `#475569` · 财报/资金 `#0d9488`。
- 字体：`ui-sans-serif, -apple-system, "Geist", "Inter", "PingFang SC"`；数据/代号用 `ui-monospace, "Geist Mono"`。
- 圆角小（6px）、边框细（1px）、阴影几乎不用；层级靠留白和边框，不靠投影。

## 4. 两个核心页面（frame）

### 4.1 主面板 / Copilot（P1.5 后做）
- 顶部：股票/问题输入框，像大模型网站一样直接问。
- 中间：回答流，逐张生成 AnswerCard（三段式 + lens invocation chips + caveat）。
- 右侧：Evidence Inspector —— lens_invocations、source freshness、data_debt、原文回链。
- 侧栏/底部：自动沉淀的 QuestionCards。

### 4.2 个股面板 / Stock Dossier（P1.5 spike 先做）
- 顶部：股票状态、ST 生命周期、最新 as-of、library 版本。
- 主区：**股价图为主角**，重要公告节点打点、可点击/定位。
- 下方：多条 timeline lane（重整 / ST 风险 / 控制权·股东 / 监管 / 财报·资金）。
- 右侧：点任意节点 → 打开节点详情、provenance、相关 lens，并可一键"围绕此节点提问"。

## 5. 联动：共享 ResearchContext

```
ResearchContext = symbol + date_range + selected_event + selected_lenses + active_question
```

主面板问沐邦 → 生成 `ResearchContext(symbol=603398)`；点答案里的某节点 → 个股页定位到该节点；
个股页点节点 → 回主面板继续问。个股面板与 AnswerCard 是**同一套证据的两个视图**
（共享 object + 节点时间线 + as-of + provenance），这也是"面板不是凭空设计，而是从证据面板自然长出来"的原因。

## 6. spike 不做

不接 LLM、不做服务/登录、不做全股票、不做写操作。只验产品形态与数据联动。
