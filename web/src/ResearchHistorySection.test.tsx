import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {ResearchHistorySection} from './ResearchHistorySection'
import {timeline as eventTimeline} from './test/historyEventFixture'
import type {HistoryDetail,HistoryQuestion} from './researchHistoryTypes'

const dates=['2026-06-01','2026-06-02','2026-06-03','2026-06-04','2026-06-05','2026-06-08','2026-06-09']
const path=(values:number[])=>dates.map((date,i)=>({date,value:values[i],level:values[i]}))
const question:HistoryQuestion={id:'q1',asked_at:'2026-06-02T08:50:00Z',asked_on:'2026-06-02',question:'尾盘偷袭是什么意思？',kind:'original_question',anchor_date:'2026-06-02',basis_note:'最近已完成收盘',categories:['短线量价'],answers:[{text:'原回答：更像洗盘。',summary:'更像洗盘。',truncated:false}],sources:[{kind:'chatgpt',url:'https://chatgpt.com/c/source',title:'宝馨开板分析'}],outcomes:{stock:{five_day:{date:'2026-06-09',change_pct:-20.43}},market:{five_day:{date:'2026-06-09',change_pct:-1.79}},st:{five_day:{date:'2026-06-09',change_pct:-5.69}}},review:{headline:'错误：卖压被解释成洗盘',assessment:'后续方向与原乐观判断不符。',then_quote:'更像洗盘。',lessons:['不由盘口猜资金身份。'],explanation:[{lens:'个股与判断逻辑',text:'公司风险需要公告确认。'}],reviewed_at:'2026-11-06T02:00:00Z'}}
const detail:HistoryDetail={availability:'available',symbol:'002514.SZ',name:'*ST宝馨',as_of:'2026-06-09',questions:[question,{...question,id:'q2',asked_at:'2026-06-03T08:00:00Z',asked_on:'2026-06-03',anchor_date:'2026-06-03',question:'黑历史有哪些？',categories:['财报与监管'],answers:[],review:null}],chart_sources:{stock:path([100,95,90,85,80,77,75]),market:path([100,99,98,98,98,97,97]),st:path([100,99,98,97,96,95,94])},st_name:'ST板块（东财）',st_note:'供应商板块，不拼接自建参考。',source_urls:{st:'https://quote.eastmoney.com/bk/90.BK0511.html'}}
const longQuestion='我想比较沐邦与整个ST板块最近一个月的走势，看看反弹有没有跟上大盘，同时区分它自己的公司风险。尤其想知道公开招募之后的价格变化，是否足以支持此前关于资金集中、核心仓安全的说法；请把当时判断和后续事实分开列出，最后也看看新公告有没有改变结论。'
function serve(custom=detail){return vi.spyOn(globalThis,'fetch').mockImplementation(async input=>{
  const url=String(input);let data:unknown
  if(url.endsWith('/history'))data={availability:'available',as_of:'2026-06-09',stocks:[{symbol:'002514.SZ',name:'*ST宝馨',original_questions:2},{symbol:'603398.SH',name:'*ST沐邦',original_questions:1}],coverage:{original_questions:3,saved_research:1,reviewed_questions:1,stocks:2,source_note:'部分长聊天更早消息待补齐'}}
  else if(url.includes('603398.SH'))data={...detail,symbol:'603398.SH',name:'*ST沐邦',questions:[{...question,id:'mu',question:'财投以后必须涨吗？'}]}
  else data=custom
  return new Response(JSON.stringify({availability:'available',data,refresh:{in_progress:false,last_error:null}}))
})}
afterEach(()=>{cleanup();vi.restoreAllMocks()})
describe('original question retrospective',()=>{
  it('uses the independently bound original period for its chart and source links',async()=>{
    const points=[{date:'2025-09-22',value:10,level:100},{date:'2025-09-23',value:11,level:110}]
    const event={...eventTimeline.events[0],published_on:'2025-09-23',relation:'after_question' as const}
    const timeline={version:'history_event_timeline_v4' as const,assessment_basis:'original_argument_only' as const,question_id:question.id,symbol:detail.symbol,initial_event_id:event.id,events:[event],content_digest:'bound',learning:{lesson:'先核利润传导',next_check:'继续补同业'},question_period:{title:'原问时段',summary:'分别核事实',source_note:'独立前复权窗口；尚缺第二报价来源。',source_refs:[],gap_notes:[],paths:{calendar:points.map(p=>p.date),stocks:{[detail.symbol]:{name:detail.name,points}},market:points,st:points,st_name:detail.st_name}}}
    const q={...question,asked_at:'2025-09-22T10:00:00Z',asked_on:'2025-09-22',anchor_date:'2025-09-22',question_chart_sources:{stock:points,market:points,st:points},question_price_source_note:timeline.question_period.source_note,question_price_source_refs:[{key:'tencent_qfq',title:'腾讯原问行情',url:'https://example.com/original-prices'}],review:{...question.review!,assessment_basis:'original_argument_only' as const,event_timeline:timeline}}
    serve({...detail,stock_history_note:'其他行情的拼接说明',questions:[q]});render(<ResearchHistorySection/>)
    expect(await screen.findByRole('img',{name:/从2025-09-22起的背景走势/})).toBeVisible()
    expect(screen.getByText('涨跌从2025-09-22收盘算起')).toBeVisible()
    expect(screen.getByRole('combobox',{name:'查看历史公告'})).toBeVisible()
    expect(screen.queryByText('当年案例走势')).not.toBeInTheDocument()
    expect(screen.queryByText('其他行情的拼接说明')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('价格口径与来源'))
    expect(screen.getByText(timeline.question_period.source_note)).toBeVisible()
    expect(screen.getByRole('link',{name:'腾讯原问行情 ↗'})).toHaveAttribute('href','https://example.com/original-prices')
    expect(screen.queryByText(/早期价格使用保存的前复权日线，后期按交易所收盘/)).not.toBeInTheDocument()
  })
  it('keeps an older case and its announcements accessible when post-question prices have no anchor',async()=>{
    const oldEvent={...eventTimeline.events[0],published_on:'2021-05-18',occurred_on:null,relation:'before_question' as const,context_period:'case_period' as const}
    const points=[{date:'2021-05-17',value:100,level:100},{date:'2021-05-19',value:106,level:106}]
    const oldTimeline={version:'history_event_timeline_v3' as const,assessment_basis:'original_argument_only' as const,question_id:question.id,symbol:detail.symbol,initial_event_id:oldEvent.id,events:[oldEvent],content_digest:'bound',learning:{lesson:'分别看公开时序',next_check:'继续补后续价格'},case_period:{title:'当年案例走势',summary:'历史机制观察',source_note:'价格变化',source_refs:[],gap_notes:[],paths:{calendar:points.map(p=>p.date),stocks:{[detail.symbol]:{name:detail.name,points}},market:points,st:points,st_name:detail.st_name}}}
    serve({...detail,questions:[{...question,asked_at:'2024-06-01T08:00:00Z',asked_on:'2024-06-01',anchor_date:null,outcomes:{},review:{...question.review!,assessment_basis:'original_argument_only',event_timeline:oldTimeline}}]})
    render(<ResearchHistorySection/>)
    expect(await screen.findByText('当年案例走势')).toBeVisible()
    expect(screen.getByRole('combobox',{name:'查看历史公告'})).toBeVisible()
    expect(screen.getByText('当年案例窗口 · 价格变化，未计现金分红')).toBeVisible()
    expect(screen.getByText(/现有行情尚未覆盖可用的比较起点/)).toBeVisible()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })
  it.each([['plan_only','当时只形成了研究计划，没有完成报告。'],['research_stopped','当时的研究已停止，没有形成完整报告。']] as const)('explains an unfinished %s without inventing an answer',async(status,note)=>{
    const q:HistoryQuestion={...question,answers:[],review:null,original_response_state:{version:'history_original_response_state_v1',status,source_url:'https://chatgpt.com/c/source',observed_label:status==='plan_only'?'Plan edited...':'Research stopped'}}
    serve({...detail,questions:[q]});render(<ResearchHistorySection/>)
    await screen.findByText(note,{selector:'.history-pending'})
    expect(screen.getByText(status==='plan_only'?'原研究 · 只形成计划':'原研究 · 已停止')).toBeVisible()
    expect(screen.getByText(note,{selector:'blockquote'})).toBeVisible()
    expect(screen.queryByText('未找到原回答')).not.toBeInTheDocument()
    expect(screen.queryByText('错误：卖压被解释成洗盘')).not.toBeInTheDocument()
  })
  it('keeps the recovered report scope and original citation index in the expandable answer',async()=>{
    const note='补回已完成内嵌报告的渲染正文；没有取得原生导出文件或原图。'
    const q:HistoryQuestion={...question,answers:[{text:'真实原报告正文',summary:'原报告摘要',truncated:false,binding:'embedded_research_report',capture_note:note,links:[{label:'原报告引用1',url:'https://example.com/original'}]}]}
    serve({...detail,questions:[q]});render(<ResearchHistorySection/>)
    await screen.findByText('当时完成的内嵌研究')
    expect(screen.getByText(note)).not.toBeVisible()
    fireEvent.click(screen.getByText('展开原回答与聊天来源'))
    expect(screen.getByText(note)).toBeVisible()
    expect(screen.getByText('真实原报告正文')).toBeVisible()
    expect(screen.getByRole('link',{name:'原报告引用1 ↗'})).toHaveAttribute('href','https://example.com/original')
  })
  it.each([true,false])('shows a group scope only for an argument review (%s)',async argumentOnly=>{
    const review={...question.review!,focused_symbol:'market',scope_label:'这33家公司的原分组',price_through:detail.as_of,...(argumentOnly?{assessment_basis:'original_argument_only' as const}:{})}
    serve({...detail,questions:[{...question,review,review_focused_name:'大盘与ST'}]});render(<ResearchHistorySection/>)
    await screen.findByText('错误：卖压被解释成洗盘')
    if(argumentOnly){expect(screen.getByText(/范围：这33家公司的原分组/)).toBeVisible();expect(screen.queryByText(/主要评估大盘与ST/)).not.toBeInTheDocument()}
    else{expect(screen.getByText(/主要评估大盘与ST/)).toBeVisible();expect(screen.queryByText(/范围：这33家公司的原分组/)).not.toBeInTheDocument()}
  })
  it('keeps the existing focused-company caption for an argument review without a group label',async()=>{
    serve({...detail,questions:[{...question,review:{...question.review!,assessment_basis:'original_argument_only',focused_symbol:'603398.SH'},review_focused_name:'*ST沐邦'}]});render(<ResearchHistorySection/>)
    expect(await screen.findByText(/主要评估\*ST沐邦/)).toBeVisible()
  })
  it('shows the BSE vendor basis without claiming a later exchange splice or a Tencent history',async()=>{
    const note='本股整段使用东方财富前复权日线，未拼接交易所逐日表。'
    const bse:HistoryDetail={...detail,symbol:'920023.BJ',name:'*ST田野',stock_price_basis_note:note,source_urls:{stock_bse_history:'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.920023'}}
    vi.spyOn(globalThis,'fetch').mockImplementation(async input=>{
      const url=String(input),data=url.endsWith('/history')?{availability:'available',as_of:detail.as_of,stocks:[{symbol:'002514.SZ',name:'*ST宝馨',original_questions:2},{symbol:'920023.BJ',name:'*ST田野',original_questions:1}],coverage:{original_questions:3,saved_research:0,reviewed_questions:1,stocks:2,source_note:'原问题'}}:url.endsWith('920023.BJ')?bse:detail
      return new Response(JSON.stringify({availability:'available',data,refresh:{in_progress:false,last_error:null}}))
    })
    render(<ResearchHistorySection/>);await screen.findByText('错误：卖压被解释成洗盘')
    fireEvent.click(screen.getByText('价格口径与来源'))
    expect(screen.getByText(/早期价格使用保存的前复权日线，后期按交易所收盘/)).toBeVisible()
    fireEvent.change(screen.getByRole('combobox',{name:'历史复盘标的'}),{target:{value:'920023.BJ'}})
    await screen.findByRole('article',{name:'*ST田野历史复盘详情'})
    fireEvent.click(screen.getByText('价格口径与来源'))
    expect(screen.getByText(note)).toBeVisible()
    expect(screen.queryByText(/早期价格使用保存的前复权日线，后期按交易所收盘/)).not.toBeInTheDocument()
    expect(screen.getByRole('link',{name:'北交所补充历史行情（东方财富） ↗'})).toHaveAttribute('href',bse.source_urls.stock_bse_history)
    expect(screen.queryByRole('link',{name:'补充历史行情（腾讯） ↗'})).not.toBeInTheDocument()
  })
  it('does not label a pending post-question price comparison as completed',async()=>{
    const archived:HistoryQuestion={...question,asked_at:'2026-06-10T08:50:00Z',asked_on:'2026-06-10',anchor_date:'2026-06-09',review:null,outcomes:{stock:{latest:{date:'2026-06-09',change_pct:null}}}}
    const original=JSON.stringify(archived)
    serve({...detail,questions:[archived]});render(<ResearchHistorySection/>)
    expect(await screen.findByText('原问题 · 可比行情待补')).toBeVisible()
    expect(screen.getByText('原问题和原回答已保留；可比后续行情仍待补齐，判断也待复核。')).toBeVisible()
    expect(screen.queryByText('原问题 · 走势已对照')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('展开原回答与聊天来源'))
    expect(screen.getByText('原回答：更像洗盘。')).toBeVisible()
    expect(JSON.stringify(archived)).toBe(original)
  })
  it('keeps a measured flat return distinct from missing followup prices',async()=>{
    serve({...detail,questions:[{...question,review:null,outcomes:{stock:{five_day:{date:'2026-06-09',change_pct:0}}}}]})
    render(<ResearchHistorySection/>)
    expect(await screen.findByText('原问题 · 走势已对照')).toBeVisible()
    expect(screen.getByText('后续走势已对照；这条原回答的事实与推理仍待逐项复核。')).toBeVisible()
    expect(screen.queryByText('原问题 · 可比行情待补')).not.toBeInTheDocument()
  })
  it('leads with the corrected judgment, dated original and common-window paths',async()=>{
    const request=serve();render(<ResearchHistorySection/>)
    expect(await screen.findByText('错误：卖压被解释成洗盘')).toBeVisible()
    expect(screen.getByText(/2026\/06\/02 16:50/)).toBeVisible()
    expect(screen.getByRole('img',{name:/从2026-06-02起/})).toBeVisible()
    expect(screen.queryByRole('region',{name:'追问背景'})).not.toBeInTheDocument()
    expect(screen.queryByText('完整原问题')).not.toBeInTheDocument()
    expect(screen.getAllByText('-20.43%')[0]).toBeVisible()
    const source=screen.getByText('展开原回答与聊天来源').closest('details')!
    expect(source.open).toBe(false)
    fireEvent.click(screen.getByText('展开原回答与聊天来源'))
    expect(screen.getByRole('link',{name:'宝馨开板分析 ↗'})).toHaveAttribute('href','https://chatgpt.com/c/source')
    expect(request.mock.calls.every(([,options])=>!options?.body)).toBe(true)
  })
  it('keeps a medium-length question compact with its full words available before the judgment',async()=>{
    expect(longQuestion.length).toBeLessThan(200)
    const original={...question,question:longQuestion},request=serve({...detail,questions:[original]})
    render(<ResearchHistorySection/>);await screen.findByText('错误：卖压被解释成洗盘')
    const article=screen.getByRole('article',{name:'*ST宝馨历史复盘详情'}),heading=within(article).getByRole('heading',{level:3})
    expect(heading.textContent).toMatch(/^我想比较沐邦.*…$/)
    expect(heading.textContent).not.toContain('新公告有没有改变结论')
    const full=within(article).getByText('完整原问题').closest('details')!,content=full.querySelector('p')!
    expect(full.open).toBe(false);expect(content).not.toBeVisible()
    const calls=request.mock.calls.length
    fireEvent.click(within(article).getByText('完整原问题'))
    expect(content).toBeVisible();expect(content.textContent).toBe(longQuestion)
    expect(screen.getByText('错误：卖压被解释成洗盘')).toBeVisible()
    expect(screen.getByRole('img',{name:/从2026-06-02起/})).toBeVisible()
    fireEvent.click(within(article).getByText('完整原问题'));expect(full.open).toBe(false)
    expect(request.mock.calls).toHaveLength(calls);expect(original.question).toBe(longQuestion)
  })
  it('collapses short multiline headings while preserving their original paragraph layout on expansion',async()=>{
    const text='第一行：先看同窗大盘。\n\n第二行：再核个股公告。'
    serve({...detail,questions:[{...question,question:text}]});render(<ResearchHistorySection/>)
    const heading=await screen.findByRole('heading',{name:'第一行：先看同窗大盘。 第二行：再核个股公告。'})
    expect(heading.textContent).not.toMatch(/\n/)
    const full=screen.getByText('完整原问题').closest('details')!;expect(full.open).toBe(false)
    fireEvent.click(screen.getByText('完整原问题'))
    expect(full.querySelector('p')!.textContent).toBe(text)
  })
  it.each(['👩🏽‍💻','🇨🇳'])('does not split the visible %s character when shortening the excerpt',async emoji=>{
    const text='要'.repeat(78)+emoji+'继续检查问题是否完整。'
    serve({...detail,questions:[{...question,question:text}]});render(<ResearchHistorySection/>)
    await screen.findByText('错误：卖压被解释成洗盘')
    const heading=within(screen.getByRole('article',{name:'*ST宝馨历史复盘详情'})).getByRole('heading',{level:3})
    expect(heading.textContent).toBe('要'.repeat(78)+emoji+'…')
    fireEvent.click(screen.getByText('完整原问题'))
    expect(screen.getByText('完整原问题').closest('details')!.querySelector('p')!.textContent).toBe(text)
  })
  it('makes a compact verified background expandable even when it is shorter than the previous cutoff',async()=>{
    const context={version:'history_question_context_v1',question_id:'earlier',question:longQuestion,asked_on:'2026-06-02',source_url:'https://chatgpt.com/c/context'}
    serve({...detail,questions:[{...question,question:'继续看',question_context:context}]});render(<ResearchHistorySection/>)
    const background=await screen.findByRole('region',{name:'追问背景'}),quote=background.querySelector('blockquote')!
    expect(quote.textContent).toMatch(/…$/);expect(quote.textContent).not.toContain('新公告有没有改变结论')
    const full=within(background).getByText('完整背景原问题').closest('details')!;expect(full.open).toBe(false)
    fireEvent.click(within(background).getByText('完整背景原问题'))
    expect(full.querySelector('p')!.textContent).toBe(longQuestion)
    expect(within(background).getByRole('link',{name:'打开这轮原聊天 ↗'})).toHaveAttribute('href',context.source_url)
    expect(context.question).toBe(longQuestion)
  })
  it('finds words outside the visible excerpt without fetching or rewriting the archived question',async()=>{
    const request=serve({...detail,questions:[{...question,question:longQuestion},detail.questions[1]]})
    render(<ResearchHistorySection/>);await screen.findByText('错误：卖压被解释成洗盘')
    const calls=request.mock.calls.length
    fireEvent.change(screen.getByRole('searchbox',{name:'查找历史问题或经验'}),{target:{value:'新公告有没有改变结论'}})
    expect(within(screen.getByRole('complementary',{name:'*ST宝馨历史提问'})).getAllByRole('button')).toHaveLength(1)
    const article=screen.getByRole('article',{name:'*ST宝馨历史复盘详情'})
    expect(within(article).getByRole('heading',{level:3}).textContent).not.toContain('新公告有没有改变结论')
    fireEvent.click(within(article).getByText('完整原问题'))
    expect(within(article).getByText('完整原问题').closest('details')!.querySelector('p')!.textContent).toBe(longQuestion)
    expect(request.mock.calls).toHaveLength(calls)
  })
  it('starts the next question’s complete text folded after switching from an expanded question',async()=>{
    serve({...detail,questions:[{...question,question:longQuestion},{...question,id:'q2',asked_on:'2026-06-03',anchor_date:'2026-06-03',question:'另一个长问题：'+longQuestion}]})
    render(<ResearchHistorySection/>);await screen.findByText('错误：卖压被解释成洗盘')
    fireEvent.click(screen.getByText('完整原问题'));expect(screen.getByText('完整原问题').closest('details')!.open).toBe(true)
    fireEvent.click(within(screen.getByRole('complementary',{name:'*ST宝馨历史提问'})).getByRole('button',{name:/另一个长问题/}))
    const full=screen.getByText('完整原问题').closest('details')!
    expect(full.open).toBe(false);expect(full.querySelector('p')!.textContent).toBe('另一个长问题：'+longQuestion)
    expect(full.querySelector('p')).not.toBeVisible()
  })
  it('switches by question marker and does not fabricate a missing answer',async()=>{
    serve();render(<ResearchHistorySection/>);await screen.findByText('错误：卖压被解释成洗盘')
    const marker=screen.getByRole('button',{name:/2026-06-03 的提问/})
    fireEvent.keyDown(marker,{key:'Enter'})
    expect(screen.getByText('这条原问题尚未找到对应原回答，不补写当时的判断。')).toBeVisible()
    expect(screen.getByRole('img',{name:/从2026-06-03起/})).toBeVisible()
    expect(screen.queryByText('错误：卖压被解释成洗盘')).not.toBeInTheDocument()
  })
  it('navigates an unanswered ask to its verified expanded followup without copying the later answer',async()=>{
    const expanded={...question,id:'expanded',question:'补充后的完整问题',asked_at:'2026-06-03T08:00:00Z',asked_on:'2026-06-03',categories:['财报与监管'],review:{...question.review!,headline:'补充问题的复盘'}}
    const first={...question,id:'first',question:'原来的短问题',answers:[],review:null,unanswered_followup:{version:'history_unanswered_followup_v1' as const,question_id:expanded.id,question:expanded.question,asked_at:expanded.asked_at,asked_on:expanded.asked_on,source_url:'https://chatgpt.com/c/source',target_question_digest:'bound-target'}}
    serve({...detail,questions:[first,expanded]});render(<ResearchHistorySection/>)
    expect(await screen.findByText('这条当时没有单独回复；随后补充的问题已有原回答。')).toBeVisible()
    expect(screen.queryByText('更像洗盘。')).not.toBeInTheDocument()
    fireEvent.change(screen.getByRole('combobox',{name:'历史问题分类'}),{target:{value:'短线量价'}})
    fireEvent.change(screen.getByRole('searchbox',{name:'查找历史问题或经验'}),{target:{value:'2026-06-02'}})
    fireEvent.click(screen.getByRole('button',{name:'查看补充后的提问与原答'}))
    expect(screen.getByText('补充问题的复盘')).toBeVisible()
    expect(screen.getByRole('heading',{name:'补充后的完整问题'})).toBeVisible()
    expect(screen.getByRole('combobox',{name:'历史问题分类'})).toHaveValue('全部')
    expect(screen.getByRole('searchbox',{name:'查找历史问题或经验'})).toHaveValue('')
    expect(screen.queryByText('这条当时未单独作答')).not.toBeInTheDocument()
    expect(first.answers).toEqual([])
  })
  it('does not offer a followup jump when its answered target is absent from the same packet',async()=>{
    const followup={version:'history_unanswered_followup_v1' as const,question_id:'missing',question:'另一个问题',asked_at:question.asked_at!,asked_on:question.asked_on!,source_url:'https://chatgpt.com/c/source',target_question_digest:'bound-target'}
    serve({...detail,questions:[{...question,answers:[],review:null,unanswered_followup:followup}]});render(<ResearchHistorySection/>)
    expect(await screen.findByText('这条原问题尚未找到对应原回答，不补写当时的判断。')).toBeVisible()
    expect(screen.queryByRole('button',{name:'查看补充后的提问与原答'})).not.toBeInTheDocument()
    expect(screen.queryByText('当时未单独回复 · 有补充问答')).not.toBeInTheDocument()
  })
  it('does not call an intraday question’s same-day first close the next day',async()=>{
    serve({...detail,questions:[{...question,asked_at:'2026-06-02T04:00:00Z',answer_completed_at:'2026-06-02T12:05:00+08:00',anchor_date:'2026-06-01',outcomes:{stock:{one_day:{date:'2026-06-02',change_pct:-5}},market:{},st:{}}}]})
    render(<ResearchHistorySection/>);await screen.findByText('错误：卖压被解释成洗盘')
    const article=screen.getByRole('article',{name:'*ST宝馨历史复盘详情'})
    const outcomes=article.querySelector<HTMLElement>('.history-outcomes')!
    expect(within(outcomes).getByText('下一个收盘')).toBeVisible()
    expect(within(outcomes).getByText('2026-06-02')).toBeVisible()
    expect(within(outcomes).getByText('-5.00%')).toBeVisible()
    const reference=within(article).getByText('涨跌从2026-06-01收盘算起')
    expect(reference).toBeVisible()
    expect(within(article).getByText(/数字包含提问前已发生的当日涨跌/)).toBeVisible()
    expect(reference.compareDocumentPosition(outcomes)&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(within(article).queryByText('次日')).not.toBeInTheDocument()
    expect(screen.getByRole('img',{name:/从2026-06-01起/})).toBeVisible()
  })
  it.each(['2026-06-01','2026-06-02'])('explains a post-close answer with the actual %s anchor, including a missing stock close',async anchor_date=>{
    serve({...detail,questions:[{...question,asked_at:'2026-06-02T06:50:00Z',answer_completed_at:'2026-06-02T07:05:00Z',anchor_date}]})
    render(<ResearchHistorySection/>)
    expect(await screen.findByText(`涨跌从${anchor_date}收盘算起`)).toBeVisible()
    expect(screen.getByText('原回答完成于2026/06/02 15:05，采用那时已完成的最近收盘。')).toBeVisible()
    expect(screen.queryByText(/盘中提问：数字/)).not.toBeInTheDocument()
    expect(screen.getAllByText('-20.43%')[0]).toBeVisible()
  })
  it('keeps an overnight answer completion distinct from the earlier question date',async()=>{
    serve({...detail,questions:[{...question,asked_at:'2026-06-01T16:10:00Z',answer_completed_at:'2026-06-02T16:05:00Z'}]})
    render(<ResearchHistorySection/>);await screen.findByText('错误：卖压被解释成洗盘')
    expect(screen.getByText('原回答完成于2026/06/03 00:05，采用那时已完成的最近收盘。')).toBeVisible()
    expect(screen.getByText(/2026\/06\/02 00:10 · 北京时间 · 原提问时间/)).toBeVisible()
    expect(screen.getByText('涨跌从2026-06-02收盘算起')).toBeVisible()
  })
  it.each([
    ['before the open','2026-06-02T01:00:00Z'],
    ['on a non-trading day','2026-06-06T04:00:00Z'],
    ['after the close with no same-day stock price','2026-06-02T08:50:00Z'],
    ['during a stock suspension','2026-06-02T04:00:00Z'],
  ])('does not invent an intraday gain warning %s',async(_label,asked_at)=>{
    serve({...detail,chart_sources:{...detail.chart_sources,stock:detail.chart_sources.stock.map(p=>p.date==='2026-06-02'?{...p,value:null,level:null}:p)},questions:[{...question,asked_at,anchor_date:'2026-06-01'}]})
    render(<ResearchHistorySection/>);await screen.findByText('错误：卖压被解释成洗盘')
    expect(screen.getByText('涨跌从2026-06-01收盘算起')).toBeVisible()
    expect(screen.queryByText(/盘中提问：数字/)).not.toBeInTheDocument()
  })
  it('leaves the comparison start pending instead of making up a date when the anchor is missing',async()=>{
    serve({...detail,questions:[{...question,asked_at:'2025-09-24T01:34:15Z',asked_on:'2025-09-24',anchor_date:null,outcomes:{},review:null}]})
    render(<ResearchHistorySection/>)
    expect(await screen.findByText('现有行情尚未覆盖可用的比较起点，暂不显示后续收益。原问题和原回答已保留。')).toBeVisible()
    expect(screen.getByText('原问题 · 可比行情待补')).toBeVisible()
    expect(screen.queryByText('走势数据正在更新。')).not.toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.queryByText(/涨跌从/)).not.toBeInTheDocument()
    expect(screen.queryByText('-20.43%')).not.toBeInTheDocument()
  })
  it('distinguishes a dated historical price gap from a future horizon and preserves the gap date',async()=>{
    serve({...detail,questions:[{...question,outcomes:{...question.outcomes,stock:{five_day:{date:'2026-06-09',change_pct:null},sixty_day:{date:null,change_pct:null}}}}]})
    render(<ResearchHistorySection/>);await screen.findByText('错误：卖压被解释成洗盘')
    const values=screen.getByRole('article',{name:'*ST宝馨历史复盘详情'}).querySelector<HTMLElement>('.history-outcomes')!
    const historical=within(values).getByText('5个交易日').parentElement!
    expect(within(historical).getByText('暂无可比价格')).toBeVisible()
    expect(within(historical).getByText('2026-06-09')).toBeVisible()
    const future=within(values).getByText('60个交易日').parentElement!
    expect(within(future).getByText('待后续行情')).toBeVisible()
    expect(within(future).getByText('后续收盘待更新')).toBeVisible()
    fireEvent.click(screen.getByText('同一窗口，大盘和ST分别走了多少？'))
    const row=screen.getByRole('row',{name:/5个交易日 暂无可比价格/})
    expect(within(row).getByText('—')).toBeVisible()
    expect(within(row).queryByText('0.00%')).not.toBeInTheDocument()
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
    expect(screen.getByText('涨跌从2026-06-02收盘算起')).toBeVisible()
    expect(screen.getByText('提问时刻不详，这是事后按日线作的比较。')).toBeVisible()
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
  it('opens a complete attachment group in original order and unloads both when collapsed',async()=>{
    const visuals=[0,1].map(index=>({kind:'rendered_capture' as const,sha256:'a'.repeat(64),url:`/api/v1/workbench/history-assets/${index}`,
      width:436,height:1043,captured_at:'2026-11-06T02:00:00Z',source_url:'https://chatgpt.com/c/source',
      attachment_id:`attachment-${index}`,attachment_index:index,attachment_count:2}))
    serve({...detail,questions:[{...question,unavailable_attachments:2,question_visuals:visuals}]})
    render(<ResearchHistorySection/>);await screen.findByText('错误：卖压被解释成洗盘')
    expect(screen.queryByAltText('原聊天附件展示截图')).not.toBeInTheDocument()
    expect(screen.queryByText('这条原问的附件画面待补齐。')).not.toBeInTheDocument()
    const toggle=screen.getByText('当时看到的附件 · 展示截图');fireEvent.click(toggle)
    const images=await screen.findAllByAltText('原聊天附件展示截图')
    expect(images.map(image=>image.getAttribute('src'))).toEqual(visuals.map(visual=>visual.url))
    expect(screen.getByText(/附件 1\/2/)).toBeVisible();expect(screen.getByText(/附件 2\/2/)).toBeVisible()
    fireEvent.click(toggle)
    await waitFor(()=>expect(screen.queryByAltText('原聊天附件展示截图')).not.toBeInTheDocument())
  })
  it('keeps a date-range question readable without assigning it a return or a fake chart',async()=>{
    serve({...detail,questions:[{...question,asked_at:null,asked_on:null,time_precision:'range',asked_from:'2026-06-01',asked_through:'2026-06-04',anchor_date:null,outcomes:{},review:null}]})
    render(<ResearchHistorySection/>)
    expect(await screen.findByRole('region',{name:'提问日期待确认'})).toBeVisible()
    expect(screen.getAllByText('2026-06-01—2026-06-04（日期待确认）')[0]).toBeVisible()
    expect(screen.getByText('当时怎么回答')).toBeVisible()
    expect(screen.getByText('原问题 · 日期待确认')).toBeVisible()
    expect(screen.queryByText(/后续走势已对照/)).not.toBeInTheDocument()
    expect(screen.queryByText('后来怎样了')).not.toBeInTheDocument()
    expect(screen.queryByRole('img',{name:/从/})).not.toBeInTheDocument()
    expect(screen.queryByText('走势数据正在更新。')).not.toBeInTheDocument()
    expect(screen.queryByText('-20.43%')).not.toBeInTheDocument()
  })
  it('keeps a missing attachment visible even when the original question needs no background',async()=>{
    serve({...detail,questions:[{...question,unavailable_attachments:6}]})
    render(<ResearchHistorySection/>)
    expect(await screen.findByText('这条原问的附件画面待补齐。')).toBeVisible()
    expect(screen.queryByAltText('原聊天附件展示截图')).not.toBeInTheDocument()
    expect(screen.queryByRole('region',{name:'追问背景'})).not.toBeInTheDocument()
  })
  it('surfaces missing images declared by a legacy ChatGPT capture without changing the original or loading assets',async()=>{
    const text='这两张图说明什么？\n\n[User attached 2 images; image contents were not included]'
    const original={...question,question:text}
    const request=serve({...detail,questions:[original]});render(<ResearchHistorySection/>)
    expect(await screen.findByText('这条原问的附件画面待补齐。')).toBeVisible()
    expect(screen.getByRole('heading',{name:'这两张图说明什么？'})).toBeVisible()
    expect(screen.queryByAltText('原聊天附件展示截图')).not.toBeInTheDocument()
    expect(original.question).toBe(text)
    expect(request.mock.calls.every(([url])=>!String(url).includes('history-assets'))).toBe(true)
  })
  it('describes a file-only original as a missing file instead of calling it a picture',async()=>{
    serve({...detail,questions:[{...question,question:'[User attached 1 file; file contents were not included]'}]})
    render(<ResearchHistorySection/>)
    expect(await screen.findByText('这条原问的附件文件内容待补齐。')).toBeVisible()
    expect(screen.getByRole('heading',{name:'附件问题（文字档案未包含文件）'})).toBeVisible()
    expect(screen.queryByText('这条原问的附件画面待补齐。')).not.toBeInTheDocument()
    expect(screen.queryByAltText('原聊天附件展示截图')).not.toBeInTheDocument()
  })
  it('puts one combined missing-file-and-image notice beside a short followup’s background',async()=>{
    const context={version:'history_question_context_v1',question_id:'earlier',question:'看这份材料',asked_on:'2026-06-02',source_url:'https://chatgpt.com/c/source'}
    serve({...detail,questions:[{...question,question:'就是这个\n\n[User attached 1 file; file contents were not included]\n[User attached 1 image; image contents were not included]',question_context:context}]})
    render(<ResearchHistorySection/>)
    const background=await screen.findByRole('region',{name:'追问背景'})
    expect(within(background).getByText('这条追问的图片和文件内容待补齐。')).toBeVisible()
    expect(screen.getAllByText('这条追问的图片和文件内容待补齐。')).toHaveLength(1)
  })
  it('keeps an unarchived file visible when the same original already has a verified image preview',async()=>{
    const url='/api/v1/workbench/history-assets/'+'a'.repeat(64)
    serve({...detail,questions:[{...question,question:'看附件\n\n[User attached 1 file; file contents were not included]\n[User attached 1 image; image contents were not included]',unavailable_attachments:1,question_visuals:[{kind:'rendered_capture',sha256:'a'.repeat(64),url,width:436,height:1043,captured_at:'2026-11-06T02:00:00Z',source_url:'https://chatgpt.com/c/source'}]}]})
    render(<ResearchHistorySection/>)
    expect(await screen.findByText('可在下方展开图片展示截图；原文件内容仍待补齐。')).toBeVisible()
    expect(screen.queryByText('这条原问的附件画面待补齐。')).not.toBeInTheDocument()
    expect(screen.queryByAltText('原聊天附件展示截图')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('当时看到的附件 · 展示截图'))
    expect(await screen.findByAltText('原聊天附件展示截图')).toHaveAttribute('src',url)
  })
  it.each([
    '引用：[User attached 2 images; image contents were not included]',
    '> [User attached 2 images; image contents were not included]',
    '```text\n[User attached 2 images; image contents were not included]\n```',
    '```text\n```still quoted\n[User attached 2 images; image contents were not included]\n```',
    '~~~text\n[User attached 2 images; image contents were not included]',
    '[User attached 2 files; image contents were not included]',
    '[User attached 0 images; image contents were not included]',
  ])('does not infer missing pictures from quoted, fenced or invalid annotation text: %s',async text=>{
    serve({...detail,questions:[{...question,question:text}]});render(<ResearchHistorySection/>)
    await screen.findByText('错误：卖压被解释成洗盘')
    expect(screen.queryByText('这条原问的附件画面待补齐。')).not.toBeInTheDocument()
    expect(screen.queryByText('这条原问的附件文件内容待补齐。')).not.toBeInTheDocument()
  })
  it.each(['codex','chatgpt_rendered'])('does not treat a %s message’s quoted ChatGPT-style marker as capture metadata',async kind=>{
    serve({...detail,questions:[{...question,question:'看示例\n\n[User attached 2 images; image contents were not included]',sources:[{...question.sources[0],kind}]}]});render(<ResearchHistorySection/>)
    await screen.findByText('错误：卖压被解释成洗盘')
    expect(screen.queryByText('这条原问的附件画面待补齐。')).not.toBeInTheDocument()
  })
  it('recognizes a real capture annotation after a closed example block',async()=>{
    serve({...detail,questions:[{...question,question:'```text\n示例\n```\n\n[User attached 1 image; image contents were not included]'}]});render(<ResearchHistorySection/>)
    expect(await screen.findByText('这条原问的附件画面待补齐。')).toBeVisible()
  })
  it('does not infer an attachment from an annotation quoted in separately saved research',async()=>{
    serve({...detail,questions:[{...question,kind:'saved_research',question:'看示例\n\n[User attached 2 images; image contents were not included]'}]})
    render(<ResearchHistorySection/>);fireEvent.click(await screen.findByRole('button',{name:'显示保存研究'}))
    expect(screen.getByText(/保存研究时间/)).toBeVisible()
    expect(screen.queryByText('这条原问的附件画面待补齐。')).not.toBeInTheDocument()
  })
  it('finds dated questions and current lessons with combined normalized terms without another request',async()=>{
    const request=serve();render(<ResearchHistorySection/>);await screen.findByText('错误：卖压被解释成洗盘')
    const search=screen.getByRole('searchbox',{name:'查找历史问题或经验'})
    fireEvent.change(search,{target:{value:'２０２６-０６-０２ 资金身份'}})
    expect(screen.getByText('1条记录 · 按提问时间')).toBeVisible()
    expect(screen.getByText('错误：卖压被解释成洗盘')).toBeVisible()
    expect(within(screen.getByRole('complementary',{name:'*ST宝馨历史提问'})).queryByText('黑历史有哪些？')).not.toBeInTheDocument()
    fireEvent.change(search,{target:{value:'黑历史'}})
    expect(screen.getByRole('heading',{name:'黑历史有哪些？'})).toBeVisible()
    expect(screen.queryByText('错误：卖压被解释成洗盘')).not.toBeInTheDocument()
    expect(request.mock.calls).toHaveLength(2)
  })
  it('keeps filters usable when their intersection is empty and restores the selected stock’s records',async()=>{
    serve();render(<ResearchHistorySection/>);await screen.findByText('错误：卖压被解释成洗盘')
    fireEvent.change(screen.getByRole('combobox',{name:'历史问题分类'}),{target:{value:'财报与监管'}})
    fireEvent.change(screen.getByRole('searchbox',{name:'查找历史问题或经验'}),{target:{value:'尾盘'}})
    expect(screen.getByRole('status')).toHaveTextContent('没有符合当前条件的记录。')
    expect(screen.queryByText('这组暂时只有保存的研究题。')).not.toBeInTheDocument()
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button',{name:'重置筛选'}))
    expect(screen.getByRole('searchbox')).toHaveValue('')
    expect(screen.getByRole('combobox',{name:'历史问题分类'})).toHaveValue('全部')
    expect(screen.getByText('2条记录 · 按提问时间')).toBeVisible()
  })
  it('searches verified follow-up background and resets the search on a stock change',async()=>{
    serve({...detail,questions:[{...question,question:'就是这个',question_context:{version:'history_question_context_v1',question_id:'earlier',question:'监管投诉是否影响进度？',asked_on:'2026-06-02',source_url:'https://chatgpt.com/c/source'}}]})
    render(<ResearchHistorySection/>);await screen.findByRole('heading',{name:'就是这个'})
    fireEvent.change(screen.getByRole('searchbox'),{target:{value:'监管投诉'}})
    expect(screen.getByRole('heading',{name:'就是这个'})).toBeVisible()
    fireEvent.change(screen.getByRole('combobox',{name:'历史复盘标的'}),{target:{value:'603398.SH'}})
    expect(await screen.findByRole('heading',{name:'财投以后必须涨吗？'})).toBeVisible()
    expect(screen.getByRole('searchbox')).toHaveValue('')
  })
  it('lazily reads a recovered document and full-size image without replacing the original answer',async()=>{
    const file={media_kind:'document' as const,label:'策略参考',file_name:'playbook.md',sha256:'a'.repeat(64),mime_type:'text/plain',size_bytes:100,captured_at:'2026-11-07T00:00:00Z',source_url:'https://chatgpt.com/c/source',url:'/api/v1/workbench/history-files/'+'a'.repeat(64)}
    const image={...file,media_kind:'image' as const,label:'原候选表',file_name:null,sha256:'b'.repeat(64),mime_type:'image/png',width:1440,height:4206,url:'/api/v1/workbench/history-files/'+'b'.repeat(64)}
    const row={...question,question:'看图与文件\n[User attached 1 file; file contents were not included]\n[User attached 1 image; image contents were not included]',unavailable_attachments:1,question_files:[file,image]},archived=JSON.stringify(row)
    const request=serve({...detail,questions:[row]}),base=request.getMockImplementation()!
    request.mockImplementation((input,options)=>String(input)===file.url?Promise.resolve(new Response('# 原参考\n<script>只是文字</script>')):base(input,options))
    const view=render(<ResearchHistorySection/>);await screen.findByText('已补回当时的附件，可在下方展开。')
    const fileCalls=()=>request.mock.calls.filter(([url])=>String(url)===file.url).length
    expect(screen.queryByAltText(image.label)).not.toBeInTheDocument();expect(fileCalls()).toBe(0)
    fireEvent.click(screen.getByText('当时的附件与参考文件'))
    expect(await screen.findByAltText(image.label)).toHaveAttribute('height','4206');expect(screen.getByAltText(image.label)).toHaveAttribute('src',image.url);expect(fileCalls()).toBe(0)
    fireEvent.click(screen.getByText('展开playbook.md全文'))
    expect(await screen.findByRole('region',{name:'原参考文档全文'})).toHaveTextContent('<script>只是文字</script>')
    expect(view.container.querySelector('script')).not.toBeInTheDocument();expect(fileCalls()).toBe(1)
    expect(screen.getByText('当时的附件与参考文件').closest('details')!.open).toBe(true)
    fireEvent.click(screen.getByText('当时的附件与参考文件'))
    await waitFor(()=>expect(screen.queryByRole('region',{name:'原参考文档全文'})).not.toBeInTheDocument())
    fireEvent.click(screen.getByText('当时的附件与参考文件'));await screen.findByText('展开playbook.md全文')
    expect(screen.getByText('展开playbook.md全文').closest('details')!.open).toBe(false);expect(fileCalls()).toBe(1)
    fireEvent.click(screen.getByText('展开原回答与聊天来源'));expect(screen.getByText('原回答：更像洗盘。')).toBeVisible();expect(JSON.stringify(row)).toBe(archived)
  })
  it('lets a failed document read retry and retains the notice for an unrecovered image',async()=>{
    const file={media_kind:'document' as const,label:'策略参考',file_name:'reference.md',sha256:'a'.repeat(64),mime_type:'text/plain',size_bytes:10,captured_at:'2026-11-07T00:00:00Z',source_url:'https://chatgpt.com/c/source',url:'/api/v1/workbench/history-files/'+'a'.repeat(64)}
    const request=serve({...detail,questions:[{...question,question:'看图与文件\n[User attached 1 file; file contents were not included]\n[User attached 1 image; image contents were not included]',unavailable_attachments:1,question_files:[file]}]}),base=request.getMockImplementation()!
    let attempts=0
    request.mockImplementation((input,options)=>String(input)===file.url?Promise.resolve(++attempts===1?new Response('',{status:404}):new Response('原文已读取')):base(input,options))
    render(<ResearchHistorySection/>);await screen.findByText('这条原问的附件画面待补齐。')
    fireEvent.click(screen.getByText('当时的附件与参考文件'));await screen.findByText('展开reference.md全文')
    fireEvent.click(screen.getByText('展开reference.md全文'));await screen.findByText('文件暂时未能读取，收起后可重新展开。')
    fireEvent.click(screen.getByText('展开reference.md全文'));await waitFor(()=>expect(screen.queryByRole('status')).not.toBeInTheDocument())
    fireEvent.click(screen.getByText('展开reference.md全文'));expect(await screen.findByRole('region',{name:'原参考文档全文'})).toHaveTextContent('原文已读取');expect(attempts).toBe(2)
  })
  it('shows a date-range argument review without claiming an assessed return window',async()=>{
    const review={...question.review!,assessment_basis:'original_argument_only' as const,headline:'不能由盘口确认资金意图',assessment:'原答的推断缺少证据。'}
    serve({...detail,questions:[{...question,asked_at:null,asked_on:null,time_precision:'range',asked_from:'2026-06-01',asked_through:'2026-06-04',anchor_date:null,outcomes:{},review,review_status:'argument_only'}]})
    render(<ResearchHistorySection/>)
    expect(await screen.findByText('仅复核判断依据 · 未评估交易回报')).toBeVisible()
    expect(screen.getByText('不能由盘口确认资金意图')).toBeVisible()
    expect(screen.getByText('已复核判断依据 · 未评估回报')).toBeVisible()
    expect(screen.getByRole('region',{name:'提问日期待确认'})).toBeVisible()
    expect(screen.queryByRole('img',{name:/从/})).not.toBeInTheDocument()
    expect(screen.queryByText('后来怎样了')).not.toBeInTheDocument()
    expect(screen.queryByText('价格口径与来源')).not.toBeInTheDocument()
    expect(screen.queryByText(/复盘窗口截至/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('为什么这样判断 · 原答与依据'))
    expect(screen.getByText(/本条只核对原答的依据与推理，未用价格涨跌验收/)).toBeVisible()
  })
  it('can show dated price observations separately from an argument-only judgment',async()=>{
    serve({...detail,questions:[{...question,review:{...question.review!,assessment_basis:'original_argument_only'},review_status:'argument_only'}]})
    const view=render(<ResearchHistorySection/>)
    expect(await screen.findByText('仅复核判断依据 · 未评估交易回报')).toBeVisible()
    expect(screen.getByRole('img',{name:/从2026-06-02起/})).toBeVisible()
    expect(screen.getByRole('heading',{name:'同期价格背景'})).toBeVisible()
    expect(screen.getByText('这里只展示该股的同期价格，未用这些涨跌验证本条判断的回报。')).toBeVisible()
    expect(view.container.querySelector('.history-outcomes')).not.toBeInTheDocument()
    expect(screen.queryByText('后来怎样了')).not.toBeInTheDocument()
    expect(screen.queryByText(/复盘窗口截至/)).not.toBeInTheDocument()
    expect(screen.queryByText(/有更长走势可继续复盘/)).not.toBeInTheDocument()
  })
  it.each(['argument-only','price-reviewed','unreviewed'] as const)('keeps index context distinct from individual returns for a %s market question',async mode=>{
    const original:HistoryQuestion={...question,id:'screening',question:'比较美芝、帅电和三六五',review:mode==='unreviewed'?null:{...question.review!,price_through:detail.as_of,...(mode==='argument-only'?{assessment_basis:'original_argument_only' as const}:{})},review_status:mode==='argument-only'?'argument_only':mode==='unreviewed'?'not_reviewed':'current'}
    const archived=JSON.stringify(original)
    const market={...detail,symbol:'market',name:'大盘、ST与待定位问题',questions:[original],chart_sources:{market:detail.chart_sources.market,st:detail.chart_sources.st}}
    vi.spyOn(globalThis,'fetch').mockImplementation(async input=>new Response(JSON.stringify({availability:'available',data:String(input).endsWith('/history')?{
      availability:'available',as_of:detail.as_of,stocks:[{symbol:'002514.SZ',name:'*ST宝馨',original_questions:1},{symbol:'market',name:market.name,original_questions:1}],coverage:{original_questions:2,saved_research:0,reviewed_questions:1,stocks:1,source_note:'原问已归档'}
    }:String(input).includes('/history/market')?market:detail,refresh:{in_progress:false,last_error:null}})))
    const view=render(<ResearchHistorySection/>)
    await screen.findByText('错误：卖压被解释成洗盘')
    expect(view.container.querySelector('.history-outcomes')!.children).toHaveLength(5)
    expect(screen.getByRole('heading',{name:'后来怎样了'})).toBeVisible()
    fireEvent.change(screen.getByRole('combobox',{name:'历史复盘标的'}),{target:{value:'market'}})
    expect(await screen.findByRole('heading',{name:'同期市场背景'})).toBeVisible()
    expect(screen.getByText('这里只对照大盘和ST，不代表原问所提个股或组合的回报。')).toBeVisible()
    expect(screen.getByRole('img',{name:/背景走势/})).toBeVisible()
    expect(view.container.querySelector('.history-outcomes')).not.toBeInTheDocument()
    expect(screen.queryByText('后来怎样了')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('同期大盘与ST数值'))
    const table=within(screen.getByText('同期大盘与ST数值').closest('details')!).getByRole('table')
    expect(within(table).getAllByRole('columnheader').map(cell=>cell.textContent)).toEqual(['窗口','中证全指',detail.st_name])
    expect(within(table).getByText('-1.79%')).toBeVisible()
    expect(within(table).getByText('-5.69%')).toBeVisible()
    expect(JSON.stringify(original)).toBe(archived)
    fireEvent.change(screen.getByRole('combobox',{name:'历史复盘标的'}),{target:{value:'002514.SZ'}})
    await screen.findByRole('heading',{name:'后来怎样了'})
    expect(view.container.querySelector('.history-outcomes')!.children).toHaveLength(5)
    expect(view.container.querySelector('.history-outcomes')).toHaveTextContent('-20.43%')
  })
  it('shows an uncertain question interval over contextual prices without choosing a return anchor',async()=>{
    serve({...detail,questions:[{...question,asked_at:null,asked_on:null,time_precision:'range',asked_from:'2026-06-02',asked_through:'2026-06-04',range_context:{kind:'pre_range_common_close',reference_date:'2026-06-01'},anchor_date:null,outcomes:{},review:{...question.review!,assessment_basis:'original_argument_only'},review_status:'argument_only'}]})
    const view=render(<ResearchHistorySection/>)
    expect(await screen.findByRole('img',{name:/提问区间与价格观察/})).toBeVisible()
    expect(screen.getByRole('group',{name:'可能提问区间：2026-06-02至2026-06-04'})).toBeVisible()
    expect(screen.getByText(/观察参照：2026-06-01收盘＝100/)).toBeVisible()
    expect(screen.getByText('仅复核判断依据 · 未评估交易回报')).toBeVisible()
    expect(view.container.querySelector('.history-outcomes')).not.toBeInTheDocument()
    expect(view.container.querySelector('.reading-question-marker')).not.toBeInTheDocument()
    expect(screen.queryByText(/复盘窗口截至/)).not.toBeInTheDocument()
    expect(view.container.querySelector('.reading-chart-legend strong')).toHaveTextContent('75.00')
    fireEvent.click(screen.getByText('价格口径与来源'))
    expect(screen.getByRole('link',{name:'ST板块行情 ↗'})).toBeVisible()
  })
  it.each(['2026-06-02','2026-06-04'])('rejects a visual reference inside the possible ask interval: %s',reference_date=>{
    serve({...detail,questions:[{...question,asked_at:null,asked_on:null,time_precision:'range',asked_from:'2026-06-02',asked_through:'2026-06-04',range_context:{kind:'pre_range_common_close',reference_date},anchor_date:null,outcomes:{},review:null}]})
    render(<ResearchHistorySection/>)
    return screen.findByRole('region',{name:'提问日期待确认'}).then(region=>{
      expect(within(region).getByText(/尚缺区间之前共同有效的收盘参照/)).toBeVisible()
      expect(screen.queryByRole('img',{name:/价格观察/})).not.toBeInTheDocument()
      expect(screen.queryByText('价格口径与来源')).not.toBeInTheDocument()
    })
  })
  it('withdraws a changed argument scope without attributing it to a price correction',async()=>{
    serve({...detail,questions:[{...question,review:null,previous_review:{...question.review!,assessment_basis:'original_argument_only'},review_status:'review_basis_changed'}]})
    render(<ResearchHistorySection/>)
    expect(await screen.findByText('复盘范围或依据已改变，需要重新复盘。')).toBeVisible()
    expect(screen.queryByText('复盘用到的历史价格已更正，需要重新复盘。')).not.toBeInTheDocument()
    const toggle=screen.getByText('此前复盘（依据已变）')
    expect(toggle.closest('details')!.open).toBe(false)
    fireEvent.click(toggle)
    expect(screen.getByText(/该版仅复核判断依据，未评估交易回报/)).toBeVisible()
  })
  it('connects original, corrected old study and replacement across filters without promoting the old assertion',async()=>{
    const correction={old_run_id:'old-study',replacement_run_id:'new-study',original_question_id:'q1',headline:'原答已经列出长期借款',summary:'遗漏批评已经撤回，重新细化借款口径。',corrected_at:'2026-06-09T00:00:00Z'}
    const original:HistoryQuestion={...question,research_corrections:[{...correction,role:'original_review'}]}
    const old:HistoryQuestion={...question,id:'old-study',kind:'saved_research',outcomes:{stock:{}},question:'旧研究误称没有列长期借款',categories:['财报与监管'],review:null,answers:[{text:'这是已撤回的旧研究断言。',summary:'这是已撤回的旧研究断言。',truncated:false}],research_corrections:[{...correction,role:'corrected_study'}]}
    const replacement:HistoryQuestion={...old,id:'new-study',question:'重新核对年报的借款口径',answers:[{text:'修正后的事实核对。',summary:'修正后的事实核对。',truncated:false}],research_corrections:[{...correction,role:'replacement_study'}]}
    const records=[original,old,replacement],before=JSON.stringify(records),request=serve({...detail,questions:records})
    render(<ResearchHistorySection/>);await screen.findByRole('region',{name:'研究更正'})
    const calls=request.mock.calls.length
    fireEvent.change(screen.getByRole('combobox',{name:'历史问题分类'}),{target:{value:'短线量价'}})
    fireEvent.change(screen.getByRole('searchbox',{name:'查找历史问题或经验'}),{target:{value:'遗漏批评已经撤回'}})
    expect(screen.getByRole('checkbox',{name:'同时显示保存的研究题'})).not.toBeChecked()
    expect(screen.getByRole('region',{name:'研究更正'}).querySelector('details')!.open).toBe(false)
    fireEvent.click(screen.getByText('展开原因与原文'))
    fireEvent.click(screen.getByRole('button',{name:'查看修正后的研究'}))
    expect(screen.getByRole('heading',{name:'重新核对年报的借款口径'})).toBeVisible()
    expect(screen.queryByText('后续走势已对照；这条原回答的事实与推理仍待逐项复核。')).not.toBeInTheDocument()
    expect(screen.getByText('行情尚未覆盖这份研究保存后的交易日。可回到当时的原问题查看价格过程。')).toBeVisible()
    expect(screen.queryByText('走势数据正在更新。')).not.toBeInTheDocument()
    expect(screen.getByRole('checkbox',{name:'同时显示保存的研究题'})).toBeChecked()
    expect(screen.getByRole('searchbox')).toHaveValue('')
    expect(screen.getByRole('combobox',{name:'历史问题分类'})).toHaveValue('全部')
    fireEvent.click(screen.getByRole('button',{name:'查看旧研究原文'}))
    expect(screen.getByText('这份旧研究有更正')).toBeVisible()
    expect(screen.getByText(/内容曾作更正/)).toBeVisible()
    expect(screen.queryByText(/旧研究题目含已撤回前提/)).not.toBeInTheDocument()
    expect(screen.getByText('这是已撤回的旧研究断言。')).not.toBeVisible()
    expect(screen.queryByText('后续走势已对照；这条原回答的事实与推理仍待逐项复核。')).not.toBeInTheDocument()
    const oldText=screen.getByText('展开旧研究原文（含已更正内容）').closest('details')!
    expect(oldText.open).toBe(false);fireEvent.click(screen.getByText('展开旧研究原文（含已更正内容）'))
    expect(screen.getByText('这是已撤回的旧研究断言。')).toBeVisible()
    fireEvent.click(screen.getByRole('button',{name:'回到当时的原问题'}))
    expect(screen.getByText('这条复盘曾作更正')).toBeVisible()
    expect(screen.getByRole('heading',{name:question.question})).toBeVisible()
    expect(request.mock.calls).toHaveLength(calls)
    expect(JSON.stringify(records)).toBe(before)
  })

})


describe('event timeline inside the original question',()=>{
  it('connects selection and the chart while keeping the original question reference',async()=>{
    const reviewed={...question,review:{...question.review!,event_timeline:{...eventTimeline,question_id:question.id}}}
    serve({...detail,questions:[reviewed,detail.questions[1]]});render(<ResearchHistorySection/> )
    const select=await screen.findByRole('combobox',{name:'查看历史公告'})
    expect(screen.getByText('涨跌从2026-06-02收盘算起')).toBeVisible()
    fireEvent.change(select,{target:{value:'second'}})
    expect(within(screen.getByRole('article',{name:'选中公告的判断变化'})).getByRole('heading',{name:'同日披露财报'})).toBeVisible()
    expect(screen.getByRole('button',{name:/公告 2026-06-06/})).toHaveAttribute('aria-pressed','true')
    fireEvent.click(screen.getByRole('button',{name:/2026-06-03 黑历史有哪些/}))
    expect(screen.queryByRole('combobox',{name:'查看历史公告'})).not.toBeInTheDocument()
    expect(screen.getByText('涨跌从2026-06-03收盘算起')).toBeVisible()
  })
})


describe('group argument timeline projection',()=>{
  it.each([true,false])('accepts v2 only on an argument-only review: %s',async argumentOnly=>{
    const base={question_id:eventTimeline.question_id,symbol:eventTimeline.symbol,initial_event_id:eventTimeline.initial_event_id,events:eventTimeline.events,content_digest:eventTimeline.content_digest}
    const t={...base,version:'history_event_timeline_v2' as const,assessment_basis:'original_argument_only' as const,question_id:question.id,learning:{lesson:'阶段比标签重要',next_check:'继续追交割'}}
    serve({...detail,questions:[{...question,review:{...question.review!,event_timeline:t,...(argumentOnly?{assessment_basis:'original_argument_only' as const}:{})}}]})
    render(<ResearchHistorySection/>);await screen.findAllByText('错误：卖压被解释成洗盘')
    if(argumentOnly){
      expect(screen.getByRole('combobox',{name:'查看历史公告'})).toBeVisible()
      expect(screen.queryByText('原问后1日')).not.toBeInTheDocument()
      fireEvent.click(screen.getByText('用哪些 lens 看 · 下一步观察'))
      expect(screen.getByText(/阶段比标签重要/)).toBeVisible()
    }else expect(screen.queryByRole('combobox',{name:'查看历史公告'})).not.toBeInTheDocument()
  })
})

describe('original attachment preview quality',()=>{
  it('keeps a low resolution connector preview distinct from an original readable download',async()=>{
    const file={media_kind:'image' as const,source_mode:'connector_preview' as const,label:'美芝原附件预览（低清长图，小字未核清）',file_name:'original.jpeg',sha256:'a'.repeat(64),mime_type:'image/jpeg',size_bytes:72908,width:130,height:1536,captured_at:'2026-11-07T08:00:00Z',source_url:'https://chatgpt.com/c/source',url:'/api/v1/workbench/history-files/preview'}
    serve({...detail,questions:[{...question,question_files:[file],unavailable_attachments:1}]});render(<ResearchHistorySection/>);
    expect(await screen.findByText(/已找回当时的低清附件预览/)).toBeVisible()
    expect(screen.queryByRole('img',{name:file.label})).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('当时的附件与参考文件'))
    expect(screen.getByText(/保留从原聊天找回的附件副本/)).toBeVisible()
    expect(await screen.findByRole('img',{name:file.label})).toHaveAttribute('width','130')
    expect(screen.queryByText(/保留原聊天中下载的副本/)).not.toBeInTheDocument()
  })
})
