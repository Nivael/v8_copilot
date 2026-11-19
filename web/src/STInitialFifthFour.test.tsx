import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STInitialFour} from './STInitialFour'
import type {InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-fifth-four.json'
afterEach(cleanup)
const data=fixture as InitialFour
it('compares repairs with actual later outcomes and retains the counterexample',()=>{
 render(<STInitialFour data={data}/>);expect(screen.getByText(/58 → 62\/150/)).toBeVisible();const t=screen.getByRole('table',{name:'期初四家风险与同窗表现'});expect(within(t).getByText('+6.88%')).toBeVisible();expect(within(t).getByText('-33.36%')).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'期初四家比较窗口'}),{target:{value:'early20'}});expect(within(t).getByText('+6.05%')).toBeVisible()
})
it('retains all 150 and exposes the remaining 88 gaps',()=>{
 render(<STInitialFour data={data}/>);fireEvent.click(screen.getByText('覆盖如何更新，哪些仍缺？'));const t=screen.getByRole('table',{name:'更新后的期初事实覆盖名单'});expect(within(t).getAllByRole('row')).toHaveLength(89);fireEvent.change(screen.getByRole('combobox',{name:'期初事实覆盖名单'}),{target:{value:'all'}});expect(within(t).getAllByRole('row')).toHaveLength(151)
})

it('uses readable units while retaining exact evidence on demand',()=>{
 render(<STInitialFour data={data} readableAmounts/>);fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'002214'}});expect(screen.getByText(/扣除后营收约3.31亿元/)).toBeVisible();fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'));expect(screen.getByText(/精确数值与原披露表述/)).toHaveTextContent('330763727.44元')
})
