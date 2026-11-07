import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {MemoryRouter} from 'react-router-dom'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {BroadETFSection} from './BroadETFSection'
import {SwingWatchSection} from './SwingWatchSection'
import {ExperienceHub} from './ExperienceHub'
import {learningReading} from './test/readingFixtures'
import type {BroadETFReading,SwingReading,SwingRow} from './readingTypes'

const note={judgment:'等回踩确认',reasons:['价格转强，仍需看公司事实'],watch_next:['不要再创新低'],sources:[{label:'公司三季报',url:'https://www.cninfo.com.cn/filing'}]}
const row:SwingRow={symbol:'688629.SH',name:'华丰科技',as_of:'2026-11-05',availability:'available',close:71.6,day_change_pct:1,five_day_change_pct:6.64,twenty_day_change_pct:-26.53,from_window_high_pct:-30,from_twenty_day_low_pct:16,five_day_mean_close:66.256,twenty_day_low_close:61.72,stage:'early_repair',latest_amount_yuan:20000000,path:[{date:'2026-11-04',close:70,level:100},{date:'2026-11-05',close:71.6,level:102.28}],note}
const swing:SwingReading={availability:'available',as_of:'2026-11-05',start:'2026-09-07',horizon:'1–4周反弹观察',analysis:{headline:'先等回踩，ST暂缓新增',summary:'公司事实与价格一起看。',preferred_symbol:row.symbol},groups:[{key:'star50',name:'科创50',pool_count:50,observed_count:50,oversold_count:9,early_repair_count:2,excluded:[],rows:Array.from({length:9},(_,i)=>({...row,symbol:`68862${i}.SH`,name:i===9?'其他样本':i===0?'华丰科技':`样本${i}`}))},{key:'st',name:'ST池',pool_count:195,observed_count:191,oversold_count:1,early_repair_count:1,excluded:[{name:'停牌样本',availability:'not_trading'}],rows:[{...row,name:'*ST沐邦',symbol:'603398.SH',note:undefined}]}],rules:{twenty_day_change_lte_pct:-15,from_window_high_lte_pct:-20,five_day_change_lte_pct:15,from_twenty_day_low_lte_pct:20,latest_amount_gte_yuan:10000000,latest_close_gte_yuan:1},reading_note:'用当前成员与同窗行情观察。',watchlist:[]}

describe('trader capital and rebound views',()=>{
  afterEach(()=>{cleanup();vi.restoreAllMocks()})
  it('keeps a current conclusion visible and lets the user inspect candidates and sources on demand',async()=>{
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify({availability:'available',data:swing,refresh:{in_progress:false,last_error:null}})))
    render(<SwingWatchSection/> );expect(await screen.findByRole('heading',{name:'先等回踩，ST暂缓新增'})).toBeVisible()
    expect(screen.getByText('等回踩确认')).toBeVisible()
    expect(screen.queryByRole('button',{name:'样本8'})).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button',{name:'展开全部9只'}));expect(screen.getByRole('button',{name:'样本8'})).toBeVisible()
    expect(screen.getByRole('link',{name:'公司三季报 ↗',hidden:true})).not.toBeVisible()
    fireEvent.click(screen.getByText('这条判断的依据'));expect(screen.getByRole('link',{name:'公司三季报 ↗'})).toBeVisible()
    fireEvent.click(screen.getByRole('button',{name:'ST池'}))
    expect(screen.getByRole('button',{name:'*ST沐邦'})).toBeVisible()
    expect(screen.getByText(/公司最新事项还需要进一步核查/)).toBeVisible()
    expect(screen.getByText(/1只停牌或行情不齐/)).toBeVisible()
  })
  it('separates the latest four-stock close from the older common market chart',async()=>{
    const cases=[['603398.SH','*ST沐邦'],['600363.SH','ST联光'],['002667.SZ','*ST威领'],['688053.SH','ST思科瑞']].map(([symbol,name])=>({...learningReading.cases[0],symbol,name,last_close:6.34,latest_quote:{as_of:'2026-11-05',close:6.34,day_change_pct:4.1,five_day_change_pct:3.59,twenty_day_change_pct:-18.5,stage:'early_repair'},current_observation:note}))
    vi.spyOn(globalThis,'fetch').mockImplementation(async input=>new Response(JSON.stringify(String(input).includes('/swing')?{availability:'warming',refresh:{in_progress:false,last_error:null}}:{availability:'available',as_of:'2026-11-05',data:{...learningReading,cases},refresh:{in_progress:false,last_error:null}})))
    render(<MemoryRouter><ExperienceHub/></MemoryRouter>)
    expect(await screen.findByText('价格截至 2026-11-05')).toBeVisible()
    const watch=screen.getByRole('group',{name:'持续跟踪个股'})
    expect(within(watch).getAllByRole('button')).toHaveLength(4)
    fireEvent.click(within(watch).getByRole('button',{name:/ST思科瑞/}))
    expect(screen.getByRole('heading',{name:'ST思科瑞'})).toBeVisible()
    expect(screen.getByText(/当日 .*2026-11-05/)).toBeVisible()
    expect(screen.getByText('与大盘、ST作同期对照 · 截至2026-11-04').closest('details')!.open).toBe(false)
    expect(within(screen.getByRole('article',{name:'ST思科瑞持续跟踪'})).getByRole('heading',{name:'等回踩确认'})).toBeVisible()
  })
  it('shows institution action conclusions with dated identity and source detail behind an expansion',()=>{
    const broad:BroadETFReading={availability:'available',as_of:'2026-11-04',start:'2026-09-04',headline:'份额增加',interpretation:'价格仍弱',institution_reading:'总份额不能确定买家身份',sample_funds:2,source_url:'https://www.sse.com.cn/',groups:[{name:'科创50',sample_count:2,increasing_5d:2,decreasing_5d:0,five_day_price_change_pct:-1.36,twenty_day_price_change_pct:-17.29,reading:'样本份额都增加，价格尚未同步回升',source_url:'https://www.csindex.com.cn/',funds:[]}],capital_actions:{headline:'险资有明确增持',summary:'先看已披露动作',actions:[{name:'太保系',date:'2026-10-30',judgment:'增持发生在港股',detail:'寿险及资产管理产品增持',scope:'单次H股交易',sources:[{label:'举牌公告',url:'https://example.com/disclosure'}]}]}}
    render(<BroadETFSection data={broad}/> )
    expect(screen.getByText('增持发生在港股')).toBeVisible()
    expect(screen.getByText('2026-10-30')).toBeVisible()
    expect(screen.getByText('寿险及资产管理产品增持')).not.toBeVisible()
    fireEvent.click(screen.getByText('具体动作与来源'))
    expect(screen.getByText('寿险及资产管理产品增持')).toBeVisible()
    expect(screen.getByRole('link',{name:'举牌公告 ↗'})).toHaveAttribute('href','https://example.com/disclosure')
  })
})
