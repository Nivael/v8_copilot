import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {ETFProspectusRules} from './ETFProspectusRules'
import type {ETFProspectusRules as Rules} from './types'

const common={availability:'observed',document_observed_at:'2026-11-04T22:00:00Z',pdf_url:'https://www.sse.com.cn/rules.pdf',
  financial_data_asof:'2026-06-30',cutoff_exception:null,financial_audit_status:'report_states_unaudited',source_page_count:119,reviewed_pages:[3,31,32,35,43,65],
  full_document_semantics_checked:false as const,corporate_actions_checked:false as const,market_window_correction_applied:false as const,
  consideration_components:['组合证券','现金替代','现金差额','其他对价'],cash_is_only_consideration:false as const,distribution_mode_as_stated:'cash',
  distribution_condition_as_stated:'符合条件时可以分红。',actual_distributions_in_market_window:null,current_cash_flow_yuan:null}
const unit={quantity_scope:'fund_shares_per_business_unit',effective_at_market_target:'not_verified'}
const fixture:Rules={version:'etf_prospectus_rule_review_v1',availability:'partial',reviewed_versions:2,selected_prospectus_versions:2,
  corporate_actions_checked:false,all_window_documents_reconciled:false,note:'规则、假设示例和历史复述不当作当前事件。',versions:[
    {...common,code:'510300.SH',publication_date:'2026-08-13',content_asof:'2026-07-31',max_annual_distributions_as_stated:4,
      minimum_units:[{...unit,route:'ordinary_create_redeem',label:'申购 / 赎回',stated_unit_shares:'900000',table_page:35},
                     {...unit,route:'collection_create',label:'集合申购',stated_unit_shares:'900000',table_page:43}],
      historical_restatement:{classification:'later_prospectus_restatement',event_on:'2012-05-11',registered_on:'2012-05-14',stated_ratio:'0.37094933',rounding_in_this_version:'nearest_whole_share',pages:[32],not_historical_point_in_time_evidence:true},
      illustration:{classification:'hypothetical_illustration',before_shares:'5000',stated_ratio:'0.26671819',after_shares:'1334',pages:[31,32],not_a_verified_event:true}},
    {...common,code:'159922.SZ',publication_date:'2026-08-29',content_asof:'2026-07-29',cutoff_exception:'特别事项注明除外',source_page_count:151,
      reviewed_pages:[3,50,53,61,64,75,103],max_annual_distributions_as_stated:12,
      minimum_units:[{...unit,route:'physical_create_redeem',label:'实物申购 / 赎回',stated_unit_shares:'1000000',table_page:53},
                     {...unit,route:'sz_physical_sh_cash_substitute',label:'深市股票实物、沪市股票现金替代申赎',stated_unit_shares:'1000000',table_page:64},
                     {...unit,route:'collection_create',label:'集合申购',stated_unit_shares:'1000000',table_page:75}],
      historical_restatement:{classification:'later_prospectus_restatement',event_on:'2013-03-05',registered_on:'2013-03-06',stated_ratio:'0.28038605',rounding_in_this_version:'floor_to_whole_share',pages:[50],not_historical_point_in_time_evidence:true},illustration:null},
  ]}

function open(){fireEvent.click(screen.getByText('查看已核对条款（2份版本）'))}

describe('ETFProspectusRules',()=>{
  afterEach(cleanup)
  it('separates publication, content, financial and observation dates with exact primary-page links',()=>{
    render(<ETFProspectusRules data={fixture}/>);open()
    expect(screen.getByText('发布于 2026-08-13')).toBeVisible()
    expect(screen.getByText('主要内容截止 2026-07-31')).toBeVisible()
    expect(screen.getAllByText('财务及表现数据截止 2026-06-30')).toHaveLength(2)
    expect(screen.getByText('特别事项注明除外')).toBeVisible()
    fireEvent.click(screen.getAllByText('原文页码与取得时间')[0])
    expect(screen.getByText('所列条款涉及 6 页；原文共 119 页，未声称逐页完整核对。')).toBeVisible()
    expect(screen.getByRole('link',{name:'所列条款 · PDF第32页 ↗'})).toHaveAttribute('href','https://www.sse.com.cn/rules.pdf#page=32')
    expect(screen.getAllByText('本次取得 2026/11/5 06:00:00（北京时间）')[0]).toBeVisible()
  })
  it('keeps each business unit separate from fund-total conversion and current validity',()=>{
    render(<ETFProspectusRules data={fixture}/>);open()
    expect(screen.getByText('申购 / 赎回：900,000 份')).toBeVisible()
    expect(screen.getByText('深市股票实物、沪市股票现金替代申赎：1,000,000 份')).toBeVisible()
    expect(screen.getAllByText('每笔单位，不是基金总份额的折算倍数')).toHaveLength(2)
    expect(screen.getAllByText('当前市场目标日是否仍有效：尚未核对')).toHaveLength(2)
    expect(screen.getByRole('link',{name:'业务单位条款 · 第64页 ↗'})).toHaveAttribute('href','https://www.sse.com.cn/rules.pdf#page=64')
  })
  it('preserves distribution limits as conditional rules without inventing observed counts or cash flows',()=>{
    render(<ETFProspectusRules data={fixture}/>);open()
    expect(screen.getByText('所列分配方式：现金分红；规则上限每年 4 次。')).toBeVisible()
    expect(screen.getByText('所列分配方式：现金分红；规则上限每年 12 次。')).toBeVisible()
    expect(screen.getAllByText('观察窗实际分红次数：尚未核对')).toHaveLength(2)
    expect(screen.getByText(/份额×净值不能直接等同现金进出/)).toBeVisible()
    expect(screen.queryByText(/实际分红次数：0/)).not.toBeInTheDocument()
  })
  it('labels the hypothetical calculation and later historical restatements without a current factor',()=>{
    render(<ETFProspectusRules data={fixture}/>);open()
    expect(screen.getByText('假设示例：5,000 份 × 0.26671819 → 1,334 份。')).toBeVisible()
    expect(screen.getByText('仅为文中假设，不登记为实际折算事件')).toBeVisible()
    expect(screen.getByText('文中历史复述：2012-05-11 折算，比例 0.37094933；变更登记 2012-05-14。')).toBeVisible()
    expect(screen.getByText('该版本述份额截去小数部分')).toBeVisible()
    expect(screen.getAllByText('这份后续版本不能回填为历史当时已知，未用于当前曲线校正')).toHaveLength(2)
  })
  it('keeps a partial version count and removes unavailable source facts',()=>{
    const {rerender}=render(<ETFProspectusRules data={{...fixture,reviewed_versions:1,versions:fixture.versions.slice(0,1)}}/>)
    expect(screen.getByText('条款核对 1/2 份筛选版本')).toBeInTheDocument()
    expect(screen.queryByText(/这两份/)).not.toBeInTheDocument()
    rerender(<ETFProspectusRules data={{...fixture,availability:'reload_required',reviewed_versions:0,versions:[]}}/>)
    expect(screen.getByText('所列版本尚未通过原文与日期核对，暂不展示规则或历史比例。')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})
