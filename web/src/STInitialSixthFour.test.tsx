import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STInitialFour} from './STInitialFour'
import type {InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-sixth-four.json'
afterEach(cleanup)
const data=fixture as InitialFour
it('preserves the partial-removal counterexample and both windows',()=>{
 render(<STInitialFour data={data} readableAmounts/>);expect(screen.getByText(/62 → 66\/150/)).toBeVisible();const t=screen.getByRole('table',{name:'期初四家风险与同窗表现'});expect(within(t).getByText('-33.65%')).toBeVisible();expect(within(t).getByText('-19.72%')).toBeVisible();fireEvent.change(screen.getByRole('combobox',{name:'期初四家比较窗口'}),{target:{value:'early20'}});expect(within(t).getByText('-18.27%')).toBeVisible()
})
it('does not treat a prior notice as the final penalty',()=>{
 render(<STInitialFour data={data}/>);expect(screen.getByText(/不把告知书当最终处罚决定/)).toBeVisible()
})
it('keeps old audit evidence remediation distinct from cash collection and new warning',()=>{
 render(<STInitialFour data={data}/>);fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'002227'}});expect(screen.getByText(/旧证据修复不等于新年度财务条件达标/)).toBeVisible();fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'));expect(screen.getByText(/专项落款4月17日/)).toHaveTextContent('不是同额现金到账')
})
it('updates Yunwang to approved partial removal while retaining other frozen accounts',()=>{
 render(<STInitialFour data={data}/>);fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'002306'}});expect(screen.getByText(/6月12日起已正式撤销/)).toHaveTextContent('新增一般户冻结')
})
it('keeps all 150 companies and the 84 remaining gaps',()=>{
 render(<STInitialFour data={data}/>);fireEvent.click(screen.getByText('覆盖如何更新，哪些仍缺？'));const t=screen.getByRole('table',{name:'更新后的期初事实覆盖名单'});expect(within(t).getAllByRole('row')).toHaveLength(85);fireEvent.change(screen.getByRole('combobox',{name:'期初事实覆盖名单'}),{target:{value:'all'}});expect(within(t).getAllByRole('row')).toHaveLength(151)
})
