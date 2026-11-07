import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {ETFReviewScope} from './ETFReviewScope'
import type {ETFReviewScope as Review} from './types'

const flags={implementation_verified:false as const,current_validity_verified:false as const,fund_total_share_conversion:false as const,market_window_correction_applied:false as const,estimated_net_subscription_yuan:null}
const base={published_on:'2026-07-17',title:'单位调整',source_url:'https://www.chinaamc.com/original.pdf',format:'pdf',observed_at:'2026-11-04T22:00:00Z'}
const fixture:Review={version:'etf_selected_document_scoped_review_v1',availability:'scoped_reviewed',selected_document_items:4,items_with_scoped_review:4,items_without_scoped_review:0,
  all_selected_items_have_scoped_review:true,full_document_semantics_checked:false,all_window_share_events_verified:false,corporate_actions_checked:false,
  daily_share_scope_verified:false,share_precision_verified:false,final_revision_verified:false,estimated_net_subscription_yuan:null,historical_PIT:false,effect_measured:false,
  window_start:'2026-08-04',window_end:'2026-11-04',publication_cutoff:'2026-11-05',pdf_items:3,distinct_pdf_originals:2,pdf_pages_by_item:6,distinct_pdf_pages:4,issuer_html_items:1,
  supplemental_items:4,supplemental_counts:{creation_unit_declaration:2,liquidity_service_end:1,creation_redemption_pause:1},distinct_creation_unit_declarations:2,duplicate_unit_reminders:0,
  scope_counts:{creation_unit_declaration:2,liquidity_service_end:1,creation_redemption_pause:1},scope_labels:{creation_unit_declaration:'历史每笔申赎单位公告',liquidity_service_end:'历史流动性服务终止',creation_redemption_pause:'历史折算相关申赎暂停'},
  documents:[
    {...base,document_id:'unknown',code:'159845.SZ',url:'https://www.chinaamc.com/landing.shtml',review_reason:'historical_share_title',review_scopes:['creation_unit_declaration'],page_count:1,reviewed_pages:[1],raw_sha256:'one'},
    {...base,document_id:'html',code:'159922.SZ',published_on:'2014-02-20',url:'https://www.jsfund.cn/main/fund/noticedetails.shtml?adId=99609',source_url:'https://www.jsfund.cn/main/fund/noticedetails.shtml?adId=99609',format:'issuer_html',review_reason:'historical_share_title',review_scopes:['creation_unit_declaration'],page_count:null,reviewed_pages:[],raw_sha256:'two'},
    {...base,document_id:'provider',code:'159919.SZ',title:'服务终止',url:'https://www.jsfund.cn/provider.pdf',review_reason:'historical_share_title',review_scopes:['liquidity_service_end'],page_count:1,reviewed_pages:[1],raw_sha256:'three'},
    {...base,document_id:'pause',code:'510500.SH',title:'折算暂停',url:'https://www.sse.com.cn/pause.pdf',source_url:'https://www.sse.com.cn/pause.pdf',review_reason:'historical_share_title',review_scopes:['creation_redemption_pause'],page_count:2,reviewed_pages:[2],raw_sha256:'four'},
  ],
  supplemental_documents:[
    {...base,...flags,document_id:'unknown',code:'159845.SZ',kind:'creation_unit_declaration',announced_effective_on:'2026-07-20',unit_before_shares:null,unit_after_shares:'3000000',proofs:[{page:1,text:'最小申购、赎回单位调整为300万份',role:'per_order_unit'}]},
    {...base,...flags,document_id:'html',code:'159922.SZ',format:'issuer_html',source_url:'https://www.jsfund.cn/main/fund/noticedetails.shtml?adId=99609',kind:'creation_unit_declaration',announced_effective_on:'2014-02-24',unit_before_shares:'900000',unit_after_shares:'450000',proofs:[{page:null,text:'最小申购、赎回单位自90万份调整为45万份',role:'dated_per_order_unit'}]},
    {...base,...flags,document_id:'provider',code:'159919.SZ',kind:'liquidity_service_end',announced_effective_on:'2024-08-26',provider:'长江证券股份有限公司',proofs:[{page:1,text:'终止长江证券股份有限公司为本基金提供流动性服务',role:'service_provider'}]},
    {...base,...flags,document_id:'pause',code:'510500.SH',source_url:'https://www.sse.com.cn/pause.pdf',kind:'creation_redemption_pause',announced_effective_on:'2015-04-13',record_on:'2015-04-13',related_event_date:'2015-04-14',announced_resume_on:'2015-04-15',creation_redemption_code:'510501',proofs:[{page:2,text:'暂停申购起始日2015年4月13日',role:'creation_pause'}]},
  ],
}

