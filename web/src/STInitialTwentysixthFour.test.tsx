import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STInitialFour,type InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-twentysixth-four.json'
afterEach(cleanup)
it('shows uncertified returns as conflicts and preserves company evidence boundaries',()=>{
 render(<STInitialFour data={fixture as InitialFour} readableAmounts/>);
 expect(screen.getByText(/142 → 146\/150家/)).toBeVisible()
 const table=screen.getByRole('table',{name:'期初四家风险与同窗表现'})
 expect(within(table).getByText('报价口径冲突，暂不认证收益')).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'期初四家比较窗口'}),{target:{value:'early20'}})
 expect(within(table).getByText('报价口径冲突，暂不认证收益')).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'603838'}})
 expect(screen.getByText(/正式库存与原件名称均为\*ST四通/)).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'603869'}})
 expect(screen.getByText('来源有冲突：查看采用依据与保留的异值')).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'603843'}})
 expect(screen.getByText(/授权上限/)).toBeVisible()
})
