import {cleanup,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {MarketCapCohortPanel} from './MarketCapCohortPanel'
import {marketCapCohortData} from './marketCapCohortData'

const rows:Array<Record<string,unknown>>=[
  {
    row_id:'microcap_definition',记录类型:'市值分层定义',
    收益窗口起点:'2026-07-06',收益窗口终点:'2026-07-20',因子日期:'2026-07-06',
    微盘阈值:'20.61亿元',微盘口径:'窗口起点 ST 总市值最小 30%；阈值同值一并纳入',
    ST成员数:211,有效市值数:208,市值覆盖率:'98.58%',
  },
  {
    row_id:'microcap_distribution',记录类型:'市值分层分布',分组:'微盘ST',
    成员数:63,有效收益数:60,收益覆盖率:'95.24%',平均收益:'-11.75%',
    中位收益:'-14.01%',中位总市值:'17.07亿元',
  },
  {
    row_id:'other_st_distribution',记录类型:'市值分层分布',分组:'普通ST',
    成员数:145,有效收益数:142,收益覆盖率:'97.93%',平均收益:'-12.40%',
    中位收益:'-10.67%',中位总市值:'36.17亿元',
  },
  {
    row_id:'microcap_comparison_summary',记录类型:'市值分层比较摘要',
    微盘减普通ST平均收益:'+0.65个百分点',微盘减普通ST中位收益:'-3.34个百分点',
    解释边界:'百分点差只描述该窗口历史分布，不是 alpha 或交易信号',
  },
]

describe('MarketCapCohortPanel',()=>{
  it('parses stable AnswerCard row ids without changing the answer contract',()=>{
    const parsed=marketCapCohortData(rows)
    expect(parsed.definition?.['微盘阈值']).toBe('20.61亿元')
    expect(parsed.microcap?.['成员数']).toBe(63)
    expect(parsed.gap).toBeNull()
  })

  it('renders the frozen definition, both cohorts, coverage, and relative differences',()=>{
    render(<MarketCapCohortPanel rows={rows}/>)
    expect(screen.getByRole('region',{name:'窗口起点市值分层'})).toBeInTheDocument()
    expect(screen.getByRole('heading',{name:'窗口起点市值分层'})).toBeInTheDocument()
    expect(screen.getByText('微盘阈值 20.61亿元')).toBeInTheDocument()
    expect(screen.getByText('60/63 · 95.24%')).toBeInTheDocument()
    expect(screen.getByText('+0.65个百分点')).toBeInTheDocument()
    expect(screen.getByText('-3.34个百分点')).toBeInTheDocument()
    expect(screen.getByText(/不是 alpha 或交易信号/)).toBeInTheDocument()
  })

  it('renders an explicit operational gap instead of an empty comparison',()=>{
    render(<MarketCapCohortPanel rows={[{
      row_id:'microcap_comparison_gap',记录类型:'市值分层缺口',缺口:'market-factor manifest 不存在',
    }]}/>)
    expect(screen.getByRole('region',{name:'市值分层缺口'})).toBeInTheDocument()
    expect(screen.getByText('market-factor manifest 不存在')).toBeInTheDocument()
  })
})

afterEach(()=>cleanup())
