import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STThirteenthPeriodFollowup} from './STThirteenthPeriodFollowup'
import type {ThirteenthPeriodFollowup} from './STThirteenthPeriodFollowup'
import fixture from './__fixtures__/thirteenth-period-followup.json'
afterEach(cleanup)
const data=fixture as ThirteenthPeriodFollowup
const company=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value}})
const issue=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘事项'}),{target:{value}})
it('separates receipt and delivery from registration, with dash ratios preserved',()=>{
 render(<STThirteenthPeriodFollowup data={data}/> )
 expect(screen.getByText(/登记仍为后续手续/)).toBeVisible()
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
 fireEvent.click(screen.getByText('半年同比：哪些是报告值，哪些只是另算？'))
 expect(within(screen.getByRole('table',{name:'半年同比披露与计算'})).getAllByText('原表破折号')).toHaveLength(2)
})
it('keeps positive quarterly cash distinct from negative cumulative cash',()=>{
 render(<STThirteenthPeriodFollowup data={data}/>);company('600084')
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
 const table=screen.getByRole('table',{name:'季度经营桥接'})
 expect(within(table).getByText('515.27万元')).toBeVisible()
 expect(within(table).getByText('-1,861.19万元')).toBeVisible()
 expect(within(table).getByText('单季为差额推算')).toBeVisible()
})
it('distinguishes successful bidding from the other failed lot and company cash',()=>{
 render(<STThirteenthPeriodFollowup data={data}/>);company('600107')
 expect(screen.getByText(/450万股竞买成功与410万股流拍属于不同批次/)).toBeVisible()
 issue('600107-410万股流拍，是同一批成功股份吗')
 expect(screen.getByText(/410万与450万主体批次、法院和程序分开/,{selector:'section > p'})).toBeVisible()
})
it('does not turn reversal of a provision into a final judgment or receipt',()=>{
 render(<STThirteenthPeriodFollowup data={data}/>);company('600119')
 expect(screen.getByText(/会计入账和法律终局分别核/)).toBeVisible()
 issue('600119-冲回预计负债以后，利润与现金怎样')
 expect(screen.getByText(/入账冲回不当现金回款，也不由此推定案件生效/,{selector:'section > p'})).toBeVisible()
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
 expect(within(screen.getByRole('table',{name:'季度经营桥接'})).queryByText('单季为差额推算')).not.toBeInTheDocument()
 expect(screen.getByRole('link',{name:'三季报主要数据 · 第2页 ↗'})).toHaveAttribute('href',expect.stringContaining('#page=2'))
})
