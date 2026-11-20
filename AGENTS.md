# AGENTS.md

This repo had no AGENTS.md/CLAUDE.md despite being the active version as of
2026-07-20 — added as part of ST_invest_quant `.todos/018.md` (cross-repo
documentation cleanup). Keep this short; it's an index, not a duplicate of
the docs it points to.

## What this is

ST Research Codex Workbench — a read-only evidence research core plus a
Codex-hosted local research workbench. Full product definition lives in
`README.md` (spine: QuestionCard → LensInvocation → AnswerCard →
QuestionCard/DataDebt) and `OPERATING_MODEL.md` (the daily three-window
routine: data maintenance / research Q&A / browser audit). Visual/product
design principles are in `DESIGN.md`.

**Read `README.md` first, always.** It is the canonical current-state doc and
is kept up to date; this file is only a pointer.

## Repo state

- `origin` is `github.com/Nivael/v8_copilot`; important changes should be
  pushed through scoped feature branches and draft PRs. The current PR stack
  and accepted data snapshots are summarized in the workspace-root
  `AGENTS.md`, `README.md`, and the relevant result note.
- Uses the same worktree pattern as `ST_invest_quant`: feature work happens
  under `wt/<name>` (see `git worktree list`), not on local `master` directly.
- Retained worktrees are traceability artifacts; do not delete them without
  owner confirmation.

## Documentation hygiene

- `README.md`, `OPERATING_MODEL.md`, `DESIGN.md`, `SELECTIVE_EVIDENCE_ARCHITECTURE_2026_07_15.md`,
  `V8_NEXT_PRD.md`, and `V8_NEXT_TODO.md`
  are the living reference docs — check for cross-references (`grep -rl
  <filename>`) before assuming any of them is safe to touch or archive.
- Point-in-time handoff/closeout/PRD-recovery notes (named with a date, e.g.
  `*_HANDOFF_YYYY_MM_DD.md`) are working notes, not living docs. Once their
  content is folded into `README.md`/`OPERATING_MODEL.md` and nothing else
  references them, archive them to `_archive/cleanup_YYYYMMDD/` at the
  `st_research/` workspace root with a manifest (see that directory for the
  convention) — do not `rm`. Six such docs were archived on 2026-07-20; see
  `_archive/cleanup_20260720/v8_copilot_dated_docs/MANIFEST.md`.

## Contracts

`contracts/` holds frozen, versioned JSON contracts (`v8_answer_contract_v0`,
`v8_copilot_api_contract_v0`/`v1`, `v8_question_card_contract_v0`,
`v8_query_template_contract_v0`). Treat these like the "contract" concept in
`ST_invest_quant/AGENTS.md` — do not edit without the change being an
explicit, versioned, reversible decision; a new contract version, not an
in-place edit, is the default way to change one.

最新期间复盘已发布：海钦旧处罚/新监管与现金、洲际补认/独立审计、中路798万元未收与司法、京化重述/非经常性损益分别核。6条问题链、四家同窗横向比较；期初仍126/150。见 [本轮结果](ST_TWENTYFIRST_PERIOD_FOLLOWUP_RESULT_2026_11_20.md)。

最新期初补证已发布：福成双审计、文峰部分回收和年份冲突、际华告知依据及审计分类、喜临门担保转占款与股东预重整分别核。覆盖130/150、剩20家。见 [本轮结果](ST_INITIAL_TWENTYSECOND_FOUR_RESULT_2026_11_20.md)。

最新期间复盘已发布：福成程序通过与鉴证、文峰新增本金/旧诉讼/新立案、际华最终处罚/非经常性收益及三项衔接差异、喜临门担保转占款分别核。期初仍130/150，见 [本轮结果](ST_TWENTYSECOND_PERIOD_FOLLOWUP_RESULT_2026_11_20.md)。

最新期初补证已发布：联翔双无保留与财务门槛、东珠更正与鉴证延期、东时旧审计消除与部分申请、亚士负净资产与受限资金分别核。覆盖134/150、剩16家。见 [本轮结果](ST_INITIAL_TWENTYTHIRD_FOUR_RESULT_2026_11_20.md)。

