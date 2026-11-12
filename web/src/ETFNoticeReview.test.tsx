import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {ETFNoticeReview} from './ETFNoticeReview'
import type {ETFNoticeReview as Review} from './types'

const base={published_on:'2026-09-05',observed_at:'2026-11-04T22:00:00Z',url:'https://www.sse.com.cn/notice.pdf',evidence_pages:[1,4],fund_share_change_verified:false as const,full_document_semantics_checked:false as const}
const stock={issuer:'示例证券',asset_unit:'stock_share',quantity:'5200',amount_yuan:'739336.00',table_page:4}
const fixture:Review={version:'etf_notice_fact_review_v1',availability:'partial',reviewed_notices:5,reviewed_funds:4,distinct_original_pdfs:5,
  catalog_window_start:'2026-08-04',catalog_window_end:'2026-11-04',
  window_selected_documents:42,window_documents_outside_this_review:37,corporate_actions_checked:false,all_window_documents_reconciled:false,
  category_counts:{portfolio_allocation:2,listing_valuation_risk:1,creation_redemption_agent:1,liquidity_provider:1},
  note:'只核对所列正文段落，股和张不计作ETF份额申赎。',
  repeat_disclosure_groups:[{code:'510330.SH',issuer:'示例证券',quantity:'5200',amount_yuan:'739336.00',document_ids:['stock','risk'],not_additional_subscription_flow:true}],
  notices:[
    {...base,document_id:'stock',code:'510330.SH',category:'portfolio_allocation',title:'股票获配',allocations:[stock]},
    {...base,document_id:'bond',code:'510500.SH',category:'portfolio_allocation',title:'可转债获配',allocations:[{issuer:'示例可转债',asset_unit:'bond_piece',quantity:'56675',amount_yuan:'5667500',table_page:1}]},
    {...base,document_id:'risk',code:'510330.SH',category:'listing_valuation_risk',title:'上市估值提醒',published_on:'2026-09-11',allocations:[stock],listing_on:'2026-09-11',nav_reference_on:'2026-09-10',reported_weight_text:'0.00%',risk_clause:'IOPV未包含新股市场价格波动。'},
    {...base,document_id:'agent',code:'510310.SH',category:'creation_redemption_agent',title:'新增机构',allocations:[],service:{role:'申购赎回代办证券公司',provider:'示例证券股份有限公司',effective_on:'2026-08-17'}},
    {...base,document_id:'liquidity',code:'159919.SZ',category:'liquidity_provider',title:'主流动性服务商',allocations:[],service:{role:'主流动性服务商',provider:'另一家证券股份有限公司',effective_on:'2026-10-28'}},
  ],
}

function open(){fireEvent.click(screen.getByText(/查看正文核对/))}

describe('ETFNoticeReview',()=>{
  afterEach(cleanup)
  it('keeps stock shares, bond pieces and service appointments separate from ETF subscriptions',()=>{
    render(<ETFNoticeReview data={fixture}/>);open()
    expect(screen.getByText(/公告筛选窗 2026-08-04 至 2026-11-04，按披露日筛选；与主图的近两个月市场窗口分开/)).toBeVisible()
    const stockRows=screen.getAllByText('示例证券：5,200 股（持仓证券）；获配金额 739,336.00 元。')
    expect(stockRows).toHaveLength(2)
    stockRows.forEach(row=>expect(row).toBeVisible())
    expect(screen.getByText('示例可转债：56,675 张（可转债）；获配金额 5,667,500 元。')).toBeVisible()
    expect(screen.getByText('公告角色：申购赎回代办证券公司')).toBeInTheDocument()
    expect(screen.getByText('公告角色：主流动性服务商')).toBeInTheDocument()
    expect(screen.getByText('公告生效日 2026-10-28')).toBeInTheDocument()
    expect(screen.getAllByText('不计作ETF份额申赎')).toHaveLength(5)
    expect(screen.getAllByRole('link',{name:'正文或表格 · PDF第4页 ↗'})[0]).toHaveAttribute('href','https://www.sse.com.cn/notice.pdf#page=4')
  })
  it('preserves positive allotment values beside a two-decimal zero weight and the earlier denominator date',()=>{
    render(<ETFNoticeReview data={fixture}/>);open()
    expect(screen.getByText('披露占比 0.00%（两位小数）')).toBeVisible()
    expect(screen.getByText('披露值按两位小数显示')).toBeVisible()
    expect(screen.getByText('公告挂牌日 2026-09-11')).toBeInTheDocument()
    expect(screen.getByText('占比分母净值日期 2026-09-10')).toBeInTheDocument()
    fireEvent.click(screen.getByText('IOPV与净值差异原文'))
    expect(screen.getByText('IOPV未包含新股市场价格波动。')).toBeVisible()
    expect(screen.getByText(/发现 1 组.*分开回链，不累计成新增申赎/)).toBeInTheDocument()
    expect(screen.getByRole('link',{name:'2026-09-11 · 对应披露 ↗'})).toHaveAttribute('href','https://www.sse.com.cn/notice.pdf#page=4')
  })
  it('filters locally without rewriting the overall review counts or dropping the repeat source link',()=>{
    render(<ETFNoticeReview data={fixture}/>);open()
    fireEvent.change(screen.getByLabelText('正文ETF筛选'),{target:{value:'510330.SH'}})
    fireEvent.change(screen.getByLabelText('正文类型筛选'),{target:{value:'listing_valuation_risk'}})
    expect(screen.getByText('当前显示 1/5 条；整体核对数量不随筛选改变')).toBeInTheDocument()
    expect(screen.getByText('已核对正文事项 5 条')).toBeInTheDocument()
    expect(screen.getByRole('link',{name:'2026-09-05 · 对应披露 ↗'})).toBeInTheDocument()
    expect(screen.queryByText('可转债获配')).not.toBeInTheDocument()
  })
  it('retains a lost fund selection with an explicit empty state on source refresh',()=>{
    const {rerender}=render(<ETFNoticeReview data={fixture}/>);open()
    fireEvent.change(screen.getByLabelText('正文ETF筛选'),{target:{value:'510310.SH'}})
    rerender(<ETFNoticeReview data={{...fixture,reviewed_notices:4,notices:fixture.notices.filter(row=>row.document_id!=='agent')}}/>)
    expect(screen.getByLabelText('正文ETF筛选')).toHaveValue('510310.SH')
    expect(screen.getByRole('option',{name:'510310.SH（当前未取得）'})).toBeDisabled()
    expect(screen.getByText('当前筛选没有通过原文核对的事项，可切换ETF或类型查看。')).toBeInTheDocument()
  })
  it('does not keep stale amounts or categories when the reviewed source is unavailable',()=>{
    render(<ETFNoticeReview data={{...fixture,availability:'reload_required',notices:[],reviewed_notices:0}}/>)
    expect(screen.getByText('所列正文事项尚未通过当前原文核对，暂不展示已失效的分类或金额。')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.queryByText(/5,667,500 元/)).not.toBeInTheDocument()
  })
})
