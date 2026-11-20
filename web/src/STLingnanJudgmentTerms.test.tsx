import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,expect,it} from 'vitest'
import {STLingnanJudgmentTerms} from './STLingnanJudgmentTerms'
afterEach(cleanup)
it('separates bond amount, shared fees and subtotal from actual payment or a calendar deadline',()=>{
 render(<STLingnanJudgmentTerms/>);
 const table=screen.getByRole('table',{name:'岭南判项金额构成'})
 expect(within(table).getByText('376,991,941.00元')).toBeInTheDocument()
 expect(table).toHaveTextContent('450,000.00元');expect(table).toHaveTextContent('100,478.93元');expect(table).toHaveTextContent('377,542,419.93元')
 expect(screen.getByText(/不是从公告日直接数七日/)).toBeInTheDocument()
 expect(screen.getByText(/不能再把标题金额当第四笔相加/)).toBeInTheDocument()
 expect(table).toHaveTextContent('四被告共同支付；不能按四家各加一遍')
})
it('keeps the plaintiff request and judgment interest bases distinct without inventing interest or payment',()=>{
 render(<STLingnanJudgmentTerms/>);fireEvent.click(screen.getByText('原告诉请与判项，哪里不同？'))
 expect(screen.getByText(/377,003,241.00元/)).toHaveTextContent('11,300.00元')
 expect(screen.getByText(/诉请按6%/)).toHaveTextContent('8月22日')
 const table=screen.getByRole('table',{name:'判项资金占用利息分段'});expect(table).toHaveTextContent('2024-08-22');expect(table).toHaveTextContent('376,991,941.00元');expect(table).toHaveTextContent('实际清偿日')
 expect(screen.getByText(/不计算截至今日的占用利息总额/)).toBeInTheDocument()
 expect(screen.getByRole('link',{name:'判项第2—4页 ↗'})).toHaveAttribute('href','https://static.cninfo.com.cn/finalpage/2026-10-28/1225632581.PDF#page=2')
})
it('does not turn receivable caps or an issuer notice into recovered cash or a court original',()=>{
 render(<STLingnanJudgmentTerms/>);fireEvent.click(screen.getByText('优先受偿权与资产价值，怎样分开？'))
 const table=screen.getByRole('table',{name:'判项应收账款金额上限'});expect(table).toHaveTextContent('103,201,445.57元');expect(table).toHaveTextContent('260,175,412.47元')
 expect(screen.getByText(/上限不是已收回金额/)).toBeInTheDocument()
 fireEvent.click(screen.getByText('这次补到的是什么原件？'));expect(screen.getByText(/不是法院出具的判决书原始文件/)).toBeVisible()
 expect(screen.getByText(/不能从10月28日公告日推算已经生效/)).toBeVisible()
})
