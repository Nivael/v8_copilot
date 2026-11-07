import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import type {ExchangeRiskMembership} from './types'
import {ExchangeRiskLists} from './ExchangeRiskLists'

const data:ExchangeRiskMembership={availability:'observed',observed_on:'2026-11-05',started_at:'2026-11-05T03:49:06+00:00',completed_at:'2026-11-05T03:49:15+00:00',
  is_today_observation:true,historical_membership_ready:false,common_source_as_of:null,risk_warning_a_shares:195,delisting_a_shares:1,excluded_b_shares:3,
  note:'深市表标明数据日，沪市表未声明数据日。不回填历史成员、收益或近期对照。',groups:[
    {group:'sse_main_risk',venue:'SSE',board:'main',kind:'risk_warning',source_url:'https://www.sse.com.cn/disclosure/listedinfo/riskplate/',source_as_of:null,source_rows:69,pages_read:1,a_shares:68,b_shares:1},
    {group:'szse_delisting',venue:'SZSE',board:'main_and_gem',kind:'delisting',source_url:'http://www.szse.cn/disclosure/listed/warn/index.html',source_as_of:'2026-11-05',source_rows:1,pages_read:1,a_shares:1,b_shares:0}],
  rows:[{ts_code:'002731.SZ',name:'萃华退',share_class:'A',kind:'delisting',venue:'SZSE',group:'szse_delisting'},
        {ts_code:'900915.SH',name:'ST中路B',share_class:'B',kind:'risk_warning',venue:'SSE',group:'sse_main_risk'}]}

function open(){fireEvent.click(screen.getByText('交易所风险警示与退市整理名单 · 本次读取'))}

describe('ExchangeRiskLists',()=>{
  afterEach(cleanup)
  it('keeps warning A shares, delisting A shares and B shares separate',()=>{
    render(<ExchangeRiskLists data={data}/>);open()
    expect(screen.getByText(/风险警示A股 195 只，退市整理A股 1 只；另列B股 3 只/)).toBeVisible()
    expect(screen.getByText(/退市整理A股：002731.SZ 萃华退/)).toBeVisible()
    expect(screen.getByText(/另列B股：900915.SH ST中路B/)).toBeVisible()
    expect(screen.getByText(/分类取自交易所名单，不由简称前缀推定/)).toBeVisible()
  })
  it('distinguishes observation date, declared source date and missing historical membership',()=>{
    render(<ExchangeRiskLists data={data} quoteDate="2026-11-04"/>);open()
    expect(screen.getByText('来源未声明数据日')).toBeVisible()
    expect(screen.getByRole('cell',{name:'2026-11-05'})).toBeVisible()
    expect(screen.getByText(/不能直接合并计算历史ST收益/)).toBeVisible()
    expect(screen.getByText(/上方收盘截面是 2026-11-04，本名单读取于 2026-11-05/)).toBeVisible()
    expect(screen.getByRole('link',{name:'深市主板与创业板 ↗'})).toHaveAttribute('href','http://www.szse.cn/disclosure/listed/warn/index.html')
  })
  it('explains separate selected-tab reads and preserves keyboard table access',()=>{
    render(<ExchangeRiskLists data={data}/>);open()
    expect(screen.getByText(/未选中的空页不当作零记录/)).toBeVisible()
    expect(screen.getByRole('region',{name:'可滚动的风险名单分类表'})).toHaveAttribute('tabindex','0')
  })
  it('marks an older observation as requiring another collection',()=>{
    render(<ExchangeRiskLists data={{...data,is_today_observation:false}}/>);open()
    expect(screen.getByText('这是上次读取的名单，当前名单需要重新采集。')).toBeVisible()
  })
  it('hides old counts when source validation fails',()=>{
    render(<ExchangeRiskLists data={{...data,availability:'invalid'}}/>);open()
    expect(screen.getByText(/未知不记为零/)).toBeVisible()
    expect(screen.queryByText(/风险警示A股 195 只/)).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})
