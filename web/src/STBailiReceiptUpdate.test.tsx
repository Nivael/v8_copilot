import {MemoryRouter,Route,Routes} from 'react-router-dom'
import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STBailiReceiptUpdate} from './STBailiReceiptUpdate'
import {STCashReceiptMeaning} from './STCashReceiptMeaning'
import {STTwentyseventhPeriodFollowup} from './STTwentyseventhPeriodFollowup'
import type {TwentyseventhPeriodFollowup} from './STTwentyseventhPeriodFollowup'
import receipt from './__fixtures__/cash-receipt-meaning.json'
import period from './__fixtures__/twentyseventh-period-followup.json'
import type {STRegimeData} from './stRegimeTypes'
afterEach(cleanup)
it('states issuer-confirmed receipts and first-stage fulfillment while retaining specific missing evidence',()=>{
 render(<STBailiReceiptUpdate/>)
 const notice=screen.getByRole('complementary',{name:'百利赠与收款补证更正'})
 expect(notice).toHaveTextContent('截至2026年10月30日')
 expect(notice).toHaveTextContent('第一笔、第二笔赠与款合计7500万元')
 expect(notice).toHaveTextContent('各赠与人已按期履行首期付款义务')
 expect(notice).toHaveTextContent('剩余算术差额改为5500万元')
 expect(notice).toHaveTextContent('不能相加成1.14亿元')
 expect(notice).toHaveTextContent('第一笔、第二笔各自金额、付款人和精确到账日仍未分列')
 expect(notice).toHaveTextContent('该公告披露时仍未获法院裁定受理')
 expect(within(notice).getByRole('link',{name:'1225654047 · 收款公告物理第2页 ↗'})).toHaveAttribute('href','https://static.cninfo.com.cn/finalpage/2026-11-03/1225654047.PDF#page=2')
})
it('updates the current receipt table instead of merely appending new numbers beside stale latest totals',()=>{
 const d=structuredClone(receipt);const before=JSON.stringify(d)
 render(<STCashReceiptMeaning data={d as unknown as STRegimeData}/>)
 const rows=within(screen.getByRole('table',{name:'三种实收：补偿、项目销售与资本支持'})).getAllByRole('row')
 expect(rows[3]).toHaveTextContent('两笔赠与合计7500万元')
 expect(rows[3]).toHaveTextContent('剩余差额5500万元')
 expect(rows[3]).not.toHaveTextContent('39,000,000')
 expect(screen.getByText('回看旧稿3900万元与9100万元差额：为什么不能继续沿用？').closest('details')).not.toHaveAttribute('open')
 expect(JSON.stringify(d)).toBe(before)
})
it('corrects the original period entry and folds the pre-correction interpretation without rewriting saved data',()=>{
 const d=structuredClone(period);const before=JSON.stringify(d)
 render(<STTwentyseventhPeriodFollowup data={d as unknown as TwentyseventhPeriodFollowup}/>)
 fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value:'603959'}})
 expect(screen.getByRole('complementary',{name:'百利赠与收款补证更正'})).toBeVisible()
 const old=screen.getByText('回看修正前旧稿：当时漏选了11月3日收款公告').closest('details')
 expect(old).not.toHaveAttribute('open')
 expect(old).toHaveTextContent('3900万元')
 expect(screen.getByText(/下方仍保留前轮签约/)).toHaveTextContent('不代表已加入11月3日收款公告的行情反应')
 expect(JSON.stringify(d)).toBe(before)
})

it('opens the recorded study through application navigation',()=>{
 render(<MemoryRouter initialEntries={['/learning']}><Routes><Route path="/learning" element={<STBailiReceiptUpdate/>}/><Route path="/runs" element={<h1>补证研究记录</h1>}/></Routes></MemoryRouter>)
 fireEvent.click(screen.getByText('新原件、旧口径与仍未关闭的缺口'))
 fireEvent.click(screen.getByRole('link',{name:'查看本次补证研究与验证记录 →'}))
 expect(screen.getByRole('heading',{name:'补证研究记录'})).toBeVisible()
})
