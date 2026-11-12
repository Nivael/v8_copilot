import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {STReconstruction} from './STReconstruction'
import type {MarketRiskIndex,SSESTNoticeReview,STReconstruction as Reference} from './types'

const sample=(close:number)=>({close,member_count:20,observed_members:19,coverage_ratio:.95,missing_symbols:['600001.SH'],daily_return_pct:0})
const points=['2026-09-04','2026-09-07','2026-09-08'].map((date,i)=>({date,all:sample(1000-i*50),SSE:sample(1000-i*40),SZSE:sample(1000-i*60)}))
const metric={return_pct:-10,max_drawdown_pct:-10,minimum_coverage:.95,member_day_observations:60,observed_member_days:57}
const data:Reference={version:'synthetic',availability:'reconstructed',start:points[0].date,through:points[2].date,
  combined_ST_ready:false,historical_membership_verified:false,historical_PIT:false,portfolio_wealth:false,effect_measured:false,
  coverage_threshold:.95,points,metrics:{all:metric,SSE:metric,SZSE:metric},sse_reviewed_transitions:1,szse_reviewed_transitions:8,
  sse_anchor_members:20,sse_distinct_members:21,sse_endpoint_members:20,szse_distinct_members:20,szse_endpoint_members:20,
  events:[{symbol:'600001',old_name:'公司',new_name:'ST公司',kind:'warning_added',effective_on:'2026-09-07',published_on:'2026-09-04',
    source_url:'https://static.cninfo.com.cn/synthetic.PDF',proof_page:2,observed_at:'2026-11-05T04:00:00+00:00'}],
  catalog:{items:[{symbol:'600001',published_on:'2026-09-04',title:'申请其他风险警示',catalog_url:'https://www.sse.com.cn/synthetic.PDF',triage:'application_only_title'}],
    review_level:'title_only',observed_at:'2026-11-05T04:00:00+00:00',full_body_review:false,daily_membership_certificate:false},
  memberships:points.map(p=>({date:p.date,SSE:['600001.SH'],SZSE:['000001.SZ']}))}
const baseline:MarketRiskIndex={code:'000985.CSI',name:'中证全指',through:points[2].date,historical_only:false,return_5d_pct:null,
  return_20d_pct:null,return_60d_pct:null,max_drawdown_60d_pct:null,from_60d_peak_pct:null,amount_5d_to_20d_ratio:null,
  path:points.map((p,i)=>({date:p.date,close:100+i}))}

