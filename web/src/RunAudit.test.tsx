import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {MemoryRouter} from 'react-router-dom'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {RunAudit} from './RunAudit'

describe('RunAudit',()=>{
  afterEach(()=>{cleanup();vi.restoreAllMocks()})

  it('drills from a run into evidence rows, lens, backing, gaps and weights',async()=>{
    const fetchMock=vi.spyOn(globalThis,'fetch').mockImplementation(async input=>{
      const url=String(input)
      if(url.includes('/api/v1/research/corrections'))return new Response(JSON.stringify({availability:'available',corrections:[]}))
      if(url.includes('/api/v1/research/evidence/'))return new Response(JSON.stringify({
        pack_id:'EP-AAAAAAAAAAAAAAAAAAAA',pack_digest:'a'.repeat(64),created_at:'2026-07-15T00:00:00Z',
        payload:{
          contract_version:'v8_evidence_pack_v1',pack_id:'EP-AAAAAAAAAAAAAAAAAAAA',pack_digest:'a'.repeat(64),
          question_scope:{},query_plan_id:'comparison',rows:[{row_id:'row-1',stage:'预重整'}],
          lens_invocations:[{release_id:'RL-1',contributed_section:'historical context'}],
          freshness_manifest:{manifest_id:'FM-AAAAAAAAAAAAAAAAAAAA',overall_status:'ready'},external_evidence:[],
          source_freshness:{announcements:'2026-07-08'},provenance:['db'],
          coverage_gaps:[{gap_id:'G-1',note:'管理人渠道未覆盖'}],definitions:[],allowed_claims:[],
          forbidden_inferences:['不得预测'],validation_catalog:{},applicable_experiences:[],
          deterministic_response:{},not_evidence:false,
        },
      }),{status:200,headers:{'Content-Type':'application/json'}})
      return new Response(JSON.stringify([{
        run_id:'RUN-AAAAAAAAAAAAAAAAAAAAAAAA',request_id:'req-1',question_text:'当前阶段是什么？',
        normalized_intent:'stage',object_refs:['603398'],evidence_pack_ids:['EP-AAAAAAAAAAAAAAAAAAAA'],
        final_answer:'当前公开阶段是预重整。',research_draft:{narrative:{direct_answer:{
          text:'当前公开阶段是预重整。',backing:[{kind:'query_row',ref:'row-1'}],
        }}},decision_audit:{weighting_method:'ordinal_evidence_weighting_v0',
          judgment:'当前公开阶段是预重整。',judgment_backing:[{kind:'query_row',ref:'row-1'}],confidence:'medium',
          factors:[{factor_id:'stage',label:'法院公开程序',direction:'supports',importance:'decisive',
            rationale:'公开程序决定阶段标签。',backing:[{kind:'query_row',ref:'row-1'}]}],alternatives:[],
          not_hidden_chain_of_thought:true},validation_report:{valid:true},
        source_freshness:{announcements:'2026-07-08'},tool_calls:['comparison'],experience_hits:[],
        experience_candidate_ids:[],agent_surface:'codex_desktop',model:'',config_digest:'',thread_id:'',turn_id:'',
        started_at:'2026-07-15T00:00:00Z',completed_at:'2026-07-15T00:00:01Z',created_at:'2026-07-15T00:00:01Z',
      }]),{status:200,headers:{'Content-Type':'application/json'}})
    })

    render(<MemoryRouter><RunAudit/></MemoryRouter>)
    expect(await screen.findByRole('heading',{name:'当前阶段是什么？'})).toBeInTheDocument()
    expect(screen.getByRole('region',{name:'判断权重审计'})).toHaveTextContent('决定性')
    fireEvent.click(screen.getByRole('button',{name:/EP-AAAAAAAAAAAAAAAAAAAA/}))
    expect(await screen.findByText('数据库行')).toBeInTheDocument()
    expect(screen.getAllByText(/RL-1/).length).toBeGreaterThan(0)
    expect(screen.getByText('回答 backing')).toBeInTheDocument()
    expect(screen.getByText('Coverage gap')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button',{name:'沉淀这个方法'}))
    expect(await screen.findByText('已记录；本次不生成经验候选。')).toBeInTheDocument()
    const feedbackCall=fetchMock.mock.calls.find(call=>String(call[0]).includes('/feedback'))
    expect(JSON.parse(String((feedbackCall?.[1] as RequestInit).body)).category).toBe('query_plan')
  })
  it('flags a corrected run, folds its old assertion and fetches a linked run outside the recent page',async()=>{
    const makeRun=(id:string,answer:string)=>({run_id:id,question_text:id==='old'?'旧的研究':'新的研究',agent_surface:'test',created_at:'2026-06-03T00:00:00Z',normalized_intent:'research',evidence_pack_ids:[],experience_candidate_ids:[],validation_report:{valid:true},source_freshness:{},final_answer:answer,decision_audit:{},research_draft:{}})
    const old=makeRun('old','已撤回的旧结论'),replacement=makeRun('new','修正后的事实')
    const note={old_run_id:'old',replacement_run_id:'new',original_question_id:'q',headline:'旧结论有更正',summary:'保留原文，撤回遗漏指控。',corrected_at:'2026-06-04T00:00:00Z'}
    const scroll=vi.fn();Object.defineProperty(HTMLElement.prototype,'scrollIntoView',{configurable:true,value:scroll})
    const request=vi.spyOn(globalThis,'fetch').mockImplementation(async input=>{
      const url=String(input)
      return new Response(JSON.stringify(url.includes('/corrections')?{availability:'available',corrections:[note]}:url.endsWith('/runs/new')?replacement:[old]))
    })
    render(<MemoryRouter><RunAudit/></MemoryRouter>)
    expect(await screen.findByText('这份旧研究有更正')).toBeVisible()
    expect(screen.getByText('已撤回的旧结论')).not.toBeVisible()
    expect(screen.queryByLabelText('校验通过')).not.toBeInTheDocument()
    expect(screen.queryByRole('button',{name:'沉淀这个方法'})).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button',{name:'查看修正后的研究'}))
    expect(await screen.findByRole('heading',{name:'新的研究'})).toBeVisible()
    expect(screen.getByText('这是修正后的事实核查')).toBeVisible()
    expect(request.mock.calls.some(([url])=>String(url).endsWith('/runs/new'))).toBe(true)
    expect(scroll).toHaveBeenCalled()
  })
  it('does not display unlabelled research when the correction view is unavailable',async()=>{
    vi.spyOn(globalThis,'fetch').mockImplementation(async input=>new Response(JSON.stringify(String(input).includes('/corrections')?{availability:'updating',corrections:[]}:[])))
    render(<MemoryRouter><RunAudit/></MemoryRouter>)
    expect(await screen.findByRole('alert')).toHaveTextContent('暂时无法读取研究记录或更正')
    expect(screen.queryByText('还没有 Codex 研究运行')).not.toBeInTheDocument()
  })

})