最新期间复盘已发布：联翔收入与现金、东珠鉴证与交易类门槛、东时预重整与现金重分类、亚士并表与权益口径分别核。期初仍134/150，见 [本轮结果](ST_TWENTYTHIRD_PERIOD_FOLLOWUP_RESULT_2026_11_20.md)。

最新期初补证已发布：集友财务与意向、绝味重述用途与处罚、起步审计分列、东尼分笔实收分别核。覆盖138/150、剩12家，绝味报价冲突提示保留。见 [本轮结果](ST_INITIAL_TWENTYFOURTH_FOUR_RESULT_2026_11_20.md)。

最新期间复盘已发布：集友交割与80%付款、绝味摘帽与交易终止、起步专项债权与终审计提、东尼申请与重估分别核。初始仍138/150；绝味9个窗口报价差异保留。见 [本轮结果](ST_TWENTYFOURTH_PERIOD_FOLLOWUP_RESULT_2026_11_20.md)。

最新初始补证：海利、龙韵、星农、华扬，覆盖142/150、剩8家。起源仅12页360行、两份官方PDF无目录行及星农日期冲突均保留。见 [结果](ST_INITIAL_TWENTYFIFTH_FOUR_RESULT_2026_11_20.md)。

最新期间复盘：海利、龙韵、星农、华扬，6条问题链及现金分项表。星农现金毛额倒差保留，华扬负权益不直接认证年度触发。期初仍142/150。见 [结果](ST_TWENTYFIFTH_PERIOD_FOLLOWUP_RESULT_2026_11_20.md)。

第26批期初补证已发布：利达资金回收与审计取证、四通申请与后续批准、正平持续经营/募资强调、智知内控与处罚分别核。覆盖146/150、剩4家，智知两段收益因报价冲突留空。见 [结果](ST_INITIAL_TWENTYSIXTH_FOUR_RESULT_2026_11_20.md)。

第26批期间复盘已发布：利达处罚/控制权、四通摘帽/更正、正平募资/现金范围、智知基金/经营分列。6问题链、16财务、84窗口，3报价冲突留空1缺价；期初146/150。见 [结果](ST_TWENTYSIXTH_PERIOD_FOLLOWUP_RESULT_2026_11_20.md)。

第27批期初补证已发布：金鸿顺、百利、葫芦娃、帅电，固定成员150/150均有期初事实；不代表完整研究。26份769页核23页，标题正文冲突保留，12端点8收益一致。见 [结果](ST_INITIAL_TWENTYSEVENTH_FOUR_RESULT_2026_11_20.md)。

第27批期间复盘已发布：金鸿顺一审/转回、百利部分赠与实收与更正、葫芦娃正式处罚/现金亏损、帅电过户/52%付款分别核。6问题链、四家事前事后同窗；69窗口60满9未满，15财务保留0.01元差异与缺项。期初150/150不等研究完成。见 [本轮结果](ST_TWENTYSEVENTH_PERIOD_FOLLOWUP_RESULT_2026_11_20.md)。

固定150全量核价已发布：完整段146主源配对中141跨渠道一致、5起点报价待核、4缺端点；近期147配对全部一致、3缺端点。总览改列核价通过子样本，并直达全量/退出说明；136期末名单内与14名单外仅作事后分组。旧主题输入不变，见 [结果](ST_ENDPOINT_SELECTION_AUDIT_RESULT_2026_11_20.md)。

五家复权构造解释已发布：八菱、章鼓、人福、绝味、智知424历史成交日复算，两种起点/收益并列。141直接一致统计不变；绝味实派/虚拟/参考现金分列，新原价501及0新响应明确。见 [结果](ST_ENDPOINT_BASIS_FOLLOWUP_RESULT_2026_11_20.md)。

岭南退出续核已发布：后续条件式重述不认证最终决定/摘牌，20成交日触发复算；5项财报更正勾稽、合并/归母口径及旧占款截止日分列。5份61页核8页，含1旧报告重看，旧主题输入不变。见 [结果](ST_LINGNAN_EXIT_FOLLOWUP_RESULT_2026_11_20.md)。

