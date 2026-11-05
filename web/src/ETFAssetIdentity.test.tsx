import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {ETFAssetIdentity} from './ETFAssetIdentity'
import type {ETFAssetIdentity as Identity} from './types'

const point={date:'2026-11-04',source_url:'https://source.example/nav',response_sha256:'source-proof',observed_at:'2026-11-04T21:06:40Z'}
const base:Identity={version:'etf_published_asset_identity_v1',availability:'arithmetic_compared',disclosed_points:1,compared_points:1,declared_points:1,reviewed_code:'510310.SH',
  matches_market_target:true,source_independence_verified:false,whole_fund_daily_scope_verified:false,off_exchange_shares:null,full_fund_daily_shares:null,estimated_net_subscription_yuan:null,historical_PIT:false,
  date:'2026-11-04',published_shares:'25872044000.0',unit_nav:'4.0609',shares_times_unit_nav_yuan:'105063783479.60000',difference_yuan:'0.00000',relation:'equal_as_published',
  asset:{availability:'observed',code:'510310.SH',asset_asof:'2026-11-04',asset_yuan:'105063783479.60',raw_amount_text:'105,063,783,479.60',scope:'site_states_whole_fund_net_assets',asset_field:'baseinfoAsset',asset_rounding_rule_verified:false,
    source_url:'https://www.efunds.com.cn/fund/510310.shtml',response_sha256:'asset-proof',observed_at:point.observed_at},
  NAV_source:point,share_source:{...point,source_url:'https://query.sse.com.cn/actual-request'},comparison_digest:'identity-proof',note:'仅归档单点，不作资金流或全基金日份额证明。'}

describe('ETFAssetIdentity',()=>{
  afterEach(cleanup)
  const open=()=>fireEvent.click(screen.getByText('查看这一个披露时点的数值与来源'))
  it('labels an arithmetic equality as one point with unknown independence and off-exchange shares',()=>{
    render(<ETFAssetIdentity data={base}/>);
    expect(screen.getByText(/2026-11-04.*算术上相等.*尚未核实来源独立性/)).toBeVisible()
    expect(screen.getByText(/不能由相等推定场外份额为零或全基金日份额已验收/)).toBeVisible()
    expect(screen.getByText('查看这一个披露时点的数值与来源').closest('details')).not.toHaveAttribute('open')
  })
  it('preserves exact source numbers, units and dates with all three source links',()=>{
    render(<ETFAssetIdentity data={base}/>);open()
    const table=screen.getByRole('region',{name:'可滚动的资产公布值对照表'})
    expect(within(table).getByText('105,063,783,479.60 元')).toBeVisible()
    expect(within(table).getByText('25,872,044,000.0 份')).toBeVisible()
    expect(within(table).getByText('4.0609 元/份')).toBeVisible()
    expect(screen.getByRole('link',{name:'基金公司资产披露 ↗'})).toHaveAttribute('href',base.asset!.source_url+'#baseinfoAsset')
    expect(screen.getByRole('link',{name:'交易所原响应 ↗'})).toHaveAttribute('href',base.share_source!.source_url)
    expect(screen.getByRole('link',{name:'单位净值原响应 ↗'})).toHaveAttribute('href',point.source_url)
    expect(screen.getByText(/105,063,783,479.60000 元（算术乘积）/)).toBeVisible()
    expect(screen.getByText(/0.00000 元。这是公布值差，不是资金流/)).toBeVisible()
    fireEvent.click(screen.getByText('查看三个原件的对应标识'));expect(screen.getByText('asset-proof')).toBeVisible()
  })
  it.each([undefined,{...base,availability:'invalid'},{...base,availability:'asset_only'}, {...base,NAV_source:{...point,date:'2026-11-05'}}])('withholds all stale computed numbers if the same-day comparison is unavailable',data=>{
    render(<ETFAssetIdentity data={data}/>);
    expect(screen.getByText(/同日对照当前不齐，不展示旧计算结果/)).toBeVisible()
    expect(screen.queryByText(/105,063,783/)).not.toBeInTheDocument();expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
  it('labels older points explicitly and does not turn a nonzero difference into a flow',()=>{
    render(<ETFAssetIdentity data={{...base,matches_market_target:false,relation:'different_as_published',difference_yuan:'-0.01000'}}/>);open()
    expect(screen.getByText(/算术上不同/)).toBeVisible()
    expect(screen.getByText(/不作为目标日覆盖/)).toBeVisible()
    expect(screen.getByText(/-0.01000 元。这是公布值差，不是资金流/)).toBeVisible()
    expect(screen.getByText(/季报中的场外份额仍保留其原报告日期/)).toBeVisible()
  })
})
