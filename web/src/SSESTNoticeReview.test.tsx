import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {SSESTNoticeReview} from './SSESTNoticeReview'
import type {SSESTNoticeReview as Review} from './types'

const item=(kind:string,i:number):Review['items'][number]=>({symbol:`60000${i}`,name_as_reported:'ST样本'+i,company:'公司'+i+'股份有限公司',
  kind,effective_on:kind==='warning_added'||kind==='warning_removed'?'2026-10-20':null,stated_since_on:kind==='existing_warning_described'?'2026-05-06':null,
  published_on:'2026-10-13',title:'公告标题'+i,source_url:`https://static.cninfo.com.cn/synthetic-${i}.PDF`,catalog_url:`https://www.sse.com.cn/synthetic-${i}.pdf`,
  proofs:[{page:2,text:kind==='application_pending'?'撤销尚待审核，存在不确定性':'公司股票此前被实施风险警示',role:kind==='application_pending'?'approval_pending':'prior_warning'}],observed_at:'2026-11-05T09:00:00+00:00'})
const data:Review={version:'synthetic',availability:'reviewed',review_scope:'security_identity_and_member_status_clauses_only',start:'2026-09-01',through:'2026-11-04',
  latest_publication:'2026-10-31',catalog_items:6,reviewed_items:6,distinct_companies:6,pdf_pages:20,
  counts:{warning_added:1,warning_removed:1,application_pending:1,layered_warning_existing_member:1,existing_warning_described:2},
  full_body_semantics_reviewed:false,full_window_membership_certificate:false,historical_membership_verified:false,historical_PIT:false,combined_ST_ready:false,effect_measured:false,
  items:['warning_added','warning_removed','application_pending','layered_warning_existing_member','existing_warning_described','existing_warning_described'].map(item)}

describe('SSESTNoticeReview',()=>{
  afterEach(cleanup)
  it('defaults to consequential clauses without treating the complete notice set as a daily membership certificate',()=>{
    render(<SSESTNoticeReview data={data}/>)
    expect(screen.getByText('显示 4/6 项')).toBeVisible()
    expect(screen.getByText(/未声称所有正文语义或逐日法定名单已核验/)).toBeVisible()
    expect(screen.getByText(/本目录最近公告发布于 2026-10-31/)).toBeVisible()
    expect(screen.queryByText('公司4股份有限公司')).not.toBeInTheDocument()
    expect(screen.getByRole('region',{name:'可滚动的沪市ST公告原文条款表'})).toHaveAttribute('tabindex','0')
  })
  it('can filter pending applications and links their actual proof page without assigning an effective removal',()=>{
    render(<SSESTNoticeReview data={data}/>)
    fireEvent.change(screen.getByRole('combobox',{name:'沪市ST原文条款筛选'}),{target:{value:'application_pending'}})
    expect(screen.getByText('显示 1/6 项')).toBeVisible()
    expect(screen.getByText('本项未登记成员增减生效日')).toBeVisible()
    expect(screen.queryByText('实际生效 2026-10-20')).not.toBeInTheDocument()
    expect(screen.getByRole('link',{name:'原PDF第2页 ↗'})).toHaveAttribute('href','https://static.cninfo.com.cn/synthetic-2.PDF#page=2')
    expect(screen.getByText(/审核尚未确定：撤销尚待审核/)).toBeVisible()
  })
  it('keeps all original identities and titles accessible in the complete set',()=>{
    render(<SSESTNoticeReview data={data}/>)
    fireEvent.change(screen.getByRole('combobox',{name:'沪市ST原文条款筛选'}),{target:{value:'all'}})
    expect(screen.getByText('显示 6/6 项')).toBeVisible()
    expect(screen.getByText('公司4股份有限公司')).toBeVisible()
    expect(screen.getByText('公告标题5')).toBeVisible()
    expect(within(screen.getByRole('region')).getAllByRole('row')).toHaveLength(7)
  })
  it.each(['invalid','scope','short','count'])('withholds old proof rows and review counts when %s',bad=>{
    const copy=structuredClone(data)
    if(bad==='invalid')copy.availability='invalid'
    if(bad==='scope')copy.review_scope='full_daily_membership'
    if(bad==='short')copy.items.pop()
    if(bad==='count')copy.reviewed_items=5
    render(<SSESTNoticeReview data={copy}/>)
    expect(screen.getByText(/原文条款核对当前不可用/)).toBeVisible()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })
})
