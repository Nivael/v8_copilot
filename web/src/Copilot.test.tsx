import {fireEvent,render,screen} from '@testing-library/react'
import {Link,MemoryRouter} from 'react-router-dom'
import {describe,expect,it} from 'vitest'
import {Copilot,EvidenceNavigation,QuestionDrawer} from './Copilot'
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

describe('Copilot evidence loops',()=>{
  it('renders all seven navigable evidence reference kinds',()=>{
    render(<MemoryRouter><EvidenceNavigation items={response.navigation_refs} selectedId="nav-provenance"/></MemoryRouter>)
    expect(screen.getAllByRole('link')).toHaveLength(7)
    kinds.forEach(kind=>expect(screen.getByText(`label-${kind}`)).toBeInTheDocument())
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
})
