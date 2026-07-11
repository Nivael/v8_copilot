const labels:Record<string,string>={
  aggregate_weak:'汇总弱证据',
  small_n_case_notes:'小样本案例证据',
  anecdotal_support:'个案支持',
  descriptive_query:'描述性查询',
  insufficient_data:'数据不足',
  context_only:'仅上下文说明',
  evidence:'证据',
  query:'查询',
  checklist:'观察清单',
  methodology:'方法论',
  data_debt:'数据债',
  lens_gap:'Lens 缺口',
  evidence_lens:'证据 Lens',
  case_note_evidence:'案例证据',
  methodology_frame:'方法论框架',
  answer_query:'查询型回答',
  answer_evidence:'证据型回答',
  answer_checklist:'观察清单回答',
  answer_methodology:'方法论回答',
  refuse_or_rewrite:'合规改写',
  clarify:'需要澄清',
  boundary:'边界处理',
  answerable:'当前可答',
  needs_data:'需要补数据',
  needs_review:'需要人审',
  stock:'股票',
  stock_event:'股票事件',
  unknown:'未知对象',
  date:'日期',
  announcement:'公告',
  episode:'事件路径',
  lens:'Lens',
  provenance:'出处',
  fact:'事实',
  inference:'推断',
  caveat:'边界说明',
  question:'待核问题',
  data_gap:'数据缺口',
  query_row:'查询结果',
  lens_invocation:'Lens 调用',
  provenance_ref:'出处',
  effect_digest:'历史效应摘要',
  answer_card:'回答卡',
  user_question:'用户问题',
  system_gap:'系统缺口',
  not_applicable:'不适用',
  lens_gap_required:'必须记录 Lens 缺口',
  evidence_or_lens_gap_required:'需要证据或 Lens 缺口',
  lens_invocation_required:'需要 Lens 调用',
  restructured_context:'重整上下文',
  restructuring_path:'重整路径',
  st_entry_or_escalation_path:'ST 风险进入或升级',
  delisting_terminal_path:'终止上市风险',
  risk_warning_removal_path:'风险警示撤销路径',
  control_or_investor_path:'控制权或投资人变化',
  regulatory_pressure_path:'监管压力',
  financial_reporting_path:'财报与审计',
  fund_occupation_resolution_path:'资金占用处置',
  other_event_path:'其他事件',
  annual_report_release:'年报或定期报告披露',
  annual_report_st_continues:'年报后风险警示延续',
  annual_report_st_start_problem:'年报触发风险警示问题',
  audit_opinion_issue_resolved:'审计意见相关问题消除',
  audit_opinion_nonstandard:'非标审计意见或内控问题',
  audit_progress:'年报编制或审计进展',
  controlling_shareholder_pledge_or_execution:'控股股东质押、冻结或执行',
  control_or_investor:'控制权或投资人变化',
  delisting_possible_termination:'可能终止上市风险提示',
  earnings_forecast_or_preannouncement:'业绩预告或业绩预披露',
  fund_occupation_rectification:'资金占用整改',
  fund_occupation_repayment_or_clearing:'资金占用清偿',
  fund_occupation_special_report:'资金占用专项报告',
  investor_or_control_change:'投资人或控制权变化',
  regulatory_discipline_or_measure:'监管措施或纪律处分',
  regulatory_inquiry_delay:'监管问询延期回复',
  regulatory_inquiry_letter:'监管问询函',
  regulatory_inquiry_reply:'监管问询回复',
  regulatory_investigation_opened:'监管立案或调查启动',
  regulatory_letter:'监管工作函',
  regulatory_penalty_decision:'行政处罚告知或决定',
  restructuring_pre_restructuring_started:'预重整启动',
  restructuring_progress_update:'重整或预重整进展',
  risk_warning_removal_application:'申请撤销风险警示',
  delisting_risk_warning:'退市风险警示',
  announcement_unclassified:'其他公开公告',
  st_status_fetched_at:'ST 生命周期抓取时间',
  st_evidence_generated_at:'ST 触发公告证据生成日',
  st_status_history:'ST 生命周期记录',
  case_note_only:'个案记录边界',
  unclassified:'未纳入事件段分类',
  price_data_as_of:'价格数据截至',
  company_announcements_as_of:'公告数据截至',
  shareholder_count_as_of:'股东人数数据截至',
  equity_timeline_as_of:'股权时间线截至',
  shareholder_count:'股东人数',
  capital_structure:'股本结构',
  episode_index_as_of:'事件段索引截至',
  release_library_frozen_at:'Lens 库冻结时间',
  data_debt_registry_as_of:'数据债台账截至',
  release_id:'Lens 编号',
  lens_kind:'Lens 类型',
  release_role:'库内角色',
  contributed_section:'贡献位置',
  evidence_grade:'证据等级',
  cohort_id:'样本组',
  sample_n:'样本数',
  trigger:'触发样本',
  control:'对照样本',
  positive:'正向',
  negative:'负向',
  neutral:'中性',
  unstable:'不稳定',
  anchor:'锚点',
  'multiple-testing':'多重检验',
  episode_index:'事件段索引',
  allowed_wording:'允许措辞',
  forbidden_wording:'禁止措辞',
  missing_for:'缺口对象',
  gap_id:'缺口编号',
  debt_ref:'数据债编号',
  source_ref:'来源编号',
  source_kind:'来源类型',
  selected_episode:'选中事件路径',
  selected_lenses:'选中 Lens',
  object_scope:'对象范围',
  object_kind:'对象类型',
  date_start:'开始日期',
  date_end:'结束日期',
  event_id:'事件编号',
  event_title:'事件标题',
  episode_ref:'事件路径',
  lens_id:'Lens 编号',
  data_debt_ref:'数据债编号',
  provenance_refs:'出处',
  related_lens_ids:'相关 Lens',
  status_name:'状态',
  status_type:'状态类型',
  source:'来源',
  view:'视图',
  route:'路径',
  status:'状态',
  reason:'原因',
  matched_rules:'命中规则',
  required_lens_behavior:'Lens 约束',
  question_card_refs:'问题卡',
  data_debt_refs:'数据债',
  next_any_announcement:'下一个任意公告',
  next_classified_restructuring:'下一个已分类重整节点',
  next_stage_milestone:'下一个不同阶段里程碑',
  two_week_return_quantiles:'两周收益分位',
  two_week_move_frequency:'两周异动频率',
  selected_event:'选中事件',
  event_price_window:'事件价格窗口',
  risk_warning_window:'退市风险警示窗口',
  restructuring_window:'重整进展窗口',
  volatility_window:'短窗波动收敛窗口',
  controller_window:'控股股东司法处置窗口',
  abnormal_move_window:'交易异常波动窗口',
  stock_event_window:'选中事件窗口',
  stock_event_window_lens:'选中事件 Lens 缺口',
  restructuring_timing_evidence:'重整时点证据缺口',
  two_week_cross_section_evidence:'两周横截面证据缺口',
  consolidation_case_framework:'平台整理框架缺口',
  province_mapping_missing:'省份映射缺口',
  st_reason_announcement_binding:'ST 原因公告绑定缺口',
  st_interval_missing:'ST 状态区间缺失',
  daily_prices:'日线价格',
  'C03:stock_calendar_window':'股票日历窗口样本',
  'C04:stock_event_episode':'股票事件段样本',
  'C03:stock_calendar_month_panel':'股票日历月份面板样本',
  'C06:investor_quality':'投资人质量候选样本',
  'C14:market_cap_window':'市值分层样本',
  'C17:stock_price_behavior_episode':'股价行为事件样本',
}

