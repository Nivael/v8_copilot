import {cleanup,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {MarketComparisonChart} from './MarketComparisonChart'
import {comparisonData} from './marketComparisonData'

const rows:Array<Record<string,unknown>>=[
  {
    row_id:'market_comparison_summary',记录类型:'市场对比摘要',
    窗口起点:'2026-07-06',窗口终点:'2026-07-20',
    个股收益:'-29.18%',ST等权收益:'-12.79%',中证2000收益:'-19.30%',中证全指收益:'-11.22%',
    个股相对ST:'-16.39个百分点',个股相对中证2000:'-9.88个百分点',
    个股相对全市场:'-17.96个百分点',ST相对中证2000:'+6.51个百分点',
    ST相对全市场:'-1.57个百分点',中证2000相对全市场:'-8.08个百分点',
  },
  ...['2026-07-06','2026-07-07'].map((date,index)=>({
    row_id:`market_comparison_point_0${index+1}`,记录类型:'市场对比序列',date,
    stock_normalized:100-index*2,st_normalized:100-index,csi2000_normalized:100-index*3,
    market_normalized:100-index*.5,
  })),
]

describe('MarketComparisonChart',()=>{
  it('parses typed AnswerCard rows without a new answer contract',()=>{
    const parsed=comparisonData(rows)
    expect(parsed.summary?.['个股收益']).toBe('-29.18%')
    expect(parsed.points).toHaveLength(2)
    expect(parsed.points[1].csi2000).toBe(97)
  })

  it('renders four aligned return metrics and the common window',()=>{
    render(<MarketComparisonChart rows={rows}/>)
    expect(screen.getByRole('region',{name:'同窗市场对比'})).toBeInTheDocument()
    expect(screen.getByRole('heading',{name:'同窗市场对比'})).toBeInTheDocument()
    expect(screen.getByText('2026-07-06 — 2026-07-20')).toBeInTheDocument()
    expect(screen.getByText('-29.18%')).toBeInTheDocument()
    expect(screen.getByText('-19.30%')).toBeInTheDocument()
    expect(screen.getByRole('generic',{name:'相对收益百分点差'})).toBeInTheDocument()
    expect(screen.getByText('-16.39个百分点')).toBeInTheDocument()
    expect(screen.getByText('ST − 中证2000')).toBeInTheDocument()
    expect(screen.getByText(/不代表资金净流入/)).toBeInTheDocument()
  })

  it('does not render when the strict comparison is unavailable',()=>{
    const {container}=render(<MarketComparisonChart rows={[
      {row_id:'market_comparison_gap',记录类型:'市场对比缺口',缺口:'价格缺失'},
    ]}/>)
    expect(container).toBeEmptyDOMElement()
  })
})

afterEach(()=>cleanup())
