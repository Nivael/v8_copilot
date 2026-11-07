import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {ETFUnitNAVAudit} from './ETFUnitNAVAudit'
import type {ETFUnitNAVReconciliation as Audit} from './types'

const point={date:'2026-11-04',raw_text:'4.060900',source_value:'4.060900',fractional_digits:6,source_url:'https://cdn.efunds.com.cn/market/2.0/510310_1y.js',
  request_method:'GET',request_params:{},response_sha256:'source-proof',observed_at:'2026-11-04T21:06:40Z'}
const base:Audit={version:'issuer_nav_raw_reconciliation_v1',availability:'source_reconciled',source_response_count:34,snapshot_digest:'nav-snapshot',start:'2026-08-04',through:'2026-11-04',nav_observations:488,
  exact_source_projection_verified:true,historical_PIT:false,corporate_actions_checked:false,whole_fund_daily_scope_verified:false,share_precision_verified:false,final_revision_verified:false,estimated_net_subscription_yuan:null,
  note:'原响应匹配不代表全基金份额范围或全窗事件验收。',funds:[{code:'510310.SH',provider:'efunds',source_field:'EnumSourceTypeNetValue',source_url:'https://www.efunds.com.cn/fund/510310.shtml',
    unit:'CNY_per_share',source_response_count:3,fractional_digit_counts:{6:1},source_responses:[{role:'unit_NAV_schema',url:'https://www.efunds.com.cn/schema.js',method:'GET',params:{},response_sha256:'schema-proof',observed_at:point.observed_at,bytes:100}],records:[point]},
    {code:'510330.SH',provider:'chinaamc',source_field:'单位净值',source_url:'https://www.chinaamc.com/query',unit:'CNY_per_share',source_response_count:4,fractional_digit_counts:{4:1},source_responses:[],records:[{...point,raw_text:'4.3583',request_method:'POST',request_params:{fundcode:'510330',pageIndex:1},source_url:'https://www.chinaamc.com/api'}]}]}

describe('ETFUnitNAVAudit',()=>{
  afterEach(cleanup)
  function open(){fireEvent.click(screen.getByText('查看基金公司原始单位净值'))}
  it('separates source-matching unit NAVs from the remaining cash and share verification gaps',()=>{
    render(<ETFUnitNAVAudit data={base} target="2026-11-04"/>);
    expect(screen.getByText(/488 条单位净值.*34 个原响应引用/)).toBeVisible()
    expect(screen.getByText(/累计净值、参考净值和基金资产净值均不作为/)).toBeVisible()
    expect(screen.getByText(/净申赎金额继续未发布/)).toBeVisible()
    expect(screen.getByText('查看基金公司原始单位净值').closest('details')).not.toHaveAttribute('open')
  })
  it('preserves exact source text and actual data/schema links',()=>{
    render(<ETFUnitNAVAudit data={base} target="2026-11-04"/>);open()
    expect(screen.getByText('4.060900')).toBeVisible()
    expect(screen.getByRole('link',{name:'原响应入口 ↗'})).toHaveAttribute('href',point.source_url)
    fireEvent.click(screen.getByText('查看该基金全部来源依据（1项）'))
    expect(screen.getByRole('link',{name:'原链接 1 ↗'})).toHaveAttribute('href','https://www.efunds.com.cn/schema.js')
    fireEvent.click(screen.getByText('查看本条来源对应'));expect(screen.getByText('source-proof')).toBeVisible()
  })
  it('opens a POST source query page without implying a GET link replays the form submission',()=>{
    render(<ETFUnitNAVAudit data={base} target="2026-11-04"/>);open()
    fireEvent.change(screen.getByLabelText('单位净值原响应基金筛选'),{target:{value:'510330.SH'}})
    expect(screen.getByRole('link',{name:'基金公司查询页 ↗'})).toHaveAttribute('href','https://www.chinaamc.com/query')
    expect(screen.getByText('4.3583')).toBeVisible();expect(screen.queryByText('4.060900')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('查看本条来源对应'));expect(screen.getByText(/不重放提交/)).toBeVisible()
  })
  it.each([undefined,{...base,availability:'invalid'},{...base,exact_source_projection_verified:false}])('withholds stale source numbers and records when source verification is unavailable',data=>{
    render(<ETFUnitNAVAudit data={data} target={null}/>);
    expect(screen.getByText(/当前未通过原响应核对，不沿用旧数量或日记录/)).toBeVisible()
    expect(screen.queryByText(/488 条/)).not.toBeInTheDocument();expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
  it('retains a lost selection after refresh and labels a different window without upgrading target coverage',()=>{
    const {rerender}=render(<ETFUnitNAVAudit data={base} target="2026-11-05"/>);open()
    expect(screen.getByText(/不算作目标日覆盖/)).toBeVisible()
    rerender(<ETFUnitNAVAudit data={{...base,funds:[base.funds[1]]}} target="2026-11-05"/>);
    expect(screen.getByText(/当前选择没有已核对的单位净值/)).toBeVisible();expect(screen.queryByText('4.060900')).not.toBeInTheDocument()
    expect(screen.getByRole('option',{name:'510310.SH（当前未取得）'})).toBeDisabled()
  })
  it('keeps empty records missing rather than filling zeros',()=>{
    render(<ETFUnitNAVAudit data={{...base,funds:[{...base.funds[0],records:[]}]}} target="2026-11-04"/>);open()
    expect(screen.getByText('本基金无已核对日记录，缺失不填零。')).toBeVisible();expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
  it('scrolls a focused table while preserving link and browser keys',()=>{
    render(<ETFUnitNAVAudit data={base} target="2026-11-04"/>);open()
    const region=screen.getByRole('region',{name:'可滚动的原始单位净值表'});region.scrollBy=vi.fn()
    expect(fireEvent.keyDown(region,{key:'ArrowRight'})).toBe(false);expect(region.scrollBy).toHaveBeenLastCalledWith({left:40,top:0,behavior:'auto'})
    expect(fireEvent.keyDown(region,{key:'PageDown'})).toBe(false);expect(region.scrollBy).toHaveBeenLastCalledWith({left:0,top:40,behavior:'auto'})
    vi.mocked(region.scrollBy).mockClear()
    expect(fireEvent.keyDown(within(region).getByRole('link',{name:'原响应入口 ↗'}),{key:'ArrowLeft'})).toBe(true)
    expect(fireEvent.keyDown(region,{key:'ArrowLeft',altKey:true})).toBe(true);expect(region.scrollBy).not.toHaveBeenCalled()
  })
})
