import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STBailiPaymentTerms,bailiPaymentTermsBound} from './STBailiPaymentTerms'
import {STCashReceiptMeaning} from './STCashReceiptMeaning'
import fixture from './__fixtures__/baili-payment-terms.json'
import receipt from './__fixtures__/cash-receipt-meaning.json'
import type {STRegimeData} from './stRegimeTypes'
afterEach(cleanup)
it('separates donation, security and share-subscription payment and refund clauses',()=>{
 render(<STBailiPaymentTerms data={fixture as unknown as STRegimeData}/>)
 fireEvent.click(screen.getByText('百利：赠与、保证金、投资款的付款条件一样吗？'))
 const table=screen.getByRole('table',{name:'同一七名投资人的三类款项，分别看条款'})
 const rows=within(table).getAllByRole('row')
 expect(rows[1]).toHaveTextContent('现金赠与')
 expect(rows[1]).toHaveTextContent('不能套用投资款的批后30工作日')
 expect(rows[2]).toHaveTextContent('5个工作日')
 expect(rows[2]).toHaveTextContent('特定违约情形下可没收')
 expect(rows[3]).toHaveTextContent('法院裁定批准重整计划后')
 expect(rows[3]).toHaveTextContent('30个工作日')
 expect(screen.getByText(/3900万元的对应缺口仍在/).parentElement).toHaveTextContent('不能仅靠整除就认证某期已付清')
 expect(screen.getByText(/已有款项转用途也不是再收到一次现金/)).toHaveTextContent('6,406,277.72元')
 expect(screen.getByText(/这是两份公司公告转述/)).toHaveTextContent('未逐方核生效日')
 expect(screen.getByText(/2028年11月30日前/)).toHaveTextContent('不是承诺法院会在该日受理')
 expect(screen.getByRole('link',{name:'1225507582 · PDF物理第40页 ↗'})).toHaveAttribute('href','https://static.cninfo.com.cn/finalpage/2026-08-26/1225507582.PDF#page=40')
})
it.each(['missing','url','hash','date','pagecount'])('withholds stale terms on source mismatch: %s',kind=>{
 const d=structuredClone(fixture)
 const source=d.themes.twentyseventh_period_followup.sources[1]
 if(kind==='missing')d.themes.twentyseventh_period_followup.sources=[]
 if(kind==='url')source.url='https://example.com/wrong'
 if(kind==='hash')source.sha256='wrong'
 if(kind==='date')source.published_on='2026-11-20'
 if(kind==='pagecount')source.pages=55
 expect(bailiPaymentTermsBound(d as unknown as STRegimeData)).toBe(false)
 render(<STBailiPaymentTerms data={d as unknown as STRegimeData}/>)
 expect(screen.getByRole('status')).toHaveTextContent('暂不显示旧解释')
 expect(screen.queryByRole('table')).not.toBeInTheDocument()
})
it('mounts the clause comparison inside the existing receipt question without replacing the unresolved balance',()=>{
 const d=structuredClone(receipt)
 d.themes.twentyseventh_period_followup.sources=d.themes.twentyseventh_period_followup.sources.filter(s=>!fixture.themes.twentyseventh_period_followup.sources.some(b=>b.announcement_id===s.announcement_id))
 d.themes.twentyseventh_period_followup.sources.push(...fixture.themes.twentyseventh_period_followup.sources)
 render(<STCashReceiptMeaning data={d as unknown as STRegimeData}/>)
 expect(screen.getByText('百利：赠与、保证金、投资款的付款条件一样吗？')).toBeInTheDocument()
 expect(screen.getByText('1.3亿元减3900万元，能直接叫剩余欠款9100万元吗？')).toBeInTheDocument()
})
