import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {HistoryEventTimeline} from './HistoryEventTimeline'
import {eventMarkers} from './historyEventMarkers'
import {ReadingChart} from './ReadingChart'
import {first,timeline} from './test/historyEventFixture'

const second=timeline.events[1]
afterEach(cleanup)

describe('source-bound event reading',()=>{
  it('keeps missing windows distinct from measured zero and gives the source and next condition',()=>{
    const select=vi.fn();render(<HistoryEventTimeline timeline={timeline} event={first} onSelect={select} stName="ST参考"/> )
    expect(screen.getByText('已核2条后续或同日记录')).toBeVisible()
    expect(screen.getByRole('link',{name:'查看原公告 · 第2页 ↗'})).toHaveAttribute('href',first.source.url)
    expect(screen.getAllByText('暂无可比价格').length).toBeGreaterThan(0)
    expect(screen.getByText('当前行情档案未覆盖完整窗口',{exact:false})).toBeVisible()
    fireEvent.click(screen.getByText('其他窗口与比较口径'))
    expect(screen.getByText('0.00%')).toBeVisible()
    fireEvent.click(screen.getByText('用哪些 lens 看 · 下一步观察'))
    expect(screen.getByText('股东行为 · 控制权')).toBeVisible()
    expect(screen.getByText(first.watch)).toBeVisible()
    fireEvent.change(screen.getByRole('combobox',{name:'查看历史公告'}),{target:{value:'second'}})
    expect(select).toHaveBeenCalledWith('second')
  })
  it('explicitly separates same-day unknown clocks and pre-question facts',()=>{
    const {rerender}=render(<HistoryEventTimeline timeline={timeline} event={{...first,relation:'same_day'}} onSelect={()=>{}} stName="ST参考"/> )
    expect(screen.getByText(/首发分钟未核/)).toBeVisible()
    rerender(<HistoryEventTimeline timeline={timeline} event={{...first,relation:'before_question'}} onSelect={()=>{}} stName="ST参考"/> )
    expect(screen.getByText(/提问前的背景/)).toBeVisible()
  })
  it('groups every same-day record and preserves selection within a group',()=>{
    const markers=eventMarkers(timeline,second)
    expect(markers).toHaveLength(1);expect(markers[0]).toMatchObject({id:'second',count:2,selected:true})
    expect(markers[0].label).toContain('等2条')
  })
  it('places a weekend disclosure between trading sessions and supports keyboard event selection',()=>{
    const callback=vi.fn(),question=vi.fn()
    render(<ReadingChart label="走势" series={[{key:'stock',name:'个股',change_pct:-2,points:[{date:'2026-06-05',value:100,level:100},{date:'2026-06-08',value:98,level:98}]}]} eventMarkers={eventMarkers(timeline,first)} onEventMarker={callback} markers={[{date:'2026-06-05',id:'q',label:'原提问'}]} onMarker={question}/> )
    const marker=screen.getByRole('button',{name:/公告 2026-06-06/})
    const x=Number(marker.querySelector('path')!.getAttribute('d')!.match(/^M([\d.]+)/)![1])
    expect(x).toBeGreaterThan(54);expect(x).toBeLessThan(920)
    expect(marker).toHaveAttribute('aria-pressed','true')
    fireEvent.keyDown(marker,{key:'Enter'});expect(callback).toHaveBeenCalledWith('first')
    fireEvent.keyDown(screen.getByRole('button',{name:'原提问'}),{key:' '});expect(question).toHaveBeenCalledWith('q')
    expect(within(screen.getByRole('figure')).getByRole('slider')).toHaveAttribute('max','1')
  })
  it('does not move out-of-range announcements onto a nearby stock close',()=>{
    render(<ReadingChart label="走势" series={[{key:'stock',name:'个股',change_pct:0,points:[{date:'2026-06-05',value:100,level:100},{date:'2026-06-08',value:100,level:100}]}]} eventMarkers={[{date:'2026-06-01',id:'old',label:'旧背景',selected:true,count:1},{date:'2026-06-30',id:'future',label:'未来',selected:false,count:1}]}/> )
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
  it('shows a future meeting as planned rather than already held',()=>{
    render(<HistoryEventTimeline timeline={timeline} event={{...first,occurred_on:null,scheduled_for:'2026-06-10'}} onSelect={()=>{}} stName="ST参考"/> )
    expect(screen.getByText(/拟安排于2026-06-10/)).toBeVisible()
    expect(screen.queryByText(/实际发生于2026-06-10/)).not.toBeInTheDocument()
  })
  it('keeps exact financial fields behind an expansion and labels the reporting period',()=>{
    render(<HistoryEventTimeline timeline={timeline} event={{...first,occurred_on:null,report_period_end:'2026-06-30',evidence_detail:'净利润-40870305.02元'}} onSelect={()=>{}} stName="ST参考"/> )
    expect(screen.getByText(/报告期截至2026-06-30/)).toBeVisible()
    expect(screen.getByText('净利润-40870305.02元')).not.toBeVisible()
    fireEvent.click(screen.getByText('其他窗口与比较口径'))
    fireEvent.click(screen.getByText('核对字段与原件说明'))
    expect(screen.getByText('净利润-40870305.02元')).toBeVisible()
  })
})
