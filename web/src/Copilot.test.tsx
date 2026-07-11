import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {Link,MemoryRouter} from 'react-router-dom'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {Copilot,EvidenceNavigation,QuestionDrawer} from './Copilot'
import {show} from './display'
import type {NavigationKind,Response} from './types'

const kinds:NavigationKind[]=['stock','date','announcement','episode','lens','provenance','data_debt']
const response:Response={
  contract_version:'v8_copilot_api_contract_v1',
  route:{route:'answer_query'},interpretation:{},answer_card:null,claims:[],gaps:[],
  sedimentation_candidates:[],degraded:false,degraded_reasons:[],llm_used:false,
  query_template_id:'QT-002',
  question_cards:[{
    id:'QC-20260710-004',question:'节点前后发生了什么？',object:{kind:'stock',ref:'603398'},
    needs_data:[],status:'answerable',view:'query',source:'user',debt_ref:null,
  }],
  data_debt_candidates:[{debt_ref:'D-021',gap:'股东人数覆盖不足',affects:'股东变化比较'}],
  navigation_refs:kinds.map((kind,index)=>({
    id:`nav-${kind}`,kind,label:`label-${kind}`,source_kind:'answer_card',
    source_ref:kind==='data_debt'?'D-021':`source-${index}`,href:`/?ref=${kind}`,context:{},
  })),
}

const answeredResponse:Response={
  ...response,
  question_cards:[],data_debt_candidates:[],navigation_refs:[],
  claims:[{text:'状态表确认该股票已进入风险警示区间。',claim_type:'fact',backing:{kind:'query_row',ref:'status-row-1'}}],
  answer_card:{
    question:'这只股票为什么被 ST？',object_ref:'stock:603398',view:'query',as_of:'2026-06-26',
    sample_scope:'1 个状态区间',evidence_grade:'descriptive_query',lens_invocations:[],lens_gap:[],
    source_freshness:{status:'2026-06-26'},body_rows:[{row_id:'status-row-1',状态:'风险警示'}],
    analysis_claims:[],data_debt:[],data_debt_refs:[],caveats:['原因仍需回到公告原文。'],
    provenance:['shared_data/v5/database.sqlite3::st_status_history'],
  },
}

describe('Copilot evidence loops',()=>{
  it('renders all seven navigable evidence reference kinds',()=>{
    render(<MemoryRouter><EvidenceNavigation items={response.navigation_refs} selectedId="nav-provenance"/></MemoryRouter>)
    expect(screen.getAllByRole('link')).toHaveLength(7)
    kinds.forEach(kind=>expect(screen.getByText(show(`label-${kind}`))).toBeInTheDocument())
    expect(screen.getByText('label-provenance').closest('a')).toHaveAttribute('aria-current','location')
  })

  it('keeps QuestionCard and data debt candidates visible together',()=>{
    render(<MemoryRouter><QuestionDrawer response={response} currentContext={{
      symbol:'603398',selected_event:{event_id:'announcement:1',date:'2026-01-01'},
    }}/></MemoryRouter>)
    expect(screen.getByRole('complementary',{name:'问题沉淀'})).toBeInTheDocument()
    expect(screen.getByText('节点前后发生了什么？')).toBeInTheDocument()
    expect(screen.getByText('股东人数覆盖不足')).toBeInTheDocument()
    expect(screen.getByText('2 项候选，本轮不写入证据库')).toBeInTheDocument()
    expect(screen.getByRole('link',{name:'再次研究：节点前后发生了什么？'}).getAttribute('href')).toContain('event=announcement%3A1')
  })

  it('updates the composer when same-page question navigation changes the URL',()=>{
    render(<MemoryRouter initialEntries={['/?question=旧问题']}><Link to="/?question=新问题">切换问题</Link><Copilot/></MemoryRouter>)
    expect(screen.getByRole('textbox',{name:'研究问题'})).toHaveValue('旧问题')
    fireEvent.click(screen.getByRole('link',{name:'切换问题'}))
    expect(screen.getByRole('textbox',{name:'研究问题'})).toHaveValue('新问题')
  })

  it('offers starter questions and submits one on click',async()=>{
    vi.spyOn(globalThis,'fetch').mockRejectedValue(new Error('研究服务不可用'))
    render(<MemoryRouter initialEntries={['/']}><Copilot/></MemoryRouter>)
    expect(screen.getByText('还没想好？这些问题覆盖了系统的各类合法回答路径：')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button',{name:/为什么ST/}))
    expect(screen.getByRole('textbox',{name:'研究问题'})).toHaveValue('沐邦为什么ST？关键节点是什么？')
    expect(await screen.findByRole('alert')).toHaveTextContent('研究服务不可用')
  })

  it('submits on Enter and keeps Shift+Enter as newline',async()=>{
    vi.spyOn(globalThis,'fetch').mockRejectedValue(new Error('研究服务不可用'))
    render(<MemoryRouter initialEntries={['/']}><Copilot/></MemoryRouter>)
    const composer=screen.getByRole('textbox',{name:'研究问题'})
    fireEvent.change(composer,{target:{value:'ST面板自身两周涨跌分布如何？'}})
    fireEvent.keyDown(composer,{key:'Enter',shiftKey:true})
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    fireEvent.keyDown(composer,{key:'Enter'})
    expect(await screen.findByRole('alert')).toHaveTextContent('研究服务不可用')
  })

  it('keeps the analysis readable and moves backing ids into the evidence module',async()=>{
    const stream={request_id:'req-1',sequence:1,event:'completed',payload:{response:answeredResponse}}
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(`${JSON.stringify(stream)}\n`,{
      status:200,headers:{'Content-Type':'application/x-ndjson'},
    }))
    render(<MemoryRouter initialEntries={['/']}><Copilot/></MemoryRouter>)
    const composer=screen.getByRole('textbox',{name:'研究问题'})
    fireEvent.change(composer,{target:{value:'这只股票为什么被 ST？'}})
    fireEvent.keyDown(composer,{key:'Enter'})

    expect(await screen.findByText('状态表确认该股票已进入风险警示区间。')).toBeInTheDocument()
    expect(screen.getByText('本题没有匹配到适用的冻结 Lens；以下内容按描述性查询呈现，不升级为历史先验。')).toBeInTheDocument()
    expect(screen.queryByText(/status-row-1/)).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button',{name:'查看证据与来源'}))
    expect(screen.getByRole('complementary',{name:'证据与来源'})).toBeInTheDocument()
    expect(screen.getByText(/status-row-1/)).toBeInTheDocument()
  })
})

afterEach(()=>{
  cleanup()
  vi.restoreAllMocks()
  window.localStorage.clear()
})
