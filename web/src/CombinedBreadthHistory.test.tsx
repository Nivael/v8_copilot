import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {CombinedBreadthHistory} from './CombinedBreadthHistory'
import type {CombinedBreadthHistory as History} from './types'

const data:History={version:'synthetic',availability:'observed',complete_market_history:true,historical_ST_ready:false,historical_PIT:false,effect_measured:false,
  covered_venues:['SSE','SZSE'],missing_venues:[],start:'2026-09-04',through:'2026-11-04',expected_days:2,observed_days:2,observation_count:10,traded_observation_count:8,
  source_url:'https://www.sse.com.cn/disclosure/dealinstruc/suspension/stock/',note:'停牌不作平盘；本次简称不回填历史ST成员。',
  points:[{date:'2026-09-04',all:{declining_share_pct:75,observed_trading_stocks:4,nontrading_stocks:1},SSE:{declining_share_pct:100,observed_trading_stocks:3,nontrading_stocks:1},SZSE:{declining_share_pct:0,observed_trading_stocks:1,nontrading_stocks:0}},
    {date:'2026-11-04',all:{declining_share_pct:50,observed_trading_stocks:4,nontrading_stocks:1},SSE:{declining_share_pct:50,observed_trading_stocks:2,nontrading_stocks:1},SZSE:{declining_share_pct:50,observed_trading_stocks:2,nontrading_stocks:0}}],
  sse_suspensions:{source_rows:4,ordinary_A_records:2,excluded:{other_securities_or_business:2},notice_confirmed_days:1,additional_continuous_days:1,
    records:[{symbol:'688001',name_as_reported:'*ST样本',start_on:'2026-09-04',last_suspended_on:null,kind:'continuous',open_when_observed:true,reason:'重要公告',end_reason:'',window_days:['2026-09-04','2026-11-04']}]}}

describe('CombinedBreadthHistory',()=>{
  afterEach(cleanup)
  it('shows all three markets and allows keyboard-accessible date selection with actual denominators',()=>{
    render(<CombinedBreadthHistory data={data}/>)
    expect(screen.getByRole('img',{name:'沪深及两所每日下跌股票比例路径'})).toBeVisible()
    const slider=screen.getByRole('slider',{name:'市场宽度观察日期'})
    expect(slider).toHaveAttribute('aria-valuetext','2026-11-04')
    fireEvent.change(slider,{target:{value:'0'}})
    expect(slider).toHaveAttribute('aria-valuetext','2026-09-04')
    expect(screen.getByText('沪深A股：下跌 75.00% · 有成交 4 · 无成交 1')).toBeVisible()
    expect(screen.getByText('沪市A股：下跌 100.00% · 有成交 3 · 无成交 1')).toBeVisible()
    expect(screen.getByText('停牌不作平盘；本次简称不回填历史ST成员。')).toBeVisible()
  })
  it('keeps ongoing stops open and exposes independently scrollable daily and interval proofs',()=>{
    render(<CombinedBreadthHistory data={data}/>);fireEvent.click(screen.getByText('逐日数量与停牌依据'))
    expect(screen.getByText('观测时仍持续')).toBeVisible()
    expect(screen.getByRole('region',{name:'可滚动的沪深每日宽度核对表'})).toHaveAttribute('tabindex','0')
    expect(screen.getByRole('region',{name:'可滚动的沪市停牌登记表'})).toHaveAttribute('tabindex','0')
    expect(screen.getByRole('link',{name:'上交所停复牌登记 ↗'})).toHaveAttribute('href',data.source_url)
    expect(screen.getByText(/恰好解释 2 个未返回股票日/)).toBeVisible()
  })
  it.each(['invalid','short','null','duplicate','out_of_range'])('withholds stale, incomplete or invalid combined paths (%s)',kind=>{
    const test=structuredClone(data)
    if(kind==='invalid')test.availability='invalid'
    if(kind==='short')test.points.pop()
    if(kind==='null')test.points[0].SSE.declining_share_pct=null
    if(kind==='duplicate')test.points[1].date=test.points[0].date
    if(kind==='out_of_range')test.points[0].all.declining_share_pct=101
    render(<CombinedBreadthHistory data={test}/>)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.queryByRole('slider')).not.toBeInTheDocument()
    expect(screen.getByText(/缺失不会解释为低风险/)).toBeVisible()
  })
})
