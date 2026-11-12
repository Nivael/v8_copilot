import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {SwingWatchSection} from './SwingWatchSection'
import type {SwingReading,SwingRow} from './readingTypes'

afterEach(()=>{cleanup();vi.restoreAllMocks()})
it('connects the previous conclusion to an explicitly dated later observation without certifying a full-horizon result',async()=>{
  const data:SwingReading={availability:'available',as_of:'2026-11-06',start:'2026-09-04',horizon:'1–4周反弹观察',watchlist:[],reading_note:'当前成分的历史价格观察。',rules:{},groups:[{key:'star50',name:'科创50',pool_count:50,observed_count:50,oversold_count:0,early_repair_count:0,rows:[],excluded:[]}],analysis:{headline:'修复条件仍在，回落需要继续确认',summary:'新增一个收盘。',previous_review:{basis_date:'2026-11-05',summary:'不把一天涨跌写成完整反弹结果。',cases:[{symbol:'688629.SH',name:'华丰科技',then_judgment:'此前的原判断',day_change_pct:-3.49,now_judgment:'价格仍符合筛选，财务条件分别检验。'}]}}}
  vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify({availability:'available',data,refresh:{in_progress:false,last_error:null}}),{status:200}))
  render(<SwingWatchSection/>)
  expect(await screen.findByRole('heading',{name:data.analysis!.headline})).toBeVisible()
  expect(screen.getByText('此前的原判断')).not.toBeVisible()
  fireEvent.click(screen.getByText('上次的判断，还成立吗？'))
  expect(screen.getByText('此前的原判断')).toBeVisible()
  expect(screen.getByText('-3.49%')).toBeVisible()
  expect(screen.getByText(/持续跟踪1–4周表现/)).toBeVisible()
  expect(screen.getByText('价格仍符合筛选，财务条件分别检验。')).toBeVisible()
})

it('opens each pool at its researched focus and keeps that stock in the first visible rows',async()=>{
  const row=(symbol:string,name:string):SwingRow=>({symbol,name,as_of:'2026-11-06',close:10,availability:'available',day_change_pct:-1,five_day_change_pct:3,twenty_day_change_pct:-20,from_window_high_pct:-30,from_twenty_day_low_pct:5,five_day_mean_close:9,twenty_day_low_close:8,stage:'early_repair',latest_amount_yuan:20_000_000,path:[],note:{judgment:`${name}的已核判断`,reasons:[],watch_next:[],sources:[]}})
  const stRows=Array.from({length:10},(_,i)=>row(`000${i}.SZ`,`示例${i}`));stRows.push(row('002759.SZ','ST天际'))
  const group=(key:string,name:string,rows:SwingRow[])=>({key,name,pool_count:rows.length,observed_count:rows.length,oversold_count:rows.length,early_repair_count:rows.length,rows,excluded:[]})
  const data:SwingReading={availability:'available',as_of:'2026-11-06',start:'2026-09-04',horizon:'1–4周',watchlist:[],reading_note:'',rules:{},groups:[group('star50','科创50',[row('688629.SH','华丰科技')]),group('st','ST池',stRows)],analysis:{headline:'当前判断',summary:'依据已核事实。',focus_by_group:{star50:'688629.SH',st:'002759.SZ'}}}
  vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify({availability:'available',data,refresh:{in_progress:false,last_error:null}}),{status:200}))
  render(<SwingWatchSection/>)
  await screen.findByRole('heading',{name:'华丰科技的已核判断'})
  fireEvent.click(screen.getByRole('button',{name:'ST池'}))
  expect(screen.getByRole('button',{name:'ST天际'})).toBeVisible()
  expect(screen.getByRole('heading',{name:'ST天际的已核判断'})).toBeVisible()
})
