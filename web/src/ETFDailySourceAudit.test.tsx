import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {ETFDailySourceAudit} from './ETFDailySourceAudit'
import type {ETFDailyRawReconciliation as Audit} from './types'

const point={code:'510310.SH',date:'2026-09-30',raw_text:'1198774.4',source_value:'1198774.4',ten_thousand_shares:'1198774.4',shares:'11987744000.0',fractional_digits:1,
  source_url:'https://query.sse.com.cn/commonQuery.do?sqlId=ETF_SHARES',response_sha256:'sha-proof',observed_at:'2026-11-04T20:10:00Z'}
const base:Audit={version:'etf_daily_raw_reconciliation_v1',availability:'source_reconciled',source_response_count:61,snapshot_digest:'snapshot-proof',start:'2026-08-04',through:'2026-11-04',
  share_observations:305,nav_observations:0,exact_source_projection_verified:true,whole_fund_daily_scope_verified:false,source_rounding_rule_verified:false,
  share_precision_verified:false,final_revision_verified:false,corporate_actions_checked:false,estimated_net_subscription_yuan:null,note:'原文本小数位不证明舍入方式。',
  funds:[{code:'510310.SH',share_field:'TOT_VOL',share_unit:'ten_thousand_shares',fractional_digit_counts:{'1':61},records:[point]}]}
const szse:Audit={...base,source_response_count:15,share_observations:183,nav_observations:30,
  funds:[{code:'159919.SZ',share_field:'current_size',share_unit:'ten_thousand_shares',fractional_digit_counts:{'2':61},records:[{...point,code:'159919.SZ',raw_text:'1,405,911.66',shares:'14059116600.00',fractional_digits:2}]}]}

