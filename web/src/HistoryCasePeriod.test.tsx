import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {HistoryCasePeriod} from './HistoryCasePeriod'
import {HistoryEventTimeline} from './HistoryEventTimeline'
import type {HistoryEventTimeline as Timeline} from './researchHistoryTypes'
import {first,timeline} from './test/historyEventFixture'

const dates=['2021-05-17','2021-05-18','2021-05-19']
const points=[{date:dates[0],value:100,level:100},{date:dates[1],value:null,level:null},{date:dates[2],value:106,level:106}]
const historical={...first,id:'historical',published_on:'2021-05-18',occurred_on:null,relation:'before_question' as const,context_period:'case_period' as const,title:'撤销风险警示',context:{...first.context,reference_close:'2021-05-18'}}
const value:Timeline={version:'history_event_timeline_v3',assessment_basis:'original_argument_only',question_id:'q',symbol:'002514.SZ',initial_event_id:'historical',content_digest:'bound',events:[historical,first],learning:{lesson:'节点与价格先后分别核',next_check:'补失败对照'},case_period:{title:'当年案例走势 · 2020—2021',summary:'拍卖前已涨，摘帽后仍涨',source_note:'前复权只比较变化，保留停牌空档',source_refs:[{key:'source',title:'历史价格来源',url:'https://example.com/source'}],gap_notes:[{date:'2021-05-18',reason:'停牌一天',url:'https://example.com/notice.pdf'}],paths:{calendar:dates,stocks:{'002514.SZ':{name:'案例公司',points}},market:points.map(p=>({...p,value:100,level:100})),st:points.map(p=>({...p,value:100,level:100})),st_name:'ST板块（东财）'}}}
afterEach(cleanup)

describe('separate historical case period',()=>{
  it('mounts the historical chart only after expansion and links its event to the selected announcement',()=>{
    const choose=vi.fn()
    render(<HistoryCasePeriod timeline={value} event={historical} onSelect={choose} askedOn="2026-06-01"/>)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    const details=screen.getByText(value.case_period.title).closest('details')!
    details.open=true;fireEvent(details,new Event('toggle'))
    expect(screen.getByText(/原问题提出于2026-06-01/)).toBeVisible()
    expect(screen.getByRole('img',{name:/案例公司当年案例走势/})).toBeVisible()
    expect(screen.getByRole('slider')).toHaveAttribute('max','2')
    expect(screen.getByText(/曲线空档表示当日无有效成交价格/)).toBeVisible()
    expect(screen.queryByRole('button',{name:/公告 2026-06-06/})).not.toBeInTheDocument()
    fireEvent.keyDown(screen.getByRole('button',{name:/公告 2021-05-18/}),{key:'Enter'})
    expect(choose).toHaveBeenCalledWith('historical')
    details.open=false;fireEvent(details,new Event('toggle'))
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })
  it('does not add a historical case chart to a legacy timeline',()=>{
    render(<HistoryCasePeriod timeline={timeline} onSelect={()=>{}} askedOn="2026-06-01"/>)
    expect(screen.queryByText(/当年案例走势/)).not.toBeInTheDocument()
  })
  it('labels the historical announcement window and keeps missing prices separate from zero',()=>{
    render(<HistoryEventTimeline timeline={value} event={historical} onSelect={()=>{}} stName="ST板块（东财）"/>)
    expect(screen.getByText('当年案例窗口 · 价格变化，未计现金分红')).toBeVisible()
    expect(screen.getByText(/从2021-05-18收盘起/)).toBeVisible()
    expect(screen.getAllByText('暂无可比价格').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByText('用哪些 lens 看 · 下一步观察'))
    expect(screen.getByText('节点与价格先后分别核')).toBeVisible()
    expect(screen.queryByRole('link',{name:/查看这条复盘方法/})).not.toBeInTheDocument()
  })
})