财报更正横向比较已发布：四通比较基数、百利当期亏损与权益、岭南历史报表与退出程序分列；三家公司同日不是独立时段检验，停牌空值和17/20未满保留。旧主题输入不变，见 [结果](ST_RESTATEMENT_COMPARISON_RESULT_2026_11_20.md)。

百利政策续核已发布：政策原文与原半年报已提政策分别核，7月发布早于8月半年报；更正公告时间表述差异保留，消费税/所得税估计/实际现金分开。4份官方网页、原报2图像页，旧主题输入不变，见 [结果](ST_BAILI_POLICY_FOLLOWUP_RESULT_2026_11_20.md)。

际华季度衔接续核已发布：归母金额对应同控合并前利润仅作线索，收入/归母/扣非三差额与非经常性100元残差保留，算术隐含半年不当披露数；2原件6图像页，旧输入主题不变，见 [结果](ST_JIHUA_BRIDGE_FOLLOWUP_RESULT_2026_11_20.md)。

ST五段横向经验检验已发布：7至9月相对强不等多数赚钱，10月起相对转弱；150家保留、139共同交集事后筛选，五段不当独立实验。900唯一逐股端点位置，旧输入主题不变，见 [结果](ST_MARKET_STAGE_EXPERIENCE_RESULT_2026_11_20.md)。

14家期末名单外结果已发布：12撤销、1主动终止、1整理后摘牌分列；固定窗非各自摘帽后收益，缺价/报价差异和账户结果保留。复用已有证据，旧主题输入不变，见 [结果](ST_EXIT_OUTCOMES_RESULT_2026_11_20.md)。

宁科比较栏续核已发布：年度审计扫描表与半年合并表/三季比较栏一致，主要指标页另一组数仍未解释；不从负比较基数讲新增权益。3原件6图像页，人工扫描读数身份与旧输入主题保留，见 [结果](ST_NINGKE_COMPARATIVE_FOLLOWUP_RESULT_2026_11_20.md)。

京机公式精度续核已发布：新增债券公告重复原式，原分母冲突未消除；两输入取整均14.47不识别唯一口径，实际换股未认证。1新1旧原件核3页，旧主题输入不变，见 [结果](ST_JINGJI_DIVIDEND_FOLLOWUP_RESULT_2026_11_20.md)。

研究材料覆盖清单已正式发布：冻结旧输入2023引用去重1296文件，1139含文本、157仅引用；支持检索/翻页及缺口跳转，非空页不当已读，旧主题和方法保持。见 [结果](ST_EVIDENCE_INVENTORY_RESULT_2026_11_20.md)。

材料清单来源提示已修复：8份新浪镜像明确保留官方原字节待补限制，新增可展开文件身份；研究快照不变，见 [结果](ST_SOURCE_PROVENANCE_RESULT_2026_11_20.md)。

反弹与回本连续路径已发布：同一139家事后核价交集，103家八月反弹不等51家回本，固定起点累计路径及逐股明细可展开；旧快照保持，见 [结果](ST_RECOVERY_PATH_RESULT_2026_11_20.md)。

连续路径样本敏感性已发布：139共同样本与各截止日起终点核价子样本并列，八九月底采用“接近起点”而不泛称回本；缺价不归零，见 [结果](ST_RECOVERY_SENSITIVITY_RESULT_2026_11_20.md)。

累计大盘对照已发布：同一7月3日起点，动态ST、固定139家中位数与大盘分列；相对少跌与绝对下跌可并存，跑赢不当上涨。见 [结果](ST_CUMULATIVE_MARKET_CONTEXT_RESULT_2026_11_20.md)。

横向阶段复盘已改为三个按问题入口：分段走势、反弹回本、大盘累计，每次显示一个；原研究不变，见 [结果](ST_STAGE_READING_RESULT_2026_11_20.md)。

摘帽20日后窗续核已发布：旧12次制度后事件均成熟，11家核价通过；四通新增，绝味起点差异留空。旧观察与材料核账基准保留，见 [结果](ST_REMOVAL_MATURE_WINDOW_RESULT_2026_11_20.md)。

摘帽20/40日同组比较已发布：同10家中位数1.14%与0.61%，5家短窗为正中3家回吐2家扩大；绝味四通各22日未满，见 [结果](ST_REMOVAL_PAIRED_40_RESULT_2026_11_20.md)。

