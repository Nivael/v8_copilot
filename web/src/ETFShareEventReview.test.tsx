import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
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
    expect(screen.getByText(/场外：变更前 708,041,821.00 份，登记后 353,862,232.00 份/)).toBeInTheDocument()
    expect(screen.getByText(/48,100.8947756500 份。该差额不计作净申赎/)).toBeInTheDocument()
    fireEvent.click(screen.getByText('原文链（2份）'))
    expect(screen.getByRole('link',{name:'结果 · PDF第2页 ↗'})).toHaveAttribute('href','https://www.sse.com.cn/synthetic-er.pdf#page=2')
  })
  it('does not display old facts when evidence is missing or invalid',()=>{
    render(<ETFShareEventReview data={{...fixture,availability:'invalid',events:[],reviewed_events:0,reconciled_documents:0}}/>)
    expect(screen.getByText(/本批事项尚未通过当前原文、日期和关系核对/)).toBeInTheDocument()
    expect(screen.queryByText('0.49977589')).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
  it('distinguishes conversion, registration, rounding modes and a result-only source',()=>{
    const data:Review={...fixture,reviewed_events:3,events:[
      {event_id:'nearest',code:'510300.SH',kind:'conversion',resolution:'implemented',event_date:'2012-05-11',registration_date:'2012-05-14',
        source_scope:'result_only',holder_rounding:'nearest_whole_share',planned_ratio:null,effective_ratio:'0.37094933',resolution_published_on:'2012-05-15',within_catalog_window:false,
        reported_totals:[{scope:'fund_total',before_shares:'32968633875.00',after_shares:'12229687690.00',after_minus_simple_ratio_shares:'-4956.9465537500'}],documents:[document('nearest','result')]},
      {event_id:'floor',code:'159919.SZ',kind:'conversion',resolution:'implemented',event_date:'2012-11-30',holder_rounding:'floor_to_whole_share',
        planned_ratio:'0.38221954',effective_ratio:'0.38221954',resolution_published_on:'2012-12-03',within_catalog_window:false,
        reported_totals:[{scope:'fund_total',before_shares:'42045307392',after_shares:'16070506477',after_minus_simple_ratio_shares:'-31573.52883968'}],documents:[document('floor','result')]},
      {event_id:'unknown',code:'510330.SH',kind:'conversion',resolution:'implemented',event_date:'2013-01-09',registration_date:'2013-01-10',
        holder_rounding:'not_stated',plan_holder_rounding:['floor_to_whole_share'],planned_ratio:null,effective_ratio:'0.40932601',resolution_published_on:'2013-01-11',within_catalog_window:false,
        reported_totals:[{scope:'fund_total',before_shares:'16020609566',after_shares:'6557649828',after_minus_simple_ratio_shares:'-2363.41861166'}],documents:[document('unknown','result')]},
    ]}
    render(<ETFShareEventReview data={data}/>)
    expect(screen.getByText('份额折算日 2012-05-11')).toBeInTheDocument()
    expect(screen.getByText('变更登记日 2012-05-14')).toBeInTheDocument()
    expect(screen.getByText('本条仅核对结果原文')).toBeInTheDocument()
    expect(screen.getByText(/份额四舍五入到整数位；简单比例/)).toBeInTheDocument()
    expect(screen.getByText(/逐户截去小数部分；简单比例/)).toBeInTheDocument()
    expect(screen.getByText(/结果公告未重述逐户舍入方式；简单比例/)).toBeInTheDocument()
    expect(screen.getByText(/计划公告载明：逐户截去小数部分。与结果公告分开记录/)).toBeInTheDocument()
    expect(screen.getByText(/-31,573.52883968 份。该差额不计作净申赎/)).toBeInTheDocument()
    expect(screen.queryByText('拆分已取消')).not.toBeInTheDocument()
  })
  it('links issuer HTML without PDF pages and keeps each plan disclosure at its own time',()=>{
    const event:Review['events'][number]={...fixture.events[2],event_id:'html',documents:[
      {...document('html-plan','plan',[]),format:'issuer_html',url:'https://www.jsfund.cn/main/fund/noticedetails.shtml?adId=synthetic',published_on:'2022-08-01',announced_ratio:null},
      {...document('html-reminder','reminder',[]),format:'issuer_html',published_on:'2022-09-03',announced_ratio:'0.36555'},
    ]}
    render(<ETFShareEventReview data={{...fixture,events:[event]}}/>)
    fireEvent.click(screen.getByText('原文链（2份）'))
    const row=screen.getByRole('rowheader',{name:/512100.SH/})
    expect(within(row).getByText('本公告未给定确定比例')).toBeInTheDocument()
    expect(within(row).getByText('本公告给定比例 0.36555')).toBeInTheDocument()
    expect(within(row).getByText('生效日后的提示，不回填为事前已知')).toBeInTheDocument()
    const links=within(row).getAllByRole('link',{name:'发行人正文 ↗'})
    expect(links[0]).toHaveAttribute('href','https://www.jsfund.cn/main/fund/noticedetails.shtml?adId=synthetic')
    expect(within(row).queryByRole('link',{name:/PDF第/})).not.toBeInTheDocument()
  })
  it('filters the review without changing global coverage and exposes a source lost on refresh',()=>{
    const {rerender}=render(<ETFShareEventReview data={fixture}/>)
    fireEvent.change(screen.getByRole('combobox',{name:'ETF事项筛选'}),{target:{value:'510310.SH'}})
    expect(screen.getByText(/当前显示 1\/4 条/)).toBeInTheDocument()
    expect(screen.getByText(/涉及 10\/105 份筛选材料/)).toBeInTheDocument()
    expect(screen.getAllByRole('row')).toHaveLength(2)
    rerender(<ETFShareEventReview data={{...fixture,events:fixture.events.filter(event=>event.code!=='510310.SH')}}/>)
    expect(screen.getByText(/该ETF当前没有通过原文核对的事项/)).toBeInTheDocument()
    expect(screen.getByRole('combobox',{name:'ETF事项筛选'})).toHaveValue('510310.SH')
    expect(screen.getByRole('option',{name:'510310.SH（当前未取得）'})).toBeDisabled()
    fireEvent.change(screen.getByRole('combobox',{name:'ETF事项筛选'}),{target:{value:'all'}})
    expect(screen.getByText(/当前显示 3\/3 条/)).toBeInTheDocument()
  })
})