describe('STReconstruction',()=>{
  afterEach(cleanup)
  it('keeps the unverified membership warning before the figure and switches the actual scope and date',()=>{
    render(<STReconstruction data={data} indices={[baseline]}/>)
    const warning=screen.getByText('价格来源覆盖沪深两所，完整ST核验尚未通过。')
    const chart=screen.getByRole('img',{name:'沪深ST重建与同窗中证全指价格参考路径'})
    expect(warning.compareDocumentPosition(chart)&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByText('沪市逐日成员待独立核验')).toBeVisible()
    fireEvent.change(screen.getByRole('combobox',{name:'ST重建查看范围'}),{target:{value:'SSE'}})
    expect(screen.getByRole('img',{name:'沪市ST重建与同窗中证全指价格参考路径'})).toBeVisible()
    const slider=screen.getByRole('slider',{name:'ST重建观察日期'})
    fireEvent.change(slider,{target:{value:'1'}})
    expect(slider).toHaveAttribute('aria-valuetext','2026-09-07')
    expect(screen.getByText('沪市ST重建 96.00 · 中证全指 101.00')).toBeVisible()
    expect(screen.getByText('成员 20 · 有成交 19 · 覆盖 95.00%')).toBeVisible()
    expect(screen.getByText('停牌或无成交：600001.SH')).toBeVisible()
  })
  it.each(['older','missing','different','null'])('never overlays a mismatched market calendar (%s)',bad=>{
    const index=structuredClone(baseline)
    if(bad==='older')index.through='2026-09-07'
    if(bad==='missing')index.path.splice(1,1)
    if(bad==='different')index.path[1].date='2026-09-06'
    if(bad==='null')index.path[1].close=null
    render(<STReconstruction data={data} indices={[index]}/>)
    expect(screen.queryByText('中证全指 · 同窗')).not.toBeInTheDocument()
    expect(screen.getByText(/日期不完全一致/)).toBeVisible()
    expect(screen.getByRole('img',{name:'沪深ST重建价格参考路径'})).toBeVisible()
  })
  it.each(['invalid','short','null','coverage','duplicate'])('withholds every path and metric when one venue or day is invalid (%s)',bad=>{
    const copy=structuredClone(data)
    if(bad==='invalid')copy.availability='invalid'
    if(bad==='short')copy.points.pop()
    if(bad==='null')copy.points[0].SSE.close=null
    if(bad==='coverage')copy.points[1].SZSE.coverage_ratio=.94
    if(bad==='duplicate')copy.points[1].date=copy.points[0].date
    render(<STReconstruction data={copy} indices={[baseline]}/>)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.queryByRole('slider')).not.toBeInTheDocument()
    expect(screen.queryByText('-10.00%')).not.toBeInTheDocument()
    expect(screen.queryByText('价格来源覆盖沪深两所，完整ST核验尚未通过。')).not.toBeInTheDocument()
    expect(screen.getByText('重建参考当前不可用，完整ST核验尚未通过。')).toBeVisible()
    expect(screen.getByText(/整段参考路径暂不发布/)).toBeVisible()
    expect(screen.getByText('沪市逐日成员待独立核验')).toBeVisible()
  })
  it('links physical proof pages and keeps title-only triage and all member denominators reviewable',()=>{
    render(<STReconstruction data={data} indices={[]}/>)
    fireEvent.click(screen.getByText('沪市成员生效依据、目录筛查与每日分母'))
    expect(screen.getByRole('link',{name:'原PDF第2页 ↗'})).toHaveAttribute('href','https://static.cninfo.com.cn/synthetic.PDF#page=2')
    expect(screen.getByText(/正文条款及逐日法定名单待核/)).toBeVisible()
    expect(screen.getByRole('region',{name:'可滚动的ST重建逐日分母表'})).toHaveAttribute('tabindex','0')
    fireEvent.click(screen.getByText('查看目录的1条标题筛查'))
    expect(screen.getByText('申请标题，未作生效')).toBeVisible()
    expect(screen.getByRole('region',{name:'可滚动的风险警示目录筛查表'})).toHaveAttribute('tabindex','0')
    fireEvent.click(screen.getByText('查看逐日成员代码'))
    expect(screen.getByRole('region',{name:'可滚动的ST重建每日成员表'})).toHaveAttribute('tabindex','0')
  })
  it.each(['matching','other_end','other_member','partial','wrong_scope'])('binds supplemental review to the exact catalog without promoting daily membership (%s)',bad=>{
    const review:SSESTNoticeReview={version:'synthetic',availability:'reviewed',review_scope:'security_identity_and_member_status_clauses_only',
      through:data.through,catalog_items:1,reviewed_items:1,full_body_semantics_reviewed:false,full_window_membership_certificate:false,
      historical_membership_verified:false,historical_PIT:false,combined_ST_ready:false,effect_measured:false,items:[{symbol:'600001',published_on:'2026-09-04',
        name_as_reported:'ST公司',company:'公司股份有限公司',title:'申请其他风险警示',source_url:'https://static.cninfo.com.cn/synthetic.PDF',catalog_url:'https://www.sse.com.cn/synthetic.PDF',
        kind:'application_pending',effective_on:null,stated_since_on:null,proofs:[],observed_at:'2026-11-05T04:00:00Z'}]}
    if(bad==='other_end')review.through='2026-09-07'
    if(bad==='other_member')review.items[0].symbol='600002'
    if(bad==='partial')review.reviewed_items=0
    if(bad==='wrong_scope')review.review_scope='full_membership'
    render(<STReconstruction data={data} indices={[]} noticeReview={review}/>)
    if(bad==='matching')expect(screen.getByText(/补充核对已覆盖这 1 项公告/)).toBeVisible()
    else expect(screen.queryByText(/补充核对已覆盖/)).not.toBeInTheDocument()
    expect(screen.getByText('沪市逐日成员待独立核验')).toBeVisible()
    expect(screen.getByText('价格来源覆盖沪深两所，完整ST核验尚未通过。')).toBeVisible()
  })
})