describe('ETFDailySourceAudit',()=>{
  afterEach(cleanup)
  it('separates matching raw projections from unknown scope, rounding rules, revisions and cash',()=>{
    render(<ETFDailySourceAudit sse={base} szse={szse} target="2026-11-04"/>);
    expect(screen.getByText(/沪市：已逐条核对 305 条份额、0 条实际返回净值，绑定 61 个响应引用/)).toBeVisible()
    expect(screen.getByText(/深市：已逐条核对 183 条份额、30 条实际返回净值/)).toBeVisible()
    expect(screen.getByText(/源端舍入规则、整个基金的日份额范围、最终修订和全窗事件仍待确认，净申赎金额继续未发布/)).toBeVisible()
    expect(screen.getByText('查看原始小数文本与逐日换算').closest('details')).not.toHaveAttribute('open')
  })
  it('preserves the original one-decimal text and exact string conversion without a float',()=>{
    render(<ETFDailySourceAudit sse={base} target="2026-11-04"/>);fireEvent.click(screen.getByText('查看原始小数文本与逐日换算'))
    expect(screen.getByText('1198774.4')).toBeVisible()
    expect(screen.getByText('11,987,744,000.0')).toBeVisible()
    expect(screen.getByText(/1位小数 61 条.*不等于已确认的字段精度或误差上界/)).toBeVisible()
    expect(screen.getByRole('link',{name:'交易所原响应 ↗'})).toHaveAttribute('href',point.source_url)
    expect(screen.getByRole('region',{name:'可滚动的ETF原始日份额表'})).toHaveAttribute('tabindex','0')
    fireEvent.click(screen.getByText('原响应摘要'));expect(screen.getByText('sha-proof')).toBeVisible()
  })
  it('selects another fund while preserving comma formatting and raw trailing zeros independently',()=>{
    const changed={...szse,funds:[{...szse.funds[0],records:[{...szse.funds[0].records[0],raw_text:'1,405,911.6600',shares:'14059116600.0000',fractional_digits:4}]}]}
    render(<ETFDailySourceAudit sse={base} szse={changed} target="2026-11-04"/>);fireEvent.click(screen.getByText('查看原始小数文本与逐日换算'))
    fireEvent.change(screen.getByLabelText('ETF原响应基金筛选'),{target:{value:'SZSE:159919.SZ'}})
    const table=screen.getByRole('region',{name:'可滚动的ETF原始日份额表'})
    expect(within(table).getByText('1,405,911.6600')).toBeVisible()
    expect(within(table).getByText('14,059,116,600.0000')).toBeVisible()
    expect(within(table).queryByText('1198774.4')).not.toBeInTheDocument()
  })
  it('labels absent sources as unverified instead of retaining stale counts',()=>{
    render(<ETFDailySourceAudit sse={{...base,availability:'invalid'}} target={null}/>);
    expect(screen.getAllByText(/当前未通过原响应核对，不沿用旧数量/)).toHaveLength(2)
    expect(screen.queryByText(/305 条份额/)).not.toBeInTheDocument()
    expect(screen.queryByRole('table',{hidden:true})).not.toBeInTheDocument()
  })
  it('rejects an unverified source-projection flag even if its status is stale',()=>{
    render(<ETFDailySourceAudit sse={{...base,exact_source_projection_verified:false}} szse={szse} target="2026-11-04"/>);
    fireEvent.click(screen.getByText('查看原始小数文本与逐日换算'))
    expect(screen.getByLabelText('ETF原响应基金筛选')).toHaveValue('SZSE:159919.SZ')
    expect(screen.queryByRole('option',{name:'沪市 · 510310.SH'})).not.toBeInTheDocument()
  })
  it('retains a lost source selection after refresh and withholds its old records',()=>{
    const {rerender}=render(<ETFDailySourceAudit sse={base} szse={szse} target="2026-11-04"/>);
    fireEvent.click(screen.getByText('查看原始小数文本与逐日换算'))
    rerender(<ETFDailySourceAudit szse={szse} target="2026-11-04"/>);
    expect(screen.getByText(/当前选择没有通过原响应核对的日表/)).toBeVisible()
    expect(screen.queryByText('1198774.4')).not.toBeInTheDocument()
    expect(screen.getByRole('option',{name:'SSE:510310.SH（当前未取得）'})).toBeDisabled()
  })
  it('does not turn an earlier matching source window into target-date coverage',()=>{
    render(<ETFDailySourceAudit sse={base} target="2026-11-05"/>);fireEvent.click(screen.getByText('查看原始小数文本与逐日换算'))
    expect(screen.getByText('当前市场目标 2026-11-05 与本核对终点 2026-11-04 不同，不合算目标日覆盖。')).toBeVisible()
  })
  it('keeps a missing product path empty rather than inventing zero-valued records',()=>{
    const data={...base,funds:[{...base.funds[0],records:[],fractional_digit_counts:{}}]}
    render(<ETFDailySourceAudit sse={data} target="2026-11-04"/>);fireEvent.click(screen.getByText('查看原始小数文本与逐日换算'))
    expect(screen.getByText('该基金在此窗没有通过核对的日记录，缺失不填零。')).toBeVisible()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
  it('scrolls a focused region in both directions without also scrolling the page',()=>{
    render(<ETFDailySourceAudit sse={base} target="2026-11-04"/>);fireEvent.click(screen.getByText('查看原始小数文本与逐日换算'))
    const region=screen.getByRole('region',{name:'可滚动的ETF原始日份额表'});Object.defineProperty(region,'clientHeight',{value:544});region.scrollBy=vi.fn()
    expect(fireEvent.keyDown(region,{key:'ArrowRight'})).toBe(false)
    expect(region.scrollBy).toHaveBeenLastCalledWith({left:40,top:0,behavior:'auto'})
    expect(fireEvent.keyDown(region,{key:'PageDown'})).toBe(false)
    expect(region.scrollBy).toHaveBeenLastCalledWith({left:0,top:504,behavior:'auto'})
  })
  it('preserves native keys for links and browser shortcuts inside the scroll region',()=>{
    render(<ETFDailySourceAudit sse={base} target="2026-11-04"/>);fireEvent.click(screen.getByText('查看原始小数文本与逐日换算'))
    const region=screen.getByRole('region',{name:'可滚动的ETF原始日份额表'});region.scrollBy=vi.fn()
    expect(fireEvent.keyDown(screen.getByRole('link',{name:'交易所原响应 ↗'}),{key:'ArrowRight'})).toBe(true)
    expect(fireEvent.keyDown(region,{key:'ArrowLeft',altKey:true})).toBe(true)
    expect(fireEvent.keyDown(region,{key:'Tab'})).toBe(true)
    expect(region.scrollBy).not.toHaveBeenCalled()
  })
})
