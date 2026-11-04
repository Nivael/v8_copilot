import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {ETFShareEventReview} from './ETFShareEventReview'
import type {MarketRiskStatus} from './types'

type Review=NonNullable<MarketRiskStatus['etf_share_events']>
const document=(id:string,role:string,pages=[1])=>({document_id:id,role,published_on:'2024-09-23',title:`样本${role}原文`,url:`https://www.sse.com.cn/synthetic-${id}.pdf`,pages})
const fixture:Review={version:'etf_share_event_review_v1',availability:'partial',reviewed_events:4,reconciled_documents:10,selected_documents:105,pending_documents:95,
  all_selected_documents_reconciled:false,corporate_actions_checked:false,note:'仅核对已列事项，不能证明观察窗没有其他事件。',events:[
    {event_id:'efund-merge',code:'510310.SH',kind:'merge',resolution:'implemented',record_date:'2024-09-20',event_date:'2024-09-20',ex_right_date:'2024-09-23',
      planned_ratio:'0.49977589',effective_ratio:'0.49977589',resolution_published_on:'2024-09-23',within_catalog_window:false,holder_rounding:'ceil_to_whole_share',
      reported_totals:[{scope:'exchange',before_shares:'124750307415.00',after_shares:'62347244017.00',after_minus_simple_ratio_shares:'48100.8947756500'},
        {scope:'off_exchange',before_shares:'708041821.00',after_shares:'353862232.00',after_minus_simple_ratio_shares:'0.7525043100'}],
      documents:[document('ep','plan'),document('er','result',[1,2])]},
    {event_id:'cancel',code:'512100.SH',kind:'split',resolution:'cancelled',record_date:'2022-08-02',event_date:'2022-08-03',planned_ratio:'1.46301',effective_ratio:null,
      resolution_published_on:'2022-07-30',within_catalog_window:false,documents:[document('cp','plan'),document('ct','reminder'),document('cc','cancellation')]},
    {event_id:'merge',code:'512100.SH',kind:'merge',resolution:'implemented',record_date:'2022-09-01',event_date:'2022-09-02',planned_ratio:'0.36555',effective_ratio:'0.36555',
      resolution_published_on:'2022-09-05',within_catalog_window:false,holder_rounding:'ceil_to_whole_share',
      reported_totals:[{scope:'fund_total',before_shares:'10207092000',after_shares:'3731217646',after_minus_simple_ratio_shares:'15165.40000'}],
      documents:[document('mp','plan'),document('m1','reminder'),document('m2','reminder'),document('mr','result')]},
    {event_id:'unit',code:'512100.SH',kind:'creation_unit',resolution:'announced_effective',event_date:'2024-02-21',planned_ratio:null,effective_ratio:null,
      unit_before_shares:'1000000',unit_after_shares:'2000000',resolution_published_on:'2024-02-21',within_catalog_window:false,documents:[document('unit','unit_notice')]},
  ]}

describe('ETFShareEventReview',()=>{
  afterEach(cleanup)
  it('counts source chains once and leaves the full review and flow correction incomplete',()=>{
    render(<ETFShareEventReview data={fixture}/>)
    expect(screen.getByRole('heading',{name:'计划、取消与实施结果'})).toBeInTheDocument()
    expect(screen.getByText('局部核对 · 4条事项')).toBeInTheDocument()
    expect(screen.getByText(/涉及 10\/105 份筛选材料；其余 95 份/)).toBeInTheDocument()
    expect(screen.getByText(/多份提示公告合为同一事项，不重复计作折算/)).toBeInTheDocument()
    expect(screen.getAllByText('位于本次观察窗外')).toHaveLength(4)
    expect(screen.getByText(/净申赎金额继续未发布/)).toBeInTheDocument()
    expect(screen.queryByText('整个观察窗已核验')).not.toBeInTheDocument()
  })
  it('distinguishes a cancelled split, a merger and a per-creation-unit change',()=>{
    render(<ETFShareEventReview data={fixture}/>)
    expect(screen.getByText('拆分已取消')).toBeInTheDocument()
    expect(screen.getByText('原计划比例 1.46301，未生效')).toBeInTheDocument()
    expect(screen.getByText('无有效折算比例')).toBeInTheDocument()
    expect(screen.getByText('0.36555')).toBeInTheDocument()
    expect(screen.getByText(/1,000,000 → 2,000,000 份/)).toBeInTheDocument()
    expect(screen.getByText('每笔最小申赎单位')).toBeInTheDocument()
    expect(screen.getByText('每笔单位改变，不将其倍数用于基金总份额。')).toBeInTheDocument()
  })
  it('keeps exact ratios, scope totals, separate share/ex-right dates and original page links',()=>{
    render(<ETFShareEventReview data={fixture}/>)
    expect(screen.getByText('0.49977589')).toBeInTheDocument()
    expect(screen.getByText('份额合并日 2024-09-20')).toBeInTheDocument()
    expect(screen.getByText('除权日 2024-09-23')).toBeInTheDocument()
    fireEvent.click(screen.getAllByText('登记总额与比例乘积')[0])
    expect(screen.getByText(/场外：合并前 708,041,821.00 份，登记后 353,862,232.00 份/)).toBeInTheDocument()
    expect(screen.getByText(/48,100.8947756500 份。该差额不计作净申购/)).toBeInTheDocument()
    fireEvent.click(screen.getByText('原文链（2份）'))
    expect(screen.getByRole('link',{name:'结果 · PDF第2页 ↗'})).toHaveAttribute('href','https://www.sse.com.cn/synthetic-er.pdf#page=2')
  })
  it('does not display old facts when evidence is missing or invalid',()=>{
    render(<ETFShareEventReview data={{...fixture,availability:'invalid',events:[],reviewed_events:0,reconciled_documents:0}}/>)
    expect(screen.getByText(/本批事项尚未通过当前原文、日期和关系核对/)).toBeInTheDocument()
    expect(screen.queryByText('0.49977589')).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})
