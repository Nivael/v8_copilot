import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import type {SSEHistoryArchive} from './types'
import {SSEHistorySources} from './SSEHistorySources'

const data:SSEHistoryArchive={version:'synthetic',availability:'observed',start:'2026-09-04',through:'2026-11-04',
  historical_breadth_ready:false,historical_ST_ready:false,effect_measured:false,distinct_securities:3,expected_security_days:80,
  price_responses:3,observed_trading_days:78,not_returned_days:1,explicit_nontrading_days:1,registry_source_rows:4,basis_responses:40,endpoint_compared_trading:2,
  new_listings:[{code:'688001',listed_on:'2026-09-17',ended_on:null,observed_name:'新上市样本',board:'8'}],
  ended_listings:[{code:'600001',listed_on:'2020-01-01',ended_on:'2026-10-19',observed_name:'退出样本',board:'1'}],
  days:[{date:'2026-09-08',listed_members:2,observed_trading:0,not_returned:['600001.SH'],explicit_nontrading:['600002.SH'],unclosed_observations_included:false}],
  first_price_observed_at:'2026-11-05T05:00:00+00:00',source_fetched_at:'2026-11-05T05:30:00+00:00',basis_fetched_at:'2026-11-05T04:00:00+00:00',
  materialized_at:'2026-11-05T05:35:00+00:00',note:'范围已核对；缺日与历史ST仍待补。'}
function open(){fireEvent.click(screen.getByText('沪市历史来源 · 范围与价格原件核对'))}

describe('SSEHistorySources',()=>{
  afterEach(cleanup)
  it('keeps original quotes and historical analysis readiness separate',()=>{
    render(<SSEHistorySources data={data}/>);open()
    expect(screen.getByText(/目标范围共 80 股票日；有成交价格记录 78 条，源端未返回 1 股票日，源端明确无成交 1 股票日/)).toBeVisible()
    expect(screen.getByText(/历史ST成员与价格路径仍未发布/)).toBeVisible()
    expect(screen.getByText(/效果尚未测量/)).toBeVisible()
  })
  it('retains exited securities and separates absent prices from explicit nontrading rows',()=>{
    render(<SSEHistorySources data={data}/>);open();fireEvent.click(screen.getByText('查看逐日价格输入与缺日代码'))
    expect(screen.getByText('600001')).toBeVisible();expect(screen.getByText('2026-10-19')).toBeVisible()
    expect(screen.getByText('600001.SH')).toBeVisible();expect(screen.getByText('600002.SH')).toBeVisible()
    expect(screen.getByRole('columnheader',{name:'源端未返回代码'})).toBeVisible()
    expect(screen.getByRole('columnheader',{name:'明确无成交代码'})).toBeVisible()
  })
  it('provides keyboard access to both tables and the primary sources',()=>{
    render(<SSEHistorySources data={data}/>);open();fireEvent.click(screen.getByText('查看逐日价格输入与缺日代码'))
    expect(screen.getByRole('region',{name:'可滚动的沪市区间上市变化表'})).toHaveAttribute('tabindex','0')
    expect(screen.getByRole('region',{name:'可滚动的沪市每日价格输入表'})).toHaveAttribute('tabindex','0')
    expect(screen.getByRole('link',{name:'每日挂牌统计 ↗'})).toHaveAttribute('href','https://www.sse.com.cn/market/stockdata/overview/day/')
  })
  it('preserves the actual first observation instead of claiming historical availability',()=>{
    render(<SSEHistorySources data={data}/>);open()
    expect(screen.getByText(/2026\/11\/5 13:00:00 至 2026\/11\/5 13:30:00/)).toBeVisible()
    expect(screen.getByText(/事后取得的历史输入/)).toBeVisible()
  })
  it('withholds old counts and tables on failed source validation',()=>{
    render(<SSEHistorySources data={{...data,availability:'invalid'}}/>);open()
    expect(screen.getByText(/旧数量不作为当前覆盖/)).toBeVisible()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.queryByText(/目标范围共 80 股票日/)).not.toBeInTheDocument()
  })
})