同日摘帽公告/窗口题已发布：四通20日+6.23%与最新−6.89%分列；绝味后披露消息不倒填，起点冲突保留，见 [结果](ST_REMOVAL_ANNOUNCEMENT_CLOCKS_RESULT_2026_11_20.md)。

## Historical study identity registration

When reusing a saved evidence bank for a new historical study, call `bind_study_identity(pack, question=..., object_refs=[...], as_of=...)` and `validate_bound_identity(pack)` before rebuilding the draft, validation and recording. Changing only request_id is not rebinding. Retain individual asset dates; do not inherit the prior question, cutoff, retrieval hits or Lens calls as new execution. Retrieval is not usage or demonstrated benefit.

Old worktrees and runs remain traceability artifacts. Correct old identity through bound, append-only identity notes, never SQL rewrites. Question-history import must quarantine bound identity corrections; the current importer does so and publication rechecks prepared records, including merged sources and occurrences. Preserve these gates when updating the pipeline. Preserve owner policy, thresholds, method bodies, statuses and accepted registry. See [identity audit](ST_RESEARCH_IDENTITY_AUDIT_RESULT_2026_11_20.md).

第二组身份核对：16条旧研究分别绑定原快照截止11月6日，累计31条更正；原268条及方法登记保持，京蓝原版/更正版分开。见 [结果](ST_RESEARCH_IDENTITY_FOLLOWUP_RESULT_2026_11_20.md)。

历史导入已接身份隔离：使用`import_ledger_with_audit`留存隔离说明；默认缺登记停止，损坏停止，发布再次核对，旧worktree不作新导入执行器。原历史阅读内容保持，见 [结果](ST_HISTORY_IDENTITY_IMPORT_RESULT_2026_11_20.md)。

市场研究身份续核：三条11月5日研究不再沿用000996/2024年截止，累计34条更正；原402条用户问题完整，保存研究阅读131→130。见 [结果与限制](ST_MARKET_STUDY_IDENTITY_RESULT_2026_11_20.md)。

旧市场窗口续核：−10.61%/−12.80%对应9月4日收盘起点；7日是首个收益日。换成7日收盘起算为−11.56%/−13.46%，原方向不翻转。面板已增折叠对照，见 [结果](ST_MARKET_WINDOW_ANCHOR_RESULT_2026_11_20.md)。

主阅读顺序更新：先行情与判断，登记/窗口核对集中到后部“资料与更正”，顶部可直达，原窗口直链保留自动展开。见 [结果](ST_READING_SOURCE_ORDER_RESULT_2026_11_20.md)。

岭南债券补核：11月3日报告时一审未生效，质押登记/前置安排/变现/兑付分列；两份旧件29页核7关键图像页，0下载。新增问题入口，原退出缺口不变，见 [结果](ST_LINGNAN_BOND_FOLLOWUP_RESULT_2026_11_20.md)。

岭南2026-124正文及判项金额已补核：本息376991941元另计占用息，本息及两费小计与标题金额勾稽，生效/实付仍待原件；研究账本268→269且原行保持，见 [结果](ST_LINGNAN_JUDGMENT_TERMS_RESULT_2026_11_20.md)。

现金流向横向比较已发布：京蓝两笔、神雾股份抵债、岭南债券判项分列；三家公司四事项逐项核流向、阶段和日期，原件按需展开，不新增方法验证次数。见 [结果](ST_CASH_DIRECTION_COMPARISON_RESULT_2026_11_20.md)。

兑现与行情对照已接入：京蓝实收后首日涨/20日跌、神雾过户后绝对跌/相对少跌并列；1/5日切换、停牌空值、期间新消息及同窗大盘分列。见 [结果](ST_CASH_MARKET_COMPARISON_RESULT_2026_11_20.md)。

到账性质比较已接入：京蓝补偿、海泰项目销售、百利资本赠与分列；不把全部卖房排为非经营，也不把算术差额当逾期欠款。阶段/性质/行情三问切换，见 [结果](ST_CASH_RECEIPT_MEANING_RESULT_2026_11_20.md)。
