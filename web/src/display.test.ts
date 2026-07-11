import {describe,expect,it} from 'vitest'
import {show} from './display'

const hiddenTokens=[
  'C03:stock_calendar_window',
  'aggregate_weak',
  'effect_digest',
  'negative',
  'neutral',
  'anchor',
  'multiple-testing',
  'Calendar-regime',
  'announcement:',
  'allowed_wording',
  'forbidden_wording',
  'May describe',
  'caveat',
  'episode',
  'restructuring_path',
  'investor_or_control_change',
  'control_or_investor',
  'risk_warning_window',
  'episode_index_v0',
  'release_library_v1',
  'validation_reports_2026_07',
  'effect_round_2026_07_08',
  'v7_worksite',
  'debt_cards',
]

describe('display labels',()=>{
  it('hides raw taxonomy and English wording notes in nested values',()=>{
    const text=show({
      evidence_grade:'aggregate_weak',
      cohort_id:'C03:stock_calendar_window',
      provenance_refs:['announcement:1221766612','RL-A-003'],
      allowed_wording:'May describe the bounded test result.',
      forbidden_wording:['Should not be called a trading signal.'],
      selected_episode:'restructuring_path',
      subtype:'investor_or_control_change',
      backing:'risk_warning_window',
      basis:'control_or_investor 冻结/拍卖/过户',
      source:'shared_data/v7/episode_index_v0/episode_index.jsonl',
      library:'shared_data/v7/release_library_v1/release_library.json',
    })

    expect(text).toContain('汇总弱证据')
    expect(text).toContain('股票日历窗口样本')
    expect(text).toContain('公告编号 1221766612')
    expect(text).toContain('重整路径')
    expect(text).toContain('投资人或控制权变化')
    expect(text).toContain('退市风险警示窗口')
    expect(text).toContain('控制权或投资人变化')
    expect(text).toContain('M6 事件段索引 v0')
    expect(text).toContain('v7.4 冻结 Lens 库 v1')
    hiddenTokens.forEach(token=>expect(text).not.toContain(token))
  })

  it('renders real calendar evidence fields without losing trigger/control N',()=>{
    const text=show({
      sample_scope:'C03:stock_calendar_window；trigger N=16215；control N=20462',
      evidence_grade:'aggregate_weak',
      body_row:{
        release_id:'RL-A-001',
        effect_digest:{negative:2,neutral:4},
        反例形状:'触发月份/报告期窗口与对照窗口相比没有方向差异、方向反转，或差异只由单一年份/制度段集中贡献的年份切片。',
        允许措辞:'May describe the 12/1/4 calendar risk window as historically weaker in this bounded corpus, with N, cohort, as-of, and caveats.',
      },
      caveats:[
        '必须预注册 anchor、窗口、比较组和所有变量；结论只做历史描述并附 multiple-testing caveat。',
        'Calendar-regime outputs are descriptive historical paths with censoring, not return promises or trading rules.',
        'M6 episode_index v0 rows are case_note_only context; proxy event-family counts do not open aggregation and do not upgrade evidence_grade.',
      ],
      provenance:[
        'shared_data/v7/release_library_v1/release_library.json',
        'shared_data/v7/validation_reports_2026_07/reports/v7_report_c03_3f9f7d626f35.json',
        'shared_data/v7/effect_round_2026_07_08/342809172_effect_report.json',
      ],
    })

    expect(text).toContain('股票日历窗口样本')
    expect(text).toContain('触发样本 N=16215')
    expect(text).toContain('对照样本 N=20462')
    expect(text).toContain('历史效应摘要')
    expect(text).toContain('负向：2')
    expect(text).toContain('中性：4')
    expect(text).toContain('12/1/4 日历风险窗口')
    expect(text).toContain('锚点')
    expect(text).toContain('多重检验')
    expect(text).toContain('日历窗口输出只是带删失约束的历史路径描述')
    expect(text).toContain('M6 事件段索引 v0 行只作为个案记录上下文')
    expect(text).toContain('v7.4 冻结 Lens 库 v1')
    expect(text).toContain('v7 验证报告：股票日历窗口')
    expect(text).toContain('v7 效应报告：股票日历窗口')
    hiddenTokens.forEach(token=>expect(text).not.toContain(token))
  })

  it('keeps formal provenance ids visible',()=>{
    expect(show('RL-A-003')).toBe('RL-A-003')
    expect(show('D-051A')).toBe('D-051A')
  })

  it('localizes new answerability freshness and pilot provenance',()=>{
    const text=show({
      st_evidence_generated_at:'2026-06-28',
      shareholder_count_as_of:'2026-06-30',
      dimension:'shareholder_count',
      source:'shared_data/v7/shareholder_count_pilot/shareholder_count.sqlite3::shareholder_count_snapshots[603398]',
    })

    expect(text).toContain('ST 触发公告证据生成日')
    expect(text).toContain('股东人数数据截至')
    expect(text).toContain('股东人数')
    expect(text).toContain('v7 股东人数试点（603398）')
    expect(text).not.toContain('shareholder_count')
    expect(text).not.toContain('shared_data/')
  })

  it('preserves unregistered evidence boundary text without dropping facts',()=>{
    const text=show(
      'Unregistered evidence note: threshold 0.73; N=12; counterexample boundary: effect reverses after shock-window thinning.',
    )

    expect(text).toContain('threshold 0.73')
    expect(text).toContain('N=12')
    expect(text).toContain('counterexample boundary')
    expect(text).toContain('effect reverses')
    expect(text).not.toContain('见证据库措辞与边界说明')
  })

  it('renders C17 free-text effect status and debt-card provenance labels',()=>{
    const text=show({
      claim:'效应摘要为 negative=2、neutral=5、positive=3、unstable=2。',
      caveat:'Release output is descriptive evidence only; operational action wording is not permitted.',
      provenance:'v7_worksite/coordination/debt_cards/D-051A_province_mapping.md',
    })

    expect(text).toContain('负向=2')
    expect(text).toContain('中性=5')
    expect(text).toContain('正向=3')
    expect(text).toContain('不稳定=2')
    expect(text).toContain('发布记录输出只作为描述性证据')
    expect(text).toContain('数据债卡 D-051A：省份映射')
    hiddenTokens.forEach(token=>expect(text).not.toContain(token))
  })
})
