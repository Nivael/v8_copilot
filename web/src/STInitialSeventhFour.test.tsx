import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STInitialFour} from './STInitialFour'
import type {InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-seventh-four.json'
afterEach(cleanup)
const data=fixture as InitialFour
it('compares early repair with the longer decline',()=>{
 render(<STInitialFour data={data} readableAmounts/>);expect(screen.getByText(/66 → 70\/150/)).toBeVisible();const t=screen.getByRole('table',{name:'期初四家风险与同窗表现'});expect(within(t).getByText('-20.74%')).toBeVisible();fireEvent.change(screen.getByRole('combobox',{name:'期初四家比较窗口'}),{target:{value:'early20'}});expect(within(t).getByText('+0.44%')).toBeVisible()
})
it('distinguishes penalty receipt from decision and automatic removal',()=>{
 render(<STInitialFour data={data}/>);expect(screen.getByText(/收到日不代替作出日/)).toBeVisible()
})
it('keeps historical thresholds and report-period balances explicit',()=>{
 render(<STInitialFour data={data}/>);fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'002485'}});expect(screen.getByText(/不能倒套后来3亿元门槛/)).toHaveTextContent('不能当作7月3日余额');fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'));expect(screen.getByText(/落款未确认（采用正式披露日）/)).toBeVisible()
})
it('keeps claims distinct from recognized compensation',()=>{
 render(<STInitialFour data={data}/>);fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'002501'}});expect(screen.getByText(/诉请不直接当损失/)).toBeVisible()
})
it('retains all 150 companies and 80 remaining gaps',()=>{
 render(<STInitialFour data={data}/>);fireEvent.click(screen.getByText('覆盖如何更新，哪些仍缺？'));const t=screen.getByRole('table',{name:'更新后的期初事实覆盖名单'});expect(within(t).getAllByRole('row')).toHaveLength(81);fireEvent.change(screen.getByRole('combobox',{name:'期初事实覆盖名单'}),{target:{value:'all'}});expect(within(t).getAllByRole('row')).toHaveLength(151)
})