const inlineLabels=Object.entries(labels)
  .filter(([key])=>key.includes('_')||key.includes(':'))
  .sort((a,b)=>b[0].length-a[0].length)

const phraseLabels:Array<[RegExp,string]>= [
  [/May describe the 12\/1\/4 calendar risk window as historically weaker in this bounded corpus, with N, cohort, as-of, and caveats\./gi,'可表述为：在当前有边界语料中，12/1/4 日历风险窗口历史表现偏弱；必须同时展示 N、样本组、截至日和边界。'],
  [/May describe November and January\/April as separate historical ST calendar regimes, with N, cohort, as-of, and caveats\./gi,'可表述为：11 月与 1/4 月分别属于历史 ST 日历窗口；必须同时展示 N、样本组、截至日和边界。'],
  [/May describe moving-average pullback as historically associated with short-window volatility compression, with N, cohort, as-of, and caveats\./gi,'可表述为：均线回踩在历史上与短窗波动收敛相关；必须同时展示 N、样本组、截至日和边界。'],
  [/Calendar-regime outputs are descriptive historical paths with censoring, not return promises or trading rules\./gi,'日历窗口输出只是带删失约束的历史路径描述，不是收益承诺或交易规则。'],
  [/M6 episode_index v0 rows are case_note_only context; proxy event-family counts do not open aggregation and do not upgrade evidence_grade\./gi,'M6 事件段索引 v0 行只作为个案记录上下文；代理事件族计数不开放聚合，也不提升证据等级。'],
  [/Source universe is the v5 canonical corpus bounded by forum mention threshold, not the full ST market\./gi,'来源语料为 v5 论坛提及边界样本，不是全 ST 市场。'],
  [/D-028 name-check gate applies: broad scope wording must match the source manifest exactly\./gi,'D-028 名称核对闸门适用：宽口径表述必须与源清单一致。'],
  [/Historical path differences are descriptive; they are not causality and not a future guarantee\./gi,'历史路径差异只是描述，不代表因果，也不是未来保证。'],
  [/Censoring can change observed distributions because suspended, delisted, or incomplete paths are excluded by frozen rules\./gi,'停牌、退市或不完整路径会按冻结规则被排除，删失可能改变观察到的分布。'],
  [/Multiple-check account: this lens contributes 3 main price-path units; event-family outcomes are side notes only in this round\./gi,'多重检验账：该 Lens 贡献 3 个主要价格路径单元；事件族结果本轮只作为旁注。'],
  [/v5 canonical corpus is forum-mention bounded, not full ST market/gi,'v5 语料是论坛提及边界样本，不是全 ST 市场'],
  [/Release output is descriptive evidence only; operational action wording is not permitted\./gi,'发布记录输出只作为描述性证据，不允许操作性行动措辞。'],
  [/Exact\/proxy N remain separate; proxy N is 0 because the D-031 rule is directly computable from daily_prices\./gi,'精确 N 与代理 N 分开报告；代理 N 为 0，因为 D-031 规则可由日线价格直接复算。'],
  [/C17 bootstrap clusters by symbol because repeated triggers in one stock are not independent\./gi,'C17 bootstrap 按股票聚类，因为同一股票的重复触发并不独立。'],
  [/Next-announcement wait is capped at 30 calendar days; capped observations are retained at 30 days\./gi,'下一公告等待期按 30 个自然日封顶；被封顶观察保留为 30 天。'],
  [/Multiple-check account: C17 contributes 6 main price-path units plus D-035 extra-outcome records in this local artifact\./gi,'多重检验账：C17 贡献 6 个主要价格路径单元，并包含 D-035 额外结果记录。'],
  [/Triggered windows do not show narrower short-window volatility, or the effect reverses by symbol\/year slice\./gi,'触发窗口未呈现更窄的短窗波动，或该效应在股票/年份切片中反转。'],
  [/Should not be called a trading signal\./gi,'不得称为交易信号。'],
  [/\bMay describe\b/gi,'可描述'],
  [/\bbounded\b/gi,'有边界的'],
  [/\btest result\b/gi,'测试结果'],
  [/negative=(\d+)/gi,'负向=$1'],
  [/neutral=(\d+)/gi,'中性=$1'],
  [/positive=(\d+)/gi,'正向=$1'],
  [/unstable=(\d+)/gi,'不稳定=$1'],
  [/\bRelease\b/g,'发布记录'],
  [/\bC17 lens\b/gi,'C17 股价行为样本'],
  [/\bC17 wording\b/gi,'历史股价行为样本措辞边界'],
  [/\btrigger N\b/gi,'触发样本 N'],
  [/\bcontrol N\b/gi,'对照样本 N'],
  [/\bas-of\b/gi,'截至日'],
  [/\banchor\b/gi,'锚点'],
  [/multiple-testing/gi,'多重检验'],
  [/\bwording\b/gi,'措辞边界'],
  [/\bcaveats?\b/gi,'边界说明'],
  [/\blens gap\b/gi,'Lens 缺口'],
  [/\bdata debt\b/gi,'数据债'],
  [/\brelease library\b/gi,'冻结 Lens 库'],
  [/\bmethodology frame\b/gi,'方法论框架'],
  [/\bevidence lens\b/gi,'证据 Lens'],
  [/\beffect digest\b/gi,'历史效应摘要'],
  [/\bcalendar-regime\b/gi,'日历窗口'],
  [/\bepisode\b/gi,'事件段'],
  [/\bpilot\b/gi,'试点样本'],
]

