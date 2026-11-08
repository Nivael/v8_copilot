import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,expect,it} from 'vitest'
import {STLabelChanges} from './STLabelChanges'
import type {RegimeLabelChanges} from './stRegimeTypes'
const source={title:'权益分派原件',url:'https://example.com/dividend.pdf#page=1',page:1,sha256:'a'.repeat(64)}
const row:RegimeLabelChanges['rows'][number]={symbol:'600079',name:'人福',kind:'ex_dividend_marker',before_name:'ST人福',effective_name:'XDST人福',effective_on:'2026-08-03',restore_on:'2026-08-04',published_on:'2026-07-25',signed_on:'2026-07-25',suspend_on:null,description:'现金分红除息标记',answer:'XD来自本次除息，不据此认定警示解除。',what_would_change:'若更正分派日期，重核参考价。',facts:[{published_on:'2026-07-25',text:'每股现金红利0.48元，8月3日除息。',source}],boundaries:[{date:'2026-08-03',matches:true},{date:'2026-08-04',matches:true}],matching_boundaries:2,same_st_presence_at_boundary:true,dividend_observation:{previous_session:'2026-07-31',ex_date:'2026-08-03',next_session:'2026-08-04',previous_raw_close:17.91,ex_raw_close:17.69,provider_adjusted_previous_close:17.43,cash_per_eligible_share:.48,reference_cash_per_share:.48,reference_before_cent_rounding:17.43,calculated_cent_reference:17.43,reference_matches_formula:true,raw_close_change_pct:-1.22836,reference_price_change_pct:1.49168,provider_reported_pct:1.4917,provider_qfq_change_pct:1.4913,factor_before:14.298,factor_on:14.6917,market_pct:-.5,st_pct:2.18,raw_quotes_match:true,qfq_channel_return_spread_pp:0,boundary:'价格比值不是个人含息总收益。',channels:[{key:'tencent_qfq',points:3,basis:'qfq',values:[{date:'2026-07-31',price:17.43,original_precision:'17.430'},{date:'2026-08-03',price:17.69,original_precision:'17.690'},{date:'2026-08-04',price:17.55,original_precision:'17.550'}],event_return_pct:1.49168,raw_price_differences:[],source:{url:'https://example.com/quote',sha256:'b'.repeat(64),observed_at:'2026-11-09T00:00:00Z'}}]}}
const data:RegimeLabelChanges={through:'2026-11-06',warning_changes:0,dividend_episodes:1,name_boundaries:2,matching_boundaries:2,new_primary_documents:1,new_primary_pages:3,quote_responses:4,quote_points:12,boundary:'只核所列边界。',identifier_rule:{published_on:'2025-07-13',attachment:{url:'https://example.com/rule.docx'}},rows:[row]}
afterEach(cleanup)
it('先区分名称边界与公司事项，现金与参考价涨跌按需展开',()=>{
 render(<STLabelChanges data={data}/>);
 expect(screen.getByText(/1次除息的名称进出合计2个边界，不算2次公司事件/)).toBeVisible()
 expect(screen.getByText('前后均在池中')).toBeVisible()
 fireEvent.click(screen.getByText('核事实与价格口径'))
 expect(screen.getByText(/直接比为-1.23%；提供方除息参考前收为17.43元，按它计算为\+1.49%/)).toBeVisible()
 expect(screen.getByRole('link',{name:'权益分派原件 · 第1页 ↗'})).toHaveAttribute('href',source.url)
 expect(screen.getByText('2026-07-31：17.430')).toBeVisible()
})
it('冲突时不改写来源，也不显示名称一致',()=>{
 render(<STLabelChanges data={{...data,matching_boundaries:1,rows:[{...row,matching_boundaries:1}]}}/>);
 expect(screen.getByText('名称与安排有冲突，待复核')).toBeVisible()
 expect(within(screen.getByRole('region',{name:'五家公司名称变化核对'})).getByText(/XDST人福/)).toBeVisible()
})
it('没有资料时不宣称完成核验',()=>{
 render(<STLabelChanges data={null}/>);expect(screen.queryByRole('region',{name:'星号与XD名称变化'})).not.toBeInTheDocument()
})
