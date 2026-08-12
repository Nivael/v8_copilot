import {fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {ExperienceCenter} from './ExperienceCenter'

const candidate={
  contract_version:'v8_research_experience_contract_v0',experience_id:'EXP-AAAAAAAAAAAAAAAAAAAA',
  experience_version:1,status:'candidate',experience_type:'query_plan',title:'事件窗口连接逐日路径',
  value_summary:'组合事件先例应连接验证截止日和逐交易日价格。',trigger_conditions:['截止日前','历史先例'],
  topic_tags:['事件时点','价格路径'],
  scope:['event_window'],required_inputs:['verified_deadline','daily_prices'],query_plan:['验证截止日','连接价格'],
  definitions:['连续按交易日定义'],answer_rubric:['先回答有无'],anti_patterns:['用公告等待期代替价格路径'],
  coverage_boundaries:['历史先例不预测未来'],validation_refs:['tests/test_precedent.py'],source_run_refs:['RUN-1'],
  supersedes:[],created_at:'2026-07-14T00:00:00Z',reviewed_at:null,reviewed_by:null,not_evidence:true,
} as const

describe('ExperienceCenter',()=>{
  afterEach(()=>vi.restoreAllMocks())

  it('renders usable method fields and sends an explicit human review',async()=>{
    const governance={accepted_count:0,candidate_count:1,blocked_count:0,conflicts:[],latest_regression:null,ordinary_success_auto_capture:false,not_evidence:true}
    const queue={review_session_id:'XRV-AAAAAAAAAAAAAAAAAAAA',review_version:'v8_experience_batch_review_v1',title:'批量审阅',source_packet:'sha256:abc',created_at:'2026-07-14T00:00:00Z',max_pending:10,cards:[{
      card_id:candidate.experience_id,experience_id:candidate.experience_id,experience_version:1,title:candidate.title,
      affected_area:'query_plan',target_field:'experience_status',scope:'experience_cluster',
      decision_requested:'是否把这个方法作为以后同类研究的方法提示？',why_surfaced:'由 1 个来源运行归并。',
      recommendation:'accept_suggested',recommendation_label:'建议接受',recommendation_reason:'已有真实运行和回归。',
      impact:'决定 1 个方法簇。',affected_count:1,options:[
        {value:'accept_suggested',label:'接受推荐',description:'升级为 accepted。'},
        {value:'need_more_evidence',label:'需要更多证据',description:'转为 blocked。'},
        {value:'reject',label:'不沉淀',description:'转为 ignored。'},
        {value:'defer',label:'稍后再看',description:'保留 candidate。'},
      ],evidence_examples:[{run_id:'RUN-1',question:'是否有先例？',intent:'precedent',answer_excerpt:'存在代表案例。',source_pointer:'research_run:RUN-1'}],counterexamples:[],prior_decisions:[],experience:candidate,
    }]}
    let submitted=false
    const fetchMock=vi.spyOn(globalThis,'fetch').mockImplementation(async input=>{
      const url=String(input)
      if(url.includes('/decisions')){submitted=true;return new Response(JSON.stringify({review_session_id:queue.review_session_id,applied:[{card_id:candidate.experience_id,status:'accepted',replayed:false}]}),{status:200})}
      if(url.includes('experience-governance'))return new Response(JSON.stringify(governance),{status:200})
      if(url.includes('experience-review'))return new Response(JSON.stringify(submitted?{...queue,cards:[]}:queue),{status:200})
      return new Response(JSON.stringify([]),{status:200})
    })

    render(<ExperienceCenter/>)
    expect(await screen.findByRole('heading',{name:'当前没有已接受'})).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button',{name:'自动待验证'}))
    expect(await screen.findByRole('heading',{name:'事件窗口连接逐日路径'})).toBeInTheDocument()
    fireEvent.click(screen.getByText('查看方法、边界和代表运行'))
    expect(screen.getByText('历史先例不预测未来')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('radio',{name:/接受推荐/}))
    fireEvent.click(screen.getByRole('button',{name:/提交已选决定/}))

    await waitFor(()=>expect(screen.queryByRole('heading',{name:'事件窗口连接逐日路径'})).not.toBeInTheDocument())
    const decisionCall=fetchMock.mock.calls.find(call=>String(call[0]).includes('/decisions'))
    const init=decisionCall?.[1] as RequestInit
    const body=JSON.parse(String(init.body))
    expect(body.review_session_id).toBe(queue.review_session_id)
    expect(body.decisions[0].decision).toBe('accept_suggested')
  })
})
