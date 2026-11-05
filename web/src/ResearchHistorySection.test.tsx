import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {ResearchHistorySection} from './ResearchHistorySection'
import type {HistoryDetail,HistoryQuestion} from './researchHistoryTypes'

const dates=['2026-06-01','2026-06-02','2026-06-03','2026-06-04','2026-06-05','2026-06-08','2026-06-09']
const path=(values:number[])=>dates.map((date,i)=>({date,value:values[i],level:values[i]}))
const question:HistoryQuestion={id:'q1',asked_at:'2026-06-02T08:50:00Z',asked_on:'2026-06-02',question:'尾盘偷袭是什么意思？',kind:'original_question',anchor_date:'2026-06-02',basis_note:'最近已完成收盘',categories:['短线量价'],answers:[{text:'原回答：更像洗盘。',summary:'更像洗盘。',truncated:false}],sources:[{kind:'chatgpt',url:'https://chatgpt.com/c/source',title:'宝馨开板分析'}],outcomes:{stock:{five_day:{date:'2026-06-09',change_pct:-20.43}},market:{five_day:{date:'2026-06-09',change_pct:-1.79}},st:{five_day:{date:'2026-06-09',change_pct:-5.69}}},review:{headline:'错误：卖压被解释成洗盘',assessment:'后续方向与原乐观判断不符。',then_quote:'更像洗盘。',lessons:['不由盘口猜资金身份。'],explanation:[{lens:'个股与判断逻辑',text:'公司风险需要公告确认。'}],reviewed_at:'2026-11-06T02:00:00Z'}}
const detail:HistoryDetail={availability:'available',symbol:'002514.SZ',name:'*ST宝馨',as_of:'2026-06-09',questions:[question,{...question,id:'q2',asked_at:'2026-06-03T08:00:00Z',asked_on:'2026-06-03',anchor_date:'2026-06-03',question:'黑历史有哪些？',categories:['财报与监管'],answers:[],review:null}],chart_sources:{stock:path([100,95,90,85,80,77,75]),market:path([100,99,98,98,98,97,97]),st:path([100,99,98,97,96,95,94])},st_name:'ST板块（东财）',st_note:'供应商板块，不拼接自建参考。',source_urls:{st:'https://quote.eastmoney.com/bk/90.BK0511.html'}}
function serve(){return vi.spyOn(globalThis,'fetch').mockImplementation(async input=>{
  const url=String(input);let data:unknown
  if(url.endsWith('/history'))data={availability:'available',as_of:'2026-06-09',stocks:[{symbol:'002514.SZ',name:'*ST宝馨',original_questions:2},{symbol:'603398.SH',name:'*ST沐邦',original_questions:1}],coverage:{original_questions:3,saved_research:1,reviewed_questions:1,stocks:2,source_note:'部分长聊天更早消息待补齐'}}
  else if(url.includes('603398.SH'))data={...detail,symbol:'603398.SH',name:'*ST沐邦',questions:[{...question,id:'mu',question:'财投以后必须涨吗？'}]}
  else data=detail
  return new Response(JSON.stringify({availability:'available',data,refresh:{in_progress:false,last_error:null}}))
})}
describe('original question retrospective',()=>{
  afterEach(()=>{cleanup();vi.restoreAllMocks()})
  it('leads with the corrected judgment, dated original and common-window paths',async()=>{
    const request=serve();render(<ResearchHistorySection/>)
    expect(await screen.findByText('错误：卖压被解释成洗盘')).toBeVisible()
    expect(screen.getByText(/2026\/06\/02 16:50/)).toBeVisible()
    expect(screen.getByRole('img',{name:/从2026-06-02起/})).toBeVisible()
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
})
