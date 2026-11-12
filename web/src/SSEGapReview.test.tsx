import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import type {SSEGapReview as Review} from './types'
import {SSEGapReview} from './SSEGapReview'

const data:Review={version:'synthetic',availability:'partial',start:'2026-09-04',through:'2026-11-04',
  historical_breadth_ready:false,historical_ST_ready:false,historical_PIT:false,effect_measured:false,
  reviewed_episodes:2,distinct_companies:2,closed_episodes:1,original_pdfs:2,not_returned_days:5,confirmed_missing_days:2,unresolved_missing_days:3,
  materialized_at:'2026-11-05T06:30:00Z',note:'终止上市日不作复牌日，停牌不填零收益。',episodes:[
    {case_id:'closed',symbol:'600001',company:'退出样本公司',kind:'continuous_to_listing_end',start_on:'2026-10-15',end_exclusive:'2026-10-19',
      interval_closed:true,window_days:['2026-10-15','2026-10-16'],confirmed_missing_days:2,unresolved_missing_days:0,endpoint_nontrading_confirmed:null,
      proofs:[{source_url:'https://static.cninfo.com.cn/finalpage/2026-09-12/123.PDF',pages:[1,2],role:'continuous_until_listing_end',published_on:'2026-09-12',observed_at:'2026-11-05T06:00:00Z'}]},
    {case_id:'pending',symbol:'688001',company:'区间待核公司',kind:'start_only',start_on:'2026-11-02',end_exclusive:null,
      interval_closed:false,window_days:['2026-11-02','2026-11-03','2026-11-04'],confirmed_missing_days:0,unresolved_missing_days:3,endpoint_nontrading_confirmed:true,
      proofs:[{source_url:'https://static.cninfo.com.cn/finalpage/2026-11-02/124.PDF',pages:[1],role:'halt_start',published_on:'2026-11-02',observed_at:'2026-11-05T06:01:00Z'}]},
  ],days:[{date:'2026-11-04',confirmed_suspended:[],unresolved:['688001.SH']}]}
const open=()=>fireEvent.click(screen.getByText('沪市历史缺日 · 已解释 2/5 股票日'))

describe('SSEGapReview',()=>{
  afterEach(cleanup)
  it('separates explained missing days from unresolved continuity and overall coverage',()=>{
    render(<SSEGapReview data={data}/>);open()
    expect(screen.getByText(/1 组有完整区间依据，解释 2 个缺失股票日；另有 3 日仍待补证/)).toBeVisible()
    expect(screen.getByText(/688001（3日）/)).toBeVisible()
    expect(screen.getByText(/沪市完整历史涨跌分布待补/)).toBeVisible()
    expect(screen.getByText('待补证 3 日')).toBeVisible()
  })
  it('keeps termination separate from resumption and links the original physical pages',()=>{
    render(<SSEGapReview data={data}/>);open()
    expect(screen.getByText('2026-10-19 终止上市，不作复牌日')).toBeVisible()
    expect(screen.getByRole('link',{name:'持续至终止上市 · 第 1、2 页 ↗'})).toHaveAttribute('href',data.episodes![0].proofs[0].source_url)
    expect(screen.getByText('发布 2026-09-12；取得 2026/11/5 14:00:00')).toBeVisible()
  })
  it('allows keyboard scrolling and retains per-day unresolved symbols',()=>{
    render(<SSEGapReview data={data}/>);open();fireEvent.click(screen.getByText('逐日查看已解释与待补证代码'))
    expect(screen.getByRole('region',{name:'可滚动的沪市停复牌依据表'})).toHaveAttribute('tabindex','0')
    expect(screen.getByRole('region',{name:'可滚动的沪市每日缺日解释表'})).toHaveAttribute('tabindex','0')
    expect(screen.getByText('688001.SH')).toBeVisible()
  })
  it('withholds stale totals and tables when source validation fails',()=>{
    render(<SSEGapReview data={{...data,availability:'invalid'}}/>);fireEvent.click(screen.getByText('沪市历史缺日 · 依据尚未通过核对'))
    expect(screen.getByText(/暂不沿用旧的已解释数量/)).toBeVisible()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.queryByText(/已解释 2\/5/)).not.toBeInTheDocument()
  })
  it('keeps the notice-only limitation separate after exchange intervals close the remaining dates',()=>{
    render(<SSEGapReview data={data} reconciled/>);fireEvent.click(screen.getByText('沪市历史缺日 · 仅公告解释 2/5 股票日'))
    expect(screen.getByText(/这些日期现已由上方独立的停复牌登记全部核对/)).toBeVisible()
    expect(screen.queryByText(/沪市完整历史涨跌分布继续待补/)).not.toBeInTheDocument()
    expect(screen.getByText('公告未闭合 3 日')).toBeVisible()
  })
})
