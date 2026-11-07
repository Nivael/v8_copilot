import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {ETFFundScopeRules} from './ETFFundScopeRules'
import type {ETFFundScopeRules as Rules} from './types'

const url='https://www.sse.com.cn/disclosure/fund/announcement/c/new/2026-07-31/510310_20260731_RPQ5.pdf'
const data:Rules={version:'etf_fund_scope_business_roles_v1',availability:'scoped_rules_reviewed',review_scope:'one_prospectus_version_business_roles_only',reviewed_documents:1,reviewed_passages:13,proof_pages:[1,4,9,32,34,35,38,39,48,70,74,75],
  document:{code:'510310.SH',published_on:'2026-07-31',title:'更新的招募说明书',url,response_url:url,document_id:'doc',catalog_digest:'catalog',raw_sha256:'pdf',text_sha256:'text',bytes:1200000,page_count:127,observed_at:'2026-11-05T10:57:45Z'},
  cutoffs:{general_content:'2026-06-16',financial:'2026-06-30',NAV_performance:'2026-06-30',personnel:'2026-07-30'},
  registrars:{exchange:'中国证券登记结算有限责任公司',off_exchange:'易方达基金管理有限公司',proof_pages:[9,48]},
  transfer:{declared_direction:'off_exchange_to_exchange',conditional:true,requires_published_rules:true,reverse_requires_separate_announcement:true,actual_window_transfers:null,daily_adjustment_applied:false,proof_pages:[32,48]},
  rounding_rules:[{target:'iopv',unit:'CNY_per_share',fractional_digits:4,method:'half_up',proof_page:32,applies_to_exchange_daily_share_field:false},
    {target:'off_exchange_subscribed_shares',unit:'fund_share',fractional_digits:0,method:'half_up',proof_page:38,applies_to_exchange_daily_share_field:false},
    {target:'off_exchange_subscription_fee',unit:'CNY',fractional_digits:2,method:'half_up',proof_page:38,applies_to_exchange_daily_share_field:false},
    {target:'off_exchange_redemption_payment_and_fee',unit:'CNY',fractional_digits:2,method:'half_up',proof_page:39,applies_to_exchange_daily_share_field:false},
    {target:'unit_NAV',unit:'CNY_per_share',fractional_digits:4,method:'half_up',proof_page:70,applies_to_exchange_daily_share_field:false},
    {target:'distribution_per_share',unit:'CNY_per_share',fractional_digits:3,method:'truncate',proof_page:75,applies_to_exchange_daily_share_field:false}],
  distribution_mode_as_stated:'cash_both_registers',distribution_mode_proof_page:74,current_business_availability_verified:false,daily_exchange_share_rounding_rule:null,
  whole_fund_daily_scope_verified:false,share_precision_verified:false,final_revision_verified:false,corporate_actions_checked:false,full_document_semantics_checked:false,all_window_share_events_verified:false,historical_PIT:false,effect_measured:false,estimated_net_subscription_yuan:null,
  note:'与原105项选中文档范围分开计数。',content_digest:'hash-proof',materialized_at:'2026-11-05T11:00:00Z'}

describe('ETFFundScopeRules',()=>{
  afterEach(cleanup)
  it('requires all four estimation conditions and explains conditional register transfer without assuming actual activity',()=>{
    render(<ETFFundScopeRules data={data}/>);
    expect(screen.getByText(/全窗份额事件、全基金日份额范围、源端精度和最终修订/)).toBeVisible()
    expect(screen.getByText(/本窗实际办理量仍未知，不据此校正任何一天的数据/)).toBeVisible()
    expect(screen.getByRole('link',{name:'登记与条件 · 原PDF第48页 ↗'})).toHaveAttribute('href',url+'#page=48')
    expect(screen.getByText('查看510310的登记、对价和舍入对象').closest('details')).not.toHaveAttribute('open')
  })
  it('keeps six quantity and money precision objects distinct from the exchange daily-share field',()=>{
    render(<ETFFundScopeRules data={data}/>);fireEvent.click(screen.getByText('查看510310的登记、对价和舍入对象'))
    const table=screen.getByRole('region',{name:'可滚动的ETF舍入对象表'})
    expect(within(table).getAllByRole('row')).toHaveLength(7)
    expect(within(table).getByText('场外申购确认份额').closest('tr')).toHaveTextContent('份；保留整数；四舍五入')
    expect(within(table).getByText('每份分红金额').closest('tr')).toHaveTextContent('元/份；保留3位小数；下一位舍去')
    expect(within(table).getByText('基金单位净值').closest('tr')).toHaveTextContent('元/份；保留4位小数；四舍五入')
    expect(screen.getByText(/均不作为交易所日份额字段的舍入规则/)).toBeVisible()
    expect(within(table).getByRole('link',{name:'原PDF第70页 ↗'})).toHaveAttribute('href',url+'#page=70')
  })
  it('preserves the general, financial, NAV and personnel cutoffs instead of replacing them with publication',()=>{
    render(<ETFFundScopeRules data={data}/>);fireEvent.click(screen.getByText('查看510310的登记、对价和舍入对象'))
    expect(screen.getByText(/一般内容 2026-06-16；财务数据 2026-06-30；净值表现 2026-06-30；主要人员 2026-07-30/)).toBeVisible()
    expect(screen.getByText(/仅核对 2026-07-31 发布的这一份说明书，13 个指定段落、原PDF 127 页/)).toBeVisible()
    expect(screen.getByText(/原件取得 2026\/11\/5 18:57:45/)).toBeVisible()
  })
  it('separates consideration routes and cash-distribution terms from current cash flows and events',()=>{
    render(<ETFFundScopeRules data={data}/>);fireEvent.click(screen.getByText('查看510310的登记、对价和舍入对象'))
    expect(screen.getByText(/场内申购、赎回均按份额申请.*场外按金额申购、份额赎回，对价为现金/)).toBeVisible()
    expect(screen.getByText(/这是分配方式条款，不证明观察窗内实际发生了分红/)).toBeVisible()
    expect(screen.getByText(/与原105项选中文档范围分开计数/)).toBeVisible()
  })
  it.each(['invalid','missing','reload_required'])('hides stale primary facts when %s',availability=>{
    render(<ETFFundScopeRules data={{...data,availability}}/>);
    expect(screen.getByText('510310的原文业务条款当前不可用，不展示上次的具体解释或舍入规则。')).toBeVisible()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.queryByRole('table',{hidden:true})).not.toBeInTheDocument()
  })
  it('does not bind a different fund or an incomplete role table to the 510310 explanation',()=>{
    const {rerender}=render(<ETFFundScopeRules data={{...data,document:{...data.document!,code:'510300.SH'}}}/>);
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    rerender(<ETFFundScopeRules data={{...data,rounding_rules:data.rounding_rules!.slice(1)}}/>);
    expect(screen.queryByRole('table',{hidden:true})).not.toBeInTheDocument()
  })
})
