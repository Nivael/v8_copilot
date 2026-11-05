import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {ETFReportContinuity} from './ETFReportContinuity'
import type {MarketRiskStatus} from './types'

const fixture:NonNullable<MarketRiskStatus['etf_report_continuity']>={
  version:'etf_report_continuity_v1',availability:'partial',declared_etfs:8,observed_midyear_reports:1,compared_etfs:1,
  matched_etfs:1,mismatched_etfs:0,corporate_actions_checked:false,
  period_start:'2026-01-01',period_end:'2026-06-30',following_period_start:'2026-07-01',following_period_end:'2026-09-30',
  note:'八月底披露的中期报告反映上半年，不代表近两个月的申赎。',reports:[{
    code:'510310.SH',midyear_report:{code:'510310.SH',availability:'observed',publication_date:'2026-08-31',
      pdf_url:'https://www.sse.com.cn/mid.pdf',table_page:58,closing_shares:'11644903922.00',opening_shares:'65934431663.00',
      subscription_shares:'3463872259.00',redemption_shares:'57753400000.00',net_subscription_shares:'-54289527741.00',
      split_entry:'-',accounting_residual_shares:'0.00',off_exchange_closing_shares:'44159905',
      audit_status:'report_states_unaudited',document_observed_at:'2026-11-04T22:19:00Z'},
    quarterly_report:{code:'510310.SH',availability:'observed',publication_date:'2026-10-27',
      pdf_url:'https://www.sse.com.cn/q3.pdf',table_page:13,opening_shares:'11644903922.00',off_exchange_opening_shares:'44159905'},
    comparison:{availability:'observed',total_relation:'equal',total_difference_shares:'0.00',off_exchange_relation:'equal',off_exchange_difference_shares:'0'},
  }],
}

describe('ETFReportContinuity',()=>{
  afterEach(cleanup)
  it('keeps the reporting periods, publication dates, acquisition time and exact whole-fund values separate',()=>{
    render(<ETFReportContinuity data={fixture}/>)
    expect(screen.getByRole('heading',{name:'中报与三季报份额衔接'})).toBeInTheDocument()
    expect(screen.getByText(/中报期间 2026-01-01 至 2026-06-30；三季报期间 2026-07-01 至 2026-09-30/)).toBeInTheDocument()
    expect(screen.getByText('中报披露于 2026-08-31')).toBeInTheDocument()
    expect(screen.getByText('三季报披露于 2026-10-27')).toBeInTheDocument()
    expect(screen.getAllByText('11,644,903,922.00 份')).toHaveLength(2)
    expect(screen.getByRole('link',{name:'中报 · PDF第58页 ↗'})).toHaveAttribute('href','https://www.sse.com.cn/mid.pdf#page=58')
    expect(screen.getByRole('link',{name:'三季报 · PDF第13页 ↗'})).toHaveAttribute('href','https://www.sse.com.cn/q3.pdf#page=13')
    expect(screen.getByText('明示场外份额差 0 份 · 相等')).toBeInTheDocument()
    fireEvent.click(screen.getByText('上半年份额明细'))
    expect(screen.getByText(/申购－赎回 -54,289,527,741.00 份，仅属于上半年/)).toBeVisible()
    expect(screen.getByText(/中报财务资料未经审计。本次取得于 2026\/11\/5 06:19:00/)).toBeVisible()
  })
  it('does not replace undisclosed off-exchange scope with zero',()=>{
    const row=fixture.reports[0]
    render(<ETFReportContinuity data={{...fixture,reports:[{...row,
      midyear_report:{...row.midyear_report,off_exchange_closing_shares:null},quarterly_report:{...row.quarterly_report,off_exchange_opening_shares:null},
      comparison:{...row.comparison,off_exchange_relation:'not_disclosed_in_both',off_exchange_difference_shares:null},
    }]}}/>)
    expect(screen.getByText('场外份额未在两份报告同时明确列示，未按零补齐')).toBeInTheDocument()
    expect(screen.queryByText(/明示场外份额差 0/)).not.toBeInTheDocument()
  })
  it('shows a small exact mismatch and a separately different off-exchange amount',()=>{
    const row=fixture.reports[0]
    render(<ETFReportContinuity data={{...fixture,matched_etfs:0,mismatched_etfs:1,reports:[{...row,
      comparison:{availability:'observed',total_relation:'different',total_difference_shares:'-0.01',off_exchange_relation:'different',off_exchange_difference_shares:'1'},
    }]}}/>)
    expect(screen.getByText('-0.01 份 · 不一致，待核对')).toBeInTheDocument()
    expect(screen.getByText('明示场外份额差 1 份 · 不一致，待核对')).toBeInTheDocument()
    expect(screen.getByText(/总份额不一致 1 只/)).toBeInTheDocument()
  })
  it('retains a verified midyear report when its following report is missing',()=>{
    const row=fixture.reports[0]
    render(<ETFReportContinuity data={{...fixture,matched_etfs:0,compared_etfs:0,reports:[{...row,
      quarterly_report:{code:row.code,availability:'invalid'},comparison:{...row.comparison,availability:'missing',total_relation:'not_compared',total_difference_shares:null},
    }]}}/>)
    expect(screen.getByRole('link',{name:'中报 · PDF第58页 ↗'})).toBeInTheDocument()
    expect(screen.getByText('三季报份额表尚未通过校验')).toBeInTheDocument()
    expect(screen.getByText('缺少可比报告，未比较')).toBeInTheDocument()
    expect(screen.queryByText('0.00 份 · 总份额相等')).not.toBeInTheDocument()
  })
  it('does not compare a nonadjacent quarter',()=>{
    render(<ETFReportContinuity data={{...fixture,availability:'not_applicable',reports:[],matched_etfs:0,compared_etfs:0,observed_midyear_reports:0}}/>)
    expect(screen.getByText('本项只比较相邻的中报与三季报；当前报告期不适用。')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})
