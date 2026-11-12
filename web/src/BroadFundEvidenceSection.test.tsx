import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {BroadFundEvidenceSection} from './BroadFundEvidenceSection'
import type {BroadFundEvidence} from './readingTypes'

const data:BroadFundEvidence={unit_nav:{availability:'available',as_of:'2026-11-06',observed_funds:8,sample_funds:12,sessions:61,fetched_at:'2026-11-06T19:56:00Z',interpretation:'净值是每份基金资产的价格。',rows:[{code:'510310.SH',name:'易方达沪深300ETF',as_of:'2026-11-06',unit_nav:'4.0000',five_day_share_change_pct:12,five_day_nav_change_pct:-2,twenty_day_nav_change_pct:-6,five_day_nav_anchor:'2026-10-30',twenty_day_nav_anchor:'2026-10-09',source_url:'https://www.efunds.com.cn/fund/510310.shtml',source_label:'易方达'}]},holders:{availability:'available',period_start:'2026-07-01',period_end:'2026-09-30',headline:'三季报披露联接基金持有变化',interpretation:'季度持有与近期每日份额分别看。',scope_note:'未达到20%阈值不等于没有持仓。',rows:[{code:'510310.SH',name:'易方达沪深300ETF',kind:'feeder_fund',holder_label:'报告中的联接基金完整名称',period_start:'2026-07-01',period_end:'2026-09-30',published_on:'2026-10-27',opening_shares:'200000000.00',closing_shares:'172200000.00',holding_change_shares:'-27800000.00',closing_share_pct:'17.22',sources:[{label:'基金三季报 · 第14页',url:'https://www.sse.com.cn/report.pdf#page=14'}]},{code:'510300.SH',name:'华泰柏瑞沪深300ETF',kind:'no_20pct_holder_reported',period_start:'2026-07-01',period_end:'2026-09-30',published_on:'2026-10-27',sources:[{label:'另一基金三季报 · 第12页',url:'https://www.sse.com.cn/other.pdf#page=12'}]}]}}

describe('dated broad-fund source observations',()=>{
  afterEach(cleanup)
  it('keeps the conclusion visible, details folded and quarter dates distinct from current NAV dates',()=>{
    render(<BroadFundEvidenceSection data={data}/>)
    expect(screen.getByRole('heading',{name:data.holders.headline!})).toBeVisible()
    const holders=screen.getByText('哪些基金在增加持有 · 三季报原文').closest('details')!
    const nav=screen.getByText('净值已补至2026-11-06 · 8/12只宽基样本').closest('details')!
    expect(holders.open).toBe(false);expect(nav.open).toBe(false)
    fireEvent.click(screen.getByText('哪些基金在增加持有 · 三季报原文'))
    expect(screen.getByText(/2026-07-01 至 2026-09-30/)).toBeVisible()
    expect(screen.getByText('-0.28亿份')).toBeVisible()
    expect(screen.queryByText('+-0.28亿份')).not.toBeInTheDocument()
    expect(screen.getByText('期末占比 17.22%')).toBeVisible()
    expect(screen.getByText('报告期内未出现达到20%披露阈值的单一投资者')).toBeVisible()
    fireEvent.click(screen.getByText('精确份额与报告页码'))
    expect(screen.getByRole('link',{name:'基金三季报 · 第14页 ↗'})).toHaveAttribute('href','https://www.sse.com.cn/report.pdf#page=14')
    expect(screen.getByText(/报告中的联接基金完整名称：期初 200000000.00/)).toBeVisible()
    expect(within(nav).getByText('4.0000元')).not.toBeVisible()
  })
  it('shows same-window NAV and share changes with exact values and source dates behind expansion',()=>{
    render(<BroadFundEvidenceSection data={data}/>)
    fireEvent.click(screen.getByText('净值已补至2026-11-06 · 8/12只宽基样本'))
    expect(screen.getByText('4.0000元')).toBeVisible()
    expect(screen.getByText('-2.00%')).toBeVisible();expect(screen.getByText('+12.00%')).toBeVisible()
    expect(screen.getByRole('link',{name:'易方达沪深300ETF · 易方达 ↗'})).not.toBeVisible()
    fireEvent.click(screen.getByText('比较日期与各基金原始净值'))
    expect(screen.getByRole('link',{name:'易方达沪深300ETF · 易方达 ↗'})).toHaveAttribute('href',data.unit_nav.rows![0].source_url)
    expect(screen.getByText(/5日从2026-10-30、20日从2026-10-09比较至2026-11-06/)).toBeVisible()
    expect(screen.getByText(/下表比较单位净值与份额的同窗变化/)).toBeVisible()
  })
  it('keeps an independently valid source visible and does not substitute a zero for an unavailable one',()=>{
    const {rerender}=render(<BroadFundEvidenceSection data={{...data,unit_nav:{availability:'unavailable'}}}/>)
    expect(screen.getByRole('heading',{name:data.holders.headline!})).toBeVisible()
    expect(screen.queryByText(/净值已补至/)).not.toBeInTheDocument()
    rerender(<BroadFundEvidenceSection data={{unit_nav:{availability:'unavailable'},holders:{availability:'unavailable'}}}/>)
    expect(screen.queryByRole('region',{name:'宽基ETF净值与披露持有人'})).not.toBeInTheDocument()
  })
  it('leads with the twelve-sample judgment while keeping quarterly coverage independent',()=>{
    const updated:BroadFundEvidence={...data,unit_nav:{...data.unit_nav,observed_funds:12,
      headline:'12只样本近5日份额和净值都回升',
      interpretation:'短线承接出现改善，但12只近20日净值仍下跌。',
      basis_note:'这里比较同一窗口的份额方向与单位净值，不能据此认定买方身份。'}}
    render(<BroadFundEvidenceSection data={updated}/>)
    expect(screen.getByRole('heading',{name:updated.unit_nav.headline!})).toBeVisible()
    expect(screen.getByText(updated.unit_nav.interpretation!)).toBeVisible()
    const nav=screen.getByText('净值已补至2026-11-06 · 12/12只宽基样本').closest('details')!
    expect(nav.open).toBe(false)
    expect(screen.getByText(updated.unit_nav.basis_note!)).not.toBeVisible()
    fireEvent.click(screen.getByText('哪些基金在增加持有 · 三季报原文'))
    expect(screen.getByText(/此处核对2只基金的季度披露/)).toBeVisible()
    expect(nav.open).toBe(false)
  })
})
