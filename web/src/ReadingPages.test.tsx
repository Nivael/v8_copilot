import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {MemoryRouter} from 'react-router-dom'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {MarketOverview} from './MarketOverview'
import {ExperienceHub} from './ExperienceHub'
import {ReadingChart} from './ReadingChart'
import {marketReading,learningReading} from './test/readingFixtures'

const latestPrice:NonNullable<typeof marketReading.latest_price>={availability:'available',as_of:'2026-11-05',headline:'大盘风险仍偏高，短期压力尚在',stance:'弱势判断',summary:'新收盘仍弱，短线反弹未变成近月回升。',metrics:{day_change_pct:-2,five_day_change_pct:3,twenty_day_change_pct:-8},reason:{title:'先看最新的价格方向',text:'新收盘的价格依据。',source_label:'最新收盘原始来源',source_url:'https://www.csindex.com.cn/latest'}}

function serve(data:unknown){return vi.spyOn(globalThis,'fetch').mockImplementation(async input=>new Response(JSON.stringify(String(input).includes('/swing')?{availability:'warming',refresh:{in_progress:false,last_error:null}}:{availability:'available',as_of:'2026-11-04',checked_at:'2026-11-05T16:00:00Z',data,refresh:{in_progress:false,last_error:null}}),{status:200}))}
describe('trader reading pages',()=>{
  afterEach(()=>{cleanup();vi.restoreAllMocks()})
  it('leads with a dated judgment and a paired ST chart, with cash explanation behind disclosure',async()=>{
    const fetch=serve(marketReading)
    render(<MemoryRouter><MarketOverview/></MemoryRouter>)
    expect(await screen.findByRole('heading',{name:marketReading.headline})).toBeVisible()
    expect(screen.getByText('收盘数据截至 2026-11-04')).toBeVisible()
    expect(screen.getByRole('img',{name:/大盘与ST走势比较/})).toBeVisible()
    const disclosure=screen.getByText('怎么看份额、价格和净流入流出？').closest('details')!
    expect(disclosure.open).toBe(false)
    fireEvent.click(screen.getByText('怎么看份额、价格和净流入流出？'))
    expect(screen.getByText('华泰柏瑞沪深300ETF')).toBeVisible()
    expect(screen.getByText(/现金净流入流出金额尚未齐备/)).toBeVisible()
    expect(screen.getByRole('link',{name:'查看跟踪与经验 →'})).toHaveAttribute('href','/learning')
    expect(fetch.mock.calls.every(([url])=>String(url).includes('/workbench/market'))).toBe(true)
  })
  it('connects historical judgment, later price and review, and filters methods by category',async()=>{
    serve(learningReading)
    render(<MemoryRouter><ExperienceHub/></MemoryRouter>)
    expect(await screen.findByRole('heading',{name:'*ST沐邦'})).toBeVisible()
    expect(screen.getByText('保留原提醒，补充市场与同类对照')).toBeVisible()
    expect(screen.getByText('签约不等于正式受理。')).toBeVisible()
    expect(screen.getByText(/此后至2026-11-04，收盘价变化-38.05%/)).toBeVisible()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button',{name:'市场与价格'}))
    expect(screen.getByRole('heading',{name:'对照ST参考'})).toBeVisible()
    expect(screen.queryByRole('heading',{name:'签约和受理分开看'})).not.toBeInTheDocument()
    expect(screen.getByText('待验证')).toBeVisible()
  })
  it('updates the price judgment while dating the older comparison, breadth and ETF separately',async()=>{
    const olderReason={title:'ST同窗观察',text:'ST只比较已经完整的窗口。',source_label:'ST依据',source_url:'/market/evidence'}
    const request=serve({...marketReading,why:[...marketReading.why,olderReason],latest_price:latestPrice})
    render(<MemoryRouter><MarketOverview/></MemoryRouter>)
    expect(await screen.findByRole('heading',{name:latestPrice.headline})).toBeVisible()
    expect(screen.getByText('指数收盘截至 2026-11-05')).toBeVisible()
    expect(screen.getByText('-2.00%')).toBeVisible()
    expect(screen.getByText('-8.00%')).toBeVisible()
    expect(screen.getByText('上涨股票占比（2026-11-04）')).toBeVisible()
    expect(screen.getByText('2026-09-04 — 2026-11-04 · 同期累计涨跌')).toBeVisible()
    expect(screen.getByText('ETF资金观察 · 份额与同窗价格截至2026-11-04')).toBeVisible()
    expect(screen.getByRole('heading',{name:'ST同窗观察 · 截至2026-11-04'})).toBeVisible()
    expect(screen.queryByRole('heading',{name:marketReading.why[0].title})).not.toBeInTheDocument()
    expect(screen.getByRole('link',{name:'最新收盘原始来源 ↗'})).toHaveAttribute('href',latestPrice.reason.source_url)
    expect(request.mock.calls.every(([url,options])=>String(url).includes('/workbench/market')&&!options?.body)).toBe(true)
  })
  it.each(['2026-11-04','2026-11-03'])('keeps the existing judgment when the extra price date is %s',async as_of=>{
    serve({...marketReading,latest_price:{...latestPrice,as_of}})
    render(<MemoryRouter><MarketOverview/></MemoryRouter>)
    expect(await screen.findByText('收盘数据截至 2026-11-04')).toBeVisible()
    expect(screen.getByRole('heading',{name:marketReading.headline})).toBeVisible()
    expect(screen.queryByRole('heading',{name:latestPrice.headline})).not.toBeInTheDocument()
    expect(screen.getByRole('heading',{name:marketReading.why[0].title})).toBeVisible()
  })
  it('returns to the dated common basis when an available reading withdraws the extra price source',async()=>{
    const request=serve({...marketReading,latest_price:latestPrice})
    render(<MemoryRouter><MarketOverview/></MemoryRouter>)
    await screen.findByRole('heading',{name:latestPrice.headline})
    await waitFor(()=>expect(screen.getByRole('button',{name:'刷新判断'})).not.toBeDisabled())
    request.mockImplementation(async()=>new Response(JSON.stringify({availability:'available',data:marketReading,refresh:{in_progress:false,last_error:null}}),{status:200}))
    fireEvent.click(screen.getByRole('button',{name:'刷新判断'}))
    expect(await screen.findByText('收盘数据截至 2026-11-04')).toBeVisible()
    expect(screen.queryByRole('heading',{name:latestPrice.headline})).not.toBeInTheDocument()
  })
  it('uses the same latest market judgment in the learning crosslink without relabeling stock prices or reviews',async()=>{
    serve({...learningReading,market_context:{...marketReading,latest_price:latestPrice}})
    render(<MemoryRouter><ExperienceHub/></MemoryRouter>)
    expect(await screen.findByText(`${latestPrice.headline} · 2026-11-05`)).toBeVisible()
    expect(screen.getByText('保留原提醒，补充市场与同类对照')).toBeVisible()
    expect(screen.getByText('个股跟踪价格截至 2026-11-04')).toBeVisible()
  })
  it('shows a new-price review as pending while retaining the previous review inside an expansion',async()=>{
    const stock=learningReading.cases[0]
    serve({...learningReading,cases:[{...stock,review:null,previous_review:stock.review}]})
    render(<MemoryRouter><ExperienceHub/></MemoryRouter>)
    expect(await screen.findByRole('heading',{name:'需要结合新资料再复盘'})).toBeVisible()
    const details=screen.getByText('查看上一版复盘').closest('details')!
    expect(details.open).toBe(false)
    expect(screen.getByText('保留原提醒，补充市场与同类对照')).not.toBeVisible()
  })
  it('keeps review sources one expansion away from the conclusion',async()=>{
    const stock=learningReading.cases[0]
    serve({...learningReading,cases:[{...stock,review:{...stock.review!,sources:[{label:'控制权变更公告 · 第2页',url:'https://static.cninfo.com.cn/example.pdf#page=2'}]}}]})
    render(<MemoryRouter><ExperienceHub/></MemoryRouter>)
    await waitFor(()=>expect(screen.getByText(stock.review!.assessment)).toBeVisible())
    const disclosure=screen.getByText('这次复盘的依据').closest('details')!
    expect(disclosure.open).toBe(false)
    fireEvent.click(screen.getByText('这次复盘的依据'))
    expect(screen.getByRole('link',{name:'控制权变更公告 · 第2页 ↗'})).toHaveAttribute('href','https://static.cninfo.com.cn/example.pdf#page=2')
  })
  it('keeps the original-question archive closed until the reader opens it',async()=>{
    const request=serve(learningReading)
    render(<MemoryRouter><ExperienceHub/></MemoryRouter>)
    await waitFor(()=>expect(screen.getByRole('button',{name:'同步记录'})).not.toBeDisabled())
    const archive=screen.getByText('原问与历史复盘').closest('details')!
    expect(archive.open).toBe(false)
    expect(request.mock.calls.some(([url])=>String(url).includes('/workbench/history'))).toBe(false)
    fireEvent.click(screen.getByText('原问与历史复盘'))
    await waitFor(()=>expect(archive.open).toBe(true))
    await waitFor(()=>expect(request.mock.calls.some(([url])=>String(url).includes('/workbench/history'))).toBe(true))
  })
  it('keeps classification verification in the source expansion',async()=>{
    serve({...marketReading,source_notes:[{title:'ST收盘分类已交叉核对',text:'名单实际读取于次日。',source_label:'独立名单',source_url:'https://www.szse.cn/source'}]})
    render(<MemoryRouter><MarketOverview/></MemoryRouter>)
    await screen.findByRole('heading',{name:marketReading.headline})
    expect(screen.getByText('名单实际读取于次日。')).not.toBeVisible()
    fireEvent.click(screen.getByText('数据口径与更多来源'))
    expect(screen.getByText('名单实际读取于次日。')).toBeVisible()
    expect(screen.getByRole('link',{name:'独立名单 ↗'})).toHaveAttribute('href','https://www.szse.cn/source')
  })
  it('keeps the last loaded conclusion when the local service fails and permits retry',async()=>{
    const request=serve(marketReading)
    render(<MemoryRouter><MarketOverview/></MemoryRouter>)
    await screen.findByRole('heading',{name:marketReading.headline})
    await waitFor(()=>expect(screen.getByRole('button',{name:'刷新判断'})).not.toBeDisabled())
    request.mockRejectedValue(new Error('连接中断'))
    fireEvent.click(screen.getByRole('button',{name:'刷新判断'}))
    expect(await screen.findByRole('alert')).toHaveTextContent('保留上次判断')
    expect(screen.getByRole('heading',{name:marketReading.headline})).toBeVisible()
  })
  it('supports keyboard date selection and rejects a nonmatching series calendar',()=>{
    render(<ReadingChart label="走势" series={[...marketReading.chart,{key:'wrong',name:'不同日期',change_pct:0,points:[{date:'2026-09-03',value:100,level:100},{date:'2026-11-04',value:100,level:100}]}]}/>)
    expect(screen.queryByText('不同日期')).not.toBeInTheDocument()
    fireEvent.change(screen.getByRole('slider'),{target:{value:'0'}})
    expect(screen.getByRole('slider')).toHaveAttribute('aria-valuetext','2026-09-04')
  })
  it('marks only an assessed cutoff present inside the displayed chart window',()=>{
    const series=marketReading.chart
    const through=series[0].points[0].date
    const view=render(<ReadingChart label="复盘走势" series={series} reviewThrough={through}/>)
    expect(screen.getByText(`复盘截至 ${through}`)).toBeVisible()
    expect(view.container.querySelector('.reading-after-review')).toBeInTheDocument()
    fireEvent.change(screen.getByRole('slider'),{target:{value:'0'}})
    expect(screen.getByRole('slider')).toHaveAttribute('aria-valuetext',through)
    for(const cutoff of ['missing',series[0].points.at(-1)!.date]){
      view.rerender(<ReadingChart label="复盘走势" series={series} reviewThrough={cutoff}/>)
      expect(view.container.querySelector('.reading-review-boundary')).not.toBeInTheDocument()
    }
  })
  it('picks up a newly recorded Codex judgment on focus without submitting another question',async()=>{
    const request=serve(learningReading)
    render(<MemoryRouter><ExperienceHub/></MemoryRouter>)
    await waitFor(()=>expect(screen.getByRole('button',{name:'同步记录'})).not.toBeDisabled())
    const stock=learningReading.cases[0]
    const updated={...learningReading,cases:[{...stock,review:null,history:[{...stock.history[0],judgment:'新记录：继续分别核查受理和资金履约。',full_answer:'新记录：继续分别核查受理和资金履约。'}]}]}
    request.mockImplementation(async()=>new Response(JSON.stringify({availability:'available',data:updated,refresh:{in_progress:false,last_error:null}}),{status:200}))
    fireEvent(window,new Event('focus'))
    const visibleJudgment=await screen.findAllByText('新记录：继续分别核查受理和资金履约。')
    expect(visibleJudgment[0]).toBeVisible()
    expect(screen.getByRole('heading',{name:'需要结合新资料再复盘'})).toBeVisible()
    expect(request.mock.calls.every(([url,options])=>/\/workbench\/(learning|swing|history|st-regime)/.test(String(url))&&!options?.body)).toBe(true)
  })
})
