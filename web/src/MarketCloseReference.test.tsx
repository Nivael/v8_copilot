import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {CloseDistanceLabel,MarketCloseReference} from './MarketCloseReference'
import type {MarketCloseReference as Reference,MarketCloseDistance} from './types'

const reference:Reference={version:'market_close_distance_v1',availability:'calendar_computed',observed_at:'2026-11-05T08:00:00Z',timezone:'Asia/Shanghai',reference_time:'15:00',latest_scheduled_close:'2026-11-05',calendar_version:'calendar-2026',calendar_source:'https://www.sse.com.cn/holidays',hours_source:'https://www.sse.com.cn/hours',calendar_rule_digest:'calendar-hash',schedule_only:true,provider_deadline_verified:false,automatic_update_observed:false}
const distance:MarketCloseDistance={availability:'compared',minimum_sessions:1,maximum_sessions:1,series_compared:3,latest_scheduled_close:'2026-11-05'}

describe('calendar reference is not a provider deadline or a validity label',()=>{
  afterEach(cleanup)
  it('shows the calendar endpoint separately from a snapshot target and exposes the actual sources',()=>{
    render(<MarketCloseReference data={reference} distance={distance}/>);
    expect(screen.getByText(/最近计划收盘日为 2026-11-05，15:00/)).toBeVisible()
    expect(screen.getByText('当前快照目标距参照 1 个收盘日')).toBeVisible()
    expect(screen.getByText(/不判断源端披露超时、期间数据完整、最终修订或自动更新是否运行/)).toBeVisible()
    fireEvent.click(screen.getByText('日历参照依据'))
    expect(screen.getByRole('link',{name:'交易所2026休市安排 ↗'})).toHaveAttribute('href',reference.calendar_source)
    expect(screen.getByText(/盘中不把当天算作已收盘/)).toBeVisible()
  })
  it('zero date distance never claims completeness, final revision or automation',()=>{
    render(<MarketCloseReference data={reference} distance={{...distance,minimum_sessions:0,maximum_sessions:0}}/>);
    expect(screen.getByText('当前快照目标距参照 0 个收盘日')).toBeVisible()
    expect(screen.getByText(/相距0个收盘日也不代表这些检查已通过/)).toBeVisible()
  })
  it('keeps different series endpoints as a range',()=>{
    render(<CloseDistanceLabel data={{...distance,maximum_sessions:2}}/>);
    expect(screen.getByText('已取得数据的末日距参照 1～2 个收盘日')).toBeVisible()
  })
  it.each([{...distance,availability:'unavailable',minimum_sessions:null,maximum_sessions:null},{...distance,minimum_sessions:-1},{...distance,maximum_sessions:.5},{...distance,series_compared:0}])('never turns an unknown or inconsistent date comparison into zero',data=>{
    render(<CloseDistanceLabel data={data}/>);
    expect(screen.getByText(/收盘日差暂无法核对/)).toBeVisible()
  })
  it('explains a data date ahead of the clock reference without marking the source corrupt',()=>{
    render(<CloseDistanceLabel data={{...distance,availability:'unavailable',reason:'data_after_reference'}}/>);
    expect(screen.getByText('数据日期晚于日历参照，未计算日差')).toBeVisible()
  })
  it('withholds an old reference and target distance when the calendar is unsupported',()=>{
    render(<MarketCloseReference data={{...reference,availability:'unavailable',latest_scheduled_close:null}} distance={distance}/>);
    expect(screen.getByText(/交易日历参照暂不可用/)).toBeVisible()
    expect(screen.queryByText(/当前快照目标距参照/)).not.toBeInTheDocument()
  })
})
