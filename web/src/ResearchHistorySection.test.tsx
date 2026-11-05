import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {ResearchHistorySection} from './ResearchHistorySection'
import type {HistoryDetail,HistoryQuestion} from './researchHistoryTypes'

const dates=['2026-06-01','2026-06-02','2026-06-03','2026-06-04','2026-06-05','2026-06-08','2026-06-09']
const path=(values:number[])=>dates.map((date,i)=>({date,value:values[i],level:values[i]}))
const question:HistoryQuestion={id:'q1',asked_at:'2026-06-02T08:50:00Z',asked_on:'2026-06-02',question:'尾盘偷袭是什么意思？',kind:'original_question',anchor_date:'2026-06-02',basis_note:'最近已完成收盘',categories:['短线量价'],answers:[{text:'原回答：更像洗盘。',summary:'更像洗盘。',truncated:false}],sources:[{kind:'chatgpt',url:'https://chatgpt.com/c/source',title:'宝馨开板分析'}],outcomes:{stock:{five_day:{date:'2026-06-09',change_pct:-20.43}},market:{five_day:{date:'2026-06-09',change_pct:-1.79}},st:{five_day:{date:'2026-06-09',change_pct:-5.69}}},review:{headline:'错误：卖压被解释成洗盘',assessment:'后续方向与原乐观判断不符。',then_quote:'更像洗盘。',lessons:['不由盘口猜资金身份。'],explanation:[{lens:'个股与判断逻辑',text:'公司风险需要公告确认。'}],reviewed_at:'2026-11-06T02:00:00Z'}}
const detail:HistoryDetail={availability:'available',symbol:'002514.SZ',name:'*ST宝馨',as_of:'2026-06-09',questions:[question,{...question,id:'q2',asked_at:'2026-06-03T08:00:00Z',asked_on:'2026-06-03',anchor_date:'2026-06-03',question:'黑历史有哪些？',categories:['财报与监管'],answers:[],review:null}],chart_sources:{stock:path([100,95,90,85,80,77,75]),market:path([100,99,98,98,98,97,97]),st:path([100,99,98,97,96,95,94])},st_name:'ST板块（东财）',st_note:'供应商板块，不拼接自建参考。',source_urls:{st:'https://quote.eastmoney.com/bk/90.BK0511.html'}}
function serve(custom=detail){return vi.spyOn(globalThis,'fetch').mockImplementation(async input=>{
  const url=String(input);let data:unknown
  if(url.endsWith('/history'))data={availability:'available',as_of:'2026-06-09',stocks:[{symbol:'002514.SZ',name:'*ST宝馨',original_questions:2},{symbol:'603398.SH',name:'*ST沐邦',original_questions:1}],coverage:{original_questions:3,saved_research:1,reviewed_questions:1,stocks:2,source_note:'部分长聊天更早消息待补齐'}}
  else if(url.includes('603398.SH'))data={...detail,symbol:'603398.SH',name:'*ST沐邦',questions:[{...question,id:'mu',question:'财投以后必须涨吗？'}]}
  else data=custom
  return new Response(JSON.stringify({availability:'available',data,refresh:{in_progress:false,last_error:null}}))
})}
describe('original question retrospective',()=>{
  afterEach(()=>{cleanup();vi.restoreAllMocks()})
  it('leads with the corrected judgment, dated original and common-window paths',async()=>{
    const request=serve();render(<ResearchHistorySection/>)
    expect(await screen.findByText('错误：卖压被解释成洗盘')).toBeVisible()
    expect(screen.getByText(/2026\/06\/02 16:50/)).toBeVisible()
    expect(screen.getByRole('img',{name:/从2026-06-02起/})).toBeVisible()
    expect(screen.queryByRole('region',{name:'追问背景'})).not.toBeInTheDocument()
    expect(screen.getAllByText('-20.43%')[0]).toBeVisible()
    const source=screen.getByText('展开原回答与聊天来源').closest('details')!
    expect(source.open).toBe(false)
    fireEvent.click(screen.getByText('展开原回答与聊天来源'))
    expect(screen.getByRole('link',{name:'宝馨开板分析 ↗'})).toHaveAttribute('href','https://chatgpt.com/c/source')
    expect(request.mock.calls.every(([,options])=>!options?.body)).toBe(true)
  })
  it('switches by question marker and does not fabricate a missing answer',async()=>{
    serve();render(<ResearchHistorySection/>);await screen.findByText('错误：卖压被解释成洗盘')
    const marker=screen.getByRole('button',{name:/2026-06-03 的提问/})
    fireEvent.keyDown(marker,{key:'Enter'})
    expect(screen.getByText('这条原问题尚未找到对应原回答，不补写当时的判断。')).toBeVisible()
    expect(screen.getByRole('img',{name:/从2026-06-03起/})).toBeVisible()
    expect(screen.queryByText('错误：卖压被解释成洗盘')).not.toBeInTheDocument()
  })
  it('changes stock without leaving another stock’s answer under its name and filters by lens',async()=>{
    serve();render(<ResearchHistorySection/>);await screen.findByText('错误：卖压被解释成洗盘')
    fireEvent.change(screen.getByRole('combobox',{name:'历史问题分类'}),{target:{value:'财报与监管'}})
    expect(within(screen.getByRole('complementary',{name:'*ST宝馨历史提问'})).queryByRole('button',{name:/尾盘/})).not.toBeInTheDocument()
    fireEvent.change(screen.getByRole('combobox',{name:'历史复盘标的'}),{target:{value:'603398.SH'}})
    await waitFor(()=>expect(screen.getByRole('heading',{name:'财投以后必须涨吗？'})).toBeVisible())
    expect(screen.queryByRole('article',{name:'*ST宝馨历史复盘详情'})).not.toBeInTheDocument()
  })
  it('shows date-only follow-ups without a made-up clock and labels a shared final answer',async()=>{
    serve({...detail,questions:[{...question,asked_at:null,time_precision:'day',answers:[{...question.answers[0],binding:'shared_turn_answer',source_question_ids:['q1','q2']}]}]})
    render(<ResearchHistorySection/>)
    expect(await screen.findByText(/2026-06-02 · 具体时刻未归档/)).toBeVisible()
    expect(screen.getByText('该轮最终回答（多条提问共同归档）')).toBeVisible()
    expect(screen.queryByText(/1970/)).not.toBeInTheDocument()
    expect(screen.getByText(/具体时刻不详，以2026-06-02收盘作事后比较/)).toBeVisible()
  })
  it('keeps the assessed date explicit when the chart gains later observations',async()=>{
    serve({...detail,questions:[{...question,review_status:'new_observations',review:{...question.review!,price_through:'2026-06-05',focused_symbol:'603398.SH'},review_focused_name:'*ST沐邦'}]})
    render(<ResearchHistorySection/>)
    expect(await screen.findByText(/复盘窗口截至 2026-06-05 · 主要评估\*ST沐邦/)).toBeVisible()
    expect(screen.getByText(/图表已延伸至2026-06-09/)).toBeVisible()
    expect(screen.getByText('复盘截至 2026-06-05')).toBeVisible()
    expect(screen.getByText('错误：卖压被解释成洗盘')).toBeVisible()
    expect(screen.getAllByText('-20.43%')[0]).toBeVisible()
  })
  it.each(['price_changed','original_changed'] as const)('withdraws a changed %s assessment and keeps the old text collapsed',async review_status=>{
    serve({...detail,questions:[{...question,review:null,previous_review:question.review!,review_status}]})
    render(<ResearchHistorySection/>)
    const previous=await screen.findByText('此前复盘（依据已变）')
    expect(previous.closest('details')!.open).toBe(false)
    expect(screen.getByText('错误：卖压被解释成洗盘')).not.toBeVisible()
    expect(screen.getByText(/需要重新复盘/)).toBeVisible()
    fireEvent.click(previous)
    expect(screen.getByText('错误：卖压被解释成洗盘')).toBeVisible()
  })
  it('identifies supplemental stock history separately from the ST benchmark inside sources',async()=>{
    serve({...detail,stock_history_note:'完整历史窗口已与重叠价格核对。',source_urls:{...detail.source_urls,stock_history:'https://example.test/qfq'}})
    render(<ResearchHistorySection/>);await screen.findByText('错误：卖压被解释成洗盘')
    expect(screen.getByText('完整历史窗口已与重叠价格核对。')).not.toBeVisible()
    fireEvent.click(screen.getByText('价格口径与来源'))
    expect(screen.getByText('完整历史窗口已与重叠价格核对。')).toBeVisible()
    expect(screen.getByRole('link',{name:'补充历史行情（腾讯） ↗'})).toHaveAttribute('href','https://example.test/qfq')
  })
  it('makes a brief follow-up readable while retaining its literal words and missing-image boundary',async()=>{
    const context={version:'history_question_context_v1',question_id:'earlier',question:'这份材料是否影响后续进度？',asked_on:'2026-06-02',source_url:'https://chatgpt.com/c/source'}
    serve({...detail,questions:[{...question,question:'就是这个',asked_at:null,time_precision:'day',question_context:context,unavailable_attachments:1}]})
    render(<ResearchHistorySection/>);await screen.findByRole('heading',{name:'就是这个'})
    const background=screen.getByRole('region',{name:'追问背景'})
    expect(within(background).getByText(context.question)).toBeVisible()
    expect(within(background).getByRole('link',{name:'打开这轮原聊天 ↗'})).toHaveAttribute('href',context.source_url)
    expect(within(background).getByText('这条追问附有原图，文字档案未包含图片。')).toBeVisible()
    expect(within(screen.getByRole('complementary',{name:'*ST宝馨历史提问'})).getByText(/这轮在问：这份材料/)).toBeVisible()
    expect(screen.getByText(/具体时刻未归档/)).toBeVisible()
  })
  it('keeps a long background question expandable',async()=>{
    serve({...detail,questions:[{...question,question:'继续看',question_context:{version:'history_question_context_v1',question_id:'earlier',question:'背景原文。'.repeat(60),asked_on:'2026-06-02',source_url:'https://chatgpt.com/c/source'}}]})
    render(<ResearchHistorySection/>);await screen.findByRole('region',{name:'追问背景'})
    const full=screen.getByText('完整背景原问题');expect(full.closest('details')!.open).toBe(false)
    fireEvent.click(full);expect(screen.getByText('背景原文。'.repeat(60))).toBeVisible()
  })
  it('only mounts an archived attachment after expansion and labels it as a rendered capture',async()=>{
    const url='/api/v1/workbench/history-assets/'+'a'.repeat(64)
    serve({...detail,questions:[{...question,question_visuals:[{kind:'rendered_capture',sha256:'a'.repeat(64),url,width:436,height:1043,captured_at:'2026-11-06T02:00:00Z',source_url:'https://chatgpt.com/c/source'}]}]})
    render(<ResearchHistorySection/>);await screen.findByText('错误：卖压被解释成洗盘')
    const toggle=screen.getByText('当时看到的附件 · 展示截图'),disclosure=toggle.closest('details')!
    expect(disclosure.open).toBe(false)
    expect(screen.queryByAltText('原聊天附件展示截图')).not.toBeInTheDocument()
    fireEvent.click(toggle)
    expect(await screen.findByAltText('原聊天附件展示截图')).toHaveAttribute('src',url)
    expect(screen.getByText(/不是原始文件，也不代表截图中的说法已核实/)).toBeVisible()
    expect(screen.getByRole('img',{name:'原聊天附件展示截图'}).closest('a')).toHaveAttribute('href',url)
    fireEvent.click(toggle)
    await waitFor(()=>expect(screen.queryByAltText('原聊天附件展示截图')).not.toBeInTheDocument())
  })
})
