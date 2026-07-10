const DISPLAY: Record<string, string> = {
  aggregate_weak: '汇总弱证据',
  small_n_case_notes: '小样本案例证据',
  anecdotal_support: '个案支持',
  descriptive_query: '描述性查询',
  insufficient_data: '数据不足',
  evidence: '证据',
  query: '查询',
  checklist: '观察清单',
  methodology: '方法论',
  data_debt: '数据债',
  evidence_lens: '证据 lens',
  methodology_frame: '方法论框架',
  restructuring_path: '重整路径',
  delisting_terminal_path: '终止上市风险',
  control_or_investor_path: '控制权或投资人变化',
  'C17:stock_price_behavior_episode': '股价行为事件样本',
  'C04:stock_event_episode': '股票事件段样本',
}

export function humanize(value: unknown): string {
  if (value === null || value === undefined || value === '') return '无'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'number') return new Intl.NumberFormat('zh-CN').format(value)
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  const text = String(value)
  if (DISPLAY[text]) return DISPLAY[text]
  if (text.startsWith('announcement:')) return `公告编号 ${text.split(':', 2)[1]}`
  return text
    .replaceAll('C17 wording', '历史股价行为样本措辞边界')
    .replaceAll('wording', '措辞边界')
}

export function badgeTone(value: string): string {
  if (value.includes('data') || value.includes('gap') || value.includes('不足')) return 'debt'
  if (value.includes('evidence') || value.includes('证据')) return 'evidence'
  if (value.includes('checklist') || value.includes('清单')) return 'checklist'
  return 'query'
}
