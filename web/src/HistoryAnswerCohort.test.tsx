import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {HistoryAnswerCohort,type AnswerCohort} from './HistoryAnswerCohort'
import {first} from './test/historyEventFixture'

afterEach(cleanup)
const points=[{date:'2026-06-05',value:100,level:100},{date:'2026-06-08',value:102,level:102}]
const cohort:AnswerCohort={version:'history_answer_cohort_v1',question_id:'q',source_run_id:'run',asked_on:'2026-06-05',reference_date:'2026-06-05',through:'2026-06-08',summary:'原答名单，三年窗口仍在进行。',price_note:'价格缺口保留。',market:points,st:points,st_name:'ST参考',members:['公司甲','公司乙'].map((name,i)=>({name,symbol:`symbol${i}`,conclusion:`${name}先核事件阶段。`,points,timeline:{version:'history_event_timeline_v2',assessment_basis:'original_argument_only',question_id:'q',symbol:`symbol${i}`,initial_event_id:`event${i}`,events:[{...first,id:`event${i}`,title:`${name}公告`,source:{...first.source,url:`https://example.com/${i}.pdf#page=2`}}],content_digest:'binding',learning:{lesson:'按阶段更新。',next_check:'核下一份公告。'}},source_refs:[{key:'prices',title:`${name}行情来源`,url:'https://example.com/prices'}],gap_notes:[{date:'2026-06-06',reason:'停牌期间保留缺口。',url:'https://example.com/suspension'}]}))}
const show=(value=cohort)=>render(<HistoryAnswerCohort cohort={value} questionId="q" sourceRunId="run"/>)
const open=()=>fireEvent.click(screen.getByText(/旧答名单：逐只查看/))

describe('historical answer cohort',()=>{
  it('mounts charts only while expanded',async()=>{
    show();expect(screen.queryByRole('figure')).not.toBeInTheDocument()
    open();expect(await screen.findByRole('figure')).toBeVisible()
    expect(screen.getByText(/起点包含提问前的当日变动/)).toBeVisible()
    expect(screen.getByRole('button',{name:'原提问 2026-06-05 · 回到重点公告'})).toBeVisible()
    open();await waitFor(()=>expect(screen.queryByRole('figure')).not.toBeInTheDocument())
  })
  it('switches company, selected event and primary source together',async()=>{
    show();open();expect(await screen.findByRole('heading',{name:/公司甲/,level:4})).toBeVisible()
    fireEvent.change(screen.getByRole('combobox',{name:'旧答名单公司'}),{target:{value:'symbol1'}})
    expect(screen.getByRole('heading',{name:/公司乙/,level:4})).toBeVisible()
    expect(screen.getByRole('link',{name:'查看原公告 · 第2页 ↗'})).toHaveAttribute('href','https://example.com/1.pdf#page=2')
    fireEvent.click(screen.getByText('这一组价格的口径与来源'))
    expect(screen.getByText(/停牌期间保留缺口/)).toBeVisible()
    expect(screen.getByRole('link',{name:'公司乙行情来源 ↗'})).toBeVisible()
  })
  it.each(['question','run','member','initial','empty'] as const)('hides a cohort with a foreign or incomplete %s binding',kind=>{
    const copy=structuredClone(cohort)
    if(kind==='question')copy.question_id='other'
    if(kind==='run')copy.source_run_id='other'
    if(kind==='member')copy.members[0].timeline.symbol='other'
    if(kind==='initial')copy.members[0].timeline.initial_event_id='missing'
    if(kind==='empty')copy.members=[]
    show(copy);expect(screen.getByText(/对应关系需要重新核对/)).toBeVisible()
    expect(screen.queryByRole('figure')).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })
  it('leaves old reviews without a cohort untouched',()=>{
    const {container}=render(<HistoryAnswerCohort questionId="q" sourceRunId="run"/>)
    expect(container).toBeEmptyDOMElement()
  })
})