describe('ETFReviewScope',()=>{
  afterEach(cleanup)
  it('separates specified review coverage, different originals and page volume from complete semantics and cash validation',()=>{
    render(<ETFReviewScope data={fixture}/>);
    expect(screen.getByText('4/4 项有指定范围依据')).toBeVisible()
    expect(screen.getByText(/全文语义、全窗份额事件.*净申赎金额继续未发布/)).toBeVisible()
    expect(screen.getByText(/查看全部文档/).closest('details')).not.toHaveAttribute('open')
    fireEvent.click(screen.getByText(/查看全部文档/))
    expect(screen.getByText(/3 个PDF文档项对应 2 份不同原PDF，另有 1 个发行人HTML正文项.*合计 6 页，原件去重后 4 页/)).toBeVisible()
    expect(screen.getByRole('link',{name:'原PDF第2页 ↗'})).toHaveAttribute('href','https://www.sse.com.cn/pause.pdf#page=2')
    const html=within(screen.getByRole('region',{name:'可滚动的ETF文档范围表'})).getByRole('link',{name:'发行人HTML正文 ↗'})
    expect(html.getAttribute('href')).not.toContain('#page=')
    expect(screen.getByRole('region',{name:'可滚动的ETF文档范围表'})).toHaveAttribute('tabindex','0')
  })
  it('filters the document ledger without changing the total coverage or claiming unselected scopes were pending',()=>{
    render(<ETFReviewScope data={fixture}/>);fireEvent.click(screen.getByText(/查看全部文档/))
    fireEvent.change(screen.getByLabelText('文档范围ETF筛选'),{target:{value:'510500.SH'}})
    fireEvent.change(screen.getByLabelText('文档核对范围筛选'),{target:{value:'creation_redemption_pause'}})
    expect(screen.getByText('显示 1/4 项')).toBeVisible()
    expect(screen.getByText('4/4 项有指定范围依据')).toBeVisible()
    expect(within(screen.getByRole('region',{name:'可滚动的ETF文档范围表'})).getAllByRole('row')).toHaveLength(2)
    fireEvent.change(screen.getByLabelText('文档核对范围筛选'),{target:{value:'creation_unit_declaration'}})
    expect(screen.getByText('当前筛选没有文档，可切换ETF或核对范围。')).toBeVisible()
  })
  it('keeps an unstated old unit unknown and links HTML without a fictional PDF page',()=>{
    render(<ETFReviewScope data={fixture}/>);fireEvent.click(screen.getByText(/查看补充的历史业务条款/))
    expect(screen.getByText('原单位未载明 → 3,000,000 份')).toBeVisible()
    expect(screen.getByText('900,000 份 → 450,000 份')).toBeVisible()
    expect(screen.getAllByText('未知原单位不从其他公告推算')).toHaveLength(2)
    expect(within(screen.getByRole('region',{name:'可滚动的ETF历史业务条款表'})).getByRole('link',{name:'发行人HTML正文 ↗'})).toHaveAttribute('href','https://www.jsfund.cn/main/fund/noticedetails.shtml?adId=99609')
    expect(screen.queryByRole('link',{name:/第null页/})).not.toBeInTheDocument()
  })
  it('preserves pause, record, conversion and resumption dates and the distinct business code',()=>{
    render(<ETFReviewScope data={fixture}/>);fireEvent.click(screen.getByText(/查看补充的历史业务条款/))
    fireEvent.change(screen.getByLabelText('历史业务条款筛选'),{target:{value:'creation_redemption_pause'}})
    expect(screen.getByText('基金主代码 510500；申购赎回业务代码 510501')).toBeVisible()
    expect(screen.getByText('公告声明暂停起始日 2015-04-13')).toBeVisible()
    expect(screen.getByText('权益登记日 2015-04-13')).toBeVisible()
    expect(screen.getByText('关联已核折算日 2015-04-14')).toBeVisible()
    expect(screen.getByText('公告声明恢复日 2015-04-15')).toBeVisible()
    expect(within(screen.getByRole('region',{name:'可滚动的ETF历史业务条款表'})).getByRole('link',{name:'原PDF第2页 ↗'})).toHaveAttribute('href','https://www.sse.com.cn/pause.pdf#page=2')
  })
  it('shows the terminated broker service without labelling it as a terminated fund or investor withdrawal',()=>{
    render(<ETFReviewScope data={fixture}/>);fireEvent.click(screen.getByText(/查看补充的历史业务条款/))
    fireEvent.change(screen.getByLabelText('历史业务条款筛选'),{target:{value:'liquidity_service_end'}})
    expect(screen.getByText('长江证券股份有限公司')).toBeVisible()
    expect(screen.getByText('终止该券商为本基金提供流动性服务')).toBeVisible()
    expect(screen.getByText(/券商流动性服务终止不能解释为基金终止或资金撤退/)).toBeVisible()
    expect(screen.getByText('显示 1/4 项补充条款')).toBeVisible()
  })
  it.each(['invalid','reload_required','missing'])('hides stale scope counts, all tables and factual clauses when %s',availability=>{
    render(<ETFReviewScope data={{...fixture,availability}}/>);
    expect(screen.getByText('汇总尚未通过当前来源校验')).toBeVisible()
    expect(screen.queryByText('4/4 项有指定范围依据')).not.toBeInTheDocument()
    expect(screen.queryByRole('table',{hidden:true})).not.toBeInTheDocument()
    expect(screen.queryByText(/300万份/)).not.toBeInTheDocument()
  })
  it('rejects a mismatched aggregate count and preserves a lost fund selection on a coherent refresh',()=>{
    const {rerender}=render(<ETFReviewScope data={fixture}/>);fireEvent.click(screen.getByText(/查看全部文档/))
    fireEvent.change(screen.getByLabelText('文档范围ETF筛选'),{target:{value:'159845.SZ'}})
    rerender(<ETFReviewScope data={{...fixture,selected_document_items:3,items_with_scoped_review:3,documents:fixture.documents.slice(1)}}/>)
    expect(screen.getByRole('option',{name:'159845.SZ（当前未取得）'})).toBeDisabled()
    expect(screen.getByText('当前筛选没有文档，可切换ETF或核对范围。')).toBeVisible()
    rerender(<ETFReviewScope data={{...fixture,items_with_scoped_review:3}}/>)
    expect(screen.getByText('汇总尚未通过当前来源校验')).toBeVisible()
  })
})
