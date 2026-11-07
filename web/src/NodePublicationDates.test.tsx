import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {NodePublicationDates} from './NodePublicationDates'
import type {NodePublicationMetadata} from './types'

const base:NodePublicationMetadata={version:'node_publication_metadata_v1',availability:'observed',frame_document_items:2,frame_events:3,frame_companies:1,matched_documents:1,matched_events:2,unbound_documents:1,metadata_responses:2,changed_parent_date_documents:1,profile_digest:'metadata-proof',
  reviews:[{document_id:'cninfo:1213919185',symbol:'600654',title:'关于收到法院文书的公告',official_catalog_date:'2022-07-02',parent_published_dates:['2022-07-01'],source_url:'https://static.cninfo.com.cn/finalpage/2022-07-02/1213919185.PDF',announcement_time_raw_ms:1656691200000,utc_interpretation_date:'2022-07-01',utc_date_matches_parent:true,changed_from_parent_date:true,event_ids:['E1','E2'],availability:'observed',query_ref:'notice-1213919185',query_params:{stock:'600654,gssh0600654',seDate:'2022-06-30~2022-07-03'},response_sha256:'query-original',observed_at:'2026-11-05T13:00:00Z',date_precision:'catalog_day_not_exact_release_timestamp'}],
  historical_PIT:false,full_body_semantics_checked:false,exact_release_timestamps_verified:false}

describe('official publication metadata preserves date precision and scope',()=>{
  afterEach(cleanup)
  const open=()=>fireEvent.click(screen.getByText('查看官方目录日期与旧字段的对应'))
  it('starts collapsed and separates document/event coverage and unbound identifiers',()=>{
    render(<NodePublicationDates data={base}/>);
    expect(screen.getByText('查看官方目录日期与旧字段的对应').closest('details')).not.toHaveAttribute('open')
    open();expect(screen.getByText(/2 个文档项中，1 份匹配官方目录、覆盖 2 条既有事件；1 个来源标识未匹配/)).toBeVisible()
    expect(screen.getByText(/没有新核公告正文，也没有把标题来源改成已核事实/)).toBeVisible()
  })
  it('keeps original, Beijing catalog and UTC dates separate without claiming an exact release timestamp',()=>{
    render(<NodePublicationDates data={base}/>);open()
    expect(screen.getByText('旧字段')).toBeVisible();expect(screen.getAllByText('2022-07-01')).toHaveLength(2)
    expect(screen.getByText('目录（北京时间）')).toBeVisible();expect(screen.getByText('2022-07-02')).toBeVisible()
    expect(screen.getByText('同值取UTC日期')).toBeVisible()
    expect(screen.getByText('1656691200000')).toBeVisible();expect(screen.getByText(/仅按目录日使用，不恢复日内发布时间/)).toBeVisible()
    expect(screen.getByRole('link',{name:'对应公告附件 ↗'})).toHaveAttribute('href',base.reviews[0].source_url)
    fireEvent.click(screen.getByText('查询范围、取得时间和原件'));expect(screen.getByText(/2022-06-30~2022-07-03/)).toBeVisible();expect(screen.getByText('query-original')).toBeVisible()
  })
  it.each([{...base,availability:'invalid'},{...base,version:'future'},{...base,matched_documents:null}])('does not carry old dates or counters across an unavailable source',data=>{
    render(<NodePublicationDates data={data}/>);open();expect(screen.getByText(/不沿用旧的目录日期或覆盖计数/)).toBeVisible();expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
  it('supports local keyboard scrolling while preserving link keys and browser shortcuts',()=>{
    render(<NodePublicationDates data={base}/>);open();const region=screen.getByRole('region',{name:'可滚动的节点目录日期对照表'});region.scrollBy=vi.fn()
    expect(fireEvent.keyDown(region,{key:'ArrowDown'})).toBe(false);expect(region.scrollBy).toHaveBeenLastCalledWith({left:0,top:40,behavior:'auto'})
    vi.mocked(region.scrollBy).mockClear();expect(fireEvent.keyDown(screen.getByRole('link',{name:'对应公告附件 ↗'}),{key:'ArrowLeft'})).toBe(true)
    expect(fireEvent.keyDown(region,{key:'ArrowLeft',altKey:true})).toBe(true);expect(region.scrollBy).not.toHaveBeenCalled()
  })
})
