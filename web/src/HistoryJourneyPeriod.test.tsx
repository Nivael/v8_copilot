import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {HistoryJourneyPeriod} from './HistoryJourneyPeriod'
import type {HistoryEventTimeline as Timeline} from './researchHistoryTypes'
import {first,timeline} from './test/historyEventFixture'

const dates=['2026-06-04','2026-06-05','2026-06-08']
const points=dates.map((date,i)=>({date,value:i===1?null:100+i,level:i===1?null:100+i}))
const period={title:'查看完整研究旅程',summary:'分别看事件与大盘',source_note:'609天交叉核对；价格变化不等于总回报',source_refs:[{key:'quotes',title:'原始报价',url:'https://example.com/quotes'}],gap_notes:[{date:'2026-06-05',reason:'公告安排停牌一天',support_kind:'verified_suspension' as const,url:'https://example.com/notice.pdf'}],paths:{calendar:dates,stocks:{'002514.SZ':{name:'案例公司',points}},market:points.map(p=>({...p,value:100,level:100})),st:points.map(p=>({...p,value:100,level:100})),st_name:'ST板块（东财）'}}
const value:Timeline={...timeline,version:'history_event_timeline_v7',experience_id:'EXP-'+'A'.repeat(20),question_period:period}
afterEach(cleanup)
describe('full journey alongside an original question',()=>{
  it.each(['history_event_timeline_v6','history_event_timeline_v7'] as const)('loads %s only on expansion and keeps gaps and event selection',version=>{
    const choose=vi.fn()
    const t:Timeline=version==='history_event_timeline_v7'?value:{...timeline,version,assessment_basis:'question_followthrough',learning:{lesson:'核真实履约',next_check:'补其他案例'},question_period:period}
    render(<HistoryJourneyPeriod timeline={t} event={first} onSelect={choose} askedOn="2026-06-02"/>)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    const details=screen.getByText(period.title).closest('details')!
    details.open=true;fireEvent(details,new Event('toggle'))
    expect(screen.getByRole('img',{name:/案例公司完整研究旅程走势/})).toBeVisible()
    expect(screen.getByText(/原问提出于2026-06-02；下方问后曲线仍保留自己的起算日/)).toBeVisible()
    expect(screen.getByText(/曲线空档表示缺少可用报价/)).toBeVisible()
    fireEvent.keyDown(screen.getByRole('button',{name:/公告 2026-06-06/}),{key:'Enter'})
    expect(choose).toHaveBeenCalledWith(first.id)
    fireEvent.click(screen.getByText('整段价格的口径与来源'))
    expect(screen.getByRole('link',{name:'停牌公告 ↗'})).toHaveAttribute('href','https://example.com/notice.pdf')
    expect(screen.getByRole('link',{name:'原始报价 ↗'})).toBeVisible()
    expect(screen.getByRole('img')).toBeVisible()
    details.open=false;fireEvent(details,new Event('toggle'))
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })
  it('adds no full-journey disclosure to older timeline versions',()=>{
    render(<HistoryJourneyPeriod timeline={timeline} onSelect={()=>{}} askedOn="2026-06-02"/>)
    expect(screen.queryByText(period.title)).not.toBeInTheDocument()
  })
})