function formatText(value:string):string{
  if(labels[value])return labels[value]
  if(value.startsWith('announcement:'))return `公告编号 ${value.split(':')[1]}`
  if(value.includes('st_stocks_v5_backup.sqlite3::daily_prices'))return value.includes('[')
    ? `v5 价格库：前复权日线（${value.split('[')[1]?.split(']')[0] ?? '指定股票'}）`
    : 'v5 价格库：前复权日线'
  if(value.includes('st_stocks_v5_backup.sqlite3::company_announcements'))return value.includes('[')
    ? `v5 公告库：公司公告（${value.split('[')[1]?.split(']')[0] ?? '指定股票'}）`
    : 'v5 公告库：公司公告'
  if(value.includes('st_stocks_v5_backup.sqlite3::st_status_history'))return 'v5 ST 生命周期表'
  if(value.includes('shareholder_count.sqlite3::shareholder_count_snapshots'))return value.includes('[')
    ? `v7 股东人数试点（${value.split('[')[1]?.split(']')[0] ?? '指定股票'}）`
    : 'v7 股东人数试点'
  if(value.includes('shareholder_count.sqlite3::equity_timeline_events'))return value.includes('[')
    ? `v7 股权事件试点（${value.split('[')[1]?.split(']')[0] ?? '指定股票'}）`
    : 'v7 股权事件试点'
  if(value.includes('v7_worksite/coordination/debt_cards/D-051A_province_mapping.md'))return '数据债卡 D-051A：省份映射'
  if(value==='shared_data/v7/episode_index_v0/episode_index.jsonl')return 'M6 事件段索引 v0'
  if(value==='shared_data/v7/release_library_v1/release_library.json')return 'v7.4 冻结 Lens 库 v1'
  if(value.includes('/validation_reports_2026_07/'))return value.includes('c03')
    ? 'v7 验证报告：股票日历窗口'
    : 'v7 验证报告'
  if(value.includes('/effect_round_2026_07_08/'))return value.includes('342809172')
    ? 'v7 效应报告：股票日历窗口'
    : 'v7 效应报告'
  if(value.startsWith('v5_lifecycle_jsonl_seed'))return 'ST 生命周期历史快照'
  if(value==='v5_2026_title_audit_lower_bound')return '2026 公告标题审计下界'
  if(/^nearby_announcement_\d+$/.test(value))return `邻近公告 ${value.split('_').at(-1)}`
  if(/^release_evidence_rl_/.test(value))return 'Lens 证据记录'
  if(/^methodology_rl_/.test(value))return '方法论记录'
  if(/^st_interval_\d+$/.test(value))return `ST 状态区间 ${value.split('_').at(-1)}`
  if(/^data_debt_/.test(value))return '数据债缺口'
  const withPhrasesFirst=phraseLabels.reduce((result,[pattern,label])=>result.replace(pattern,label),value)
  const withInline=inlineLabels.reduce((result,[key,label])=>result.replaceAll(key,label),withPhrasesFirst)
  const withPhrases=phraseLabels.reduce((result,[pattern,label])=>result.replace(pattern,label),withInline)
  if(/^C\d{2}:[^;\s]+$/.test(withPhrases))return '研究样本组'
  const withUnknownCohort=withPhrases.replace(/^C\d{2}:[^;\s]+/, '研究样本组')
  return withUnknownCohort
}

export function show(value:unknown):string{
  if(value===null||value===undefined||value==='')return '无'
  if(typeof value==='number')return value.toLocaleString('zh-CN')
  if(typeof value==='boolean')return value?'是':'否'
  if(Array.isArray(value))return value.length?value.map(show).join('、'):'无'
  if(typeof value==='object')return Object.entries(value as Record<string,unknown>)
    .map(([key,nested])=>`${show(key)}：${show(nested)}`)
    .join('；')
  return formatText(String(value))
}
