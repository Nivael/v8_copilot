import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STNineteenthPeriodFollowup,type NineteenthPeriodFollowup} from './STNineteenthPeriodFollowup'
import fixture from './__fixtures__/nineteenth-period-followup.json'
afterEach(cleanup)
const data=fixture as NineteenthPeriodFollowup
const company=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value}})
it('shows partial cash recovery without backdating the half-year balance',()=>{
 render(<STNineteenthPeriodFollowup data={data}/>);
 expect(screen.getByText(/8月11日收到6415号案执行款约104.72万元/)).toBeVisible()
 expect(screen.getAllByText(/不代表全部收回或警示解除/)[0]).toBeVisible()
})
it('keeps both exact values visible on demand for the 0.01 discrepancy',()=>{
 render(<STNineteenthPeriodFollowup data={data}/>);company('600581')
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
 fireEvent.click(screen.getByText('0.01元差异：查看原值与差额'))
 expect(screen.getByText(/报告单季-243278560.65元；累计减半年-243278560.64元/)).toBeVisible()
 expect(screen.getByRole('table',{name:'季度经营桥接'})).toHaveTextContent('报告值与差额有0.01元差异')
})
it('separates completed payment and retrial review while keeping common phases',()=>{
 render(<STNineteenthPeriodFollowup data={data}/>);company('600624')
 expect(screen.getAllByText(/立案审查不等于改判或撤销原判/)[0]).toBeVisible()
 fireEvent.click(screen.getByText('把行情分段，反转发生在哪一段？'))
 expect(screen.getByRole('table',{name:'共同阶段个股ST与大盘'})).toHaveTextContent('2026-10-30 → 2026-11-19')
})
