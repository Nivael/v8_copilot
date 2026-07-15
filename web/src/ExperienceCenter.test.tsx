import {fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {ExperienceCenter} from './ExperienceCenter'

const candidate={
  contract_version:'v8_research_experience_contract_v0',experience_id:'EXP-AAAAAAAAAAAAAAAAAAAA',
  experience_version:1,status:'candidate',experience_type:'query_plan',title:'事件窗口连接逐日路径',
  value_summary:'组合事件先例应连接验证截止日和逐交易日价格。',trigger_conditions:['截止日前','历史先例'],
  scope:['event_window'],required_inputs:['verified_deadline','daily_prices'],query_plan:['验证截止日','连接价格'],
  definitions:['连续按交易日定义'],answer_rubric:['先回答有无'],anti_patterns:['用公告等待期代替价格路径'],
  coverage_boundaries:['历史先例不预测未来'],validation_refs:['tests/test_precedent.py'],source_run_refs:['RUN-1'],
  supersedes:[],created_at:'2026-07-14T00:00:00Z',reviewed_at:null,reviewed_by:null,not_evidence:true,
} as const

describe('ExperienceCenter',()=>{
  afterEach(()=>vi.restoreAllMocks())

  it('renders usable method fields and sends an explicit human review',async()=>{
    const accepted={...candidate,status:'accepted',experience_version:2,reviewed_by:'owner',reviewed_at:'2026-07-14T01:00:00Z'}
    const governance={accepted_count:0,candidate_count:1,blocked_count:0,conflicts:[],latest_regression:null,ordinary_success_auto_capture:false,not_evidence:true}
    const fetchMock=vi.spyOn(globalThis,'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify([candidate]),{status:200}))
      .mockResolvedValueOnce(new Response(JSON.stringify(governance),{status:200}))
      .mockResolvedValueOnce(new Response(JSON.stringify(accepted),{status:200}))

    render(<ExperienceCenter/>)
    expect(await screen.findByRole('heading',{name:'事件窗口连接逐日路径'})).toBeInTheDocument()
    fireEvent.click(screen.getByText('查看方法、边界与测试'))
    expect(screen.getByText('历史先例不预测未来')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button',{name:/人工接受/}))

    await waitFor(()=>expect(screen.queryByRole('heading',{name:'事件窗口连接逐日路径'})).not.toBeInTheDocument())
    const init=fetchMock.mock.calls[2][1] as RequestInit
    expect(JSON.parse(String(init.body))).toEqual({action:'accept',actor_type:'human',reviewed_by:'owner',note:''})
  })
})
