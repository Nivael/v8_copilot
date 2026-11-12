import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {HistoryEventTimeline} from './HistoryEventTimeline'
import {eventMarkers} from './historyEventMarkers'
import {ReadingChart} from './ReadingChart'
import {first,timeline} from './test/historyEventFixture'

const second=timeline.events[1]
afterEach(cleanup)

describe('source-bound event reading',()=>{
  it('does not label later available rows as complete disclosure windows when the reference is outside coverage',()=>{
    const event={...first,context:{...first.context,reference_close:null,windows:{'1':{through:'2025-08-01',change_pct:{stock:'1',market:'2',st:'3'}},'5':{through:'2025-08-07',change_pct:{stock:'4',market:'5',st:'6'}}}}}
    render(<HistoryEventTimeline timeline={timeline} event={event} onSelect={()=>{}} stName="ST参考"/>)
    expect(screen.getByText(/披露日前收盘未覆盖/)).toBeVisible()
    fireEvent.click(screen.getByText('其他窗口与比较口径'))
    expect(screen.queryByText('2025-08-01')).not.toBeInTheDocument()
    expect(screen.queryByText('2025-08-07')).not.toBeInTheDocument()
    expect(screen.queryByText('4.00%')).not.toBeInTheDocument()
    expect(screen.getAllByText('待完整窗口行情')).toHaveLength(3)
  })
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
    expect(screen.getByText(/提问前已公开的背景/)).toBeVisible()
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


describe('argument-only event context',()=>{
  it('shows learning without inventing an experience link and labels a pre-question scheduled warning',()=>{
    const event={...first,relation:'before_question' as const,occurred_on:null,scheduled_for:'2026-06-09',scheduled_role:'warning_effective_date' as const}
    const argument={version:'history_event_timeline_v2' as const,assessment_basis:'original_argument_only' as const,question_id:timeline.question_id,symbol:timeline.symbol,initial_event_id:event.id,events:[event],content_digest:'binding',learning:{lesson:'按真实阶段更新',next_check:'补失败与未完成对照'}}
    render(<HistoryEventTimeline timeline={argument} event={event} onSelect={()=>{}} stName="ST参考"/>)
    expect(screen.getByRole('heading',{name:'提问时已经知道什么'})).toBeVisible()
    expect(screen.getByText('已核1条提问前背景')).toBeVisible()
    expect(screen.getByText(/公告安排于2026-06-09实施/)).toBeVisible()
    fireEvent.click(screen.getByText('用哪些 lens 看 · 下一步观察'))
    expect(screen.getByText(/按真实阶段更新/)).toBeVisible()
    expect(screen.getByText(/补失败与未完成对照/)).toBeVisible()
    expect(screen.queryByRole('link',{name:'查看这条复盘方法 ↓'})).not.toBeInTheDocument()
  })
  it('keeps a foreign local occurrence date and explains missing delisted stock prices',()=>{
    const event={...first,occurred_on:'2026-05-27',occurred_date_qualifier:'local_time' as const,price_note:'摘牌后无日线不等于所有账户损失100%。'}
    render(<HistoryEventTimeline timeline={timeline} event={event} onSelect={()=>{}} stName="ST参考"/>)
    expect(screen.getByText(/2026-05-27（当地时间）/)).toBeVisible()
    expect(screen.getByText(event.price_note)).toBeVisible()
  })
})
