import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STSixteenthPeriodFollowup} from './STSixteenthPeriodFollowup'
import type {SixteenthPeriodFollowup} from './STSixteenthPeriodFollowup'
import fixture from './__fixtures__/sixteenth-period-followup.json'
afterEach(cleanup)
const data=fixture as SixteenthPeriodFollowup
const company=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value}})
const issue=(source:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘事项'}),{target:{value:data.chains.find(c=>c.source===source)!.chain}})
it('separates signed effectiveness from conditional full payment',()=>{
 render(<STSixteenthPeriodFollowup data={data}/>);issue('1225438035')
 expect(screen.getAllByText(/签章后生效/)[0]).toBeVisible()
 expect(screen.getAllByText(/两份重整计划均获法院批准后10工作日内/)[0]).toBeVisible()
})
it('updates cash repayment while preserving other execution cases',()=>{
 render(<STSixteenthPeriodFollowup data={data}/>);company('600289')
 expect(screen.getAllByText(/实收/)[0]).toBeVisible()
 expect(screen.getAllByText(/两宗恢复执行案件/)[0]).toBeVisible()
})
it('shows the original quarter values and penny differences without hiding them',()=>{
 render(<STSixteenthPeriodFollowup data={data}/> )
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
 expect(within(screen.getByRole('table',{name:'季度经营桥接'})).getByText(/报告值与差额有0.01元差异/)).toBeVisible()
 fireEvent.click(screen.getByText('精确金额差异，具体是哪两项？'))
 expect(screen.getByText(/报告单季-3534710.25元/)).toBeVisible()
 expect(screen.getByText(/报告单季-33144458.53元/)).toBeVisible()
})
it('shows the falling post-signing phase and pre-waiver rebound',()=>{
 render(<STSixteenthPeriodFollowup data={data}/> )
 fireEvent.click(screen.getByText('把行情分段，反转发生在哪一段？'))
 const table=screen.getByRole('table',{name:'共同阶段个股ST与大盘'})
 expect(within(table).getByText('-24.70%')).toBeVisible()
 expect(within(table).getByText('+29.15%')).toBeVisible()
 expect(screen.getByText(/早于首份8月28日豁免公告/)).toBeVisible()
})
