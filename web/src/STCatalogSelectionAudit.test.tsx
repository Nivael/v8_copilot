import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STCatalogSelectionAudit,STCatalogCaseUpdate,catalogCaseBound} from './STCatalogSelectionAudit'
import {STTwentysecondPeriodFollowup} from './STTwentysecondPeriodFollowup'
import type {TwentysecondPeriodFollowup} from './STTwentysecondPeriodFollowup'
import sixteenth from './__fixtures__/sixteenth-period-followup.json'
import twentyfirst from './__fixtures__/twentyfirst-period-followup.json'
import twentysecond from './__fixtures__/twentysecond-period-followup.json'
import type {STRegimeData} from './stRegimeTypes'
afterEach(cleanup)
const snapshot='e0ed59aa8cc346fc45349f5daac23d091211c82c145b91c38d031e47579e612f'
const data=()=>({content_digest:snapshot,themes:{sixteenth_period_followup:sixteenth,twentyfirst_period_followup:twentyfirst,twentysecond_period_followup:twentysecond}} as unknown as STRegimeData)
it('keeps 84-company saved-query scope and 8 title leads separate from confirmed omissions or independent cases',()=>{
 render(<STCatalogSelectionAudit data={data()}/>)
 const region=screen.getByRole('region',{name:'保存目录与选源完整性核对'})
 expect(region).toHaveTextContent('84家公司的138页保存目录')
 expect(region).toHaveTextContent('3126条去重记录')
 expect(region).toHaveTextContent('另66家尚未纳入这批保存目录核对')
 expect(region).toHaveTextContent('未命中也不证明没有遗漏')
 fireEvent.click(screen.getByText('查看8条原始线索及当前处理状态'))
 const table=screen.getByRole('table',{name:'选源核对线索，不是8个独立新事件'})
 expect(within(table).getAllByRole('row')).toHaveLength(9)
 expect(table).toHaveTextContent('正文已补核：原募投终止并拟改投收购，非全部业务终止')
 expect(table).toHaveTextContent('正文已补核：保荐核查意见，不替代股东会或交割')
 fireEvent.click(screen.getByText('已核三条：分别改变了什么？'))
 expect(screen.getByRole('complementary',{name:'600818目录正文补核'})).toHaveTextContent('原件补强，原判断保留')
 expect(screen.getByRole('complementary',{name:'603008目录正文补核'})).toHaveTextContent('个人债务集中清理')
})
it('withholds frozen audit totals when the source snapshot changes',()=>{
 const d=data();d.content_digest='different'
 render(<STCatalogSelectionAudit data={d}/>)
 expect(screen.getByRole('status')).toHaveTextContent('暂不显示旧统计')
 expect(screen.queryByRole('region',{name:'保存目录与选源完整性核对'})).not.toBeInTheDocument()
})
it.each(['source','chain'])('withholds case followup when existing case binding changes: %s',kind=>{
 const d=structuredClone(twentysecond)
 if(kind==='source')d.sources=d.sources.map(s=>s.symbol==='603008'?{...s,url:'https://example.com/wrong'}:s)
 else d.chains=d.chains.map(c=>c.chain.startsWith('603008-')?{...c,open:'different'}:c)
 expect(catalogCaseBound(d,'603008')).toBe(false)
 render(<STCatalogCaseUpdate symbol="603008" context={d}/>)
 expect(screen.getByRole('status')).toHaveTextContent('暂不显示新解释')
})
it('qualifies the old legal-person pre-reorganization description and preserves saved input',()=>{
 const d=structuredClone(twentysecond);const before=JSON.stringify(d)
 render(<STTwentysecondPeriodFollowup data={d as unknown as TwentysecondPeriodFollowup}/>)
 fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value:'603008'}})
 expect(screen.getByRole('complementary',{name:'603008目录正文补核'})).toBeVisible()
 expect(screen.getAllByText(/华易智能制造、华瀚投资两法人仍为预重整/).length).toBeGreaterThan(0)
 expect(JSON.stringify(d)).toBe(before)
})
it('does not invent a status note for an unrelated company',()=>{
 render(<STCatalogCaseUpdate symbol="600965" context={twentysecond}/>)
 expect(screen.queryByRole('complementary')).not.toBeInTheDocument()
 expect(screen.queryByRole('status')).not.toBeInTheDocument()
})

it('separates five body reviews from execution and preserves source identity conflicts',()=>{
 render(<STCatalogSelectionAudit data={data()}/>);
 fireEvent.click(screen.getByText('后续补核五份：哪些不是新的终止事件？'))
 expect(screen.getByText(/目录简称\*ST明德，PDF为明德生物/)).toBeVisible()
 expect(screen.getByText(/本件不证明已结算实付/)).toBeVisible()
 expect(screen.getByText(/本轮5份共41页，核14关键图像页/)).toBeVisible()
 expect(screen.getByText(/末页签章日期为空/)).toBeVisible()
})

it('shows current coverage without turning mixed-date totals or zero title leads into completeness',()=>{
 render(<STCatalogSelectionAudit data={data()}/>);
 expect(screen.getByText(/当前目录覆盖90／150家公司/)).toBeVisible()
 fireEvent.click(screen.getByText('90家覆盖了哪段日期，为什么不是统一窗口公告总数？'))
 expect(screen.getByText(/原84家查询从7月4日开始，新增6家从7月1日开始/)).toBeVisible()
 expect(screen.getByText(/未选命中为0，不意味着零遗漏/)).toBeVisible()
 expect(screen.getByText(/尚未纳入的60家公司/)).toBeVisible()
})
