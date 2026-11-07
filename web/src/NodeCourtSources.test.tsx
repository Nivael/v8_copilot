import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {NodeCourtSources} from './NodeCourtSources'
import type {NodeCourtSourcePool} from './types'

const fact:NodeCourtSourcePool['facts'][number]={event_id:'NCP-1',symbol:'002356',event_type:'restructuring_plan_approved',event_date:null,
  decision_date:null,receipt_date:'2021-12-29',information_available_date:'2021-12-29',subject:'示例公司一',court:'示例中级人民法院',court_case:null,
  title:'关于法院裁定批准重整计划的公告',source_url:'https://static.cninfo.com.cn/finalpage/2021-12-29/1212056976.PDF',source_observed_at:'2026-11-05T14:22:00+00:00',
  raw_sha256:'a'.repeat(64),text_sha256:'b'.repeat(64),source_pages:4,stage_proof:{page:1,text:'本次法院裁定批准公司重整计划。'},reviewed_pages:[1,2],original_discovery_source_ref:'cninfo:AN1',original_alias_asserted:false}
const pool:NodeCourtSourcePool={version:'node_public_court_pool_v1',availability:'observed',primary_bound_clauses:2,companies:2,metadata_responses:5,
  archived_PDFs:5,archived_pages:18,scoped_review_documents:4,selected_candidates:3,selected_rejections:1,extra_related_entity_exclusions:1,unreviewed_extra_attachments:1,
  unknown_decision_dates:1,unknown_receipt_dates:1,reviewed_at:'2026-11-05T15:25:00+00:00',historical_PIT:false,full_body_semantics_checked:false,P8_gold_validation_completed:false,original_alias_identity_asserted:false,
  facts:[fact,{...fact,event_id:'NCP-2',symbol:'300010',event_type:'formal_restructuring_accepted',subject:'示例公司二',event_date:'2023-11-15',decision_date:'2023-11-15',receipt_date:null,information_available_date:'2023-11-16'}]}
function open(){fireEvent.click(screen.getByText('查看新增公开法院条款与原件'))}

describe('NodeCourtSources',()=>{
  afterEach(cleanup)
  it('separates new primary clauses, old titles, rejected candidates and unreviewed attachments',()=>{
    render(<NodeCourtSources data={pool}/>);open()
    expect(screen.getByText(/2 份公告、2 家公司的法院阶段条款已绑定独立原件/)).toBeVisible()
    expect(screen.getByText(/不声称新原件就是原AN标识的同一附件/)).toBeVisible()
    expect(screen.getByText(/选定 3 条候选，1 条旧事项回述排除/)).toBeVisible()
    expect(screen.getByText(/1 份额外相近附件未核本项条款/)).toBeVisible()
    expect(screen.getByText(/条款核对不等于全文语义或金标验收/)).toBeVisible()
    expect(screen.getByText(/不恢复日内发布时间或历史当时可见/)).toBeVisible()
  })
  it('keeps disclosure, decision and receipt roles distinct and links physical proof pages',()=>{
    render(<NodeCourtSources data={pool}/>);open()
    const rows=screen.getAllByRole('row');const first=within(rows[1]);const second=within(rows[2])
    expect(first.getByText('法院批准计划')).toBeVisible()
    expect(first.getAllByText('2021-12-29')).toHaveLength(2)
    expect(first.getAllByText('待核')).toHaveLength(1)
    expect(second.getByText('法院受理重整')).toBeVisible()
    expect(second.getByText('2023-11-16')).toBeVisible()
    expect(second.getByText('2023-11-15')).toBeVisible()
    expect(second.getByText('待核')).toBeVisible()
    expect(first.getByRole('link',{name:'法院条款 · PDF第1页 ↗'})).toHaveAttribute('href',fact.source_url+'#page=1')
    expect(first.getByRole('link',{name:'其他已核条款 · PDF第2页 ↗'})).toHaveAttribute('href',fact.source_url+'#page=2')
  })
  it('supports a keyboard-focusable local table and preserves source observation time separately',()=>{
    render(<NodeCourtSources data={pool}/>);open()
    expect(screen.getByRole('region',{name:'可滚动的新增法院条款表'})).toHaveAttribute('tabindex','0')
    const first=within(screen.getAllByRole('row')[1])
    fireEvent.click(first.getByText('条款与取得时间'))
    expect(first.getByText('本次法院裁定批准公司重整计划。')).toBeVisible()
    expect(first.getByText(/原件共 4 页；本次取得 2026\/11\/5 22:22:00/)).toBeVisible()
  })
  it.each(['invalid','missing','foreign_version','count_mismatch'])('withdraws all old counts and proof rows for %s',state=>{
    const data={...pool,availability:state,version:state==='foreign_version'?'future':pool.version,
      primary_bound_clauses:state==='count_mismatch'?31:pool.primary_bound_clauses}
    if(state==='foreign_version'||state==='count_mismatch')data.availability='observed'
    render(<NodeCourtSources data={data}/>);open()
    expect(screen.getByText(/当前未通过来源核对，不沿用旧条款或旧覆盖计数/)).toBeVisible()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.queryByText(/2 份公告、2 家公司/)).not.toBeInTheDocument()
  })
})
